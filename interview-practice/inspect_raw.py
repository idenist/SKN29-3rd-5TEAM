"""온통청년 원본 정책 데이터의 구조를 확인하는 파일."""

import json
from pathlib import Path

# 실제 저장한 파일명으로 수정
path = Path("data/youth_policies_raw.json")

with path.open(encoding="utf-8") as f:
    raw = json.load(f)

print("최상위 자료형:", type(raw).__name__)

if isinstance(raw, list):
    policies = raw

elif isinstance(raw, dict):
    print("최상위 키:", list(raw.keys()))
    policies = raw.get("policies", [])

else:
    policies = []

print("전체 정책 수:", len(policies))

if policies:
    print("\n[첫 번째 정책의 필드와 값]")

    # for key, value in policies[0].items():
        # print(f"{key}: {str(value)[:100]}")
        
from collections import Counter

def clean(value):
    return "" if value is None else str(value).strip()

fields = [
    "lclsfNm",             # 정책 분야
    "sprtTrgtAgeLmtYn",    # 연령 제한 여부
    "sprtTrgtMinAge",      # 최소 연령
    "sprtTrgtMaxAge",      # 최대 연령
    "zipCd",              # 지역 관련 코드
    "aplyPrdSeCd",        # 신청 기간 구분 코드
    "aplyYmd"             # 신청 기간
]

for field in fields:
    values = [clean(p.get(field)) for p in policies]
    counts = Counter(values)

    print(f"\n[{field}]")
    print("누락:", counts[""])
    print("고유 값 개수:", len(counts))
    print("상위 5개 값:", counts.most_common(5))
    
import pandas as pd

df = pd.DataFrame(policies)

# 신청 기간이 비어 있는지 확인
df["missing_date"] = (
    df["aplyYmd"].fillna("").str.strip() == ""
)

# 신청 기간 유형별 결측 여부 교차 집계
print(pd.crosstab(
    df["aplyPrdSeCd"],
    df["missing_date"]
))

# 연령 값을 숫자로 변환
min_age = pd.to_numeric(
    df["sprtTrgtMinAge"], errors="coerce"
)

max_age = pd.to_numeric(
    df["sprtTrgtMaxAge"], errors="coerce"
)

print("[최소 연령이 0인지]")
print(pd.crosstab(
    df["sprtTrgtAgeLmtYn"],
    min_age == 0
))

print("\n[최대 연령이 0인지]")
print(pd.crosstab(
    df["sprtTrgtAgeLmtYn"],
    max_age == 0
))

# 연령 제한이 없지만 구체적인 연령 범위가 있는 사례
samples = df[
    (df["sprtTrgtAgeLmtYn"] == "N")
    & (min_age > 0)
    & (max_age > 0)
]

print("\n[연령 제한 N이지만 연령 범위가 있는 사례]")
print(samples[[
    "plcyNm",
    "sprtTrgtMinAge",
    "sprtTrgtMaxAge"
]].head(5).to_string(index=False))

print(
    df["lclsfNm"]
    .fillna("")
    .value_counts()
    .to_string()
)