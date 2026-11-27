"""
compare_filtering.py — 검색 전·후 필터링 비교

[관련 포트폴리오] p.10
동일한 임베딩과 사용자 조건에서
필터링 순서에 따른 검색 결과 차이를 확인한다.
"""

import chromadb

from config import DB_PATH
from indexing import embed_texts
from retriever import deduplicate_results

from compare_fetch_k import (
    QUERY,
    USER_AGE,
    REGION_PREFIX,
    TOP_K,
    matches_conditions,
    matches_domain,
    is_available
)

FETCH_K = 5


def build_where(collection):
    """기존 Python 필터와 동일한 Chroma 검색 조건을 구성한다."""

    # 현재 지역 코드는 쉼표로 연결된 문자열이므로
    # 서울을 포함하는 지역 코드 문자열들을 먼저 확보한다.
    data = collection.get(include=["metadatas"])

    regions = sorted({
        m["region_codes"]
        for m in data["metadatas"]
        if any(
            code.startswith(REGION_PREFIX)
            for code in m["region_codes"].split(",")
        )
    })

    return {
        "$and": [
            {"region_codes": {"$in": regions}},
            {
                "$or": [
                    {"age_status": "unknown"},
                    {
                        "$and": [
                            {"age_min": {"$lte": USER_AGE}},
                            {"age_max": {"$gte": USER_AGE}}
                        ]
                    }
                ]
            }
        ]
    }


def search(collection, embedding, where=None):
    """where 조건의 유무에 따라 검색 범위를 결정한다."""

    raw = collection.query(
        query_embeddings=[embedding],
        n_results=FETCH_K,
        where=where,
        include=["documents", "metadatas", "distances"]
    )

    return [
        {
            "chunk_id": chunk_id,
            "document": document,
            "metadata": metadata,
            "score": 1 - distance
        }
        for chunk_id, document, metadata, distance in zip(
            raw["ids"][0],
            raw["documents"][0],
            raw["metadatas"][0],
            raw["distances"][0]
        )
    ]


def print_results(label, results):
    """두 방식에 동일한 후속 처리 규칙을 적용한다."""

    filtered = [
        r for r in results if matches_conditions(r)
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

    final = [
        r for r in ranked if is_available(r)
    ][:TOP_K]

    print(f"\n[{label}]")
    print("의미 검색:", len(results))
    print("조건 충족:", len(filtered))
    print("최종 정책 수:", len(final))

    for r in final:
        print(
            r["metadata"]["title"],
            r["metadata"]["domain"],
            round(r["score"], 4)
        )


def main():
    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_collection("youth_policy_extended")

    # 두 방식에 동일한 질문 벡터 사용
    embedding = embed_texts([QUERY])[0]

    # 검색 후 필터링
    post = search(collection, embedding)

    # 검색 전 필터링
    where = build_where(collection)
    pre = search(collection, embedding, where=where)

    print_results("Post-filtering", post)
    print_results("Pre-filtering", pre)


if __name__ == "__main__":
    main()