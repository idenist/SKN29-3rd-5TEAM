import streamlit as st


def render_profile_page():
    st.markdown('<div class="section-title">사용자 조건 입력</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-sub">추출된 조건을 확인하고 필요한 값을 보완한 뒤 추천을 실행하세요.</div>',
        unsafe_allow_html=True
    )

    profile = st.session_state.profile

    with st.form("profile_form"):
        c1, c2, c3 = st.columns(3)

        with c1:
            age = st.number_input("나이", min_value=15, max_value=80, value=int(profile["age"]))
            region = st.selectbox(
                "지역",
                ["서울", "부산", "대구", "인천", "광주", "대전", "경기", "기타"],
                index=["서울", "부산", "대구", "인천", "광주", "대전", "경기", "기타"].index(profile["region"])
            )

        with c2:
            income = st.number_input("연소득", min_value=0, max_value=20000, value=int(profile["income"]), step=100)
            job_status = st.selectbox(
                "현재 상태",
                ["구직자", "재직자", "중소기업 재직자", "프리랜서", "예비창업자", "사업자", "학생"],
                index=["구직자", "재직자", "중소기업 재직자", "프리랜서", "예비창업자", "사업자", "학생"].index(profile["job_status"])
            )

        with c3:
            housing_status = st.selectbox(
                "주거 상태",
                ["월세", "전세", "자가", "무주택", "기타"],
                index=["월세", "전세", "자가", "무주택", "기타"].index(profile["housing_status"])
            )
            interest = st.multiselect(
                "관심 분야",
                ["취업", "교육", "창업", "주거", "금융", "복지"],
                default=profile["interest"]
            )

        submitted = st.form_submit_button(
            "추천 실행",
            use_container_width=True,
            type="primary"
        )

    if submitted:
        st.session_state.profile = {
            "age": age,
            "region": region,
            "income": income,
            "job_status": job_status,
            "housing_status": housing_status,
            "interest": interest
        }
        st.session_state.page = "추천 결과"
        st.rerun()
