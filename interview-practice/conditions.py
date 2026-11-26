"""질문의 조건 추출과 정책별 자격 판정 (p.9~10).

workflow가 질문을 보내면 나이·지역·관심 분야를 추출한다. answer는 남은 후보와 사용자 조건을
check_eligibility에 전달해 판정과 그 근거를 받는다. 후보의 의미적 관련성과 지원 가능성은 별도로 판단한다."""

import json

from config import CHAT_MODEL, get_openai_client


def extract_conditions(query):
    """질문 문자열을 모델에 보내 age, region, interest_domain 딕셔너리를 반환한다.

    확인할 수 없는 사용자 정보는 null로 요청한다. JSON 모드는 필드 누락이나 자료형 오류까지
    검증하지 않으므로 외부 데이터를 확대할 때는 별도 검증이 필요하다.
    """

    # LLM이 수행할 역할과 출력 형식을 지정한다.
    system_prompt = """
    당신은 청년정책 검색을 위한 사용자 조건 추출기입니다.

    사용자 질문에서 다음 정보를 추출하세요.

    - age: 나이 (정수)
    - region: 거주 지역 (예: 서울, 대전, 경기)
    - interest_domain: 관심 분야

    관심 분야는 다음 중 하나로 분류하세요.
    일자리, 주거, 교육, 금융, 창업, 복지문화, 참여권리

    확인할 수 없는 정보는 추측하지 말고 null로 반환하세요.

    반드시 다음 형식의 JSON으로 반환하세요.

    {
        "age": null,
        "region": null,
        "interest_domain": null
    }
    """

    response = get_openai_client().chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ],
        temperature=0,
        response_format={"type": "json_object"}
    )

    # LLM이 반환한 JSON 문자열
    raw_text = response.choices[0].message.content

    # JSON 문자열을 Python 딕셔너리로 변환한다.
    # JSON Mode는 필드의 타입과 값의 정확성까지 보장하지는 않는다.
    conditions = json.loads(raw_text)

    return conditions


def check_eligibility(result, user_age, user_region):
    """대표 청크 하나와 사용자 나이·지역을 대조해 eligibility, matched, unmatched, missing을 반환한다.

    명시적 불일치가 우선이며, 미확인 조건이 남으면 추가 확인으로 판단한다. 검색 단계에서
    남았다는 사실만으로 신청을 확정할 수 없다. 소득·고용 등 세부 요건은 직접 검증하지 않는다.
    """

    metadata = result["metadata"]

    matched = []
    unmatched = []
    missing = []

    # 1. 연령 조건 판단
    if user_age is None:
        missing.append("사용자 나이 정보 없음")

    elif metadata["age_min"] <= user_age <= metadata["age_max"]:
        matched.append("연령 조건 충족")

    else:
        unmatched.append("연령 조건 불충족")

    # 2. 지역 조건 판단
    if user_region is None:
        missing.append("사용자 지역 정보 없음")

    elif metadata["region"] == user_region:
        matched.append("지역 조건 충족")

    else:
        unmatched.append("지역 조건 불충족")

    # 3. 아직 검증하지 않은 세부 자격 요건
    # 현재 실습 데이터는 소득, 고용 상태 등
    # 세부 조건이 생략되어 있으므로 기본값을 True로 둔다.
    if metadata.get("needs_detail_check", True):
        missing.append("정책별 세부 자격 요건 확인 필요")

    # 4. 최종 자격 가능성 판단
    if unmatched:
        eligibility = "가능성 낮음"

    elif missing:
        eligibility = "추가 확인 필요"

    else:
        eligibility = "가능성 높음"

    return {
        "eligibility": eligibility,
        "matched": matched,
        "unmatched": unmatched,
        "missing": missing
    }
