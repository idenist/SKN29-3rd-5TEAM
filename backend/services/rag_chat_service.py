import logging
from typing import Any

from backend.graph.workflow import run_rag_workflow
from backend.schemas.chat_schema import (
    ChatResponse,
    UserConditions,
    PolicyRecommendation,
)

logger = logging.getLogger(__name__)

# ── 상수 ──────────────────────────────────────────────────────────────────────
FALLBACK_ANSWER = (
    "죄송합니다. 현재 정책 검색 서비스에 일시적인 문제가 발생했습니다. "
    "잠시 후 다시 시도하거나 온통청년(https://www.youthcenter.go.kr)에서 직접 확인해 주세요."
)
 
 
# ── 커스텀 예외 ────────────────────────────────────────────────────────────────
class WorkflowParsingError(Exception):
    pass
 
 
# ── fallback 응답 생성 ─────────────────────────────────────────────────────────
def _build_fallback_response(error_detail: str) -> ChatResponse:
    logger.warning("[RAG fallback] %s", error_detail)
    return ChatResponse(
        answer=FALLBACK_ANSWER,
        user_conditions=UserConditions(),
        route="알 수 없음",
        route_reason="오류로 인해 라우팅 불가",
        recommendations=[],
        warnings=[f"시스템 오류: {error_detail}"],
        tool_trace=[],
        internal_search_sufficient=False,
        sufficiency_reasons=["workflow 실행 중 오류가 발생했습니다."],
        next_action="fallback_response",
        external_used=False,
        external_search_status="error",
        external_search_targets=[],
        external_search_queries=[],
    )



def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default

    text = str(value).strip()

    if not text or text.lower() in {"none", "null", "unknown"}:
        return default

    return text


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()

    if text in {"true", "1", "yes", "y"}:
        return True

    if text in {"false", "0", "no", "n"}:
        return False

    return default


def _safe_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    text = str(value).strip()
    return [text] if text else []


