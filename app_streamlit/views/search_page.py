from datetime import date, datetime
from html import escape
import re

import streamlit as st

from utils.condition_parser import parse_user_query
from utils.html_renderer import render_html


REGIONS = ["서울", "부산", "대구", "인천", "광주", "대전", "경기", "기타"]
JOB_STATUSES = ["구직자", "재직자", "중소기업 재직자", "프리랜서", "예비창업자", "사업자", "학생"]
HOUSING_STATUSES = ["월세", "전세", "자가", "무주택", "기타"]
INTERESTS = ["취업", "교육", "창업", "주거", "금융", "복지"]
RESULT_LIMIT = 30


def _is_closed_policy(policy, today=None):
    status = str(policy.get("status", "")).strip()
    if status in {"마감", "신청 마감", "접수 마감"}:
        return True

    period = str(policy.get("period", ""))
    dates = re.findall(r"\d{4}[.-]\d{2}[.-]\d{2}", period)
    if not dates:
        return False

    deadline = datetime.strptime(
        dates[-1].replace("-", "."),
        "%Y.%m.%d"
    ).date()
    return deadline < (today or date.today())


def _sync_filter_widgets(profile):
    st.session_state.filter_age = profile["age"]
    st.session_state.filter_region = profile["region"]
    st.session_state.filter_income = profile["income"]
    st.session_state.filter_job_status = profile["job_status"]
    st.session_state.filter_housing_status = profile["housing_status"]
    for interest in INTERESTS:
        st.session_state[f"filter_interest_{interest}"] = (
            interest in profile["interest"]
        )


def _matches_age(policy, age):
    try:
        age_min = int(policy["age_min"]) if policy["age_min"] else None
        age_max = int(policy["age_max"]) if policy["age_max"] else None
    except ValueError:
        return True

    return (age_min is None or age >= age_min) and (age_max is None or age <= age_max)


def _matches_region(policy, region):
    policy_region = policy["region"]
    return policy_region == "전국" or region in policy_region


def _relevance_score(policy, query):
    score = policy["score"]
    keywords = {
        token.lower()
        for token in re.findall(r"[가-힣A-Za-z0-9]+", query)
        if len(token) >= 2
    }
    score += sum(20 for keyword in keywords if keyword in policy["search_text"])
    return score


def _external_link(label, url, class_name):
    if not url:
        return ""

    return (
        f'<a class="{class_name}" href="{escape(url, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer">{label}</a>'
    )


def _shorten(text, limit):
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."


