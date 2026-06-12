import re
from typing import Any, Optional


ELIGIBILITY_HIGH = "가능성 높음"
ELIGIBILITY_NEED_CHECK = "추가 확인 필요"
ELIGIBILITY_LOW = "가능성 낮음"


SEOUL_GU_PREFIX = "11"


SIDO_CODE_MAP = {
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


def _safe_int(value: Any, default: int = -1) -> int:
    if value is None or value == "":
        return default

    if isinstance(value, bool):
        return default

    if isinstance(value, int):
        return value

    try:
        return int(float(str(value).strip()))
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


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _normalize_codes(region_code: Any) -> list[str]:
    """
    region_code가 "11110,11140" 또는 "전국" 형태로 들어와도 list로 정리한다.
    """
    if region_code is None:
        return []

    if isinstance(region_code, list):
        raw_text = ",".join([str(item) for item in region_code])
    else:
        raw_text = str(region_code)

    raw_text = raw_text.strip()

    if not raw_text:
        return []

    if raw_text in {"전국", "전체", "ALL", "00000"}:
        return ["전국"]

    codes = re.findall(r"\d{5}", raw_text)

    if codes:
        return list(dict.fromkeys(codes))

    return [raw_text]


def _infer_user_region_code(user_conditions: dict[str, Any]) -> Optional[str]:
    region_code = user_conditions.get("region_code") or user_conditions.get("user_region_code")

    if region_code:
        return str(region_code).strip()

    region = _safe_str(user_conditions.get("region"))

    if not region:
        return None

    for name, code in sorted(SIDO_CODE_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if name in region:
            return code

    return None


def _is_national_policy(policy_region_codes: list[str], policy_text: str) -> bool:
    if "전국" in policy_region_codes:
        return True

    if any(code in {"00000", "ALL"} for code in policy_region_codes):
        return True

    if "전국" in policy_text or "전국 공통" in policy_text:
        return True

    return False


def _match_region_by_code(
    user_region_code: Optional[str],
    policy_region_code: Any,
    policy_text: str,
    item_type_label: str = "정책",
) -> tuple[str, str]:
    """
    반환:
    - status: matched | missing | unmatched
    - message: 판단 근거
    """
    policy_codes = _normalize_codes(policy_region_code)

    if _is_national_policy(policy_codes, policy_text):
        return "matched", f"지역 조건 충족: 전국 대상 {item_type_label}"

    if not user_region_code:
        return "missing", "사용자 지역 정보가 없어 지역 조건 확인 필요"

    if not policy_codes:
        return "missing", f"{item_type_label} 지역 조건이 구조화되어 있지 않아 확인 필요"

    if user_region_code in policy_codes:
        return "matched", f"지역 조건 충족: 사용자 지역 코드 {user_region_code}가 {item_type_label} 대상 지역에 포함됨"

    # 시도 단위 코드 11000, 26000 등과 시군구 코드 매칭
    if len(user_region_code) == 5 and user_region_code.endswith("000"):
        sido_prefix = user_region_code[:2]
        if any(code.startswith(sido_prefix) for code in policy_codes):
            return "matched", f"지역 조건 충족: 사용자 지역 {user_region_code}와 같은 시도 권역의 {item_type_label}"

    # 사용자가 구 단위고 정책이 시도 권역 코드 목록인 경우
    if len(user_region_code) == 5:
        user_prefix = user_region_code[:2]
        if any(code.endswith("000") and code.startswith(user_prefix) for code in policy_codes):
            return "matched", f"지역 조건 충족: 사용자 지역 {user_region_code}가 {item_type_label} 시도 권역에 포함됨"

    return "unmatched", f"지역 조건 불충족 가능성: 사용자 지역 코드 {user_region_code}가 {item_type_label} 대상 지역에 포함되지 않음"


def _match_age(
    user_age: Any,
    age_min: Any,
    age_max: Any,
    item_type_label: str = "정책",
) -> tuple[str, str]:
    """
    반환:
    - status: matched | missing | unmatched
    - message: 판단 근거
    """
    age = _safe_int(user_age, default=-1)
    min_age = _safe_int(age_min, default=-1)
    max_age = _safe_int(age_max, default=-1)

    if age == -1:
        return "missing", "사용자 나이 정보가 없어 연령 조건 확인 필요"

    if min_age == -1 or max_age == -1:
        return "missing", f"{item_type_label} 연령 조건이 구조화되어 있지 않아 확인 필요"

    if min_age <= age <= max_age:
        return "matched", f"연령 조건 충족: {age}세는 지원 대상 {min_age}~{max_age}세에 포함됨"

    return "unmatched", f"연령 조건 불충족: {age}세는 지원 대상 {min_age}~{max_age}세에 포함되지 않음"


def _extract_income_condition_from_text(text: str) -> Optional[str]:
    """
    정책 text에서 소득 조건이 언급되는지 간단히 탐지한다.
    정확한 판정은 하지 않고 확인 필요 항목으로만 사용한다.
    """
    patterns = [
        r"중위소득\s*\d+%",
        r"소득\s*[\w\s가-힣]*\d+%",
        r"월\s*소득",
        r"연\s*소득",
        r"건강보험료",
        r"기준중위소득",
        r"소득요건",
        r"소득\s*조건",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)

    return None


def _match_income(
    user_conditions: dict[str, Any],
    policy_text: str,
    item_type_label: str = "정책",
) -> tuple[str, str]:
    """
    소득은 명확히 계산하지 않는다.
    - 사용자 소득 정보와 정책 기준을 구조화하지 않은 상태에서는 추가 확인 필요로 둔다.
    """
    user_income = _safe_str(user_conditions.get("income"))
    policy_income_hint = _extract_income_condition_from_text(policy_text)

    if policy_income_hint and not user_income:
        return "missing", f"소득 조건 확인 필요: {item_type_label}에 '{policy_income_hint}' 관련 조건이 있음"

    if policy_income_hint and user_income:
        return "missing", f"소득 조건 확인 필요: 사용자 소득 정보와 {item_type_label} 소득 기준을 원문에서 대조해야 함"

    return "matched", f"소득 조건: 검색된 {item_type_label} chunk에서 명확한 소득 제한을 확인하지 못함"


def _check_employment_status(
    user_conditions: dict[str, Any],
    policy_text: str,
    item_type_label: str = "정책",
) -> tuple[str, str]:
    user_status = _safe_str(user_conditions.get("employment_status"))

    if not user_status:
        return "missing", "사용자 고용 상태 정보가 없어 고용 조건 확인 필요"

    status_keywords = {
        "취업준비생": ["취업준비", "구직", "미취업", "취준"],
        "재직자": ["재직", "근로자", "직장인"],
        "창업자": ["창업", "사업자"],
        "프리랜서": ["프리랜서"],
    }

    keywords = status_keywords.get(user_status, [user_status])

    if any(keyword in policy_text for keyword in keywords):
        return "matched", f"고용 상태 조건 충족 가능성: {item_type_label} 본문에 '{user_status}' 관련 표현이 있음"

    # 정책 본문에 고용 조건이 없으면 불합격 처리하지 않는다.
    return "missing", f"고용 상태 조건 확인 필요: {item_type_label} 본문에서 '{user_status}' 조건을 명확히 확인하지 못함"


def _has_application_period(text: str) -> bool:
    return any(keyword in text for keyword in ["application_period", "신청기간", "신청 기간", "접수기간", "모집기간"])


def _has_required_documents(text: str) -> bool:
    return any(keyword in text for keyword in ["required_documents", "제출서류", "제출 서류", "구비서류"])


def _build_policy_view(policy: dict[str, Any]) -> dict[str, Any]:
    """
    retrieve_policies() 반환값이 들어와도, 직접 만든 policy dict가 들어와도 처리 가능하게 표준화한다.
    """
    metadata = policy.get("metadata") or {}

    item_id = (
        policy.get("item_id")
        or metadata.get("item_id")
        or policy.get("policy_id")
        or metadata.get("policy_id")
        or ""
    )

    title = (
        policy.get("title")
        or metadata.get("title")
        or policy.get("policy_name")
        or metadata.get("policy_name")
        or ""
    )

    source_category = (
        policy.get("source_category")
        or metadata.get("source_category")
        or ""
    )

    return {
        "policy_id": item_id,
        "policy_name": title,
        "item_id": item_id,
        "title": title,
        "source_category": source_category,
        "domain": policy.get("domain") or metadata.get("domain") or "",
        "text": policy.get("text") or "",
        "age_min": policy.get("age_min", metadata.get("age_min", -1)),
        "age_max": policy.get("age_max", metadata.get("age_max", -1)),
        "region_code": policy.get("region_code", metadata.get("region_code", "")),
        "source_url": policy.get("source_url", metadata.get("source_url", "")),
        "application_url": policy.get("application_url", metadata.get("application_url", "")),
        "info_score": policy.get("info_score", metadata.get("info_score", 0)),
        "needs_detail_check": policy.get("needs_detail_check", metadata.get("needs_detail_check", True)),
        "deadline_status": policy.get("deadline_status", metadata.get("deadline_status", "")),
        "application_end_date": policy.get("application_end_date", metadata.get("application_end_date", "")),
        "is_expired": policy.get("is_expired", metadata.get("is_expired", False)),
    }

def _get_item_type_label(source_category: str) -> str:
    if source_category == "training":
        return "교육훈련 과정"

    if source_category == "startup_notice":
        return "창업지원 공고"

    if source_category == "policy":
        return "정책"

    return "지원 정보"

def check_policy_eligibility(
    user_conditions: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """
    사용자 조건과 단일 정책을 비교하여 신청 가능성 등급을 산정한다.
    """
    policy_view = _build_policy_view(policy)
    
    item_type_label = _get_item_type_label(
        _safe_str(policy_view.get("source_category"))
    )

    policy_id = _safe_str(policy_view.get("policy_id"))
    policy_name = _safe_str(policy_view.get("policy_name"))
    policy_text = _safe_str(policy_view.get("text"))

    matched_conditions: list[str] = []
    missing_conditions: list[str] = []
    cautions: list[str] = []
    blockers: list[str] = []

    # 1. 연령 조건
    age_status, age_message = _match_age(
        user_age=user_conditions.get("age"),
        age_min=policy_view.get("age_min"),
        age_max=policy_view.get("age_max"),
        item_type_label=item_type_label,
    )

    if age_status == "matched":
        matched_conditions.append(age_message)
    elif age_status == "missing":
        missing_conditions.append(age_message)
    else:
        blockers.append(age_message)

    # 2. 지역 조건
    user_region_code = _infer_user_region_code(user_conditions)

    region_status, region_message = _match_region_by_code(
        user_region_code=user_region_code,
        policy_region_code=policy_view.get("region_code"),
        policy_text=policy_text,
        item_type_label=item_type_label,
    )

    if region_status == "matched":
        matched_conditions.append(region_message)
    elif region_status == "missing":
        missing_conditions.append(region_message)
    else:
        blockers.append(region_message)

    # 3. 소득 조건
    income_status, income_message = _match_income(
        user_conditions=user_conditions,
        policy_text=policy_text,
        item_type_label=item_type_label,
    )

    if income_status == "matched":
        matched_conditions.append(income_message)
    elif income_status == "missing":
        missing_conditions.append(income_message)
    else:
        blockers.append(income_message)

    # 4. 고용 상태 조건
    employment_status, employment_message = _check_employment_status(
        user_conditions=user_conditions,
        policy_text=policy_text,
        item_type_label=item_type_label,
    )

    if employment_status == "matched":
        matched_conditions.append(employment_message)
    elif employment_status == "missing":
        missing_conditions.append(employment_message)
    else:
        blockers.append(employment_message)

    # 5. 데이터 품질 / 원문 확인 주의사항
    needs_detail_check = _safe_bool(policy_view.get("needs_detail_check"), default=True)
    info_score = _safe_int(policy_view.get("info_score"), default=0)

    if needs_detail_check:
        cautions.append(f"{item_type_label} 데이터에 상세 확인 필요 플래그가 있어 원문 확인 필요")
    
    if info_score and info_score < 80:
        cautions.append(f"{item_type_label} 정보 완성도 점수(info_score={info_score})가 낮아 세부 조건 확인 필요")

    if not policy_view.get("source_url"):
        cautions.append(f"출처 URL이 없어 참여 또는 신청 전 원문/담당 기관 확인 필요")

    if not _has_application_period(policy_text):
        cautions.append(f"{item_type_label}의 신청기간 또는 모집기간 정보가 검색된 chunk에 명확히 포함되어 있지 않음")

    if not _has_required_documents(policy_text):
        cautions.append(f"{item_type_label}의 제출서류 정보가 검색된 chunk에 명확히 포함되어 있지 않음")

    # 6. 마감/최신성 조건
    deadline_status = _safe_str(policy_view.get("deadline_status"))
    application_end_date = _safe_str(policy_view.get("application_end_date"))
    is_expired = _safe_bool(policy_view.get("is_expired"), default=False)

    if is_expired or deadline_status == "expired":
        if application_end_date:
            blockers.append(f"마감된 {item_type_label}: 신청/접수 종료일이 {application_end_date}로 확인됨")
        else:
            blockers.append(f"마감된 {item_type_label}으로 표시되어 현재 신청 가능 여부가 낮음")
    elif deadline_status == "open":
        if application_end_date:
            matched_conditions.append(f"신청/접수 기간 조건: {application_end_date}까지 신청 가능성이 있음")
        else:
            matched_conditions.append(f"신청/접수 기간 조건: 상시/수시 등 현재 신청 가능성이 있는 표현이 확인됨")
    elif deadline_status == "unknown":
        cautions.append(f"{item_type_label}의 마감일을 구조화 데이터에서 명확히 확인하지 못해 원문 확인 필요")

    # 6. 최종 등급 산정
    if blockers:
        eligibility = ELIGIBILITY_LOW
    elif missing_conditions or cautions:
        eligibility = ELIGIBILITY_NEED_CHECK
    else:
        eligibility = ELIGIBILITY_HIGH

    # 단, 연령/지역이 모두 명확히 충족되고, missing이 고용/소득 정도만 있으면 가능성 높음으로 볼 수도 있음
    # 하지만 안전 원칙상 missing이 있으면 추가 확인 필요를 유지한다.

    return {
        "policy_id": policy_id,
        "policy_name": policy_name,
        "item_id": policy_view.get("item_id", policy_id),
        "title": policy_view.get("title", policy_name),
        "source_category": policy_view.get("source_category", ""),
        "eligibility": eligibility,
        "matched_conditions": matched_conditions,
        "missing_conditions": missing_conditions,
        "cautions": cautions,
        "blockers": blockers,
        "deadline_status": policy_view.get("deadline_status", ""),
        "application_end_date": policy_view.get("application_end_date", ""),
        "is_expired": policy_view.get("is_expired", False),
    }


def check_policies_eligibility(
    user_conditions: dict[str, Any],
    policies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    여러 정책에 대해 Eligibility Checker를 적용한다.
    """
    return [
        check_policy_eligibility(
            user_conditions=user_conditions,
            policy=policy,
        )
        for policy in policies
    ]


def attach_eligibility_to_policies(
    user_conditions: dict[str, Any],
    policies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    retrieve_policies() 결과에 eligibility 판단 결과를 합쳐서 반환한다.
    """
    enriched = []

    for policy in policies:
        eligibility_result = check_policy_eligibility(
            user_conditions=user_conditions,
            policy=policy,
        )

        enriched.append(
            {
                **policy,
                "eligibility": eligibility_result["eligibility"],
                "matched_conditions": eligibility_result["matched_conditions"],
                "missing_conditions": eligibility_result["missing_conditions"],
                "cautions": eligibility_result["cautions"],
                "blockers": eligibility_result["blockers"],
                "deadline_status": policy.get("deadline_status") or eligibility_result.get("deadline_status", ""),
                "application_end_date": policy.get("application_end_date") or eligibility_result.get("application_end_date", ""),
                "is_expired": policy.get("is_expired", eligibility_result.get("is_expired", False)),
            }
        )

    return enriched