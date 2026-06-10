# 데이터 전처리 파이프라인 요약

## 1. 전체 흐름

```text
데이터 수집
→ 원본 raw 데이터 보존
→ 출처별 전처리
→ 컬럼 표준화
→ 결측치 확인
→ 중복 제거
→ 청년 관련성 분류
→ raw_text 생성
→ 공통 스키마 통합
→ RAG 청크 생성
→ KoNLPy 형태소 분석
→ 불용어 제거
→ BoW / TF-IDF 키워드 리포트 생성
→ 최종 백엔드/RAG 산출물 생성
```

## 2. 단계별 산출물

| 단계 | 입력 | 처리 | 출력 |
|---|---|---|---|
| 수집 | API 응답 | 원본 저장 | `data/raw/` |
| 출처별 전처리 | raw 데이터 | 컬럼 표준화, 결측/중복 확인 | 출처별 processed 파일 |
| 청년 관련성 분류 | 정제 데이터 | high/medium/low 분류 | high 데이터 |
| 통합 | high 데이터 | 공통 스키마 매핑 | `opportunities.json` |
| 청킹 | 통합 데이터 | content/metadata 생성 | `opportunity_chunks.jsonl` |
| 형태소 분석 | 통합 데이터 | KoNLPy/fallback 명사 추출 | `opportunities_with_keywords.json` |
| 키워드 분석 | 텍스트 토큰 | BoW/TF-IDF 분석 | keyword reports |
| 검증 | 최종 데이터 | 결측/중복/청크 통계 | reports |

## 3. 최종 데이터 수량

| 구분 | 건수 |
|---|---:|
| 온통청년 정책 | 2,611 |
| K-Startup 청년 HIGH 창업공고 | 3,789 |
| HRD 청년 HIGH 교육훈련 | 20,403 |
| 최종 opportunities.json | 26,803 |
| 최종 opportunity_chunks.jsonl | 33,950 |

## 4. 편향성 관리

본 프로젝트는 청년 지원 탐색 서비스이므로 모든 공공 데이터를 무조건 통합하지 않았다.

- K-Startup은 청년 관련성 HIGH 데이터만 통합
- HRD는 청년 취업·디지털 교육 관련성 HIGH 데이터만 통합
- 공모전/경진대회는 공식 OpenAPI 기반 다건 수집원이 불명확하여 제외

이 방식은 서비스 목적과 무관한 데이터가 검색 결과를 오염시키는 것을 줄이기 위한 것이다.

## 5. 결측치 처리 원칙

- 원본에 없는 값은 임의 생성하지 않는다.
- 빈 값은 “해당 없음”이 아니라 “정보 미제공”으로 본다.
- 결측률은 `data/reports/missing_value_report.csv`와 `data/processed/source_coverage_report.csv`에 기록한다.

## 6. 중복 처리 원칙

- 통합 기준은 `item_id`
- `policy_id`는 온통청년 원본 내부 key로만 유지
- 최종 중복 확인 결과는 `data/reports/duplicate_check_report.csv`에 기록한다.
