from __future__ import annotations
import html,json,math,re,os
from pathlib import Path
import streamlit as st
import catalog
ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='오토버스 · 자동차 탐색과 제작',page_icon='🚘',layout='wide',initial_sidebar_state='collapsed')
st.markdown('''<style>
#MainMenu,footer{visibility:hidden}.block-container{max-width:1460px;padding-top:2rem;padding-bottom:3rem}h1,h2,h3{letter-spacing:-.045em}h1{font-weight:750}h3{line-height:1.35}.eyebrow{font-size:11px;letter-spacing:.16em;color:#49766f;margin-bottom:10px}.hero-line{font-size:16px;color:#647a7a;line-height:1.8}.car-title{font-size:19px;font-weight:700;line-height:1.45;color:#183d45;margin:8px 0 4px}.photo-pending{height:110px;background:linear-gradient(145deg,#e4e9e3,#f3f2ea);border-radius:10px;display:flex;align-items:center;justify-content:center;color:#718783;font-size:12px;margin-bottom:12px;border:1px solid #d9e1d8}.car-meta{font-size:12px;color:#68807d}.tag{display:inline-block;background:#e6efeb;color:#35695f;border:1px solid #d4e2da;padding:3px 8px;border-radius:20px;font-size:10px;margin:0 4px 5px 0}.result-summary{color:#425e62;font-size:13px;margin:10px 0 18px}.detail-pending{padding:44px 22px;background:#eaece5;border-radius:14px;text-align:center;color:#70827d;border:1px dashed #bfcfc4}.stButton>button{border-radius:9px}div[data-testid=stMetricValue]{font-size:1.75rem}div[data-testid=stVerticalBlockBorderWrapper]{border-radius:14px}button:focus-visible{outline:3px solid #93beb0}
</style>''',unsafe_allow_html=True)
DEFAULTS={'app_page':'세계 자동차 탐색','query':'','map_year':2026,'year_scope':'선택 연도','strict_model':False,'country_choice':'','maker_choice':'','selected_codes':None,'selected_feature':None,'selected_region':'','selected_vehicle':None,'page_number':1,'all_country_labels':False}
for key,value in DEFAULTS.items():st.session_state.setdefault(key,st.session_state.get('explorer_settings',{}).get(key,value))
st.session_state.explorer_settings={key:st.session_state[key] for key in DEFAULTS}
page=st.radio('기능 선택',['세계 자동차 탐색','자동차 제작 작업실'],key='app_page',horizontal=True,label_visibility='collapsed')
if page=='자동차 제작 작업실':
 import workshop_runtime
 st.markdown('<div class="eyebrow">두 번째 기능 · 제작</div>',unsafe_allow_html=True)
 st.title('나만의 자동차 작업실')
 st.caption('메인 작업실과 소부품 작업실에서 설계하고 조립하세요. 작업은 작업실 안에서 저장·불러올 수 있습니다.')
 with st.expander('작업실 화면 높이'):
  height=st.slider('작업실 높이',700,1600,1100,50)
 if hasattr(st,'iframe'):st.iframe(workshop_runtime.workshop_html(),height=height,alt='자동차 제작 작업실')
 else:
  import streamlit.components.v1 as components
  components.html(workshop_runtime.workshop_html(),height=height,scrolling=False)
 st.stop()

def query_changed():st.session_state.year_scope='전체 연도';st.session_state.page_number=1;st.session_state.selected_vehicle=None

def year_changed():
 st.session_state.selected_feature=None;st.session_state.selected_region='선택한 제조사 국적';st.session_state.page_number=1
 if st.session_state.country_choice=='@map' and len(st.session_state.selected_codes or [])==1:st.session_state.country_choice=st.session_state.selected_codes[0]

def filters_changed():st.session_state.page_number=1

def clear_country():st.session_state.country_choice='';st.session_state.selected_codes=None;st.session_state.selected_feature=None;st.session_state.selected_region='';st.session_state.maker_choice='';st.session_state.page_number=1

