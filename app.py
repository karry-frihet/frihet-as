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

/* 밝은 갈색 배경 + 진한 검정 글자 버튼 */
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
div.stButton > button:hover { background-color: #C5A478 !important; color: #000000 !important; }
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
else:
    st.markdown("<h1 style='text-align: center; color: #4B3621;'>Frihet AS 접수 시스템</h1>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ★ 가장 안전한 방식: 스트림릿 비밀 금고에서 키를 꺼내옵니다.
api_key = st.secrets["GEMINI_API_KEY"]

store_name = st.text_input("🏢 AS 접수 점포명을 입력하세요 (예시: 프리헷 강남점)")

st.markdown("---")
st.write("🎙️ **방법 1: 파일 업로드** (카톡 캡처나 음성)")
evidence_file = st.file_uploader("사진(png, jpg) 또는 음성(mp3, wav, m4a)", type=["png", "jpg", "jpeg", "mp3", "wav", "m4a"])

st.write("✍️ **방법 2: 텍스트 직접 입력**")
user_text = st.text_area("파일이 없다면 여기에 증상을 직접 적어주세요.", placeholder="예: 커피 머신에서 원두 추출이 안 되고 물만 나옵니다. 제빙기 얼음이 얼지 않아요.")
st.markdown("---")

# 실행 버튼
if st.button("🚀 AS 접수 시작하기"):
    if not store_name:
        st.warning("점포명을 입력해주세요!")
        st.stop()
    
    if not evidence_file and not user_text.strip():
        st.warning("증상을 확인할 수 있는 파일(사진/음성)을 올리거나 텍스트를 입력해주세요!")
        st.stop()

    genai.configure(api_key=api_key)
    model_flash = genai.GenerativeModel('gemini-2.5-flash') # 최신 엔진으로 세팅 완료

    with st.spinner("AI가 분석 중입니다..."):
        # PDF 정보 추출
        pdf_text = ""
        try:
            reader = PyPDF2.PdfReader("list.pdf")
            for page in reader.pages:
                pdf_text += page.extract_text() + "\n"
        except:
            pass
            
        pdf_prompt = f"{pdf_text}\n\n위 데이터에서 '{store_name}' 점포의 장비번호, 출고일자, 주소, 연락처, 담당 바이저 이름을 JSON으로 추출해."
        pdf_resp = model_flash.generate_content(pdf_prompt)
        store_info = parse_json(pdf_resp.text)
        supervisor_name = store_info.get("담당 바이저 이름", "")

        # 비상연락망 OCR
        supervisor_phone = "확인불가"
        if supervisor_name:
            try:
                contact_img = Image.open("contact.png")
                ocr_resp = model_flash.generate_content([contact_img, f"'{supervisor_name}'의 연락처 번호를 010-XXXX-XXXX 형식으로 말해줘."])
                supervisor_phone = ocr_resp.text.strip()
            except:
                pass

        # 증상 분석
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

        # 최종 출력 양식
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
