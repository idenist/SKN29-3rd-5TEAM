import streamlit as st
import pandas as pd

from utils.html_renderer import render_html


def render_detail_page(policies):
    st.markdown('<div class="page-title">정책 상세 분석</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">추천된 정책이 내 조건에 맞는지 항목별로 비교합니다.</div>', unsafe_allow_html=True)

    selected = st.selectbox("정책 선택", [p["title"] for p in policies])
    policy = next(p for p in policies if p["title"] == selected)

    html = f"""
<div class="content-card">
    <div class="policy-title">{policy['icon']} {policy['title']}</div>
    <div class="policy-desc">{policy['description']}</div>
    <span class="{policy['status_class']}">{policy['status']}</span>
    <span class="badge-blue">{policy['category']}</span>
</div>
"""
    render_html(html)

    df = pd.DataFrame([
        ["나이", "27세", policy["age"], "충족"],
        ["지역", "서울특별시", "전국 또는 서울", "충족"],
        ["소득", "3,000만원", policy["income"], "확인 필요"],
        ["취업 상태", "중소기업 재직자", "중소기업 재직자", "충족"],
        ["주거 상태", "월세", "무관", "충족"],
    ], columns=["조건", "내 정보", "정책 조건", "판정"])

    st.dataframe(df, use_container_width=True, hide_index=True)

    render_html("""
<div class="content-card">
    <div class="section-title">추천 이유</div>
    <div class="policy-desc">
        사용자의 나이, 지역, 취업 상태 조건이 정책 조건과 대체로 일치합니다.
        다만 소득 기준이 있는 정책은 정확한 기준중위소득 환산이 필요합니다.
    </div>
</div>
""")
