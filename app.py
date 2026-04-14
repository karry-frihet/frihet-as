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

# 배경색(베이지) 및 브랜드 색상(다크 브라운) 지정 CSS
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
.stTextInput>div>div>input, .stTextArea>div>div>textarea {
    border: 1px solid #4B3621 !important;
}

/* ★★★ 버튼 스타일 최종 수정: 프리헷 로고 색상(다크 브라운), 글자 흰색 굵게 ★★★ */
.stButton>button {
    background-color: #4B3621 !important; /* 프리헷 로고 다크 브라운 색상 */
    color: #ffffff !important;           /* 완전 선명한 흰색 글자 */
    border: none;
    border-radius: 8px;
    font-size: 20px !important;           /* 글자 크기 키움 */
    font-weight: bold !important;          /* ★★★ 볼드하게 ★★★ */
    width: 100%;
    padding: 15px;
    margin-top: 10px;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.3); /* 가독성을 위한 약간의 그림자 */
}
.stButton>button:hover {
    background-color: #3b2816 !important; /* 호버 시 약간 더 어둡게 */
    color: #ffffff !important;
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
    st.markdown("<h1 style='text-align: center; color: #4B3621;'>Frihet AS 접수 시스템</h1>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# 필수 입력값 받기
# 보안을 위해 Secrets에서 API 키를 가져옵니다.
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("설정(Secrets)에서 'GEMINI_API_KEY'가 누락되었습니다.")
    st.stop()

store_name = st.text_input("🏢 AS 접수 점포명을 입력하세요 (예시: 프리헷 강남점)")

st.markdown("---")
st.write("🎙️ **방법 1: 파일 업로드** (카톡 캡처나 음성)")
evidence_file = st.file_uploader("사진(png, jpg) 또는 음성(mp3, wav, m4a)", type=["png", "jpg", "jpeg", "mp3", "wav", "m4a"])

st.write("✍️ **방법 2: 텍스트 직접 입력**")
user_text = st.text_area("파일이 없다면 여기에 증상을 직접 적어주세요.", placeholder="예: 세탁기 3번 기기에서 소음이 발생하고 결제가 안 됩니다.")
st.markdown("---")

# 실행 버튼 (개선된 스타일 적용됨)
if st.button("🚀 AS 접수 시작하기"):
    # 누락된 입력값 방어 코딩
    if not store_name:
        st.warning("점포명을 입력해주세요!")
        st.stop()
    
    # 파일도 없고 텍스트도 없는 경우 차단
    if not evidence_file and not user_text.strip():
        st.warning("증상을 확인할 수 있는 파일(사진/음성)을 올리거나 텍스트를 입력해주세요!")
        st.stop()

    if not os.path.exists("list.pdf"):
        st.error("현재 폴더에 'list.pdf' 파일이 없습니다. 가맹점 리스트 문서를 준비해주세요.")
        st.stop()
    if not os.path.exists("contact.png"):
        st.error("현재 폴더에 'contact.png' 파일이 없습니다. 비상연락망 이미지를 준비해주세요.")
        st.stop()

    # 제미나이 초기 권한 설정
    genai.configure(api_key=api_key)
    model_flash = genai.GenerativeModel('gemini-1.5-flash') # 최신 모델로 유지

    with st.spinner("AI가 자료들을 스캔하고 분석중입니다. (잠시만 기다려주세요!)"):
        
        # [단계 1] 가맹점 PDF 정보 추출
        pdf_text = ""
        try:
            reader = PyPDF2.PdfReader("list.pdf")
            for page in reader.pages:
                text = page.extract_text()
                if text: pdf_text += text + "\n"
        except Exception as e:
            st.error(f"list.pdf 분석 실패: {e}")
            st.stop()
            
        pdf_prompt = f"{pdf_text}\n\n위 데이터에서 '{store_name}' 점포의 장비번호, 출고일자, 주소, 연락처, 담당 바이저 이름을 JSON으로 추출해."
        pdf_resp = model_flash.generate_content(pdf_prompt)
        store_info = parse_json(pdf_resp.text)
        supervisor_name = store_info.get("담당 바이저 이름", "")

        # [단계 2] 비상연락망 OCR
        supervisor_phone = "확인불가"
        if supervisor_name:
            try:
                contact_img = Image.open("contact.png")
                ocr_resp = model_flash.generate_content([contact_img, f"'{supervisor_name}'의 연락처 번호만 말해줘. (010-XXXX-XXXX 형식)"])
                supervisor_phone = ocr_resp.text.strip()
            except Exception as e:
                supervisor_phone = "연락처 스캔 실패"

        # [단계 3] 증상 분석 (파일 또는 텍스트)
        symptom_text = ""
        request_text = ""
        
        # 1순위: 파일 분석
        if evidence_file:
            file_ext = evidence_file.name.split(".")[-1].lower()
            analysis_prompt = "AS 접수 자료야. '증상'과 '처리요청'을 JSON으로 요약해."
            
            try:
                if file_ext in ["png", "jpg", "jpeg"]:
                    img = Image.open(evidence_file)
                    resp = model_flash.generate_content([img, analysis_prompt])
                else: # 음성 파일
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp:
                        tmp.write(evidence_file.read())
                        uploaded_audio = genai.upload_file(path=tmp.name)
                        resp = model_flash.generate_content([uploaded_audio, analysis_prompt])
                        uploaded_audio.delete()
                        os.remove(tmp.name)
                
                parsed = parse_json(resp.text)
                symptom_text = parsed.get("증상", "")
                request_text = parsed.get("처리요청", "")
            except Exception as e:
                st.error(f"파일 분석 실패: {e}")
        
        # 2순위: 텍스트 입력이 있다면 내용 보강/대체
        if user_text.strip():
            # 파일 분석 내용이 있을 경우 뒤에 붙임
            if symptom_text:
                symptom_text += f" (추가입력: {user_text})"
                if not request_text: request_text = "현장 확인 및 수리 요청"
            else: # 파일 없이 텍스트로만 분석
                symptom_text = user_text
                request_text = "현장 확인 및 수리 요청"

        # [단계 4] 최종 출력
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

        st.success("🎉 AS 접수 문서 작성이 완료되었습니다.")
        st.text_area("결과 복사하기", value=final_text, height=350)
