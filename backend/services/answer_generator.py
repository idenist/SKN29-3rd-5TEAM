import json
import os
import re
import time

from openai import OpenAI, RateLimitError, APIStatusError, APITimeoutError
from typing import Any, Optional
from dotenv import load_dotenv


from backend.graph.prompts import (
    ANSWER_GENERATION_SYSTEM_PROMPT,
    ANSWER_GENERATION_USER_PROMPT_TEMPLATE,
)


load_dotenv()


DEFAULT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5.4-nano")
MISSING_TEXT = "제공된 데이터에는 정보가 없습니다."

# temperature / top_p use-case별 파라미터
LLM_PARAMS_BY_ROUTE = {
    "질의응답":  {"temperature": 0.2, "top_p": 0.9},   # 기본 QA
    "일자리":    {"temperature": 0.2, "top_p": 0.9},
    "주거":      {"temperature": 0.2, "top_p": 0.9},
    "교육":      {"temperature": 0.3, "top_p": 0.95},  # 교육훈련은 설명 다양성 허용
    "복지문화":  {"temperature": 0.3, "top_p": 0.95},
    "참여권리":  {"temperature": 0.3, "top_p": 0.95},
    "금융":      {"temperature": 0.1, "top_p": 0.85},  # 금융은 정확성 최우선
    "창업":      {"temperature": 0.3, "top_p": 0.95},
    "전체":      {"temperature": 0.3, "top_p": 0.95},
    "요약":      {"temperature": 0.5, "top_p": 0.95},  # 요약 use-case
}
LLM_PARAMS_DEFAULT = {"temperature": 0.2, "top_p": 0.9}




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


def _clean_text_for_answer(text: str) -> str:
    text = _safe_str(text)

    # HTML 태그 제거
    text = re.sub(r"<[^>]+>", "", text)

    # 공백 정리
    text = re.sub(r"\r\n?", "\n", text)

    # 중복 줄 제거
    lines = []
    seen = set()

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if line in seen:
            continue

        seen.add(line)
        lines.append(line)

    return "\n".join(lines)


def _extract_field_from_text(text: str, field_names: list[str]) -> Optional[str]:
    """
    chunk text에서 특정 필드 값을 간단히 추출한다.

    예:
    policy_summary: ...
    support_content: ...
    application_period_text: ...
    required_documents: ...
    훈련기간: ...
    신청기간: ...
    """
    if not text:
        return None

    # 다음 필드가 나오기 전까지 잘라내기 위한 후보
    # 영어 필드와 한글 필드를 모두 넣는다.
    known_fields = [
        # policy / 기존 구조
        "policy_summary",
        "support_content",
        "application_period_text",
        "application_period",
        "application_method",
        "required_documents",
        "screening_method",
        "application_url",
        "age_text",
        "region_codes",
        "income_condition",
        "employment_status",
        "source_url",

        # training / HRD·고용24
        "훈련과정명",
        "훈련기관",
        "훈련유형",
        "훈련대상",
        "지역",
        "훈련기간",
        "훈련비/지원정보",
        "NCS코드",
        "상세URL",
        "청년 관련성",

        # startup_notice / K-Startup
        "공고명",
        "분야",
        "지원사업분류",
        "요약",
        "신청대상",
        "신청기간",
        "신청방법",
        "접수기간",
        "모집기간",
        "제출서류",
        "구비서류",
        "문의처",
        "기관명",
        "주관기관",
    ]

    field_pattern = "|".join(map(re.escape, known_fields))

    for field in field_names:
        pattern = rf"{re.escape(field)}\s*:\s*(.*?)(?=\n?(?:{field_pattern})\s*:|$)"
        match = re.search(pattern, text, flags=re.DOTALL)

        if match:
            value = _clean_text_for_answer(match.group(1).strip())
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


def _get_application_url(policy: dict[str, Any], text: str = "") -> str:
    metadata = _get_policy_metadata(policy)

    extracted_url = _extract_field_from_text(
        text,
        ["application_url", "상세URL"],
    )

    return _safe_str(
        extracted_url
        or metadata.get("application_url")
        or policy.get("application_url")
    )


def _get_item_type_label(source_category: str) -> str:
    if source_category == "training":
        return "교육훈련 과정"

    if source_category == "startup_notice":
        return "창업지원 공고"

    if source_category == "policy":
        return "정책"

    return "지원 정보"


