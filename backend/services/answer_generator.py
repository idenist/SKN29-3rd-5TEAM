import json
import os
import re
from typing import Any, Optional

from dotenv import load_dotenv
from openai import OpenAI

from backend.graph.prompts import (
    ANSWER_GENERATION_SYSTEM_PROMPT,
    ANSWER_GENERATION_USER_PROMPT_TEMPLATE,
)


load_dotenv()


DEFAULT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")


MISSING_TEXT = "제공된 데이터에는 정보가 없습니다."


def _get_client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default

    text = str(value).strip()

    if not text or text.lower() in {"none", "null", "unknown"}:
        return default

    return text


def _safe_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    text = str(value).strip()

    if not text:
        return []

    return [text]


def _truncate_text(text: str, max_chars: int = 1800) -> str:
    text = _safe_str(text)

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "...(이하 생략)"


def _extract_field_from_text(text: str, field_names: list[str]) -> Optional[str]:
    """
    chunk text에서 특정 필드 값을 간단히 추출한다.

    예:
    policy_summary: ...
    support_content: ...
    application_period_text: ...
    required_documents: ...
    """
    if not text:
        return None

    # 다음 필드가 나오기 전까지 잘라내기 위한 후보
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

    for field in field_names:
        pattern = rf"{re.escape(field)}\s*:\s*(.*?)(?=\n?(?:{'|'.join(map(re.escape, known_fields))})\s*:|$)"
        match = re.search(pattern, text, flags=re.DOTALL)

        if match:
            value = match.group(1).strip()
            if value:
                return value

    return None


def _get_policy_metadata(policy: dict[str, Any]) -> dict[str, Any]:
    metadata = policy.get("metadata") or {}
    return metadata if isinstance(metadata, dict) else {}


def _get_source_url(policy: dict[str, Any]) -> str:
    metadata = _get_policy_metadata(policy)
    return _safe_str(
        metadata.get("source_url")
        or policy.get("source_url")
        or metadata.get("application_url")
        or policy.get("application_url")
    )


def _compact_policy_for_prompt(policy: dict[str, Any]) -> dict[str, Any]:
    """
    LLM에 넘길 정책 정보를 필요한 필드만 남겨 압축한다.
    """
    metadata = _get_policy_metadata(policy)
    text = _safe_str(policy.get("text"))

    support_content = _extract_field_from_text(
        text,
        ["support_content", "policy_summary"],
    )

    application_period = _extract_field_from_text(
        text,
        ["application_period_text", "application_period"],
    )

    application_method = _extract_field_from_text(
        text,
        ["application_method"],
    )

    required_documents = _extract_field_from_text(
        text,
        ["required_documents"],
    )

    application_url = _extract_field_from_text(
        text,
        ["application_url"],
    )

    source_url = _get_source_url(policy)

    return {
        "policy_id": _safe_str(policy.get("policy_id")),
        "policy_name": _safe_str(policy.get("policy_name")),
        "domain": _safe_str(policy.get("domain")),
        "score": policy.get("score"),
        "eligibility": _safe_str(policy.get("eligibility"), "추가 확인 필요"),
        "matched_conditions": _safe_list(policy.get("matched_conditions")),
        "missing_conditions": _safe_list(policy.get("missing_conditions")),
        "cautions": _safe_list(policy.get("cautions")),
        "blockers": _safe_list(policy.get("blockers")),
        "support_content": support_content or MISSING_TEXT,
        "application_period": application_period or MISSING_TEXT,
        "application_method": application_method or MISSING_TEXT,
        "required_documents": required_documents or MISSING_TEXT,
        "source_url": source_url or MISSING_TEXT,
        "application_url": application_url or _safe_str(metadata.get("application_url")) or MISSING_TEXT,
        "needs_detail_check": metadata.get("needs_detail_check", policy.get("needs_detail_check")),
        "info_score": metadata.get("info_score", policy.get("info_score")),
        "raw_text_excerpt": _truncate_text(text, max_chars=1200),
    }


def _compact_policies_for_prompt(policies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_compact_policy_for_prompt(policy) for policy in policies]


def generate_answer_with_llm(
    query: str,
    user_conditions: dict[str, Any],
    policies: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
) -> str:
    """
    LLM을 사용해 최종 답변을 생성한다.
    단, 프롬프트에는 검색된 정책 데이터만 넣는다.
    """
    if not policies:
        return (
            "제공된 데이터에서 조건에 맞는 정책을 찾지 못했습니다. "
            "지역, 나이, 관심 분야 조건을 조금 넓혀 다시 검색해 주세요."
        )

    compact_policies = _compact_policies_for_prompt(policies)

    user_prompt = ANSWER_GENERATION_USER_PROMPT_TEMPLATE.format(
        query=query,
        user_conditions=json.dumps(user_conditions, ensure_ascii=False, indent=2),
        policies=json.dumps(compact_policies, ensure_ascii=False, indent=2),
    )

    client = _get_client()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": ANSWER_GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
    )

    return response.choices[0].message.content or ""


