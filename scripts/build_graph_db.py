"""
scripts/build_graph_db.py

Neo4j Graph DB 초기 데이터 적재 스크립트.
opportunity_chunks.jsonl 을 읽어 Item 노드와 관계를 생성한다.

사용법:
    python scripts/build_graph_db.py \
        --input data/processed/opportunity_chunks.jsonl \
        [--limit 500]   # 테스트용 건수 제한 (생략 시 전체)

환경변수 (.env):
    NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=xxxxxxxx
"""

import argparse
import json
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.db.graph_service import GraphService


def load_chunks(path: str, limit: int | None = None) -> list[dict]:
    chunks = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def main():
    parser = argparse.ArgumentParser(description="Neo4j Graph DB 초기 데이터 적재")
    parser.add_argument("--input",  default="data/processed/opportunity_chunks.jsonl")
    parser.add_argument("--limit",  type=int, default=None, help="적재 건수 제한 (테스트용)")
    args = parser.parse_args()

    uri      = os.getenv("NEO4J_URI", "")
    user     = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")

    if not uri or not password:
        logger.error("NEO4J_URI, NEO4J_PASSWORD 환경변수를 .env에 설정하세요.")
        sys.exit(1)

    logger.info("Neo4j 연결 중: %s", uri)
    svc = GraphService(uri=uri, user=user, password=password)

    if not svc.is_connected():
        logger.error("Neo4j 연결 실패. 종료.")
        sys.exit(1)

    logger.info("청크 파일 읽기: %s", args.input)
    chunks = load_chunks(args.input, limit=args.limit)
    logger.info("총 %d개 청크 로드 완료", len(chunks))

    logger.info("Graph 구축 시작...")
    result = svc.build_graph_from_chunks(chunks)

    logger.info("Graph 구축 완료: %s", result)
    svc.close()


if __name__ == "__main__":
    main()