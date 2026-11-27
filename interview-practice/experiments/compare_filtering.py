"""같은 FETCH_K에서 조건 적용 시점에 따른 후보 차이를 관찰한다 (p.10, 12).

기존 확장 컬렉션과 질문 벡터 하나로 검색하고 experiments.common을 통해 단계별 후보와 정책을 출력한다.
기간과 사용자 조건은 고정하며 속도나 전체 질문의 정확도는 측정하지 않는다.
"""

from experiments.common import CONDITIONS, QUERY, report
from indexing import embed_texts, get_collection
from retriever import search_by_vector


def run(collection, embedding):
    """준비된 벡터를 모든 비교군에서 재사용한다. 비교군 간에는 지정한 검색 조건만 바꾼다."""
    for mode in ("post", "pre"):
        hits = search_by_vector(collection, embedding, 5, CONDITIONS, mode)
        report(f"{mode} / FETCH_K = 5", hits)


def main():
    """기존 확장 컬렉션을 열고 질문 한 건만 임베딩해 비교를 실행한다."""
    collection = get_collection("extended")
    run(collection, embed_texts([QUERY])[0])


if __name__ == "__main__":
    main()