def _get_item_collection_label(compact_policies: list[dict[str, Any]]) -> str:
    labels = {
        _safe_str(policy.get("item_type_label"))
        for policy in compact_policies
        if _safe_str(policy.get("item_type_label"))
    }

    if len(labels) == 1:
        label = next(iter(labels))
        if label == "교육훈련 과정":
            return "교육훈련 과정"
        if label == "창업지원 공고":
            return "창업지원 공고"
        if label == "정책":
            return "정책"

    return "지원 정보"


def _format_deadline_status(policy: dict[str, Any]) -> str:
    deadline_status = _safe_str(policy.get("deadline_status"))
    application_end_date = _safe_str(policy.get("application_end_date"))
    is_expired = bool(policy.get("is_expired"))

    if is_expired or deadline_status == "expired":
        if application_end_date:
            return f"마감됨({application_end_date} 종료)"
        return "마감됨"

    if deadline_status == "open":
        if application_end_date:
            return f"신청 가능성 있음({application_end_date}까지)"
        return "신청 가능성 있음"

    if deadline_status == "unknown":
        return "마감일 확인 필요"

    return MISSING_TEXT


def _compact_policy_for_prompt(policy: dict[str, Any]) -> dict[str, Any]:
    """
    LLM에 넘길 지원 정보를 필요한 필드만 남겨 압축한다.
    policy/startup_notice/training을 모두 처리한다.
    """
    metadata = _get_policy_metadata(policy)
    text = _safe_str(policy.get("text"))

    source_category = _safe_str(
        policy.get("source_category")
        or metadata.get("source_category")
    )
    item_type_label = _get_item_type_label(source_category)

    item_id = _safe_str(
        policy.get("item_id")
        or metadata.get("item_id")
        or policy.get("policy_id")
        or metadata.get("policy_id")
    )

    title = _safe_str(
        policy.get("title")
        or metadata.get("title")
        or policy.get("policy_name")
        or metadata.get("policy_name")
    )

    raw_text_excerpt = _clean_text_for_answer(
        _truncate_text(text, max_chars=600)
    )

    support_content = _extract_field_from_text(
        text,
        [
            "support_content",
            "policy_summary",
            "요약",
            "훈련과정명",
            "공고명",
        ],
    )

    training_period = _extract_field_from_text(
        text,
        ["훈련기간", "training_period", "program_period_text"],
    )

    application_period = _extract_field_from_text(
        text,
        [
            "application_period_text",
            "application_period",
            "신청기간",
            "접수기간",
            "모집기간",
        ],
    )

    application_method = _extract_field_from_text(
        text,
        ["application_method", "신청방법"],
    )

    required_documents = _extract_field_from_text(
        text,
        ["required_documents", "제출서류", "제출 서류", "구비서류"],
    )

    training_institution = _extract_field_from_text(
        text,
        ["훈련기관", "기관명", "주관기관"],
    )

    training_target = _extract_field_from_text(
        text,
        ["훈련대상", "신청대상"],
    )

    training_cost = _extract_field_from_text(
        text,
        ["훈련비/지원정보"],
    )

    region = _extract_field_from_text(
        text,
        ["지역"],
    )

    application_url = _get_application_url(policy, text)
    source_url = _get_source_url(policy)

    deadline_status = _safe_str(
        policy.get("deadline_status")
        or metadata.get("deadline_status")
    )
    application_end_date = _safe_str(
        policy.get("application_end_date")
        or metadata.get("application_end_date")
    )
    is_expired = bool(
        policy.get("is_expired")
        if policy.get("is_expired") is not None
        else metadata.get("is_expired", False)
    )

    # training/startup_notice는 구조화 정책 필드가 비어 있는 경우가 많으므로
    # 주요 내용에는 정리된 원문 일부를 fallback으로 사용한다.
    if not support_content and source_category in {"training", "startup_notice"}:
        support_content = raw_text_excerpt

    return {
        "policy_id": item_id,
        "policy_name": title,
        "item_id": item_id,
        "title": title,
        "source_category": source_category,
        "item_type_label": item_type_label,

        "domain": _safe_str(policy.get("domain") or metadata.get("domain")),
        "score": policy.get("score"),
        "eligibility": _safe_str(policy.get("eligibility"), "추가 확인 필요"),
        "matched_conditions": _safe_list(policy.get("matched_conditions")),
        "missing_conditions": _safe_list(policy.get("missing_conditions")),
        "cautions": _safe_list(policy.get("cautions")),
        "blockers": _safe_list(policy.get("blockers")),

        "support_content": support_content or MISSING_TEXT,
        "training_period": training_period or MISSING_TEXT,
        "application_period": application_period or training_period or MISSING_TEXT,
        "application_method": application_method or MISSING_TEXT,
        "required_documents": required_documents or MISSING_TEXT,
        "training_institution": training_institution or MISSING_TEXT,
        "training_target": training_target or MISSING_TEXT,
        "training_cost": training_cost or MISSING_TEXT,
        "region": region or MISSING_TEXT,

        "source_url": source_url or application_url or MISSING_TEXT,
        "application_url": application_url or MISSING_TEXT,
        "needs_detail_check": metadata.get("needs_detail_check", policy.get("needs_detail_check")),
        "info_score": metadata.get("info_score", policy.get("info_score")),
        "raw_text_excerpt": raw_text_excerpt,

        "deadline_status": deadline_status or MISSING_TEXT,
        "application_end_date": application_end_date or MISSING_TEXT,
        "is_expired": is_expired,
        "deadline_display": _format_deadline_status(
            {
                "deadline_status": deadline_status,
                "application_end_date": application_end_date,
                "is_expired": is_expired,
            }
        ),
    }


