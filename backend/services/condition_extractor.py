import json
import os
import re
import time

from openai import OpenAI, RateLimitError, APIStatusError, APITimeoutError
from typing import Any, Optional
from dotenv import load_dotenv


from backend.graph.prompts import (
    CONDITION_EXTRACTION_SYSTEM_PROMPT,
    CONDITION_EXTRACTION_USER_PROMPT_TEMPLATE,
    JSON_REPAIR_SYSTEM_PROMPT,
)


load_dotenv()


DEFAULT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")


DEFAULT_CONDITIONS = {
    "age": None,
    "region": None,
    "income": None,
    "employment_status": None,
    "company_type": None,
    "education_status": None,
    "major": None,
    "interest_domain": None,
    "keywords": [],
}


REGION_CODE_MAP = {
    "서울": "11000",
    "서울특별시": "11000",
    "부산": "26000",
    "부산광역시": "26000",
    "대구": "27000",
    "대구광역시": "27000",
    "인천": "28000",
    "인천광역시": "28000",
    "광주": "29000",
    "광주광역시": "29000",
    "대전": "30000",
    "대전광역시": "30000",
    "울산": "31000",
    "울산광역시": "31000",
    "세종": "36000",
    "세종특별자치시": "36000",
    "경기": "41000",
    "경기도": "41000",
    "강원": "51000",
    "강원도": "51000",
    "강원특별자치도": "51000",
    "충북": "43000",
    "충청북도": "43000",
    "충남": "44000",
    "충청남도": "44000",
    "전북": "52000",
    "전라북도": "52000",
    "전북특별자치도": "52000",
    "전남": "46000",
    "전라남도": "46000",
    "경북": "47000",
    "경상북도": "47000",
    "경남": "48000",
    "경상남도": "48000",
    "제주": "50000",
    "제주도": "50000",
    "제주특별자치도": "50000",
}


DOMAIN_KEYWORDS = {
    "일자리": ["취업", "일자리", "구직", "면접", "이력서", "자소서", "인턴", "재취업"],
    "주거": ["월세", "전세", "주거", "임대", "보증금", "주택", "집"],
    "금융": ["금융", "자산", "목돈", "저축", "적금", "대출", "청년도약", "통장"],
    "복지문화": ["복지", "문화", "건강", "심리", "상담", "생활비"],
    "교육": ["교육", "강의", "수업", "훈련", "자격증", "시험", "응시료"],
    "창업": ["창업", "사업", "스타트업", "예비창업"],
    "참여기반": ["참여", "위원", "네트워크", "정책참여", "청년참여"],
}


EMPLOYMENT_STATUS_KEYWORDS = {
    "취업준비생": ["취준생", "취업준비생", "구직자", "미취업", "취업 준비"],
    "재직자": ["재직자", "직장인", "근로자", "회사원", "일하고"],
    "창업자": ["창업자", "사업자", "자영업자"],
    "프리랜서": ["프리랜서"],
}


def _get_client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _chat_completion(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    max_retries: int = 2,        # 파라미터 추가
) -> str:
    client = _get_client()

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""

        except RateLimitError:
            # 429 — 잠깐 기다렸다 재시도
            if attempt < max_retries:
                time.sleep(2 ** attempt)  # 1초, 2초
                continue
            raise

        except APITimeoutError:
            # timeout — 바로 재시도
            if attempt < max_retries:
                time.sleep(1)
                continue
            raise

        except APIStatusError as e:
            # 5xx — 재시도 / 4xx — 재시도 의미 없으므로 바로 raise
            if e.status_code >= 500 and attempt < max_retries:
                time.sleep(1)
                continue
            raise


def _extract_json_object(text: str) -> str:
    """
    LLM 응답에서 JSON 객체 부분만 잘라낸다.
    """
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or start >= end:
        raise ValueError("JSON object not found in model output")

    return text[start : end + 1]


def _parse_json(text: str) -> dict[str, Any]:
    json_text = _extract_json_object(text)
    return json.loads(json_text)


def _repair_json(raw_text: str, query: str) -> dict[str, Any]:
    repair_input = f"""
사용자 질문:
{query}

고쳐야 할 출력:
{raw_text}
""".strip()

    repaired = _chat_completion(
        messages=[
            {"role": "system", "content": JSON_REPAIR_SYSTEM_PROMPT},
            {"role": "user", "content": repair_input},
        ],
        temperature=0.0,
    )

    return _parse_json(repaired)


def _safe_int_or_none(value: Any) -> Optional[int]:
    if value is None:
        return None

    if isinstance(value, int):
        return value

    text = str(value).strip()

    if not text or text.lower() in {"null", "none", "unknown"}:
        return None

    match = re.search(r"\d+", text)

    if not match:
        return None

    return int(match.group())


def _safe_str_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()

    if not text or text.lower() in {"null", "none", "unknown"}:
        return None

    return text


