"""같은 검색 순위에서 FETCH_K 변화의 영향을 관찰한다 (p.10, 12).

기존 확장 컬렉션과 질문 벡터 하나로 검색하고 experiments.common을 통해 단계별 후보와 정책을 출력한다.
기간과 사용자 조건은 고정하며 속도나 전체 질문의 정확도는 측정하지 않는다.
"""

from experiments.common import CONDITIONS, QUERY, report
from indexing import embed_texts, get_collection
from retriever import search_by_vector


def run(collection, embedding):
    """준비된 벡터를 모든 비교군에서 재사용한다. 비교군 간에는 지정한 검색 조건만 바꾼다."""
    sizes = (5, 20, 80)
    hits = search_by_vector(collection, embedding, max(sizes), CONDITIONS, "post")
    for size in sizes:
        report(f"FETCH_K = {size}", hits[:size])


def main():
    """기존 확장 컬렉션을 열고 질문 한 건만 임베딩해 비교를 실행한다."""
    collection = get_collection("extended")
    run(collection, embed_texts([QUERY])[0])


if __name__ == "__main__":
    main()
