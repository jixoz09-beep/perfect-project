from __future__ import annotations
import html,json,math,re,os,types
from pathlib import Path
import streamlit as st
ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='오토버스 · 자동차 탐색과 제작',page_icon='🚘',layout='wide',initial_sidebar_state='collapsed')
# Fixed application source: bundled so a missing catalog.py cannot prevent startup.
_CATALOG_SOURCE = '"""Read-only vehicle search and optional, separately supplied detail records."""\nfrom __future__ import annotations\nimport functools,gzip,hashlib,json,os,re,shutil,sqlite3,tempfile,urllib.parse\nfrom pathlib import Path\nfrom contextlib import contextmanager\nROOT=Path(__file__).resolve().parent\n_DATA_STAGING=None\n_DATA_ERROR=None\ndef _deployment_data():\n """Read either a normal data folder or the original split upload folders."""\n global _DATA_STAGING,_DATA_ERROR\n if os.environ.get(\'AUTOVERSE_DATA_DIR\'):\n  return Path(os.environ[\'AUTOVERSE_DATA_DIR\']).resolve()\n roots=[]\n direct=ROOT/\'data\'\n if direct.is_dir():roots.append(direct.resolve())\n # GitHub may contain the numbered upload folders themselves, optionally\n # inside one extra folder created when extracting the download.\n candidates=list(ROOT.glob(\'*/data\'))+list(ROOT.glob(\'*/*/data\'))\n for path in sorted(candidates):\n  if not path.is_dir():continue\n  if not ((path/\'catalog_manifest.json\').is_file() or\n          (path/\'maps/manifest.json\').is_file() or\n          any(path.glob(\'catalog.sqlite.gz.part*\'))):continue\n  resolved=path.resolve()\n  if resolved not in roots:roots.append(resolved)\n if not roots:return direct.resolve()\n if len(roots)==1:return roots[0]\n # Build a read-only view without changing any uploaded file. Hard links\n # avoid duplicating the data on the same filesystem; copy only if needed.\n _DATA_STAGING=tempfile.TemporaryDirectory(prefix=\'autoverse_data_view_\')\n merged=Path(_DATA_STAGING.name)\n for source in roots:\n  for path in sorted(source.rglob(\'*\')):\n   if not path.is_file() or not path.resolve().is_relative_to(source):continue\n   relative=path.relative_to(source);target=merged/relative\n   if target.exists():\n    identical=target.stat().st_size==path.stat().st_size\n    if identical:\n     with target.open(\'rb\') as a,path.open(\'rb\') as b:\n      identical=hashlib.file_digest(a,\'sha256\').digest()==hashlib.file_digest(b,\'sha256\').digest()\n    if not identical:_DATA_ERROR=\'서로 다른 버전의 탐색 자료가 중복되어 있습니다: \'+relative.as_posix()\n    continue\n   target.parent.mkdir(parents=True,exist_ok=True)\n   try:os.link(path,target)\n   except OSError:shutil.copyfile(path,target)\n return merged\nDATA=_deployment_data()\n@functools.lru_cache(maxsize=1)\ndef manifest():\n if _DATA_ERROR:raise ValueError(_DATA_ERROR)\n return json.loads((DATA/\'catalog_manifest.json\').read_text(encoding=\'utf-8\'))\n@functools.lru_cache(maxsize=1)\ndef database_path():\n m=manifest();digest=m[\'sqlite_sha256\'];dest=Path(tempfile.gettempdir())/(\'autoverse_catalog_\'+digest[:20]+\'.sqlite\')\n if dest.exists() and dest.stat().st_size==m[\'sqlite_bytes\']:\n  with dest.open(\'rb\') as cached:\n   if hashlib.file_digest(cached,\'sha256\').hexdigest()==digest:return dest\n with tempfile.TemporaryDirectory(prefix=\'autoverse_unpack_\') as temporary:\n  compressed=Path(temporary)/\'catalog.gz\';output=Path(temporary)/\'catalog.sqlite\'\n  with compressed.open(\'wb\') as out:\n   for part in m[\'parts\']:\n    name=part[\'file\']\n    if Path(name).name!=name:raise ValueError(\'검색 자료 경로가 올바르지 않습니다.\')\n    path=DATA/name;h=hashlib.sha256()\n    with path.open(\'rb\') as f:\n     while block:=f.read(1024*1024):h.update(block);out.write(block)\n    if h.hexdigest()!=part[\'sha256\']:raise ValueError(\'검색 자료 파일이 손상되었습니다: \'+name)\n  h=hashlib.sha256()\n  with gzip.open(compressed,\'rb\') as src,output.open(\'wb\') as out:\n   while block:=src.read(1024*1024):h.update(block);out.write(block)\n  if h.hexdigest()!=digest:raise ValueError(\'검색 자료 무결성 검사를 통과하지 못했습니다.\')\n  # os.replace is atomic; concurrent readers only see a complete database.\n  os.replace(output,dest)\n return dest\n@contextmanager\ndef connection():\n con=sqlite3.connect(database_path().as_uri()+\'?mode=ro&immutable=1\',uri=True);con.row_factory=sqlite3.Row\n try:yield con\n finally:con.close()\ndef normalize(q):return re.sub(r\'[^a-z0-9가-힣ㄱ-ㅎ]\',\'\',str(q or \'\').lower())\nBASE=\' FROM vehicles v JOIN models n ON n.model_id=v.model_id JOIN makers m ON m.maker_id=n.maker_id \'\nFIELDS=\'v.vehicle_id,v.year,v.year_kind,v.year_label_ko,v.source_kind,n.name_ko AS model_ko,m.name_ko AS maker_ko,m.maker_key,m.origin_code\'\ndef conditions(query=\'\',year=None,countries=None,maker=None,strict_model=False,unknown_year=False):\n clauses=[];values=[];q=normalize(query)\n if year is not None:clauses.append(\'v.year=?\');values.append(int(year))\n if unknown_year:clauses.append(\'v.year IS NULL\')\n if countries is not None:\n  if not countries:clauses.append(\'0\')\n  else:clauses.append(\'COALESCE(m.origin_code,\\\'UNKNOWN\\\') IN (\'+\',\'.join(\'?\' for _ in countries)+\')\');values.extend(countries)\n if maker:clauses.append(\'m.maker_key=?\');values.append(maker)\n if strict_model:clauses.append("v.year_kind=\'model\'")\n if q:clauses.append(\'(n.search_text LIKE ? ESCAPE \\\'\\\\\\\' OR n.initials LIKE ? ESCAPE \\\'\\\\\\\' OR m.search_text LIKE ? ESCAPE \\\'\\\\\\\')\');values.extend([\'%\'+q+\'%\']*3)\n return (\' WHERE \'+\' AND \'.join(clauses)) if clauses else \'\',values\n@functools.lru_cache(maxsize=512)\ndef search(query=\'\',year=None,countries=None,maker=None,strict_model=False,unknown_year=False,page=1,page_size=18):\n countries=tuple(countries) if countries is not None else None;where,values=conditions(query,year,countries,maker,strict_model,unknown_year)\n page=max(1,int(page));page_size=min(60,max(1,int(page_size)))\n with connection() as con:\n  total=con.execute(\'SELECT COUNT(*)\'+BASE+where,values).fetchone()[0];pages=max(1,(total+page_size-1)//page_size);page=min(page,pages)\n  rows=con.execute(\'SELECT \'+FIELDS+BASE+where+\' ORDER BY m.name_ko,n.name_ko,v.year DESC,v.vehicle_id LIMIT ? OFFSET ?\',values+[page_size,(page-1)*page_size]).fetchall()\n return {\'total\':total,\'page\':page,\'pages\':pages,\'rows\':[dict(r) for r in rows]}\n@functools.lru_cache(maxsize=256)\ndef country_counts(query=\'\',year=None,strict_model=False,unknown_year=False):\n where,values=conditions(query,year,None,None,strict_model,unknown_year)\n with connection() as con:rows=con.execute("SELECT COALESCE(m.origin_code,\'UNKNOWN\') AS code,COUNT(*) AS n"+BASE+where+\' GROUP BY m.origin_code\',values).fetchall()\n return {r[\'code\']:r[\'n\'] for r in rows}\n@functools.lru_cache(maxsize=256)\ndef maker_options(query=\'\',year=None,countries=None,strict_model=False,unknown_year=False):\n where,values=conditions(query,year,countries,None,strict_model,unknown_year)\n with connection() as con:rows=con.execute(\'SELECT DISTINCT m.maker_key,m.name_ko\'+BASE+where+\' ORDER BY m.name_ko\',values).fetchall()\n return [dict(r) for r in rows]\ndef vehicle(vehicle_id):\n with connection() as con:row=con.execute(\'SELECT \'+FIELDS+BASE+\' WHERE v.vehicle_id=?\',(vehicle_id,)).fetchone()\n return dict(row) if row else None\n@functools.lru_cache(maxsize=8)\ndef map_for_year(year):\n index=json.loads((DATA/\'maps/manifest.json\').read_text());row=index.get(str(int(year)))\n if not row:raise ValueError(\'해당 연도의 지도 자료가 없습니다.\')\n path=DATA/\'maps\'/row[\'file\']\n if hashlib.sha256(path.read_bytes()).hexdigest()!=row[\'sha256\']:raise ValueError(\'지도 자료 무결성 검사를 통과하지 못했습니다.\')\n return json.loads(gzip.decompress(path.read_bytes()))\n@functools.lru_cache(maxsize=1)\ndef country_names():return json.loads((DATA/\'countries_ko.json\').read_text())\ndef country_name(code):return \'국적 확인 중\' if code==\'UNKNOWN\' or not code else country_names().get(code,\'국가명 확인 중\')\ndef load_details(vehicle_id):\n if not re.fullmatch(\'[A-Za-z0-9_-]{1,90}\',vehicle_id):return {}\n path=DATA/\'details\'/(vehicle_id+\'.json\')\n if not path.exists():return {}\n if path.stat().st_size>2*1024*1024:raise ValueError(\'상세 자료 파일 크기가 너무 큽니다.\')\n data=json.loads(path.read_text(encoding=\'utf-8\'))\n if not isinstance(data,dict):raise ValueError(\'상세 자료는 객체 형식이어야 합니다.\')\n if data.get(\'vehicle_id\')!=vehicle_id or data.get(\'schema_version\')!=1:raise ValueError(\'상세 자료의 차량 식별번호 또는 형식이 일치하지 않습니다.\')\n for key in (\'photos\',\'specifications\',\'sources\'):\n  if key in data and not isinstance(data[key],list):raise ValueError(\'상세 자료 목록 형식이 잘못되었습니다: \'+key)\n if data.get(\'history_ko\') is not None and not isinstance(data[\'history_ko\'],str):raise ValueError(\'역사 자료는 문장 형식이어야 합니다.\')\n return data\n\ndef photo_location(photo):\n location=photo.get(\'path\') or photo.get(\'url\')\n if not location:return None\n if \'://\' in location:\n  u=urllib.parse.urlparse(location)\n  if u.scheme!=\'https\' or not u.hostname or u.hostname in [\'localhost\',\'127.0.0.1\',\'::1\'] or u.username or u.password:return None\n  return location\n path=(DATA/location).resolve()\n if not path.is_relative_to(DATA) or path.suffix.lower() not in [\'.png\',\'.jpg\',\'.jpeg\',\'.webp\'] or not path.is_file():return None\n return str(path)\n'
_MAP_ASSETS = {'html': '<div class="world-map"><div class="map-actions"><button data-zoom="in" aria-label="지도 확대">＋</button><button data-zoom="out" aria-label="지도 축소">−</button><button data-zoom="reset">전체 보기</button></div><svg viewBox="0 0 1000 500" aria-label="연도별 세계지도" role="group"><g class="map-layer"></g></svg><div class="map-legend"><span><i></i>자동차 기록 있음</span><span><i class="selected"></i>선택한 국가</span><span>드래그로 이동 · 휠로 확대</span></div><div class="map-tooltip" hidden></div></div>\n', 'css': ".world-map{position:relative;width:100%;overflow:hidden;border:1px solid #294956;border-radius:18px;background:radial-gradient(ellipse at 48% 42%,#153844 0,#0c2632 65%,#081d27 100%);color:#ecf6f6;font-family:system-ui,'Noto Sans KR',sans-serif}\n.world-map svg{display:block;width:100%;height:480px;touch-action:none;user-select:none;cursor:grab}\n.world-map svg:active{cursor:grabbing}\n.country{fill:#234653;stroke:#64808a;stroke-width:.55;vector-effect:non-scaling-stroke;cursor:pointer;transition:fill .12s}\n.country.has-cars{fill:#387d82;stroke:#8fc6c3}\n.country:hover,.country:focus{fill:#b6d5b3;stroke:#f1ead6;outline:none}\n.country.selected{fill:#e4c780;stroke:#ffefbe;stroke-width:1.2}\n.country-label{fill:#b7d1d6;font-size:8px;text-anchor:middle;pointer-events:none;paint-order:stroke;stroke:#0c2632;stroke-width:2px}\n.country-label.active-label{fill:#f0f6e9;font-size:9px;font-weight:650}\n.graticule{fill:none;stroke:#56838a;stroke-opacity:.14;stroke-width:.6;pointer-events:none}\n.map-actions{position:absolute;top:14px;right:14px;display:flex;gap:5px;z-index:3}\n.map-actions button{border:1px solid #64808a;background:#102f3ddd;color:#eaf4f4;border-radius:8px;padding:6px 11px;cursor:pointer}\n.map-legend{position:absolute;bottom:13px;left:16px;display:flex;gap:14px;font-size:11px;color:#bdd1d4;pointer-events:none}\n.map-legend i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;background:#387d82}\n.map-legend i.selected{background:#e4c780}\n.map-tooltip{position:absolute;pointer-events:none;z-index:4;background:#f3f2e7;color:#183841;border-radius:7px;padding:8px 10px;font-size:12px;box-shadow:0 4px 18px #0004;min-width:120px}\n.map-tooltip[hidden]{display:none}\n@media(max-width:700px){.world-map svg{height:340px}\n.map-legend{font-size:10px;gap:8px}\n.country-label{font-size:9px}}\n", 'js': 'export default function(component){\n const {parentElement:root,data,setTriggerValue}=component;\n const NS=\'http://www.w3.org/2000/svg\',make=(tag,attrs={},text=null)=>{const e=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);if(text!==null)e.textContent=text;return e;};\n const container=root.querySelector(\'.world-map\'),svg=root.querySelector(\'svg\'),layer=root.querySelector(\'.map-layer\'),tooltip=root.querySelector(\'.map-tooltip\');let view=container.__autoverseView||{x:0,y:0,k:1},drag=null,moved=false,pointers=new Map();\n const apply=()=>{container.__autoverseView=view;layer.setAttribute(\'transform\',`translate(${view.x} ${view.y}) scale(${view.k})`);const rect=svg.getBoundingClientRect(),factor=1/Math.min(rect.width/1000,rect.height/500);for(const label of layer.querySelectorAll(\'.country-label\'))label.style.fontSize=(10*factor/view.k)+\'px\';},project=p=>[(p[0]+180)*1000/360,(90-p[1])*500/180];\n const ringPath=ring=>{let previous=null;return ring.map((p,i)=>{let lon=p[0];if(previous!==null){while(lon-previous>180)lon-=360;while(lon-previous< -180)lon+=360;}previous=lon;const x=(lon+180)*1000/360,y=(90-Math.max(-90,Math.min(90,p[1])))*500/180;return(i?\'L\':\'M\')+x.toFixed(2)+\',\'+y.toFixed(2);}).join(\'\')+\'Z\';};\n const click=f=>{if(moved)return;setTriggerValue(\'selection\',{feature_id:f.properties.id,year:data.year,nonce:Date.now()});};\n const counts=data.counts||{},selected=new Set(data.selected_codes||[]);layer.replaceChildren();\n // Grid is purely geographic and has no external map-service dependency.\n for(let lat=-60;lat<=60;lat+=30){const a=project([-180,lat]),b=project([180,lat]);layer.append(make(\'path\',{d:`M${a}L${b}`,class:\'graticule\'}));}\n for(let lon=-120;lon<=120;lon+=60){const a=project([lon,80]),b=project([lon,-75]);layer.append(make(\'path\',{d:`M${a}L${b}`,class:\'graticule\'}));}\n for(const f of data.features||[]){\n  const p=f.properties,codes=p.country_codes||[],number=codes.reduce((n,c)=>n+(counts[c]||0),0),isSelected=p.id===data.selected_feature||codes.some(c=>selected.has(c)),geometry=f.geometry,polygons=geometry.type===\'Polygon\'?[geometry.coordinates]:geometry.type===\'MultiPolygon\'?geometry.coordinates:[],group=make(\'g\');\n  const d=polygons.map(poly=>poly.map(ringPath).join(\'\')).join(\'\');if(!d)continue;\n  for(const shift of [-1000,0,1000]){const path=make(\'path\',{d,transform:`translate(${shift} 0)`,class:\'country\'+(number?\' has-cars\':\'\')+(isSelected?\' selected\':\'\'),tabindex:shift===0?\'0\':\'-1\',role:\'button\',\'aria-label\':p.name_ko+\' · \'+number.toLocaleString(\'ko-KR\')+\'건\',\'fill-rule\':\'evenodd\',\'data-feature\':p.id});path.append(make(\'title\',{},p.name_ko+\' · \'+number.toLocaleString(\'ko-KR\')+\'건\'));path.onclick=e=>{if(e.pointerType===\'touch\'||e.pointerType===\'pen\')return;click(f);};path.onkeydown=e=>{if(e.key===\'Enter\'||e.key===\' \'){e.preventDefault();moved=false;click(f);}};path.onpointermove=e=>{tooltip.textContent=p.name_ko+\' · \'+number.toLocaleString(\'ko-KR\')+\'건\';tooltip.hidden=false;const r=container.getBoundingClientRect();tooltip.style.left=Math.min(e.clientX-r.left+12,r.width-190)+\'px\';tooltip.style.top=Math.max(8,e.clientY-r.top-36)+\'px\';};path.onpointerleave=()=>tooltip.hidden=true;group.append(path);}\n  layer.append(group);\n  if(p.label_point){const[x,y]=project(p.label_point),label=make(\'text\',{x,y,class:\'country-label\'+(number?\' active-label\':\'\'),\'data-count\':number},p.name_ko);label.style.display=number||data.all_labels?\'\':\'none\';layer.append(label);}\n }\n const point=e=>{const rect=svg.getBoundingClientRect();const scale=Math.min(rect.width/1000,rect.height/500);return[(e.clientX-rect.left-(rect.width-1000*scale)/2)/scale,(e.clientY-rect.top-(rect.height-500*scale)/2)/scale];};\n const zoom=(factor,focus=[500,250])=>{const k=Math.max(1,Math.min(12,view.k*factor)),ratio=k/view.k;view.x=focus[0]-(focus[0]-view.x)*ratio;view.y=focus[1]-(focus[1]-view.y)*ratio;view.k=k;apply();};\n root.querySelector(\'[data-zoom="in"]\').onclick=()=>zoom(1.45);root.querySelector(\'[data-zoom="out"]\').onclick=()=>zoom(1/1.45);root.querySelector(\'[data-zoom="reset"]\').onclick=()=>{view={x:0,y:0,k:1};apply();};\n const wheel=e=>{e.preventDefault();zoom(Math.exp(-Math.max(-200,Math.min(200,e.deltaY))*.003),point(e));};svg.addEventListener(\'wheel\',wheel,{passive:false});\n svg.onpointerdown=e=>{pointers.set(e.pointerId,point(e));moved=false;drag={id:e.pointerId,start:point(e),x:view.x,y:view.y,feature:e.target?.dataset?.feature};if(e.pointerType!==\'mouse\')svg.setPointerCapture(e.pointerId);};\n svg.onpointermove=e=>{if(!pointers.has(e.pointerId))return;const old=pointers.get(e.pointerId),p=point(e);pointers.set(e.pointerId,p);if(pointers.size===2){const other=[...pointers].find(([id])=>id!==e.pointerId)[1],before=Math.hypot(old[0]-other[0],old[1]-other[1]),after=Math.hypot(p[0]-other[0],p[1]-other[1]);if(before>0)zoom(after/before,[(p[0]+other[0])/2,(p[1]+other[1])/2]);moved=true;return;}if(drag){const dx=p[0]-drag.start[0],dy=p[1]-drag.start[1];if(Math.hypot(dx,dy)>4)moved=true;if(moved){view.x=drag.x+dx;view.y=drag.y+dy;apply();}}};\n const release=e=>{const first=pointers.size===1,feature=drag?.feature;pointers.delete(e.pointerId);if(e.pointerType!==\'mouse\'&&first&&feature&&!moved){const f=data.features.find(f=>f.properties.id===feature);if(f)click(f);}drag=null;tooltip.hidden=true;};svg.onpointerup=release;window.addEventListener(\'pointerup\',release);svg.onpointercancel=e=>{pointers.delete(e.pointerId);drag=null;moved=true;};\n apply();return()=>{svg.removeEventListener(\'wheel\',wheel);window.removeEventListener(\'pointerup\',release);svg.onpointerdown=svg.onpointermove=svg.onpointerup=svg.onpointercancel=null;};\n}\n'}
@st.cache_resource
def _catalog_runtime():
 module=types.ModuleType('autoverse_embedded_catalog')
 module.__file__=str(ROOT/'catalog.py')
 exec(compile(_CATALOG_SOURCE,'<autoverse embedded catalog>','exec'),module.__dict__)
 return module
