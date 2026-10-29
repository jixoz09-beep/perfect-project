

"""AUTOVERSE — 자동차 탐색 · 분석 · 제작 (Python 3.11+).

실행: pip install -r requirements.txt && streamlit run main.py
main.py와 requirements.txt만으로 시작할 수 있습니다. API 키는 필수가 아닙니다.

범위: 확인 가능한 초기 차량 목록 + Wikidata 온라인 확장, 역사 지도 스냅샷,
직접 조절하는 간이 3D, GLB 보기, 종방향 성능 추정, 설계 코드 저장/복원.
전 세계 모든 차량 데이터/연도별 국경/정밀 실차 3D를 포함한 제품은 아닙니다.
사진 한 장에서 실차의 정확한 구조를 복원하거나 임의 GLB의 문을 자동 분리하지 않습니다.
실제 운전/충돌/열/강도/조향 시뮬레이션은 다음 개발 범위입니다.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import html
import json
import math
import os
import re
import secrets
import struct
import time
import zlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

import pandas as pd
import requests
import streamlit as st
from babel import Locale
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parent
CURRENT_YEAR = datetime.now(timezone.utc).year
SCHEMA_VERSION = 1
HTTP_HEADERS = {"User-Agent": "AUTOVERSE-Education/1.0 (open educational car explorer)"}
BASEMAP_REPO = "https://github.com/aourednik/historical-basemaps"
BASEMAP_RAW = "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/"
MAX_MODEL_BYTES = 15 * 1024 * 1024
MAX_CODE_CHARS = 50000

# country는 개발·제작 국가의 역사적 구분이며, 브랜드의 현재 본사 국가와 구별합니다.
# 각 차량의 당시 국가 ID를 보존합니다.
COUNTRIES = {
    "FR": {"ko": "프랑스", "point": [2.35, 48.86], "colors": ["#203a83", "#e6e9f0", "#b92735"], "flag": "Flag of France.svg", "aliases": ["france", "kingdom of france", "french republic", "french empire"]},
    "GB": {"ko": "영국", "point": [-1.6, 52.5], "colors": ["#17305c", "#f0edf1", "#b52636"], "flag": "Flag of the United Kingdom.svg", "aliases": ["united kingdom", "great britain", "britain", "england"]},
    "US": {"ko": "미국", "point": [-96, 38], "colors": ["#173764", "#d8dde8", "#a33145"], "flag": "Flag of the United States.svg", "aliases": ["usa", "united states", "united states of america"]},
    "DE": {"ko": "독일", "point": [9.7, 51], "colors": ["#1a1b22", "#a11d29", "#cda82d"], "flag": "Flag of Germany.svg", "aliases": ["germany", "german empire", "prussia", "kingdom of prussia", "nazi germany", "weimar republic"]},
    "DE-W": {"ko": "서독", "point": [7.5, 50.8], "colors": ["#15171d", "#b22932", "#d4aa32"], "flag": "Flag of Germany.svg", "aliases": ["west germany", "federal republic of germany", "germany (uk)", "germany (usa)", "germany (france)"]},
    "DE-E": {"ko": "동독", "point": [13.3, 52], "colors": ["#17191e", "#8e2739", "#c29c41"], "flag": "Flag of East Germany.svg", "aliases": ["east germany", "german democratic republic", "germany (soviet)"]},
    "AT": {"ko": "오스트리아", "point": [14.3, 47.6], "colors": ["#ac2738", "#ece9ec", "#b32737"], "flag": "Flag of Austria.svg", "aliases": ["austria", "austrian empire", "austria-hungary"]},
    "IT": {"ko": "이탈리아", "point": [12.5, 42], "colors": ["#137158", "#f2efe7", "#bc3443"], "flag": "Flag of Italy.svg", "aliases": ["italy", "kingdom of italy"]},
    "JP": {"ko": "일본", "point": [138, 37], "colors": ["#e7e9ef", "#8b263e", "#e7e9ef"], "flag": "Flag of Japan.svg", "aliases": ["japan", "empire of japan"]},
    "KR": {"ko": "대한민국", "point": [127.8, 36.3], "colors": ["#e5e9ef", "#9d263c", "#234d87"], "flag": "Flag of South Korea.svg", "aliases": ["south korea", "korea, republic of", "republic of korea"]},
    "CN": {"ko": "중국", "point": [105, 35], "colors": ["#8d2030", "#b52d37", "#c0a045"], "flag": "Flag of the People's Republic of China.svg", "aliases": ["china", "people's republic of china", "qing empire", "qing dynasty"]},
    "CZ": {"ko": "체코", "point": [15.5, 49.8], "colors": ["#1b4774", "#e1e6ef", "#a8253d"], "flag": "Flag of the Czech Republic.svg", "aliases": ["czechia", "czech republic", "czechoslovakia"]},
    "SU": {"ko": "소련", "point": [37.6, 55.75], "colors": ["#751d29", "#a92336", "#c6a63b"], "flag": "Flag of the Soviet Union.svg", "aliases": ["ussr", "soviet union", "union of soviet socialist republics"]},
    "RU": {"ko": "러시아", "point": [37.6, 55.75], "colors": ["#dddded", "#254d8c", "#9b263f"], "flag": "Flag of Russia.svg", "aliases": ["russia", "russian federation", "russian empire"]},
    "SE": {"ko": "스웨덴", "point": [15, 62], "colors": ["#1a4f88", "#c8ad37", "#1a4f88"], "flag": "Flag of Sweden.svg", "aliases": ["sweden"]},
    "IN": {"ko": "인도", "point": [79, 23], "colors": ["#b46d28", "#e8e6d9", "#397353"], "flag": "Flag of India.svg", "aliases": ["india", "republic of india"]},
}

# 추가 국가의 ISO 코드·한글 이름. 국경·국기·개발국을 자동 추론하는 자료는 아닙니다.
_ko_territories = Locale.parse("ko").territories
for _iso, _english in Locale.parse("en").territories.items():
    if len(_iso) == 2 and _iso.isalpha() and _iso not in COUNTRIES and _iso not in {"ZZ", "EU", "UN", "EZ"}:
        COUNTRIES[_iso] = dict(ko=_ko_territories.get(_iso, _english), point=None,
            colors=["#24324b", "#8a7953", "#24324b"], flag="", aliases=[_english.lower()])

def seed_car(cid, name, en, year, country, kind, event, description, source, *, specs=None, shape="sedan", photo=None, note=""):
    return dict(id=cid, name=name, name_en=en, year=year, country=country,
                kind=kind, event=event, description=description, source=source,
                specs=specs or {}, shape=shape, photo_title=photo or "",
                photo_query=en, note=note, source_kind="초기 자료", model_url="",
                model_license="", model_source="", model_author="")

# 숫자가 확인되지 않은 제원은 비워 둡니다. 발표/양산/시제 날짜는 event로 구별합니다.
# 같은 모델의 모든 세대·트림을 포함한 목록이 아닙니다.
CATALOG = [
    seed_car("cugnot-1769", "퀴뇨 증기차 1차 시제", "Cugnot steam wagon", 1769, "FR", "실험·특수차", "시제 시험", "포를 운반하기 위해 고안한 증기 동력 도로 차량. 초기 시제품과 오늘날 남아 있는 후속 실물의 제작 연도는 구별해야 합니다.", "https://www.lefardierdecugnot.fr/inventeur", shape="steam", note="대표 사진에는 1770~1771년 후속 차량 또는 복제품이 포함될 수 있습니다."),
    seed_car("benz-1886", "벤츠 파텐트 모터바겐 1호", "Benz Patent-Motorwagen", 1886, "DE", "승용차", "특허·공개", "강관 프레임, 단기통 4행정 엔진, 세 개의 바퀴를 결합한 초기 가솔린 자동차입니다.", "https://group.mercedes-benz.com/company/tradition/company-history/1885-1886.html", specs={"power_kw": 0.55}, shape="vintage", note="차량 완성은 1885년, 특허·공개 기준 연도는 1886년입니다."),
    seed_car("benz-bus-1895", "벤츠 모터 옴니버스", "Benz Omnibus 1895", 1895, "DE", "버스", "노선 운행", "초기 내연기관 노선버스. 마차와 유사한 차체에 엔진을 결합했습니다.", "https://group.mercedes-benz.com/company/tradition/company-history/1886-1920.html", shape="van"),
    seed_car("daimler-truck-1896", "다임러 모터 트럭", "Daimler Motor Lastwagen", 1896, "DE", "트럭", "공개·납품", "화물 마차를 바탕으로 만든 초기 엔진 트럭으로, 피닉스 2기통 엔진을 사용했습니다.", "https://www.daimlertruck.com/en/company/history", specs={"payload_kg": 1500}, shape="truck", note="공식 사료의 엔진 출력은 4 hp. 단위 혼동을 피하기 위해 kW 값은 별도 입력하지 않았습니다."),
    seed_car("ford-t-1908", "포드 모델 T", "Ford Model T", 1908, "US", "승용차", "판매 시작", "표준화와 대량생산을 통해 자동차 보급에 큰 영향을 준 모델입니다.", "https://corporate.ford.com/articles/history/the-model-t.html", shape="vintage"),
    seed_car("traction-1934", "시트로엥 트락시옹 아방", "Citroen Traction Avant", 1934, "FR", "승용차", "공개", "전륜구동과 일체형 강철 차체를 활용한 자동차입니다.", "https://www.media.stellantis.com/me-en/citroen/press/citroen-celebrates-90-years-of-the-traction-avant-an-iconic-model-with-100-patents", shape="vintage"),
    seed_car("vw-kdf-1938", "폭스바겐 KdF 바겐", "Volkswagen KdF Wagen", 1938, "DE", "승용차", "명칭·모델 공개", "전후 비틀로 이어진 Type 1 계열의 전쟁 전 모델입니다. 당시 정치·산업 배경과 실제 민간 보급 규모를 함께 살펴봐야 합니다.", "https://www.volkswagen-newsroom.com/en/press-releases/75-years-ago-in-wolfsburg-start-of-series-production-of-the-volkswagen-beetle-6732", shape="coupe", note="전후 비틀의 본격적인 양산 개시인 1945년과 구분합니다."),
    seed_car("vw-beetle-1945", "폭스바겐 Type 1 전후 양산형", "Volkswagen Beetle", 1945, "DE", "승용차", "전후 양산 시작", "영국 점령 행정 아래에서 생산이 재개된 Type 1입니다.", "https://www.volkswagen-newsroom.com/en/press-releases/75-years-ago-in-wolfsburg-start-of-series-production-of-the-volkswagen-beetle-6732", shape="coupe", note="1945년에는 서독·동독이 아직 수립되지 않았습니다. 생산지는 영국 점령 구역입니다."),
    seed_car("porsche-356-1948", "포르쉐 356 1호 로드스터", "Porsche 356 No 1 Roadster", 1948, "AT", "시제·스포츠카", "도로 운행 허가", "포르쉐 이름을 단 첫 스포츠카. 오스트리아 그뮌트에서 제작된 1호 차량입니다.", "https://newsroom.porsche.com/en/press-kits/Porsche-Museum/Porsche-356-%E2%80%9ENr.1%E2%80%9C-Roadster.html", shape="roadster", note="브랜드는 독일계이지만 이 차량의 개발·제작 국가는 오스트리아로 분류했습니다."),
    seed_car("citroen-2cv-1948", "시트로엥 2CV", "Citroen 2CV", 1948, "FR", "승용차", "공개", "간결한 구조와 실용성을 추구한 프랑스의 소형차입니다.", "https://www.citroen.fr/univers-citroen/history.html", shape="hatchback"),
    seed_car("vw-t1-1950", "폭스바겐 트랜스포터 T1", "Volkswagen Type 2 T1", 1950, "DE-W", "밴·버스", "양산 시작", "상용 밴과 승합차 등 다양한 용도로 발전한 후방 엔진 차량입니다.", "https://www.volkswagenvans.ie/en/all-about-volkswagen-commercial-vehicles/brand-history.html", specs={"payload_kg": 750}, shape="van"),
    seed_car("firebird-1954", "GM 파이어버드 I", "GM Firebird I", 1954, "US", "콘셉트카", "시제 제작", "항공기에서 영감을 얻은 가스터빈 실험 차량입니다. 일반 판매 모델과 구분됩니다.", "https://www.gm.com/heritage/collection/gm-concept/1954-firebird-I", shape="coupe", note="GM 공식 컬렉션의 1954년 공개 모델 기준입니다. 개발 완료 시점을 1953년으로 기술하는 자료와 구별합니다."),
    seed_car("sl-1954", "메르세데스 벤츠 300 SL", "Mercedes-Benz 300 SL W198", 1954, "DE-W", "스포츠카", "공개", "걸윙 도어와 연료분사 엔진으로 알려진 스포츠카입니다.", "https://www.mercedes-benz.com/en/art-and-culture/museum/", shape="coupe", note="기본 3D는 일반형 문 경첩을 사용하는 간이 모형입니다. 실차 걸윙 도어를 재현하지 않습니다."),
    seed_car("trabant-1957", "트라반트 P50", "Trabant P50", 1957, "DE-E", "승용차", "초기 생산", "동독에서 만들어진 소형차입니다. 초기 생산과 1958년 본격 양산을 구별할 필요가 있습니다.", "https://www.trabant-original.de/otdbx/TDokumente_view.php", shape="sedan"),
    seed_car("mini-1959", "오스틴 세븐·모리스 미니 마이너", "Mini 1959", 1959, "GB", "승용차", "공개", "가로 배치 엔진과 전륜구동으로 공간 효율을 높인 소형차입니다.", "https://www.mini.com/en_MS/home/heritage.html", shape="hatchback"),
    seed_car("porsche-901-1963", "포르쉐 901·초기 911", "Porsche 901", 1963, "DE-W", "스포츠카", "모터쇼 공개", "356의 후속으로 공개된 스포츠카입니다. 901이라는 이름으로 공개되었고 이후 911로 바뀌었습니다.", "https://newsroom.porsche.com/en/press-kits/60-Years-Porsche-911/1.-Generation-Porsche-911-%28Ur-Elfer%29%2C-1963-1973.html", shape="coupe", note="공개 연도와 판매·모델 연도를 동일하게 취급하지 않습니다."),
    seed_car("trabant-601-1964", "트라반트 601", "Trabant 601", 1964, "DE-E", "승용차", "양산 시작", "동독의 대표적 소형차로, 오랫동안 생산된 모델입니다.", "https://www.trabant-original.de/otdbx/TDokumente_view.php", shape="sedan"),
    seed_car("miura-1966", "람보르기니 미우라", "Lamborghini Miura", 1966, "IT", "스포츠카", "공개", "미드십 엔진 배치의 역사에서 중요한 위치를 차지하는 스포츠카입니다.", "https://www.lamborghini.com/en-en/history/miura", shape="coupe"),
    seed_car("pony-coupe-1974", "현대 포니 쿠페 콘셉트", "Hyundai Pony Coupe Concept", 1974, "KR", "콘셉트카", "모터쇼 공개", "토리노 모터쇼에서 공개된 쿠페 콘셉트. 양산 포니와 별도 항목으로 분류합니다.", "https://www.hyundai.com/kr/ko/brand/brandstory/campaigns/n-vision-74", shape="coupe", note="사진은 후대 복원 차량입니다. 1974년 공개 당시의 촬영 사진과 구별합니다."),
    seed_car("pony-1975", "현대 포니", "Hyundai Pony", 1975, "KR", "승용차", "생산 시작", "현대자동차의 초기 고유 모델로, 대한민국 자동차 산업의 성장 과정을 살펴볼 수 있는 차량입니다.", "https://www.hyundai.com/kr/ko/brand/heritage/model/pony-history", shape="hatchback", note="생산 시작 1975년과 국내 판매 시작 1976년을 구분합니다."),
    seed_car("prius-1997", "토요타 프리우스 NHW10", "Toyota Prius first generation", 1997, "JP", "하이브리드", "발표·판매 시작", "초기 양산 하이브리드 승용차. 엔진 출력과 하이브리드 시스템 총출력을 구분해야 합니다.", "https://www.toyota-global.com/company/history_of_toyota/75years/vehicle_lineage/car/id60012360/index.html", specs={"length_mm": 4275, "width_mm": 1695, "height_mm": 1490, "wheelbase_mm": 2550, "mass_kg": 1240, "engine_kw": 43}, shape="sedan", note="43 kW는 가솔린 엔진 출력이며 하이브리드 시스템 총출력이 아닙니다."),
    seed_car("gina-2008", "BMW GINA 라이트 비저너리", "BMW GINA", 2008, "DE", "콘셉트카", "공개", "유연한 외피와 가변 구조를 탐구한 디자인 실험 차량입니다.", "https://www.press.bmwgroup.com/asia/article/detail/T0046590EN/gina-the-bmw-group-design-philosophy-challenging-established-concepts-hazarding-visions", shape="roadster", note="기본 간이 3D는 실제 외피 변형 구조를 재현하지 않습니다."),
    seed_car("leaf-2010", "닛산 리프 1세대", "Nissan Leaf first generation", 2010, "JP", "전기차", "판매 시작", "배터리 전기차의 대중화 과정을 살펴볼 수 있는 해치백입니다.", "https://www.nissan-global.com/EN/HERITAGE_COLLECTION/", shape="hatchback"),
    seed_car("mirai-2014", "토요타 미라이 1세대", "Toyota Mirai first generation", 2014, "JP", "수소전기차", "판매 시작", "수소연료전지로 전기를 만들어 모터를 구동하는 세단입니다.", "https://global.toyota/en/detail/4197769/", specs={"length_mm":4890,"width_mm":1815,"height_mm":1535,"wheelbase_mm":2780,"mass_kg":1850,"power_kw":113,"torque_nm":335}, shape="sedan"),
    seed_car("nvision-2022", "현대 N 비전 74", "Hyundai N Vision 74", 2022, "KR", "실험·콘셉트카", "공개", "수소연료전지와 배터리를 결합한 고성능 롤링랩. 포니 쿠페 콘셉트의 디자인에서 영감을 얻었습니다.", "https://www.hyundai-n.com/en/brand/press/n-day-2022", specs={"length_mm": 4952, "width_mm": 1995, "height_mm": 1331, "wheelbase_mm": 2905}, shape="coupe", note="공식 공개 출력은 500 kW 초과로 제시되어 단일한 실측 출력값으로 저장하지 않았습니다."),
]

# 초기 사진: Commons 파일명·저자·라이선스 확인 시점의 메타데이터. 사진은 원본 서버에서 불러옵니다.
PREPARED_PHOTOS = {'cugnot-1769': {'title': 'File:FardierdeCugnot20050111.jpg',
                 'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/5/56/FardierdeCugnot20050111.jpg/960px-FardierdeCugnot20050111.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
                 'original_url': 'https://upload.wikimedia.org/wikipedia/commons/5/56/FardierdeCugnot20050111.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                 'source': 'https://commons.wikimedia.org/wiki/File:FardierdeCugnot20050111.jpg',
                 'author': 'Roby',
                 'license': 'CC BY-SA 3.0',
                 'license_url': 'http://creativecommons.org/licenses/by-sa/3.0/',
                 'checked': '2026-10-27'},
 'benz-1886': {'title': 'File:Patent-Motorwagen Nr.1 Benz 2.jpg',
               'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/b/b8/Patent-Motorwagen_Nr.1_Benz_2.jpg/960px-Patent-Motorwagen_Nr.1_Benz_2.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
               'original_url': 'https://upload.wikimedia.org/wikipedia/commons/b/b8/Patent-Motorwagen_Nr.1_Benz_2.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
               'source': 'https://commons.wikimedia.org/wiki/File:Patent-Motorwagen_Nr.1_Benz_2.jpg',
               'author': 'DaimlerChrysler AG',
               'license': 'CC BY-SA 3.0',
               'license_url': 'http://creativecommons.org/licenses/by-sa/3.0/',
               'checked': '2026-10-27'},
 'benz-bus-1895': {'title': 'File:Benz Omnibus replica 1895 IMG 0853.jpg',
                   'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/f/f1/Benz_Omnibus_replica_1895_IMG_0853.jpg/960px-Benz_Omnibus_replica_1895_IMG_0853.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
                   'original_url': 'https://upload.wikimedia.org/wikipedia/commons/f/f1/Benz_Omnibus_replica_1895_IMG_0853.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                   'source': 'https://commons.wikimedia.org/wiki/File:Benz_Omnibus_replica_1895_IMG_0853.jpg',
                   'author': 'Alexander Migl',
                   'license': 'CC BY-SA 4.0',
                   'license_url': 'https://creativecommons.org/licenses/by-sa/4.0',
                   'checked': '2026-10-27'},
 'daimler-truck-1896': {'title': 'File:DMG-Lastwagen von 1896.jpg',
                        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/9/90/DMG-Lastwagen_von_1896.jpg/960px-DMG-Lastwagen_von_1896.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
                        'original_url': 'https://upload.wikimedia.org/wikipedia/commons/9/90/DMG-Lastwagen_von_1896.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                        'source': 'https://commons.wikimedia.org/wiki/File:DMG-Lastwagen_von_1896.jpg',
                        'author': 'Martin Dürrschnabel',
                        'license': 'CC BY 3.0',
                        'license_url': 'https://creativecommons.org/licenses/by/3.0',
                        'checked': '2026-10-27'},
 'ford-t-1908': {'title': 'File:Ford T Jon Sullivan.jpg',
                 'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/3/31/Ford_T_Jon_Sullivan.jpg/960px-Ford_T_Jon_Sullivan.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
                 'original_url': 'https://upload.wikimedia.org/wikipedia/commons/3/31/Ford_T_Jon_Sullivan.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                 'source': 'https://commons.wikimedia.org/wiki/File:Ford_T_Jon_Sullivan.jpg',
                 'author': 'Jon Sullivan',
                 'license': 'Public domain',
                 'license_url': '',
                 'checked': '2026-10-27'},
 'traction-1934': {'title': 'File:Traction 11 BL 1950.jpg',
                   'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/c/cd/Traction_11_BL_1950.jpg/960px-Traction_11_BL_1950.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
                   'original_url': 'https://upload.wikimedia.org/wikipedia/commons/c/cd/Traction_11_BL_1950.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                   'source': 'https://commons.wikimedia.org/wiki/File:Traction_11_BL_1950.jpg',
                   'author': 'Palauenc05',
                   'license': 'CC BY-SA 4.0',
                   'license_url': 'https://creativecommons.org/licenses/by-sa/4.0',
                   'checked': '2026-10-27'},
 'vw-kdf-1938': {'title': 'File:Volkswagen Type 1 (1938).jpg',
                 'url': 'https://upload.wikimedia.org/wikipedia/commons/8/8e/Volkswagen_Type_1_%281938%29.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail_unscaled',
                 'original_url': 'https://upload.wikimedia.org/wikipedia/commons/8/8e/Volkswagen_Type_1_%281938%29.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                 'source': 'https://commons.wikimedia.org/wiki/File:Volkswagen_Type_1_(1938).jpg',
                 'author': 'Unknown authorUnknown author',
                 'license': 'Public domain',
                 'license_url': '',
                 'checked': '2026-10-27'},
 'vw-beetle-1945': {'title': 'File:Ivan Hirst and VW Beetle.jpg',
                    'url': 'https://upload.wikimedia.org/wikipedia/commons/a/a4/Ivan_Hirst_and_VW_Beetle.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail_unscaled',
                    'original_url': 'https://upload.wikimedia.org/wikipedia/commons/a/a4/Ivan_Hirst_and_VW_Beetle.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                    'source': 'https://commons.wikimedia.org/wiki/File:Ivan_Hirst_and_VW_Beetle.jpg',
                    'author': 'Ivan Hirst: the story of how he saved the VW Beetle - Heritage Parts Centre',
                    'license': 'Public domain',
                    'license_url': '',
                    'checked': '2026-10-27'},
 'porsche-356-1948': {'title': 'File:Porsche 356 No. 1 Roadster IMG 0814.jpg',
                      'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/e/ec/Porsche_356_No._1_Roadster_IMG_0814.jpg/960px-Porsche_356_No._1_Roadster_IMG_0814.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
                      'original_url': 'https://upload.wikimedia.org/wikipedia/commons/e/ec/Porsche_356_No._1_Roadster_IMG_0814.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                      'source': 'https://commons.wikimedia.org/wiki/File:Porsche_356_No._1_Roadster_IMG_0814.jpg',
                      'author': 'Alexander Migl',
                      'license': 'CC BY-SA 4.0',
                      'license_url': 'https://creativecommons.org/licenses/by-sa/4.0',
                      'checked': '2026-10-27'},
 'citroen-2cv-1948': {'title': 'File:Paris - Bonhams 2013 - Citroën 2CV A - 1950 - 002.jpg',
                      'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/1/1d/Paris_-_Bonhams_2013_-_Citro%C3%ABn_2CV_A_-_1950_-_002.jpg/960px-Paris_-_Bonhams_2013_-_Citro%C3%ABn_2CV_A_-_1950_-_002.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
                      'original_url': 'https://upload.wikimedia.org/wikipedia/commons/1/1d/Paris_-_Bonhams_2013_-_Citro%C3%ABn_2CV_A_-_1950_-_002.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                      'source': 'https://commons.wikimedia.org/wiki/File:Paris_-_Bonhams_2013_-_Citro%C3%ABn_2CV_A_-_1950_-_002.jpg',
                      'author': 'Thesupermat',
                      'license': 'CC BY-SA 3.0',
                      'license_url': 'https://creativecommons.org/licenses/by-sa/3.0',
                      'checked': '2026-10-27'},
 'vw-t1-1950': {'title': 'File:Volkswagen 23 dutch licence registration 47-AP-98 pic2.JPG',
                'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/d/de/Volkswagen_23_dutch_licence_registration_47-AP-98_pic2.JPG/960px-Volkswagen_23_dutch_licence_registration_47-AP-98_pic2.JPG?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
                'original_url': 'https://upload.wikimedia.org/wikipedia/commons/d/de/Volkswagen_23_dutch_licence_registration_47-AP-98_pic2.JPG?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                'source': 'https://commons.wikimedia.org/wiki/File:Volkswagen_23_dutch_licence_registration_47-AP-98_pic2.JPG',
                'author': 'AlfvanBeem',
                'license': 'CC0',
                'license_url': 'http://creativecommons.org/publicdomain/zero/1.0/deed.en',
                'checked': '2026-10-27'},
 'sl-1954': {'title': 'File:Mercedes 300SL grijs Nürburgring 2006 small.jpg',
             'url': 'https://upload.wikimedia.org/wikipedia/commons/5/50/Mercedes_300SL_grijs_N%C3%BCrburgring_2006_small.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail_unscaled',
             'original_url': 'https://upload.wikimedia.org/wikipedia/commons/5/50/Mercedes_300SL_grijs_N%C3%BCrburgring_2006_small.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
             'source': 'https://commons.wikimedia.org/wiki/File:Mercedes_300SL_grijs_N%C3%BCrburgring_2006_small.jpg',
             'author': 'Zefke',
             'license': 'CC BY-SA 3.0',
             'license_url': 'https://creativecommons.org/licenses/by-sa/3.0',
             'checked': '2026-10-27'},
 'trabant-1957': {'title': 'File:Trabant P50 front.jpg',
                  'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/0/03/Trabant_P50_front.jpg/960px-Trabant_P50_front.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
                  'original_url': 'https://upload.wikimedia.org/wikipedia/commons/0/03/Trabant_P50_front.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                  'source': 'https://commons.wikimedia.org/wiki/File:Trabant_P50_front.jpg',
                  'author': 'burts',
                  'license': 'CC BY-SA 3.0',
                  'license_url': 'http://creativecommons.org/licenses/by-sa/3.0/',
                  'checked': '2026-10-27'},
 'mini-1959': {'title': 'File:Morris Mini-Minor 1959 (621 AOK).jpg',
               'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/2/2f/Morris_Mini-Minor_1959_%28621_AOK%29.jpg/960px-Morris_Mini-Minor_1959_%28621_AOK%29.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
               'original_url': 'https://upload.wikimedia.org/wikipedia/commons/2/2f/Morris_Mini-Minor_1959_%28621_AOK%29.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
               'source': 'https://commons.wikimedia.org/wiki/File:Morris_Mini-Minor_1959_(621_AOK).jpg',
               'author': 'DeFacto',
               'license': 'CC BY-SA 2.5',
               'license_url': 'https://creativecommons.org/licenses/by-sa/2.5',
               'checked': '2026-10-27'},
 'porsche-901-1963': {'title': 'File:1964 Porsche 901 rear.jpg',
                      'url': 'https://upload.wikimedia.org/wikipedia/commons/9/9d/1964_Porsche_901_rear.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail_unscaled',
                      'original_url': 'https://upload.wikimedia.org/wikipedia/commons/9/9d/1964_Porsche_901_rear.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                      'source': 'https://commons.wikimedia.org/wiki/File:1964_Porsche_901_rear.jpg',
                      'author': 'Theodulf',
                      'license': 'CC BY-SA 3.0',
                      'license_url': 'https://creativecommons.org/licenses/by-sa/3.0',
                      'checked': '2026-10-27'},
 'trabant-601-1964': {'title': 'File:AWZ Trabant 601S, Verkehrszentrum des Deutschen Museums.JPG',
                      'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/b/b8/AWZ_Trabant_601S%2C_Verkehrszentrum_des_Deutschen_Museums.JPG/960px-AWZ_Trabant_601S%2C_Verkehrszentrum_des_Deutschen_Museums.JPG?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
                      'original_url': 'https://upload.wikimedia.org/wikipedia/commons/b/b8/AWZ_Trabant_601S%2C_Verkehrszentrum_des_Deutschen_Museums.JPG?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                      'source': 'https://commons.wikimedia.org/wiki/File:AWZ_Trabant_601S,_Verkehrszentrum_des_Deutschen_Museums.JPG',
                      'author': 'High Contrast',
                      'license': 'CC BY 3.0 de',
                      'license_url': 'https://creativecommons.org/licenses/by/3.0/de/deed.en',
                      'checked': '2026-10-27'},
 'miura-1966': {'title': 'File:Lamborghini Miura P400 S Classic-Days 2022 DSC 0086.jpg',
                'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/e/ee/Lamborghini_Miura_P400_S_Classic-Days_2022_DSC_0086.jpg/960px-Lamborghini_Miura_P400_S_Classic-Days_2022_DSC_0086.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
                'original_url': 'https://upload.wikimedia.org/wikipedia/commons/e/ee/Lamborghini_Miura_P400_S_Classic-Days_2022_DSC_0086.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                'source': 'https://commons.wikimedia.org/wiki/File:Lamborghini_Miura_P400_S_Classic-Days_2022_DSC_0086.jpg',
                'author': 'Alexander Migl',
                'license': 'CC BY-SA 4.0',
                'license_url': 'https://creativecommons.org/licenses/by-sa/4.0',
                'checked': '2026-10-27'},
 'pony-coupe-1974': {'title': 'File:Hyundai Pony Coupe Concept (6).jpg',
                     'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/f/f4/Hyundai_Pony_Coupe_Concept_%286%29.jpg/960px-Hyundai_Pony_Coupe_Concept_%286%29.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
                     'original_url': 'https://upload.wikimedia.org/wikipedia/commons/f/f4/Hyundai_Pony_Coupe_Concept_%286%29.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                     'source': 'https://commons.wikimedia.org/wiki/File:Hyundai_Pony_Coupe_Concept_(6).jpg',
                     'author': 'Damian B Oh',
                     'license': 'CC BY-SA 4.0',
                     'license_url': 'https://creativecommons.org/licenses/by-sa/4.0',
                     'checked': '2026-10-27'},
 'pony-1975': {'title': 'File:1976-1982 Hyundai Pony front.jpg',
               'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/e/ea/1976-1982_Hyundai_Pony_front.jpg/960px-1976-1982_Hyundai_Pony_front.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
               'original_url': 'https://upload.wikimedia.org/wikipedia/commons/e/ea/1976-1982_Hyundai_Pony_front.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
               'source': 'https://commons.wikimedia.org/wiki/File:1976-1982_Hyundai_Pony_front.jpg',
               'author': '원문: 자작(Self-made) · 업로더 Sim1992',
               'license': 'CC BY-SA 4.0',
               'license_url': 'https://creativecommons.org/licenses/by-sa/4.0',
               'checked': '2026-10-27'},
 'prius-1997': {'title': 'File:TOYOTA Prius.jpg',
                'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/7/7a/TOYOTA_Prius.jpg/960px-TOYOTA_Prius.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
                'original_url': 'https://upload.wikimedia.org/wikipedia/commons/7/7a/TOYOTA_Prius.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                'source': 'https://commons.wikimedia.org/wiki/File:TOYOTA_Prius.jpg',
                'author': 'Gnsin',
                'license': 'CC BY-SA 3.0',
                'license_url': 'http://creativecommons.org/licenses/by-sa/3.0/',
                'checked': '2026-10-27'},
 'gina-2008': {'title': 'File:BMW Gina Museum.jpg',
               'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/c/c3/BMW_Gina_Museum.jpg/960px-BMW_Gina_Museum.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
               'original_url': 'https://upload.wikimedia.org/wikipedia/commons/c/c3/BMW_Gina_Museum.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
               'source': 'https://commons.wikimedia.org/wiki/File:BMW_Gina_Museum.jpg',
               'author': 'ravas51',
               'license': 'CC BY-SA 2.0',
               'license_url': 'https://creativecommons.org/licenses/by-sa/2.0',
               'checked': '2026-10-27'},
 'leaf-2010': {'title': 'File:2011 Nissan Leaf SL -- 10-28-2011.jpg',
               'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/7/77/2011_Nissan_Leaf_SL_--_10-28-2011.jpg/960px-2011_Nissan_Leaf_SL_--_10-28-2011.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
               'original_url': 'https://upload.wikimedia.org/wikipedia/commons/7/77/2011_Nissan_Leaf_SL_--_10-28-2011.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
               'source': 'https://commons.wikimedia.org/wiki/File:2011_Nissan_Leaf_SL_--_10-28-2011.jpg',
               'author': 'IFCAR',
               'license': 'Public domain',
               'license_url': '',
               'checked': '2026-10-27'},
 'mirai-2014': {'title': 'File:Toyota MIRAI (JPD10) front.JPG',
                'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/8/86/Toyota_MIRAI_%28JPD10%29_front.JPG/960px-Toyota_MIRAI_%28JPD10%29_front.JPG?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
                'original_url': 'https://upload.wikimedia.org/wikipedia/commons/8/86/Toyota_MIRAI_%28JPD10%29_front.JPG?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                'source': 'https://commons.wikimedia.org/wiki/File:Toyota_MIRAI_(JPD10)_front.JPG',
                'author': 'Tokumeigakarinoaoshima',
                'license': 'CC0',
                'license_url': 'http://creativecommons.org/publicdomain/zero/1.0/deed.en',
                'checked': '2026-10-27'},
 'nvision-2022': {'title': 'File:2022 Hyundai N Vision 74 FOS23.jpg',
                  'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/0/08/2022_Hyundai_N_Vision_74_FOS23.jpg/960px-2022_Hyundai_N_Vision_74_FOS23.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
                  'original_url': 'https://upload.wikimedia.org/wikipedia/commons/0/08/2022_Hyundai_N_Vision_74_FOS23.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                  'source': 'https://commons.wikimedia.org/wiki/File:2022_Hyundai_N_Vision_74_FOS23.jpg',
                  'author': 'MrWalkr',
                  'license': 'CC BY-SA 4.0',
                  'license_url': 'https://creativecommons.org/licenses/by-sa/4.0',
                  'checked': '2026-10-27'},
 'firebird-1954': {'title': 'File:Firebird I in Motion expo.jpg',
                   'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/1/18/Firebird_I_in_Motion_expo.jpg/960px-Firebird_I_in_Motion_expo.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail',
                   'original_url': 'https://upload.wikimedia.org/wikipedia/commons/1/18/Firebird_I_in_Motion_expo.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original',
                   'source': 'https://commons.wikimedia.org/wiki/File:Firebird_I_in_Motion_expo.jpg',
                   'author': 'Luistxo',
                   'license': 'CC BY-SA 4.0',
                   'license_url': 'https://creativecommons.org/licenses/by-sa/4.0',
                   'checked': '2026-10-27'}}
for _photo in PREPARED_PHOTOS.values():
    _photo["license_url"] = _photo["license_url"] or _photo["source"]
for _car in CATALOG:
    if _car["id"] in PREPARED_PHOTOS:
        _car["photo_title"] = PREPARED_PHOTOS[_car["id"]]["title"]

SPEC_LABELS = {
    "length_mm": ("전장", "mm"), "width_mm": ("전폭", "mm"), "height_mm": ("전고", "mm"),
    "wheelbase_mm": ("축거", "mm"), "mass_kg": ("공차질량", "kg"), "power_kw": ("구동계 최고출력", "kW"),
    "engine_kw": ("엔진 최고출력", "kW"), "torque_nm": ("최대토크", "N·m"),
    "top_speed_kmh": ("공식 최고속도", "km/h"), "zero100_s": ("공식 0→100 km/h", "초"),
    "payload_kg": ("적재량", "kg"), "battery_kwh": ("배터리 용량", "kWh"),
}

BODY_TYPES = {"sedan": "세단", "coupe": "쿠페", "hatchback": "해치백", "suv": "SUV", "roadster": "로드스터", "van": "밴", "bus": "버스", "truck": "트럭", "vintage": "초기 자동차", "steam": "증기 실험차"}
ENGINES = {
    "전기모터 100 kW": {"mass": 85., "power": 100., "torque": 230., "rpm": 12000., "type": "ev"},
    "전기모터 200 kW": {"mass": 115., "power": 200., "torque": 400., "rpm": 16000., "type": "ev"},
    "가솔린 I4 110 kW": {"mass": 145., "power": 110., "torque": 220., "rpm": 6500., "type": "ice"},
    "가솔린 V6 220 kW": {"mass": 215., "power": 220., "torque": 400., "rpm": 7000., "type": "ice"},
    "디젤 180 kW": {"mass": 340., "power": 180., "torque": 800., "rpm": 4000., "type": "diesel"},
}
BRAKES = {"일반 디스크": {"mass": 48., "torque": 5200.}, "대형 디스크": {"mass": 62., "torque": 7600.}, "고성능 디스크": {"mass": 52., "torque": 10000.}}
TIRES = {"일반 도로 타이어": {"mu": .85, "crr": .012}, "저구름저항 타이어": {"mu": .75, "crr": .009}, "스포츠 타이어": {"mu": 1.05, "crr": .015}}
DEFAULT_DESIGN = dict(name="나의 첫 AUTOVERSE", body="coupe", length=4.5, width=1.85,
    height=1.35, wheelbase=2.65, wheel_radius=.33, cabin=.49, nose=.24,
    color="#d6b76d", rim="#c6cbd5", spoiler=True, engine="전기모터 200 kW",
    brake="일반 디스크", tire="일반 도로 타이어", drive="후륜", suspension="더블 위시본",
    battery_kwh=60., battery_density=170., body_mass=650., occupant_mass=75.,
    fuel_liters=0., cd=.29, area_factor=.85, efficiency=.90,
    gear_launch=9., gear_top=9., power_kw=200., torque_nm=400., max_rpm=16000.,
    brake_torque=5200., mu=.85, crr=.012, reaction=1., slope=0.,
    positions={"engine": [.27, .48, 0.], "battery": [0., .30, 0.], "gearbox": [.10, .44, 0.], "tank": [-.30, .45, 0.]})

def secret_value(name, default=""):
    try:
        return st.secrets.get(name, default)
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return os.environ.get(name, default)

def get_json(url, *, params=None, timeout=12, headers=None):
    r = requests.get(url, params=params, headers={**HTTP_HEADERS, **(headers or {})}, timeout=(5, timeout))
    r.raise_for_status()
    if len(r.content) > 25 * 1024 * 1024:
        raise ValueError("자료가 허용 크기를 초과했습니다.")
    return r.json()

def safe_https(url):
    try:
        p = urlparse(str(url))
        return p.scheme == "https" and bool(p.hostname) and not p.username
    except ValueError:
        return False

def country_name(cid):
    if cid.startswith("MAP:"):
        return cid[4:].title()
    return COUNTRIES.get(cid, {}).get("ko", cid)

def historical_country(cid, year):
    if cid == "DE":
        if 1933 <= year <= 1945:
            return "독일 · 나치 집권기" if year < 1945 else "독일 · 전후 점령기"
        if 1871 <= year < 1919:
            return "독일 제국"
        if 1919 <= year < 1933:
            return "독일 · 바이마르 공화국"
        if 1946 <= year < 1949:
            return "독일 · 전후 점령기"
    if cid == "FR" and year < 1789:
        return "프랑스 왕국"
    return country_name(cid)

def country_for_feature(name, snapshot_year):
    n = str(name or "").strip().lower()
    if n.startswith("germany (") and snapshot_year == 1945:
        return "DE"
    for cid, meta in COUNTRIES.items():
        if n in meta["aliases"]:
            return cid
    return "MAP:" + n if n else ""

def vehicle_matches_country(car, cid):
    # 과거 국가 ID를 보존하며 1945년 점령 구역을 서독·동독으로 부르지 않습니다.
    return car["country"] == cid

@st.cache_data(ttl=86400, show_spinner=False, max_entries=32)
def load_historical_map(year):
    local = ROOT / "maps" / f"world_{year}.geojson"
    if local.is_file():
        return json.loads(local.read_text(encoding="utf-8")), year, "추가한 연도별 지도", ""
    try:
        index = basemap_index()
        candidates = [e for e in index["years"] if 1700 <= int(e["year"]) <= year]
        if not candidates:
            raise ValueError("선택 연도 이전의 지도 파일이 없습니다.")
        entry = max(candidates, key=lambda e: int(e["year"]))
        filename = str(entry["filename"])
        if not re.fullmatch(r"world_\d{4}\.geojson", filename):
            raise ValueError("지원하지 않는 지도 파일명입니다.")
        data = basemap_snapshot(filename)
        return data, int(entry["year"]), "historical-basemaps", ""
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        return None, None, "", f"지도 경계를 불러오지 못했습니다 ({type(e).__name__}). 국가 선택 목록은 계속 사용할 수 있습니다."

@st.cache_data(ttl=86400, show_spinner=False)
def basemap_index():
    return get_json(BASEMAP_RAW + "index.json")

@st.cache_data(ttl=604800, show_spinner=False, max_entries=20)
def basemap_snapshot(filename):
    return get_json(BASEMAP_RAW + "geojson/" + filename)

def map_payload(geojson, snapshot_year, counts, selected):
    if not geojson:
        return {"type": "FeatureCollection", "features": []}
    features = []
    for f in geojson.get("features", []):
        props = f.get("properties") or {}
        n = str(props.get("NAME") or props.get("name") or props.get("ADMIN") or "")
        if not n:
            continue
        cid = country_for_feature(n, snapshot_year)
        count = counts.get(cid, 0)
        features.append(dict(type="Feature", geometry=f.get("geometry"), properties=dict(
            name=n, ko=country_name(cid) if not cid.startswith("MAP:") else n,
            cid=cid, count=count, selected=cid == selected)))
    return dict(type="FeatureCollection", features=features)

def clean_text(value):
    return html.unescape(re.sub(r"<[^>]*>", "", str(value or ""))).strip()

@st.cache_data(ttl=86400, show_spinner=False, max_entries=160)
def commons_photo(title="", query=""):
    """파일별 저자·라이선스를 확인한 경우에만 표시. 검색 결과는 실차/연식 검증을 대체하지 않음."""
    endpoint = "https://commons.wikimedia.org/w/api.php"
    try:
        if not title and query:
            found = get_json(endpoint, params=dict(action="query", format="json", list="search",
                srsearch=query + " filetype:bitmap", srnamespace=6, srlimit=4), timeout=10)
            candidates = [x["title"] for x in found.get("query", {}).get("search", [])]
            if not candidates:
                return {"error": "등록된 사진을 찾지 못했습니다."}
            title = candidates[0]
        if not title:
            return {"error": "사진 자료가 없습니다."}
        if not title.startswith("File:"):
            title = "File:" + title
        data = get_json(endpoint, params=dict(action="query", format="json", titles=title,
            prop="imageinfo", iiprop="url|extmetadata", iiurlwidth=1100), timeout=10)
        page = next(iter(data.get("query", {}).get("pages", {}).values()), {})
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        license_name = clean_text(meta.get("LicenseShortName", {}).get("value"))
        license_url = meta.get("LicenseUrl", {}).get("value", "")
        author = clean_text(meta.get("Artist", {}).get("value"))
        url = info.get("thumburl") or info.get("url", "")
        allowed = any(x in license_name.lower() for x in ["cc by", "cc0", "public domain", "pdm"])
        if not allowed or not author or not safe_https(url):
            return {"error": "이 파일의 재사용 조건·저자를 자동 확인하지 못했습니다. 원문에서 확인해 주세요.", "source": info.get("descriptionurl", "")}
        return dict(url=url, title=page.get("title", title), author=author, license=license_name,
                    license_url=license_url, source=info.get("descriptionurl", ""))
    except (requests.RequestException, ValueError, KeyError, StopIteration) as e:
        return {"error": f"사진 서버에 연결하지 못했습니다 ({type(e).__name__})."}

@st.cache_data(ttl=86400, show_spinner=False, max_entries=120)
def image_bytes(url):
    # 사진 다운로드 실패 시 안내를 표시하고 나머지 화면은 유지합니다.
    if not safe_https(url) or urlparse(url).hostname not in {"upload.wikimedia.org", "thumb.wikimedia.org", "commons.wikimedia.org"}:
        return None
    try:
        r = requests.get(url, headers=HTTP_HEADERS, timeout=(5, 10))
        r.raise_for_status()
        return r.content if len(r.content) < 8 * 1024 * 1024 and r.headers.get("Content-Type", "").startswith("image/") else None
    except requests.RequestException:
        return None

@st.cache_data(ttl=3600, show_spinner=False, max_entries=20)
def wikidata_cars(year):
    # P571은 성립·도입 시점이며 현지 출시 연도와 다를 수 있습니다.
    # 공개 DB의 불균일한 분류로 누락이 있으므로 전체 조회로 표시하지 않습니다.
    query = f'''SELECT DISTINCT ?item ?itemLabel ?itemDescription ?country ?countryLabel ?iso ?makerLabel ?image ?date WHERE {{
      {{ SELECT DISTINCT ?item ?date WHERE {{
          ?item wdt:P571 ?date .
          FILTER(?date >= "{int(year)}-01-01T00:00:00Z"^^xsd:dateTime && ?date < "{int(year)+1}-01-01T00:00:00Z"^^xsd:dateTime)
          VALUES ?root {{ wd:Q3231690 wd:Q1420 wd:Q5638 wd:Q43193 }}
          ?item wdt:P31/wdt:P279* ?root .
      }} LIMIT 160 }}
      OPTIONAL {{ ?item wdt:P495 ?country . OPTIONAL {{ ?country wdt:P297 ?iso }} }}
      OPTIONAL {{ ?item wdt:P176 ?maker . }}
      OPTIONAL {{ ?item wdt:P18 ?image . }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "ko,en". }}
    }} LIMIT 240'''
    query = "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n" + query
    data = get_json("https://query.wikidata.org/sparql", params={"query": query, "format": "json"},
                    headers={"Accept": "application/sparql-results+json"}, timeout=25)
    out = {}
    for row in data.get("results", {}).get("bindings", []):
        val = lambda k: row.get(k, {}).get("value", "")
        qid = val("item").rsplit("/", 1)[-1]
        iso = val("iso")
        cid = {"GB": "GB", "DD": "DE-E", "SU": "SU"}.get(iso, iso)
        if cid not in COUNTRIES:
            cid = country_for_feature(val("countryLabel"), year)
        if not cid or cid.startswith("MAP:"):
            cid = "미분류"
        if cid == "DE" and 1949 <= year <= 1989:
            cid = "미분류"  # 제조사 소재지를 확인하지 않고 동·서독을 추정하지 않습니다.
        car = seed_car("wd-" + qid, val("itemLabel") or qid, val("itemLabel"), year, cid,
            "공개 DB·검토 필요", "Wikidata P571", val("itemDescription") or "공개 DB에 등록된 차량 항목입니다. 원문에서 모델·연도·국가를 확인해 주세요.",
            "https://www.wikidata.org/wiki/" + qid)
        if val("image"):
            from urllib.parse import unquote
            car["photo_title"] = unquote(val("image").rsplit("/", 1)[-1])
        car["source_kind"] = "Wikidata CC0 · 항목 검토 필요"
        car["note"] = "P571은 출시일이 아닐 수 있습니다. 원산국(P495)이 없는 항목은 미분류로 표시합니다. 모델별 모든 버전을 포함하지 않습니다."
        out.setdefault(car["id"], car)
    return list(out.values())

def validate_car(raw):
    if not isinstance(raw, dict):
        raise ValueError("차량 항목은 JSON 객체여야 합니다.")
    for field in ["id", "name", "country", "source"]:
        if not isinstance(raw.get(field), str) or not 1 <= len(raw[field]) <= 2000:
            raise ValueError(f"차량의 {field} 필드를 확인해 주세요.")
    year = raw.get("year")
    if isinstance(year, bool) or not isinstance(year, int) or not 1700 <= year <= CURRENT_YEAR:
        raise ValueError("차량 연도는 1700년부터 올해까지의 정수여야 합니다.")
    if not safe_https(raw["source"]):
        raise ValueError("출처는 HTTPS 원문 주소를 입력해 주세요.")
    car = seed_car(raw["id"], raw["name"], str(raw.get("name_en", raw["name"])), year,
        raw["country"], str(raw.get("kind", "추가 차량")), str(raw.get("event", "등록 자료")),
        str(raw.get("description", ""))[:5000], raw["source"], shape=raw.get("shape", "sedan"),
        note=str(raw.get("note", ""))[:2000], photo=str(raw.get("photo_title", ""))[:300])
    for k, v in raw.get("specs", {}).items():
        if k in SPEC_LABELS and isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0:
            car["specs"][k] = v
    for k in ["model_url", "model_license", "model_source", "model_author"]:
        car[k] = str(raw.get(k, ""))[:2000]
    if car["model_url"] and not (safe_https(car["model_url"]) and safe_https(car["model_source"]) and car["model_license"] and car["model_author"]):
        raise ValueError("GLB를 등록하려면 HTTPS 모델 주소·원문·라이선스·제작자가 모두 필요합니다.")
    car["source_kind"] = "사용자 추가 자료"
    return car

def all_cars():
    merged = {v["id"]: copy.deepcopy(v) for v in CATALOG}
    local = ROOT / "vehicles.json"
    errors = []
    if local.is_file():
        try:
            data = json.loads(local.read_text(encoding="utf-8"))
            if not isinstance(data, list) or len(data) > 5000:
                raise ValueError("vehicles.json은 최대 5,000개 항목의 목록이어야 합니다.")
            for v in data:
                car = validate_car(v)
                merged[car["id"]] = car
        except (ValueError, OSError, TypeError, AttributeError) as e:
            errors.append(str(e))
    for v in st.session_state.get("extra_cars", []) + st.session_state.get("online_cars", []):
        merged.setdefault(v["id"], copy.deepcopy(v))
    return sorted(merged.values(), key=lambda v: (v["year"], v["country"], v["name"])), errors

def normalize_design(raw):
    if not isinstance(raw, dict):
        raise ValueError("설계 데이터 형식이 잘못되었습니다.")
    d = copy.deepcopy(DEFAULT_DESIGN)
    limits = dict(length=(2., 14.), width=(1.2, 2.6), height=(.9, 4.), wheel_radius=(.20, .65),
        cabin=(.28, .74), nose=(.12, .38), body_mass=(150., 15000.), occupant_mass=(0., 6000.),
        battery_kwh=(0., 400.), battery_density=(80., 300.), fuel_liters=(0., 400.),
        cd=(.15, 1.2), area_factor=(.65, 1.), efficiency=(.5, .98), gear_launch=(2., 25.),
        gear_top=(1., 20.), power_kw=(1., 1500.), torque_nm=(10., 5000.), max_rpm=(2000., 25000.),
        brake_torque=(1000., 60000.), mu=(.15, 1.3), crr=(.005, .04), reaction=(0., 3.), slope=(-10., 20.))
    for k, (lo, hi) in limits.items():
        value = raw.get(k, d[k])
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{k} 값은 유한한 숫자여야 합니다.")
        d[k] = min(hi, max(lo, float(value)))
    wb = raw.get("wheelbase", d["wheelbase"])
    if not isinstance(wb, (int, float)) or isinstance(wb, bool) or not math.isfinite(wb):
        raise ValueError("축거 값이 잘못되었습니다.")
    d["wheelbase"] = min(d["length"] * .80, max(d["length"] * .45, float(wb)))
    for k, choices in [("body", BODY_TYPES), ("engine", ENGINES), ("brake", BRAKES), ("tire", TIRES),
                       ("drive", ["전륜", "후륜", "사륜"]), ("suspension", ["맥퍼슨", "더블 위시본", "리프 스프링"])]:
        if raw.get(k, d[k]) not in choices:
            raise ValueError(f"지원하지 않는 {k} 선택입니다.")
        d[k] = raw.get(k, d[k])
    for k in ["color", "rim"]:
        value = raw.get(k, d[k])
        if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("색상은 #RRGGBB 형식이어야 합니다.")
        d[k] = value
    d["name"] = str(raw.get("name", d["name"])).strip()[:80] or "이름 없는 설계"
    d["spoiler"] = bool(raw.get("spoiler", d["spoiler"]))
    p = raw.get("positions", d["positions"])
    if not isinstance(p, dict):
        raise ValueError("부품 위치 데이터가 잘못되었습니다.")
    for part in d["positions"]:
        pos = p.get(part, d["positions"][part])
        if not isinstance(pos, list) or len(pos) != 3 or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in pos):
            raise ValueError("부품 위치는 x, y, z 숫자 세 개로 입력합니다.")
        d["positions"][part] = [min(.42, max(-.42, pos[0])), min(d["height"]*.72, max(.15, pos[1])), min(.35, max(-.35, pos[2]))]
    return d

def component_masses(d):
    e = ENGINES[d["engine"]]
    transmission = 28. if e["type"] == "ev" else 75.
    battery = d["battery_kwh"] * 1000. / d["battery_density"]
    fuel = d["fuel_liters"] * (.835 if e["type"] == "diesel" else .745)
    return dict(body=d["body_mass"], engine=e["mass"], battery=battery, gearbox=transmission,
                tank=fuel + (12. if d["fuel_liters"] else 0.), brakes=BRAKES[d["brake"]]["mass"],
                wheels=4 * (12. + 24. * d["wheel_radius"]), spoiler=8. if d["spoiler"] else 0., occupant=d["occupant_mass"])

def performance(design):
    """종방향 교육 모델. 정적 축하중, 일정 Cd·마찰, 토크·출력 포락선을 사용합니다."""
    d = normalize_design(design)
    masses = component_masses(d)
    m = sum(masses.values())
    cg = sum(masses[k] * d["positions"][k][0] * d["length"] for k in d["positions"]) / m
    front = min(.95, max(.05, .5 + cg / d["wheelbase"]))
    driven = front if d["drive"] == "전륜" else 1.-front if d["drive"] == "후륜" else 1.
    area = d["area_factor"] * d["width"] * d["height"]
    slope = math.atan(d["slope"] / 100.)
    pw = d["power_kw"] * 1000. * d["efficiency"]
    torque_force = d["torque_nm"] * d["gear_launch"] * d["efficiency"] / d["wheel_radius"]
    grip_force = d["mu"] * m * 9.80665 * math.cos(slope) * driven
    rpm_speed = d["max_rpm"] / d["gear_top"] * 2.*math.pi*d["wheel_radius"] / 60.
    def resistance(v):
        return .5 * 1.225 * d["cd"] * area * v*v + d["crr"] * m * 9.80665 * math.cos(slope) + m * 9.80665 * math.sin(slope)
    def net(v):
        return min(torque_force, grip_force, pw/max(v, .2)) - resistance(v)
    if net(0) <= 0:
        vmax = 0.
    else:
        lo, hi = 0., max(1., min(160., rpm_speed))
        for _ in range(65):
            mid = (lo+hi)/2.
            if net(mid) > 0:
                lo = mid
            else:
                hi = mid
        vmax = min((lo+hi)/2., rpm_speed)
    v, t, hit = 0., 0., None
    trace = [(0., 0.)]
    dt = .04
    for i in range(3000):
        a = net(v)/m if v < rpm_speed else min(0., net(v)/m)
        vn = max(0., min(rpm_speed, v + a*dt))
        if hit is None and vn >= 100/3.6 > v:
            hit = t + dt*((100/3.6-v)/max(vn-v, 1e-9))
        t += dt
        v = vn
        if i % 5 == 0:
            trace.append((round(t, 2), v*3.6))
        if t > 15 and abs(a) < .004:
            break
    brake_a = min(d["mu"] * 9.80665 * math.cos(slope), d["brake_torque"]/(m*d["wheel_radius"])) + 9.80665*math.sin(slope)
    stopping = (100/3.6)**2/(2*brake_a) if brake_a > .01 else None
    return dict(mass=m, masses=masses, area=area, cg_x=cg, front_fraction=front,
                power_wheel_kw=pw/1000, vmax=vmax*3.6, zero100=hit, brake_distance=stopping,
                reaction_distance=100/3.6*d["reaction"], trace=trace,
                power_curve=[(s, max(0., resistance(s/3.6)*(s/3.6)/1000.)) for s in range(0, 301, 5)])

def bounded_decompress(payload, maximum=80000):
    dec = zlib.decompressobj()
    out = dec.decompress(payload, maximum + 1)
    if len(out) > maximum or dec.unconsumed_tail or not dec.eof:
        raise ValueError("설계 데이터의 압축 크기가 허용 범위를 넘었습니다.")
    return out

def make_portable_code(design):
    doc = dict(schema=SCHEMA_VERSION, created=datetime.now(timezone.utc).isoformat(), design=normalize_design(design))
    key, nonce = secrets.token_bytes(32), secrets.token_bytes(12)
    data = zlib.compress(json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    encrypted = AESGCM(key).encrypt(nonce, data, b"AUTOVERSE-1")
    return "AV1." + base64.urlsafe_b64encode(key+nonce+encrypted).decode().rstrip("=")

def restore_portable_code(code):
    code = code.strip()
    if not code.startswith("AV1.") or len(code) > MAX_CODE_CHARS:
        raise ValueError("AV1.로 시작하는 설계 코드 전체를 입력해 주세요.")
    if not re.fullmatch(r"AV1\.[A-Za-z0-9_-]+", code):
        raise ValueError("설계 코드에 지원하지 않는 문자가 있습니다.")
    try:
        payload = base64.urlsafe_b64decode(code[4:] + "="*(-len(code[4:])%4))
        if len(payload) < 60:
            raise ValueError("코드가 너무 짧습니다.")
        data = AESGCM(payload[:32]).decrypt(payload[32:44], payload[44:], b"AUTOVERSE-1")
        doc = json.loads(bounded_decompress(data))
        if doc.get("schema") != SCHEMA_VERSION:
            raise ValueError("지원하지 않는 설계 코드 버전입니다.")
        return normalize_design(doc["design"])
    except (InvalidTag, ValueError, KeyError, TypeError, zlib.error) as e:
        raise ValueError("코드가 손상되었거나 지원하지 않는 설계입니다. 전체 코드를 다시 확인해 주세요.") from e

def database_config():
    url = secret_value("SUPABASE_URL")
    key = secret_value("SUPABASE_SECRET_KEY") or secret_value("SUPABASE_SERVICE_ROLE_KEY")
    return (url.rstrip("/"), key) if url and key and safe_https(url) else None

def database_headers(api_key):
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    # 새 sb_secret 키는 JWT가 아니므로 Authorization: Bearer에 넣지 않습니다.
    if api_key.startswith("eyJ"):
        headers["Authorization"] = "Bearer "+api_key
    return headers

def save_short_code(design):
    config = database_config()
    if not config:
        raise ValueError("짧은 코드를 사용하려면 Supabase Secrets 설정이 필요합니다.")
    code = "AVS." + secrets.token_urlsafe(24)
    lookup = hashlib.sha256(code.encode()).hexdigest()
    key = hashlib.sha256((code+":encryption-v1").encode()).digest()
    nonce = secrets.token_bytes(12)
    data = json.dumps(dict(schema=SCHEMA_VERSION, design=normalize_design(design)), ensure_ascii=False).encode()
    cipher = base64.urlsafe_b64encode(nonce+AESGCM(key).encrypt(nonce, data, b"AUTOVERSE-DB1")).decode()
    url, api_key = config
    response = requests.post(url+"/rest/v1/autoverse_designs", headers={**database_headers(api_key), "Prefer": "return=minimal"},
        json={"id": lookup, "payload": cipher}, timeout=(5, 15))
    response.raise_for_status()
    return code

def restore_short_code(code):
    config = database_config()
    if not config:
        raise ValueError("이 앱에는 짧은 코드 저장소가 연결되지 않았습니다. AV1. 휴대용 코드나 설계 파일을 사용해 주세요.")
    if not re.fullmatch(r"AVS\.[A-Za-z0-9_-]{32}", code):
        raise ValueError("짧은 설계 코드 형식이 올바르지 않습니다.")
    url, api_key = config
    lookup = hashlib.sha256(code.encode()).hexdigest()
    response = requests.get(url+"/rest/v1/autoverse_designs", params={"id": "eq."+lookup, "select": "payload", "limit": 1},
        headers=database_headers(api_key), timeout=(5, 15))
    response.raise_for_status()
    rows = response.json()
    if not rows:
        raise ValueError("저장된 설계를 찾지 못했습니다.")
    try:
        payload = base64.urlsafe_b64decode(rows[0]["payload"])
        key = hashlib.sha256((code+":encryption-v1").encode()).digest()
        doc = json.loads(AESGCM(key).decrypt(payload[:12], payload[12:], b"AUTOVERSE-DB1"))
        if doc.get("schema") != 1:
            raise ValueError("지원하지 않는 설계입니다.")
        return normalize_design(doc["design"])
    except (ValueError, KeyError, InvalidTag, TypeError) as e:
        raise ValueError("설계 코드를 해독하지 못했습니다.") from e

def validate_glb(blob):
    if len(blob) > MAX_MODEL_BYTES or len(blob) < 20:
        raise ValueError("GLB는 최대 15 MB이며 올바른 GLB 2.0 파일이어야 합니다.")
    magic, version, size = struct.unpack_from("<4sII", blob)
    if magic != b"glTF" or version != 2 or size != len(blob):
        raise ValueError("GLB 2.0 헤더가 올바르지 않습니다.")
    json_len, json_type = struct.unpack_from("<II", blob, 12)
    if json_type != 0x4E4F534A or json_len > len(blob)-20:
        raise ValueError("GLB JSON 청크가 올바르지 않습니다.")
    try:
        document = json.loads(blob[20:20+json_len].decode("utf-8").rstrip("\x00 "))
    except (UnicodeDecodeError, ValueError) as e:
        raise ValueError("GLB 설명 데이터를 읽지 못했습니다.") from e
    for collection in ["buffers", "images"]:
        for resource in document.get(collection, []):
            uri = resource.get("uri", "")
            if uri and not uri.startswith("data:"):
                raise ValueError("외부 리소스가 있는 GLB는 지원하지 않습니다. 텍스처를 포함해 하나의 GLB로 내보내 주세요.")
    return document


APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');
:root{--ink:#e8e9ee;--muted:#9aa2b4;--gold:#d9bb78;--line:#29303e;--panel:#121721}
.stApp{background:radial-gradient(ellipse at 76% 0%,#1c2331 0%,#0b1018 45%);color:var(--ink);font-family:'DM Sans','Noto Sans KR',sans-serif}
[data-testid="stHeader"]{background:transparent} .block-container{max-width:1500px;padding-top:2rem;padding-bottom:4rem}
[data-testid="stSidebar"]{background:#0c111a;border-right:1px solid var(--line)}
h1,h2,h3{font-family:'DM Sans','Noto Sans KR',sans-serif;letter-spacing:-.035em;color:#edf0f5}
.brand{font-size:25px;font-weight:800;letter-spacing:.19em;color:#f2e4c5}.brand small{font-size:10px;letter-spacing:.18em;color:#8d99ae;display:block;margin-top:4px}
.eyebrow{font-size:11px;letter-spacing:.24em;color:#d9bb78;font-weight:700;margin:12px 0}
.hero-title{font-size:clamp(44px,5.3vw,78px);font-weight:700;line-height:1.05;letter-spacing:-.06em;margin:12px 0 24px;color:#f4f1e9}
.hero-title em{font-style:normal;color:#d9bb78}.hero-copy{color:#a9b2c4;font-size:16px;line-height:1.9;max-width:540px}
.tag{display:inline-block;border:1px solid #41404a;border-radius:30px;padding:4px 12px;font-size:11px;color:#ddcba4;margin:3px 5px 3px 0}
.fine{font-size:12px;color:#8f9bb0;line-height:1.8}.section-number{color:#d2b16c;font-size:11px;letter-spacing:.22em;margin:12px 0}
.nation-banner{position:relative;overflow:hidden;border:1px solid #454252;border-radius:16px;padding:26px 30px;margin:12px 0 24px;min-height:110px;background:#151c29}
.nation-banner h2{position:relative;margin:5px 0;color:#faf3e2;font-size:30px}.nation-banner p{position:relative;color:#c3ccdb;margin:0}
.nation-banner img{position:absolute;right:0;top:0;width:220px;height:160px;object-fit:cover;opacity:.19;transform:rotate(-12deg) scale(1.25)}
.nation-band{position:absolute;inset:0;opacity:.20}.card-meta{font-size:12px;color:#b7a077;letter-spacing:.02em;margin:3px 0 10px}
.car-placeholder{height:160px;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#202a39,#101722);border-radius:10px;color:#8d9db6;font-size:13px;border:1px solid #263245}
.stButton>button{border:1px solid #3c4659;background:#181f2c;color:#e9eaf0;border-radius:9px;min-height:43px;font-weight:600;transition:.18s}
.stButton>button:hover{border-color:#d5b575;color:#e4c58b;background:#232734}
.stButton>button[kind="primary"]{background:#d9bb78;color:#16181d;border-color:#d9bb78}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:14px;border-color:#2b3343;background:#10172155}
[data-testid="stMetricValue"]{color:#e6cf9c;font-size:28px}[data-testid="stMetricLabel"]{color:#aab5c7}
[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input,[data-baseweb="select"]>div,[data-testid="stTextArea"] textarea{background:#121a28;color:#e9edf5;border-color:#374052}
[data-testid="stCaptionContainer"]{color:#9ba9bf}hr{border-color:#303847}
.stApp [data-testid="stWidgetLabel"] p,.stApp [data-testid="stExpander"] summary p,.stApp [role="tab"],.stApp [data-testid="stCheckbox"] label p{color:#c9d4e5}
div[data-testid="stDataFrame"]{border:1px solid #303949;border-radius:10px}
.note-box{border-left:2px solid #d9bb78;background:#1c2230;padding:14px 18px;border-radius:0 9px 9px 0;font-size:13px;color:#c4ccdc;line-height:1.85}
@media(max-width:700px){.block-container{padding-top:1rem;padding-left:1rem;padding-right:1rem}.nation-banner{padding:18px}.hero-title{font-size:42px}}
</style>
"""

