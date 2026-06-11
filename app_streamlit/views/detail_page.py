from html import escape

import streamlit as st
import pandas as pd

from utils.html_renderer import render_html


def render_detail_page(policies):
    st.markdown('<div class="page-title">정책 상세 분석</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">추천 결과에서 검색된 정책을 선택해 상세 내용과 조건을 확인합니다.</div>',
        unsafe_allow_html=True
    )

    policies_by_id = {policy["id"]: policy for policy in policies}
    recommended_ids = [
        policy_id
        for policy_id in st.session_state.get("recommended_policy_ids", [])
        if policy_id in policies_by_id
    ]
    selectable_ids = recommended_ids or list(policies_by_id)

    selected_id = st.selectbox(
        "검색된 정책 선택",
        selectable_ids,
        format_func=lambda policy_id: policies_by_id[policy_id]["title"]
    )
    policy = policies_by_id[selected_id]
    profile = st.session_state.profile

    html = f"""
<div class="content-card">
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
            <div class="meta-value">{escape(policy['age'])}</div>
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
"""
    render_html(html)

    link_columns = st.columns(2)
    with link_columns[0]:
        if policy["application_url"]:
            st.link_button(
                "신청 사이트 바로가기 ↗",
                policy["application_url"],
                use_container_width=True,
                type="primary"
            )
    with link_columns[1]:
        if policy["source_url"]:
            st.link_button(
                "공식 출처 확인 ↗",
                policy["source_url"],
                use_container_width=True
            )

    st.markdown("### 내 조건과 비교")

    df = pd.DataFrame([
        ["나이", f"{profile['age']}세", policy["age"], "확인 필요"],
        ["지역", profile["region"], policy["region"], "확인 필요"],
        ["소득", f"{profile['income']:,}만원", policy["income"], "공식 공고 확인"],
        ["현재 상태", profile["job_status"], policy["job_status"], "공식 공고 확인"],
        ["주거 상태", profile["housing_status"], policy["housing_status"], "공식 공고 확인"],
    ], columns=["조건", "내 정보", "정책 조건", "판정"])

    st.dataframe(df, use_container_width=True, hide_index=True)

    detail_notice = (
        "원본 데이터에 일부 세부 조건이 없어 공식 공고 확인이 필요합니다."
        if policy["needs_detail_check"]
        else "전처리된 공공데이터를 기준으로 비교했습니다. 최종 자격은 공식 공고에서 확인하세요."
    )
    render_html(f"""
<div class="content-card">
    <div class="section-title">추천 이유</div>
    <div class="policy-desc">
        {escape(detail_notice)}
    </div>
</div>
""")