catalog=_catalog_runtime()

st.markdown('''<style>
#MainMenu,footer{visibility:hidden}.block-container{max-width:1460px;padding-top:2rem;padding-bottom:3rem}h1,h2,h3{letter-spacing:-.045em}h1{font-weight:750}h3{line-height:1.35}.eyebrow{font-size:11px;letter-spacing:.16em;color:#49766f;margin-bottom:10px}.hero-line{font-size:16px;color:#647a7a;line-height:1.8}.car-title{font-size:19px;font-weight:700;line-height:1.45;color:#183d45;margin:8px 0 4px}.photo-pending{height:110px;background:linear-gradient(145deg,#e4e9e3,#f3f2ea);border-radius:10px;display:flex;align-items:center;justify-content:center;color:#718783;font-size:12px;margin-bottom:12px;border:1px solid #d9e1d8}.car-meta{font-size:12px;color:#68807d}.tag{display:inline-block;background:#e6efeb;color:#35695f;border:1px solid #d4e2da;padding:3px 8px;border-radius:20px;font-size:10px;margin:0 4px 5px 0}.result-summary{color:#425e62;font-size:13px;margin:10px 0 18px}.detail-pending{padding:44px 22px;background:#eaece5;border-radius:14px;text-align:center;color:#70827d;border:1px dashed #bfcfc4}.stButton>button{border-radius:9px}div[data-testid=stMetricValue]{font-size:1.75rem}div[data-testid=stVerticalBlockBorderWrapper]{border-radius:14px}button:focus-visible{outline:3px solid #93beb0}
</style>''',unsafe_allow_html=True)
DEFAULTS={'app_page':'세계 자동차 탐색','query':'','map_year':2026,'year_scope':'선택 연도','strict_model':False,'country_choice':'','maker_choice':'','selected_codes':None,'selected_feature':None,'selected_region':'','selected_vehicle':None,'page_number':1,'all_country_labels':False}
for key,value in DEFAULTS.items():st.session_state.setdefault(key,st.session_state.get('explorer_settings',{}).get(key,value))
st.session_state.explorer_settings={key:st.session_state[key] for key in DEFAULTS}
nav,quick=st.columns([5,1])
with nav:page=st.radio('기능 선택',['세계 자동차 탐색','자동차 제작 작업실','3D 운전교실'],key='app_page',horizontal=True,label_visibility='collapsed')
with quick:st.button('바로 주행하기',key='quick_drive',on_click=lambda:st.session_state.update(app_page='3D 운전교실'))
if page=='3D 운전교실':
 if not (ROOT/'driving_runtime.py').is_file():
  st.warning('driving_runtime.py 파일이 없습니다. 압축을 풀어 main.py와 같은 폴더에 올려 주세요. 파일 이름에 괄호나 숫자가 붙지 않았는지도 확인하세요.')
  st.stop()
 import driving_runtime
 st.caption('종로 모티브 가상 도로 · 제작 차량과 10대의 주행 선택지')
 if hasattr(st,'iframe'):st.iframe(driving_runtime.driving_html(),height=900,alt='종로 3D 운전교실')
 else:
  import streamlit.components.v1 as components
  components.html(driving_runtime.driving_html(),height=900,scrolling=False)
 st.stop()