TIMELINE_CSS = """
:host{display:block}*{box-sizing:border-box}.timeline{font-family:'Noto Sans KR',sans-serif;color:#ccd5e5;background:#111823;border:1px solid #303a4e;border-radius:12px;padding:13px 10px}
.row{display:flex;gap:8px;align-items:center}.track{display:flex;overflow:auto;scroll-behavior:smooth;scrollbar-color:#655c48 #16202c;gap:3px;padding:8px 3px;flex:1}
button{background:#182231;color:#9caac0;border:1px solid transparent;border-radius:7px;cursor:pointer;min-width:54px;height:49px;position:relative;font-size:12px}
button:hover{border-color:#9a8556}button.active{color:#151820;background:#dcc182;font-weight:800}.dot{display:block;margin:5px auto 0;width:4px;height:4px;background:#d9bb78;border-radius:50%}.active .dot{background:#1b2028}
.arrow{min-width:30px;font-size:22px}.legend{font-size:10px;letter-spacing:.10em;color:#8798b1;margin:0 6px}
"""
TIMELINE_JS = r"""
export default function({parentElement,data,setTriggerValue}) {
  const root=parentElement.querySelector('.timeline');
  root.innerHTML='<div class="row"><button class="arrow prev" aria-label="이전 연도들">‹</button><div class="track" role="group" aria-label="가로 연표"></div><button class="arrow next" aria-label="다음 연도들">›</button></div><div class="legend">가로 스크롤 · 좌우 화살표 · 점은 등록 차량이 있는 연도</div>';
  const track=root.querySelector('.track'), has=new Set(data.years);
  for(let y=data.start;y<=data.end;y++) {
    const b=document.createElement('button');b.textContent=y;b.title=`${y}년 선택`;
    if(y===data.year){b.className='active';b.setAttribute('aria-pressed','true');}
    if(has.has(y)){const dot=document.createElement('span');dot.className='dot';b.append(dot);}
    b.onclick=()=>setTriggerValue('picked',y);track.append(b);
  }
  root.querySelector('.prev').onclick=()=>track.scrollBy({left:-380,behavior:'smooth'});
  root.querySelector('.next').onclick=()=>track.scrollBy({left:380,behavior:'smooth'});
  const wheel=e=>{if(Math.abs(e.deltaY)>Math.abs(e.deltaX)){track.scrollLeft+=e.deltaY;e.preventDefault();}};
  track.addEventListener('wheel',wheel,{passive:false});
  const frame=requestAnimationFrame(()=>{const b=track.querySelector('.active');if(b)track.scrollLeft=b.offsetLeft-track.offsetLeft-track.clientWidth/2+b.clientWidth/2;});
  return()=>{cancelAnimationFrame(frame);track.removeEventListener('wheel',wheel);};
}
"""

