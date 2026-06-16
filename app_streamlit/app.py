import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st
from PIL import Image

from utils.data_loader import load_policies
from utils.loading_overlay import show_policy_loading
from views.home_page import render_home_page
from views.search_page import render_search_page
from views.guide_page import render_guide_page
from views.chatbot_page import render_chatbot_page

APP_VERSION = "v1.5"
LOGO_PATH = Path(__file__).resolve().parents[1] / "docs" / "images" / "home_logo.png"
STYLE_PATH = Path(__file__).resolve().parent / "styles" / "style.css"


@lru_cache(maxsize=8)
def _load_text_file(path_text, modified_at):
    return Path(path_text).read_text(encoding="utf-8")


@lru_cache(maxsize=8)
def _load_logo_data_uri(path_text, modified_at):
    return (
        "data:image/png;base64,"
        + base64.b64encode(Path(path_text).read_bytes()).decode("ascii")
    )


@lru_cache(maxsize=4)
def _load_page_icon(path_text, modified_at):
    return Image.open(path_text).copy()


LOGO_STAMP = LOGO_PATH.stat().st_mtime_ns
STYLE_STAMP = STYLE_PATH.stat().st_mtime_ns
LOGO_DATA_URI = _load_logo_data_uri(str(LOGO_PATH), LOGO_STAMP)

# -----------------------------------
# 기본 설정
# -----------------------------------

st.set_page_config(
    page_title="이젠, 안쉼",
    page_icon=_load_page_icon(str(LOGO_PATH), LOGO_STAMP),
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------------
# CSS 로드
# -----------------------------------

st.markdown(
    f"<style>{_load_text_file(str(STYLE_PATH), STYLE_STAMP)}</style>",
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
# 세션
# -----------------------------------

if "page" not in st.session_state:
    st.session_state.page = "홈"
elif st.session_state.page == "상세 분석":
    st.session_state.page = "추천 결과"

if "has_searched" not in st.session_state:
    st.session_state.has_searched = False

if st.session_state.get("cache_version") != APP_VERSION:
    st.cache_data.clear()
    st.session_state.cache_version = APP_VERSION

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
# 데이터
# -----------------------------------

def _go_to_page(page):
    if st.session_state.page != page:
        st.session_state.page = page


# -----------------------------------
# 상단 로고
# -----------------------------------

st.markdown(
    f"""
    <style>
    .st-key-brand_home_button button::before {{
        background-image: url("{LOGO_DATA_URI}");
    }}
    </style>
    """,
    unsafe_allow_html=True
)

pages = [
    "추천 결과",
    "신청 가이드",
    "챗봇"
]


def _page_needs_policies():
    current_page = st.session_state.page
    has_searched = st.session_state.get("has_searched", False)
    if current_page == "챗봇":
        return False
    if current_page in ("추천 결과", "신청 가이드") and not has_searched:
        return False
    return True


needs_policies = _page_needs_policies()
initial_loading_slot = None

if needs_policies and not st.session_state.get("initial_loading_shown", False):
    initial_loading_slot = st.empty()
    show_policy_loading(initial_loading_slot)

policies = load_policies() if needs_policies else []

if initial_loading_slot is not None:
    initial_loading_slot.empty()
    st.session_state.initial_loading_shown = True

with st.container(key="site_header"):
    tabs = st.columns([2.4, 1, 1, 1, 0.38], vertical_alignment="center")

    with tabs[0]:
        st.button(
            "이젠, 안쉼",
            key="brand_home_button",
            on_click=_go_to_page,
            args=("홈",)
        )

    for idx, page in enumerate(pages):

        with tabs[idx + 1]:

            button_type = (
                "primary"
                if st.session_state.page == page
                else "secondary"
            )

            st.button(
                page,
                width="stretch",
                type=button_type,
                on_click=_go_to_page,
                args=(page,)
            )

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

elif st.session_state.page == "신청 가이드":
    render_guide_page(policies)

elif st.session_state.page == "챗봇":
    render_chatbot_page(policies)
