"""수집 후 정규화 전에 필드 분포와 결측 패턴을 살펴보는 읽기 전용 도구 (p.10, 12).

collect_youth_policies가 저장한 원본 JSON을 읽고 연령·분야·기간의 빈도와 사례를 출력한다.
이 통계만으로 코드의 공식 의미를 확정할 수 없다. normalize_policies의 잠정 규칙을 검토할 때 사용한다.
"""

import json
from collections import Counter
from pathlib import Path

import pandas as pd


def main():
    """원본 필드를 요약하고 연령 플래그와 실제 값, 기간 유형과 날짜 누락을 교차 집계한다."""
    path = Path(__file__).resolve().parents[1] / "data/youth_policies_raw.json"
    with path.open(encoding="utf-8") as source:
        raw = json.load(source)
    policies = raw["policies"] if isinstance(raw, dict) else raw
    print("전체 정책 수:", len(policies))
    if not policies:
        return

    fields = ["lclsfNm", "sprtTrgtAgeLmtYn", "sprtTrgtMinAge", "sprtTrgtMaxAge",
              "zipCd", "aplyPrdSeCd", "aplyYmd"]
    for field in fields:
        values = Counter("" if row.get(field) is None
                         else str(row[field]).strip() for row in policies)
        print(field, "누락", values[""], "고유 값", len(values), "상위 5개", values.most_common(5))

    df = pd.DataFrame(policies, columns=["plcyNm", *fields])
    age_min = pd.to_numeric(df["sprtTrgtMinAge"], errors="coerce")
    age_max = pd.to_numeric(df["sprtTrgtMaxAge"], errors="coerce")
    print("기간 유형별 날짜 누락", pd.crosstab(df["aplyPrdSeCd"], df["aplyYmd"].fillna("").str.strip() == ""))
    print("연령 플래그별 최소 연령 0", pd.crosstab(df["sprtTrgtAgeLmtYn"], age_min == 0))
    print("연령 플래그별 최대 연령 0", pd.crosstab(df["sprtTrgtAgeLmtYn"], age_max == 0))
    sample = df[(df["sprtTrgtAgeLmtYn"] == "N") & (age_min > 0) & (age_max > 0)]
    print(sample[["plcyNm", "sprtTrgtMinAge", "sprtTrgtMaxAge"]].head(5).to_string(index=False))
    print(df["lclsfNm"].fillna("").value_counts().to_string())


if __name__ == "__main__":
    main()
