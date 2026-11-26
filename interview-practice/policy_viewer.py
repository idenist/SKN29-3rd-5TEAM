import json
import pandas as pd
import streamlit as st

st.set_page_config(layout="wide")

with open("data/youth_policies_raw_200.json", encoding="utf-8") as f:
    raw = json.load(f)["policies"]

with open("data/youth_policies_normalized.json", encoding="utf-8") as f:
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