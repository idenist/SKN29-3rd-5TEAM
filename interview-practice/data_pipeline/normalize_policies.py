"""
normalize_policies.py — 온통청년 원본 데이터 정규화

[관련 포트폴리오] p.10, p.12

원본 정책 JSON을 읽어 검색용 본문(documents)과
필터링용 메타데이터(metadata)로 분리한다.

기관 필드와 결측 표현을 통일해야 숫자·날짜를 비교할 수 있다. 본문은 의미 검색에, 메타데이터는 조건 비교에 사용한다.
indexing.build_chunks가 이 결과를 받는다. 연령 플래그와 신청 기간 코드의 해석은 잠정적이다.
"""

import json
import re
from pathlib import Path
from datetime import datetime
from collections import Counter

BASE_DIR = Path(__file__).resolve().parents[1]

RAW_PATH = BASE_DIR / "data/youth_policies_raw.json"
OUTPUT_PATH = BASE_DIR / "data/youth_policies_normalized.json"


def clean(value):
    """None과 불필요한 앞뒤 공백을 제거한다."""
    return "" if value is None else str(value).strip()


def normalize_domain(value):
    """복합 분야를 기존 RAG의 분야 체계로 통일한다."""

    mapping = {
        "일자리": ["일자리"],
        "주거": ["주거"],
        "교육": ["교육"],
        "교육･직업훈련": ["교육"],
        "금융･복지･문화": ["금융", "복지문화"],
        "금융": ["금융"],
        "창업": ["창업"],
        "복지문화": ["복지문화"],
        "참여･기반": ["참여권리"],
        "참여권리": ["참여권리"]
    }

    domains = []

    for part in clean(value).split(","):
        for domain in mapping.get(part.strip(), []):

            # 동일 분야가 중복 저장되지 않도록 한다.
            if domain not in domains:
                domains.append(domain)

    return ",".join(domains) or "미분류"


def normalize_age(policy):
    """잠정적인 연령 범위를 반환한다.

    Y/N의 정확한 의미가 확인되지 않았으므로
    N이면서 유효한 범위인 경우에만 필터링에 활용한다.
    나머지는 미확인(-1)으로 처리한다.
    """

    flag = clean(policy.get("sprtTrgtAgeLmtYn"))

    try:
        age_min = int(clean(policy.get("sprtTrgtMinAge")))
        age_max = int(clean(policy.get("sprtTrgtMaxAge")))
    except ValueError:
        return -1, -1, "unknown"

    if flag == "N" and 0 < age_min <= age_max:
        return age_min, age_max, "inferred_range"

    return -1, -1, "unknown"


def normalize_period(policy):
    """신청 기간의 유형과 시작일, 마감일을 반환한다."""

    mapping = {
        "0057001": "fixed",
        "0057002": "always",
        "0057003": "closed"
    }

    period_type = mapping.get(
        clean(policy.get("aplyPrdSeCd")),
        "unknown"
    )

    raw_date = clean(policy.get("aplyYmd"))

    # 특정 기간일 때만 날짜를 추출한다.
    if period_type == "fixed":
        match = re.fullmatch(
            r"(\d{8})\s*[~～]\s*(\d{8})",
            raw_date
        )

        if match:
            try:
                start = datetime.strptime(
                    match.group(1), "%Y%m%d"
                ).date()

                end = datetime.strptime(
                    match.group(2), "%Y%m%d"
                ).date()

                if start <= end:
                    return (
                        period_type,
                        start.isoformat(),
                        end.isoformat()
                    )

            except ValueError:
                pass

    # 상시 모집, 마감, 날짜 해석 실패 등의 경우
    return period_type, "", ""


def build_document(title, fields):
    """빈 필드는 제외하고 정책명을 포함한 본문을 구성한다."""

    lines = [
        f"{label}: {clean(value)}"
        for label, value in fields
        if clean(value)
    ]

    if not lines:
        return ""

    return "\n".join([
        f"정책명: {title}",
        *lines
    ])


