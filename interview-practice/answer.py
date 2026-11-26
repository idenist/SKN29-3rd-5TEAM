"""선택된 근거로 사용자에게 보여줄 답변을 만든다 (p.10~11).

workflow의 내부 경로는 후보별 판정과 본문을 묶어 LLM에 주고, 외부 경로는 Tavily 결과로
고정 양식을 채운다. 두 함수 모두 문자열을 반환한다. 평가에는 이 답변과 실제 경로의 근거가 쓰인다."""

import json

from conditions import check_eligibility
from config import CHAT_MODEL, get_openai_client


def build_internal_context(results, user_age, user_region):
    """
    내부 검색 후보마다 자격을 한 번씩 판정하고 답변용 근거를 구성한다.

    반환하는 각 딕셔너리에는 정책명, 본문, 메타데이터와 판정 결과가 들어 있다.
    출력 함수와 답변 생성 함수가 동일한 판정 데이터를 재사용하므로
    자격 판정을 중복 실행하지 않는다.
    """

    context = []

    for result in results:
        judgment = check_eligibility(result, user_age, user_region)

        # 검색 결과와 규칙 기반 판정 결과를 하나로 묶는다.
        context.append({
            "title": result["metadata"]["title"],
            "document": result["document"],
            "metadata": result["metadata"],
            "judgment": judgment
        })

    return context


def generate_internal_answer(query, context, as_of):
    """
    검색 근거와 이미 계산한 자격 판정을 LLM에 전달한다.

    자격 판정은 Python 코드에서 수행하며, LLM은 판정 근거를 바탕으로
    자연어 답변을 생성한다. 프롬프트만으로 사실 오류를 완전히 방지할 수는 없다.
    """

    system_prompt = """
    당신은 청년정책 안내 서비스입니다.

    제공된 검색 결과와 자격 판정 근거만 사용하여
    사용자의 질문에 답변하세요.

    다음 규칙을 준수하세요.

    1. 제공되지 않은 정보를 만들어내지 마세요.
    2. 자격 판정 결과를 임의로 변경하지 마세요.
    3. 확인이 필요한 조건은 명시하세요.
    4. 질문과 관련 없는 정책은 추천하지 마세요.
    5. 마감 판단 기준일과 실제 현재 날짜를 혼동하지 마세요.
    """

    user_prompt = f"""
    사용자 질문: {query}
    마감 판단 기준일: {as_of}

    검색 결과 및 자격 판정 근거:
    {json.dumps(context, ensure_ascii=False, indent=2)}
    """

    response = get_openai_client().chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0
    )

    return response.choices[0].message.content


def generate_external_answer(results):
    """정제한 웹 결과를 제목, 본문 첫 300자, URL로 조립해 답변 문자열을 반환한다.

    결과가 없으면 근거 없음으로 안내한다. 검증된 자격 필드가 없으므로 신청 가능성은
    추가 확인으로 남긴다. 본문 미리보기만으로 공고의 마감·세부 요건을 판단하지 않는다.
    """

    if not results:
        return "관련 근거를 찾지 못했습니다."

    answer = [
        "내부 데이터에서 답변에 충분한 근거를 확보하지 못했습니다.",
        "공식 사이트에서 다음 확인 후보를 찾았습니다."
    ]

    for i, result in enumerate(results, start=1):

        # 검색된 본문의 일부를 발췌한다.
        preview = result["content"][:300]

        answer.append(
            f"\n{i}. {result['title']}"
        )
        answer.append(f"본문 일부: {preview}...")
        answer.append(f"출처: {result['url']}")
        answer.append("신청 가능 여부: 추가 확인 필요")

    answer.append(
        "\n정확한 신청 기간과 자격 조건은 "
        "공식 원문에서 확인해야 합니다."
    )

    return "\n".join(answer)