def render_search_page(policies):
    render_html("""
<div class="search-page-marker"></div>
<div class="search-layout">
    <div class="left-panel">
        <div class="side-title">추천 조건</div>
        <div class="side-sub">추출된 조건을 확인하고 결과와 함께 수정하세요</div>

        <div class="side-label">자연어 다시 검색</div>
</div>
""")

    left, right = st.columns([1.05, 4])

    with left:
        profile = st.session_state.profile
        query = st.session_state.get(
            "result_query",
            "27살, 서울 거주, 연소득 3000만원, 중소기업 재직자야."
        )
        st.session_state.setdefault("result_query_input", query)
        st.session_state.setdefault("filter_age", profile["age"])
        st.session_state.setdefault("filter_region", profile["region"])
        st.session_state.setdefault("filter_income", profile["income"])
        st.session_state.setdefault("filter_job_status", profile["job_status"])
        st.session_state.setdefault("filter_housing_status", profile["housing_status"])
        for interest in INTERESTS:
            st.session_state.setdefault(
                f"filter_interest_{interest}",
                interest in profile["interest"]
            )

        keyword = st.text_input(
            "검색어",
            label_visibility="collapsed",
            key="result_query_input"
        )

        if st.button("조건 다시 추출", width="stretch"):
            extracted = parse_user_query(keyword)
            updated_profile = profile.copy()

            for key in ("age", "region", "income", "job_status"):
                if extracted[key] is not None:
                    updated_profile[key] = extracted[key]

            if extracted["interest"]:
                updated_profile["interest"] = extracted["interest"]

            st.session_state.profile = updated_profile
            st.session_state.extracted_conditions = extracted
            st.session_state.result_query = keyword
            _sync_filter_widgets(updated_profile)
            st.rerun()

        st.caption("예: 서울 사는 28살 월세 지원 정책 알려줘")

        st.divider()

        st.markdown("### 조건 입력 필터")

        with st.form("recommendation_filter_form"):
            age = st.number_input(
                "나이",
                min_value=15,
                max_value=80,
                key="filter_age"
            )
            region = st.selectbox(
                "지역",
                REGIONS,
                key="filter_region"
            )
            income = st.number_input(
                "연소득 (만원)",
                min_value=0,
                max_value=20000,
                step=100,
                key="filter_income"
            )
            job_status = st.selectbox(
                "현재 상태",
                JOB_STATUSES,
                key="filter_job_status"
            )
            housing_status = st.selectbox(
                "주거 상태",
                HOUSING_STATUSES,
                key="filter_housing_status"
            )
            st.markdown('<div class="filter-field-label">관심 분야</div>', unsafe_allow_html=True)
            interest = []
            for row_start in range(0, len(INTERESTS), 2):
                interest_columns = st.columns(2)
                for column, interest_name in zip(
                    interest_columns,
                    INTERESTS[row_start:row_start + 2]
                ):
                    with column:
                        if st.checkbox(
                            interest_name,
                            key=f"filter_interest_{interest_name}"
                        ):
                            interest.append(interest_name)

            filter_submitted = st.form_submit_button(
                "조건 적용",
                width="stretch",
                type="primary"
            )

        if filter_submitted:
            st.session_state.profile = {
                "age": age,
                "region": region,
                "income": income,
                "job_status": job_status,
                "housing_status": housing_status,
                "interest": interest
            }
            st.rerun()

        render_html("""
<div class="info-box" style="margin-top:24px;">
    <b>조건 입력 팁</b><br>
    · 자연어에서 추출된 값이 기본으로 설정됩니다.<br>
    · 결과를 보면서 조건을 수정할 수 있습니다.
</div>
""")

    with right:
        profile = st.session_state.profile
        selected_interests = profile["interest"]
        exclude_closed = st.session_state.get("exclude_closed_policies", True)
        filtered_policies = [
            policy for policy in policies
            if (not selected_interests or policy["category"] in selected_interests)
            and _matches_age(policy, profile["age"])
            and _matches_region(policy, profile["region"])
        ]
        if exclude_closed:
            filtered_policies = [
                policy for policy in filtered_policies
                if not _is_closed_policy(policy)
            ]
        filtered_policies.sort(
            key=lambda policy: _relevance_score(policy, keyword),
            reverse=True
        )
        visible_policies = filtered_policies[:RESULT_LIMIT]
        st.session_state.recommended_policy_ids = [
            policy["id"] for policy in visible_policies
        ]
        interest_text = ", ".join(selected_interests) if selected_interests else "전체"
        condition_summary = (
            f"{profile['age']}세 · {profile['region']} · "
            f"연소득 {profile['income']:,}만원 · {profile['job_status']} · "
            f"{profile['housing_status']} · {interest_text}"
        )

        render_html(f"""
<div class="search-result-box">
    <span style="font-size:28px;">🔎</span>
    <span class="result-search-title">"{escape(st.session_state.get("result_query", keyword))}"</span>
    <div class="result-search-condition">
        <b>현재 적용 조건</b> · {escape(condition_summary)}
    </div>
    <div class="result-search-sub">추출된 조건을 반영한 추천 결과입니다.</div>
</div>

<div class="info-box">
    <b>ℹ️ 현재 데이터는 공공 API 기반 정책 정보입니다.</b><br>
    일부 정책은 신청 링크, 제출서류, 소득 조건 등의 정보가 제공되지 않을 수 있습니다.
    정확한 신청 가능 여부는 공식 출처를 확인해주세요.
</div>
""")

        with st.container(border=True):
            result_title, closed_filter = st.columns([3, 1.15], vertical_alignment="center")

            with result_title:
                render_html(f"""
<div class="result-filter-heading">
    <div class="result-title">총 {len(filtered_policies)}개의 관련 정책을 찾았습니다.</div>
    <div class="small-muted">관련도 순으로 상위 {min(len(filtered_policies), RESULT_LIMIT)}개를 보여드려요.</div>
</div>
""")

            with closed_filter:
                st.toggle(
                    "마감 정책 제외",
                    value=True,
                    key="exclude_closed_policies",
                    help="끄면 신청이 마감된 정책도 결과에 함께 표시됩니다."
                )
                st.caption(
                    "마감된 정책을 숨기는 중"
                    if exclude_closed
                    else "마감된 정책도 함께 표시 중"
                )

        for display_rank, p in enumerate(visible_policies, 1):
            apply_link = _external_link(
                "신청하기 ↗",
                p["application_url"],
                "action-btn policy-link"
            )
            source_link = _external_link(
                "출처 보기 ↗",
                p["source_url"],
                "sub-btn policy-link"
            )
            if not apply_link:
                apply_link = '<div class="action-btn action-btn-disabled">신청 링크 없음</div>'
            if not source_link:
                source_link = '<div class="sub-btn action-btn-disabled">출처 없음</div>'

            render_html(f"""
<div class="policy-card">
    <div class="policy-layout">
        <div class="policy-left">
            <span class="rank-badge">{display_rank}</span>
            <div class="category-box">{escape(p['icon'])}</div>
            <div class="category-label">{escape(p['category'])}</div>
        </div>

        <div>
            <div class="policy-top">
                <div class="policy-title">{escape(p['title'])}</div>
                <div class="policy-badges">
                    <span class="{p['status_class']}">{escape(p['status'])}</span>
                    <span class="badge-blue">{escape(p['detail'])}</span>
                </div>
            </div>

            <div class="policy-desc policy-desc-summary">
                {escape(_shorten(p['description'], 105))}
            </div>

            <div class="policy-meta">
                <div>
                    <div class="meta-label">신청기간</div>
                    <div class="meta-value">{escape(p['period'])}</div>
                </div>
                <div>
                    <div class="meta-label">대상연령</div>
                    <div class="meta-value">{escape(p['age'])}</div>
                </div>
                <div>
                    <div class="meta-label">지원내용</div>
                    <div class="meta-value">{escape(_shorten(p['support'], 75))}</div>
                </div>
            </div>
        </div>

        <div>
            {apply_link}
            {source_link}
        </div>
    </div>
</div>
""")

        render_html("""
<div class="info-box">
    <b>원하는 결과를 찾지 못하셨나요?</b><br>
    검색어를 더 구체적으로 입력하거나, 필터 조건을 변경해보세요.
</div>
""")