MAP_CSS = """
:host{display:block}*{box-sizing:border-box}.map-root{position:relative;background:radial-gradient(ellipse at 50% 35%,#182538,#0c141f);border:1px solid #2d394e;border-radius:15px;overflow:hidden;min-height:440px;font-family:'Noto Sans KR',sans-serif;color:#c5cfde}
svg{display:block;width:100%;height:440px}.map-tip{position:absolute;top:14px;left:18px;background:#0b131ee6;border:1px solid #445066;border-radius:7px;padding:8px 12px;font-size:12px;pointer-events:none}
.map-controls{position:absolute;right:12px;bottom:16px;display:flex;gap:4px}.map-controls button{background:#142133;border:1px solid #48556d;color:#e9dfc5;border-radius:5px;width:34px;height:32px;cursor:pointer;font-size:18px}
.map-foot{position:absolute;bottom:12px;left:16px;font-size:10px;color:#8d9db5;pointer-events:none}.map-error{padding:70px 24px;line-height:1.9}
path.country{cursor:pointer;transition:fill .12s}path.country:focus{outline:none;stroke:#fcf2be;stroke-width:1.5px}
"""
MAP_JS = r"""
export default function({parentElement,data,setTriggerValue}) {
 const root=parentElement.querySelector('.map-root');let disposed=false,cleanup=()=>{};
 root.innerHTML='<div class="map-tip">지도를 불러오는 중…</div><div class="map-foot">노랑: 현재 목록에 차량 있음 · 회색: 등록 자료 없음 · 휠: 확대/축소</div><div class="map-controls"><button class="zin" aria-label="확대">+</button><button class="zout" aria-label="축소">−</button><button class="reset" aria-label="초기화">↺</button></div>';
 async function boot(){
  const d3=await import('https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm');if(disposed)return;
  const w=Math.max(320,root.clientWidth),h=440,svg=d3.select(root).insert('svg',':first-child').attr('viewBox',`0 0 ${w} ${h}`).attr('role','group').attr('aria-label','자동차 역사지도');
  const projection=d3.geoEqualEarth().fitExtent([[16,12],[w-16,h-30]],{type:'Sphere'}),path=d3.geoPath(projection);
  const defs=svg.append('defs');const glow=defs.append('filter').attr('id','avglow');glow.append('feGaussianBlur').attr('stdDeviation',2.5);
  const g=svg.append('g'),tip=root.querySelector('.map-tip');
  g.append('path').datum(d3.geoGraticule10()).attr('d',path).attr('fill','none').attr('stroke','#25354b').attr('stroke-width',.35);
  const paths=g.selectAll('.country').data(data.geo.features).join('path').attr('class','country').attr('d',path)
    .attr('fill',d=>d.properties.selected?'#f5db96':d.properties.count?'#bd9a46':'#3b4657')
    .attr('stroke',d=>d.properties.count?'#e3c674':'#71829b').attr('stroke-width',d=>d.properties.count?.7:.28)
    .attr('tabindex',0).attr('aria-label',d=>`${d.properties.ko}, ${d.properties.count}개 등록`);
  paths.attr('role','button');
  g.selectAll('.halo').data(data.geo.features.filter(f=>f.properties.count)).join('path').attr('d',path).attr('fill','none').attr('stroke','#eaca74').attr('stroke-width',2).attr('opacity',.3).attr('filter','url(#avglow)').attr('pointer-events','none');
  const choose=d=>setTriggerValue('picked',{cid:d.properties.cid,name:d.properties.name});
  paths.on('mouseenter',function(e,d){tip.textContent=`${d.properties.ko} · ${d.properties.name} · ${d.properties.count}대 등록`;d3.select(this).attr('fill','#ebd18a');})
    .on('mouseleave',function(e,d){d3.select(this).attr('fill',d.properties.selected?'#f5db96':d.properties.count?'#bd9a46':'#3b4657');})
    .on('click',(e,d)=>{if(!e.defaultPrevented)choose(d);}).on('keydown',(e,d)=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose(d);}});
  const represented=new Set(data.geo.features.map(f=>f.properties.cid));
  const points=data.points.filter(p=>!represented.has(p.cid));
  g.selectAll('.fallback-point').data(points).join('circle').attr('cx',d=>projection(d.point)[0]).attr('cy',d=>projection(d.point)[1]).attr('r',5).attr('fill','#e4c477').attr('stroke','#fff0be').attr('stroke-width',1).style('cursor','pointer')
    .on('mouseenter',(e,d)=>{tip.textContent=`${d.ko} · ${d.count}대 등록 · 위치 표식(해당 국가 경계 미확보)`;})
    .on('click',(e,d)=>setTriggerValue('picked',{cid:d.cid,name:d.ko}));
  const zoom=d3.zoom().scaleExtent([1,12]).on('zoom',e=>g.attr('transform',e.transform));svg.call(zoom).on('dblclick.zoom',null);
  root.querySelector('.zin').onclick=()=>svg.transition().call(zoom.scaleBy,1.5);root.querySelector('.zout').onclick=()=>svg.transition().call(zoom.scaleBy,.67);root.querySelector('.reset').onclick=()=>svg.transition().call(zoom.transform,d3.zoomIdentity);
  tip.textContent=data.geo.features.length?`선택 ${data.year}년 · 지도 ${data.snapshot}년 · 나라를 눌러 주세요`:'경계 자료 없음 · 국가 위치 표식이나 아래 목록을 선택해 주세요';
  cleanup=()=>{svg.on('.zoom',null);svg.remove();};
 }
 boot().catch(e=>{if(!disposed){root.querySelector('.map-tip').textContent='지도 라이브러리 로딩 실패 · 아래 국가 목록으로 선택해 주세요';}});
 return()=>{disposed=true;cleanup();};
}
"""

