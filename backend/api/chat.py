import time
import logging
from fastapi import APIRouter, HTTPException
from backend.schemas.chat_schema import (
    ChatRequest, ChatResponse, 
    UserConditions, PolicyRecommendation,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Chat"])

# RAG 엔진 연동 전 목 응답 플래그
# 승혁님 run_rag_chat() 완성되면 False로 바꾸고 아래 import 활성화
USE_MOCK = False

from backend.services.rag_chat_service import run_rag_chat


def _mock_response(request: ChatRequest) -> ChatResponse:
    """RAG 연동 전 임시 목 응답 - 민지님 Streamlit 작업용"""
    profile = request.user_profile

    return ChatResponse(
        answer=f"'{request.message}'에 대한 정책을 검색했습니다. (현재 목 응답 — RAG 연동 전)",
        user_conditions=UserConditions(
            age=profile.age if profile else None,
            region=profile.region if profile else None,
            income=profile.income if profile else None,
            employment_status=profile.employment_status if profile else None,
            interest_domain=profile.interest_domain if profile else None,
        ),
        route=profile.interest_domain if (profile and profile.interest_domain) else "일자리",
        recommendations=[
            PolicyRecommendation(
                policy_id="R202406010001",
                policy_name="청년일자리도약장려금",
                eligibility="추가 확인 필요",
                score=0.82,
                reason="취업 및 일자리 지원과 관련성이 높습니다.",
                support_content="청년 채용 기업에 최대 월 60만원 장려금 지원",
                application_period="상시 모집",
                required_documents="정보 없음",
                source_url="https://www.work.go.kr",
                needs_detail_check=True,
                cautions=["신청 전 원문 URL 확인이 필요합니다."],
            ),
            PolicyRecommendation(
                policy_id="R202406010002",
                policy_name="청년내일채움공제",
                eligibility="추가 확인 필요",
                score=0.75,
                reason="장기 취업 지원 및 자산 형성에 관련성이 높습니다.",
                support_content="2년 근속 시 최대 1,200만원 적립",
                application_period="정보 없음",
                required_documents="정보 없음",
                source_url="https://www.work.go.kr",
                needs_detail_check=True,
                cautions=["제공 데이터에 신청 기간 정보가 없습니다."],
            ),
        ],
        warnings=["현재 목 응답입니다. RAG 엔진 연동 후 실제 정책 데이터가 반환됩니다."],
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="정책 추천 채팅",
    description="사용자 자연어 질문을 받아 RAG 기반 청년 정책을 추천합니다.",
)
async def chat(request: ChatRequest):
    start = time.time()
    logger.info(f"[CHAT] message=\"{request.message[:50]}\"")

    # 1. 빈 메시지 검증 (Pydantic min_length=1 로 이미 잡히지만 명시적 처리)
    if not request.message.strip():
        raise HTTPException(status_code=422, detail="질문을 입력해 주세요.")

    try:
        if USE_MOCK:
            result = _mock_response(request)
        # else:
        #     # RAG 연동 시 아래 주석 해제
        #     raw = run_rag_chat(
        #         message=request.message,
        #         user_profile=request.user_profile,
        #         top_k=request.top_k,
        #     )
        #     result = ChatResponse(**raw)
        #     raise NotImplementedError("RAG 서비스가 아직 연동되지 않았습니다.")
        # 나중에 이렇게 교체
        else:
            try:
                result = run_rag_chat(
                    message=request.message,
                    user_profile=request.user_profile,
                    top_k=request.top_k,
                )
                
            except ConnectionError:
                raise HTTPException(
                    status_code=503,
                    detail="Vector DB 연결에 실패했습니다. 잠시 후 다시 시도해 주세요."
                )
            except ValueError:
                raise HTTPException(
                    status_code=500,
                    detail="LLM 응답 처리 중 오류가 발생했습니다."
                )
            except TimeoutError:
                raise HTTPException(
                    status_code=504,
                    detail="응답 시간이 초과됐습니다. 잠시 후 다시 시도해 주세요."
                )

        elapsed = time.time() - start
        logger.info(
            f"[CHAT] route=\"{result.route}\", "
            f"retrieved={len(result.recommendations)}, "
            f"elapsed={elapsed:.2f}s"
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"[ERROR] rag_service failed ({elapsed:.2f}s): {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": True,
                "message": "정책 검색 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.",
                "detail": str(e),
                "recoverable": True,
            },
        )