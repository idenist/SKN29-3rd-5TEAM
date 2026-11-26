"""내부 후보가 부족할 때 공식 사이트를 보강 검색한다 (p.11).

workflow가 질문을 넘기면 Tavily 결과 목록을 받아 정제한다. answer는 남은 제목·본문 일부·URL을
사용해 원문 확인용 답변을 작성한다. 웹 검색은 항상 실행 시점의 자료를 대상으로 한다."""

import os
from urllib.parse import urlparse

from tavily import TavilyClient


def search_external(query):
    """질문을 기존 공식 도메인에 한정해 basic 검색하고 최대 세 개의 결과 딕셔너리를 받는다.

    TAVILY_API_KEY가 없으면 빈 목록을 반환한다. 공식 출처여도 접수 여부나 개인의 자격은 미확인이다.
    """

    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        print("Tavily API 키가 설정되지 않았습니다.")
        return []

    tavily_client = TavilyClient(api_key=api_key)

    # 검색 범위를 공식 사이트 도메인으로 제한한다.
    # 공식 도메인이라도 공고 마감 여부나 실제 신청 자격을 보장하지 않는다.
    response = tavily_client.search(
        query=query,
        search_depth="basic",
        max_results=3,
        include_domains=[
            "youthcenter.go.kr",
            "youth.seoul.go.kr",
            "housing.seoul.go.kr",
            "daejeon.go.kr",
            "bokjiro.go.kr",
            "work24.go.kr",
            "hrd.go.kr",
            "k-startup.go.kr"
        ]
    )

    return response["results"]


def refine_external_results(results):
    """Tavily 결과 목록에서 메인 페이지와 정규화한 중복 URL을 제외해 새 목록을 만든다.

    같은 URL이면 먼저 받은 결과를 유지한다. 제목에 ‘개요’가 있는 자료를 뒤로 두고
    각 그룹은 Tavily 점수 내림차순으로 정렬한다. URL 쿼리나 본문 내용의 중복까지 비교하지 않는다.
    """

    refined = []
    seen_urls = set()

    for result in results:
        url = result["url"]
        title = result["title"]

        # URL을 구성 요소별로 분리한다.
        parsed = urlparse(url)

        # 1. 사이트 메인 페이지 제외
        if parsed.path in ("", "/") and not parsed.query:
            continue

        # 2. 동일한 URL 중복 제거
        normalized_url = parsed._replace(
            path=parsed.path.rstrip("/"),
            fragment=""
        ).geturl()

        if normalized_url in seen_urls:
            continue

        seen_urls.add(normalized_url)

        # 3. 일반 안내 페이지인지 판단
        is_general_page = "개요" in title

        refined.append({
            **result,
            "is_general_page": is_general_page
        })

    # 1순위: 일반 안내 페이지가 아닌 결과
    # 2순위: Tavily 검색 점수가 높은 결과
    ranked = sorted(
        refined,
        key=lambda result: (
            not result["is_general_page"],
            result["score"]
        ),
        reverse=True
    )

    return ranked