VIEWER_CSS = """
:host{display:block}*{box-sizing:border-box}.viewer{position:relative;height:510px;border:1px solid #364052;border-radius:16px;overflow:hidden;background:radial-gradient(ellipse at 50% 35%,#303849,#111824 70%);color:#d7dfeb;font-family:'Noto Sans KR',sans-serif}
.viewport{position:absolute;inset:0}.viewport canvas,.viewport>svg{display:block;width:100%;height:100%;touch-action:none}.vtop{position:absolute;top:16px;left:18px;right:18px;display:flex;align-items:start;justify-content:space-between;gap:12px;pointer-events:none}
.vtitle{font-size:12px;letter-spacing:.08em;color:#e4c98b;background:#101724b0;padding:7px 10px;border:1px solid #424455;border-radius:6px;max-width:70%}.vstatus{position:absolute;left:16px;right:16px;bottom:52px;font-size:11px;color:#ccd7e9;background:#101723b5;padding:7px 10px;border-radius:6px;pointer-events:none;line-height:1.6}
.vtools{position:absolute;bottom:12px;left:14px;right:14px;display:flex;gap:5px;flex-wrap:wrap}.vtools button,.vtools select{font-size:11px;color:#dce3ef;background:#182337ee;border:1px solid #4a5265;border-radius:6px;min-height:30px;padding:4px 9px;cursor:pointer}.vtools button:hover{border-color:#d7ba7e}.vtools button.active{background:#7c6740;color:white}
.error{padding:80px 24px;line-height:1.9;color:#d6c8ad}.spinner{position:absolute;left:0;right:0;top:45%;text-align:center;color:#a8b8cf;font-size:13px;pointer-events:none}
"""

