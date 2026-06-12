from html import escape

import streamlit as st

from utils.html_renderer import render_html


OFFICIAL_SITES = {
    "청년일자리도약장려금": "https://www.work24.go.kr",
    "청년도약계좌": "https://ylaccount.kinfa.or.kr",
    "청년 월세 특별지원": "https://www.bokjiro.go.kr",
    "국민내일배움카드": "https://www.work24.go.kr",
}


def render_guide_page(policies):
    st.markdown('<div class="page-title">신청 가이드</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">검색된 정책 중에서 신청 절차와 필요 서류를 확인합니다.</div>',
        unsafe_allow_html=True
    )

    policies_by_id = {policy["id"]: policy for policy in policies}
    recommended_ids = [
        policy_id
        for policy_id in st.session_state.get("recommended_policy_ids", [])
        if policy_id in policies_by_id
    ]
    selectable_ids = recommended_ids or list(policies_by_id)
    preferred_id = (
        st.session_state.get("guide_selected_policy_id")
        or st.session_state.get("selected_policy_id")
    )
    current_selected_id = st.session_state.get("guide_policy_select")
    if current_selected_id not in selectable_ids:
        st.session_state.guide_policy_select = (
            preferred_id
            if preferred_id in selectable_ids
            else selectable_ids[0]
        )

    selected_id = st.selectbox(
        "검색된 정책 선택",
        selectable_ids,
        format_func=lambda policy_id: policies_by_id[policy_id]["title"],
        key="guide_policy_select"
    )
    st.session_state.guide_selected_policy_id = selected_id
    policy = policies_by_id[selected_id]

    html = f"""
<div class="content-card">
    <div class="policy-title">{escape(policy['icon'])} {escape(policy['title'])}</div>
    <div class="policy-desc">신청 기간: {escape(policy['period'])}</div>
    <span class="{policy['status_class']}">{escape(policy['status'])}</span>
</div>
"""
    render_html(html)

    steps = [
        "공식 사이트 접속",
        "회원가입 또는 본인 인증",
        "신청서 작성",
        f"필요 서류 제출: {policy['docs']}",
        "심사 결과 확인"
    ]
    official_url = policy.get("official_url") or OFFICIAL_SITES.get(policy["title"])

    for i, step in enumerate(steps, 1):
        site_link = ""
        if i == 1 and official_url:
            site_link = f"""
<a class="guide-site-link"
   href="{escape(official_url, quote=True)}"
   target="_blank"
   rel="noopener noreferrer">
    공식 사이트 접속 ↗
</a>
"""

        step_html = f"""
<div class="guide-step">
    <div class="step-num">{i}</div>
    <div class="guide-step-content">
        <b>{escape(step)}</b><br>
        <span class="small-muted">신청 전 세부 조건을 반드시 확인하세요.</span>
    </div>
    {site_link}
</div>
"""
        render_html(step_html)

    st.warning("신청 기간을 반드시 확인하세요. 서류 누락 시 지원이 취소될 수 있습니다.")
