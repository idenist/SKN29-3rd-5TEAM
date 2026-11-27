"""두 검색 비교에서 고정할 입력과 결과 표시 방법 (p.10, 12).

두 비교 모듈에서 같은 질문·기준일·조건을 사용하고 retriever가 남긴 단계별 수와 정책을 출력한다.
조건 추출의 변동을 없애려고 사용자 조건을 고정했다. 한 질문의 관찰만으로 일반화할 수 없다.
"""

from datetime import date

from retriever import refine_candidates


QUERY = "서울에 사는 28세 청년인데 월세 지원 정책 알려줘"
CONDITIONS = {"age": 28, "region": "서울", "interest_domain": "주거"}
AS_OF = date(2026, 11, 27)
TOP_K = 5


def report(label, hits):
    """같은 후처리를 적용해 단계별 잔여 수와 최종 정책명·분야·유사도를 출력한다."""
    final, counts = refine_candidates(hits, CONDITIONS, AS_OF, TOP_K)
    print(f"\n[{label}] 의미 검색 {len(hits)}개 청크")
    for stage, count in counts.items():
        print(stage, count)
    for hit in final:
        meta = hit["metadata"]
        print(meta["title"], meta["domain"], round(hit["score"], 4))
    return final, counts