VIEWER_JS = r"""
export default function({parentElement,data,setTriggerValue}) {
 const root=parentElement.querySelector('.viewer');let disposed=false,cleanup=()=>{};
 root.innerHTML='<div class="viewport"></div><div class="spinner">3D 스튜디오를 준비하는 중…</div><div class="vtop"><span class="vtitle"></span></div><div class="vstatus"></div><div class="vtools"><button data-action="reset">시점 초기화</button><button data-action="rotate">자동 회전</button><button data-action="open">문·트렁크 열기</button><button data-action="xray">차체 반투명</button><button data-action="dims">치수</button><select aria-label="이동할 부품"><option value="">부품 이동 선택</option><option value="engine">엔진·모터</option><option value="battery">배터리</option><option value="gearbox">변속기</option><option value="tank">연료 탱크</option></select><button data-action="anim" hidden>GLB 애니메이션</button></div>';
 root.querySelector('.vtitle').textContent=data.label||'AUTOVERSE · PARAMETRIC STUDIO';
 const status=root.querySelector('.vstatus');
 const timer=setTimeout(()=>{if(!disposed)status.textContent='3D 로딩이 지연되고 있습니다. 네트워크의 esm.sh 접근과 WebGL 사용 여부를 확인해 주세요.';},15000);
 async function boot(){
  const [THREE,{OrbitControls},{TransformControls},{GLTFLoader}]=await Promise.all([
   import('https://esm.sh/three@0.160.1'),
   import('https://esm.sh/three@0.160.1/examples/jsm/controls/OrbitControls.js'),
   import('https://esm.sh/three@0.160.1/examples/jsm/controls/TransformControls.js'),
   import('https://esm.sh/three@0.160.1/examples/jsm/loaders/GLTFLoader.js')]);
  if(disposed)return;clearTimeout(timer);
  const host=root.querySelector('.viewport');let renderer,software=false;
  try{renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'high-performance'});}
  catch(e){const {SVGRenderer}=await import('https://esm.sh/three@0.160.1/examples/jsm/renderers/SVGRenderer.js');if(disposed)return;renderer=new SVGRenderer();renderer.setQuality('low');software=true;}
  renderer.setPixelRatio?.(Math.min(devicePixelRatio,2));renderer.setSize(host.clientWidth,host.clientHeight);if(renderer.shadowMap){renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;}
  renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.25;host.append(renderer.domElement);
  const scene=new THREE.Scene();scene.background=new THREE.Color(data.workshop?'#1a1c20':'#171f2c');
  scene.fog=new THREE.Fog(scene.background,18,42);
  const camera=new THREE.PerspectiveCamera(38,host.clientWidth/host.clientHeight,.05,150);
  const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.maxPolarAngle=Math.PI*.49;controls.minDistance=2;controls.maxDistance=40;
  controls.mouseButtons.RIGHT=null;controls.autoRotateSpeed=.65;
  const hemi=new THREE.HemisphereLight('#d9e9ff','#423b31',2.5);scene.add(hemi);
  const key=new THREE.DirectionalLight('#fff3dc',4);key.position.set(5,9,4);key.castShadow=true;key.shadow.mapSize.set(2048,2048);key.shadow.camera.left=-12;key.shadow.camera.right=12;key.shadow.camera.top=12;key.shadow.camera.bottom=-12;scene.add(key);
  const rimLight=new THREE.DirectionalLight('#8aafff',2.5);rimLight.position.set(-6,4,-4);scene.add(rimLight);
  const ground=new THREE.Mesh(new THREE.PlaneGeometry(100,100),new THREE.MeshStandardMaterial({color:data.workshop?'#363433':'#272e3b',roughness:.8,metalness:.15}));ground.rotation.x=-Math.PI/2;ground.receiveShadow=true;ground.position.y=-.015;scene.add(ground);
  const grid=new THREE.GridHelper(40,40,'#6a6555','#39404b');grid.position.y=.002;grid.material.transparent=true;grid.material.opacity=.22;scene.add(grid);
  const d=data.design,L=d.length,W=d.width,H=d.height,R=d.wheel_radius,WB=d.wheelbase;
  const car=new THREE.Group();scene.add(car);const panels=[],parts={},paintMeshes=[],wheels=[];let opening=false,ghost=false,dimVisible=false,mixer=null,animations=[],playing=false;
  const paint=new THREE.MeshPhysicalMaterial({color:d.color,metalness:.62,roughness:.26,clearcoat:1,clearcoatRoughness:.2});
  const trim=new THREE.MeshStandardMaterial({color:'#242832',metalness:.4,roughness:.55});
  const glass=new THREE.MeshPhysicalMaterial({color:'#34465a',metalness:.4,roughness:.18,transparent:true,opacity:.70,side:THREE.DoubleSide});
  const rubber=new THREE.MeshStandardMaterial({color:'#111317',roughness:.85});
  const rim=new THREE.MeshStandardMaterial({color:d.rim,metalness:.9,roughness:.24});
  const mat=(color,metal=.25)=>new THREE.MeshStandardMaterial({color,metalness:metal,roughness:.55});
  function box(parent,x,y,z,sx,sy,sz,material){const mesh=new THREE.Mesh(new THREE.BoxGeometry(Math.max(.01,sx),Math.max(.01,sy),Math.max(.01,sz)),material);mesh.position.set(x,y,z);mesh.castShadow=true;mesh.receiveShadow=true;parent.add(mesh);if(material===paint)paintMeshes.push(mesh);return mesh;}
  function profile(parent,points,depth,material,z=0){const shape=new THREE.Shape();points.forEach((p,i)=>i?shape.lineTo(p[0],p[1]):shape.moveTo(p[0],p[1]));shape.closePath();const geo=new THREE.ExtrudeGeometry(shape,{depth,bevelEnabled:true,bevelThickness:.025,bevelSize:.025,bevelSegments:2,steps:1});geo.translate(0,0,-depth/2);const mesh=new THREE.Mesh(geo,material);mesh.position.z=z;mesh.castShadow=true;parent.add(mesh);if(material===paint)paintMeshes.push(mesh);return mesh;}
  function cylinder(parent,r1,r2,depth,material,x,y,z){const m=new THREE.Mesh(new THREE.CylinderGeometry(r1,r2,depth,32),material);m.rotation.x=Math.PI/2;m.position.set(x,y,z);m.castShadow=true;parent.add(m);return m;}
  function lamp(x,y,z,red=false){return box(car,x,y,z,.065,.08,W*.22,new THREE.MeshStandardMaterial({color:red?'#b22430':'#f0ecb6',emissive:red?'#8b1729':'#f6eccc',emissiveIntensity:1.2}));}
  function hinge(name,x,y,z,axis,angle){const g=new THREE.Group();g.name=name;g.position.set(x,y,z);g.userData={panel:true,axis,angle,target:0};car.add(g);panels.push(g);return g;}
  function wheel(x,z){const g=new THREE.Group();car.add(g);g.position.set(x,R,z);cylinder(g,R,R,.20,rubber,0,0,0);cylinder(g,R*.67,R*.67,.215,rim,0,0,0);cylinder(g,R*.47,R*.47,.224,mat('#51555b',.8),0,0,0);for(let k=0;k<6;k++){const spoke=box(g,0,0,0,R*1.18,.035,.236,rim);spoke.rotation.z=k*Math.PI/6;}cylinder(g,R*.17,R*.17,.245,trim,0,0,0);box(g,.10,.03,z>0?.14:-.14,.09,R*.58,.08,mat('#b13c32'));wheels.push(g);}
  function makePart(name,size,color){const g=new THREE.Group();g.name=name;const p=d.positions[name];g.position.set(p[0]*L,p[1],p[2]*W);const body=box(g,0,0,0,...size,mat(color,.5));body.userData.part=name;car.add(g);parts[name]=g;for(let j=0;j<3;j++)box(g,0,size[1]*.53,(j-1)*size[2]*.25,size[0]*.85,.015,.028,trim);return g;}
  function makeProcedural(){
   const tall=['suv','van','bus','truck'].includes(d.body),vintage=['steam','vintage'].includes(d.body),open=d.body==='roadster'||vintage;
   const lower=Math.max(R*1.15,H*(tall?.39:.40)),cabinLen=L*d.cabin,frontCab=L*(d.nose-.04),backCab=frontCab-cabinLen;
   box(car,0,R*.85,0,L*.91,.18,W*.82,trim);
   const lowerPoints=[[-L*.49,R*.95],[-L*.49,lower*.86],[-L*.37,lower*1.1],[L*.35,lower*1.12],[L*.49,lower*.88],[L*.49,R*.95]];
   profile(car,lowerPoints,W*.94,paint);
   box(car,0,lower*.65,0,L*.60,.15,W*.74,trim);
   const noseLen=Math.max(.15,L*.49-frontCab),rearLen=Math.max(.15,backCab+L*.49);
   box(car,frontCab+noseLen*.5,lower,0,noseLen,.26,W*.95,paint);
   box(car,-L*.49+rearLen*.5,lower,0,rearLen,.25,W*.95,paint);
   const cabinBase=lower+.12,top=H-.05;
   if(!open){
    box(car,(frontCab+backCab)*.5,top,0,cabinLen*.68,.08,W*.86,paint);
    for(const z of [-W*.43,W*.43]){
     const pillarFront=box(car,frontCab-.11,(cabinBase+top)*.5,z,.07,top-cabinBase,.07,paint);pillarFront.rotation.z=.24;
     box(car,backCab+.1,(cabinBase+top)*.5,z,.07,top-cabinBase,.07,paint);
    }
    const windshield=box(car,frontCab-.15,(top+cabinBase)*.5,0,.025,top-cabinBase-.05,W*.85,glass);windshield.rotation.z=.25;
    box(car,backCab+.08,(top+cabinBase)*.5,0,.025,top-cabinBase-.08,W*.83,glass);
   }
   const doorCount=d.body==='sedan'||d.body==='suv'||d.body==='hatchback'?2:1;
   for(const side of [-1,1])for(let i=0;i<doorCount;i++){
    const dl=cabinLen/doorCount,front=frontCab-i*dl;
    const door=hinge(`door-${side}-${i}`,front,cabinBase,side*W*.48,'y',-side*1.05);
    box(door,-dl*.5,-.11,0,dl*.94,.36,.045,paint);
    if(!open){profile(door,[[-dl*.96,.08],[-dl*.92,top-cabinBase-.06],[-dl*.12,top-cabinBase-.06],[-.04,.08]],.018,glass);box(door,-dl*.53,top-cabinBase-.05,0,dl*.83,.035,.045,paint);}
    box(door,-dl*.78,.04,side*.03,.12,.025,.02,rim);
   }
   for(const x of [backCab+cabinLen*.30,frontCab-.28])for(const z of [-W*.22,W*.22]){
    box(car,x,cabinBase+.02,z,.35,.12,W*.27,trim);const seat=box(car,x-.13,cabinBase+.23,z,.09,.43,W*.28,trim);seat.rotation.z=-.12;
   }
   box(car,frontCab-.20,cabinBase+.10,0,.16,.18,W*.80,trim);
   const sw=new THREE.Mesh(new THREE.TorusGeometry(.15,.018,10,28),trim);sw.rotation.y=Math.PI/2;sw.position.set(frontCab-.4,cabinBase+.26,W*.23);car.add(sw);
   const trunk=hinge('trunk',backCab,lower+.16,0,'z',-.70);box(trunk,-rearLen*.45,.025,0,rearLen*.87,.055,W*.91,paint);
   const hood=hinge('hood',frontCab,lower+.16,0,'z',.72);box(hood,noseLen*.43,.025,0,noseLen*.83,.055,W*.91,paint);
   for(const x of [-WB/2,WB/2])for(const side of [-1,1])wheel(x,side*(W*.5-.055));
   for(const side of [-1,1]){lamp(L*.495,lower+.07,side*W*.30);lamp(-L*.495,lower+.07,side*W*.30,true);box(car,frontCab-.1,cabinBase+.12,side*W*.57,.18,.08,.12,paint);}
   box(car,L*.498,lower-.08,0,.02,.14,W*.35,trim);box(car,-L*.499,lower-.08,0,.02,.10,W*.23,trim);
   if(d.spoiler){for(const z of [-W*.30,W*.30])box(car,-L*.40,lower+.35,z,.06,.35,.06,trim);box(car,-L*.42,lower+.53,0,.30,.055,W*.93,paint);}
   if(d.body==='truck'){box(car,-L*.24,lower+.23,0,L*.43,.12,W*.9,trim);for(const side of [-1,1])box(car,-L*.24,lower+.40,side*W*.46,L*.44,.44,.045,paint);}
   if(d.body==='bus'||d.body==='van'){
    box(car,-L*.21,(H+lower)*.5,0,L*.44,H-lower,W*.9,paint);
    for(const side of [-1,1])for(let i=0;i<(d.body==='bus'?5:2);i++)box(car,-L*.40+i*L*.075,H*.77,side*W*.459,L*.064,H*.25,.018,glass);
   }
   if(d.body==='steam'){const boiler=new THREE.Mesh(new THREE.SphereGeometry(W*.30,24,18),mat('#5d655b',.7));boiler.position.set(L*.35,H*.65,0);car.add(boiler);box(car,L*.30,H*.78,0,.09,H*.38,.09,trim);}
   makePart('engine',[Math.min(.65,L*.17),.34,W*.36],'#cb7f46');
   makePart('battery',[Math.min(1.6,L*.38),.16,W*.62],'#58788b').visible=d.battery_kwh>0;
   makePart('gearbox',[.32,.24,.32],'#a2a3a7');makePart('tank',[.42,.20,W*.35],'#8d9a63').visible=d.fuel_liters>0;
  }
  if(data.glb){
   try{
    const bytes=Uint8Array.from(atob(data.glb),c=>c.charCodeAt(0));
    const asset=await new Promise((resolve,reject)=>new GLTFLoader().parse(bytes.buffer,'',resolve,reject));
    if(disposed){asset.scene.traverse(o=>{if(o.geometry)o.geometry.dispose();});return;}
    const bounds=new THREE.Box3().setFromObject(asset.scene),size=bounds.getSize(new THREE.Vector3()),center=bounds.getCenter(new THREE.Vector3());
    const s=4.5/Math.max(size.x,size.z,.01);asset.scene.scale.setScalar(s);asset.scene.position.set(-center.x*s,-bounds.min.y*s,-center.z*s);
    asset.scene.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});car.add(asset.scene);
    if(asset.animations.length){mixer=new THREE.AnimationMixer(asset.scene);animations=asset.animations;root.querySelector('[data-action="anim"]').hidden=false;}
    status.textContent='등록 GLB · 드래그 회전 / 휠 확대 · 문 조작은 원본에 door·trunk·hood 애니메이션이 있을 때 지원';
   }catch(e){status.textContent='GLB 읽기 실패 · 압축·외부 텍스처 여부를 확인해 주세요. 간이 모형으로 표시합니다.';makeProcedural();}
   root.querySelector('select').hidden=true;root.querySelector('[data-action="dims"]').hidden=true;
  }else{makeProcedural();status.textContent='치수 기반 간이 3D · 실차 복원 아님 · 좌클릭 드래그: 회전 / 휠: 확대 / 문·트렁크 우클릭: 열기';}
  if(!data.editable)root.querySelector('select').hidden=true;
  if(data.workshop){
   const wallmat=mat('#3a3937');box(scene,0,3.5,-8,24,7,.12,wallmat);
   for(let x=-10;x<12;x+=3){box(scene,x,3.5,-7.9,.10,7,.20,mat('#706047'));box(scene,x,6.7,0,.08,.12,16,mat('#6e6256'));}
   for(const x of [-6,6]){box(scene,x,1.1,-5.5,2.4,.14,1.,mat('#726047'));for(const z of [-5.9,-5.1])for(const dx of [-.9,.9])box(scene,x+dx,.55,z,.08,1.1,.08,trim);for(let k=0;k<4;k++)box(scene,x-.7+k*.5,1.3,-5.5,.25,.32,.3,mat(['#856b44','#5b6b71','#7a4740','#b7a68a'][k]));}
   const tubeMat=new THREE.MeshStandardMaterial({color:'#fff0cb',emissive:'#fff0cb',emissiveIntensity:3});for(const z of [-4,0,4])box(scene,0,6,z,5,.035,.12,tubeMat);
  }
  const dimensions=new THREE.Group();scene.add(dimensions);dimensions.visible=false;
  const points=[new THREE.Vector3(-L/2,.04,W*.7),new THREE.Vector3(L/2,.04,W*.7),new THREE.Vector3(L/2,.04,-W*.7)];
  dimensions.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:'#eed29b'})));
  function label(text,x,y,z){const cv=document.createElement('canvas');cv.width=384;cv.height=80;const ctx=cv.getContext('2d');ctx.fillStyle='#151d2ccc';ctx.fillRect(0,0,384,80);ctx.fillStyle='#f1d698';ctx.font='36px sans-serif';ctx.textAlign='center';ctx.fillText(text,192,53);const texture=new THREE.CanvasTexture(cv),sp=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,depthTest:false}));sp.scale.set(1.3,.27,1);sp.position.set(x,y,z);dimensions.add(sp);}
  label(`L ${L.toFixed(2)} m`,0,.16,W*.75);label(`W ${W.toFixed(2)} m`,L*.58,.16,0);label(`H ${H.toFixed(2)} m`,-L*.58,H*.65,0);
  function reset(){const l=data.glb?4.5:L;camera.position.set(l*.95,Math.max(2.4,H*1.6),l*1.10);controls.target.set(0,Math.min(H*.5,1.4),0);controls.update();}
  reset();
  const transform=new TransformControls(camera,renderer.domElement);transform.setMode('translate');transform.setTranslationSnap(.05);scene.add(transform.getHelper?transform.getHelper():transform);
  if(software){ground.visible=false;hemi.intensity=.8;key.intensity=.8;rimLight.intensity=.35;scene.traverse(o=>{if(o.isMesh&&o.material){const convert=m=>{const n=new THREE.MeshLambertMaterial({color:m.color||'#9099aa',transparent:m.transparent,opacity:m.opacity,side:m.side,visible:m.visible,depthTest:m.depthTest,depthWrite:m.depthWrite});if(m===paint)paintMeshes.push(o);return n;};o.material=Array.isArray(o.material)?o.material.map(convert):convert(o.material);}});status.textContent+=' · WebGL 미지원: CPU 3D 모드';}
  transform.addEventListener('dragging-changed',e=>{controls.enabled=!e.value;});
  transform.addEventListener('mouseUp',()=>{if(!transform.object)return;const changed={};for(const [k,p] of Object.entries(parts)){p.position.x=Math.max(-L*.42,Math.min(L*.42,p.position.x));p.position.y=Math.max(.15,Math.min(H*.72,p.position.y));p.position.z=Math.max(-W*.35,Math.min(W*.35,p.position.z));changed[k]=[p.position.x/L,p.position.y,p.position.z/W];}setTriggerValue('layout',changed);});
  root.querySelector('select').onchange=e=>{const p=parts[e.target.value];if(p&&p.visible){transform.attach(p);status.textContent='화살표 축을 드래그해 이동 · 놓으면 설계와 무게중심 계산에 반영됩니다.';}else transform.detach();};
  function togglePanel(g){g.userData.target=g.userData.target?0:g.userData.angle;status.textContent=`${g.name}: ${g.userData.target?'열기':'닫기'} · 간이 3D 개폐` ;}
  const ray=new THREE.Raycaster(),pointer=new THREE.Vector2();
  function context(e){e.preventDefault();if(transform.dragging)return;const rect=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);ray.setFromCamera(pointer,camera);const hits=ray.intersectObject(car,true);if(!hits.length)return;let obj=hits[0].object;for(let p=obj;p;p=p.parent){if(p.userData.panel){togglePanel(p);return;}}
   if(mixer){const names=[];for(let p=obj;p;p=p.parent)names.push(p.name);const clip=animations.find(c=>/door|trunk|boot|hood|bonnet/i.test(c.name)&&c.tracks.some(t=>names.some(n=>n&&t.name.startsWith(n+'.'))));if(clip){const action=mixer.clipAction(clip);action.setLoop(THREE.LoopOnce,1);action.clampWhenFinished=true;action.reset().play();return;}}
   status.textContent=data.glb?'이 부분에는 인식 가능한 개폐 애니메이션이 없습니다.':'문·트렁크·보닛 표면을 우클릭해 주세요.';
  }
  renderer.domElement.addEventListener('contextmenu',context);
  const buttons=root.querySelectorAll('[data-action]');buttons.forEach(b=>b.onclick=()=>{
   const a=b.dataset.action;
   if(a==='reset')reset();
   if(a==='rotate'){controls.autoRotate=!controls.autoRotate;b.classList.toggle('active',controls.autoRotate);}
   if(a==='open'){opening=!opening;panels.forEach(p=>p.userData.target=opening?p.userData.angle:0);b.textContent=opening?'문·트렁크 닫기':'문·트렁크 열기';b.classList.toggle('active',opening);if(!panels.length)status.textContent='등록 GLB의 문 조작은 원본 애니메이션이 필요합니다.';}
   if(a==='xray'){ghost=!ghost;paint.transparent=ghost;paint.opacity=ghost?.18:1.;paint.depthWrite=!ghost;if(software)for(const o of new Set(paintMeshes)){o.material.transparent=ghost;o.material.opacity=ghost?.18:1.;o.material.depthWrite=!ghost;}b.classList.toggle('active',ghost);if(data.glb)status.textContent='등록 GLB에는 차체 재질 식별 정보가 없어 반투명 전환을 적용하지 않습니다.';}
   if(a==='dims'){dimVisible=!dimVisible;dimensions.visible=dimVisible;b.classList.toggle('active',dimVisible);if(software&&dimVisible)status.textContent=`표시 치수: 전장 ${L.toFixed(2)} m / 전폭 ${W.toFixed(2)} m / 전고 ${H.toFixed(2)} m · CPU 3D`;}
   if(a==='anim'&&mixer){playing=!playing;animations.forEach(c=>{const action=mixer.clipAction(c);if(playing){action.reset().play();}else action.stop();});b.classList.toggle('active',playing);}
  });
  const resize=new ResizeObserver(()=>{const w=host.clientWidth,h=host.clientHeight;if(w&&h){renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();}});resize.observe(host);
  const clock=new THREE.Clock();let frame,lastRender=0;
  const tick=(now=0)=>{if(disposed)return;const dt=Math.min(clock.getDelta(),.05);for(const p of panels){const axis=p.userData.axis;p.rotation[axis]+= (p.userData.target-p.rotation[axis])*Math.min(1,dt*8);}if(mixer)mixer.update(dt);controls.update();if(!software||now-lastRender>100){renderer.render(scene,camera);lastRender=now;}frame=requestAnimationFrame(tick);};tick();
  root.querySelector('.spinner').remove();
  cleanup=()=>{cancelAnimationFrame(frame);resize.disconnect();controls.dispose();transform.dispose();renderer.domElement.removeEventListener('contextmenu',context);scene.traverse(o=>{if(o.geometry)o.geometry.dispose();if(o.material){for(const m of Array.isArray(o.material)?o.material:[o.material]){if(m.map)m.map.dispose();m.dispose();}}});renderer.dispose?.();renderer.forceContextLoss?.();renderer.domElement.remove();};
 }
 boot().catch(e=>{clearTimeout(timer);if(!disposed){root.querySelector('.spinner')?.remove();status.textContent='3D를 시작하지 못했습니다. WebGL 또는 esm.sh 접근을 확인해 주세요. 설계·제원·저장은 계속 사용할 수 있습니다.';}});
 return()=>{disposed=true;clearTimeout(timer);cleanup();};
}
"""