def _normalize_keywords(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        keywords = [str(item).strip() for item in value if str(item).strip()]
    else:
        keywords = [word.strip() for word in str(value).split(",") if word.strip()]

    # 중복 제거, 최대 5개
    return list(dict.fromkeys(keywords))[:5]


def _infer_age_rule_based(query: str) -> Optional[int]:
    patterns = [
        r"(\d{1,2})\s*세",
        r"(\d{1,2})\s*살",
        r"만\s*(\d{1,2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            return int(match.group(1))

    return None


def _infer_region_code(region: Optional[str]) -> Optional[str]:
    if not region:
        return None

    region = region.strip()

    # 긴 이름 우선 매칭
    for name, code in sorted(REGION_CODE_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if name in region:
            return code

    return None


def _infer_interest_domain_rule_based(query: str) -> Optional[str]:
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(keyword in query for keyword in keywords):
            return domain

    return None


def _infer_employment_status_rule_based(query: str) -> Optional[str]:
    for status, keywords in EMPLOYMENT_STATUS_KEYWORDS.items():
        if any(keyword in query for keyword in keywords):
            return status

    return None


def _normalize_interest_domain(value: Optional[str], query: str) -> Optional[str]:
    value = _safe_str_or_none(value)

    if value is None:
        return _infer_interest_domain_rule_based(query)

    aliases = {
        "취업": "일자리",
        "구직": "일자리",
        "고용": "일자리",
        "일자리": "일자리",
        "주거": "주거",
        "월세": "주거",
        "금융": "금융",
        "자산": "금융",
        "저축": "금융",
        "복지": "복지문화",
        "문화": "복지문화",
        "복지문화": "복지문화",
        "교육": "교육",
        "자격증": "교육",
        "창업": "창업",
        "참여": "참여기반",
        "청년참여": "참여기반",
        "참여기반": "참여기반",
        "unknown": None,
    }

    if value in aliases:
        return aliases[value]

    # "일자리 > 취업" 같은 값이 오면 앞부분 기준으로 처리
    for key, normalized in aliases.items():
        if key and key in value:
            return normalized

    return value


def _postprocess_conditions(raw: dict[str, Any], query: str) -> dict[str, Any]:
    """
    LLM 결과를 서비스 내부에서 쓰기 좋은 형태로 정규화한다.
    """
    result = dict(DEFAULT_CONDITIONS)

    for key in DEFAULT_CONDITIONS:
        if key in raw:
            result[key] = raw[key]

    result["age"] = _safe_int_or_none(result.get("age"))

    # LLM이 age를 놓친 경우만 규칙 기반 보완
    if result["age"] is None:
        result["age"] = _infer_age_rule_based(query)

    result["region"] = _safe_str_or_none(result.get("region"))
    result["income"] = _safe_str_or_none(result.get("income"))
    result["employment_status"] = _safe_str_or_none(result.get("employment_status"))
    result["company_type"] = _safe_str_or_none(result.get("company_type"))
    result["education_status"] = _safe_str_or_none(result.get("education_status"))
    result["major"] = _safe_str_or_none(result.get("major"))

    if result["employment_status"] is None:
        result["employment_status"] = _infer_employment_status_rule_based(query)

    result["interest_domain"] = _normalize_interest_domain(
        result.get("interest_domain"),
        query=query,
    )

    result["keywords"] = _normalize_keywords(result.get("keywords"))

    # Retriever filters에 바로 쓰기 위한 보조 필드
    result["region_code"] = _infer_region_code(result.get("region"))

    return result


def extract_conditions(
    query: str,
    max_retries: int = 1,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """
    사용자 질문에서 정책 검색 조건을 추출한다.

    반환 예시:
    {
        "age": 25,
        "region": "서울",
        "income": None,
        "employment_status": "취업준비생",
        "company_type": None,
        "education_status": None,
        "major": None,
        "interest_domain": "일자리",
        "keywords": ["취업", "지원"],
        "region_code": "11000"
    }
    """
    if not query or not query.strip():
        result = dict(DEFAULT_CONDITIONS)
        result["region_code"] = None
        return result

    user_prompt = CONDITION_EXTRACTION_USER_PROMPT_TEMPLATE.format(query=query)

    messages = [
        {"role": "system", "content": CONDITION_EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    last_output = ""

    for attempt in range(max_retries + 1):
        try:
            last_output = _chat_completion(
                messages=messages,
                model=model,
                temperature=0.0,
            )
            parsed = _parse_json(last_output)
            return _postprocess_conditions(parsed, query=query)

        except Exception:
            if attempt >= max_retries:
                break

    # JSON 파싱 실패 시 repair 한 번 시도
    try:
        repaired = _repair_json(last_output, query=query)
        return _postprocess_conditions(repaired, query=query)
    except Exception:
        # 최종 fallback: 규칙 기반 최소 추출
        fallback = dict(DEFAULT_CONDITIONS)
        fallback["age"] = _infer_age_rule_based(query)
        fallback["employment_status"] = _infer_employment_status_rule_based(query)
        fallback["interest_domain"] = _infer_interest_domain_rule_based(query)
        fallback["keywords"] = []
        fallback["region_code"] = None
        return fallback


def conditions_to_retriever_filters(conditions: dict[str, Any]) -> dict[str, Any]:
    """
    condition_extractor 결과를 retrieve_policies filters 형식으로 변환한다.
    """
    filters = {}

    if conditions.get("age") is not None:
        filters["user_age"] = conditions["age"]

    if conditions.get("region_code"):
        filters["user_region_code"] = conditions["region_code"]

    if conditions.get("interest_domain"):
        filters["domain"] = conditions["interest_domain"]

    return filters


def build_query_from_conditions(original_query: str, conditions: dict[str, Any]) -> str:
    """
    원문 질문에 추출된 키워드를 보강해서 Retriever query로 사용한다.
    """
    keywords = conditions.get("keywords") or []

    if not keywords:
        return original_query

    keyword_text = " ".join(keywords)

    return f"{original_query}\n검색 키워드: {keyword_text}"