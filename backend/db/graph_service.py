"""
backend/db/graph_service.py

Neo4j Graph DB 서비스.
- 기존 Chroma Vector DB 파이프라인과 독립적으로 동작
- 연결 실패 시 graceful degradation (빈 결과 반환)
- item_id 기반으로 opportunities.json과 동일한 식별 체계 사용
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class GraphService:
    """
    Neo4j Graph DB 연결 및 검색 서비스.

    사용법:
        svc = GraphService(uri, user, password)
        if svc.is_connected():
            svc.build_graph_from_chunks(chunks)
            results = svc.search_by_conditions(domain="주거", region_code="11000", limit=5)
    """

    def __init__(self, uri: str, user: str, password: str):
        self.driver = None
        self._connected = False
        try:
            from neo4j import GraphDatabase
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            # 연결 유효성 확인
            self.driver.verify_connectivity()
            self._connected = True
            logger.info("Neo4j 연결 성공: %s", uri)
        except ImportError:
            logger.warning("neo4j 패키지 미설치 — pip install neo4j 필요. Graph 검색 비활성화.")
        except Exception as e:
            logger.warning("Neo4j 연결 실패 (%s) — Graph 검색 비활성화. 기존 Vector 검색만 동작.", e)

    def is_connected(self) -> bool:
        return self._connected

    def close(self):
        if self.driver:
            self.driver.close()

    # ── 그래프 구축 ──────────────────────────────────────────

    def build_graph_from_chunks(self, chunks: list[dict]) -> dict:
        """
        opportunity_chunks.jsonl 데이터로 Neo4j 노드/관계를 생성한다.

        노드:
            (Item   {item_id, title, source_category, domain, info_score})
            (Domain {name})
            (Region {code})
            (Org    {name})

        관계:
            Item -[:BELONGS_TO]->  Domain
            Item -[:AVAILABLE_IN]-> Region
            Item -[:PROVIDED_BY]-> Org
        """
        if not self._connected:
            return {"status": "skipped", "reason": "not connected"}

        inserted = 0
        errors = 0

        with self.driver.session() as session:
            # 제약 조건 (중복 방지)
            session.run("CREATE CONSTRAINT item_id IF NOT EXISTS FOR (n:Item) REQUIRE n.item_id IS UNIQUE")
            session.run("CREATE CONSTRAINT domain_name IF NOT EXISTS FOR (n:Domain) REQUIRE n.name IS UNIQUE")
            session.run("CREATE CONSTRAINT region_code IF NOT EXISTS FOR (n:Region) REQUIRE n.code IS UNIQUE")
            session.run("CREATE CONSTRAINT org_name IF NOT EXISTS FOR (n:Org) REQUIRE n.name IS UNIQUE")

            for chunk in chunks:
                try:
                    item_id        = chunk.get("item_id") or chunk.get("policy_id", "")
                    title          = chunk.get("title") or chunk.get("policy_name", "")
                    source_cat     = chunk.get("source_category", "policy")
                    domain         = chunk.get("domain", "")
                    info_score     = int(chunk.get("info_score") or chunk.get("metadata", {}).get("info_score") or 0)
                    region_code    = str(chunk.get("region_code") or chunk.get("metadata", {}).get("region_code") or "")
                    organization   = chunk.get("organization") or chunk.get("metadata", {}).get("organization") or chunk.get("supervising_org", "")

                    if not item_id:
                        continue

                    session.run(
                        """
                        MERGE (item:Item {item_id: $item_id})
                        SET   item.title           = $title,
                              item.source_category = $source_cat,
                              item.domain          = $domain,
                              item.info_score      = $info_score

                        WITH item

                        // Domain 관계
                        FOREACH (_ IN CASE WHEN $domain <> '' THEN [1] ELSE [] END |
                            MERGE (d:Domain {name: $domain})
                            MERGE (item)-[:BELONGS_TO]->(d)
                        )

                        // Region 관계 (comma-separated region_code 지원)
                        WITH item
                        FOREACH (code IN
                            CASE WHEN $region_code <> ''
                                 THEN split($region_code, ',')
                                 ELSE [] END |
                            MERGE (r:Region {code: trim(code)})
                            MERGE (item)-[:AVAILABLE_IN]->(r)
                        )

                        // Org 관계
                        WITH item
                        FOREACH (_ IN CASE WHEN $org <> '' THEN [1] ELSE [] END |
                            MERGE (o:Org {name: $org})
                            MERGE (item)-[:PROVIDED_BY]->(o)
                        )
                        """,
                        item_id=item_id,
                        title=title,
                        source_cat=source_cat,
                        domain=domain,
                        info_score=info_score,
                        region_code=region_code,
                        org=organization,
                    )
                    inserted += 1
                except Exception as e:
                    logger.debug("노드 삽입 오류 (%s): %s", chunk.get("item_id"), e)
                    errors += 1

        logger.info("Graph 구축 완료 — inserted=%d, errors=%d", inserted, errors)
        return {"status": "ok", "inserted": inserted, "errors": errors}

    # ── 검색 ─────────────────────────────────────────────────

    def search_by_conditions(
        self,
        domain: Optional[str] = None,
        region_code: Optional[str] = None,
        source_category: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        if not self._connected:
            return []

        try:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (item:Item)
                    WHERE
                        ($domain IS NULL OR item.domain CONTAINS $domain)
                        AND ($source_cat IS NULL OR item.source_category = $source_cat)
                    RETURN
                        item.item_id        AS item_id,
                        item.title          AS title,
                        item.source_category AS source_category,
                        item.domain         AS domain,
                        item.info_score     AS info_score,
                        [] AS region_codes
                    ORDER BY item.info_score DESC
                    LIMIT $limit
                    """,
                    domain=domain,
                    source_cat=source_category,
                    limit=limit,
                )

                rows = result.data()
                return [self._to_compact(row) for row in rows]

        except Exception as e:
            logger.warning("Graph 검색 실패: %s", e)
            return []

    def search_related_items(self, item_id: str, limit: int = 3) -> list[dict]:
        """
        특정 item과 같은 Domain에 속한 관련 항목 검색.
        중복 수급 체크 확장 포인트.
        """
        if not self._connected:
            return []

        try:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (item:Item)
                    WHERE
                        ($domain IS NULL OR item.domain CONTAINS $domain)
                        AND ($source_cat IS NULL OR item.source_category = $source_cat)
                    RETURN
                        item.item_id        AS item_id,
                        item.title          AS title,
                        item.source_category AS source_category,
                        item.domain         AS domain,
                        item.info_score     AS info_score,
                        [] AS region_codes
                    ORDER BY item.info_score DESC
                    LIMIT $limit
                    """,
                    domain=domain,
                    source_cat=source_category,
                    limit=limit,
                )
                return [self._to_compact(row) for row in result.data()]
        except Exception as e:
            logger.warning("관련 항목 검색 실패: %s", e)
            return []

    # ── 내부 유틸 ─────────────────────────────────────────────

    @staticmethod
    def _to_compact(row: dict) -> dict:
        """Neo4j 결과를 기존 Vector 검색 compact format과 동일하게 변환."""
        return {
            "item_id":         row.get("item_id", ""),
            "title":           row.get("title", ""),
            "policy_name":     row.get("title", ""),   # 기존 호환 alias
            "policy_id":       row.get("item_id", ""), # 기존 호환 alias
            "source_category": row.get("source_category", "policy"),
            "domain":          row.get("domain", ""),
            "info_score":      row.get("info_score", 0),
            "score":           0.0,   # Vector score 없음 — Graph 결과임을 구분
            "from_graph":      True,  # Hybrid merge에서 출처 구분용
            "text":            "",
            "source_url":      "",
            "application_url": "",
            "needs_detail_check": False,
        }