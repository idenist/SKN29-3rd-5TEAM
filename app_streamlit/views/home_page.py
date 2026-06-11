import streamlit as st

from utils.condition_parser import parse_user_query
from utils.html_renderer import render_html


INTERESTS = ["취업", "교육", "창업", "주거", "금융", "복지"]
EXAMPLE_QUERIES = [
    "부산 청년 월세 지원 알려줘",
    "취업 준비생 지원 정책 알려줘",
    "중소기업 재직자 청년 정책 알려줘",
]


def _apply_query_and_open_results(user_query):
    extracted = parse_user_query(user_query)
    profile = st.session_state.profile.copy()

    for key in ("age", "region", "income", "job_status"):
        if extracted[key] is not None:
            profile[key] = extracted[key]

    if extracted["interest"]:
        profile["interest"] = extracted["interest"]

    st.session_state.profile = profile
    st.session_state.extracted_conditions = extracted
    st.session_state.result_query = user_query
    st.session_state.result_query_input = user_query
    st.session_state.filter_age = profile["age"]
    st.session_state.filter_region = profile["region"]
    st.session_state.filter_income = profile["income"]
    st.session_state.filter_job_status = profile["job_status"]
    st.session_state.filter_housing_status = profile["housing_status"]
    for interest in INTERESTS:
        st.session_state[f"filter_interest_{interest}"] = (
            interest in profile["interest"]
        )
    st.session_state.page = "추천 결과"
    st.rerun()


def render_home_page():
    html = """
<div class="hero-section">
    <div class="hero-layout">

        <div class="hero-left">
            <div class="service-badge">청년 지원 정보 통합 탐색 에이전트</div>

            <div class="hero-title">
                이젠, 안쉼
            </div>

            <div class="hero-subtitle">
                자연어로 입력하면<br>
                나에게 맞는 청년 정책을 추천해드립니다.
            </div>

            <div class="hero-desc">
                나이, 지역, 소득, 직업 상태를 입력하면 받을 수 있는 정책과 신청 정보를 찾아드려요.
            </div>
        </div>

        <div class="hero-illust">
            🔎
        </div>

    </div>
</div>
"""
    render_html(html)

    col1, col2 = st.columns([4, 1])

    with col1:
        user_query = st.text_area(
            "자연어 입력",
            value="27살, 서울 거주, 연소득 3000만원, 중소기업 재직자야. 받을 수 있는 청년 정책 알려줘.",
            height=110,
            label_visibility="collapsed",
            key="home_user_query"
        )

    with col2:
        st.write("")
        st.write("")
        extract_clicked = st.button(
            "조건 추출하기",
            use_container_width=True,
            type="primary"
        )

    if extract_clicked:
        _apply_query_and_open_results(user_query)

    render_html("""
<div class="example-area">
    <div class="example-title">예시로 입력해보기</div>
</div>
""")

    example_columns = st.columns(len(EXAMPLE_QUERIES))
    for column, example_query in zip(example_columns, EXAMPLE_QUERIES):
        with column:
            if st.button(
                example_query,
                key=f"example_query_{example_query}",
                use_container_width=True
            ):
                _apply_query_and_open_results(example_query)

    flow_html = """
<div class="flow-section">
    <div class="section-title">서비스 흐름</div>

    <div class="flow-grid">
        <div class="flow-item">
            <div class="flow-icon">📋</div>
            <div class="flow-name">1. 입력 및 조건 추출</div>
            <div class="flow-desc">
                자연어 입력에서<br>
                나이, 지역, 소득, 상태를 추출
            </div>
        </div>

        <div class="arrow">→</div>

        <div class="flow-item">
            <div class="flow-icon">🧠</div>
            <div class="flow-name">2. 정책 추천 및 자격 판단</div>
            <div class="flow-desc">
                정책 조건과 비교하고<br>
                적합도 점수를 계산
            </div>
        </div>

        <div class="arrow">→</div>

        <div class="flow-item">
            <div class="flow-icon">📄</div>
            <div class="flow-name">3. 최종 출력 및 안내</div>
            <div class="flow-desc">
                신청 정보, 필요 서류,<br>
                링크와 유의사항 제공
            </div>
        </div>
    </div>
</div>
"""
    render_html(flow_html)