@st.cache_resource
def custom_components():
    return (
        st.components.v2.component("autoverse_timeline_v1", html='<div class="timeline"></div>', css=TIMELINE_CSS, js=TIMELINE_JS),
        st.components.v2.component("autoverse_map_v1", html='<div class="map-root"></div>', css=MAP_CSS, js=MAP_JS),
        st.components.v2.component("autoverse_viewer_v1", html='<div class="viewer"></div>', css=VIEWER_CSS, js=VIEWER_JS),
    )


def initialize():
    defaults = dict(page="home", year=2022, era="현대 · 1945년부터", selected_country="KR",
                    selected_car=None, design=copy.deepcopy(DEFAULT_DESIGN), design_revision=0,
                    saved_designs=[], favorites=[], extra_cars=[], online_cars=[], pending_photo=False)
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def navigate(page):
    st.session_state.page = page

def set_year(year):
    year = max(1700, min(CURRENT_YEAR, int(year)))
    st.session_state.year = year
    st.session_state.era = "현대 · 1945년부터" if year >= 1945 else "근대 · 1700–1944년"
    st.session_state.year_input = year
    st.session_state.selected_car = None

def sync_year_input():
    set_year(st.session_state.year_input)

def sync_era():
    if st.session_state.era.startswith("현대") and st.session_state.year < 1945:
        set_year(1945)
    if st.session_state.era.startswith("근대") and st.session_state.year >= 1945:
        set_year(1886)

def install_design(design):
    st.session_state.design = normalize_design(design)
    st.session_state.design_revision += 1
    st.session_state.pop("last_saved_code", None)

def header():
    a, b, c, d = st.columns([4, 1.5, 1.5, 1.5], vertical_alignment="center")
    with a:
        st.markdown('<div class="brand">AUTO<span style="color:#b7c0d2">VERSE</span><small>EXPLORE · UNDERSTAND · CREATE</small></div>', unsafe_allow_html=True)
    b.button("홈", width="stretch", on_click=navigate, args=("home",), key="nav_home")
    c.button("World Garage", width="stretch", on_click=navigate, args=("garage",), key="nav_garage")
    d.button("Design Lab", width="stretch", on_click=navigate, args=("lab",), key="nav_lab")
    st.divider()

def render_viewer(design, *, label="", key="viewer", workshop=False, editable=False, glb=""):
    viewer = custom_components()[2]
    result = viewer(data=dict(design=design, label=label, workshop=workshop, editable=editable, glb=glb),
                    key=key, on_layout_change=lambda: None)
    if editable and result.layout:
        new = copy.deepcopy(st.session_state.design)
        new["positions"] = result.layout
        try:
            new = normalize_design(new)
            if new["positions"] != st.session_state.design["positions"]:
                install_design(new)
                st.rerun()
        except ValueError as e:
            st.warning(str(e))

def home_page(cars):
    left, right = st.columns([.9, 1.25], gap="large", vertical_alignment="center")
    with left:
        st.markdown('<div class="eyebrow">THE AUTOMOTIVE ENGINEERING ATLAS</div><div class="hero-title">자동차의 시간을<br>탐색하고,<br><em>다음을 설계하다.</em></div>', unsafe_allow_html=True)
        st.markdown('<p class="hero-copy">1700년대 증기 실험차부터 전기차와 콘셉트카까지.<br>세계지도에서 시작해 나만의 작은 설계실로 이어지는 자동차 탐구.</p>', unsafe_allow_html=True)
        st.markdown('<span class="tag">HISTORICAL ATLAS</span><span class="tag">INTERACTIVE 3D</span><span class="tag">ENGINEERING LAB</span>', unsafe_allow_html=True)
        st.caption(f"초기 차량 {len(CATALOG)}개 · 현재 목록 {len(cars)}개 · 추가 자료와 모델로 확장")
    with right:
        render_viewer(DEFAULT_DESIGN, key="home_3d", label="AUTOVERSE / STUDIO 001 · 간이 3D")
    st.markdown('<div class="section-number">01 / CHOOSE YOUR DESTINATION</div>', unsafe_allow_html=True)
    a, b = st.columns(2, gap="medium")
    with a:
        with st.container(border=True):
            st.subheader("자동차 찾아보기")
            st.write("연도를 고르고 세계지도를 움직이며 자동차의 역사·사진·제원을 확인하세요.")
            st.button("World Garage 입장  →", type="primary", width="stretch", on_click=navigate, args=("garage",))
    with b:
        with st.container(border=True):
            st.subheader("자동차 만들어보기")
            st.write("차체와 동력계를 선택하고 부품을 배치해 설계의 변화와 예상 성능을 살펴보세요.")
            st.button("Design Lab 입장  →", width="stretch", on_click=navigate, args=("lab",))
    with st.container(border=True):
        st.write("**저장된 자동차 꺼내기**")
        st.caption("설계 코드·설계 파일로 복원하거나 이번 접속에서 보관한 자동차를 열 수 있습니다.")
        st.button("내 차고 열기  →", width="stretch", on_click=navigate, args=("saved",))
    with st.expander("이 버전의 데이터와 기능 범위"):
        st.write("전체 자동차를 모두 수록한 목록은 아닙니다. 초기 자료와 Wikidata 조회 결과를 구별하며, 사진·제원·3D는 각각 별도로 확보합니다. 없는 값은 미확보로 표시합니다.")
        st.write("사진 한 장의 정확한 3D 복원은 포함되지 않습니다. 기본 모형은 차종과 치수를 이용한 간이 표현이며, 별도로 확보한 GLB를 업로드하면 원본 3D를 볼 수 있습니다.")
        st.write("역사지도는 공개 데이터가 제공하는 연도의 스냅샷입니다. 선택 연도의 정확한 국경이 없으면 직전 스냅샷의 실제 연도를 표시합니다. 조향·도로·충돌을 포함한 3D 운전 기능은 후속 개발 범위입니다.")

def country_banner(cid, year):
    meta = COUNTRIES.get(cid)
    if not meta:
        st.subheader(country_name(cid))
        return
    flag = meta["flag"]
    if cid == "DE" and 1871 <= year <= 1918:
        flag = "Flag of the German Empire.svg"
    elif cid == "DE" and 1935 <= year < 1945:
        flag = "Flag of Germany (1935–1945).svg"
    elif cid == "DE" and year == 1945:
        flag = ""  # 점령기 독일에 서독·동독 국기를 적용하지 않음.
    elif cid == "FR" and year < 1789:
        flag = ""  # 확인되지 않은 왕실 국기를 현대 삼색기로 대체하지 않음.
    if cid == "GB" and 1707 <= year < 1801:
        flag = "Flag of Great Britain (1707–1800).svg"
    colors = meta["colors"]
    if cid == "DE" and 1871 <= year <= 1918:
        colors = ["#202229", "#d8dbe0", "#b83844"]
    gradient = f"linear-gradient(115deg,{colors[0]} 0%,{colors[1]} 50%,{colors[2]} 100%)"
    img = f'<img alt="시대별 대표 국기" src="https://commons.wikimedia.org/wiki/Special:FilePath/{quote(flag)}">' if flag else ""
    st.markdown(f'<div class="nation-banner"><div class="nation-band" style="background:{gradient}"></div>{img}<div class="eyebrow">NATIONAL GARAGE / {year}</div><h2>{html.escape(historical_country(cid, year))}</h2><p>발표·양산·시제 시험의 시간을 함께 읽는 자동차 아카이브</p></div>', unsafe_allow_html=True)
    if flag:
        st.caption("국기: 시대 대표 도안 · 세부 규격의 모든 연도별 변경은 미반영")
        st.link_button("국기 원문", "https://commons.wikimedia.org/wiki/File:"+quote(flag), help="당시 국가 구분을 설명하기 위한 역사 자료입니다.")

def photo_panel(car):
    if not car.get("photo_title"):
        st.info("이 차량의 사진 파일은 아직 확정되지 않았습니다. 아래에서 Commons 후보를 찾거나 출처 원문을 확인할 수 있습니다.")
        st.link_button("사진 후보 검색", "https://commons.wikimedia.org/w/index.php?search="+quote(car["photo_query"])+"&title=Special:MediaSearch&type=image")
        if st.button("Commons 대표 사진 후보 불러오기", key="find_photo_"+car["id"]):
            st.session_state["photo_result_"+car["id"]] = commons_photo(query=car["photo_query"])
        photo = st.session_state.get("photo_result_"+car["id"])
        if not photo:
            return
        st.caption("검색으로 찾은 후보입니다. 다른 세대·복제품·유사 차량인지 원문에서 확인해 주세요.")
    else:
        photo = copy.deepcopy(PREPARED_PHOTOS.get(car["id"]))
        if not photo or photo.get("title") != car["photo_title"]:
            photo = commons_photo(title=car["photo_title"])
    if photo.get("error"):
        st.warning(photo["error"])
        if safe_https(photo.get("source", "")):
            st.link_button("사진 원문 확인", photo["source"])
        return
    content = image_bytes(photo["url"])
    if content:
        st.image(content, caption="모델 계열 대표 사진 · 동일 연식·세부 트림을 보장하지 않습니다.", width="stretch")
    else:
        st.warning("사진 파일 다운로드에 실패했습니다. 원문 링크에서 사진을 확인할 수 있습니다.")
    st.caption(f"{photo['title']} · 원문 저작자 표기: {photo['author'][:700]} · {photo['license']}")
    st.caption("앱에서 사진을 추가 수정하지 않았습니다. 화면 맞춤 크기로 표시합니다.")
    links = st.columns(2)
    if safe_https(photo["source"]):
        links[0].link_button("Commons 사진 원문", photo["source"])
    license_url = photo["license_url"].replace("http://creativecommons.org/", "https://creativecommons.org/")
    if safe_https(license_url):
        links[1].link_button("사진 사용 조건", license_url)

def glb_upload(car):
    encoded = ""
    with st.expander("확보한 실차 3D 모델(GLB)로 보기"):
        st.caption("하나의 GLB 2.0 파일에 텍스처를 포함해 주세요. 최대 15 MB. Draco/KTX2 압축 모델은 이 뷰어에서 지원하지 않습니다. 모델 자체의 문 구조·애니메이션이 없는 경우 개폐를 자동 생성하지 않습니다.")
        uploaded = st.file_uploader("GLB 파일", type=["glb"], key="glb_"+car["id"])
        if uploaded:
            source = st.text_input("모델 원문 주소 또는 직접 제작 표시", key="model_source_"+car["id"])
            author = st.text_input("모델 제작자", key="model_author_"+car["id"])
            license_name = st.text_input("라이선스 / 직접 제작", key="model_license_"+car["id"])
            permission = st.checkbox("직접 제작했거나 이 방식으로 표시할 수 있는 사용권을 확인했습니다.", key="model_ok_"+car["id"])
            if permission and source.strip() and author.strip() and license_name.strip():
                try:
                    blob = uploaded.getvalue()
                    info = validate_glb(blob)
                    unsupported = set(info.get("extensionsRequired", [])) & {"KHR_draco_mesh_compression", "KHR_texture_basisu", "EXT_meshopt_compression"}
                    if unsupported:
                        raise ValueError("압축을 해제한 GLB로 내보내 주세요: "+", ".join(sorted(unsupported)))
                    encoded = base64.b64encode(blob).decode()
                    st.success(f"GLB 준비 완료 · 애니메이션 {len(info.get('animations', []))}개")
                    st.caption(f"제작자: {author} · 사용 조건: {license_name} · 출처: {source}")
                except ValueError as e:
                    st.error(str(e))
            else:
                st.info("원문·제작자·사용 조건을 입력하고 확인 항목을 선택하면 모델을 표시합니다.")
        elif car.get("model_url"):
            st.link_button("등록 모델 원문", car["model_source"])
            st.caption(f"{car['model_author']} · {car['model_license']}")
            # 서버의 임의 URL 요청 대신 사용자가 원문 파일을 내려받아 업로드.
            st.link_button("등록 GLB 파일 열기", car["model_url"])
            st.info("등록 파일을 내려받아 위 칸에 업로드하면 표시합니다. 원문 서버의 CORS·응답 형식과 무관하게 확인할 수 있습니다.")
        else:
            st.info("이 항목의 검증된 실차 GLB가 아직 등록되지 않았습니다. 아래 기본 모형은 차종·치수에 따른 간이 3D입니다.")
    return encoded

