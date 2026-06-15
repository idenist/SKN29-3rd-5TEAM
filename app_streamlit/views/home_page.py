import streamlit as st

from utils.condition_parser import parse_user_query
from utils.html_renderer import render_html
from utils.api_client import extract_conditions_from_backend

INTERESTS = ["취업", "교육", "창업", "주거", "금융", "복지"]
EXAMPLE_QUERIES = [
    "월세 지원 정책 찾아줘",
    "취업 준비 지원 알려줘",
    "창업 지원사업 있어?",
    "교육비 지원 받을 수 있어?",
]


def _apply_query_and_open_results(user_query):
    extracted = parse_user_query(user_query)

    try:
        backend_extracted = extract_conditions_from_backend(user_query)

        for key in ("age", "region", "income", "job_status", "housing_status"):
            if backend_extracted.get(key) is not None:
                extracted[key] = backend_extracted[key]

        if backend_extracted.get("interest"):
            extracted["interest"] = backend_extracted["interest"]

    except Exception:
        st.toast("AI 조건 추출에 실패해 기본 조건 추출을 사용합니다.")

    profile = st.session_state.profile.copy()

    for key in ("age", "region", "income", "job_status", "housing_status"):
        if extracted.get(key) is not None:
            profile[key] = extracted[key]

    if extracted.get("interest"):
        profile["interest"] = extracted["interest"]

    # 여기부터가 현재 빠진 부분
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

    st.session_state.has_searched = True
    st.session_state.page = "추천 결과"
    st.rerun()
def render_home_page(policies):
    category_count = len({
        policy["category"]
        for policy in policies
        if policy.get("category")
    })
    organization_count = len({
        policy["organization"]
        for policy in policies
        if policy.get("organization")
        and policy["organization"] != "기관 정보 없음"
    })

    html = """
<div class="home-page-marker"></div>
<div class="hero-section">
    <div class="hero-glow hero-glow-one"></div>
    <div class="hero-glow hero-glow-two"></div>
    <div class="hero-content">
        <div class="service-badge">
            <span class="badge-spark">✦</span>
            RAG 기반 AI 청년정책 추천 서비스
        </div>
        <h1 class="hero-title">
            청년정책,<br>
            <span>헤매지 말고 물어보세요.</span>
        </h1>
        <p class="hero-desc">
            나이, 지역, 상황을 입력하면 지금 받을 수 있는 청년정책을 찾아드립니다.
        </p>
        <div class="hero-search-label">
            <span>⌕</span>
            궁금한 내용을 입력하세요
        </div>
    </div>
</div>
"""
    render_html(html)

    search_shell = st.container()
    with search_shell:
        col1, col2 = st.columns([4.5, 1.55], vertical_alignment="center")

        with col1:
            user_query = st.text_input(
                "자연어 입력",
                placeholder="예: 서울 사는 25살 취준생인데 받을 수 있는 정책 알려줘",
                label_visibility="collapsed",
                key="home_user_query"
            )

        with col2:
            extract_clicked = st.button(
                "✦ AI에게 물어보기",
                width="stretch",
                type="primary",
                key="home_search_button"
            )

    if extract_clicked:
        if user_query.strip():
            _apply_query_and_open_results(user_query)
        else:
            st.toast("궁금한 정책이나 현재 상황을 입력해 주세요.")

    example_columns = st.columns(len(EXAMPLE_QUERIES))
    for column, example_query in zip(example_columns, EXAMPLE_QUERIES):
        with column:
            if st.button(
                example_query,
                key=f"example_query_{example_query}",
                width="stretch"
            ):
                _apply_query_and_open_results(example_query)

    stats_html = f"""
<div class="home-stats">
    <div class="stat-item">
        <div class="stat-value">{len(policies):,}</div>
        <div class="stat-label">통합 지원 정보</div>
    </div>
    <div class="stat-item">
        <div class="stat-value">{organization_count:,}</div>
        <div class="stat-label">정책 제공 기관</div>
    </div>
    <div class="stat-item">
        <div class="stat-value">{category_count}개</div>
        <div class="stat-label">맞춤 지원 분야</div>
    </div>
</div>
<div class="home-intro">
    <div class="eyebrow">HOW IT WORKS</div>
    <div class="section-title">복잡한 정책 탐색을 더 간단하게</div>
    <div class="intro-copy">한 문장으로 질문하면 조건을 이해하고, 관련 정책과 신청 정보를 연결합니다.</div>
</div>
<div class="flow-section">
    <div class="flow-grid">
        <div class="flow-item">
            <div class="flow-number">01</div>
            <div class="flow-icon">⌨</div>
            <div class="flow-name">상황을 알려주세요</div>
            <div class="flow-desc">나이, 지역, 관심 분야를<br>입력하세요.</div>
        </div>
        <div class="arrow">→</div>
        <div class="flow-item">
            <div class="flow-number">02</div>
            <div class="flow-icon">✦</div>
            <div class="flow-name">AI가 조건을 분석해요</div>
            <div class="flow-desc">질문에서 핵심 조건을 찾고<br>지원 정보를 비교합니다.</div>
        </div>
        <div class="arrow">→</div>
        <div class="flow-item">
            <div class="flow-number">03</div>
            <div class="flow-icon">✓</div>
            <div class="flow-name">맞춤 정책을 확인하세요</div>
            <div class="flow-desc">추천 이유부터 신청 링크까지<br>한눈에 확인할 수 있어요.</div>
        </div>
    </div>
</div>
"""
    render_html(stats_html)
