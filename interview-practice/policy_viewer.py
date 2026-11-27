"""수집 원본과 정규화 결과를 비교하는 보조 Streamlit 화면 (p.12).

data의 두 JSON 파일을 입력받아 원본과 메타데이터 표를 표시한다. main·policies와 독립적이며,
두 파일을 별도로 준비해야 한다. 이 화면은 Chroma에 실제 적재된 상태까지 검증하지 않는다.
"""

import json
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(layout="wide")

data_dir = Path(__file__).resolve().parent / "data"
raw_path = data_dir / "youth_policies_raw.json"
normalized_path = data_dir / "youth_policies_normalized.json"
if not raw_path.is_file() or not normalized_path.is_file():
    st.info("원본·정규화 JSON이 필요합니다. 파일 위치는 README의 정책 데이터 조회 항목을 확인하세요.")
    st.stop()

with raw_path.open(encoding="utf-8") as f:
    raw = json.load(f)["policies"]

with normalized_path.open(encoding="utf-8") as f:
    normalized = json.load(f)

st.title("청년정책 데이터 Explorer")

tab1, tab2 = st.tabs(["API 원본", "정규화 결과"])

with tab1:
    st.dataframe(pd.DataFrame(raw), hide_index=True)

with tab2:
    rows = [
        {
            "item_id": p["item_id"],
            "title": p["title"],
            **p["metadata"]
        }
        for p in normalized
    ]

    st.dataframe(pd.DataFrame(rows), hide_index=True)