if page=='자동차 제작 작업실':
 if not (ROOT/'workshop_runtime.py').is_file():
  st.warning('workshop_runtime.py 파일이 없습니다. 압축을 풀어 main.py와 같은 폴더에 올려 주세요. 파일 이름에 괄호나 숫자가 붙지 않았는지도 확인하세요.')
  st.stop()
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

# The other two sections remain usable when exploration data is not uploaded yet.
required=['catalog_manifest.json','countries_ko.json','maps/manifest.json']
missing=[name for name in required if not (catalog.DATA/name).is_file()]
if not missing:
 try:
  _deployment_manifest=catalog.manifest()
  missing += [p['file'] for p in _deployment_manifest.get('parts',[]) if not (catalog.DATA/p['file']).is_file()]
 except (OSError,ValueError,KeyError,json.JSONDecodeError):
  missing=['catalog_manifest.json 형식 확인 필요']
if missing:
 st.title('자동차 탐색 자료를 연결해 주세요')
 st.info('상단 메뉴에서 자동차 제작 작업실과 3D 운전교실을 사용할 수 있습니다. 자동차 탐색은 검색 자료와 지도를 업로드하면 열립니다.')
 st.warning('data 폴더와 01·02·03 업로드 분류 폴더 안의 data를 자동으로 확인했습니다. 아래에 표시된 자료가 저장소에 있는지 확인해 주세요.')
 with st.expander('없는 파일과 업로드 위치 확인'):
  st.write('아래 파일을 data 폴더의 해당 위치에 올려 주세요.')
  for name in missing:st.code('data/'+name,language=None)
 st.stop()

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
  return st.components.v2.component('autoverse_korean_world_map',html=_MAP_ASSETS['html'],css=_MAP_ASSETS['css'],js=_MAP_ASSETS['js'])
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
