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

# 배경색 및 버튼 스타일 강제 지정 CSS
st.markdown("""
<style>
/* 전체 페이지 배경색 */
.stApp {
    background-color: #F5F0E6;
}

/* 텍스트 색상 고정 */
h1, h2, h3, h4, p, label, .stMarkdown, .stText {
    color: #4B3621 !important;
}

/* ★★★ 버튼 스타일 최종 병기 (가독성 극대화) ★★★ */
div.stButton > button:first-child {
    background-color: #4B3621 !important; /* 다크 브라운 */
    color: #FFFFFF !important;           /* ★무조건 선명한 흰색★ */
    border: 2px solid #4B3621 !important;
    border-radius: 12px !important;
    font-size: 22px !important;           /* 글자 크기 더 키움 */
    font-weight: 900 !important;          /* ★초강력 볼드★ */
    height: 4em !important;
    width: 100% !important;
    box-shadow: 0px 4px 10px rgba(0,0,0,0.2) !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}

/* 버튼 안에 있는 글자(Span)까지 강제로 흰색 지정 */
div.stButton > button:first-child span {
    color: #FFFFFF !important;
}

/* 호버 효과 */
div.stButton > button:hover {
    background-color: #3b2816 !important;
    border-color: #3b2816 !important;
    color: #FFFFFF !important;
}

/* 입력창 스타일 */
.stTextInput>div>div>input, .stTextArea>div>div>textarea {
    border: 1px solid #4B3621 !important;
}
</style>
""", unsafe_allow_html=True)

# 안전하게 JSON 텍스트 파싱하는 도구
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

# 상단 로고
logo_path = "브랜드-로고.png"
if os.path.exists(logo_path):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(logo_path, use_container_width=True)
else:
    st.markdown("<h1 style='text-align: center; color: #4B3621;'>Frihet AS 접수 시스템</h1>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# API 키 및 입력창
api_key = st.secrets["GEMINI_API_KEY"]
store_name = st.text_input("🏢 AS 접수 점포명을 입력하세요 (예시: 프리헷 강남점)")

st.markdown("---")
st.write("🎙️ **방법 1: 파일 업로드** (카톡 캡처나 음성)")
evidence_file = st.file_uploader("사진(png, jpg) 또는 음성(mp3, wav, m4a)", type=["png", "jpg", "jpeg", "mp3", "wav", "m4a"])

st.write("✍️ **방법 2: 텍스트 직접 입력**")
user_text = st.text_area("파일이 없다면 여기에 증상을 직접 적어주세요.", placeholder="예: 세탁기 3번 기기에서 소음이 발생하고 결제가 안 됩니다.")
st.markdown("---")

# 실행 버튼 (강화된 CSS 적용)
if st.button("🚀 AS 접수 시작하기"):
    if not store_name:
        st.warning("점포명을 입력해주세요!")
        st.stop()
    
    if not evidence_file and not user_text.strip():
        st.warning("증상을 확인할 수 있는 파일(사진/음성)을 올리거나 텍스트를 입력해주세요!")
        st.stop()

    genai.configure(api_key=api_key)
    model_flash = genai.GenerativeModel('gemini-1.5-flash')

    with st.spinner("AI가 분석 중입니다..."):
        # [단계 1] PDF 정보 추출
        pdf_text = ""
        reader = PyPDF2.PdfReader("list.pdf")
        for page in reader.pages:
            pdf_text += page.extract_text() + "\n"
            
        pdf_prompt = f"{pdf_text}\n\n위 데이터에서 '{store_name}' 점포의 장비번호, 출고일자, 주소, 연락처, 담당 바이저 이름을 JSON으로 추출해."
        pdf_resp = model_flash.generate_content(pdf_prompt)
        store_info = parse_json(pdf_resp.text)
        supervisor_name = store_info.get("담당 바이저 이름", "")

        # [단계 2] 비상연락망 OCR
        supervisor_phone = "확인불가"
        if supervisor_name:
            contact_img = Image.open("contact.png")
            ocr_resp = model_flash.generate_content([contact_img, f"'{supervisor_name}'의 연락처 번호만 010-XXXX-XXXX 형식으로 말해줘."])
            supervisor_phone = ocr_resp.text.strip()

        # [단계 3] 증상 분석
        symptom_text = ""
        request_text = ""
        
        if evidence_file:
            file_ext = evidence_file.name.split(".")[-1].lower()
            analysis_prompt = "AS 접수 자료야. '증상'과 '처리요청'을 JSON으로 요약해."
            
            if file_ext in ["png", "jpg", "jpeg"]:
                img = Image.open(evidence_file)
                resp = model_flash.generate_content([img, analysis_prompt])
            else:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp:
                    tmp.write(evidence_file.read())
                    uploaded_audio = genai.upload_file(path=tmp.name)
                    resp = model_flash.generate_content([uploaded_audio, analysis_prompt])
                    uploaded_audio.delete()
                    os.remove(tmp.name)
            
            parsed = parse_json(resp.text)
            symptom_text = parsed.get("증상", "")
            request_text = parsed.get("처리요청", "")
        
        if user_text.strip():
            if symptom_text:
                symptom_text += f" (추가입력: {user_text})"
            else:
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
