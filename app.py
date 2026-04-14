import streamlit as st
import google.generativeai as genai
import PyPDF2
from PIL import Image
import json
import re
import tempfile
import os
from datetime import datetime

# ========================================================
# 1. 디자인 및 브랜드 톤앤매너 설정
# ========================================================
st.set_page_config(page_title="Frihet 무인머신 AS 접수", layout="centered")

# 배경색(베이지) 및 강조색(다크 브라운) 지정 CSS
st.markdown("""
<style>
/* 전체 페이지 배경색: 따뜻한 베이지 (#F5F0E6) */
.stApp {
    background-color: #F5F0E6;
}

/* 텍스트 및 기본 요소 테마 컬러: 다크 브라운 (#4B3621) */
h1, h2, h3, h4, p, label, .stMarkdown, .stText {
    color: #4B3621 !important;
}

/* 텍스트 입력창 테두리 색상 */
.stTextInput>div>div>input {
    border: 1px solid #4B3621 !important;
}

/* 클릭 버튼 스타일 (다크 브라운) */
.stButton>button {
    background-color: #4B3621;
    color: white !important;
    border: none;
    border-radius: 8px;
    font-weight: bold;
    width: 100%;
    padding: 10px;
}
.stButton>button:hover {
    background-color: #3b2816;
}

/* 결과 출력용 Text Area 스타일링 */
.stTextArea>div>div>textarea {
    border: 2px solid #4B3621 !important;
    background-color: white !important;
    font-family: inherit;
    font-size: 15px;
}

/* 업로더 영역 시각적 강조 */
[data-testid='stFileUploader'] {
    border: 2px dashed #4B3621 !important;
    border-radius: 10px;
    padding: 15px;
}
</style>
""", unsafe_allow_html=True)

# 안전하게 JSON 텍스트 파싱하는 도구 (Gemini 출력 정제)
def parse_json(json_text):
    text = json_text.strip()
    text = re.sub(r'```json', '', text)
    text = re.sub(r'```', '', text)
    try:
        return json.loads(text)
    except:
        return {}


# ========================================================
# 2. 메인 UI (웹 앱 화면 구축)
# ========================================================

