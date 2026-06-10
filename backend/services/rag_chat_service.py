from typing import Any

from backend.graph.workflow import run_rag_workflow
from backend.schemas.chat_schema import (
    ChatResponse,
    UserConditions,
    PolicyRecommendation,
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

    source_url = (
        _safe_str(metadata.get("source_url"))
        or _safe_str(policy.get("source_url"))
        or "정보 없음"
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
        policy_id=_safe_str(policy.get("policy_id")),
        policy_name=_safe_str(policy.get("policy_name")),
        eligibility=_safe_str(policy.get("eligibility"), "추가 확인 필요"),
        score=_safe_float(policy.get("score")),
        reason=_build_reason(policy),
        support_content=support_content,
        application_period=application_period,
        required_documents=required_documents,
        source_url=source_url,
        needs_detail_check=_safe_bool(
            metadata.get("needs_detail_check", policy.get("needs_detail_check")),
            default=True,
        ),
        cautions=cautions,
    )


def _workflow_result_to_chat_response(raw: dict[str, Any]) -> ChatResponse:
    conditions = raw.get("user_conditions") or {}
    recommendations = raw.get("recommendations") or raw.get("eligibility_results") or []

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
        recommendations=[
            _policy_to_recommendation(policy)
            for policy in recommendations
        ],
        warnings=_safe_list(raw.get("warnings")),
    )


def run_rag_chat(
    message: str,
    user_profile: Any = None,
    top_k: int = 5,
) -> ChatResponse:
    """
    FastAPI chat.py에서 호출하는 RAG 어댑터 함수.

    chat.py는 API 입출력만 담당하고,
    실제 RAG workflow 실행 및 ChatResponse 변환은 이 함수에서 처리한다.
    """
    raw = run_rag_workflow(
        query=message,
        return_full_state=False,
    )

    return _workflow_result_to_chat_response(raw)