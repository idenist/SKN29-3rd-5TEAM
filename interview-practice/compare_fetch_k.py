"""
compare_fetch_k.py — 검색 후보 수에 따른 결과 비교

[관련 포트폴리오] p.10

동일한 질문과 필터링 조건에서 FETCH_K만 변경하여
최종 추천 정책이 어떻게 달라지는지 확인한다.
"""

import chromadb
from datetime import date

from config import DB_PATH
from retriever import search_chunks, deduplicate_results

QUERY = "서울에 사는 28세 청년인데 월세 지원 정책 알려줘"

USER_AGE = 28
REGION_PREFIX = "11"  # 이번 실험은 서울로 한정
USER_DOMAIN = "주거"

AS_OF = date(2026, 11, 27)
TOP_K = 5


def matches_conditions(result):
    """연령과 지역 조건을 검사한다."""

    m = result["metadata"]

    # 연령 미확인 정책은 검색 후보에서 제외하지 않는다.
    age_match = (
        m["age_status"] == "unknown"
        or m["age_min"] <= USER_AGE <= m["age_max"]
    )

    # 복수 지역 코드 중 서울에 해당하는 코드가 있는지 확인
    region_codes = m["region_codes"].split(",")

    region_match = any(
        code.startswith(REGION_PREFIX)
        for code in region_codes
    )

    return age_match and region_match


def matches_domain(result):
    """복수 분야 중 사용자 관심 분야가 있는지 확인한다."""

    return USER_DOMAIN in result["metadata"]["domain"].split(",")


def is_available(result):
    """명시적으로 마감되었거나 모집 기간 밖인 후보를 제외한다."""

    m = result["metadata"]

    if m["application_period_type"] == "closed":
        return False

    start = m["application_start_date"]
    end = m["application_end_date"]

    if start and AS_OF < date.fromisoformat(start):
        return False

    if end and AS_OF > date.fromisoformat(end):
        return False

    return True


def main():
    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_collection("youth_policy_extended")

    print("전체 청크 수:", collection.count())

    # 동일한 검색 순위를 기준으로 후보 수만 비교하기 위해
    # 80개를 한 번 검색하고 각각 필요한 개수만 사용한다.
    retrieved = search_chunks(collection, QUERY, fetch_k=80)

    for fetch_k in [5, 20, 80]:

        candidates = retrieved[:fetch_k]

        filtered = [
            r for r in candidates
            if matches_conditions(r)
        ]

        unique = deduplicate_results(filtered)

        ranked = sorted(
            unique,
            key=lambda r: (
                matches_domain(r),
                r["score"]
            ),
            reverse=True
        )

        available = [
            r for r in ranked
            if is_available(r)
        ]

        final = available[:TOP_K]

        print(f"\n[FETCH_K = {fetch_k}]")
        print("의미 검색:", len(candidates))
        print("조건 필터링:", len(filtered))
        print("중복 제거:", len(unique))
        print("마감 필터링:", len(available))

        print("[최종 추천]")

        for r in final:
            print(
                r["metadata"]["title"],
                r["metadata"]["domain"],
                round(r["score"], 4)
            )


if __name__ == "__main__":
    main()