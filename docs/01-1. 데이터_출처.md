# 데이터 출처 문서

## 1. 온통청년 Open API

- 출처명: 온통청년 Open API
- URL: https://www.youthcenter.go.kr/cmnFooter/openapiIntro/oaiGuide
- 보조 URL: https://www.data.go.kr/data/15143273/openapi.do
- 사용 데이터: 청년정책 데이터
- 통합 방식: `source_category = policy`로 통합
- 비고: 정책명, 지원내용, 신청기간, 대상, 지역, 신청 URL 등을 활용했다.

## 2. K-Startup / 창업진흥원 Open API

- 출처명: K-Startup / 창업진흥원 Open API
- URL: https://www.data.go.kr/data/15125364/openapi.do
- 보조 URL: https://nidview.k-startup.go.kr/view/public/kisedKstartupService/announcementInformation
- 사용 데이터: 창업지원 사업공고
- 통합 방식: `youth_relevance = high` 데이터만 `source_category = startup_notice`로 통합
- 비고: 청년, 청년창업, 청년기업, 청년 우대, 청년 연령 조건 등을 기준으로 선별했다.

## 3. 고용24/HRD Open API

- 출처명: 고용24 Open API
- URL: https://www.work24.go.kr/cm/e/a/0110/selectOpenApiIntro.do
- 사용 데이터: 국민내일배움카드 훈련과정
- 통합 방식: `youth_relevance = high` 데이터만 `source_category = training`으로 통합
- 비고: 청년 취업, 디지털 교육, 구직자 친화 교육훈련 데이터를 중심으로 선별했다.

## 4. 제외 데이터

### 공모전·경진대회·모집공고

이번 최종 범위에서 제외했다.

제외 사유:

- 공식 OpenAPI 기반의 안정적인 다건 수집원이 명확하지 않음
- 현재 통합 데이터만으로도 청년정책, 창업지원, 교육훈련 영역을 충분히 구성함
- 평가 대응을 위해 추가 수집보다 전처리 품질과 문서화를 우선함