def design_for_car(car):
    d = copy.deepcopy(DEFAULT_DESIGN)
    shape = car.get("shape", "sedan")
    d["body"] = shape if shape in BODY_TYPES else "sedan"
    presets = dict(bus=(10., 2.45, 3., 5.5), van=(5., 1.95, 2.3, 3.), truck=(6.5, 2.2, 2.6, 3.8), vintage=(3., 1.55, 1.65, 1.8), steam=(3.2, 1.7, 1.7, 2.0))
    d["length"], d["width"], d["height"], d["wheelbase"] = presets.get(shape, (4.5, 1.85, 1.4, 2.65))
    for key in ["length", "width", "height", "wheelbase"]:
        if key+"_mm" in car["specs"]:
            d[key] = car["specs"][key+"_mm"]/1000.
    d["name"] = car["name"]+"에서 시작한 설계"
    return normalize_design(d)

def vehicle_detail(car):
    st.markdown('<div class="section-number">02 / VEHICLE DOSSIER</div>', unsafe_allow_html=True)
    st.subheader(car["name"])
    st.caption(f"{car['name_en']} · {car['year']}년 · {country_name(car['country'])} · {car['event']} · {car['source_kind']}")
    left, right = st.columns([1.3, 1.], gap="large")
    with right:
        photo_panel(car)
        st.write(car["description"])
        if car.get("note"):
            st.info(car["note"])
        st.link_button("차량 정보 출처 원문", car["source"])
        if car["id"] == "prius-1997":
            st.link_button("프리우스 엔진 출력 · 토요타 공식 카탈로그", "https://toyota.jp/ucar/catalog/brand-TOYOTA/car-PRIUS/199712/1003892/")
        specrows = [{"항목": label, "확인값": f"{car['specs'][key]:g} {unit}" if key in car["specs"] else "미확보", "구분": "출처 기재값" if key in car["specs"] else "—"} for key, (label, unit) in SPEC_LABELS.items()]
        st.dataframe(pd.DataFrame(specrows), hide_index=True, width="stretch")
        if st.button("내 차고에 보관", key="favorite_"+car["id"], width="stretch"):
            if car["id"] not in st.session_state.favorites:
                st.session_state.favorites.append(car["id"])
            st.success("이번 접속의 내 차고에 보관했습니다. 다른 기기까지 유지하려면 목록 JSON을 내려받아 주세요.")
        if st.button("이 치수로 Design Lab 시작  →", key="start_design_"+car["id"], width="stretch"):
            install_design(design_for_car(car))
            st.session_state.compare_id = car["id"]
            st.session_state.compare_vehicle = car["id"]
            navigate("lab")
            st.rerun()
    with left:
        model = glb_upload(car)
        d = design_for_car(car)
        render_viewer(d, label=car["name"]+(" / 등록 GLB" if model else " / 차종 기반 간이 3D"), key="vehicle_"+car["id"], glb=model)
        missing = [label for k, (label, unit) in SPEC_LABELS.items() if k in ["length_mm", "width_mm", "height_mm", "wheelbase_mm"] and k not in car["specs"]]
        st.caption("3D: 등록 GLB의 외관과 간이 모형을 구별합니다. 간이 모형의 미확보 치수는 표시용 가정이며 실제 차량 제원에 합산하지 않습니다.")
        if missing:
            st.caption("표시용 가정 치수: "+", ".join(missing))

def garage_page(cars):
    st.markdown('<div class="eyebrow">WORLD GARAGE / AUTOMOTIVE HISTORY</div>', unsafe_allow_html=True)
    st.title("지도를 따라, 자동차의 시간 속으로.")
    st.caption("출시·발표·양산·시제 시험을 구분한 목록입니다. 노란색은 현재 목록에 차량 자료가 있다는 뜻입니다.")
    quick = st.columns(7)
    for col, (year, cid, title) in zip(quick, [(1769,"FR","증기차"),(1886,"DE","모터바겐"),(1938,"DE","전쟁 전 독일"),(1957,"DE-E","동독"),(1963,"DE-W","서독"),(1975,"KR","포니"),(2022,"KR","N 비전 74")]):
        if col.button(f"{year} · {title}", key=f"jump_{year}", width="stretch"):
            set_year(year)
            st.session_state.selected_country = cid
            st.rerun()
    a, b, c = st.columns([2., 1., 1.7], vertical_alignment="bottom")
    a.radio("시대", ["근대 · 1700–1944년", "현대 · 1945년부터"], horizontal=True, key="era", on_change=sync_era)
    if "year_input" not in st.session_state:
        st.session_state.year_input = st.session_state.year
    b.number_input("연도 직접 입력", 1700, CURRENT_YEAR, step=1, key="year_input", on_change=sync_year_input)
    mode = c.selectbox("차량 표시 범위", ["선택한 연도의 차량", "선택 연도까지 누적된 차량"])
    year = st.session_state.year
    timeline = custom_components()[0]
    tr = timeline(data=dict(start=1945 if year >= 1945 else 1700, end=CURRENT_YEAR if year >= 1945 else 1944,
        year=year, years=sorted({v["year"] for v in cars})), key="timeline", on_picked_change=lambda: None)
    if tr.picked is not None and int(tr.picked) != year:
        # 위에서 생성한 number_input 키를 같은 실행 중에 바꾸지 않음.
        st.session_state.pending_year = int(tr.picked)
        st.rerun()
    relevant = [v for v in cars if v["year"] <= year] if mode.startswith("선택 연도까지") else [v for v in cars if v["year"] == year]
    counts = Counter(v["country"] for v in relevant)
    with st.spinner("공개 역사지도 자료를 확인하는 중…"):
        geo, snapshot, provider, error = load_historical_map(year)
    if error:
        st.warning(error)
    else:
        st.caption(f"선택 {year}년 / 지도 원자료 {snapshot}년 · {provider} · 국경은 해당 스냅샷의 역사적 근사 표현입니다.")
        if snapshot != year:
            st.info(f"{year}년의 정확한 국경 파일이 없어 {snapshot}년 지도를 사용합니다. 두 연도 사이의 국경 변화는 자동으로 복원하지 않습니다.")
    payload = map_payload(geo, snapshot or year, counts, st.session_state.selected_country)
    mr = custom_components()[1](data=dict(geo=payload, year=year, snapshot=snapshot,
        points=[dict(cid=cid, ko=country_name(cid), count=n, point=COUNTRIES[cid]["point"]) for cid, n in counts.items() if cid in COUNTRIES and COUNTRIES[cid].get("point")]),
        key="world_map", on_picked_change=lambda: None)
    if mr.picked and mr.picked.get("cid") and mr.picked["cid"] != st.session_state.selected_country:
        st.session_state.selected_country = mr.picked["cid"]
        st.rerun()
    st.caption("회색 = 현재 자료에 등록된 차량 없음. 그 나라에 자동차 산업이 없었다는 의미가 아닙니다. 원산국·개발국 기준이며 판매국 기준이 아닙니다.")
    labels = {"ALL": "전 세계 전체"}
    labels.update({cid: country_name(cid) for cid in COUNTRIES})
    labels.update({f["properties"]["cid"]: f["properties"]["ko"] for f in payload["features"]})
    labels.update({cid: country_name(cid) for cid in counts})
    selected = st.session_state.selected_country
    if selected not in labels:
        labels[selected] = selected.replace("MAP:", "")
    options = sorted(labels, key=lambda k: (k != "ALL", -counts.get(k, 0), labels[k]))
    # 키에 현재 선택을 포함해 지도 선택과 네이티브 선택 위젯의 상태를 일치시킴.
    cid = st.selectbox("국가 선택 · 지도 클릭이 어려울 때도 사용 가능", options,
        index=options.index(selected), format_func=lambda k: f"{labels[k]} · {counts.get(k, len(relevant) if k == 'ALL' else 0)}대",
        key=f"country_select_{year}_{selected}_{mode}")
    if cid != selected:
        st.session_state.selected_country = cid
        st.rerun()
    if cid != "ALL":
        country_banner(cid, year)
    qcol, tcol = st.columns([2, 1])
    query = qcol.text_input("자동차 이름 검색", placeholder="한글·영문 이름 검색", key="garage_search")
    kinds = sorted({v["kind"] for v in relevant})
    kind = tcol.selectbox("차량 종류", ["전체"]+kinds)
    filtered = [v for v in relevant if (cid == "ALL" or vehicle_matches_country(v, cid)) and
        (not query or query.casefold() in (v["name"]+" "+v["name_en"]).casefold()) and (kind == "전체" or v["kind"] == kind)]
    st.write(f"**{len(filtered)}대의 차량 자료**")
    if not filtered:
        st.info("이 조건에 등록된 자료가 없습니다. 다른 연도·국가를 선택하거나 아래 온라인 자료 확장을 사용해 주세요.")
    else:
        with st.container(height=360, border=True):
            for v in filtered[:240]:
                c1, c2 = st.columns([5, 1], vertical_alignment="center")
                c1.write(f"**{v['name']}**")
                c1.caption(f"{v['year']} · {country_name(v['country'])} · {v['kind']} · {v['event']}")
                if c2.button("살펴보기", key="open_"+v["id"], width="stretch"):
                    st.session_state.selected_car = v["id"]
                st.divider()
    with st.expander("온라인 자료 확장 · 현재 선택 연도의 Wikidata 조회"):
        st.write("해당 연도의 P571(성립·도입 시점)이 등록된 자동차·버스·트럭 관련 항목을 최대 160개 조회합니다. 공개 DB의 누락·분류 차이가 있어 전체 차량 목록이 아니며, 한국어 명칭이 없으면 원문 이름을 사용합니다.")
        if st.button(f"{year}년 공개 DB 조회", key="fetch_wikidata"):
            try:
                with st.spinner("공개 DB에 질의하는 중…"):
                    new = wikidata_cars(year)
                merged = {v["id"]: v for v in st.session_state.online_cars}
                merged.update({v["id"]: v for v in new})
                st.session_state.online_cars = list(merged.values())
                st.session_state.fetch_message = f"{year}년 자료 {len(new)}개를 받았습니다. 원산국이 확인되지 않은 항목은 '미분류'에 있습니다."
                st.rerun()
            except (requests.RequestException, ValueError, KeyError) as e:
                st.warning(f"공개 DB 조회를 완료하지 못했습니다 ({type(e).__name__}). 잠시 후 다시 조회해 주세요. 초기 자료와 설계 기능은 계속 사용할 수 있습니다.")
        if st.session_state.get("fetch_message"):
            st.info(st.session_state.fetch_message)
    selected_car = next((v for v in filtered if v["id"] == st.session_state.selected_car), None)
    if not selected_car and filtered:
        selected_car = filtered[0]
    if selected_car:
        vehicle_detail(selected_car)
    with st.expander("데이터 출처·지도 기준·목록 내보내기"):
        st.markdown(f"지도: [historical-basemaps]({BASEMAP_REPO}) · 저장소 표기 GPL-3.0. 원자료·기여자·사용 조건은 저장소에서 확인할 수 있습니다. 각 스냅샷은 특정 시기의 근사 자료이며 영토 분쟁에 대한 판단을 뜻하지 않습니다.")
        st.markdown("사진: [Wikimedia Commons](https://commons.wikimedia.org). 파일별 저자·라이선스·원문을 표시합니다. 초기 목록의 글은 이 앱을 위해 작성한 설명이며, 제원과 공개 연도의 원문은 각 차량에 연결되어 있습니다.")
        st.markdown("구조화 정보: [Wikidata CC0](https://www.wikidata.org/wiki/Wikidata:Licensing). 검색된 항목은 자동 검증된 제조사 제원으로 표시하지 않습니다.")
        st.download_button("현재 차량 목록 JSON 다운로드", json.dumps(cars, ensure_ascii=False, indent=2), "vehicles.json", "application/json")


def design_num(d, key, label, lo, hi, step=.05, help=None):
    widget_key = f"design_{st.session_state.design_revision}_{key}"
    value = min(float(hi), max(float(lo), float(d[key])))
    if widget_key in st.session_state:
        st.session_state[widget_key] = min(float(hi), max(float(lo), float(st.session_state[widget_key])))
    d[key] = st.number_input(label, min_value=float(lo), max_value=float(hi), value=value,
        step=float(step), key=widget_key, help=help)

def design_select(d, key, label, choices, format_func=None):
    choices = list(choices)
    d[key] = st.selectbox(label, choices, index=choices.index(d[key]),
        key=f"design_{st.session_state.design_revision}_{key}", format_func=format_func or (lambda x: x))

def lab_controls():
    d = copy.deepcopy(st.session_state.design)
    rev = st.session_state.design_revision
    d["name"] = st.text_input("설계 이름", d["name"], max_chars=80, key=f"design_{rev}_name")
    with st.container(height=650, border=True):
        shape, equipment, layout, assumptions = st.tabs(["외형", "부품", "배치", "계산 가정"])
        with shape:
            design_select(d, "body", "차체 유형", BODY_TYPES, lambda x: BODY_TYPES[x])
            if st.button("이 차종의 기본 치수 적용", key="body_preset"):
                presets = dict(sedan=(4.6,1.84,1.45,2.7),coupe=(4.5,1.85,1.35,2.65),hatchback=(4.1,1.75,1.5,2.55),suv=(4.7,1.93,1.8,2.8),roadster=(4.2,1.8,1.22,2.45),van=(5.2,1.98,2.25,3.15),bus=(10.,2.45,3.2,5.6),truck=(6.5,2.3,2.8,3.8),vintage=(3.2,1.6,1.7,1.9),steam=(3.6,1.8,1.8,2.1))
                for k, v in zip(["length","width","height","wheelbase"], presets[d["body"]]):
                    d[k] = v
                d["body_mass"] = 4200. if d["body"] == "bus" else 2500. if d["body"] == "truck" else 650.
                install_design(d)
                st.rerun()
            design_num(d,"length","전장 (m)",2.,14.)
            design_num(d,"width","전폭 (m)",1.2,2.6)
            design_num(d,"height","전고 (m)",.9,4.)
            design_num(d,"wheelbase","축거 (m)",round(d["length"]*.45,3),round(d["length"]*.80,3))
            design_num(d,"wheel_radius","타이어 바깥 반지름 (m)",.20,.65,.01)
            d["cabin"] = st.slider("캐빈 길이 / 전장", .28, .74, float(d["cabin"]), .01, key=f"design_{rev}_cabin")
            d["nose"] = st.slider("앞부분 비율", .12, .38, float(d["nose"]), .01, key=f"design_{rev}_nose")
            x, y = st.columns(2)
            d["color"] = x.color_picker("차체 색상", d["color"], key=f"design_{rev}_color")
            d["rim"] = y.color_picker("휠 색상", d["rim"], key=f"design_{rev}_rim")
            d["spoiler"] = st.checkbox("리어 스포일러", d["spoiler"], key=f"design_{rev}_spoiler")
            st.caption("비율·색·스포일러는 3D 외형에 반영됩니다. 외형 변경으로 Cd나 다운포스를 자동 산출하지 않습니다. 스포일러는 가정 질량 8 kg만 추가합니다.")
        with equipment:
            st.caption("아래 부품은 브랜드 실물 제원이 아닌 교육용 기본 규격입니다. 출력·질량·토크 등 계산 가정을 직접 바꿀 수 있습니다.")
            before_engine = d["engine"]
            design_select(d,"engine","엔진 / 모터",ENGINES)
            if d["engine"] != before_engine:
                e = ENGINES[d["engine"]]
                d.update(power_kw=e["power"], torque_nm=e["torque"], max_rpm=e["rpm"],
                    battery_kwh=60. if e["type"] == "ev" else 0., fuel_liters=0. if e["type"] == "ev" else 45.,
                    gear_top=9. if e["type"] == "ev" else 3.)
                install_design(d)
                st.rerun()
            design_select(d,"drive","구동 방식",["전륜","후륜","사륜"])
            before_brake = d["brake"]
            design_select(d,"brake","브레이크",BRAKES)
            if d["brake"] != before_brake:
                d["brake_torque"] = BRAKES[d["brake"]]["torque"]
                install_design(d)
                st.rerun()
            before_tire = d["tire"]
            design_select(d,"tire","타이어",TIRES)
            if d["tire"] != before_tire:
                d["mu"], d["crr"] = TIRES[d["tire"]]["mu"], TIRES[d["tire"]]["crr"]
                install_design(d)
                st.rerun()
            design_select(d,"suspension","서스펜션 설계 기록",["맥퍼슨","더블 위시본","리프 스프링"])
            st.caption("서스펜션은 설계 기록으로 저장합니다. 스프링·감쇠·횡방향 운동 해석은 포함되지 않습니다.")
            design_num(d,"power_kw","구동원 최고출력 가정 (kW)",1.,1500.,5.)
            design_num(d,"torque_nm","구동원 최대토크 가정 (N·m)",10.,5000.,10.)
            design_num(d,"max_rpm","구동원 회전수 상한 가정 (rpm)",2000.,25000.,500.)
            design_num(d,"body_mass","차체·내장 질량 입력 (kg)",150.,15000.,25.,help="엔진·배터리·변속기·브레이크·휠·탑승자를 제외한 나머지 질량입니다. 차체 치수로 자동 계산한 구조 질량이 아닙니다.")
            design_num(d,"battery_kwh","배터리 용량 (kWh)",0.,400.,5.)
            design_num(d,"battery_density","배터리 팩 에너지밀도 가정 (Wh/kg)",80.,300.,5.)
            design_num(d,"fuel_liters","탑재 연료량 (L)",0.,400.,5.)
            design_num(d,"occupant_mass","탑승자·추가 적재 질량 (kg)",0.,6000.,5.)
        with layout:
            st.write("3D 화면에서 **차체 반투명 → 부품 선택 → 화살표 축 드래그** 순서로 배치할 수 있습니다. 아래 숫자로도 조절할 수 있습니다.")
            st.caption("x: 전장 대비 위치, +는 앞쪽 / y: 지면에서 높이(m) / z: 전폭 대비 좌우 위치. 부품 간 간섭·실제 장착 가능 여부는 별도 검토가 필요합니다.")
            for key, title in [("engine","엔진·모터"),("battery","배터리"),("gearbox","변속기"),("tank","연료 탱크")]:
                st.write(f"**{title}**")
                pos = list(d["positions"][key])
                pos[0] = st.slider("앞뒤 x", -.42, .42, float(pos[0]), .01, key=f"design_{rev}_{key}_x")
                pos[1] = st.slider("높이 y (m)", .15, max(.16,round(d["height"]*.72,2)), min(float(pos[1]),round(d["height"]*.72,2)), .01, key=f"design_{rev}_{key}_y")
                pos[2] = st.slider("좌우 z", -.35, .35, float(pos[2]), .01, key=f"design_{rev}_{key}_z")
                d["positions"][key] = pos
        with assumptions:
            design_num(d,"cd","공기저항계수 Cd 가정",.15,1.2,.01)
            design_num(d,"area_factor","정면적 보정계수 k",.65,1.,.01,help="A=k×전폭×전고. 실제 투영 면적·CFD 결과와 다릅니다.")
            design_num(d,"efficiency","구동계 전달 효율 가정",.5,.98,.01)
            design_num(d,"gear_launch","저속 유효 기어비 가정",2.,25.,.5)
            design_num(d,"gear_top","최고단 총기어비 가정",1.,20.,.25)
            design_num(d,"brake_torque","네 바퀴 합산 제동토크 가정 (N·m)",1000.,60000.,200.)
            design_num(d,"mu","타이어·노면 마찰계수 μ 가정",.15,1.3,.05)
            design_num(d,"crr","구름저항계수 Crr 가정",.005,.04,.001)
            design_num(d,"reaction","운전자 반응시간 가정 (s)",0.,3.,.1)
            design_num(d,"slope","도로 경사 가정 (%)",-10.,20.,1.)
    return normalize_design(d)

