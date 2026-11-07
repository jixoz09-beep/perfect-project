# 지도 출처와 변경 사항

- 역사 경계: **Seshat Global History Databank — Cliopatria v0.2.1**.
  - 프로젝트: https://github.com/Seshat-Global-History-Databank/cliopatria
  - 사용 데이터: https://raw.githubusercontent.com/Seshat-Global-History-Databank/cliopatria/v0.2.1/cliopatria.geojson.zip
  - 이용 조건: Creative Commons Attribution 4.0 International, https://creativecommons.org/licenses/by/4.0/
  - 원본 이용 조건은 `LICENSE_Cliopatria.txt`에 보존했습니다.
  - 변경 사항: 1769~2024년 중 차량 기록이 있는 연도를 FromYear ≤ 연도 ≤ ToYear로 추출하고, Type=POLITY를 선택했습니다. 괄호로 시작하는 집합 항목은 제외했습니다. 표시 성능을 위해 지형을 0.045도 허용 오차로 단순화하고 좌표를 소수점 4자리로 정리했습니다. 대표 표시점을 계산하고, 한국어 국가명·제조사 국적 연결 코드를 추가했으며 연도별 파일로 압축했습니다.
- 2025·2026년: 사용자 제공 지도 인수 파일의 Natural Earth 기반 현대 경계. 두 연도 파일을 그대로 원천으로 사용했습니다. 해당 시점의 개별 국경 변경을 새로 검증한 지도는 아닙니다.
  - https://www.naturalearthdata.com/
  - Natural Earth 이용 조건: public domain, https://www.naturalearthdata.com/about/terms-of-use/
- 한국어 국가명 보조: Wikidata의 한국어 라벨과 ISO 코드, Babel·pycountry의 국가명, 한국어 보완 사전.
  - Wikidata 데이터는 CC0, https://www.wikidata.org/wiki/Wikidata:Licensing
  - 라벨 조회에 사용한 엔터티 ID와 원문은 `polities_ko.json`에 있습니다.
- 역사 국가와 제조사 국적 연결은 앱의 탐색을 위한 편집 매핑입니다. 과거 식민 통치자의 국적을 현지 제조사의 국적으로 간주하지 않았습니다. 대응 정보가 없으면 연결을 비워 두었습니다.

역사 경계의 근사·불확실성, 중첩 또는 원자료의 누락이 있을 수 있습니다. 이 지도는 정치적 지위나 영유권에 관한 판단을 나타내지 않습니다. 차량의 제조사 국적과 판매 시장은 별개입니다.
