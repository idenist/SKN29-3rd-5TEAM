import re


# Streamlit 필터 UI에서 지원하는 지역 값에 맞춘 정규화 맵입니다.
# UI에 없는 시도는 "기타"로 묶어 selectbox 값 오류를 방지합니다.
_REGION_ALIASES = {
    "서울특별시": "서울",
    "서울시": "서울",
    "서울": "서울",
    "부산광역시": "부산",
    "부산시": "부산",
    "부산": "부산",
    "대구광역시": "대구",
    "대구시": "대구",
    "대구": "대구",
    "인천광역시": "인천",
    "인천시": "인천",
    "인천": "인천",
    "광주광역시": "광주",
    "광주시": "광주",
    "광주": "광주",
    "대전광역시": "대전",
    "대전시": "대전",
    "대전": "대전",
    "경기도": "경기",
    "경기": "경기",
    "세종특별자치시": "기타",
    "세종시": "기타",
    "세종": "기타",
    "강원특별자치도": "기타",
    "강원도": "기타",
    "강원": "기타",
    "충청북도": "기타",
    "충북": "기타",
    "충청남도": "기타",
    "충남": "기타",
    "전북특별자치도": "기타",
    "전라북도": "기타",
    "전북": "기타",
    "전라남도": "기타",
    "전남": "기타",
    "경상북도": "기타",
    "경북": "기타",
    "경상남도": "기타",
    "경남": "기타",
    "제주특별자치도": "기타",
    "제주도": "기타",
    "제주": "기타",
}


# 사용자가 다양하게 입력할 수 있는 표현을 분야별로 묶습니다.
# 비교 시에는 _normalize_query_text()를 한 번 거치므로
# "K-디지털", "k digital", "케이디지털", "KDT" 같은 변형도 함께 잡힙니다.
_INTEREST_KEYWORDS = {
    "취업": [
        "취업", "구직", "일자리", "채용", "면접", "자소서", "자기소개서",
        "이력서", "인턴", "재직", "근로", "알바", "아르바이트", "취준",
        "취업준비", "취준생", "청년일자리", "고용", "직무", "커리어",
    ],
    "교육": [
        "교육", "훈련", "강의", "수강", "자격증", "학원", "부트캠프",
        "부트 캠프", "국비", "국비지원", "국민내일배움카드", "내일배움",
        "내일배움카드", "hrd", "직업훈련", "개발자교육", "데이터교육",
        "ai교육", "k-digital", "k digital", "k-디지털", "k디지털",
        "케이디지털", "케이 디지털", "kdt", "kdigital", "kdigitaltraining",
    ],
    "창업": [
        "창업", "예비창업", "초기창업", "사업화", "스타트업", "창업지원",
        "창업공고", "창업지원사업", "투자", "ir", "투자유치", "멘토링",
        "시제품", "사업계획서", "창업자금", "창업교육", "창업특강",
    ],
    "주거": [
        "주거", "월세", "전세", "임대", "임차", "보증금", "주택",
        "청년주택", "행복주택", "공공임대", "매입임대", "전세임대",
        "분양", "분양정보", "주택청약", "청약", "무주택", "기숙사",
        "주거비", "전월세", "임대주택", "lh", "sh", "보증금대출",
        "전세대출", "월세지원", "청년월세", "청년월세지원",
    ],
    "금융": [
        "금융", "대출", "적금", "저축", "계좌", "이자", "자산", "자산형성",
        "청년도약계좌", "희망적금", "생활비대출", "학자금대출", "신용",
        "보증", "융자", "금리", "저금리", "목돈", "재테크",
    ],
    "복지": [
        "복지", "문화", "상담", "심리", "마음건강", "건강", "교통비",
        "바우처", "지원금", "수당", "생활지원", "의료", "청년수당",
        "활동지원", "고립", "은둔", "식비", "생활비", "자립", "참여",
    ],
}


