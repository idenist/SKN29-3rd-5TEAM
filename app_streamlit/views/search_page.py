from datetime import date, datetime
from html import escape
import re
from urllib.parse import urlparse

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from utils.condition_parser import parse_user_query
from utils.html_renderer import render_html
from utils.api_client import extract_conditions_from_backend
from utils.loading_overlay import show_policy_loading

REGIONS = ["서울", "부산", "대구", "인천", "광주", "대전", "경기", "기타"]
JOB_STATUSES = ["구직자", "재직자", "중소기업 재직자", "프리랜서", "예비창업자", "사업자", "학생"]
HOUSING_STATUSES = ["월세", "전세", "자가", "무주택", "기타"]
INTERESTS = ["취업", "교육", "창업", "주거", "금융", "복지"]
RESULTS_PER_PAGE = 10
NO_MATCH_INTEREST = "__NO_MATCH_INTEREST__"


def _empty_profile():
    return {
        "age": None,
        "region": None,
        "income": None,
        "job_status": None,
        "housing_status": None,
        "interest": [],
    }


def _profile_from_extracted(extracted):
    profile = _empty_profile()

    for key in ("age", "region", "income", "job_status", "housing_status"):
        if extracted.get(key) is not None:
            profile[key] = extracted[key]

    if extracted.get("interest"):
        profile["interest"] = extracted["interest"]

    return profile


def _has_extracted_condition(extracted):
    return any(
        extracted.get(key)
        for key in (
            "age",
            "region",
            "income",
            "job_status",
            "housing_status",
            "interest",
        )
    )


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


def _reset_filter_widgets():
    st.session_state.filter_age = None
    st.session_state.filter_region = None
    st.session_state.filter_income = None
    st.session_state.filter_job_status = None
    st.session_state.filter_housing_status = None
    st.session_state.filter_validation_error = False

    for interest in INTERESTS:
        st.session_state[f"filter_interest_{interest}"] = False

def _extract_conditions(keyword):
    extracted = parse_user_query(keyword)

    if _has_extracted_condition(extracted):
        return extracted

    try:
        backend_extracted = extract_conditions_from_backend(keyword)

        for key in ("age", "region", "income", "job_status", "housing_status"):
            if backend_extracted.get(key) is not None:
                extracted[key] = backend_extracted[key]

        if backend_extracted.get("interest"):
            extracted["interest"] = backend_extracted["interest"]

    except Exception:
        st.toast("AI 조건 추출에 실패해 기본 조건 추출을 사용합니다.")

    return extracted

def _extract_search_conditions():
    keyword = st.session_state.get("result_query_input", "")
    extracted = _extract_conditions(keyword)
    updated_profile = _profile_from_extracted(extracted)

    st.session_state.profile = updated_profile
    st.session_state.search_base_profile = updated_profile.copy()
    st.session_state.extracted_conditions = extracted
    st.session_state.result_query = keyword
    st.session_state.has_searched = True
    _reset_filter_widgets()

def _apply_filter_conditions():
    age = st.session_state.get("filter_age")
    region = st.session_state.get("filter_region")
    selected_interests = [
        interest
        for interest in INTERESTS
        if st.session_state.get(f"filter_interest_{interest}", False)
    ]

    if age is None and region is None and not selected_interests:
        st.session_state.filter_validation_error = True
        return

    profile = st.session_state.get(
        "search_base_profile",
        st.session_state.profile
    ).copy()

    if age is not None:
        profile["age"] = age

    if region is not None:
        profile["region"] = region

    if selected_interests:
        base_interests = profile.get("interest", [])
        if base_interests:
            profile["interest"] = [
                interest
                for interest in base_interests
                if interest in selected_interests
            ]
            if not profile["interest"]:
                profile["interest"] = [NO_MATCH_INTEREST]
        else:
            profile["interest"] = selected_interests

    st.session_state.profile = {
        "age": profile["age"],
        "region": profile["region"],
        "income": profile["income"],
        "job_status": profile["job_status"],
        "housing_status": profile["housing_status"],
        "interest": profile["interest"],
    }
    st.session_state.has_searched = True
    st.session_state.filter_validation_error = False