def _safe_tool_trace(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    trace: list[dict[str, Any]] = []

    for item in value:
        if isinstance(item, dict):
            trace.append(item)
        else:
            trace.append({"observation": str(item)})

    return trace


def _extract_field_from_text(text: str, field_name: str) -> str:
    if not text:
        return ""

    import re

    known_fields = [
        "policy_summary",
        "support_content",
        "application_period_text",
        "application_method",
        "required_documents",
        "screening_method",
        "application_url",
        "age_text",
        "region_codes",
        "income_condition",
        "employment_status",
        "source_url",
    ]

    pattern = rf"{re.escape(field_name)}\s*:\s*(.*?)(?=\n?(?:{'|'.join(map(re.escape, known_fields))})\s*:|$)"
    match = re.search(pattern, text, flags=re.DOTALL)

    if not match:
        return ""

    return match.group(1).strip()


def _build_reason(policy: dict[str, Any]) -> str:
    eligibility = _safe_str(policy.get("eligibility"), "추가 확인 필요")
    blockers = _safe_list(policy.get("blockers"))
    missing = _safe_list(policy.get("missing_conditions"))

    if blockers:
        return "검색 결과에는 포함되었지만 일부 조건이 맞지 않을 가능성이 있습니다."

    if eligibility == "가능성 높음":
        return "검색된 정책 데이터 기준으로 주요 조건이 비교적 잘 충족됩니다."

    if missing:
        return "검색된 정책 데이터 기준으로 관련성이 있으나 일부 조건은 추가 확인이 필요합니다."

    return "사용자 질문과 조건에 대해 검색 유사도가 높은 정책입니다."


def _policy_to_recommendation(policy: dict[str, Any]) -> PolicyRecommendation:
    metadata = policy.get("metadata") or {}
    text = _safe_str(policy.get("text"))
    
    item_id = (
        _safe_str(policy.get("item_id"))
        or _safe_str(metadata.get("item_id"))
        or _safe_str(policy.get("policy_id"))
        or _safe_str(metadata.get("policy_id"))
    )

    title = (
        _safe_str(policy.get("title"))
        or _safe_str(metadata.get("title"))
        or _safe_str(policy.get("policy_name"))
        or _safe_str(metadata.get("policy_name"))
    )

    domain = (
        _safe_str(policy.get("domain"))
        or _safe_str(metadata.get("domain"))
        or None
    )

    summary = (
        _safe_str(policy.get("summary"))
        or _safe_str(metadata.get("summary"))
        or _extract_field_from_text(text, "policy_summary")
        or None
    )

    source_url = (
        _safe_str(metadata.get("source_url"))
        or _safe_str(policy.get("source_url"))
        or None
    )
    
    application_url = (
        _safe_str(metadata.get("application_url"))
        or _safe_str(policy.get("application_url"))
        or _extract_field_from_text(text, "application_url")
        or None
    )

    support_content = (
        _extract_field_from_text(text, "support_content")
        or _extract_field_from_text(text, "policy_summary")
        or "정보 없음"
    )

    application_period = (
        _extract_field_from_text(text, "application_period_text")
        or "정보 없음"
    )

    required_documents = (
        _extract_field_from_text(text, "required_documents")
        or "정보 없음"
    )

    cautions = _safe_list(policy.get("cautions"))
    blockers = _safe_list(policy.get("blockers"))

    if blockers:
        cautions += [f"불충족 가능 조건: {item}" for item in blockers]

    return PolicyRecommendation(
        item_id=item_id,
        title=title,
        policy_id=item_id,
        policy_name=title,

        source_category=_safe_str(policy.get("source_category") or metadata.get("source_category")),
        domain=domain,
        summary=summary,

        eligibility=_safe_str(policy.get("eligibility"), "추가 확인 필요"),
        score=_safe_float(policy.get("score")),
        reason=_build_reason(policy),

        support_content=support_content,
        application_period=application_period,
        required_documents=required_documents,

        source_url=source_url,
        application_url=application_url,

        needs_detail_check=_safe_bool(
            metadata.get("needs_detail_check", policy.get("needs_detail_check")),
            default=True,
        ),
        cautions=cautions,
        deadline_status=_safe_str(
            policy.get("deadline_status") or metadata.get("deadline_status"),
            "unknown",
        ),
        application_end_date=(
            policy.get("application_end_date")
            or metadata.get("application_end_date")
        ),
        is_expired=_safe_bool(
            policy.get("is_expired", metadata.get("is_expired")),
            default=False,
        ),
    )
    
def _workflow_result_to_chat_response(raw: dict[str, Any]) -> ChatResponse:
    if not isinstance(raw, dict):
        raise WorkflowParsingError(f"workflow가 dict가 아닌 타입을 반환: {type(raw)}")
 
    conditions = raw.get("user_conditions") or {}
    recommendations_raw = raw.get("recommendations") or raw.get("eligibility_results") or []
 
    parsed_recs = []
    for idx, policy in enumerate(recommendations_raw):
        try:
            parsed_recs.append(_policy_to_recommendation(policy))
        except Exception as e:
            logger.warning("recommendations[%d] 파싱 실패, 건너뜀: %s", idx, e)
 
    return ChatResponse(
        answer=_safe_str(raw.get("answer")),
        user_conditions=UserConditions(
            age=conditions.get("age"),
            region=conditions.get("region"),
            income=conditions.get("income"),
            employment_status=conditions.get("employment_status"),
            interest_domain=conditions.get("interest_domain"),
        ),
        route=_safe_str(raw.get("route"), "전체"),
        route_reason=raw.get("route_reason"),
        recommendations=parsed_recs,
        warnings=_safe_list(raw.get("warnings")),
        tool_trace=_safe_tool_trace(raw.get("tool_trace")),
        internal_search_sufficient=_safe_bool(
            raw.get("internal_search_sufficient"),
            default=False,
        ),
        sufficiency_reasons=_safe_list(raw.get("sufficiency_reasons")),
        next_action=_safe_str(raw.get("next_action")),
        external_used=_safe_bool(raw.get("external_used"), default=False),
        external_search_status=_safe_str(raw.get("external_search_status")),
        external_search_targets=_safe_list(raw.get("external_search_targets")),
        external_search_queries=_safe_list(raw.get("external_search_queries")),
    )

# FastAPI /api/chat 엔드포인트의 실제 RAG 처리 진입점
def run_rag_chat(
    message: str,
    user_profile: Any = None,
    top_k: int = 5,
) -> ChatResponse:
    """
    FastAPI chat.py에서 호출하는 RAG 어댑터 함수.
    Chroma 연결 오류 / LLM 오류 / 파싱 오류 발생 시 fallback ChatResponse 반환.
    """
    try:
        raw = run_rag_workflow(
            query=message,
            top_k=top_k,
            return_full_state=False,
        )
        return _workflow_result_to_chat_response(raw)
 
    except WorkflowParsingError as e:
        logger.error("workflow 파싱 오류: %s", e)
        return _build_fallback_response(str(e))
 
    except (ConnectionError, OSError) as e:
        logger.error("Chroma 연결 오류: %s", e, exc_info=True)
        return _build_fallback_response(str(e))
 
    except Exception as e:
        err = str(e).lower()
        if any(k in err for k in ("ratelimit", "rate limit", "429")):
            logger.error("LLM RateLimit: %s", e)
        elif any(k in err for k in ("timeout", "timed out")):
            logger.error("LLM 타임아웃: %s", e)
        elif any(k in err for k in ("apiconnectionerror", "authenticationerror", "401")):
            logger.error("LLM 연결/인증 오류: %s", e)
        else:
            logger.error("workflow 알 수 없는 오류: %s", e, exc_info=True)
        return _build_fallback_response(str(e))

