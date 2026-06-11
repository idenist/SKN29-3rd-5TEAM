from html import escape

import streamlit as st
import pandas as pd

from utils.html_renderer import render_html


def render_detail_page(policies):
    st.markdown('<div class="page-title">정책 상세 분석</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">추천된 정책이 내 조건에 맞는지 항목별로 비교합니다.</div>', unsafe_allow_html=True)

    policies_by_id = {policy["id"]: policy for policy in policies}
    selected_id = st.selectbox(
        "정책 선택",
        list(policies_by_id),
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
"""
    render_html(html)

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