def _matches_age(policy, age):
    if age is None:
        return True

    try:
        age_min = int(policy["age_min"]) if policy["age_min"] else None
        age_max = int(policy["age_max"]) if policy["age_max"] else None
    except ValueError:
        return True

    return (age_min is None or age >= age_min) and (age_max is None or age <= age_max)


def _matches_region(policy, region):
    if not region:
        return True

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
    normalized_url = _normalize_url(url)
    if not normalized_url:
        return ""

    return (
        f'<a class="{class_name}" href="{escape(normalized_url, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer">{label}</a>'
    )


def _normalize_url(url):
    value = str(url or "").strip()
    if not value:
        return ""

    if value.startswith("www."):
        value = f"https://{value}"

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return value


def _policy_links(policy):
    application_url = _normalize_url(policy.get("application_url"))
    source_url = _normalize_url(policy.get("source_url"))
    official_url = _normalize_url(policy.get("official_url"))
    return (
        application_url or official_url or source_url,
        source_url or official_url or application_url,
    )


def _shorten(text, limit):
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."


def _display_user_value(value, suffix=""):
    if value is None or value == "":
        return "입력 없음"

    if isinstance(value, (int, float)):
        value = f"{value:,}"

    return f"{value}{suffix}"


def _display_policy_age(value):
    normalized = " ".join(str(value or "").split())
    if normalized in {"", "만 0세 ~ 0세", "만 0세 이상", "만 0세 이하"}:
        return "연령 정보 없음"
    return normalized


def _close_policy_dialog():
    st.session_state.pop("policy_dialog_id", None)


def _open_guide(policy_id):
    st.session_state.guide_selected_policy_id = policy_id
    st.session_state.selected_policy_id = policy_id
    st.session_state.pop("guide_policy_select", None)
    st.session_state.pop("policy_dialog_id", None)
    st.session_state.page = "신청 가이드"


def _change_result_page(delta):
    st.session_state.search_result_page = max(
        1,
        st.session_state.get("search_result_page", 1) + delta
    )
    st.session_state.scroll_to_search_results = True


def _scroll_to_search_results():
    if not st.session_state.pop("scroll_to_search_results", False):
        return

    components.html(
        """
<script>
const scrollToResults = (attempt = 0) => {
    const target = window.parent.document.querySelector('.policy-results-marker');
    if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
    }

    if (attempt < 12) {
        window.setTimeout(() => scrollToResults(attempt + 1), 80);
    }
};

window.requestAnimationFrame(() => scrollToResults());
</script>
""",
        height=0,
        scrolling=False
    )


def _reset_policy_dialog_scroll():
    components.html(
        """
<script>
const parentDocument = window.parent.document;

const resetDialogScroll = () => {
    const dialog = parentDocument.querySelector(
        '[data-testid="stDialog"], [role="dialog"]'
    );
    if (!dialog) return;

    const candidates = [
        dialog,
        dialog.parentElement,
        ...dialog.querySelectorAll('*')
    ].filter(Boolean);

    candidates.forEach((element) => {
        if (
            element.scrollTop > 0 ||
            element.scrollHeight > element.clientHeight
        ) {
            element.scrollTop = 0;
        }
    });
};

window.requestAnimationFrame(() => {
    window.requestAnimationFrame(resetDialogScroll);
});
</script>
""",
        height=0,
        scrolling=False
    )