def comparison_panel(cars, d, result):
    st.subheader("기존 자동차와 비교")
    options = [v["id"] for v in cars]
    if not options:
        return
    lookup = {v["id"]: v for v in cars}
    default = st.session_state.get("compare_id", "nvision-2022")
    if default not in lookup:
        default = options[0]
    compare = st.selectbox("비교할 차량", options, index=options.index(default), format_func=lambda x:f"{lookup[x]['year']} · {lookup[x]['name']}", key="compare_vehicle")
    car = lookup[compare]
    own = dict(length_mm=d["length"]*1000, width_mm=d["width"]*1000, height_mm=d["height"]*1000,
               wheelbase_mm=d["wheelbase"]*1000, mass_kg=result["mass"], power_kw=d["power_kw"],
               torque_nm=d["torque_nm"], top_speed_kmh=result["vmax"], zero100_s=result["zero100"], battery_kwh=d["battery_kwh"])
    rows = []
    for key, value in own.items():
        label, unit = SPEC_LABELS[key]
        official = car["specs"].get(key)
        category = "공학 모델 추정" if key in ["top_speed_kmh","zero100_s"] else "부품 질량 합계·탑승자 포함" if key == "mass_kg" else "사용자 입력"
        rows.append({"항목": label, "기존 차량 · 출처 기재값": f"{official:g} {unit}" if official is not None else "미확보",
                     "내 설계": f"{value:,.2f} {unit}" if value is not None else "100 km/h 미도달", "내 설계 값의 구분": category})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.caption("기존 차량의 공차질량과 내 설계의 탑승자 포함 총질량은 기준이 다릅니다. 서로 다른 시험 조건의 공식 성능과 교육용 추정값을 우열 판정에 사용하지 않습니다.")
    st.link_button("비교 차량 원문", car["source"])

def save_design_panel(d):
    st.subheader("설계 저장")
    st.caption("휴대용 코드는 설계 데이터와 복원 열쇠를 모두 포함합니다. 서버 저장소 없이도 다른 기기·재배포 후 복원할 수 있습니다. 코드를 가진 사람은 설계를 열 수 있습니다.")
    mode = st.radio("저장 방식", ["휴대용 코드 · 설정 없이 사용", "짧은 코드 · Supabase 연결 필요"], horizontal=True, key="save_mode")
    if st.button("자동차 저장 · 코드 만들기", type="primary", key="save_design"):
        try:
            code = save_short_code(d) if mode.startswith("짧은") else make_portable_code(d)
            snapshot = dict(name=d["name"], design=copy.deepcopy(d), code=code, created=datetime.now(timezone.utc).isoformat())
            st.session_state.saved_designs.append(snapshot)
            st.session_state.last_saved_code = code
            st.session_state.last_saved_design = copy.deepcopy(d)
            st.success("설계를 저장했습니다. 아래 코드를 복사하거나 설계 파일을 내려받아 보관해 주세요.")
        except (ValueError, requests.RequestException) as e:
            st.error("저장하지 못했습니다. "+(str(e) if isinstance(e,ValueError) else "저장소 연결·테이블·Secrets 설정을 확인해 주세요."))
    code = st.session_state.get("last_saved_code")
    if code:
        snapshot = st.session_state.last_saved_design
        st.text_area("복원 코드 · 전체를 복사하세요", code, height=120, key="generated_code_"+hashlib.sha256(code.encode()).hexdigest()[:12])
        st.caption("아래 파일은 마지막으로 저장한 시점의 설계입니다. 이후 수정은 다시 저장해야 반영됩니다.")
        a,b = st.columns(2)
        a.download_button("복원 코드 TXT",code,"autoverse-code.txt","text/plain",width="stretch")
        b.download_button("설계 JSON",json.dumps(dict(schema=1,design=snapshot),ensure_ascii=False,indent=2),"autoverse-design.json","application/json",width="stretch")

def lab_page(cars):
    st.markdown('<div class="eyebrow">DESIGN LAB / YOUR PERSONAL COACHBUILDER</div>', unsafe_allow_html=True)
    st.title("작은 작업실에서 시작하는 나만의 자동차.")
    st.caption("차체·비율·동력계·부품 배치를 바꾸고, 같은 가정 아래에서 설계의 변화를 비교하세요.")
    left, right = st.columns([.82,1.6],gap="large")
    with left:
        d = lab_controls()
        st.session_state.design = d
    result = performance(d)
    with right:
        render_viewer(d,label=d["name"]+" / 교육용 간이 설계",key="design_viewer",workshop=True,editable=True)
        a,b,c = st.columns(3)
        a.metric("총질량 · 부품 합계",f"{result['mass']:,.0f} kg")
        b.metric("최고속도 · 추정",f"{result['vmax']:.1f} km/h")
        c.metric("0→100 km/h · 추정",f"{result['zero100']:.1f} 초" if result["zero100"] is not None else "120초 내 미도달")
        a,b,c = st.columns(3)
        a.metric("100→0 제동거리 · 추정",f"{result['brake_distance']:.1f} m" if result["brake_distance"] else "정지 불가")
        b.metric("반응시간 이동거리",f"{result['reaction_distance']:.1f} m")
        c.metric("정적 앞축 하중 비율",f"{result['front_fraction']*100:.1f}%")
        st.markdown('<div class="note-box">결과는 사용자 입력과 단순화한 공학 모델의 추정값입니다. 실측 성능·인증 제원·차량 제작 가능성을 의미하지 않습니다. Cd·마찰계수·전달 효율은 계산 가정입니다.</div>',unsafe_allow_html=True)
    stats, compare, save, theory = st.tabs(["성능 분석","기존 차량 비교","저장","계산식·부품표"])
    with stats:
        a,b = st.columns(2)
        with a:
            st.write("**가속 과정 · 교육용 추정**")
            st.line_chart(pd.DataFrame(result["trace"],columns=["시간 (s)","속도 (km/h)"]).set_index("시간 (s)"),height=260)
        with b:
            st.write("**속도에 따른 주행 저항 동력**")
            st.line_chart(pd.DataFrame(result["power_curve"],columns=["속도 (km/h)","필요 동력 (kW)"]).set_index("속도 (km/h)"),height=260)
            st.caption("주행 저항을 이기는 데 필요한 바퀴 동력입니다. 엔진·모터의 출력곡선이나 주행 가능 속도 범위 자체가 아닙니다.")
        if ENGINES[d["engine"]]["type"] == "ev" and d["battery_kwh"] == 0:
            st.warning("전기모터를 선택했지만 배터리 용량이 0입니다. 계산은 에너지 공급이 있다고 가정하므로 실제 구동 가능한 설계가 아닙니다.")
        if ENGINES[d["engine"]]["type"] != "ev" and d["fuel_liters"] == 0:
            st.warning("내연기관을 선택했지만 연료량이 0입니다. 계산은 연료가 공급된다고 가정합니다.")
    with compare:
        comparison_panel(cars,d,result)
    with save:
        save_design_panel(d)
    with theory:
        st.markdown(r"""
**계산에 사용한 관계식**

- 총질량 = 차체·내장 입력 + 동력원 + 변속기 + 배터리 + 연료·탱크 + 브레이크 + 휠 + 스포일러 + 탑승자·적재.
- 배터리 질량 = 용량(kWh) × 1,000 / 팩 에너지밀도(Wh/kg).
- 정면적 근사: $A=kWH$.
- 공기저항: $F_d=\frac12\rho C_d A v^2$, 공기 밀도 $\rho=1.225\,\mathrm{kg/m^3}$.
- 구름저항: $F_r=C_{rr}mg\cos\theta$, 등판저항: $F_g=mg\sin\theta$.
- 바퀴 구동력 = 출력 제한, 저속 토크 제한, 정적 구동축 접지력 중 최솟값.
- 가속도: $a=(F_{drive}-F_d-F_r-F_g)/m$. 0.04초 간격 전진 적분, 최대 120초.
- 최고속도: 저항과 구동력이 균형을 이루는 속도와 최고단 회전수 제한 중 낮은 값.
- 제동 감속도: $a_b=\min(\mu g\cos\theta,\,T_b/(mr))+g\sin\theta$.
- 제동거리: $s=v_0^2/(2a_b)$, 반응거리: $s_r=v_0t_r$. 제동 계산에서는 공기·구름저항을 제외합니다.

**모델의 가정과 한계**

Cd는 사용자가 지정한 가정입니다. 3D 표면으로 CFD를 수행하지 않습니다. 차체 질량도 치수로 자동 추론하지 않습니다. 부품의 앞뒤 배치는 정적 축하중과 구동 접지력에 반영됩니다. 부품 높이·좌우 위치는 설계에 기록되지만 횡방향 운동·하중이동 해석에는 사용하지 않습니다.

실제 엔진 회전수별 토크곡선, 기어 변속, 휠 회전 관성, 가속 중 하중이동, 배터리 충전상태·전류 제한, 온도, 부품 간 간섭, 구조 강도, 타이어 슬립, 제동 열화, ABS·ESC는 계산하지 않습니다. 저속 유효 기어비와 최고단 기어비를 별도로 사용하는 토크·출력 포락선 모델입니다. 부품 규격·질량은 교육용 기본 가정입니다.
""")
        st.link_button("공기저항 관계식 · NASA", "https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-equation/")
        translations = dict(body="차체·내장",engine="엔진·모터",battery="배터리",gearbox="변속기",tank="연료·탱크",brakes="브레이크",wheels="휠·타이어",spoiler="스포일러",occupant="탑승자·추가 적재")
        st.dataframe(pd.DataFrame([{"부품":translations[k],"질량 (kg)":round(v,2),"구분":"사용자 입력·교육용 부품 가정"} for k,v in result["masses"].items()]),hide_index=True,width="stretch")
        st.caption(f"정면적 근사 {result['area']:.3f} m² · 앞뒤 무게중심 x={result['cg_x']:.3f} m (차체 중심 기준, +는 앞) · 바퀴 전달 출력 가정 {result['power_wheel_kw']:.1f} kW")

def saved_page(cars):
    st.markdown('<div class="eyebrow">PERSONAL GARAGE / RESTORE YOUR DESIGN</div>',unsafe_allow_html=True)
    st.title("저장된 자동차 꺼내기")
    st.write("휴대용 설계 코드, 연결된 저장소의 짧은 코드, 설계 JSON 파일로 자동차를 복원할 수 있습니다.")
    with st.form("restore_code"):
        code = st.text_area("자동차 코드 · AV1. 또는 AVS.로 시작하는 코드 전체",height=130,max_chars=MAX_CODE_CHARS)
        if st.form_submit_button("코드로 자동차 불러오기",type="primary",width="stretch"):
            try:
                restored = restore_short_code(code.strip()) if code.strip().startswith("AVS.") else restore_portable_code(code)
                install_design(restored)
                navigate("lab")
                st.rerun()
            except (ValueError,requests.RequestException) as e:
                st.error(str(e) if isinstance(e,ValueError) else "저장소에 연결하지 못했습니다. Secrets·네트워크 설정을 확인해 주세요.")
    with st.expander("설계 파일로 복원"):
        uploaded = st.file_uploader("AUTOVERSE 설계 JSON",type=["json"],key="design_json_upload")
        if uploaded and st.button("파일에서 설계 불러오기",key="restore_json"):
            try:
                if uploaded.size>100000:
                    raise ValueError("설계 파일은 최대 100 KB입니다.")
                document=json.loads(uploaded.getvalue())
                if not isinstance(document,dict) or document.get("schema")!=1:
                    raise ValueError("AUTOVERSE 버전 1 설계 파일이 아닙니다.")
                install_design(document["design"])
                navigate("lab")
                st.rerun()
            except (ValueError,KeyError,TypeError) as e:
                st.error("설계 파일을 읽지 못했습니다: "+str(e))
    st.subheader("이번 접속에서 저장한 설계")
    st.caption("이 목록은 접속 세션 동안 유지됩니다. 코드·파일을 보관하면 재접속 후 복원할 수 있습니다. 짧은 코드는 Supabase에 저장됩니다.")
    for i,saved in enumerate(reversed(st.session_state.saved_designs)):
        with st.container(border=True):
            a,b=st.columns([4,1],vertical_alignment="center")
            a.write(f"**{saved['name']}**")
            a.caption(saved["created"][:19].replace("T"," ")+" UTC 저장")
            if b.button("열기",key=f"saved_open_{i}",width="stretch"):
                install_design(saved["design"])
                navigate("lab")
                st.rerun()
            st.code(saved["code"],language=None,wrap_lines=True)
    if not st.session_state.saved_designs:
        st.info("아직 이번 접속에서 저장한 설계가 없습니다.")
    st.subheader("보관한 기존 자동차")
    favorites=[v for v in cars if v["id"] in st.session_state.favorites]
    for car in favorites:
        a,b=st.columns([4,1],vertical_alignment="center")
        a.write(f"{car['year']} · **{car['name']}**")
        if b.button("자료 열기",key="favorite_open_"+car["id"]):
            set_year(car["year"])
            st.session_state.selected_country=car["country"]
            st.session_state.selected_car=car["id"]
            st.session_state.garage_search=""
            navigate("garage")
            st.rerun()
    if favorites:
        st.download_button("보관 차량 목록 JSON",json.dumps(favorites,ensure_ascii=False,indent=2),"my-autoverse-vehicles.json","application/json")
    else:
        st.caption("World Garage의 차량 상세에서 내 차고에 보관할 수 있습니다.")

SUPABASE_SQL = """create table if not exists public.autoverse_designs (
  id text primary key,
  payload text not null,
  created_at timestamptz not null default now()
);
alter table public.autoverse_designs enable row level security;
revoke all on table public.autoverse_designs from anon, authenticated;
-- 이 앱의 서버에서만 service_role 키로 접근합니다.
-- anon/클라이언트 키에 공개 조회 정책을 추가하지 않습니다.
"""

def sidebar(cars):
    with st.sidebar:
        st.markdown("### AUTOVERSE")
        st.caption("자동차 탐색 · 분석 · 제작")
        st.button("저장된 자동차 꺼내기",on_click=navigate,args=("saved",),width="stretch",key="sidebar_saved")
        st.divider()
        with st.expander("자료 추가 · JSON"):
            st.caption("차량 목록 JSON을 업로드하면 이번 접속에 추가됩니다. 계속 제공하려면 GitHub에 vehicles.json으로 함께 올리세요.")
            uploaded=st.file_uploader("차량 목록 JSON",type=["json"],key="catalog_upload")
            if uploaded and st.button("목록 적용",key="apply_catalog"):
                try:
                    if uploaded.size>5*1024*1024:
                        raise ValueError("목록은 최대 5 MB입니다.")
                    data=json.loads(uploaded.getvalue())
                    if not isinstance(data,list) or len(data)>5000:
                        raise ValueError("최대 5,000개 항목의 JSON 목록을 입력해 주세요.")
                    validated=[validate_car(v) for v in data]
                    st.session_state.extra_cars=validated
                    st.success(f"{len(validated)}개 차량을 추가했습니다.")
                    st.rerun()
                except (ValueError,TypeError,AttributeError) as e:
                    st.error(str(e))
            st.download_button("차량 등록 양식",json.dumps([CATALOG[1]],ensure_ascii=False,indent=2),"vehicles-template.json","application/json")
        with st.expander("지도·3D 연결 안내"):
            st.write("지도는 서버에서 GitHub 원자료를 가져옵니다. 지도 렌더링은 jsDelivr의 D3, 3D는 esm.sh의 Three.js를 사용합니다. 브라우저에서 이 주소들에 접속할 수 있어야 합니다.")
            st.write("연도별 원자료가 있으면 maps/world_연도.geojson으로 추가할 수 있습니다. 파일의 출처와 사용 조건도 함께 관리하세요. 최초 두 파일만 올려도 공개 스냅샷을 조회합니다.")
            st.write("GLB를 추가하면 등록된 사진·제원과 별도로 표시합니다. 문 개폐는 원본 파일의 구조·애니메이션 지원이 필요합니다.")
        with st.expander("짧은 코드 저장소 설정"):
            st.write("기본 휴대용 코드에는 API 키가 필요 없습니다. 짧은 코드로 저장하려면 Supabase 프로젝트의 SQL Editor에서 아래 테이블을 만든 뒤, Streamlit Cloud의 App settings → Secrets에 설정하세요.")
            st.code(SUPABASE_SQL,language="sql")
            st.code('SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"\nSUPABASE_SECRET_KEY = "sb_secret_YOUR_SERVER_SIDE_SECRET"',language="toml")
            st.caption("키는 Supabase 프로젝트의 API 설정에서 확인합니다. sb_secret 키는 main.py·GitHub·브라우저 코드에 넣지 않습니다. 앱 서버에서만 사용합니다. 기존 service_role 키도 호환 설정으로 지원합니다.")
            st.link_button("Supabase API 키 안내","https://supabase.com/docs/guides/api/api-keys")
            st.link_button("Streamlit Secrets 안내","https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management")
            st.caption("상태: "+("연결 정보 설정됨 · 연결 성공 여부는 저장 시 확인" if database_config() else "미설정 · 휴대용 코드 사용 가능"))
        st.divider()
        st.caption(f"현재 목록 {len(cars)}개 · 기본 {len(CATALOG)}개")
        st.caption("실제 운전·도로·충돌 시뮬레이션은 후속 개발 범위입니다.")

def main():
    st.set_page_config(page_title="AUTOVERSE · 자동차 탐색·분석·제작",page_icon="🏎️",layout="wide",initial_sidebar_state="collapsed")
    st.markdown(APP_CSS,unsafe_allow_html=True)
    initialize()
    if "pending_year" in st.session_state:
        set_year(st.session_state.pop("pending_year"))
    cars,errors=all_cars()
    sidebar(cars)
    header()
    for error in errors:
        st.warning("추가 차량 파일을 적용하지 못했습니다: "+error)
    if st.session_state.page=="garage":
        garage_page(cars)
    elif st.session_state.page=="lab":
        lab_page(cars)
    elif st.session_state.page=="saved":
        saved_page(cars)
    else:
        home_page(cars)
    st.divider()
    st.markdown('<div class="fine">AUTOVERSE · 자동차를 이해하고 다음 설계를 탐구하는 공간<br>기존 차량 정보 · 사용자 입력 · 교육용 공학 추정을 구분해 표시합니다.</div>',unsafe_allow_html=True)

if __name__=="__main__":
    main()



