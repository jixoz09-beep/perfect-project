"""Vehicle exploration, maps, filters and detail pages."""

from __future__ import annotations

import html
import importlib.util
import json
import math
import os
import re
from pathlib import Path

import streamlit as st

from .vehicle_photos import (
    _av_user_photo,
    _card_photo,
    _photo_candidates_for,
    _show_photo_candidate,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = Path(__file__).with_name("catalog.py")
MAP_PATH = Path(__file__).with_name("map")

def _catalog_deployment_revision():
 # Include upload changes as well as source changes in the module cache key.
 roots=[ROOT/'data',*ROOT.glob('*/data'),*ROOT.glob('*/*/data')]
 configured=os.environ.get('AUTOVERSE_DATA_DIR')
 if configured:roots=[Path(configured)]
 revision=[]
 for directory in sorted(set(roots)):
  if not directory.is_dir():continue
  paths=[directory,directory/'maps',directory/'details',directory/'photos',
         directory/'catalog_manifest.json',directory/'countries_ko.json',
         directory/'maps/manifest.json',*directory.glob('catalog.sqlite.gz.part*')]
  for path in paths:
   try:
    info=path.stat();revision.append((str(path),info.st_size,info.st_mtime_ns))
   except OSError:pass
 for path in [ROOT/'autoverse_records_manifest.json',ROOT/'autoverse_records.sqlite.xz']:
  try:
   info=path.stat();revision.append((str(path),info.st_size,info.st_mtime_ns))
  except OSError:pass
 return (configured or '', CATALOG_PATH.stat().st_mtime_ns, tuple(revision))

@st.cache_resource(show_spinner=False)
def _catalog_runtime(data_revision):
    spec = importlib.util.spec_from_file_location("autoverse_catalog_snapshot", CATALOG_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@st.cache_resource(show_spinner=False)
def _map_renderer(markup, styles, script):
    return st.components.v2.component(
        "autoverse_korean_world_map", html=markup, css=styles, js=script
    )


DEFAULTS={'query':'','map_year':2026,'year_scope':'판매 확인 연도','strict_model':False,'country_choice':'','maker_choice':'','selected_codes':None,'selected_feature':None,'selected_region':'','selected_vehicle':None,'page_number':1,'all_country_labels':False}

def query_changed():st.session_state.page_number=1;st.session_state.selected_vehicle=None

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
 st.session_state.update(selected_codes=p.get('country_codes',[]),selected_feature=p['id'],selected_region=p['name_ko'],country_choice='@map',year_scope='판매 확인 연도',maker_choice='',page_number=1)


def show():
    for key, default in DEFAULTS.items():
        st.session_state.setdefault(key, st.session_state.get("explorer_settings", {}).get(key, default))
    st.session_state.explorer_settings = {key: st.session_state[key] for key in DEFAULTS}
    catalog = _catalog_runtime(_catalog_deployment_revision())

    def research_browser(vehicle=None):
        _, manifest = catalog.research_manifest()
        key = 'av_research_' + (vehicle['vehicle_id'] if vehicle else 'all')
        identity = (vehicle['maker_key'],vehicle['av_root']) if vehicle and vehicle.get('av_root') else ()
        if vehicle:
            if not identity or not st.toggle('이 모델의 등록·제원 조사 기록 보기',key=key+'_open'):
                return
            st.caption('제조사와 모델명이 대응하는 원자료입니다. 해당 카드의 세대·차체에 적용되는 제원은 위 표에서 확인할 수 있습니다.')
            query,source = '', ''
        else:
            st.subheader('1·2단계 조사 기록')
            st.caption('등록·형식승인·기술 자료에 나온 차량과 제원을 검색할 수 있습니다. 기간은 원자료가 기록한 연도 기준으로 표시됩니다.')
            query = st.text_input('조사 기록 검색',placeholder='예: Golf, Volkswagen Golf, 아반떼',key=key+'_query')
            labels = manifest.get('source_labels',{})
            source = st.selectbox('조사 출처',['',*sorted(manifest.get('sources',{}),key=lambda s:labels.get(s,s))],
                                 format_func=lambda value:labels.get(value,value) if value else '모든 출처',key=key+'_source')
        marker = (query,source)
        if st.session_state.get(key+'_marker') != marker:
            st.session_state[key+'_marker'] = marker
            st.session_state[key+'_page'] = 1
        total, rows, page = catalog.research_search(query,source,st.session_state.get(key+'_page',1),identity)
        if not rows:
            st.info('검색 조건에 맞는 조사 기록이 없습니다.')
            return
        labels = manifest.get('source_labels',{})
        last = (total+19)//20
        st.caption(f'조사 기록 {total:,}개 · {page:,}/{last:,}페이지')
        table=[]
        for row in rows:
            year = str(row['recorded_year']) if row['recorded_year'] else ''
            if row['report_year']:
                year += (' · ' if year else '') + f"보고 {row['report_year']}"
            table.append({'제조사':catalog.maker_display_label(row['brand'],row['maker']) if row['maker'] else '미상','원본 모델명':row['model'] or '미상',
                          '기록연도':year,'시장·등록지':row['market'],'차체·분류':row['body'],
                          '출처':labels.get(row['source'],row['source']),'조사 행':row['n']})
        st.dataframe(table,hide_index=True,width='stretch')
        prior,next_page=st.columns(2)
        if prior.button('이전 조사 기록',key=key+'_prior',disabled=page<=1):
            st.session_state[key+'_page']=page-1
            st.rerun()
        if next_page.button('다음 조사 기록',key=key+'_next',disabled=page>=last):
            st.session_state[key+'_page']=page+1
            st.rerun()
        titles={r['id']:f"{catalog.maker_display_label(r['brand'],r['maker']) if r['maker'] else '제조사 미상'} {r['model']} · {r['market'] or '시장 미상'} · {labels.get(r['source'],r['source'])}" for r in rows}
        selected=st.selectbox('제원을 볼 기록',list(titles),index=None,format_func=titles.get,key=key+'_id_'+str(rows[0]['id']))
        if selected is None:
            return
        row=catalog.research_record(selected)
        if not row:
            return
        if row['year_basis']:
            st.caption(row['year_basis'])
        if row['fuel']:
            st.caption('연료 '+row['fuel'])
        if row['specifications']:
            st.dataframe(row['specifications'],hide_index=True,width='stretch')
        else:
            st.caption('이 원자료에 기록된 수치 제원이 없습니다.')
        if row['reference']:
            st.caption('원자료 참조 '+row['reference'])
        for url in json.loads(row['urls']):
            if re.match(r'^https?://',url):
                st.link_button('원자료 보기',url)


    def details_view(record):
     st.button('← 검색 결과로 돌아가기',on_click=lambda:st.session_state.update(selected_vehicle=None))
     st.markdown('<div class="eyebrow">자동차 살펴보기</div>',unsafe_allow_html=True)
     st.title(record['model_ko']);st.caption(record['maker_ko']+' · '+catalog.country_name(record['origin_code'])+' · '+catalog.identity_year_label(record))
     badges=catalog.identity_badges(record)
     if badges:st.caption(' · '.join(badges))
     if record.get('scope')=='sale':
      st.caption('판매 개시 또는 판매 실적이 확인된 달력 연도입니다. 제조사 국적과 판매 지역을 구분합니다.')
     elif record.get('scope')=='release':
      st.caption('제조사가 기록한 출시연도입니다.')
     else:
      st.caption('표시 연도는 연결 자료의 연도 범위입니다. 제조사 국적 기준으로 표시합니다.')
     st.caption('같은 모델·세대·페이스리프트·차체의 연식과 트림을 묶었습니다. 제원은 수치 범위(~) 또는 항목 목록(,)으로 표시합니다.')
     try:detail=catalog.load_group_details(record['vehicle_id'])
     except (ValueError,OSError,json.JSONDecodeError):detail={};st.warning('상세 자료 연결 정보를 확인해야 합니다.')
     for market, evidence, url in detail.get('calendar_evidence',()):
      st.caption(market+' · '+evidence)
     if detail.get('origin_note_ko'):st.caption(detail['origin_note_ko'])
     if detail.get('linked_original_count',0)>1:st.caption(f"원자료 {detail['linked_original_count']:,}건의 제원을 연결한 차량입니다.")
     photo_tab,history_tab,spec_tab=st.tabs(['사진','역사','제원'])
     with photo_tab:
      photos=detail.get('photos',[])
      locations=[(catalog.photo_location(p),p.get('caption_ko','')) for p in photos if isinstance(p,dict)]
      locations=[p for p in locations if p[0]]
      chosen_photo=_card_photo(record)
      if chosen_photo:st.image(chosen_photo,width='stretch')
      else:
       if not locations:st.markdown('<div class="detail-pending">자동차 사진을 준비하고 있습니다.</div>',unsafe_allow_html=True)
       for location,caption in locations:st.image(location,caption=caption or None,width='stretch')
      for candidate in ([] if chosen_photo else _photo_candidates_for(record) if not record.get('scope') else []):
       with st.expander('사진 후보 · 검토 중'):
        _show_photo_candidate(candidate)
        st.caption('차종·세대·변경 모델·촬영 각도와 이용 조건을 확인 중인 후보입니다.')
     with history_tab:
      history=detail.get('history_ko')
      if history:
       st.write(history)
       if detail.get('history_scope_ko'):st.caption(detail['history_scope_ko'])
      else:st.markdown('<div class="detail-pending">이 자동차의 역사 자료를 준비하고 있습니다.</div>',unsafe_allow_html=True)
     with spec_tab:
      specs=detail.get('specifications',[])
      if detail.get('research_unsourced'):st.caption('원본 시트에 출처 링크가 없는 제원도 포함돼 있습니다.')
      if specs:
       units={'mm':'밀리미터','m':'미터','kg':'킬로그램','kW':'킬로와트','hp':'마력','cc':'세제곱센티미터','kWh':'킬로와트시','km':'킬로미터','N·m':'뉴턴미터','g/km':'그램/킬로미터'}
       rows=[]
       for spec in specs:
        if not isinstance(spec,dict) or not spec.get('label_ko'):continue
        value=spec.get('value')
        if value is None and spec.get('min') is not None and spec.get('max') is not None:value=str(spec['min'])+' ~ '+str(spec['max'])
        rows.append({'항목':spec['label_ko'],'값':str(value) if value is not None else '준비 중','단위':units.get(spec.get('unit'),spec.get('unit_ko',spec.get('unit','')))})
       if rows:st.dataframe(rows,hide_index=True,width='stretch')
      else:
       st.markdown('<div class="detail-pending">제원 자료를 준비하고 있습니다.</div>',unsafe_allow_html=True)
      if catalog.research_manifest()[1]:
       research_browser(record)
     if detail.get('sources'):
      with st.expander('자료 출처'):
       for source in detail['sources']:
        if isinstance(source,dict) and re.match(r'^https://',source.get('url','')):st.link_button(source.get('label_ko','원본 자료 보기'),source['url'])
     with st.expander('이 기록에 대한 안내'):
      st.write('차량 식별번호를 유지해 사진·역사·제원을 연결하는 구조입니다. 현재 화면에서 비어 있는 자료는 확인된 내용이 추가되면 표시됩니다.')
      st.write('원자료의 모델 연식·등록연도·세대 시작연도는 서로 다른 기준입니다. 한국어 명칭은 정식 국내 판매명과 읽기 표기가 함께 포함되어 있습니다.')
      labels={'calendar_sale':'판매 확인 자료','manufacturer_release':'제조사 출시 기록',
              'nameplate':'추가 명칭 자료','historical':'출처를 확인한 역사 보완 자료'}
      st.caption(labels.get(record['source_kind'],'1단계 차량 목록'))

    # The workshop remains available before the exploration data is uploaded.
    required=['catalog_manifest.json','countries_ko.json','maps/manifest.json']
    missing=[name for name in required if not (catalog.DATA/name).is_file()]
    if not missing:
     try:
      _deployment_manifest=catalog._base_manifest()
      missing += [p['file'] for p in _deployment_manifest.get('parts',[]) if not (catalog.DATA/p['file']).is_file()]
     except (OSError,ValueError,KeyError,json.JSONDecodeError):
      missing=['catalog_manifest.json 형식 확인 필요']
    if missing:
     st.title('자동차 탐색 자료를 연결해 주세요')
     st.info('기능 2에서 자동차 제작과 바로 주행을 사용할 수 있습니다. 자동차 탐색은 검색 자료와 지도를 업로드하면 열립니다.')
     st.warning('data 폴더와 01·02·03 업로드 분류 폴더 안의 data를 자동으로 확인했습니다. 아래에 표시된 자료가 저장소에 있는지 확인해 주세요.')
     if st.button('탐색 자료 다시 확인',key='rescan_explorer_data'):
      _catalog_runtime.clear()
      st.rerun()
     with st.expander('없는 파일과 업로드 위치 확인'):
      st.write('아래 파일을 data 폴더의 해당 위치에 올려 주세요.')
      for name in missing:st.code('data/'+name,language=None)
      st.caption('확인한 자료 폴더')
      folders=[ROOT/'data',*ROOT.glob('*/data'),*ROOT.glob('*/*/data')]
      if os.environ.get('AUTOVERSE_DATA_DIR'):folders=[Path(os.environ['AUTOVERSE_DATA_DIR'])]
      for folder in sorted(set(folders)):
       if folder.is_dir():
        label=folder.relative_to(ROOT).as_posix() if folder.is_relative_to(ROOT) else '별도로 지정한 자료 폴더'
        st.code(label,language=None)
     st.stop()

    try:
     m=(catalog._base_manifest() if st.session_state.year_scope in ('판매 확인 연도','판매 확인 전체 연도','제조사 출시 기록') else catalog.manifest());years=sorted({int(y) for y in m['year_counts'] if y!='unknown'} | catalog.sales_years())
     if st.session_state.selected_vehicle:
      for name in ('query','map_year','year_scope','strict_model','country_choice','maker_choice','all_country_labels'):
       st.session_state[name]=st.session_state[name]
      record=catalog.vehicle(st.session_state.selected_vehicle)
      if record:details_view(record);st.stop()
      st.session_state.selected_vehicle=None
     st.markdown('<div class="eyebrow">첫 번째 기능 · 탐색</div>',unsafe_allow_html=True)
     left,right=st.columns([3,1])
     with left:
      st.title('자동차의 시간을 여행하세요')
      st.markdown('<p class="hero-line">지도의 국가를 누르거나 이름을 검색해 자동차를 만나보세요.<br>국가는 판매 지역이 아닌 제조사의 국적을 기준으로 연결합니다.</p>',unsafe_allow_html=True)
     with right:
      st.metric('검색 가능한 원자료',f"{m['records']:,}건")
      st.caption('차량 목록과 추가 명칭·역사 보완 자료 · 고유 차종 수와 다릅니다.')
     if catalog.research_manifest()[1] and st.toggle('1·2단계 조사 기록 찾아보기',key='research_mode'):
      research_browser()
      st.stop()
     st.text_input('자동차·제조사 이름 검색',placeholder='예: 아반떼, 아우디, 롤스로이스, 비엠더블유',key='query',on_change=query_changed)
     year_col,labels_col=st.columns([5,1])
     with year_col:st.select_slider('세계지도 연도',options=years,key='map_year',format_func=lambda y:f'{y}년',on_change=year_changed)
     with labels_col:st.checkbox('모든 국가명',key='all_country_labels')
     query=st.session_state.query;year=st.session_state.map_year;scope=st.session_state.year_scope;strict=st.session_state.strict_model
     scopes=['판매 확인 연도','판매 확인 전체 연도','제조사 출시 기록','자료 기록연도','전체 차량 자료','연도 미확인']
     if scope not in scopes:
      scope={'선택 연도':'판매 확인 연도','전체 연도':'전체 차량 자료'}.get(scope,scopes[0])
      st.session_state.year_scope=scope
     sale_scope='sale' if scope.startswith('판매 확인') else 'release' if scope=='제조사 출시 기록' else ''
     search_year=None if scope in ('판매 확인 전체 연도','전체 차량 자료','연도 미확인') else year
     unknown=scope=='연도 미확인'
     if st.session_state.country_choice!='@map':st.session_state.selected_codes=[st.session_state.country_choice] if st.session_state.country_choice else None
     counts=(catalog.sales_country_counts(query,search_year,sale_scope) if sale_scope
             else catalog.country_counts(query,search_year,strict,unknown))
     fc=catalog.map_for_year(year)
     # Inline v2 component: data enters through JSON, never by HTML string interpolation.
     map_renderer = _map_renderer(
      (MAP_PATH / 'world.html').read_text(encoding='utf-8'),
      (MAP_PATH / 'world.css').read_text(encoding='utf-8'),
      (MAP_PATH / 'world.js').read_text(encoding='utf-8'),
     )
     map_result=map_renderer(data={'year':year,'features':fc['features'],'counts':counts,'selected_codes':st.session_state.selected_codes,'selected_feature':st.session_state.selected_feature,'all_labels':st.session_state.all_country_labels},default={},on_selection_change=map_selection_changed,key='world_map',width='stretch',height='content')
     if year<1970:st.info('이 시기의 차량 자료는 일부만 수록되어 있습니다. 검색 연도 범위에서 제조사 출시 기록이나 전체 차량 자료를 볼 수 있습니다.')
     st.caption(f"지도 경계: {fc.get('boundary_year',year)}년"+(' 참고 자료' if fc.get('boundary_year',year)!=year else '')+' · 목록: '+(f'{year}년 · {scope}' if search_year is not None else scope)+' · 국가명은 확대하거나 가리켜 확인할 수 있습니다.')
     a,b,c,d=st.columns([1.2,1.4,1.7,1.3])
     with a:st.selectbox('검색 연도 범위',scopes,key='year_scope',on_change=filters_changed)
     country_values=['']+sorted(counts,key=catalog.country_name)
     if st.session_state.country_choice=='@map':country_values.insert(1,'@map')
     if st.session_state.country_choice not in country_values:country_values.append(st.session_state.country_choice)
     with b:
      choice=st.selectbox('제조사 국적',country_values,format_func=lambda code,region=st.session_state.selected_region:'모든 국가' if not code else ('지도 선택 · '+region if code=='@map' else catalog.country_name(code)),key='country_choice',on_change=filters_changed)
     countries=tuple(st.session_state.selected_codes or []) if choice=='@map' else (choice,) if choice else None
     if choice!='@map':st.session_state.selected_codes=list(countries) if countries else None
     options=(catalog.sales_maker_options(query,search_year,countries,sale_scope) if sale_scope else
              catalog.maker_options(query,search_year,countries,strict,unknown))
     names={row['maker_key']:row['name_ko'] for row in options};names['']='모든 제조사'
     if st.session_state.maker_choice not in names:st.session_state.maker_choice=''
     with c:st.selectbox('제조사',list(names),format_func=lambda key:names[key],key='maker_choice',on_change=filters_changed)
     if not sale_scope:
      with d:st.checkbox('확인된 모델 연식만',key='strict_model',on_change=filters_changed,help='자료 기록 가운데 모델 연식으로 분류된 기록을 표시합니다.')
     if choice:st.button('국가 선택 해제',on_click=clear_country)
     result=(catalog.sales_search(query,search_year,countries,st.session_state.maker_choice,sale_scope,st.session_state.page_number)
             if sale_scope else
             catalog.search(query,search_year,countries,st.session_state.maker_choice,strict,unknown,st.session_state.page_number))
     st.markdown('<div class="result-summary">'+f"중복 통합 차량 <b>{result['total']:,}대</b> · {result['page']}/{result['pages']}페이지"+'</div>',unsafe_allow_html=True)
     if sale_scope:
      with st.expander('판매 자료 집계'):
       st.table([catalog.sales_totals()])
     else:
      with st.expander('전체 차량 중복 및 국가 집계 검증'):
       st.caption('선택한 연도의 전체 제조사별 중복 상위 30개와 국가별 표시 차량 수를 검사할 수 있습니다. 원본 DB는 수정하지 않습니다.')
       if st.button('전체 분류 집계',key='av_classification_audit'):
        st.table([catalog.classification_counts()])
       if st.button('중복 상위 30개 검사',key='av_global_audit'):
        st.dataframe(catalog.duplicate_hotspots(year,30),hide_index=True,width='stretch')
       if st.button('전체 국가별 차종 수 검사',key='av_country_audit'):
        totals=catalog.country_counts('',year,False,False)
        ranked=[{'국가':catalog.country_name(c),'국가코드':c,'표시 차량':n} for c,n in sorted(totals.items(),key=lambda x:(-x[1],x[0]))]
        st.dataframe(ranked,hide_index=True,width='stretch')
     if not result['rows']:
      st.info('현재 수록 자료에서 선택한 조건에 맞는 기록을 찾지 못했습니다. 해당 시기에 자동차가 없었다는 뜻은 아닙니다. 연도·국가·제조사 조건을 확인해 주세요.')
      if strict and not sale_scope:st.caption('확인된 모델 연식만 켜면 생산 기간·제작연도·공개연도 자료는 제외됩니다.')
      if choice=='@map' and not countries:st.caption('이 역사 국가에 대응하는 제조사 국적은 아직 연결되지 않았습니다. 국가 목록이나 이름 검색을 이용할 수 있습니다.')
     for start in range(0,len(result['rows']),3):
      cols=st.columns(3)
      for col,record in zip(cols,result['rows'][start:start+3]):
       with col:
        with st.container(border=True):
         try:
          extra=catalog.load_details(record['vehicle_id']);photos=extra.get('photos',[]);thumbnail=catalog.photo_location(photos[0]) if photos and isinstance(photos[0],dict) else None
         except (ValueError,OSError,json.JSONDecodeError):thumbnail=None
         candidates=_photo_candidates_for(record) if not thumbnail and not record.get('scope') else []
         chosen_photo=_card_photo(record)
         if chosen_photo:st.image(chosen_photo,width='stretch')
         elif thumbnail:st.image(thumbnail,width='stretch')
         elif candidates:
          try:st.image(candidates[0]['image_url_for_trial'],caption='사진 후보 · 검토 중',width='stretch')
          except Exception:st.markdown('<div class="photo-pending">사진 후보 확인 중</div>',unsafe_allow_html=True)
         else:st.markdown('<div class="photo-pending">사진 준비 중</div>',unsafe_allow_html=True)
         st.markdown('<div class="car-meta">'+html.escape(record['maker_ko'])+' · '+html.escape(catalog.country_name(record['origin_code']))+'</div><div class="car-title">'+html.escape(record['model_ko'])+'</div>',unsafe_allow_html=True)
         tags=[catalog.identity_year_label(record),*catalog.identity_badges(record)]
         st.markdown(''.join('<span class="tag">'+html.escape(tag)+'</span>' for tag in tags),unsafe_allow_html=True)
         if st.button('자세히 보기',key='open_'+record['vehicle_id'],width='stretch'):
          st.session_state.selected_vehicle=record['vehicle_id'];st.rerun()
     if result['pages']>1:
      prev,page_label,nxt=st.columns([1,3,1])
      with prev:
       if st.button('← 이전',disabled=result['page']<=1):st.session_state.page_number=result['page']-1;st.rerun()
      with page_label:st.caption(f"한 페이지 18대 · 전체 {result['pages']:,}페이지")
      with nxt:
       if st.button('다음 →',disabled=result['page']>=result['pages']):st.session_state.page_number=result['page']+1;st.rerun()
     with st.expander('자료 범위와 지도 출처'):
      st.write('판매 확인 목록은 정부와 제조사에서 확인한 달력 연도의 판매 실적과 판매 개시를 사용합니다. 제조사 출시 기록과 기존 차량 자료도 검색 연도 범위에서 볼 수 있습니다.')
      st.write(f"기존 차량 기록 {m['master_records']:,}건과 추가 명칭 자료 {m['additional_nameplate_records']:,}건을 검색용으로 연결했습니다.")
      if m.get('integrated_statistics'):
       linked=m['integrated_statistics']
       st.write(f"기존 차량 ID에 연결된 1·2단계 제원 {linked.get('vehicles_with_specifications',0):,}건과 역사 설명 {linked.get('history_linked_existing_ids',0):,}건을 표시합니다.")
       st.caption('차량 식별이 확정되지 않은 별도 원자료와 이름·연식이 맞지 않는 항목은 연결을 보류했습니다.')
      if m.get('historical_records'):st.write(f"출처를 확인해 보완한 역사 기록 {m['historical_records']:,}건을 별도로 포함합니다.")
      st.write('확인되지 않은 제조사 국적은 판매·등록 국가로 대신 채우지 않고 국적 확인 중으로 표시합니다. 추가 명칭 자료의 연도는 임의로 추정하지 않습니다.')
      st.write('역사 국경은 원자료의 시기별 근사 경계이며 국가명·영토 범위에 여러 해석이 있을 수 있습니다.')
      st.link_button('역사 국경 원자료와 이용 조건','https://github.com/Seshat-Global-History-Databank/cliopatria')
      st.link_button('현대 국경 원자료','https://www.naturalearthdata.com/')
    except (OSError,ValueError,KeyError,json.JSONDecodeError) as error:
     st.error('탐색 자료를 읽지 못했습니다. 배포 파일의 data 폴더와 분할 자료가 모두 있는지 확인해 주세요.')
     with st.expander('오류 내용'):st.code(str(error))