def _format_list(items: list[str]) -> str:
    if not items:
        return MISSING_TEXT

    return "\n".join([f"  - {item}" for item in items])


def generate_answer_rule_based(
    query: str,
    user_conditions: dict[str, Any],
    policies: list[dict[str, Any]],
) -> str:
    """
    LLM 없이도 동작하는 안전한 답변 생성기.
    Streamlit/FastAPI fallback으로 사용할 수 있다.
    """
    if not policies:
        return (
            "제공된 데이터에서 조건에 맞는 정책을 찾지 못했습니다. "
            "지역, 나이, 관심 분야 조건을 조금 넓혀 다시 검색해 주세요."
        )

    compact_policies = _compact_policies_for_prompt(policies)

    age = user_conditions.get("age")
    region = user_conditions.get("region")
    employment_status = user_conditions.get("employment_status")
    interest_domain = user_conditions.get("interest_domain")

    condition_parts = []

    if age is not None:
        condition_parts.append(f"{age}세")

    if region:
        condition_parts.append(str(region))

    if employment_status:
        condition_parts.append(str(employment_status))

    if interest_domain:
        condition_parts.append(f"{interest_domain} 분야")

    if condition_parts:
        answer_lines = [
            f"입력하신 조건({', '.join(condition_parts)})을 기준으로 제공된 정책 데이터에서 관련 정책을 찾았습니다.",
            "",
            "다만 아래 내용은 검색된 데이터 기준의 안내이며, 신청 가능 여부는 반드시 원문 또는 담당 기관에서 최종 확인해야 합니다.",
            "",
        ]
    else:
        answer_lines = [
            "입력하신 질문을 기준으로 제공된 정책 데이터에서 관련 정책을 찾았습니다.",
            "",
            "다만 아래 내용은 검색된 데이터 기준의 안내이며, 신청 가능 여부는 반드시 원문 또는 담당 기관에서 최종 확인해야 합니다.",
            "",
        ]

    for idx, policy in enumerate(compact_policies, start=1):
        policy_name = policy.get("policy_name") or "정책명 없음"
        eligibility = policy.get("eligibility") or "추가 확인 필요"

        source_url = policy.get("source_url") or MISSING_TEXT
        application_url = policy.get("application_url") or MISSING_TEXT

        support_content = policy.get("support_content") or MISSING_TEXT
        application_period = policy.get("application_period") or MISSING_TEXT
        application_method = policy.get("application_method") or MISSING_TEXT
        required_documents = policy.get("required_documents") or MISSING_TEXT

        matched_conditions = policy.get("matched_conditions") or []
        missing_conditions = policy.get("missing_conditions") or []
        cautions = policy.get("cautions") or []
        blockers = policy.get("blockers") or []

        reason = "사용자 질문과 조건에 대해 검색 유사도가 높고, 일부 조건이 정책 대상과 일치합니다."

        if blockers:
            reason = "검색 결과에는 포함되었지만, 일부 조건이 맞지 않을 가능성이 있습니다."
        elif eligibility == "가능성 높음":
            reason = "검색된 데이터 기준으로 주요 조건이 비교적 잘 충족됩니다."
        elif eligibility == "추가 확인 필요":
            reason = "검색된 데이터 기준으로 관련성이 있으나, 일부 조건은 원문 확인이 필요합니다."

        answer_lines.extend(
            [
                f"### {idx}. {policy_name}",
                f"- 추천 이유: {reason}",
                f"- 신청 가능성: {eligibility}",
                "- 충족 조건:",
                _format_list(matched_conditions),
                "- 추가 확인 필요:",
                _format_list(missing_conditions),
            ]
        )

        if blockers:
            answer_lines.extend(
                [
                    "- 불충족 가능 조건:",
                    _format_list(blockers),
                ]
            )

        answer_lines.extend(
            [
                f"- 지원 내용: {support_content}",
                f"- 신청 기간: {application_period}",
                f"- 신청 방법: {application_method}",
                f"- 제출 서류: {required_documents}",
                f"- 출처 URL: {source_url}",
                f"- 신청 URL: {application_url}",
                "- 유의사항:",
                _format_list(cautions),
                "",
            ]
        )

    return "\n".join(answer_lines).strip()


def generate_answer(
    query: str,
    user_conditions: dict[str, Any],
    policies: list[dict[str, Any]],
    use_llm: bool = True,
) -> str:
    """
    최종 Answer Generator 진입점.

    기본은 LLM 사용.
    LLM 호출 실패 시 rule-based 답변으로 fallback한다.
    """
    if use_llm:
        try:
            return generate_answer_with_llm(
                query=query,
                user_conditions=user_conditions,
                policies=policies,
            )
        except Exception as e:
            fallback_answer = generate_answer_rule_based(
                query=query,
                user_conditions=user_conditions,
                policies=policies,
            )
            return (
                f"{fallback_answer}\n\n"
                f"※ LLM 답변 생성 중 오류가 발생하여 규칙 기반 답변으로 대체했습니다: {repr(e)}"
            )

    return generate_answer_rule_based(
        query=query,
        user_conditions=user_conditions,
        policies=policies,
    )