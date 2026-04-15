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
st.set_page_config(page_title="Frihet 무인카페 AS 접수", layout="centered")

st.markdown("""
<style>
.stApp { background-color: #F5F0E6; }
h1, h2, h3, h4, p, label, .stMarkdown, .stText { color: #4B3621 !important; }
.stTextInput>div>div>input, .stTextArea>div>div>textarea { border: 1px solid #4B3621 !important; }

/* 대표님 요청: 밝은 갈색 배경 + 진한 검정색 굵은 글씨 버튼 */
div.stButton > button:first-child {
    background-color: #D2B48C !important;
    color: #000000 !important;
    border: 2px solid #4B3621 !important;
    border-radius: 12px !important;
    font-size: 22px !important;           
    font-weight: 900 !important;
    height: 4em !important;
    width: 100% !important;
    box-shadow: 0px 4px 6px rgba(0,0,0,0.1) !important;
}
div.stButton > button:first-child span { color: #000000 !important; }
div.stButton > button:active { transform: translateY(2px) !important; box-shadow: none !important; }
</style>
""", unsafe_allow_html=True)

def parse_json(json_text):
    text = json_text.strip()
    text = re.sub(r'```json', '', text)
    text = re.sub(r'```', '', text)
    try:
        return json.loads(text)
    except:
        return {}

# ========================================================
# 2. 메인 UI
# ========================================================
logo_path = "브랜드-로고.png"
if os.path.exists(logo_path):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2: st.image(logo_path, use_container_width=True)

# 스트림릿 Secrets에서 키를 가져옵니다.
api_key = st.secrets["GEMINI_API_KEY"]

store_name = st.text_input("🏢 AS 접수 점포명을 입력하세요 (예시: 프리헷 강남점)")

st.markdown("---")
st.write("📸 **방법 1: 사진/음성 파일 업로드**")
evidence_file = st.file_uploader("카톡 캡처나 음성을 올려주세요", type=["png", "jpg", "jpeg", "mp3", "wav", "m4a"])

st.write("✍️ **방법 2: 텍스트 직접 입력**")
user_text = st.text_area("파일이 없다면 증상을 직접 적어주세요.", placeholder="예: 커피 머신에서 원두 추출이 안 되고 물만 나옵니다.")
st.markdown("---")

if st.button("🚀 AS 접수 시작하기"):
    if not store_name:
        st.warning("점포명을 입력해주세요!")
        st.stop()
    
    if not evidence_file and not user_text.strip():
        st.warning("증상을 확인할 수 있는 파일이나 텍스트를 입력해주세요!")
        st.stop()

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash') 

    with st.spinner("가맹점 리스트와 연락망을 대조하여 분석 중입니다..."):
        # [단계 1] PDF 정보 추출 (담당SV 검색 강화)
        pdf_text = ""
        try:
            reader = PyPDF2.PdfReader("list.pdf")
            for page in reader.pages:
                if page.extract_text(): pdf_text += page.extract_text() + "\n"
        except:
            st.error("list.pdf 파일을 읽을 수 없습니다.")
            st.stop()
            
        pdf_prompt = f"""
        다음 가맹점 데이터에서 '{store_name}' 점포의 정보를 찾아 아래 JSON 형식으로 추출해.
        특히 '담당SV' 또는 '관리자' 항목에 있는 이름을 찾아 '담당 바이저 이름'에 넣어줘.
        (예: 캐리, 태오, 브루노, 조비, 제임스 등)
        ★주의: 모든 값은 대괄호 [] 없이 깨끗한 문자열로만 응답해!

        {{
            "장비번호": "값",
            "출고일자": "값",
            "주소": "값",
            "연락처": "값",
            "담당 바이저 이름": "이름만"
        }}
        데이터:
        {pdf_text}
        """
        store_info = parse_json(model.generate_content(pdf_prompt).text)
        supervisor_name = store_info.get("담당 바이저 이름", "확인불가")

        # [단계 2] 비상연락망 이미지 OCR (이름 매칭 강화)
        supervisor_phone = "확인불가"
        if supervisor_name and supervisor_name != "확인불가":
            try:
                contact_img = Image.open("contact.png")
                ocr_resp = model.generate_content([contact_img, f"이 긴급연락망 이미지에서 '{supervisor_name}'의 전화번호를 찾아 번호만 010-XXXX-XXXX 형식으로 말해줘. (다른 설명 금지)"])
                supervisor_phone = ocr_resp.text.strip()
            except:
                pass

        # [단계 3] 증상 분석 및 최종 접수증 생성
        today = datetime.now().strftime("%Y년 %m월 %d일")
        
        final_prompt = f"""
        너는 프리헷 무인카페 AS 전문가야. 고객 증상을 분석해서 [지정된 양식]으로만 출력해. 
        마크다운 별표(**)나 인사말은 절대 쓰지 마!

        [지정된 양식]
        << 무인머신 AS접수 >>
        ▣ 접수일 : {today}
        ▣ 점포명 : {store_name}
        ▣ 장비번호 : {store_info.get('장비번호', '확인불가')}
        ▣ 출고일자 : {store_info.get('출고일자', '확인불가')}
        ▣ 연락처 : {store_info.get('연락처', '확인불가')}
        ▣ 담당 연락처 : {supervisor_phone}
        ▣ 주소 : {store_info.get('주소', '확인불가')}
        ▣ 증상 : (명확하게 요약)
        ▣ 처리요청 : (수리/점검 내용 요약)
        ▣ 특이사항 : 특이사항 없음

        설명내용: {user_text}
        """

        if evidence_file:
            file_ext = evidence_file.name.split(".")[-1].lower()
            if file_ext in ["png", "jpg", "jpeg"]:
                img = Image.open(evidence_file)
                resp = model.generate_content([img, final_prompt])
            else:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp:
                    tmp.write(evidence_file.read())
                    uploaded_audio = genai.upload_file(path=tmp.name)
                    resp = model.generate_content([uploaded_audio, final_prompt])
                    uploaded_audio.delete()
                    os.remove(tmp.name)
        else:
            resp = model.generate_content(final_prompt)

        st.success("🎉 프리헷 AS 접수증 작성이 완료되었습니다!")
        st.text_area("결과 복사하기", value=resp.text.strip(), height=350)
