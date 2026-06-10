# 평가 지표 대응 체크리스트

## 데이터 수집 및 구축의 적절성

- [x] NLP/RAG 목적에 맞는 데이터셋 선정
- [x] 온통청년, K-Startup, HRD 공식 출처 사용
- [x] 원본 raw 데이터 보존
- [x] 청년 관련성 기준으로 서비스 통합 범위 제한

## 데이터 편향성, 중복성, 결측치 처리

- [x] 청년 관련성 high 기준 적용
- [x] item_id 기준 중복 확인
- [x] 필드별 결측률 리포트 생성
- [x] 원본에 없는 값 임의 생성 금지

## 텍스트 전처리 및 형태소 분석

- [x] 정규표현식 기반 텍스트 정규화
- [x] KoNLPy Okt 사용 시도
- [x] KoNLPy 미설치 환경 fallback 처리
- [x] 불용어 처리
- [x] BoW 리포트 생성
- [x] TF-IDF 리포트 생성
- [x] Word2Vec/FastText 적용 상태 기록

## RAG / Graph 최적화 청킹 전략

- [x] item_id 기반 search_profile chunk 생성
- [x] Vector DB 입력용 content/metadata 분리
- [x] Graph DB 확장 후보 노드/관계 문서화
- [x] 향후 Recursive/Semantic Chunking 개선안 문서화

## 문서화 완성도

- [x] 데이터 스키마 문서
- [x] 전처리 파이프라인 문서
- [x] 데이터 수량 문서
- [x] 출처 URL 문서
- [x] 백엔드/RAG 전달 문서