def map_selection_changed():
 selection=st.session_state.get('world_map',{}).get('selection')
 if not isinstance(selection,dict):return
 year=st.session_state.map_year
 if selection.get('year')!=year:return
 feature=next((f for f in catalog.map_for_year(year)['features'] if f['properties']['id']==selection.get('feature_id')),None)
 if not feature:return
 p=feature['properties']
 st.session_state.update(selected_codes=p.get('country_codes',[]),selected_feature=p['id'],selected_region=p['name_ko'],country_choice='@map',year_scope='선택 연도',maker_choice='',page_number=1)

def details_view(record):
 st.button('← 검색 결과로 돌아가기',on_click=lambda:st.session_state.update(selected_vehicle=None))
 st.markdown('<div class="eyebrow">자동차 살펴보기</div>',unsafe_allow_html=True)
 st.title(record['model_ko']);st.caption(record['maker_ko']+' · '+catalog.country_name(record['origin_code'])+' · '+(str(record['year'])+'년' if record['year'] else '연도 미확인'))
 st.info('연도 기준: '+record['year_label_ko']+' · 국적은 제조사 기준입니다.')
 try:detail=catalog.load_details(record['vehicle_id'])
 except (ValueError,OSError,json.JSONDecodeError):detail={};st.warning('상세 자료 연결 정보를 확인해야 합니다.')
 photo_tab,history_tab,spec_tab=st.tabs(['사진','역사','제원'])
 with photo_tab:
  photos=detail.get('photos',[])
  locations=[(catalog.photo_location(p),p.get('caption_ko','')) for p in photos if isinstance(p,dict)]
  locations=[p for p in locations if p[0]]
  if not locations:st.markdown('<div class="detail-pending">자동차 사진을 준비하고 있습니다.</div>',unsafe_allow_html=True)
  for location,caption in locations:st.image(location,caption=caption or None,width='stretch')
 with history_tab:
  history=detail.get('history_ko')
  if history:st.write(history)
  else:st.markdown('<div class="detail-pending">이 자동차의 역사 자료를 준비하고 있습니다.</div>',unsafe_allow_html=True)
 with spec_tab:
  specs=detail.get('specifications',[])
  if specs:
   units={'mm':'밀리미터','m':'미터','kg':'킬로그램','kW':'킬로와트','hp':'마력','cc':'세제곱센티미터','kWh':'킬로와트시','km':'킬로미터','N·m':'뉴턴미터'}
   rows=[]
   for spec in specs:
    if not isinstance(spec,dict) or not spec.get('label_ko'):continue
    value=spec.get('value')
    if value is None and spec.get('min') is not None and spec.get('max') is not None:value=str(spec['min'])+' ~ '+str(spec['max'])
    rows.append({'항목':spec['label_ko'],'값':str(value) if value is not None else '준비 중','단위':units.get(spec.get('unit'),spec.get('unit_ko',''))})
   if rows:st.dataframe(rows,hide_index=True,width='stretch')
  else:
   st.markdown('<div class="detail-pending">제원 자료를 준비하고 있습니다.</div>',unsafe_allow_html=True)
   st.caption('전장·전폭·전고·축간거리·중량·동력 성능 등을 같은 차량에 연결할 수 있습니다.')
 if detail.get('sources'):
  with st.expander('자료 출처'):
   for source in detail['sources']:
    if isinstance(source,dict) and re.match(r'^https://',source.get('url','')):st.link_button(source.get('label_ko','원본 자료 보기'),source['url'])
 with st.expander('이 기록에 대한 안내'):
  st.write('차량 식별번호를 유지해 사진·역사·제원을 연결하는 구조입니다. 현재 화면에서 비어 있는 자료는 확인된 내용이 추가되면 표시됩니다.')
  st.write('원자료의 모델 연식·등록연도·세대 시작연도는 서로 다른 기준입니다. 한국어 명칭은 정식 국내 판매명과 읽기 표기가 함께 포함되어 있습니다.')
  st.caption('추가 명칭 자료' if record['source_kind']=='nameplate' else '1단계 차량 목록')