def normalize_policy(policy):
    """원본 정책 한 건을 공통 정책 레코드로 변환한다."""

    item_id = clean(policy.get("plcyNo"))
    title = clean(policy.get("plcyNm"))

    if not item_id or not title:
        return None

    age_min, age_max, age_status = normalize_age(policy)

    period_type, start_date, end_date = normalize_period(
        policy
    )

    domain = normalize_domain(policy.get("lclsfNm"))

    # 복수 지역을 쉼표로 구분한 문자열로 보존한다.
    region_codes = ",".join(dict.fromkeys(
        code.strip()
        for code in clean(policy.get("zipCd")).split(",")
        if code.strip()
    ))

    # 1. 의미 검색에 사용할 본문 구성
    documents = {
        "summary": build_document(title, [
            ("정책 설명", policy.get("plcyExplnCn")),
            ("지원 내용", policy.get("plcySprtCn")),
            ("정책 키워드", policy.get("plcyKywdNm"))
        ]),

        "eligibility": build_document(title, [
            ("연령 조건(잠정)", (
                f"{age_min}~{age_max}세"
                if age_status == "inferred_range"
                else "추가 확인 필요"
            )),
            ("추가 자격 조건", policy.get("addAplyQlfcCndCn")),
            ("참여 제한 대상", policy.get("ptcpPrpTrgtCn")),
            ("소득 조건", policy.get("earnEtcCn"))
        ]),

        "application": build_document(title, [
            ("신청 기간", policy.get("aplyYmd")),
            ("신청 방법", policy.get("plcyAplyMthdCn")),
            ("심사 방법", policy.get("srngMthdCn")),
            ("제출 서류", policy.get("sbmsnDcmntCn"))
        ])
    }

    # 본문이 비어 있는 청크는 생성하지 않는다.
    documents = {
        key: value
        for key, value in documents.items()
        if value
    }

    # 2. 검색 필터링 및 자격 판단에 사용할 메타데이터
    metadata = {
        "domain": domain,
        "domain_raw": clean(policy.get("lclsfNm")),

        "age_min": age_min,
        "age_max": age_max,
        "age_status": age_status,
        "age_limit_raw": clean(policy.get("sprtTrgtAgeLmtYn")),
        "age_min_raw": clean(policy.get("sprtTrgtMinAge")),
        "age_max_raw": clean(policy.get("sprtTrgtMaxAge")),

        "region_codes": region_codes,

        "application_period_type": period_type,
        "application_start_date": start_date,
        "application_end_date": end_date,
        "application_period_code": clean(policy.get("aplyPrdSeCd")),
        "application_period_raw": clean(policy.get("aplyYmd")),

        "source_name": "온통청년",
        "source_url": (
            clean(policy.get("refUrlAddr1"))
            or clean(policy.get("refUrlAddr2"))
            or clean(policy.get("aplyUrlAddr"))
        ),
        "application_url": clean(policy.get("aplyUrlAddr")),

        "needs_detail_check": True
    }

    return {
        "item_id": item_id,
        "title": title,
        "documents": documents,
        "metadata": metadata
    }


def main():
    """원본 JSON의 정책 ID를 확인하고 정규화한 목록과 필드 분포를 기록한다."""
    with RAW_PATH.open(encoding="utf-8") as f:
        raw = json.load(f)["policies"]

    normalized = []
    seen_ids = set()

    for policy in raw:
        result = normalize_policy(policy)

        # 정책 ID가 없거나 중복된 레코드는 제외한다.
        if result is None:
            continue

        if result["item_id"] in seen_ids:
            continue

        seen_ids.add(result["item_id"])
        normalized.append(result)

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)

    print("원본 정책 수:", len(raw))
    print("정규화 정책 수:", len(normalized))
    print("제외된 정책 수:", len(raw) - len(normalized))

    print("예상 청크 수:", sum(
        len(p["documents"]) for p in normalized
    ))

    print("연령 상태:", Counter(
        p["metadata"]["age_status"] for p in normalized
    ))

    print("신청 기간 유형:", Counter(
        p["metadata"]["application_period_type"]
        for p in normalized
    ))

    print("저장 위치:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