def _compact_policies_for_prompt(policies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_compact_policy_for_prompt(policy) for policy in policies]


def generate_answer_with_llm(
    query: str,
    user_conditions: dict[str, Any],
    policies: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
    graph_context: str = "",          # ← 파라미터 추가
    route: str = "",
) -> str:
    """
    LLM을 사용해 최종 답변을 생성한다.
    단, 프롬프트에는 검색된 데이터만 넣는다.
    """
    if not policies:
        return (
            "제공된 데이터에서 조건에 맞는 지원 정보를 찾지 못했습니다. "
            "지역, 나이, 관심 분야 조건을 조금 넓혀 다시 검색해 주세요."
        )

    compact_policies = _compact_policies_for_prompt(policies)

    user_prompt = ANSWER_GENERATION_USER_PROMPT_TEMPLATE.format(
        query=query,
        user_conditions=json.dumps(user_conditions, ensure_ascii=False, indent=2),
        policies=json.dumps(compact_policies, ensure_ascii=False, indent=2),
    )

    # ← 이 줄 추가
    if graph_context:
        user_prompt += f"\n\n[Graph DB 관계 검색 보완 결과]\n{graph_context}"

    client = _get_client()
    max_retries = 2
    answer = ""

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": ANSWER_GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                **LLM_PARAMS_BY_ROUTE.get(route, LLM_PARAMS_DEFAULT),
                max_tokens = 1500,
            )
            answer = response.choices[0].message.content or ""
            break  # 성공 시 루프 탈출

        except RateLimitError:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise

        except APITimeoutError:
            if attempt < max_retries:
                time.sleep(1)
                continue
            raise

        except APIStatusError as e:
            if e.status_code >= 500 and attempt < max_retries:
                time.sleep(1)
                continue
            raise

    # 검색 결과가 있는데도 LLM이 no-result 문구를 따라 쓰는 경우 방지
    if policies:
        bad_sentences = [
            "제공된 데이터에서 조건에 맞는 정책을 찾지 못했습니다. 지역, 나이, 관심 분야 조건을 조금 넓혀 다시 검색해 주세요.",
            "제공된 데이터에서 조건에 맞는 지원 정보를 찾지 못했습니다. 지역, 나이, 관심 분야 조건을 조금 넓혀 다시 검색해 주세요.",
            "위의 정보들을 참고하여 관심 있는 교육 과정을 확인해 보시기 바랍니다.",
            "위의 정보를 참고하여 관심 있는 교육 과정을 확인해 보시기 바랍니다.",
            "위의 정보들을 참고하여 관심 있는 항목을 확인해 보시기 바랍니다.",
            "위의 정보들을 참고하여 적합한 지원사업에 참여하시기 바랍니다.",
        ]

        for bad_sentence in bad_sentences:
            answer = answer.replace(bad_sentence, "").strip()

    return answer