@st.dialog(
    "정책 상세 분석",
    width="large",
    on_dismiss=_close_policy_dialog
)
def _render_policy_dialog(policy, profile):
    apply_url, source_url = _policy_links(policy)

    render_html(f"""
<div class="content-card policy-dialog-header">
    <div class="policy-title">{escape(policy['icon'])} {escape(policy['title'])}</div>
    <div class="policy-desc">{escape(policy['description'])}</div>
    <span class="{policy['status_class']}">{escape(policy['status'])}</span>
    <span class="badge-blue">{escape(policy['category'])}</span>
</div>

<div class="content-card">
    <div class="section-title">정책 상세 내용</div>
    <div class="detail-info-grid">
        <div class="detail-info-item">
            <div class="meta-label">신청 기간</div>
            <div class="meta-value">{escape(policy['period'])}</div>
        </div>
        <div class="detail-info-item">
            <div class="meta-label">대상 연령</div>
            <div class="meta-value">{escape(_display_policy_age(policy['age']))}</div>
        </div>
        <div class="detail-info-item">
            <div class="meta-label">대상 지역</div>
            <div class="meta-value">{escape(policy['region'])}</div>
        </div>
        <div class="detail-info-item">
            <div class="meta-label">운영 기관</div>
            <div class="meta-value">{escape(policy['organization'])}</div>
        </div>
    </div>
    <div class="detail-text-section">
        <div class="meta-label">지원 내용</div>
        <div class="detail-text">{escape(policy['support'])}</div>
    </div>
    <div class="detail-text-section">
        <div class="meta-label">대상 및 자격 조건</div>
        <div class="detail-text">{escape(policy['income'])}</div>
    </div>
    <div class="detail-text-section">
        <div class="meta-label">신청 방법</div>
        <div class="detail-text">{escape(policy['method'])}</div>
    </div>
</div>
""")

    dialog_apply_link = _external_link(
        "신청 사이트 바로가기 ↗",
        apply_url,
        "action-btn policy-link dialog-link-btn"
    )
    dialog_source_link = _external_link(
        "공식 출처 확인 ↗",
        source_url,
        "sub-btn policy-link dialog-link-btn"
    )
    render_html(f"""
<div class="dialog-link-actions">
    {dialog_apply_link or '<div class="action-btn action-btn-disabled dialog-link-btn">신청 링크 없음</div>'}
    {dialog_source_link or '<div class="sub-btn action-btn-disabled dialog-link-btn">출처 없음</div>'}
</div>
""")

    st.markdown("### 내 조건과 비교")
    comparison = pd.DataFrame([
        ["나이", _display_user_value(profile.get("age"), "세"), _display_policy_age(policy["age"]), "확인 필요"],
        ["지역", _display_user_value(profile.get("region")), policy["region"], "확인 필요"],
        ["소득", _display_user_value(profile.get("income"), "만원"), policy["income"], "공식 공고 확인"],
        ["현재 상태", _display_user_value(profile.get("job_status")), policy["job_status"], "공식 공고 확인"],
        ["주거 상태", _display_user_value(profile.get("housing_status")), policy["housing_status"], "공식 공고 확인"],
    ], columns=["조건", "내 정보", "정책 조건", "판정"])
    st.dataframe(comparison, width="stretch", hide_index=True)

    detail_notice = (
        "원본 데이터에 일부 세부 조건이 없어 공식 공고 확인이 필요합니다."
        if policy["needs_detail_check"]
        else "전처리된 공공데이터를 기준으로 비교했습니다. 최종 자격은 공식 공고에서 확인하세요."
    )
    render_html(f"""
<div class="content-card">
    <div class="section-title">추천 이유</div>
    <div class="policy-desc">{escape(detail_notice)}</div>
</div>
""")

    st.button(
        "이 정책의 신청 가이드 보기",
        width="stretch",
        type="primary",
        key=f"dialog_guide_{policy['id']}",
        on_click=_open_guide,
        args=(policy["id"],)
    )

    _reset_policy_dialog_scroll()


