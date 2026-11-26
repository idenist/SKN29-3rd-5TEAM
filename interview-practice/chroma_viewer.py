import chromadb
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="ChromaDB Explorer",
    layout="wide"
)

# 1. 기존 ChromaDB 연결
client = chromadb.PersistentClient(
    path="./practice_vector_db"
)

# 2. 컬렉션 선택
collections = client.list_collections()

collection_names = [
    collection.name for collection in collections
]

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

st.dataframe(
    pd.DataFrame({
        "dimension": range(len(embedding)),
        "value": embedding
    }),
    hide_index=True
)