try:
 m=catalog.manifest();years=sorted(int(y) for y in m['year_counts'] if y!='unknown')
 if st.session_state.selected_vehicle:
  record=catalog.vehicle(st.session_state.selected_vehicle)
  if record:details_view(record);st.stop()
  st.session_state.selected_vehicle=None
 st.markdown('<div class="eyebrow">첫 번째 기능 · 탐색</div>',unsafe_allow_html=True)
 left,right=st.columns([3,1])
 with left:
  st.title('자동차의 시간을 여행하세요')
  st.markdown('<p class="hero-line">지도의 국가를 누르거나 이름을 검색해 자동차를 만나보세요.<br>국가는 판매 지역이 아닌 제조사의 국적을 기준으로 연결합니다.</p>',unsafe_allow_html=True)
 with right:
  st.metric('검색 가능한 기록',f"{m['records']:,}건")
  st.caption('차량 목록과 추가 명칭 자료 · 고유 차종 수와 다릅니다.')
 st.text_input('자동차·제조사 이름 검색',placeholder='예: 아반떼, 아우디, 롤스로이스, 비엠더블유',key='query',on_change=query_changed)
 year_col,labels_col=st.columns([5,1])
 with year_col:st.select_slider('세계지도 연도',options=years,key='map_year',format_func=lambda y:f'{y}년',on_change=year_changed)
 with labels_col:st.checkbox('모든 국가명',key='all_country_labels')
 query=st.session_state.query;year=st.session_state.map_year;scope=st.session_state.year_scope;strict=st.session_state.strict_model
 search_year=year if scope=='선택 연도' else None;unknown=scope=='연도 미확인'
 if st.session_state.country_choice!='@map':st.session_state.selected_codes=[st.session_state.country_choice] if st.session_state.country_choice else None
 counts=catalog.country_counts(query,search_year,strict,unknown)
 fc=catalog.map_for_year(year)
 # Inline v2 component: data enters through JSON, never by HTML string interpolation.
 @st.cache_resource
 def map_renderer():
  return st.components.v2.component('autoverse_korean_world_map',html=(ROOT/'map_component.html').read_text(),css=(ROOT/'map_component.css').read_text(),js=(ROOT/'map_component.js').read_text())
 map_result=map_renderer()(data={'year':year,'features':fc['features'],'counts':counts,'selected_codes':st.session_state.selected_codes,'selected_feature':st.session_state.selected_feature,'all_labels':st.session_state.all_country_labels},default={},on_selection_change=map_selection_changed,key='world_map',width='stretch',height='content')
 st.caption(f'지도 경계: {year}년 · 목록: '+(f'{year}년' if scope=='선택 연도' else scope)+' · 국가명은 확대하거나 가리켜 확인할 수 있습니다.')
 a,b,c,d=st.columns([1.2,1.4,1.7,1.3])
 with a:st.selectbox('검색 연도 범위',['선택 연도','전체 연도','연도 미확인'],key='year_scope',on_change=filters_changed)
 country_values=['']+sorted(counts,key=catalog.country_name)
 if st.session_state.country_choice=='@map':country_values.insert(1,'@map')
 if st.session_state.country_choice not in country_values:country_values.append(st.session_state.country_choice)
 with b:
  choice=st.selectbox('제조사 국적',country_values,format_func=lambda code,region=st.session_state.selected_region:'모든 국가' if not code else ('지도 선택 · '+region if code=='@map' else catalog.country_name(code)),key='country_choice',on_change=filters_changed)
 countries=tuple(st.session_state.selected_codes or []) if choice=='@map' else (choice,) if choice else None
 if choice!='@map':st.session_state.selected_codes=list(countries) if countries else None
 options=catalog.maker_options(query,search_year,countries,strict,unknown);names={row['maker_key']:row['name_ko'] for row in options};names['']='모든 제조사'
 if st.session_state.maker_choice not in names:st.session_state.maker_choice=''
 with c:st.selectbox('제조사',list(names),format_func=lambda key:names[key],key='maker_choice',on_change=filters_changed)
 with d:st.checkbox('확인된 모델 연식만',key='strict_model',on_change=filters_changed,help='등록·최초 사용·형식승인·관측 연도는 제외하고 모델 연식으로 분류된 기록만 표시합니다.')
 if choice:st.button('국가 선택 해제',on_click=clear_country)
 result=catalog.search(query,search_year,countries,st.session_state.maker_choice,strict,unknown,st.session_state.page_number)
 st.markdown('<div class="result-summary">'+f"검색 결과 <b>{result['total']:,}건</b> · {result['page']}/{result['pages']}페이지"+'</div>',unsafe_allow_html=True)
 if not result['rows']:
  st.info('선택한 조건에 해당하는 기록이 없습니다. 연도 범위를 넓히거나 국가·제조사 조건을 해제해 보세요.')
  if choice=='@map' and not countries:st.caption('이 역사 국가에 대응하는 제조사 국적은 아직 연결되지 않았습니다. 국가 목록이나 이름 검색을 이용할 수 있습니다.')
 for start in range(0,len(result['rows']),3):
  cols=st.columns(3)
  for col,record in zip(cols,result['rows'][start:start+3]):
   with col:
    with st.container(border=True):
     try:
      extra=catalog.load_details(record['vehicle_id']);photos=extra.get('photos',[]);thumbnail=catalog.photo_location(photos[0]) if photos and isinstance(photos[0],dict) else None
     except (ValueError,OSError,json.JSONDecodeError):thumbnail=None
     if thumbnail:st.image(thumbnail,width='stretch')
     else:st.markdown('<div class="photo-pending">사진 준비 중</div>',unsafe_allow_html=True)
     st.markdown('<div class="car-meta">'+html.escape(record['maker_ko'])+' · '+html.escape(catalog.country_name(record['origin_code']))+'</div><div class="car-title">'+html.escape(record['model_ko'])+'</div>',unsafe_allow_html=True)
     label=str(record['year'])+'년' if record['year'] else '연도 미확인'
     st.markdown('<span class="tag">'+label+'</span><span class="tag">'+html.escape(record['year_label_ko'])+'</span>',unsafe_allow_html=True)
     if st.button('자세히 보기',key='open_'+record['vehicle_id'],width='stretch'):
      st.session_state.selected_vehicle=record['vehicle_id'];st.rerun()
 if result['pages']>1:
  prev,page_label,nxt=st.columns([1,3,1])
  with prev:
   if st.button('← 이전',disabled=result['page']<=1):st.session_state.page_number=result['page']-1;st.rerun()
  with page_label:st.caption(f"한 페이지 18건 · 전체 {result['pages']:,}페이지")
  with nxt:
   if st.button('다음 →',disabled=result['page']>=result['pages']):st.session_state.page_number=result['page']+1;st.rerun()
 with st.expander('자료 범위와 지도 출처'):
  st.write(f"1단계 기존 차량 기록 {m['master_records']:,}건과 추가 명칭 자료 {m['additional_nameplate_records']:,}건을 검색용으로 연결했습니다. 2단계 자료를 병합한 결과가 아닙니다.")
  st.write('확인되지 않은 제조사 국적은 판매·등록 국가로 대신 채우지 않고 국적 확인 중으로 표시합니다. 추가 명칭 자료의 연도는 임의로 추정하지 않습니다.')
  st.write('역사 국경은 원자료의 시기별 근사 경계이며 국가명·영토 범위에 여러 해석이 있을 수 있습니다.')
  st.link_button('역사 국경 원자료와 이용 조건','https://github.com/Seshat-Global-History-Databank/cliopatria')
  st.link_button('현대 국경 원자료','https://www.naturalearthdata.com/')
except (OSError,ValueError,KeyError,json.JSONDecodeError) as error:
 st.error('탐색 자료를 읽지 못했습니다. 배포 파일의 data 폴더와 분할 자료가 모두 있는지 확인해 주세요.')
 with st.expander('오류 내용'):st.code(str(error))
