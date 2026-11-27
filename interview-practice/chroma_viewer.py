"""실습 Chroma 컬렉션에 저장한 청크와 벡터를 확인하는 Streamlit 화면 (p.9~10, p.12).

config의 DB 경로에서 컬렉션과 청크를 선택하면 본문·메타데이터 표, 벡터 차원과 값을 표시한다.
indexing이 적재한 값을 get으로 읽으므로 질문 임베딩이나 RAG 워크플로우 실행이 필요 없다.
전체 메타데이터와 본문을 한 번에 읽으므로 대규모 컬렉션에서 화면이 느려질 수 있다.
"""

import chromadb
import pandas as pd
import streamlit as st

from config import DB_PATH

st.set_page_config(
    page_title="ChromaDB Explorer",
    layout="wide"
)

# 1. 기존 ChromaDB 연결
client = chromadb.PersistentClient(
    path=DB_PATH
)

# 2. 컬렉션 선택
collections = client.list_collections()

collection_names = [
    collection.name for collection in collections
]

if not collection_names:
    st.info("DB 경로에 조회 가능한 컬렉션이 없습니다. config.py의 DB_PATH와 데이터셋을 확인하세요.")
    st.stop()

selected = st.sidebar.selectbox(
    "Collection",
    collection_names
)

collection = client.get_collection(selected)

# 3. 저장된 데이터 조회
# 유사도 검색이나 임베딩 API 호출은 수행하지 않는다.
data = collection.get(
    include=["documents", "metadatas"]
)

# 4. 메타데이터를 개별 열로 펼쳐 테이블 구성
rows = []

for i in range(len(data["ids"])):
    rows.append({
        "chunk_id": data["ids"][i],
        "document": data["documents"][i],
        **data["metadatas"][i]
    })

df = pd.DataFrame(rows)

# 5. 테이블 출력
st.title("ChromaDB Explorer")

st.metric("저장된 청크 수", collection.count())

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    height=500
)

# 6. 선택한 청크의 임베딩 벡터 확인
st.subheader("Embedding 확인")

if not data["ids"]:
    st.info("선택한 컬렉션에 저장된 청크가 없습니다.")
    st.stop()

selected_id = st.selectbox(
    "Chunk ID",
    data["ids"]
)

record = collection.get(
    ids=[selected_id],
    include=["embeddings"]
)

embedding = record["embeddings"][0]

st.write("벡터 차원:", len(embedding))
if not st.checkbox("전체 차원 보기"):
    embedding = embedding[:10]

st.dataframe(
    pd.DataFrame({
        "dimension": range(len(embedding)),
        "value": embedding
    }),
    hide_index=True
)