def _format_list(items: list[str]) -> str:
    if not items:
        return MISSING_TEXT

    return "\n".join([f"  - {item}" for item in items])


def _build_condition_summary(user_conditions: dict[str, Any]) -> str:
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
        return f"입력하신 조건({', '.join(condition_parts)})"

    return "입력하신 질문"


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
            "제공된 데이터에서 조건에 맞는 지원 정보를 찾지 못했습니다. "
            "지역, 나이, 관심 분야 조건을 조금 넓혀 다시 검색해 주세요."
        )

    compact_policies = _compact_policies_for_prompt(policies)
    collection_label = _get_item_collection_label(compact_policies)
    condition_summary = _build_condition_summary(user_conditions)

    answer_lines = [
        f"{condition_summary}을 기준으로 제공된 데이터에서 관련 {collection_label}을 찾았습니다.",
        "",
        "아래 내용은 검색된 데이터 기준의 안내이며, 신청/참여 가능 여부는 반드시 원문 또는 담당 기관에서 최종 확인해야 합니다.",
        "",
    ]

    for idx, policy in enumerate(compact_policies, start=1):
        title = policy.get("title") or policy.get("policy_name") or "항목명 없음"
        item_type_label = policy.get("item_type_label") or "지원 정보"
        eligibility = policy.get("eligibility") or "추가 확인 필요"

        source_url = policy.get("source_url") or MISSING_TEXT
        application_url = policy.get("application_url") or MISSING_TEXT

        support_content = policy.get("support_content") or MISSING_TEXT
        application_period = policy.get("application_period") or MISSING_TEXT
        application_method = policy.get("application_method") or MISSING_TEXT
        required_documents = policy.get("required_documents") or MISSING_TEXT
        deadline_display = policy.get("deadline_display") or _format_deadline_status(policy)
        is_expired = bool(policy.get("is_expired"))

        matched_conditions = policy.get("matched_conditions") or []
        missing_conditions = policy.get("missing_conditions") or []
        cautions = policy.get("cautions") or []
        blockers = policy.get("blockers") or []

        reason = f"사용자 질문과 관련성이 높은 {item_type_label}으로 검색되었습니다."

        if is_expired and "마감" not in "\n".join(blockers + cautions):
            cautions.append("마감된 항목일 수 있으므로 현재 신청 가능 항목으로 단정하지 않습니다.")

        if blockers:
            reason = "검색 결과에는 포함되었지만, 일부 조건이 맞지 않을 가능성이 있습니다."
        elif eligibility == "가능성 높음":
            reason = "검색된 데이터 기준으로 주요 조건이 비교적 잘 충족됩니다."
        elif eligibility == "추가 확인 필요":
            reason = "검색된 데이터 기준으로 관련성이 있으나, 일부 조건은 원문 확인이 필요합니다."

        answer_lines.extend(
            [
                f"### {idx}. {title}",
                f"- 항목 유형: {item_type_label}",
                f"- 추천 이유: {reason}",
                f"- 신청/참여 가능성: {eligibility}",
                f"- 마감 상태: {deadline_display}",
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

        if item_type_label == "교육훈련 과정":
            answer_lines.extend(
                [
                    f"- 주요 내용: {support_content}",
                    f"- 훈련 기간: {application_period}",
                    f"- 훈련 기관: {policy.get('training_institution') or MISSING_TEXT}",
                    f"- 훈련 대상: {policy.get('training_target') or MISSING_TEXT}",
                    f"- 훈련비/지원 정보: {policy.get('training_cost') or MISSING_TEXT}",
                    f"- 지역: {policy.get('region') or MISSING_TEXT}",
                    f"- 신청/접수 방법: {application_method}",
                    f"- 제출 서류: {required_documents}",
                ]
            )
        else:
            answer_lines.extend(
                [
                    f"- 주요 내용: {support_content}",
                    f"- 신청/접수 기간: {application_period}",
                    f"- 신청/접수 방법: {application_method}",
                    f"- 제출 서류: {required_documents}",
                ]
            )

        answer_lines.extend(
            [
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
    graph_context: str = "",          # ← 추가
    route: str = "",
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
                graph_context=graph_context,   # ← 추가
                route=route,          # ← 추가
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
