import streamlit as st

from utils.html_renderer import render_html


def render_chatbot_page(policies):
    st.markdown('<div class="page-title">정책 챗봇</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">궁금한 정책 정보를 질문해보세요.</div>', unsafe_allow_html=True)

    html = """
<div class="chat-layout">
    <div>
        <div class="chat-bubble-user">
            청년도약계좌랑 청년일자리도약장려금은 같이 받을 수 있어?
        </div>

        <div class="chat-bubble-ai">
            네, 두 정책은 목적이 다르기 때문에 중복 수급 가능성이 있습니다.<br><br>
            · 청년일자리도약장려금: 중소기업 취업 청년의 고용 지원<br>
            · 청년도약계좌: 청년의 자산 형성 지원<br><br>
            다만 세부 조건은 각 정책의 공고문을 확인해야 합니다.
        </div>
    </div>

    <div class="content-card">
        <div class="section-title">자주 묻는 질문</div>
        <div class="faq-item">청년 정책은 어떻게 신청하나요?</div>
        <div class="faq-item">중복 수급 가능한 정책은?</div>
        <div class="faq-item">소득 기준은 세전인가요?</div>
        <div class="faq-item">신청 결과는 언제 알 수 있나요?</div>
    </div>
</div>
"""
    render_html(html)

    st.text_input("질문 입력", placeholder="질문을 입력하세요...")
    st.button("질문하기")
