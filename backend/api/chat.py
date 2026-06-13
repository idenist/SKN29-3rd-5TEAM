import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, status

from backend.schemas.chat_schema import ChatRequest, ChatResponse
from backend.services.rag_chat_service import run_rag_chat

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="청년 정책 질의응답",
    description="자연어 질문을 입력하면 RAG 기반으로 관련 청년 정책을 검색하고 답변을 반환합니다.",
)
async def chat_endpoint(request: ChatRequest, http_request: Request) -> ChatResponse:
    request_id = str(uuid.uuid4())[:8]
    client_ip = http_request.client.host if http_request.client else "unknown"
    logger.info(
        "[chat][%s] 요청 수신 | ip=%s | message=%s | top_k=%d",
        request_id,
        client_ip,
        (request.message or "")[:80],
        request.top_k,
    )

    # ── 입력 검증 (top_k는 Pydantic 스키마에서 ge=1, le=20 처리됨) ──────────
    if len(request.message.strip()) < 2:
        logger.warning("[chat][%s] 메시지가 너무 짧음: %r", request_id, request.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="질문이 너무 짧습니다. 구체적으로 입력해 주세요.",
        )

    # ── RAG 호출 ───────────────────────────────────────────────────────────────
    # run_rag_chat() 내부에서 Chroma / LLM / 파싱 오류를 모두 잡고
    # fallback ChatResponse를 반환하므로 여기서는 예상치 못한 오류만 처리
    try:
        result: ChatResponse = run_rag_chat(
            message=request.message.strip(),
            user_profile=request.user_profile,
            top_k=request.top_k,
        )

        if result.warnings:
            logger.warning(
                "[chat][%s] RAG fallback 응답 반환 | warnings=%s",
                request_id,
                result.warnings,
            )
        else:
            logger.info(
                "[chat][%s] 정상 응답 반환 | route=%s | recs=%d",
                request_id,
                result.route,
                len(result.recommendations),
            )

        return result

    except HTTPException:
        raise

    except MemoryError as e:
        logger.critical("[chat][%s] MemoryError: %s", request_id, str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="서버 리소스가 부족합니다. 잠시 후 다시 시도해 주세요.",
        )

    except Exception as e:
        logger.error("[chat][%s] 예상치 못한 오류: %s", request_id, str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        )

