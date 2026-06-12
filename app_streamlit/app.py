import base64
from pathlib import Path

import streamlit as st
from PIL import Image

from utils.data_loader import load_policies
from utils.html_renderer import render_html
from views.home_page import render_home_page
from views.search_page import render_search_page
from views.detail_page import render_detail_page
from views.guide_page import render_guide_page
from views.chatbot_page import render_chatbot_page

APP_VERSION = "v1.2"
LOGO_PATH = Path(__file__).resolve().parents[1] / "KakaoTalk_20260612_161223810.png"
LOGO_DATA_URI = (
    "data:image/png;base64,"
    + base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
)

# -----------------------------------
# 기본 설정
# -----------------------------------

st.set_page_config(
    page_title="이젠, 안쉼",
    page_icon=Image.open(LOGO_PATH),
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------------
# CSS 로드
# -----------------------------------

with open("styles/style.css", encoding="utf-8") as f:
    st.markdown(
        f"<style>{f.read()}</style>",
        unsafe_allow_html=True
    )

# -----------------------------------
# Streamlit 기본 UI 제거
# -----------------------------------

st.markdown("""
<style>
#MainMenu {
    visibility:hidden;
}

footer {
    visibility:hidden;
}

header {
    visibility:hidden;
}

[data-testid="stToolbar"] {
    display:none;
}

[data-testid="stDecoration"] {
    display:none;
}

[data-testid="stStatusWidget"] {
    display:none;
}

[data-testid="collapsedControl"] {
    display:none;
}

div[data-testid="stToolbar"]{
    display:none;
}

button[kind="header"]{
    display:none;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------
# 데이터
# -----------------------------------

policies = load_policies()

# -----------------------------------
# 세션
# -----------------------------------

if "page" not in st.session_state:
    st.session_state.page = "홈"

if "has_searched" not in st.session_state:
    st.session_state.has_searched = False

if "profile" not in st.session_state:
    st.session_state.profile = {
        "age": 27,
        "region": "서울",
        "income": 3000,
        "job_status": "중소기업 재직자",
        "housing_status": "월세",
        "interest": []
    }

# -----------------------------------
# 상단 로고
# -----------------------------------

render_html("""
<div class="top-header">
    <div class="brand">
        <div class="brand-icon">
            <img src="{logo_data_uri}" alt="이젠, 안쉼 로고">
        </div>

        <div>
            <div class="brand-title">
                이젠, 안쉼
            </div>

            <div class="brand-sub">
                청년 지원 정보 통합 탐색 에이전트
            </div>
        </div>
    </div>
</div>
""".format(logo_data_uri=LOGO_DATA_URI))

# -----------------------------------
# 네비게이션
# -----------------------------------

pages = [
    "홈",
    "추천 결과",
    "상세 분석",
    "신청 가이드",
    "챗봇"
]

with st.container(key="main_navigation"):
    tabs = st.columns([1, 1, 1, 1, 1, 0.38], vertical_alignment="center")

    for idx, page in enumerate(pages):

        with tabs[idx]:

            button_type = (
                "primary"
                if st.session_state.page == page
                else "secondary"
            )

            if st.button(
                page,
                width="stretch",
                type=button_type
            ):
                st.session_state.page = page
                st.rerun()

    with tabs[-1]:
        st.markdown(
            f'<span class="app-version">{APP_VERSION}</span>',
            unsafe_allow_html=True
        )

st.divider()

# -----------------------------------
# 페이지 렌더링
# -----------------------------------

if st.session_state.page == "홈":
    render_home_page(policies)

elif st.session_state.page == "추천 결과":
    render_search_page(policies)

elif st.session_state.page == "상세 분석":
    render_detail_page(policies)

elif st.session_state.page == "신청 가이드":
    render_guide_page(policies)

elif st.session_state.page == "챗봇":
    render_chatbot_page(policies)