# 상단 중앙에 로고 배치
logo_path = "브랜드-로고.png"
if os.path.exists(logo_path):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(logo_path, use_container_width=True)
else:
    st.markdown("<h1 style='text-align: center;'>Frihet AS 접수 시스템</h1>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# 필수 입력값 받기
api_key = st.text_input("🔑 Gemini API 키를 입력하세요 (안전하게 로컬에서만 사용됩니다)", type="password")
store_name = st.text_input("🏢 AS 접수 점포명을 입력하세요 (예시: 프리헷 강남점)")

st.write("🎙️ **카톡 캡처 사진**이나 **녹음 파일**을 올려주세요. AI가 자동으로 내용을 요약합니다.")
evidence_file = st.file_uploader("사진(png, jpg) 또는 음성(mp3, wav, m4a)", type=["png", "jpg", "jpeg", "mp3", "wav", "m4a"])

# 실행 버튼
if st.button("🚀 AS 자동 접수 시작하기"):
    # 누락된 파일이나 입력값 방어 코딩
    if not api_key:
        st.error("Gemini API 키를 먼저 입력해주세요!")
        st.stop()
    if not store_name:
        st.warning("점포명을 입력해주세요!")
        st.stop()
    if not evidence_file:
        st.warning("증상을 확인할 수 있는 파일(사진/음성)을 업로드해주세요!")
        st.stop()
    if not os.path.exists("list.pdf"):
        st.error("현재 폴더에 가맹점 리스트 문서인 'list.pdf' 파일이 없습니다. 준비해주세요!")
        st.stop()
    if not os.path.exists("contact.png"):
        st.error("현재 폴더에 비상연락망 이미지인 'contact.png' 파일이 없습니다. 준비해주세요!")
        st.stop()

    # 제미나이 초기 권한 설정
    genai.configure(api_key=api_key)
    
    # 두 가지 모델 모두 장점이 달라 목적별로 활용합니다.
    # Flash 모델: 일반 텍스트나 간단 문맹 분석에 매우 빠름
    # Pro 모델: 복잡한 카톡 대화요약이나 음성 분석에 높은 정확도
    model_flash = genai.GenerativeModel('gemini-2.5-flash')
    model_pro = genai.GenerativeModel('gemini-2.5-flash')

    with st.spinner("AI가 자료들을 스캔하고 분석중입니다. (잠시만 기다려주세요!)"):
        
        # ========================================================
        # [단계 1] 가맹점 PDF에서 점포 상세 정보 뽑아오기
        # ========================================================
        st.info("📄 가맹점 리스트(PDF)에서 주소와 담당 바이저를 찾고 있어요...")
        pdf_text = ""
        try:
            reader = PyPDF2.PdfReader("list.pdf")
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pdf_text += text + "\n"
        except Exception as e:
            st.error(f"PDF 파일 내용을 읽는데 실패했습니다: {e}")
            st.stop()
            
        pdf_prompt = f"""
        다음은 가맹점 정보가 담긴 문서 텍스트입니다.
        {pdf_text}
        
        여기서 '{store_name}' 점포의 정보를 찾아, 아래 5개 항목을 순수한 JSON 포맷으로 추출해주세요:
        {{
            "장비번호": "값",
            "출고일자": "값",
            "주소": "값",
            "연락처": "값",
            "담당 바이저 이름": "이름만 (SVOOO 등)"
        }}
        * 만약 텍스트에서 찾을 수 없는 값이 있다면, 해당 항목은 빈 문자열("")로 남겨주세요!
        * 코드 블록 기호(```json 등)는 절대 쓰지 말고 괄호 {{ }} 부분만 출력하세요.
        """
        
        pdf_resp = model_flash.generate_content(pdf_prompt)
        store_info = parse_json(pdf_resp.text)
        
        supervisor_name = store_info.get("담당 바이저 이름", "")

        # ========================================================
        # [단계 2] 비상연락망 이미지에서 해당 바이저 연락처 스캔(OCR)
        # ========================================================
        supervisor_phone = ""
        if supervisor_name:
            st.info(f"🔍 '{supervisor_name}' 담당자 연락처를 비상연락망 이미지에서 스캔하고 있어요...")
            try:
                contact_img = Image.open("contact.png")
                ocr_prompt = f"""
                비상 연락망 연락처 표기가 된 이미지 문서입니다.
                '{supervisor_name}'의 연락처(휴대폰 번호)를 찾아서 
                번호만 출력해주세요. (예: 010-1234-5678)
                찾을 수 없다면 '확인불가' 라고만 대답하세요.
                """
                ocr_resp = model_flash.generate_content([contact_img, ocr_prompt])
                supervisor_phone = ocr_resp.text.strip()
            except Exception as e:
                supervisor_phone = "이미지 스캔 오류"
        else:
            supervisor_phone = "이름을 찾지 못해 연락처 검색 불가"


        # ========================================================
        # [단계 3] 증상 파일(카톡 이미지 혹은 음성파일) AI 멀티모달 분석
        # ========================================================
        st.info("⚙️ 파트너님이 올리신 카톡 캡처/음성을 분석해서 증상을 파악하고 있어요...")
        symptom_text = ""
        request_text = ""
        
        file_ext = evidence_file.name.split(".")[-1].lower()
        
        if file_ext in ["png", "jpg", "jpeg"]:
            # 이미지(카톡 캡처 등)인 경우
            img_evidence = Image.open(evidence_file)
            analysis_prompt = """
            고객/가맹점주가 접수한 AS 문제를 나타내는 캡처 이미지 혹은 현장 사진입니다.
            이미지 안의 내용(텍스트 포함)을 파악해서 아래 항목으로 요약해주세요.
            
            순수한 JSON 형식으로만 답해주세요 (마크다운 기호 없이!):
            {
                "증상": "요약된 기기 오류 또는 문제 현상",
                "처리요청": "요약된 바라는 조치 사항이나 수리 요청 내용"
            }
            """
            analysis_resp = model_pro.generate_content([img_evidence, analysis_prompt])
            parsed = parse_json(analysis_resp.text)
            symptom_text = parsed.get("증상", "증상 파악 불가")
            request_text = parsed.get("처리요청", "요청 파악 불가")
            
        elif file_ext in ["mp3", "wav", "m4a"]:
            # 음성 파일인 경우 (Temp 파일 변환 후, Gemini File API 업로드 필요)
            st.info("🎵 음성파일 판독 중...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp:
                tmp.write(evidence_file.read())
                tmp_path = tmp.name
                
            try:
                uploaded_audio = genai.upload_file(path=tmp_path)
                analysis_prompt = """
                다음은 AS 접수를 위한 고객/가맹점주의 음성 녹음 파일입니다.
                내용(목소리)을 잘 듣고, '증상'과 '처리요청'을 정확하게 요약해주세요.
                
                순수한 JSON 형식으로만 답해주세요 (마크다운 기호 없이!):
                {
                    "증상": "요약된 기기 오류 또는 문제 현상",
                    "처리요청": "요약된 바라는 조치 사항이나 수리 요청 내용"
                }
                """
                analysis_resp = model_pro.generate_content([uploaded_audio, analysis_prompt])
                parsed = parse_json(analysis_resp.text)
                symptom_text = parsed.get("증상", "음성 파악 불가")
                request_text = parsed.get("처리요청", "요청 파악 불가")
                
                # 안전하게 서버상 파일 삭제
                uploaded_audio.delete()
            except Exception as e:
                st.error(f"음성 파일 분석 중 오류가 났습니다: {e}")
            finally:
                os.remove(tmp_path)

        # ========================================================
        # [단계 4] 최종 결과 양식 맞춰서 텍스트 렌더링하기
        # ========================================================
        today = datetime.now().strftime("%Y년 %m월 %d일")
        
        final_text = f"""<< 무인머신 AS접수 >>
▣ 접수일 : {today}
▣ 점포명 : {store_name}
▣ 장비번호 : {store_info.get('장비번호', '확인불가')}
▣ 출고일자 : {store_info.get('출고일자', '확인불가')}
▣ 연락처 : {store_info.get('연락처', '확인불가')}
▣ 담당 연락처 : {supervisor_phone}
▣ 주소 : {store_info.get('주소', '확인불가')}
▣ 증상 : {symptom_text}
▣ 처리요청 : {request_text}
▣ 특이사항 : """

        st.success("🎉 만세! AS 접수 문서 자동 작성이 완료되었습니다.")
        
        # 쉽게 복사할 수 있도록 높이가 여유로운 구역(Text Area)을 제공
        st.text_area("아래 출력된 내용을 복사해서 공유 및 전달하시면 됩니다.", value=final_text, height=350)