def render_search_page(policies):
    has_searched = st.session_state.get("has_searched", False)
    render_html('<div class="search-page-marker"></div>')

    render_html('<div class="search-condition-title">조건 검색</div>')

    profile = st.session_state.profile
    query = st.session_state.get("result_query", "")
    st.session_state.setdefault("result_query_input", query)
    st.session_state.setdefault(
        "filter_age",
        profile["age"] if has_searched else None
    )
    st.session_state.setdefault(
        "filter_region",
        profile["region"] if has_searched else None
    )
    for interest in INTERESTS:
        st.session_state.setdefault(
            f"filter_interest_{interest}",
            interest in profile["interest"]
        )

    search_left, search_right = st.columns([1.05, 4])

    with search_left:
        with st.form("condition_search_form", border=False):
            keyword = st.text_input(
                "검색어",
                label_visibility="collapsed",
                key="result_query_input"
            )

            submitted = st.form_submit_button(
                "조건 추출",
                width="stretch",
                type="primary",
                key="extract_search_conditions"
            )

        st.caption("예: 서울 28살 월세 지원 정책")

        if submitted:
            keyword = st.session_state.get("result_query_input", "").strip()
            if keyword:
                loading_slot = st.empty()
                show_policy_loading(loading_slot)
                _extract_search_conditions()
                st.rerun()
            else:
                st.toast("검색어를 입력해 주세요.")

    with search_right:
        render_html(f"""
<div class="search-result-box search-result-box-top">
    <span style="font-size:28px;">🔎</span>
    <span class="result-search-title">"{escape(st.session_state.get("result_query", keyword))}"</span>
    <div class="result-search-sub">추출된 조건을 반영한 추천 결과입니다.</div>
</div>
<div class="info-box recommendation-api-notice">
    <b>ℹ️ 현재 데이터는 공공 API 기반 정책 정보입니다.</b><br>
    일부 정책은 신청 링크, 제출서류, 소득 조건 등의 정보가 제공되지 않을 수 있습니다.<br>
    정확한 신청 가능 여부는 공식 출처를 확인해주세요.
</div>
""")

    render_html('<div class="search-section-divider"></div>')

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
    result_signature = (
        keyword,
        profile["age"],
        profile["region"],
        profile["income"],
        profile["job_status"],
        profile["housing_status"],
        tuple(selected_interests),
        exclude_closed,
    )
    if st.session_state.get("search_result_signature") != result_signature:
        st.session_state.search_result_signature = result_signature
        st.session_state.search_result_page = 1

    total_pages = max(
        1,
        (len(filtered_policies) + RESULTS_PER_PAGE - 1)
        // RESULTS_PER_PAGE
    )
    current_page = min(
        st.session_state.get("search_result_page", 1),
        total_pages
    )
    st.session_state.search_result_page = current_page
    page_start = (current_page - 1) * RESULTS_PER_PAGE
    page_end = page_start + RESULTS_PER_PAGE
    visible_policies = filtered_policies[page_start:page_end]
    st.session_state.recommended_policy_ids = [
        policy["id"] for policy in filtered_policies
    ]

    heading_left, heading_right = st.columns(
        [1.05, 4],
        vertical_alignment="center"
    )
    with heading_left:
        st.markdown("### 조건 입력 필터")

    with heading_right:
        if has_searched:
            with st.container(border=True):
                result_title, closed_filter = st.columns(
                    [3, 1.15],
                    vertical_alignment="center"
                )
                with result_title:
                    render_html(f"""
<div class="result-filter-heading">
    <div class="result-title">총 {len(filtered_policies)}개의 관련 정책을 찾았습니다.</div>
    <div class="small-muted">관련도 순으로 한 페이지에 {RESULTS_PER_PAGE}개씩 보여드려요.</div>
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

    filter_left, results_right = st.columns([1.05, 4])

    with filter_left:
        with st.form("recommendation_filter_form"):
            age = st.number_input(
                "나이",
                min_value=15,
                max_value=80,
                placeholder="나이 입력",
                key="filter_age"
            )
            region = st.selectbox(
                "지역",
                REGIONS,
                index=None,
                placeholder="지역 선택",
                key="filter_region"
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

            st.form_submit_button(
                "조건 적용",
                width="stretch",
                type="primary",
                on_click=_apply_filter_conditions
            )

        if st.session_state.get("filter_validation_error", False):
            st.warning("적용할 필터 조건을 하나 이상 입력해 주세요.")

        render_html("""
<div class="info-box" style="margin-top:24px;">
    <b>조건 입력 팁</b><br>
    · 먼저 위에서 궁금한 정책을 검색해 주세요.<br>
· 더 정확한 결과가 필요할 때만 나이, 지역, 관심 분야를 추가로 적용해 주세요.
</div>
""")

    with results_right:
        render_html('<div class="policy-results-marker"></div>')
        _scroll_to_search_results()

        if not has_searched:
            st.session_state.recommended_policy_ids = []
            render_html("""
<div class="empty-search-state empty-search-list">
    <div class="empty-search-icon">⌕</div>
    <div class="empty-search-title">아직 검색한 정책이 없습니다.</div>
    <div class="empty-search-desc">
        자연어를 입력해 조건을 추출하거나 왼쪽 필터에서 조건을 적용해 주세요.
    </div>
</div>
""")
            return

        for display_rank, p in enumerate(visible_policies, page_start + 1):
            apply_url, source_url = _policy_links(p)
            apply_link = _external_link(
                "신청하기 ↗",
                apply_url,
                "action-btn policy-link"
            )
            source_link = _external_link(
                "출처 보기 ↗",
                source_url,
                "sub-btn policy-link"
            )
            if not apply_link:
                apply_link = '<div class="action-btn action-btn-disabled">신청 링크 없음</div>'
            if not source_link:
                source_link = '<div class="sub-btn action-btn-disabled">출처 없음</div>'

            with st.container(key=f"policy_card_{p['id']}"):
                if st.button(
                    f"{p['title']} 상세 보기",
                    key=f"open_policy_detail_{p['id']}",
                    width="stretch"
                ):
                    st.session_state.policy_dialog_id = p["id"]

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

                    <div class="policy-meta">
                        <div>
                            <div class="meta-label">신청기간</div>
                            <div class="meta-value">{escape(p['period'])}</div>
                        </div>
                        <div>
                            <div class="meta-label">대상연령</div>
                            <div class="meta-value">{escape(_display_policy_age(p['age']))}</div>
                        </div>
                        <div>
                            <div class="meta-label">지원내용</div>
                            <div class="meta-value support-summary">{escape(p['description'])}</div>
                        </div>
                    </div>
                </div>

                <div class="policy-actions">
                    {apply_link}
                    {source_link}
                </div>
            </div>
        </div>
""")

        if total_pages > 1:
            previous_page, page_status, next_page = st.columns(
                [1, 1.4, 1],
                vertical_alignment="center"
            )
            with previous_page:
                st.button(
                    "← 이전",
                    width="stretch",
                    disabled=current_page == 1,
                    key="previous_result_page",
                    on_click=_change_result_page,
                    args=(-1,)
                )
            with page_status:
                st.markdown(
                    f'<div class="pagination-status">'
                    f'{current_page} / {total_pages} 페이지'
                    f'</div>',
                    unsafe_allow_html=True
                )
            with next_page:
                st.button(
                    "다음 →",
                    width="stretch",
                    disabled=current_page == total_pages,
                    key="next_result_page",
                    on_click=_change_result_page,
                    args=(1,)
                )

        policies_by_id = {policy["id"]: policy for policy in filtered_policies}
        dialog_policy_id = st.session_state.get("policy_dialog_id")
        if dialog_policy_id in policies_by_id:
            _render_policy_dialog(policies_by_id[dialog_policy_id], profile)

        render_html("""
<div class="info-box">
    <b>원하는 결과를 찾지 못하셨나요?</b><br>
    검색어를 더 구체적으로 입력하거나, 필터 조건을 변경해보세요.
</div>
""")
