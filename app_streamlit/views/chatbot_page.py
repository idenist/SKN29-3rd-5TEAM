import streamlit as st
import requests
from utils.html_renderer import render_html

def render_chatbot_page(policies):
    st.markdown('<div class="page-title">정책 챗봇</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">궁금한 정책 정보를 질문해보세요.</div>', unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # 1. 대화 기록 세션 초기화
    # ------------------------------------------------------------------
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {
                "role": "assistant",
                "message": "안녕하세요! '이젠, 안쉼' 통합 정책 챗봇입니다. 무엇이 궁금하신가요?\n\n(예: '나에게 맞는 창업 지원 정책이 있어?', '국비지원 데이터 분석 강의 알려줘')"
            }
        ]

    # ------------------------------------------------------------------
    # 2. 레이아웃 분할 (좌측: 대화창 / 우측: FAQ)
    # ------------------------------------------------------------------
    chat_col, faq_col = st.columns([2.5, 1])

    with faq_col:
        html_faq = """
        <div class="content-card">
            <div class="section-title">자주 묻는 질문</div>
            <div class="faq-item">💡 청년 정책은 어떻게 신청하나요?</div>
            <div class="faq-item">🔄 중복 수급 가능한 정책은?</div>
            <div class="faq-item">💰 소득 기준은 세전인가요?</div>
            <div class="faq-item">📅 신청 마감일 확인 방법</div>
        </div>
        """
        render_html(html_faq)

    # ------------------------------------------------------------------
    # 3. 기존 대화 기록 출력
    # ------------------------------------------------------------------
    with chat_col:
        for chat in st.session_state.chat_history:
            if chat["role"] == "user":
                st.chat_message("user").write(chat["message"])
            else:
                st.chat_message("assistant").write(chat["message"])

        # ------------------------------------------------------------------
        # 4. 실시간 채팅 입력 및 백엔드 스키마 매핑 연동
        # ------------------------------------------------------------------
        if user_input := st.chat_input("질문을 입력하세요..."):
            
            # 사용자 질문 즉시 렌더링 및 저장
            st.chat_message("user").write(user_input)
            st.session_state.chat_history.append({"role": "user", "message": user_input})

            with st.chat_message("assistant"):
                with st.spinner("AI 에이전트가 통합 지원 데이터를 검색 중입니다..."):
                    try:
                        # 홈 또는 세션에 저장된 사용자 프로필 데이터 가져오기
                        user_profile = st.session_state.get("profile", {})
                        
                        # [🚨 chat_schema.py 기반 완벽한 규격 조립]
                        payload = {
                            "message": user_input,
                            "user_profile": {
                                "age": int(user_profile.get("age" or 27)),
                                "region": str(user_profile.get("region", "서울")),
                                # 소득 수준을 백엔드 사양에 맞춰 문자열(String)로 변환
                                "income": f"연소득 {user_profile.get('income'or 3000)}만원 이하",
                                "employment_status": str(user_profile.get("job_status", "중소기업 재직자")),
                                "interest_domain": "전체"
                            },
                            "top_k": 5
                        }

                        # 8000번 포트로 떠 있는 FastAPI 서버 구멍 찌르기
                        response = requests.post("http://localhost:8000/api/chat", json=payload, timeout=30)

                        if response.status_code == 200:
                            result = response.json()
                            
                            # chat_schema.py의 최종 아웃풋 Key인 'answer' 추출
                            ai_answer = result.get("answer")
                            
                            if ai_answer:
                                st.write(ai_answer)
                                st.session_state.chat_history.append({"role": "assistant", "message": ai_answer})
                            else:
                                st.warning("백엔드 서버와 통신은 성공했으나 답변 내용(answer)이 없습니다.")
                                st.json(result)
                        else:
                            st.error(f"백엔드 유효성 검사 실패 또는 서버 에러 (에러 코드: {response.status_code})")
                            # 백엔드가 보낸 세부 에러 내역을 화면에 출력하여 디버깅 보조
                            st.json(response.json())

                    except requests.exceptions.ConnectionError:
                        st.error("백엔드 서버(FastAPI)가 가동 중이지 않습니다. 터미널에서 uvicorn 서버를 먼저 켜주세요.")
                    except Exception as e:
                        st.error(f"연동 통신 중 알 수 없는 에러 발생: {str(e)}")