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
    st.markdown('<div class="page-sub">선택한 정책의 신청 절차와 필요 서류를 안내합니다.</div>', unsafe_allow_html=True)

    selected = st.selectbox("정책 선택", [p["title"] for p in policies])
    policy = next(p for p in policies if p["title"] == selected)

    html = f"""
<div class="content-card">
    <div class="policy-title">{policy['icon']} {policy['title']}</div>
    <div class="policy-desc">신청 기간: {policy['period']}</div>
    <span class="{policy['status_class']}">{policy['status']}</span>
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
   href="{official_url}"
   target="_blank"
   rel="noopener noreferrer">
    공식 사이트 접속 ↗
</a>
"""

        step_html = f"""
<div class="guide-step">
    <div class="step-num">{i}</div>
    <div class="guide-step-content">
        <b>{step}</b><br>
        <span class="small-muted">신청 전 세부 조건을 반드시 확인하세요.</span>
    </div>
    {site_link}
</div>
"""
        render_html(step_html)

    st.warning("신청 기간을 반드시 확인하세요. 서류 누락 시 지원이 취소될 수 있습니다.")