_HOUSING_STATUS_KEYWORDS = {
    "월세": ["월세", "월세방", "월세집", "전월세", "월세지원", "청년월세"],
    "전세": ["전세", "전셋집", "전세임대", "전세대출", "전세보증금"],
    "자가": ["자가", "자가주택", "내집", "내 집", "소유주택", "집 보유"],
    "무주택": ["무주택", "집없", "집 없음", "주택 없음", "주택무소유"],
    "기타": ["기숙사", "고시원", "쉐어하우스", "셰어하우스", "하숙"],
}


_JOB_STATUS_RULES = [
    ("중소기업 재직자", ["중소기업", "중기 재직", "중소 재직"]),
    ("프리랜서", ["프리랜서", "프리", "개인 프리랜서"]),
    ("예비창업자", ["예비창업", "창업 준비", "창업준비", "창업하려", "창업하고", "창업 예정"]),
    ("사업자", ["사업자", "자영업", "개인사업", "법인사업", "창업자"]),
    ("학생", ["학생", "대학생", "재학생", "휴학생", "졸업예정", "대학원생"]),
    ("재직자", ["재직", "직장인", "근로자", "회사원", "일하는 중", "근무"]),
    ("구직자", ["구직", "취준", "취업준비", "취준생", "실업", "무직", "미취업"]),
]


def _normalize_query_text(text: str) -> str:
    """검색어 비교용 정규화 문자열을 만든다."""
    normalized = str(text or "").lower()
    normalized = re.sub(r"[^가-힣a-z0-9]", "", normalized)

    replacements = {
        "케이디지털트레이닝": "kdigital",
        "케이디지털훈련": "kdigital",
        "케이디지털": "kdigital",
        "k디지털트레이닝": "kdigital",
        "k디지털훈련": "kdigital",
        "k디지털": "kdigital",
        "kdigitaltraining": "kdigital",
        "kdigital": "kdigital",
        "kdt": "kdigital",
        "국민내일배움카드": "내일배움카드",
        "내일배움": "내일배움카드",
    }

    for old, new in replacements.items():
        normalized = normalized.replace(old, new)

    return normalized


def _unique_keep_order(values):
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def extract_interests(query: str) -> list[str]:
    """자연어 검색어에서 관심 분야 체크박스 값을 추론한다."""
    normalized_query = _normalize_query_text(query)
    interests = []

    for interest, keywords in _INTEREST_KEYWORDS.items():
        for keyword in keywords:
            normalized_keyword = _normalize_query_text(keyword)
            if normalized_keyword and normalized_keyword in normalized_query:
                interests.append(interest)
                break

    return _unique_keep_order(interests)


def _extract_age(query: str):
    match = re.search(r"(?<!\d)(1[5-9]|[2-7]\d|80)\s*(?:살|세)", query)
    if match:
        return int(match.group(1))
    return None


def _extract_income(query: str):
    # 기존 UI가 income을 숫자(만원 단위)로 다루므로, 명확한 금액 표현만 추출한다.
    match = re.search(
        r"(?:연소득|소득|연봉)\s*(?:이|은|는|:)?\s*([0-9,]+)\s*(?:만원)?",
        query,
    )
    if match:
        return int(match.group(1).replace(",", ""))
    return None


def _extract_region(query: str):
    for keyword, region in sorted(_REGION_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if keyword in query:
            return region
    return None


def _extract_job_status(query: str):
    normalized_query = _normalize_query_text(query)

    for status, keywords in _JOB_STATUS_RULES:
        for keyword in keywords:
            normalized_keyword = _normalize_query_text(keyword)
            if normalized_keyword and normalized_keyword in normalized_query:
                return status

    return None


def _extract_housing_status(query: str):
    normalized_query = _normalize_query_text(query)

    for status, keywords in _HOUSING_STATUS_KEYWORDS.items():
        for keyword in keywords:
            normalized_keyword = _normalize_query_text(keyword)
            if normalized_keyword and normalized_keyword in normalized_query:
                return status

    return None


def parse_user_query(query: str):
    query = str(query or "")

    result = {
        "age": _extract_age(query),
        "region": _extract_region(query),
        "income": _extract_income(query),
        "job_status": _extract_job_status(query),
        "housing_status": _extract_housing_status(query),
        "interest": extract_interests(query),
    }

    return result
