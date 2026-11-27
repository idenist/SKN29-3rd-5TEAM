"""연령·지역·분야·신청 기간을 메타데이터로 비교한다 (p.10~11).

retriever와 conditions가 같은 규칙을 사용한다. 조건 비교는 True(충족), False(불일치),
None(미확인)을 반환한다. 이름이나 날짜로 검증할 수 없는 세부 자격은 원문 확인이 필요하다.
"""

from datetime import date

# 팀 저장소 backend/services/policy_matcher.py의 SIDO_CODE_MAP에 명시된 대응만 사용한다.
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

NATIONAL = {"전국", "전체", "ALL", "00000"}


def age_match(metadata, age):
    """사용자 나이와 저장 범위를 비교한다. 잠정 정규화에서 unknown으로 남긴 범위는 보류한다."""
    if type(age) is not int or metadata.get("age_status") == "unknown":
        return None
    low, high = metadata.get("age_min"), metadata.get("age_max")
    if not isinstance(low, int) or not isinstance(high, int) or not 0 < low <= high:
        return None
    return low <= age <= high


def parts(value):
    """Chroma에 문자열로 저장된 복수 값을 경계 단위로 나눈다. 빈 문자열은 빈 집합이다."""
    if not isinstance(value, str):
        return set()
    return {token.strip() for token in value.split(",") if token.strip()}


def region_code(value):
    """이미 주어진 5자리 코드와 기존 시도명만 해석한다. 시군구 이름의 코드는 추측하지 않는다."""
    if len(value) == 5 and value.isascii() and value.isdigit():
        return value
    return SIDO_CODE_MAP.get(value)


def region_match(metadata, region):
    """샘플의 지역명 또는 확장의 복수 코드 중 하나라도 사용자 거주지를 포괄하는지 확인한다."""
    targets = parts(metadata.get("region_codes") or metadata.get("region"))
    if targets & NATIONAL:
        return True
    if not targets or not isinstance(region, str) or not region.strip():
        return None
    region = region.strip()
    if region in targets:
        return True
    user_code = region_code(region)
    if not user_code:
        return None

    uncertain = False
    for target in targets:
        code = region_code(target)
        if code is None:
            uncertain = True
        elif code == user_code:
            return True
        elif code[:2] == user_code[:2]:
            if code.endswith("000"):
                return True  # 시도 전체 공고는 그 아래 자치구도 포함한다.
            if user_code.endswith("000"):
                uncertain = True  # '서울 거주'만으로 특정 자치구 거주를 확정할 수 없다.
    return None if uncertain else False


def candidate_matches(metadata, age, region):
    """검색에서는 명시적 불일치만 제외한다. 미확인 사유는 이후 자격 판정에서 드러낸다."""
    return age_match(metadata, age) is not False and region_match(metadata, region) is not False


def domain_matches(metadata, domain):
    """사용자 관심 분야와 정책의 분야가 하나라도 겹치면 True. 벡터 유사도는 별도로 비교한다."""
    return bool(parts(domain) & parts(metadata.get("domain")))


def period_match(metadata, as_of):
    """기준일과 양 끝 날짜를 포함해 비교한다. 정보가 한쪽뿐이면 확정할 수 있는 탈락만 판정한다."""
    kind = metadata.get("application_period_type")
    if kind == "closed":
        return False
    if kind == "always":
        return True
    try:
        start_text, end_text = metadata.get("application_start_date"), metadata.get("application_end_date")
        start = date.fromisoformat(start_text) if start_text else None
        end = date.fromisoformat(end_text) if end_text else None
    except (TypeError, ValueError):
        return None
    if start and end and start > end:
        return None
    if (start and as_of < start) or (end and as_of > end):
        return False
    if start and end:
        return True
    return None
