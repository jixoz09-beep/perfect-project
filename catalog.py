"""Read-only vehicle search and optional, separately supplied detail records."""
from __future__ import annotations
import functools,gzip,hashlib,json,math,os,re,shutil,sqlite3,tempfile,urllib.parse
from pathlib import Path
from contextlib import contextmanager
ROOT=Path(__file__).resolve().parents[1]
_REFS=Path(__file__).with_name('catalog_data')
_DATA_STAGING=None
_DATA_ERROR=None
def _deployment_data():
 """Read either a normal data folder or the original split upload folders."""
 global _DATA_STAGING,_DATA_ERROR
 if os.environ.get('AUTOVERSE_DATA_DIR'):
  return Path(os.environ['AUTOVERSE_DATA_DIR']).resolve()
 roots=[]
 direct=ROOT/'data'
 if direct.is_dir():roots.append(direct.resolve())
 # GitHub may contain the numbered upload folders themselves, optionally
 # inside one extra folder created when extracting the download.
 candidates=list(ROOT.glob('*/data'))+list(ROOT.glob('*/*/data'))
 for path in sorted(candidates):
  if not path.is_dir():continue
  if not ((path/'catalog_manifest.json').is_file() or
          (path/'maps/manifest.json').is_file() or
          any(path.glob('catalog.sqlite.gz.part*'))):continue
  resolved=path.resolve()
  if resolved not in roots:roots.append(resolved)
 if not roots:return direct.resolve()
 if len(roots)==1:return roots[0]
 # Build a read-only view without changing any uploaded file. Hard links
 # avoid duplicating the data on the same filesystem; copy only if needed.
 _DATA_STAGING=tempfile.TemporaryDirectory(prefix='autoverse_data_view_')
 merged=Path(_DATA_STAGING.name)
 for source in roots:
  for path in sorted(source.rglob('*')):
   if not path.is_file() or not path.resolve().is_relative_to(source):continue
   relative=path.relative_to(source);target=merged/relative
   if target.exists():
    identical=target.stat().st_size==path.stat().st_size
    if identical:
     with target.open('rb') as a,path.open('rb') as b:
      identical=hashlib.file_digest(a,'sha256').digest()==hashlib.file_digest(b,'sha256').digest()
    if not identical:_DATA_ERROR='서로 다른 버전의 탐색 자료가 중복되어 있습니다: '+relative.as_posix()
    continue
   target.parent.mkdir(parents=True,exist_ok=True)
   try:os.link(path,target)
   except OSError:shutil.copyfile(path,target)
 return merged
DATA=_deployment_data()
@functools.lru_cache(maxsize=1)
def manifest():
 if _DATA_ERROR:raise ValueError(_DATA_ERROR)
 return json.loads((DATA/'catalog_manifest.json').read_text(encoding='utf-8'))
@functools.lru_cache(maxsize=1)
def database_path():
 m=_base_manifest();digest=m['sqlite_sha256'];dest=Path(tempfile.gettempdir())/('autoverse_catalog_'+digest[:20]+'.sqlite')
 if dest.exists() and dest.stat().st_size==m['sqlite_bytes']:
  with dest.open('rb') as cached:
   if hashlib.file_digest(cached,'sha256').hexdigest()==digest:return dest
 with tempfile.TemporaryDirectory(prefix='autoverse_unpack_') as temporary:
  compressed=Path(temporary)/'catalog.gz';output=Path(temporary)/'catalog.sqlite'
  with compressed.open('wb') as out:
   for part in m['parts']:
    name=part['file']
    if Path(name).name!=name:raise ValueError('검색 자료 경로가 올바르지 않습니다.')
    path=DATA/name;h=hashlib.sha256()
    with path.open('rb') as f:
     while block:=f.read(1024*1024):h.update(block);out.write(block)
    if h.hexdigest()!=part['sha256']:raise ValueError('검색 자료 파일이 손상되었습니다: '+name)
  h=hashlib.sha256()
  with gzip.open(compressed,'rb') as src,output.open('wb') as out:
   while block:=src.read(1024*1024):h.update(block);out.write(block)
  if h.hexdigest()!=digest:raise ValueError('검색 자료 무결성 검사를 통과하지 못했습니다.')
  # os.replace is atomic; concurrent readers only see a complete database.
  os.replace(output,dest)
 return dest
@contextmanager
def connection():
 con=sqlite3.connect(database_path().as_uri()+'?mode=ro&immutable=1',uri=True);con.row_factory=sqlite3.Row
 try:yield con
 finally:con.close()
def normalize(q):return re.sub(r'[^a-z0-9가-힣ㄱ-ㅎ]','',str(q or '').lower())
BASE=' FROM vehicles v JOIN models n ON n.model_id=v.model_id JOIN makers m ON m.maker_id=n.maker_id '
FIELDS='v.vehicle_id,v.year,v.year_kind,v.year_label_ko,v.source_kind,n.name_ko AS model_ko,m.name_ko AS maker_ko,m.maker_key,m.origin_code'
def conditions(query='',year=None,countries=None,maker=None,strict_model=False,unknown_year=False):
 clauses=[];values=[];q=normalize(query)
 if year is not None:clauses.append('v.year=?');values.append(int(year))
 if unknown_year:clauses.append('v.year IS NULL')
 if countries is not None:
  if not countries:clauses.append('0')
  else:clauses.append('COALESCE(m.origin_code,\'UNKNOWN\') IN ('+','.join('?' for _ in countries)+')');values.extend(countries)
 if maker:clauses.append('m.maker_key=?');values.append(maker)
 if strict_model:clauses.append("v.year_kind='model'")
 if q:clauses.append('(n.search_text LIKE ? ESCAPE \'\\\' OR n.initials LIKE ? ESCAPE \'\\\' OR m.search_text LIKE ? ESCAPE \'\\\')');values.extend(['%'+q+'%']*3)
 return (' WHERE '+' AND '.join(clauses)) if clauses else '',values
@functools.lru_cache(maxsize=512)
def search(query='',year=None,countries=None,maker=None,strict_model=False,unknown_year=False,page=1,page_size=18):
 countries=tuple(countries) if countries is not None else None;where,values=conditions(query,year,countries,maker,strict_model,unknown_year)
 page=max(1,int(page));page_size=min(60,max(1,int(page_size)))
 with connection() as con:
  total=con.execute('SELECT COUNT(*)'+BASE+where,values).fetchone()[0];pages=max(1,(total+page_size-1)//page_size);page=min(page,pages)
  rows=con.execute('SELECT '+FIELDS+BASE+where+' ORDER BY m.name_ko,n.name_ko,v.year DESC,v.vehicle_id LIMIT ? OFFSET ?',values+[page_size,(page-1)*page_size]).fetchall()
 return {'total':total,'page':page,'pages':pages,'rows':[dict(r) for r in rows]}
@functools.lru_cache(maxsize=256)
def country_counts(query='',year=None,strict_model=False,unknown_year=False):
 where,values=conditions(query,year,None,None,strict_model,unknown_year)
 with connection() as con:rows=con.execute("SELECT COALESCE(m.origin_code,'UNKNOWN') AS code,COUNT(*) AS n"+BASE+where+' GROUP BY m.origin_code',values).fetchall()
 return {r['code']:r['n'] for r in rows}
@functools.lru_cache(maxsize=256)
def maker_options(query='',year=None,countries=None,strict_model=False,unknown_year=False):
 where,values=conditions(query,year,countries,None,strict_model,unknown_year)
 with connection() as con:rows=con.execute('SELECT DISTINCT m.maker_key,m.name_ko'+BASE+where+' ORDER BY m.name_ko',values).fetchall()
 return [dict(r) for r in rows]
def vehicle(vehicle_id):
 with connection() as con:row=con.execute('SELECT '+FIELDS+BASE+' WHERE v.vehicle_id=?',(vehicle_id,)).fetchone()
 return dict(row) if row else None
@functools.lru_cache(maxsize=8)
def map_for_year(year):
 index=json.loads((DATA/'maps/manifest.json').read_text());row=index.get(str(int(year)))
 if not row:raise ValueError('해당 연도의 지도 자료가 없습니다.')
 path=DATA/'maps'/row['file']
 if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('지도 자료 무결성 검사를 통과하지 못했습니다.')
 return json.loads(gzip.decompress(path.read_bytes()))
@functools.lru_cache(maxsize=1)
def country_names():return json.loads((DATA/'countries_ko.json').read_text())
def country_name(code):return '국적 확인 중' if code=='UNKNOWN' or not code else country_names().get(code,'국가명 확인 중')
def load_details(vehicle_id):
 if not re.fullmatch('[A-Za-z0-9_-]{1,90}',vehicle_id):return {}
 path=DATA/'details'/(vehicle_id+'.json')
 if not path.exists():return {}
 if path.stat().st_size>2*1024*1024:raise ValueError('상세 자료 파일 크기가 너무 큽니다.')
 data=json.loads(path.read_text(encoding='utf-8'))
 if not isinstance(data,dict):raise ValueError('상세 자료는 객체 형식이어야 합니다.')
 if data.get('vehicle_id')!=vehicle_id or data.get('schema_version')!=1:raise ValueError('상세 자료의 차량 식별번호 또는 형식이 일치하지 않습니다.')
 for key in ('photos','specifications','sources'):
  if key in data and not isinstance(data[key],list):raise ValueError('상세 자료 목록 형식이 잘못되었습니다: '+key)
 if data.get('history_ko') is not None and not isinstance(data['history_ko'],str):raise ValueError('역사 자료는 문장 형식이어야 합니다.')
 return data

def photo_location(photo):
 location=photo.get('path') or photo.get('url')
 if not location:return None
 if '://' in location:
  u=urllib.parse.urlparse(location)
  if u.scheme!='https' or not u.hostname or u.hostname in ['localhost','127.0.0.1','::1'] or u.username or u.password:return None
  return location
 path=(DATA/location).resolve()
 if not path.is_relative_to(DATA) or path.suffix.lower() not in ['.png','.jpg','.jpeg','.webp'] or not path.is_file():return None
 return str(path)

# Verified historical corrections are embedded in main.py. Uploaded data stays intact.
_HISTORY_SCHEMA='verified-history-1'
_HISTORY=[
 {'key':'cugnot-1769','vehicle_id':'AV-B37281F7F3534DEDEEB5','maker':'cugnot',
  'name_ko':'퀴뇨 증기자동차 1차 시제차','aliases':['Cugnot','Fardier de Cugnot','퀴뇨 증기차'],
  'history_ko':'1769년에 시험된 퀴뇨의 첫 증기자동차 시제차입니다. 프랑스의 니콜라 조제프 퀴뇨가 개발했습니다. 박물관에 보존된 1770~1771년의 두 번째 차량과 구분합니다.',
  'sources':[{'label_ko':'프랑스 공예박물관 · 퀴뇨 증기차','url':'https://www.arts-et-metiers.net/musee/fardier-vapeur'},
             {'label_ko':'프랑스 역사자동차연맹 · 퀴뇨','url':'https://www.ffve.org/carte/fardier-cugnot'}]},
 {'key':'willys-mb','maker':'willys','raw_name':'MB','name_ko':'엠비','aliases':['Willys MB','윌리스 엠비'],
  'ranges':[[1941,1945]],'year_kind':'production',
  'history_ko':'제조사의 역사 자료에 생산 시기가 1941~1945년으로 제시된 윌리스 엠비 군용차입니다. 해당 기간의 각 연도에서 검색됩니다. 이는 개별 차량의 등록연도나 매년 새로 출시된 모델을 뜻하지 않습니다.',
  'sources':[{'label_ko':'지프 제조사 역사 · 1941~1945년 윌리스 엠비','url':'https://www.jeep.com/history/1940s.html'}]},
 {'key':'peugeot-vlv','vehicle_id':'AV-C9A021C19E97DA50C702','maker':'peugeot','name_ko':'브이엘브이',
  'aliases':['Peugeot VLV','푸조 브이엘브이'],'ranges':[[1941,1943]],'year_kind':'production',
  'history_ko':'푸조의 전기자동차 브이엘브이입니다. 제조사의 2020년 7월 자료는 1941년 6월~1943년 2월 생산으로 설명합니다. 다른 제조사 자료에는 종료연도가 1945년으로도 적혀 있습니다. 검색에는 두 자료가 공통으로 포함하며 구체적인 연월 자료로 확인되는 1941~1943년을 반영하고, 1944~1945년 생산은 확정하지 않았습니다.',
  'sources':[{'label_ko':'푸조 제조사 · 1941년 6월~1943년 2월 생산 자료','url':'https://www.media.stellantis.com/em-en/peugeot/press/from-the-peugeot-vlv-to-the-new-peugeot-e-2008-the-tale-of-an-electric-revolution'},
             {'label_ko':'푸조 제조사 · 종료연도가 다르게 표기된 자료','url':'https://www.media.stellantis.com/em-en/peugeot/press/peugeot-celebrates-electricity-on-the-peugeot-adventure-stand-at-retromobile'}]},
 {'key':'mercedes-170v-prewar','maker':'mercedesbenz','raw_name':'170 V (W 136, pre-war)',
  'name_ko':'170 브이 (더블유 136, 전쟁 이전형)','aliases':['Mercedes-Benz 170 V','벤츠 170V','W136'],
  'ranges':[[1936,1942]],'year_kind':'production',
  'history_ko':'메르세데스 벤츠 공식 기록보관소가 1936~1942년형으로 구분하는 전쟁 이전의 170 브이입니다. 1942년 11월까지 생산된 것으로 확인됩니다. 전쟁 후 생산된 같은 이름의 차량과 구분하며 1943년 이후로 이 생산 기간을 연장하지 않습니다.',
  'sources':[{'label_ko':'메르세데스 벤츠 기록보관소 · 170 브이, 1936~1942년','url':'https://mercedes-benz-publicarchive.com/marsClassic/en/instance/ko/170-V-W-136-1936---1942.xhtml?oid=4278'}]},
 {'key':'ford-v8-superdeluxe-1942','maker':'ford','raw_name':'V-8 Super DeLuxe (1942)',
  'name_ko':'브이8 수퍼 디럭스 (1942년형)','aliases':['Ford V8 Super Deluxe','포드 수퍼 디럭스'],
  'ranges':[[1942,1942]],'year_kind':'manufacture',
  'history_ko':'헨리 포드 박물관에 1942년 제작으로 기록된 포드 브이8 수퍼 디럭스 세단입니다. 전시 차량은 전쟁 후 1946년형 부품으로 일부 개조되었으므로 그 상태의 사진을 원래 1942년형 외관으로 단정하지 않습니다.',
  'sources':[{'label_ko':'헨리 포드 박물관 · 1942년 제작 수퍼 디럭스','url':'https://www.thehenryford.org/collections/explore/artifact/247093'}]}
]
_base_manifest=manifest
_base_database_path=database_path
_base_load_details=load_details
_base_map_for_year=map_for_year

def _history_initials(text):
 initials='ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
 return ''.join(initials[(ord(ch)-0xac00)//588] if 0xac00<=ord(ch)<=0xd7a3 else ch for ch in text if ch.isalnum())

@functools.lru_cache(maxsize=1)
def database_path():
 base=_base_database_path()
 fingerprint=hashlib.sha256((_HISTORY_SCHEMA+json.dumps(_HISTORY,ensure_ascii=False,sort_keys=True)).encode()).hexdigest()
 dest=Path(tempfile.gettempdir())/('autoverse_history_'+_base_manifest()['sqlite_sha256'][:12]+'_'+fingerprint[:20]+'.sqlite')
 if dest.is_file():
  with sqlite3.connect(dest.as_uri()+'?mode=ro',uri=True) as db:
   if db.execute('SELECT fingerprint FROM history_meta').fetchone()==(fingerprint,):return dest
 with tempfile.TemporaryDirectory(prefix='autoverse_history_build_') as temporary:
  output=Path(temporary)/'catalog.sqlite';shutil.copyfile(base,output)
  with sqlite3.connect(output) as db:
   db.execute('CREATE TABLE history_meta(fingerprint TEXT NOT NULL)')
   db.execute('INSERT INTO history_meta VALUES(?)',(fingerprint,))
   db.execute('CREATE TABLE history_details(vehicle_id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
   for entry in _HISTORY:
    maker=db.execute('SELECT maker_id FROM makers WHERE maker_key=?',(entry['maker'],)).fetchone()
    if not maker:raise ValueError('역사 자료의 제조사 연결을 확인해야 합니다.')
    maker_id=maker[0];reference=None
    if entry.get('vehicle_id'):
     reference=db.execute('SELECT model_id FROM vehicles WHERE vehicle_id=?',(entry['vehicle_id'],)).fetchone()
     if not reference:raise ValueError('역사 자료의 원본 차량 식별번호가 없습니다.')
    else:
     reference=db.execute('SELECT model_id FROM models WHERE maker_id=? AND raw_name=?',(maker_id,entry['raw_name'])).fetchone()
    search='|'.join(normalize(value) for value in [entry['name_ko'],entry.get('raw_name',''),*entry.get('aliases',[])])
    if reference:
     model_id=reference[0]
     db.execute("UPDATE models SET maker_id=?,name_ko=?,search_text=search_text||'|'||?,initials=? WHERE model_id=?",(maker_id,entry['name_ko'],search,_history_initials(entry['name_ko']),model_id))
    else:
     model_id=db.execute('INSERT INTO models(maker_id,raw_name,name_ko,search_text,initials) VALUES(?,?,?,?,?)',(maker_id,entry['raw_name'],entry['name_ko'],search,_history_initials(entry['name_ko']))).lastrowid
    ids=[entry['vehicle_id']] if entry.get('vehicle_id') else []
    for start,end in entry.get('ranges',[]):
     for year in range(start,end+1):
      existing=db.execute('SELECT vehicle_id FROM vehicles WHERE model_id=? AND year=?',(model_id,year)).fetchall()
      if existing:ids.extend(row[0] for row in existing);continue
      identifier='AVH-'+hashlib.sha256((entry['key']+':'+str(year)).encode()).hexdigest()[:24]
      kind=entry['year_kind']
      label=(f'확인된 생산 기간 {start}~{end}년' if kind=='production' else '확인된 제작연도')
      db.execute('INSERT INTO vehicles VALUES(?,?,?,?,?,?,?)',(identifier,model_id,year,kind,label,'historical',''))
      ids.append(identifier)
    for identifier in set(ids):
     detail={'schema_version':1,'vehicle_id':identifier,'history_ko':entry['history_ko'],'sources':entry['sources']}
     db.execute('INSERT OR REPLACE INTO history_details VALUES(?,?)',(identifier,json.dumps(detail,ensure_ascii=False)))
   db.commit()
   if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('역사 자료 반영 후 무결성 검사를 통과하지 못했습니다.')
  os.replace(output,dest)
 return dest

@functools.lru_cache(maxsize=1)
def manifest():
 result=json.loads(json.dumps(_base_manifest()))
 with connection() as db:
  result['records']=db.execute('SELECT COUNT(*) FROM vehicles').fetchone()[0]
  result['models']=db.execute('SELECT COUNT(*) FROM models').fetchone()[0]
  result['historical_records']=db.execute("SELECT COUNT(*) FROM vehicles WHERE source_kind='historical'").fetchone()[0]
  result['year_counts']={str(row[0]) if row[0] is not None else 'unknown':row[1] for row in db.execute('SELECT year,COUNT(*) FROM vehicles GROUP BY year')}
  result['country_coverage']={row[0]:row[1] for row in db.execute("SELECT COALESCE(m.origin_code,'UNKNOWN'),COUNT(*) FROM vehicles v JOIN models n ON n.model_id=v.model_id JOIN makers m ON m.maker_id=n.maker_id GROUP BY m.origin_code")}
  result['source_kind_counts']={row[0]:row[1] for row in db.execute('SELECT source_kind,COUNT(*) FROM vehicles GROUP BY source_kind')}
  result['year_kind_counts']={row[0]:row[1] for row in db.execute('SELECT year_kind,COUNT(*) FROM vehicles GROUP BY year_kind')}
 return result

def load_details(vehicle_id):
 if not re.fullmatch('[A-Za-z0-9_-]{1,90}',vehicle_id):return {}
 with connection() as db:row=db.execute('SELECT payload FROM history_details WHERE vehicle_id=?',(vehicle_id,)).fetchone()
 verified=json.loads(row[0]) if row else {}
 return {**verified,**_base_load_details(vehicle_id)}

@functools.lru_cache(maxsize=8)
def map_for_year(year):
 year=int(year);index=json.loads((DATA/'maps/manifest.json').read_text())
 if str(year) in index:return _base_map_for_year(year)
 # Some newly verified production years have no exact boundary file. Show
 # the actual reference year explicitly; do not invent a historical border.
 available=sorted(int(key) for key in index)
 reference=min(available,key=lambda candidate:(abs(candidate-year),candidate))
 result=dict(_base_map_for_year(reference));result['boundary_year']=reference
 return result


"""Existing-ID data attachment. Source observations never create guessed vehicles."""
import lzma

_pre_integration_database_path=database_path
_pre_integration_manifest=manifest
_pre_integration_load_details=load_details
_pre_integration_conditions=conditions

@functools.lru_cache(maxsize=1)
def integrated_manifest():
 for directory in [ROOT,DATA]:
  path=directory/'autoverse_records_manifest.json'
  if path.is_file():
   value=json.loads(path.read_text(encoding='utf-8'))
   if value.get('schema_version')!=1:raise ValueError('추가 자료 버전이 맞지 않습니다.')
   return value,directory
 return None,None

@functools.lru_cache(maxsize=1)
def integrated_database_path():
 info,directory=integrated_manifest()
 if not info:return None
 digest=info['sqlite_sha256']
 dest=Path(tempfile.gettempdir())/('autoverse_records_'+digest+'.sqlite')
 if dest.is_file()and dest.stat().st_size==info['sqlite_bytes']:return dest
 source=directory/'autoverse_records.sqlite.xz'
 if not source.is_file():raise ValueError('autoverse_records.sqlite.xz 파일을 main.py와 같은 위치에 올려 주세요.')
 with source.open('rb')as f:
  if hashlib.file_digest(f,'sha256').hexdigest()!=info['packed_sha256']:raise ValueError('추가 자료 파일이 손상되었습니다.')
 with tempfile.TemporaryDirectory(prefix='autoverse_records_')as temporary:
  output=Path(temporary)/'records.sqlite';h=hashlib.sha256()
  with lzma.open(source,'rb')as src,output.open('wb')as dst:
   while block:=src.read(1024*1024):h.update(block);dst.write(block)
  if h.hexdigest()!=digest:raise ValueError('추가 자료 압축 해제 결과가 일치하지 않습니다.')
  os.replace(output,dest)
 return dest

def _updated_year_kind(basis,year):
 if year is None:return 'unknown'
 text=str(basis or '').lower()
 registration=any(v in text for v in ['등록','registration','first_use','최초 사용'])
 model=any(v in text for v in ['모델 연식','모델연식','model_year','model year'])
 not_model=any(v in text for v in ['모델 연식 아님','모델연식 아님','모델 연식·출시연도와 별개','not model'])
 if model and not not_model and not registration and' / 'not in text:return 'model'
 if registration:return 'mixed'if model else'registration'
 if '세대'in text:return 'generation'
 if any(v in text for v in ['공개','출시','도입','발표','시작일','성립']):return 'introduction'
 if any(v in text for v in ['제조','생산','제작']):return 'manufacture'
 if 'approval'in text or'형식승인'in text:return 'approval'
 return 'observation'

@functools.lru_cache(maxsize=1)
def database_path():
 base=_pre_integration_database_path()
 extra=integrated_database_path()
 if extra is None:return base
 info,_=integrated_manifest()
 fingerprint=hashlib.sha256((str(base)+info['sqlite_sha256']+'vehicle-records-1').encode()).hexdigest()
 dest=Path(tempfile.gettempdir())/('autoverse_linked_'+fingerprint+'.sqlite')
 if dest.is_file():return dest
 with tempfile.TemporaryDirectory(prefix='autoverse_attach_')as temporary:
  output=Path(temporary)/'catalog.sqlite';shutil.copyfile(base,output)
  with sqlite3.connect(output)as db,sqlite3.connect(extra.as_uri()+'?mode=ro&immutable=1',uri=True)as values:
   db.execute('ALTER TABLE vehicles ADD COLUMN origin_override TEXT')
   db.execute('PRAGMA synchronous=OFF')
   def updates():
    for vid,year,basis,code in values.execute('SELECT vehicle_id,stored_year,year_basis,country_code FROM records'):
     yield year,_updated_year_kind(basis,year),basis or'연도 미확인',code or'UNKNOWN',vid
   db.executemany('UPDATE vehicles SET year=?,year_kind=?,year_label_ko=?,origin_override=? WHERE vehicle_id=?',updates())
   db.execute('CREATE INDEX idx_integrated_country ON vehicles(origin_override,year)')
   db.execute('CREATE TABLE integrated_release(fingerprint TEXT NOT NULL)')
   db.execute('INSERT INTO integrated_release VALUES(?)',(fingerprint,));db.commit()
  os.replace(output,dest)
 return dest

_EFFECTIVE_ORIGIN="COALESCE(v.origin_override,m.origin_code,'UNKNOWN')"
if integrated_manifest()[0]:
 FIELDS='v.vehicle_id,v.year,v.year_kind,v.year_label_ko,v.source_kind,n.name_ko AS model_ko,m.name_ko AS maker_ko,m.maker_key,'+_EFFECTIVE_ORIGIN+' AS origin_code'

def conditions(query='',year=None,countries=None,maker=None,strict_model=False,unknown_year=False):
 where,values=_pre_integration_conditions(query,year,countries,maker,strict_model,unknown_year)
 if integrated_manifest()[0]:where=where.replace("COALESCE(m.origin_code,'UNKNOWN')",_EFFECTIVE_ORIGIN)
 return where,values

@functools.lru_cache(maxsize=256)
def country_counts(query='',year=None,strict_model=False,unknown_year=False):
 where,values=conditions(query,year,None,None,strict_model,unknown_year)
 expression=_EFFECTIVE_ORIGIN if integrated_manifest()[0]else"COALESCE(m.origin_code,'UNKNOWN')"
 with connection()as con:
  rows=con.execute('SELECT '+expression+' AS code,COUNT(*) AS n'+BASE+where+' GROUP BY '+expression,values).fetchall()
 return {row['code']:row['n']for row in rows}

@functools.lru_cache(maxsize=1)
def manifest():
 result=_pre_integration_manifest()
 info,_=integrated_manifest()
 if info:
  result['country_coverage']=country_counts()
  result['integrated_statistics']=info.get('statistics',{})
  result['integrated_data_date']=info.get('data_date','')
 return result

@functools.lru_cache(maxsize=4096)
def _integrated_record(vehicle_id):
 path=integrated_database_path()
 if path is None:return None
 with sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)as db:
  db.row_factory=sqlite3.Row
  row=db.execute('''SELECT r.*,s.payload AS specs,h.payload AS history,
   a.payload AS source_urls,b.payload AS country_sources,c.payload AS year_sources
   FROM records r LEFT JOIN spec_sets s ON s.id=r.spec_id
   LEFT JOIN history_sets h ON h.id=r.history_id
   LEFT JOIN source_sets a ON a.id=r.sources_id
   LEFT JOIN source_sets b ON b.id=r.country_source_id
   LEFT JOIN source_sets c ON c.id=r.year_source_id WHERE r.vehicle_id=?''',(vehicle_id,)).fetchone()
 return dict(row)if row else None

def load_details(vehicle_id):
 previous=_pre_integration_load_details(vehicle_id)
 row=_integrated_record(vehicle_id)
 if not row:return previous
 result=dict(previous)
 if row['specs']:
  existing=previous.get('specifications',[])
  added=json.loads(row['specs'])
  if isinstance(added,list):
   result['specifications']=(existing if isinstance(existing,list) else [])+added
 history=json.loads(row['history'])if row['history']else{}
 if history.get('history_ko')and not result.get('history_ko'):
  result['history_ko']=history['history_ko']
  result['history_scope_ko']='모델 계보에 대한 역사 설명입니다. 개별 차량의 세대나 연식을 새로 확정한 자료는 아닙니다.'
 sources=[x for x in previous.get('sources',[])if isinstance(x,dict)]
 for field,label in [('source_urls','제원 원자료'),('country_sources','제조사 국적 근거'),('year_sources','연도 근거')]:
  for url in json.loads(row[field]or'[]'):sources.append({'label_ko':label,'url':url})
 for url in history.get('sources',[]):sources.append({'label_ko':'자동차 역사 원자료','url':url})
 seen=set();result['sources']=[]
 for source in sources:
  url=source.get('url','')
  if not url.startswith('https://')or url in seen:continue
  seen.add(url);result['sources'].append(source)
 result['vehicle_id']=vehicle_id;result['schema_version']=1
 if row['country']and not row['country_code']:
  result['origin_note_ko']='제조사 국적 원자료: '+row['country']+' (지도에는 단일 국가로 배정하지 않았습니다.)'
 return result


# AUTOVERSE: all-model display-level deduplication. Original vehicle_id rows remain intact.
# A source occurrence is NOT a display vehicle. Generation/FL signals split a group only
# when two explicitly distinguishable generations/versions coexist in the same model year.
import unicodedata
from contextlib import contextmanager as _av_contextmanager

_AV_SUFFIX = re.compile(
 r'(?<!\w)(?:hybrid|plug[ -]?in|phev|mhev|hev|bev|ev|electric|diesel|gasoline|petrol|lpg|cng|'
 r'2wd|4wd|awd|fwd|rwd|dct|cvt|a[ /-]?t|m[ /-]?t|automatic|manual|'
 r't[ -]?gdi|gdi|crdi|tdi|tsi|turbo|mpi|gpl|hdi|bluehdi|puretech|ecoboost|'
 r'prestige|noblesse|signature|inspiration|exclusive|premium|luxury|limited|'
 r'standard|business|executive|elegance|comfort|trend|active|base|'
 r'gt[ -]?line|n[ -]?line|x[ -]?line|s[ -]?line|sport[ -]?package|'
 r'long[ -]?range|performance|sel|se|le|lx|ex|sx|xle|xse|'
 r'\d[.,]\d\s*(?:litre|liter|liters|l|t|리터)?|\d{2,4}\s*(?:hp|ps|bhp|kw|마력))(?=\W|$)|'
 r'(?:하이브리드|플러그인하이브리드|전기차?|가솔린|휘발유|디젤|경유|'
 r'사륜구동|이륜구동|자동변속기|수동변속기|터보|프레스티지|노블레스|'
 r'시그니처|인스퍼레이션|익스클루시브|프리미엄|럭셔리|스탠다드|'
 r'트렌디|스타일|베이직|스마트|모던|스포츠패키지|컴포트|어스|웨이브|에어)', re.I)
_AV_PRE = re.compile(r'\b(?:pre[ -]?(?:facelift|face[ -]?lift)|before[ -]?facelift)\b|변경전|부분변경이전',re.I)
_AV_FL = re.compile(r'\b(?:facelift|face[ -]?lift|lci|f[ /-]?l)\b|페이스리프트|부분변경',re.I)
_AV_GEN = re.compile(
 r'(?<![a-z0-9])(?:sg2|cn7|nx4|nx5|nq5|dl3|gl3|dn8|bn7|gn7|'
 r'\b(?:sl|ql|de|ad|md|lf|yf|tf|jf|ja|sk3|sp2|sp3|nm|ka4|mq4)\b|'
 r'[efg]\d{2}|w\d{3}|\bmk\s*(?:[ivx]+|\d+)\b|'
 r'\bgen(?:eration)?\s*[1-9]\b)(?![a-z0-9])|[1-9]세대',re.I)
_AV_BODY = re.compile(r'(?<!\w)(?:suv|sedan|hatchback|fastback|crossover|estate|wagon|touring|coupe|mpv|cabrio|cabriolet|roadster|convertible)(?!\w)',re.I)
_AV_ROMAN = re.compile(r'(?<![a-z0-9])(?:ii|iii|iv|v|vi|vii|viii|ix)(?![a-z0-9])',re.I)
_AV_YEAR = re.compile(r'(?<!\d)(?:19[0-9]{2}|20[0-9]{2})(?!\d)')
_AV_PREFIX = re.compile(r'\b(?:the[ -]+(?:all[ -]+)?new|all[ -]+new|new|my|model[ -]?year)\b|(?:더\s*뉴|올\s*뉴|디\s*올\s*뉴|신형)',re.I)
_AV_MAKER_WORDS = {
 'kia':['kia','기아','kia motors'], 'hyundai':['hyundai','현대','hyundai motor'],
 'bmw':['bmw','비엠더블유'], 'genesis':['genesis','제네시스'],
 'mercedesbenz':['mercedes-benz','mercedes','benz','메르세데스벤츠','벤츠'],
 'toyota':['toyota','토요타','도요타'], 'honda':['honda','혼다'],
 'audi':['audi','아우디'], 'volkswagen':['volkswagen','vw','폭스바겐'],
 'tesla':['tesla','테슬라'], 'ford':['ford','포드']}
# Only confirmed common market-language spellings are mapped to the same display label.
_AV_ROOT_ALIAS = {
 '니로':'niro','니로플러스':'niroplus', '셀토스':'seltos','스포티지':'sportage',
 '쏘렌토':'sorento','모닝':'picanto','피칸토':'picanto',
 '아반떼':'elantra','엘란트라':'elantra','쏘나타':'sonata',
 '투싼':'tucson','그랜저':'grandeur','싼타페':'santafe',
 '카니발':'carnival','봉고':'bongo','레이':'ray','코나':'kona',
 'k3':'k3','k5':'k5','k8':'k8','k9':'k9',
 '아이오닉5':'ioniq5','아이오닉6':'ioniq6','아이오닉9':'ioniq9',
 '모델3':'model3','모델y':'modely','모델s':'models',
 'gv70':'gv70','gv80':'gv80','g70':'g70','g80':'g80','g90':'g90',
}
_AV_ALIAS_NAMES = sorted(_AV_ROOT_ALIAS, key=len,reverse=True)

def _av_nfkc(s):
 return unicodedata.normalize('NFKC',str(s or '')).strip().lower()

def _av_scrub(text,maker=''):
 s=_av_nfkc(text)
 s=re.split(r'\s*[·•|]\s*',s,1)[0]
 s=_AV_YEAR.sub(' ',s)
 s=_AV_PREFIX.sub(' ',s)
 s=_AV_BODY.sub(' ',s)
 # Edition/generation Roman numerals are not model names after a model token.
 if len(s.split())>1:s=_AV_ROMAN.sub(' ',s)
 s=_AV_GEN.sub(' ',s)
 s=_AV_PRE.sub(' ',s)
 s=_AV_FL.sub(' ',s)
 s=_AV_SUFFIX.sub(' ',s)
 # Any leftover engine code/power in parentheses should not become a model name.
 s=re.sub(r'\([^)]*(?:\d[.,]\d|hp|ps|kw|마력|engine|엔진)[^)]*\)',' ',s,flags=re.I)
 s=re.sub(r'(?<!\w)\d+(?:cv|ch|bhp|hp|ps|kw|마력)(?!\w)',' ',s,flags=re.I)
 for w in _AV_MAKER_WORDS.get(str(maker or '').lower().replace('-','').replace('_',''),[]):
  s=re.sub(r'^\s*'+re.escape(w)+r'(?=\W|$)',' ',s,flags=re.I)
 return re.sub(r'[^a-z0-9가-힣]+','',s)

@functools.lru_cache(maxsize=131072)
def _av_root(maker,raw,ko):
 a=_av_scrub(raw,maker)
 b=_av_scrub(ko,maker)
 # Known Korean native label matches its official international model spelling.
 for val in (a,b):
  if val in _AV_ROOT_ALIAS:return _AV_ROOT_ALIAS[val]
 # English source names usually supply the most consistent cross-market key.
 # Strip the manufacturer prefix and residual configuration suffix above.
 return a or b or normalize(raw or ko)

@functools.lru_cache(maxsize=131072)
def _av_gen(raw,ko):
 s=_av_nfkc(raw)+' '+_av_nfkc(ko)
 x=_AV_GEN.search(s)
 return re.sub(r'\s+','',x.group(0)) if x else ''

@functools.lru_cache(maxsize=131072)
def _av_facelift(raw,ko):
 s=_av_nfkc(raw)+' '+_av_nfkc(ko)
 return 'pre' if _AV_PRE.search(s) else 'fl' if _AV_FL.search(s) else ''

@functools.lru_cache(maxsize=131072)
def _av_display(text,raw,maker):
 s=str(text or raw or '').strip()
 # Display the chosen record's trimmed label without hiding its source ID.
 s=_AV_YEAR.sub(' ',s)
 s=_AV_PREFIX.sub(' ',s)
 s=_AV_BODY.sub(' ',s)
 # Edition/generation Roman numerals are not model names after a model token.
 if len(s.split())>1:s=_AV_ROMAN.sub(' ',s)
 s=_AV_GEN.sub(' ',s)
 s=_AV_SUFFIX.sub(' ',s)
 s=re.sub(r'\([^)]*(?:\d[.,]\d|hp|ps|kw|마력)[^)]*\)',' ',s,flags=re.I)
 s=re.sub(r'\s+',' ',s).strip(' ·•|,()[]')
 return s or str(text or raw or '')

_av_prev_connection=connection
_av_base=BASE
@functools.lru_cache(maxsize=1)
def _av_index_path():
 """Once per deployed catalog, build a small reusable, atomic SQLite search index."""
 source=database_path()
 stat=source.stat()
 fingerprint=hashlib.sha256((str(source.resolve())+':'+str(stat.st_size)+':'+str(stat.st_mtime_ns)+':nation-universal-v3').encode()).hexdigest()[:24]
 target=Path(tempfile.gettempdir())/('autoverse_display_index_'+fingerprint+'.sqlite')
 if target.is_file():
  try:
   with sqlite3.connect(target.as_uri()+'?mode=ro&immutable=1',uri=True) as c:
    if c.execute("SELECT fingerprint FROM av_meta").fetchone()==(fingerprint,):return target
  except (sqlite3.Error,OSError):pass
 with tempfile.TemporaryDirectory(prefix='autoverse_display_build_') as d:
  output=Path(d)/'display.sqlite'
  with sqlite3.connect(output) as dest, _av_prev_connection() as original:
   dest.execute('PRAGMA synchronous=OFF')
   dest.execute('PRAGMA journal_mode=OFF')
   dest.execute('CREATE TABLE vehicle_keys(vehicle_id TEXT PRIMARY KEY,root TEXT NOT NULL,gen TEXT,face TEXT,origin TEXT NOT NULL,brand TEXT NOT NULL)')
   cursor=original.execute('SELECT v.vehicle_id,m.maker_key,n.raw_name,n.name_ko,m.origin_code'+_av_base)
   dest.executemany('INSERT INTO vehicle_keys VALUES(?,?,?,?,?,?)',(
      (vid,_av_root(maker,raw,ko),_av_gen(raw,ko),_av_facelift(raw,ko),_av_maker_origin(maker,origin),_av_brand_for_record(maker,raw,ko))
      for vid,maker,raw,ko,origin in cursor))
   dest.execute('CREATE INDEX ix_av_keys_root ON vehicle_keys(root)')
   dest.execute('CREATE TABLE av_meta(fingerprint TEXT NOT NULL)')
   dest.execute('INSERT INTO av_meta VALUES(?)',(fingerprint,))
   dest.commit()
  os.replace(output,target)
 return target

@_av_contextmanager
def connection():
 with _av_prev_connection() as con:
  idx=_av_index_path()
  con.execute('ATTACH DATABASE ? AS av_idx',(idx.as_uri()+'?mode=ro&immutable=1',))
  yield con

# Original schema and original vehicle IDs are not modified.
BASE=_av_base+' JOIN av_idx.vehicle_keys k ON k.vehicle_id=v.vehicle_id '
FIELDS='v.vehicle_id,v.year,v.year_kind,v.year_label_ko,v.source_kind,n.name_ko AS model_ko,m.name_ko AS maker_ko,k.brand AS maker_key,k.origin AS origin_code'
_AV_FIELDS=FIELDS+',n.raw_name AS raw_model,k.root AS av_root,k.gen AS av_gen,k.face AS av_face,k.body AS av_body'
def _av_cte(where):
 return ('WITH filtered AS (SELECT '+_AV_FIELDS+BASE+where+'),'
  'signals AS (SELECT maker_key,av_root,year,COUNT(DISTINCT NULLIF(av_gen,\'\')) AS gen_types,'
  'COUNT(DISTINCT NULLIF(av_face,\'\')) AS face_types FROM filtered GROUP BY maker_key,av_root,year),'
  'named AS (SELECT f.*,'
  " CASE WHEN s.gen_types>1 THEN COALESCE(NULLIF(f.av_gen,''),'unverified') ELSE '' END AS kept_gen,"
  " CASE WHEN s.face_types>1 THEN COALESCE(NULLIF(f.av_face,''),'unverified') ELSE '' END AS kept_face,"
  " CASE WHEN f.year IS NULL THEN f.vehicle_id ELSE '' END AS unknown_id "
  'FROM filtered f JOIN signals s ON f.maker_key=s.maker_key AND f.av_root=s.av_root '
  'AND (f.year=s.year OR (f.year IS NULL AND s.year IS NULL))),'
  'ranked AS (SELECT named.*,'
  'ROW_NUMBER() OVER (PARTITION BY maker_key,av_root,year,kept_gen,kept_face,unknown_id '
  "ORDER BY CASE WHEN year_kind='model' THEN 0 ELSE 1 END,"
  " CASE WHEN source_kind='master' THEN 0 ELSE 1 END,LENGTH(model_ko),vehicle_id) AS rn,"
  'COUNT(*) OVER (PARTITION BY maker_key,av_root,year,kept_gen,kept_face,unknown_id) AS linked_record_count '
  'FROM named) ')

@functools.lru_cache(maxsize=512)
def search(query='',year=None,countries=None,maker=None,strict_model=False,unknown_year=False,page=1,page_size=18):
 countries=tuple(countries) if countries is not None else None
 where,values=conditions(query,year,countries,maker,strict_model,unknown_year)
 page=max(1,int(page));page_size=min(60,max(1,int(page_size)))
 cte=_av_cte(where)
 with connection() as con:
  total=con.execute(cte+'SELECT COUNT(*) FROM ranked WHERE rn=1',values).fetchone()[0]
  pages=max(1,(total+page_size-1)//page_size)
  page=min(page,pages)
  rows=con.execute(cte+'SELECT ranked.vehicle_id,ranked.year,year_kind,year_label_ko,source_kind,model_ko,raw_model,'
      'maker_ko,maker_key,origin_code,'
      'kept_gen,kept_face,av_body,av_root,av_group,first_year,last_year,known_year_count,'
      'source_count AS linked_record_count FROM ranked JOIN av_idx.cards ON cards.group_id=av_group WHERE rn=1 '
      'ORDER BY maker_ko,model_ko,ranked.year DESC,ranked.vehicle_id LIMIT ? OFFSET ?',values+[page_size,(page-1)*page_size]).fetchall()
 result=[]
 for r in rows:
  entry=dict(r)
  entry['model_ko']=_av_display(entry['model_ko'],entry['raw_model'],entry['maker_key'])
  result.append(entry)
 return {'total':total,'page':page,'pages':pages,'rows':result}

@functools.lru_cache(maxsize=256)
def country_counts(query='',year=None,strict_model=False,unknown_year=False):
 where,values=conditions(query,year,None,None,strict_model,unknown_year)
 cte=_av_cte(where)
 with connection() as con:
  rows=con.execute(cte+"SELECT COALESCE(origin_code,'UNKNOWN') AS code,COUNT(*) AS n "
                   'FROM ranked WHERE rn=1 GROUP BY COALESCE(origin_code,\'UNKNOWN\')',values).fetchall()
 return {r['code']:r['n'] for r in rows}

@functools.lru_cache(maxsize=64)
def duplicate_diagnostics(year, maker_key, name_pairs):
 """Exact displayed vs source counts for a few selected model names, using deployed catalog."""
 year=int(year)
 results=[]
 for english,korean in name_pairs:
  where,vals=conditions('',year,None,maker_key,False,False)
  suffix=' AND (LOWER(n.raw_name) LIKE ? OR LOWER(n.name_ko) LIKE ? OR LOWER(n.search_text) LIKE ?)'
  qs=('%'+english.lower()+'%','%'+korean.lower()+'%','%'+english.lower()+'%')
  with connection() as con:
   row=con.execute(_av_cte(where+suffix)+'SELECT COUNT(*) raw,COUNT(DISTINCT CASE WHEN rn=1 THEN vehicle_id END) shown '
      'FROM ranked',vals+list(qs)).fetchone()
  results.append({'모델':korean,'원자료 기록':row['raw'],'화면 표시 차량':row['shown']})
 return results

@functools.lru_cache(maxsize=16)
def duplicate_hotspots(year,limit=30):
 """Audit all brands, not only Kia: source rows vs distinct display models."""
 where,values=conditions('',int(year),None,None,False,False)
 sql=(_av_cte(where)+
  'SELECT maker_ko AS 제조사,MIN(model_ko) AS 대표명,year AS 연도,'
  'SUM(linked_record_count) AS 원자료,COUNT(*) AS 표시차량,'
  'SUM(linked_record_count)-COUNT(*) AS 통합기록 '
  'FROM ranked WHERE rn=1 GROUP BY maker_key,av_root,year '
  'HAVING SUM(linked_record_count)>COUNT(*) ORDER BY 통합기록 DESC LIMIT ?')
 with connection() as con:rows=con.execute(sql,values+[int(limit)]).fetchall()
 return [dict(x) for x in rows]


# Universally applied display/nationality integrity fixes (not per-example patches).
_AV_ISO_MAP = {'ABW': 'AW', 'AFG': 'AF', 'AGO': 'AO', 'AIA': 'AI', 'ALA': 'AX', 'ALB': 'AL', 'AND': 'AD', 'ARE': 'AE', 'ARG': 'AR', 'ARM': 'AM', 'ASM': 'AS', 'ATA': 'AQ', 'ATF': 'TF', 'ATG': 'AG', 'AUS': 'AU', 'AUT': 'AT', 'AZE': 'AZ', 'BDI': 'BI', 'BEL': 'BE', 'BEN': 'BJ', 'BES': 'BQ', 'BFA': 'BF', 'BGD': 'BD', 'BGR': 'BG', 'BHR': 'BH', 'BHS': 'BS', 'BIH': 'BA', 'BLM': 'BL', 'BLR': 'BY', 'BLZ': 'BZ', 'BMU': 'BM', 'BOL': 'BO', 'BRA': 'BR', 'BRB': 'BB', 'BRN': 'BN', 'BTN': 'BT', 'BVT': 'BV', 'BWA': 'BW', 'CAF': 'CF', 'CAN': 'CA', 'CCK': 'CC', 'CHE': 'CH', 'CHL': 'CL', 'CHN': 'CN', 'CIV': 'CI', 'CMR': 'CM', 'COD': 'CD', 'COG': 'CG', 'COK': 'CK', 'COL': 'CO', 'COM': 'KM', 'CPV': 'CV', 'CRI': 'CR', 'CUB': 'CU', 'CUW': 'CW', 'CXR': 'CX', 'CYM': 'KY', 'CYP': 'CY', 'CZE': 'CZ', 'DEU': 'DE', 'DJI': 'DJ', 'DMA': 'DM', 'DNK': 'DK', 'DOM': 'DO', 'DZA': 'DZ', 'ECU': 'EC', 'EGY': 'EG', 'ERI': 'ER', 'ESH': 'EH', 'ESP': 'ES', 'EST': 'EE', 'ETH': 'ET', 'FIN': 'FI', 'FJI': 'FJ', 'FLK': 'FK', 'FRA': 'FR', 'FRO': 'FO', 'FSM': 'FM', 'GAB': 'GA', 'GBR': 'GB', 'GEO': 'GE', 'GGY': 'GG', 'GHA': 'GH', 'GIB': 'GI', 'GIN': 'GN', 'GLP': 'GP', 'GMB': 'GM', 'GNB': 'GW', 'GNQ': 'GQ', 'GRC': 'GR', 'GRD': 'GD', 'GRL': 'GL', 'GTM': 'GT', 'GUF': 'GF', 'GUM': 'GU', 'GUY': 'GY', 'HKG': 'HK', 'HMD': 'HM', 'HND': 'HN', 'HRV': 'HR', 'HTI': 'HT', 'HUN': 'HU', 'IDN': 'ID', 'IMN': 'IM', 'IND': 'IN', 'IOT': 'IO', 'IRL': 'IE', 'IRN': 'IR', 'IRQ': 'IQ', 'ISL': 'IS', 'ISR': 'IL', 'ITA': 'IT', 'JAM': 'JM', 'JEY': 'JE', 'JOR': 'JO', 'JPN': 'JP', 'KAZ': 'KZ', 'KEN': 'KE', 'KGZ': 'KG', 'KHM': 'KH', 'KIR': 'KI', 'KNA': 'KN', 'KOR': 'KR', 'KWT': 'KW', 'LAO': 'LA', 'LBN': 'LB', 'LBR': 'LR', 'LBY': 'LY', 'LCA': 'LC', 'LIE': 'LI', 'LKA': 'LK', 'LSO': 'LS', 'LTU': 'LT', 'LUX': 'LU', 'LVA': 'LV', 'MAC': 'MO', 'MAF': 'MF', 'MAR': 'MA', 'MCO': 'MC', 'MDA': 'MD', 'MDG': 'MG', 'MDV': 'MV', 'MEX': 'MX', 'MHL': 'MH', 'MKD': 'MK', 'MLI': 'ML', 'MLT': 'MT', 'MMR': 'MM', 'MNE': 'ME', 'MNG': 'MN', 'MNP': 'MP', 'MOZ': 'MZ', 'MRT': 'MR', 'MSR': 'MS', 'MTQ': 'MQ', 'MUS': 'MU', 'MWI': 'MW', 'MYS': 'MY', 'MYT': 'YT', 'NAM': 'NA', 'NCL': 'NC', 'NER': 'NE', 'NFK': 'NF', 'NGA': 'NG', 'NIC': 'NI', 'NIU': 'NU', 'NLD': 'NL', 'NOR': 'NO', 'NPL': 'NP', 'NRU': 'NR', 'NZL': 'NZ', 'OMN': 'OM', 'PAK': 'PK', 'PAN': 'PA', 'PCN': 'PN', 'PER': 'PE', 'PHL': 'PH', 'PLW': 'PW', 'PNG': 'PG', 'POL': 'PL', 'PRI': 'PR', 'PRK': 'KP', 'PRT': 'PT', 'PRY': 'PY', 'PSE': 'PS', 'PYF': 'PF', 'QAT': 'QA', 'REU': 'RE', 'ROU': 'RO', 'RUS': 'RU', 'RWA': 'RW', 'SAU': 'SA', 'SDN': 'SD', 'SEN': 'SN', 'SGP': 'SG', 'SGS': 'GS', 'SHN': 'SH', 'SJM': 'SJ', 'SLB': 'SB', 'SLE': 'SL', 'SLV': 'SV', 'SMR': 'SM', 'SOM': 'SO', 'SPM': 'PM', 'SRB': 'RS', 'SSD': 'SS', 'STP': 'ST', 'SUR': 'SR', 'SVK': 'SK', 'SVN': 'SI', 'SWE': 'SE', 'SWZ': 'SZ', 'SXM': 'SX', 'SYC': 'SC', 'SYR': 'SY', 'TCA': 'TC', 'TCD': 'TD', 'TGO': 'TG', 'THA': 'TH', 'TJK': 'TJ', 'TKL': 'TK', 'TKM': 'TM', 'TLS': 'TL', 'TON': 'TO', 'TTO': 'TT', 'TUN': 'TN', 'TUR': 'TR', 'TUV': 'TV', 'TWN': 'TW', 'TZA': 'TZ', 'UGA': 'UG', 'UKR': 'UA', 'UMI': 'UM', 'URY': 'UY', 'USA': 'US', 'UZB': 'UZ', 'VAT': 'VA', 'VCT': 'VC', 'VEN': 'VE', 'VGB': 'VG', 'VIR': 'VI', 'VNM': 'VN', 'VUT': 'VU', 'WLF': 'WF', 'WSM': 'WS', 'YEM': 'YE', 'ZAF': 'ZA', 'ZMB': 'ZM', 'ZWE': 'ZW', 'UK': 'GB', 'EL': 'GR', 'XKX': 'XK', 'XK': 'XK', 'KOS': 'XK', 'ROM': 'RO', 'GRE': 'GR', 'GER': 'DE', 'SLO': 'SI', 'SUI': 'CH', 'BUL': 'BG', 'RSA': 'ZA', 'UAE': 'AE', 'KSA': 'SA', 'ENG': 'GB', 'SCO': 'GB', 'WAL': 'GB', 'NIR': 'GB'}
_AV_KNOWN_BRANDS = {'kia': 'KR', 'hyundai': 'KR', 'genesis': 'KR', 'ssangyong': 'KR', 'kgm': 'KR', 'daewoo': 'KR', 'renaultkorea': 'KR', 'bmw': 'DE', 'audi': 'DE', 'volkswagen': 'DE', 'vw': 'DE', 'mercedesbenz': 'DE', 'mercedes': 'DE', 'porsche': 'DE', 'opel': 'DE', 'maybach': 'DE', 'smart': 'DE', 'renault': 'FR', 'peugeot': 'FR', 'citroen': 'FR', 'dsautomobiles': 'FR', 'alpine': 'FR', 'bugatti': 'FR', 'dacia': 'RO', 'skoda': 'CZ', 'seat': 'ES', 'cupra': 'ES', 'jaguar': 'GB', 'landrover': 'GB', 'rollsroyce': 'GB', 'mini': 'GB', 'mg': 'GB', 'lotus': 'GB', 'mclaren': 'GB', 'astonmartin': 'GB', 'bentley': 'GB', 'vauxhall': 'GB', 'rover': 'GB', 'triumph': 'GB', 'morgan': 'GB', 'volvo': 'SE', 'polestar': 'SE', 'saab': 'SE', 'koenigsegg': 'SE', 'fiat': 'IT', 'ferrari': 'IT', 'lamborghini': 'IT', 'maserati': 'IT', 'alfaromeo': 'IT', 'lancia': 'IT', 'abarth': 'IT', 'pagani': 'IT', 'ford': 'US', 'tesla': 'US', 'chevrolet': 'US', 'cadillac': 'US', 'jeep': 'US', 'dodge': 'US', 'chrysler': 'US', 'ram': 'US', 'lincoln': 'US', 'buick': 'US', 'gmc': 'US', 'rivian': 'US', 'lucid': 'US', 'toyota': 'JP', 'lexus': 'JP', 'honda': 'JP', 'acura': 'JP', 'nissan': 'JP', 'infiniti': 'JP', 'subaru': 'JP', 'mazda': 'JP', 'suzuki': 'JP', 'mitsubishi': 'JP', 'isuzu': 'JP', 'daihatsu': 'JP', 'byd': 'CN', 'geely': 'CN', 'chery': 'CN', 'greatwall': 'CN', 'haval': 'CN', 'nio': 'CN', 'xpeng': 'CN', 'li': 'CN', 'zeekr': 'CN', 'hongqi': 'CN', 'holden': 'AU', 'tata': 'IN', 'mahindra': 'IN', 'maruti': 'IN', 'proton': 'MY', 'perodua': 'MY'}
_AV_MAKER_NAMES = {'kia': '기아', 'hyundai': '현대', 'genesis': '제네시스', 'ssangyong': '쌍용', 'kgm': 'KGM', 'bmw': 'BMW', 'audi': '아우디', 'volkswagen': '폭스바겐', 'vw': '폭스바겐', 'mercedesbenz': 'Mercedes-Benz', 'mercedes': 'Mercedes-Benz', 'porsche': '포르쉐', 'opel': '오펠', 'maybach': 'Mercedes-Maybach', 'smart': 'smart', 'renault': '르노', 'peugeot': '푸조', 'citroen': '시트로엥', 'dsautomobiles': 'DS Automobiles', 'alpine': '알핀', 'bugatti': '부가티', 'dacia': '다치아', 'skoda': 'Škoda', 'seat': 'SEAT', 'cupra': 'CUPRA', 'jaguar': '재규어', 'landrover': 'Land Rover', 'rollsroyce': 'Rolls-Royce', 'mini': 'MINI', 'mg': 'MG', 'lotus': 'Lotus', 'mclaren': 'McLaren', 'astonmartin': 'Aston Martin', 'bentley': 'Bentley', 'vauxhall': 'Vauxhall', 'rover': 'Rover', 'triumph': 'Triumph', 'morgan': 'Morgan', 'volvo': '볼보', 'polestar': 'Polestar', 'saab': 'Saab', 'koenigsegg': 'Koenigsegg', 'fiat': 'FIAT', 'ferrari': '페라리', 'lamborghini': '람보르기니', 'maserati': '마세라티', 'alfaromeo': 'Alfa Romeo', 'lancia': 'Lancia', 'abarth': 'Abarth', 'pagani': 'Pagani', 'ford': '포드', 'tesla': '테슬라', 'chevrolet': '쉐보레', 'cadillac': '캐딜락', 'jeep': 'Jeep', 'dodge': 'Dodge', 'chrysler': 'Chrysler', 'ram': 'RAM', 'lincoln': 'Lincoln', 'buick': 'Buick', 'gmc': 'GMC', 'rivian': 'Rivian', 'lucid': 'Lucid', 'toyota': '토요타', 'lexus': '렉서스', 'honda': '혼다', 'acura': 'Acura', 'nissan': '닛산', 'infiniti': 'Infiniti', 'subaru': '스바루', 'mazda': 'Mazda', 'suzuki': '스즈키', 'mitsubishi': '미쓰비시', 'isuzu': '이스즈', 'daihatsu': '다이하쓰', 'byd': 'BYD', 'geely': 'Geely', 'chery': 'Chery', 'greatwall': 'GWM', 'haval': 'Haval', 'nio': 'NIO', 'xpeng': 'XPENG', 'zeekr': 'ZEEKR', 'hongqi': '홍치', 'holden': 'Holden', 'tata': 'Tata', 'mahindra': 'Mahindra', 'maruti': 'Maruti Suzuki', 'proton': 'Proton', 'perodua': 'Perodua'}

def _av_maker_token(s):
 return re.sub(r'[^a-z0-9]','',str(s or '').casefold())

def _av_country_code(value):
 code=str(value or '').strip().upper()
 if code in ('','UNKNOWN','UNK','N/A','NONE','NULL','ZZ','XX','-','?'):
  return 'UNKNOWN'
 code=_AV_ISO_MAP.get(code,code)
 return code if re.fullmatch(r'[A-Z]{2}',code) else 'UNKNOWN'

def _av_maker_origin(maker,existing):
 return _AV_KNOWN_BRANDS.get(_av_maker_token(maker)) or _av_country_code(existing)

def _av_maker_name(maker,display):
 mk=_av_maker_token(maker)
 if mk in _AV_MAKER_NAMES:return _AV_MAKER_NAMES[mk]
 # Unknown/non-Latin maker names stay unchanged rather than inventing translations.
 return str(display or maker or '제조사 미확인')

# All 249 ISO countries use one normalization; flags for non-ISO region are retained unassigned.


_av_old_scrub=_av_scrub
def _av_scrub(text,maker=''):
 text=re.sub(r'(?<![a-z0-9])\d[.,]\d\s*[dti](?![a-z])',' ',str(text or ''),flags=re.I)
 text=re.sub(r'(?<![a-z0-9])(?:xdrive|sdrive|4matic|quattro|4motion)\s*\d{1,3}[a-z]*',' ',text,flags=re.I)
 root=_av_old_scrub(text,maker)
 # Engine suffixes such as 2.0d, 1.5T, 30d, xDrive30d are configurations, not model names.
 root=re.sub(r'(?<![a-z0-9])\d[.,]\d\s*[dti](?![a-z])','',root)
 root=re.sub(r'(?:xdrive|sdrive|4matic|quattro|4motion)\d{1,3}[a-z]*$','',root)
 # Retain X5 and 3008 model name numbers, do not strip stand-alone numeric names.
 token=_av_maker_token(maker)
 if token and root.startswith(token) and len(root)>len(token)+1:
  root=root[len(token):]
 return root
# do not change the semantically meaningful separate variants like Niro Plus.


_av_source_conditions = conditions
def conditions(query='',year=None,countries=None,maker=None,strict_model=False,unknown_year=False):
 where,values=_av_source_conditions(query,year,countries,maker,strict_model,unknown_year)
 for expression in (_EFFECTIVE_ORIGIN,"COALESCE(m.origin_code,'UNKNOWN')"):
  where=where.replace(expression,'k.origin')
 where=where.replace('m.maker_key=?','k.brand=?')
 if countries is not None and countries:
  start=1 if year is not None else 0
  values[start:start+len(countries)]=[_av_country_code(c) for c in countries]
 return where,values

_av_source_maker_options=maker_options
def maker_options(query='',year=None,countries=None,strict_model=False,unknown_year=False):
 rows=_av_source_maker_options(query,year,countries,strict_model,unknown_year)
 return [dict(row, name_ko=_av_maker_name(row['maker_key'],row['name_ko'])) for row in rows]

_av_source_vehicle=vehicle
def vehicle(vehicle_id):
 row=_av_source_vehicle(vehicle_id)
 if row:row['maker_ko']=_av_maker_name(row['maker_key'],row['maker_ko'])
 return row

# Country names in Korean follow current ISO territory names; map geography is unmodified.
@functools.lru_cache(maxsize=1)
def _av_territory_labels():
 from babel import Locale
 return Locale.parse('ko').territories

def country_name(code):
 code=_av_country_code(code)
 if code=='UNKNOWN':return '국적 확인 중'
 official={'GB':'영국','KR':'대한민국','US':'미국','FR':'프랑스','SI':'슬로베니아','XK':'코소보', 'TW':'대만','HK':'홍콩','MO':'마카오'}
 if code in official:return official[code]
 try: return _av_territory_labels().get(code) or country_names().get(code,'국가명 확인 중')
 except Exception:return country_names().get(code,'국가명 확인 중')

_av_source_map_for_year=map_for_year
@functools.lru_cache(maxsize=8)
def map_for_year(year):
 import copy
 data=copy.deepcopy(_av_source_map_for_year(year))
 for feature in data.get('features',[]):
  p=feature.get('properties') or {}
  codes=[_av_country_code(c) for c in p.get('country_codes',[])]
  codes=list(dict.fromkeys(c for c in codes if c!='UNKNOWN'))
  if codes:p['country_codes']=codes
  # Historical empires/territories retain their period-specific names.
  if int(year)>=2025 and len(codes)==1:
   name=country_name(codes[0])
   if name!='국가명 확인 중':p['name_ko']=name
 return data

# Format names consistently on results without changing search aliases in SQLite.
_av_old_search=search
@functools.lru_cache(maxsize=512)
def search(query='',year=None,countries=None,maker=None,strict_model=False,unknown_year=False,page=1,page_size=18):
 result=_av_old_search(query,year,countries,maker,strict_model,unknown_year,page,page_size)
 for row in result['rows']:
  row['maker_ko']=_av_maker_name(row['maker_key'],row['maker_ko'])
  raw=str(row.get('raw_model') or '')
  displayed=str(row.get('model_ko') or '')
  # Preserve important alphanumeric model identifiers (X5, i4, EV6, CX-5, 3008).
  raw=re.sub(r'(?<![a-z0-9])\d[.,]\d\s*[dti](?![a-z])',' ',raw,flags=re.I)
  raw=re.sub(r'(?<![a-z0-9])(?:xdrive|sdrive|4matic|quattro|4motion)\s*\d{1,3}[a-z]*',' ',raw,flags=re.I)
  core=_av_display(raw,raw,row['maker_key'])
  is_code=bool(re.search(r'(?i)\b(?:[a-z]{0,3}[- ]?\d{1,4}|\d{3,4}|[a-z]{1,3}[- ]?[a-z0-9]*\d)\b',core))
  if is_code and not re.search(r'\d{2,4}\s*(?:hp|ps|kw)',core,re.I):
   if core and len(core)<=35:row['model_ko']=core
  elif not displayed.strip():row['model_ko']=core or raw
 return result



# AUTOVERSE full-model identity + linked-record detail aggregation, v4.
# Keep raw vehicle IDs and the source catalog immutable.
# Configuration labels (wheel size, drivetrain, tire, options) are not new cars.
_AV_CONFIG_NOTE = re.compile(
 r'(?i)\b(?:\d{1,2}\s*(?:inch(?:es)?|in\.?|인치|\")\s*(?:alloy\s*)?(?:wheel\s*s?|rim\s*s?|휠|타이어)?|'
 r'(?:wheel\s*size|rim\s*size|휠\s*크기|wheel\s*diameter)\s*[:=]?\s*\d{1,2}\s*(?:in(?:ch)?|인치)?|'
 r'(?:with\s*)?(?:\d{1,2}\s*(?:inch|in)\s*)?(?:alloy\s*)?(?:wheel\s*s?|rim\s*s?)\s*(?:package|option)|'
 r'(?:tire|tyre|wheel)\s*package|\d{3}\s*/\s*\d{2}\s*r\d{2})\b|'
 r'\b(?:19|20|21|22)\s*인치(?:\s*(?:휠|타이어))?', re.I)
_AV_CONFIG_EXTRAS = re.compile(
 r'(?i)(?<![a-z0-9])(?:dual\s*motor|single\s*motor|rear\s*wheel\s*drive|'
 r'all\s*wheel\s*drive|front\s*wheel\s*drive|long\s*range|standard\s*range|'
 r'sport\s*edition|launch\s*edition|first\s*edition|'
 r'\d{1,3}\s*(?:kwh|kwh battery)|\d{1,3}\s*kw\s*motor)(?![a-z0-9])', re.I)
_AV_REMOVE_INSIDE_PARENS = re.compile(
 r'(?i)^\s*(?:\d{1,2}\s*(?:inch|inches|in|인치)|'
 r'\d{2,3}\s*kw|\d[.,]\d\s*(?:l|t|liter)|'
 r'(?:19|20|21|22)\s*인치|'
 r'wheel|tire|tyre|rim|awd|fwd|rwd|4wd|2wd|'
 r'hev|phev|bev|ev|hybrid|electric|diesel|gasoline|petrol|'
 r'performance|long\s*range|standard\s*range|'
 r'\d{2,3}\s*(?:hp|ps|kw)).*$',re.I)

def _av_clean_variant_name(s):
 s=str(s or '')
 # Keep parenthesized actual independent model names; remove only configuration parentheses.
 s=re.sub(r'\(([^)]*)\)',lambda m:' ' if _AV_REMOVE_INSIDE_PARENS.match(m.group(1)) else m.group(0),s)
 s=_AV_CONFIG_NOTE.sub(' ',s)
 s=_AV_CONFIG_EXTRAS.sub(' ',s)
 s=re.sub(r'\b(?:18|19|20|21|22)\s*(?:inch|in|인치)\s*(?:wheel|휠|타이어)s?\b',' ',s,flags=re.I)
 return re.sub(r'\s+',' ',s).strip(' ·•|,()[]')

# Reuse existing normalization logic for every manufacturer. Non-configuration model
# identifiers such as EV6, i4, X5, and 3008 are deliberately not removed.
_av_scrub_before_v4=_av_scrub
def _av_scrub(text,maker=''):
 return _av_scrub_before_v4(_av_clean_variant_name(text),maker)

_av_display_before_v4=_av_display
def _av_display(text,raw,maker):
 return _av_display_before_v4(_av_clean_variant_name(text),_av_clean_variant_name(raw),maker)

# A few non-semantic catalog suffixes require *explicit* model label aliases.
# Never discard "Fe" globally: Santa Fe is a genuine, different model name.
_AV_ROOT_ALIAS.update({'nirofe':'niro', '니로fe':'niro'})

# Index fingerprint changes on deployment even when source catalog does not.
_av_index_path_original=_av_index_path
@functools.lru_cache(maxsize=1)
def _av_index_path():
 # Existing index builder uses _av_scrub and _av_display dynamically. Change its
 # target filename via the source-code version salt, without replacing raw DB.
 return _av_index_path_v4()

@functools.lru_cache(maxsize=1)
def _av_index_path_v4():
 source=database_path();stat=source.stat()
 salt='av-v7-market-alias-historical-labels-20261109'
 fingerprint=hashlib.sha256((str(source.resolve())+':'+str(stat.st_size)+':'+str(stat.st_mtime_ns)+':'+salt).encode()).hexdigest()[:24]
 target=Path(tempfile.gettempdir())/('autoverse_display_index_'+fingerprint+'.sqlite')
 if target.is_file():
  try:
   with sqlite3.connect(target.as_uri()+'?mode=ro&immutable=1',uri=True) as c:
    if c.execute('SELECT fingerprint FROM av_meta').fetchone()==(fingerprint,):return target
  except (sqlite3.Error,OSError):pass
 with tempfile.TemporaryDirectory(prefix='autoverse_display_v4_') as d:
  output=Path(d)/'display.sqlite'
  with sqlite3.connect(output) as dest,_av_prev_connection() as original:
   dest.execute('PRAGMA synchronous=OFF');dest.execute('PRAGMA journal_mode=OFF')
   dest.execute('CREATE TABLE vehicle_keys(vehicle_id TEXT PRIMARY KEY,root TEXT NOT NULL,gen TEXT,face TEXT,origin TEXT NOT NULL,brand TEXT NOT NULL)')
   cursor=original.execute('SELECT v.vehicle_id,m.maker_key,n.raw_name,n.name_ko,m.origin_code'+_av_base)
   dest.executemany('INSERT INTO vehicle_keys VALUES(?,?,?,?,?,?)',(
     (vid,_av_root(maker,raw,ko),_av_gen(raw,ko),_av_facelift(raw,ko),_av_maker_origin(maker,origin),_av_brand_for_record(maker,raw,ko))
     for vid,maker,raw,ko,origin in cursor))
   dest.execute('CREATE INDEX ix_av_root_year ON vehicle_keys(root,origin)')
   dest.execute('CREATE TABLE av_meta(fingerprint TEXT NOT NULL)')
   dest.execute('INSERT INTO av_meta VALUES(?)',(fingerprint,));dest.commit()
  os.replace(output,target)
 return target

@functools.lru_cache(maxsize=1024)
def _av_group_members(vehicle_id):
 """Return originals represented by a displayed vehicle, preserving gen/FL signals."""
 with connection() as con:
  target=con.execute('SELECT v.year,k.brand,k.root,k.gen,k.face FROM vehicles v '
   'JOIN models n ON n.model_id=v.model_id JOIN av_idx.vehicle_keys k ON k.vehicle_id=v.vehicle_id '
   'WHERE v.vehicle_id=?',(vehicle_id,)).fetchone()
  if not target:return ()
  if target['year'] is None:return ((vehicle_id,'',''),)
  candidates=con.execute('SELECT v.vehicle_id,k.gen,k.face,n.raw_name,n.name_ko FROM vehicles v '
   'JOIN models n ON n.model_id=v.model_id JOIN av_idx.vehicle_keys k ON k.vehicle_id=v.vehicle_id '
   'WHERE v.year=? AND k.brand=? AND k.root=? '
   'ORDER BY v.vehicle_id',(target['year'],target['brand'],target['root'])).fetchall()
  gens={r['gen'] for r in candidates if r['gen']}
  faces={r['face'] for r in candidates if r['face']}
  matched=[(r['vehicle_id'],r['raw_name'],r['name_ko']) for r in candidates
   if (len(gens)<=1 or r['gen']==target['gen']) and
      (len(faces)<=1 or r['face']==target['face'])]
  return tuple(matched) if matched else ((vehicle_id,'',''),)

_AV_FUEL_TEXT={
 'gasoline':'휘발유','petrol':'휘발유','benzin':'휘발유','gas':'휘발유',
 'diesel':'경유','diesel fuel':'경유','lpg':'LPG','cng':'CNG',
 'electric':'전기','electricity':'전기','battery electric':'전기',
 'bev':'전기','ev':'전기','hev':'하이브리드','hybrid':'하이브리드',
 'phev':'플러그인 하이브리드','plug-in hybrid':'플러그인 하이브리드',
 'hydrogen':'수소','fuel cell':'수소(연료전지)','petrol/electric':'휘발유·전기',
 'gasoline/electric':'휘발유·전기','diesel/electric':'경유·전기',
 '휘발유':'휘발유','가솔린':'휘발유','경유':'경유','디젤':'경유',
 '전기':'전기','전기차':'전기','하이브리드':'하이브리드',
 '플러그인하이브리드':'플러그인 하이브리드',
}

def _av_is_fuel_field(label):
 s=re.sub(r'[^a-z0-9가-힣]','',str(label or '').casefold())
 return s in ('연료','연료종류','연료유형','연료구분','동력원','fuel','fueltype','fuelkind','fuelcategory','fuelsource')

def _av_fuel_word(value, spec=None):
 raw=str(value or '').strip();key=re.sub(r'\s+',' ',raw.casefold())
 if key in _AV_FUEL_TEXT:return _AV_FUEL_TEXT[key]
 # No universal numeric fuel codebook exists. Honour explicit source codebook
 # when supplied; otherwise mark the original code as unresolved.
 if re.fullmatch(r'\d+(?:\.0+)?',raw):
  book=(spec or {}).get('codebook') or (spec or {}).get('enum_map') or {}
  if isinstance(book,dict) and (raw in book or str(int(float(raw))) in book):
   return _av_fuel_word(book.get(raw,book.get(str(int(float(raw))))),{})
  return '원자료 코드 '+raw+' (정의 미확인)'
 return raw

def _av_fuels_in_name(name):
 s=str(name or '').casefold();out=[]
 # Named variants are evidence of marketed powertrain; not a decoded fuel enum.
 for pat,label in [(r'\bphev\b|plug[ -]?in\s*hybrid|플러그인\s*하이브리드','플러그인 하이브리드'),
  (r'\bhev\b|\bmhev\b|\bhybrid\b|하이브리드','하이브리드'),
  (r'\bbev\b|\bev\b|\belectric\b|전기차','전기'),
  (r'\bdiesel\b|\btdi\b|\bcrdi\b|경유|디젤','경유'),
  (r'\bgasoline\b|\bpetrol\b|\bgdi\b|휘발유|가솔린','휘발유')]:
  if re.search(pat,s):out.append(label)
 return out

def _av_number(value):
 if isinstance(value,bool):return None
 if isinstance(value,(int,float)):
  f=float(value);return f if math.isfinite(f) else None
 s=str(value or '').strip()
 if not s:return None
 s=re.sub(r'(?<=\d),(?=\d{3}(?:\D|$))','',s)
 try:
  if re.fullmatch(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)',s):
   f=float(s)
   return f if math.isfinite(f) else None
 except (ValueError,OverflowError):pass
 return None

def _av_numeric_endpoints(spec):
 nums=[]
 for field in ('min','max'):
  f=_av_number(spec.get(field))
  if f is not None:nums.append(f)
 v=spec.get('value')
 f=_av_number(v)
 if f is not None:nums.append(f)
 elif isinstance(v,str):
  parts=re.split(r'\s*[~～–—]\s*|\s+-\s+',v.strip(),maxsplit=1)
  if len(parts)==2:
   first,last=map(_av_number,parts)
   if first is not None and last is not None:nums.extend((first,last))
 return nums

def _av_format_number(v):
 return f'{int(v):,}' if float(v).is_integer() else f'{v:,.6f}'.rstrip('0').rstrip('.')

_AV_SPEC_LABELS={
 'overalllength':'전장','차량길이':'전장',
 'overallwidth':'전폭','차량너비':'전폭',
 'overallheight':'전고','차량높이':'전고',
 'wheelbase':'축거','축간거리':'축거',
 'curbweight':'공차중량','kerbweight':'공차중량',
 'displacement':'배기량','엔진배기량':'배기량',
 'maximumtorque':'최대토크','maxtorque':'최대토크',
 'maximumpower':'최고출력','maxpower':'최고출력','최대출력':'최고출력',
 'drivetrain':'구동방식','drivetype':'구동방식','구동방식':'구동방식',
}
_AV_SPEC_UNITS={
 '밀리미터':'mm','미터':'m','킬로그램':'kg','킬로와트':'kW',
 '킬로와트시':'kWh','㎜':'mm','㎏':'kg','kw':'kW','kwh':'kWh',
 '㎤':'cc','cm3':'cc','cm³':'cc','cc':'cc','n·m':'N·m','nm':'N·m',
}

def _av_merge_specs(all_specs,model_names):
 grouped={}
 for spec in all_specs:
  if not isinstance(spec,dict):continue
  label=str(spec.get('label_ko') or '').strip()
  if not label:continue
  label=_AV_SPEC_LABELS.get(normalize(label),label)
  unit=str(spec.get('unit') or spec.get('unit_ko') or '').strip()
  unit=_AV_SPEC_UNITS.get(unit.casefold(),unit)
  fuel=_av_is_fuel_field(label)
  key=('연료', '') if fuel else (label,unit)
  cell=grouped.setdefault(key,{'label_ko':key[0],'unit':key[1],'numbers':[],'texts':[]})
  val=spec.get('value')
  if fuel:
   if val is not None:cell['texts'].append(_av_fuel_word(val,spec))
  else:
   nums=_av_numeric_endpoints(spec)
   if nums:cell['numbers'].extend(nums)
   elif val is not None and str(val).strip():cell['texts'].append(str(val).strip())
 variant_fuels=[]
 for name in model_names:variant_fuels.extend(_av_fuels_in_name(name))
 if variant_fuels:
  cell=grouped.setdefault(('연료',''),{'label_ko':'연료','unit':'','numbers':[],'texts':[]})
  cell['texts'].extend(variant_fuels)
 output=[]
 for item in grouped.values():
  nums=item['numbers'];texts=list(dict.fromkeys(item['texts']))
  if nums:
   lo,hi=min(nums),max(nums)
   result=_av_format_number(lo) if lo==hi else _av_format_number(lo)+'~'+_av_format_number(hi)
   if texts:result+=', '+', '.join(texts)
  else:result=', '.join(texts) if texts else '미확인'
  output.append({'label_ko':item['label_ko'],'value':result,'unit':item['unit']})
 return output

@functools.lru_cache(maxsize=256)
def load_group_details(vehicle_id):
 """Merge source-linked facts from the same displayed model/year/gen/FL.
 Numeric specifications aggregate as min~max only within the SAME units.
 Unknown fuel code meanings are never guessed. No source database rows are deleted.
 """
 members=_av_group_members(vehicle_id)
 selected=load_details(vehicle_id)
 if not members:return selected
 result=dict(selected)
 all_specs=[];all_names=[];photos=[];sources=[];seen_photos=set();seen_sources=set();histories=[]
 for vid,raw_name,ko_name in members:
  all_names.append(raw_name);all_names.append(ko_name)
  try:detail=load_details(vid)
  except (OSError,ValueError,KeyError,json.JSONDecodeError):continue
  if not isinstance(detail,dict):continue
  all_specs.extend(detail.get('specifications',[]) if isinstance(detail.get('specifications'),list) else [])
  if detail.get('history_ko'):histories.append(str(detail['history_ko']))
  for p in detail.get('photos',[]):
   if not isinstance(p,dict):continue
   loc=p.get('path') or p.get('url')
   if loc and loc not in seen_photos and len(photos)<10:seen_photos.add(loc);photos.append(p)
  for src in detail.get('sources',[]):
   if not isinstance(src,dict):continue
   url=src.get('url')
   if url and url not in seen_sources and len(sources)<100:seen_sources.add(url);sources.append(src)
 result['specifications']=_av_merge_specs(all_specs,all_names)
 if photos:result['photos']=photos
 if sources:result['sources']=sources
 if histories:result['history_ko']=max(histories,key=lambda s:len(s))
 result['linked_original_count']=len(members)
 result['aggregation_truncated']=False
 result['origin_ids_preserved']=True
 return result


# Apply the same public-facing model name in detailed view (not just search cards).
_av_detail_vehicle_before_v4=vehicle
def vehicle(vehicle_id):
 row=_av_detail_vehicle_before_v4(vehicle_id)
 if row:
  row['model_ko']=_av_display(row.get('model_ko'),row.get('model_ko'),row.get('maker_key'))
 return row


# v5: consistent brand identities, modern country labels, and family-level RV names.
# No extra screen/list/flag is created for records lacking an English source name.
_AV_CAMPER_MAKERS = {
 'dethleffs','adria','sunliving','laika','hymer','hobby','knaus',
 'weinsberg','carado','buerstner','burstner','rapido','pilote','rollerteam',
 'benimar','chausson','challenger','eura','euramobil','mobilvetta',
 'mclouis','frankia','concorde','niesmannbischoff','sunlight',
 'autotrail','swift','bailey','eldis','autostar','phoenix','phoeni x',
 'ci','rimor','malibu','carthago',
}
_AV_BRAND_VISIBLE = {
 'fojiaxing':'Fo Jia Xing',
 'jaguarlandroverlimited':'Jaguar Land Rover',
 'jaguarlandrover':'Jaguar Land Rover',
}
_AV_CANONICAL_MODEL_LABELS = {
 ('kia','soul'):'쏘울', ('kia','niro'):'니로',
 ('kia','seltos'):'셀토스',('kia','sportage'):'스포티지',
 ('kia','sorento'):'쏘렌토',('kia','carnival'):'카니발',
 ('hyundai','sonata'):'쏘나타',('hyundai','elantra'):'아반떼',
 ('hyundai','tucson'):'투싼',('hyundai','santafe'):'싼타페',
 ('hyundai','grandeur'):'그랜저',('hyundai','kona'):'코나',
 ('hyundai','ioniq5'):'아이오닉 5',('hyundai','ioniq6'):'아이오닉 6',
 ('genesis','gv70'):'GV70',('genesis','gv80'):'GV80',
}
_AV_ROOT_ALIAS.update({
 '쏘울':'soul','소울':'soul','솔':'soul','soul':'soul',
 '솔에코다이내믹스':'soul','소울에코다이내믹스':'soul',
 'soulecodynamics':'soul',
})

def _av_is_jlr_legal(maker):
 t=_av_maker_token(maker)
 return bool(t=='jlr' or re.search(r'jaguar.*landrover|jaguar.*rover|재규어.*랜드로버|재그아.*랜드로버',t))

def _av_brand_for_record(maker,raw,ko):
 """Classify only brand-identifiable JLR legal-entity records. Others stay in source DB."""
 mk=_av_maker_token(maker)
 if not _av_is_jlr_legal(maker):return mk
 s=_av_nfkc(raw)+' '+_av_nfkc(ko)
 jaguar=bool(re.search(r'(?i)\b(jaguar|f[- ]?pace|e[- ]?pace|i[- ]?pace|f[- ]?type|xj[0-9a-z]*|xf|xe|xk[0-9a-z]*|s[- ]?type)\b|재규어|재그아',s))
 rover=bool(re.search(r'(?i)\b(land\s*rover|range\s*rover|defender|discovery|freelander|evoque|velar|lr[234])\b|랜드\s*로버|디스커버리|디펜더|레인지\s*로버',s))
 # Don't let the manufacturer's name itself classify both brands; examine the model text only.
 if jaguar and not rover:return 'jaguar'
 if rover and not jaguar:return 'landrover'
 return 'jlr_unclassified'

def _av_camper_family(text,maker):
 """Plan/bed/layout suffixes are variants, not distinct motorhome nameplate families."""
 if _av_maker_token(maker) not in _AV_CAMPER_MAKERS:return str(text or '')
 s=str(text or '').strip()
 # E.g. JUST GO T6615, JUST GO T45 -> JUST GO (verified Dethleffs family).
 # E.g. Coral XL 670 SL -> Coral XL. Avoid removing names consisting only of digits.
 if re.search(r'(?i)\b(?:just\s*go|coral(?:\s*xl)?|matrix|compact|ecovip|kosmo|sky\s*wave|sun\s*living)\b',s):
  s=re.sub(r'(?i)\s+(?:T\s*\d{2,5}|[LP]\s*\d{3,5}|\d{3,5})(?:\s+[A-Z]{1,4}|\s+\d[A-Z]?)?\s*$', '', s)
 elif len(s.split())>=3:
  s=re.sub(r'(?i)\s+(?:T\s*\d{2,5}|[LP]\s*\d{3,5}|\d{3,5})(?:\s+[A-Z]{1,4})?\s*$', '', s)
 return s.strip()

_av_scrub_before_v5=_av_scrub
def _av_scrub(text,maker=''):
 s=_av_camper_family(text,maker)
 if _av_maker_token(maker)=='kia':
  s=re.sub(r'(?i)\b(?:eco\s*dynamics|eco\s*dynamic)\b|에코\s*다이내믹스',' ',s)
 return _av_scrub_before_v5(s,maker)

_av_display_before_v5=_av_display
def _av_display(text,raw,maker):
 s=_av_camper_family(text,maker)
 s=_av_display_before_v5(s,_av_camper_family(raw,maker),maker)
 if _av_maker_token(maker)=='kia':
  s=re.sub(r'(?i)\b(?:eco\s*dynamics|eco\s*dynamic)\b|에코\s*다이내믹스',' ',s)
 return re.sub(r'\s+',' ',s).strip()

def _av_final_model_name(maker,display,raw):
 key=_av_root(maker,raw,display)
 if (maker,key) in _AV_CANONICAL_MODEL_LABELS:return _AV_CANONICAL_MODEL_LABELS[(maker,key)]
 if _av_maker_token(maker) in _AV_CAMPER_MAKERS and re.search('[A-Za-z]',str(raw or '')):
  return _av_display(raw,raw,maker) or str(display or raw)
 korean_count=sum('가'<=ch<='힣' for ch in str(display or ''))
 if korean_count>=6 and re.search('[A-Za-z]',str(raw or '')):
  return _av_display(raw,raw,maker) or str(display or raw)
 return _av_display(display,raw,maker) or str(display or raw)

_av_maker_name_before_v5=_av_maker_name
def _av_maker_name(maker,display):
 mk=_av_maker_token(maker)
 if mk in _AV_BRAND_VISIBLE:return _AV_BRAND_VISIBLE[mk]
 value=_av_maker_name_before_v5(maker,display)
 if sum('가'<=ch<='힣' for ch in str(value))>=6 and re.fullmatch(r'[a-z0-9_-]+',str(maker or ''),re.I):
  return mk.upper() if len(mk)<=5 else mk[:1].upper()+mk[1:]
 return value

# Stable national-brand filters. Raw source rows remain available in the original database.
_av_conditions_before_v5=conditions
def conditions(query='',year=None,countries=None,maker=None,strict_model=False,unknown_year=False):
 where,values=_av_conditions_before_v5(query,year,countries,maker,strict_model,unknown_year)
 # Prevent discontinued marque registration/observation dates from masquerading as new model years.
 add=("(k.brand <> 'jlr_unclassified')",
      "NOT (k.brand='holden' AND v.year>2020)",
      "NOT (k.brand='delorean' AND v.year>1982)")
 where+=(' AND ' if where else ' WHERE ')+' AND '.join(add)
 return where,values

@functools.lru_cache(maxsize=256)
def maker_options(query='',year=None,countries=None,strict_model=False,unknown_year=False):
 countries=tuple(countries) if countries is not None else None
 where,values=conditions(query,year,countries,None,strict_model,unknown_year)
 with connection() as con:
  rows=con.execute('SELECT k.brand AS maker_key,MIN(m.name_ko) AS maker_display '+BASE+where+
                   ' GROUP BY k.brand ORDER BY maker_display',values).fetchall()
 return [{'maker_key':r['maker_key'],'name_ko':_av_maker_name(r['maker_key'],r['maker_display'])} for r in rows]

_av_search_before_v5=search
@functools.lru_cache(maxsize=512)
def search(query='',year=None,countries=None,maker=None,strict_model=False,unknown_year=False,page=1,page_size=18):
 countries=tuple(countries) if countries is not None else None
 result=_av_search_before_v5(query,year,countries,maker,strict_model,unknown_year,page,page_size)
 for row in result['rows']:
  row['maker_ko']=_av_maker_name(row['maker_key'],row['maker_ko'])
  row['model_ko']=_av_final_model_name(row['maker_key'],row['model_ko'],row.get('raw_model',''))
 return result

_av_vehicle_before_v5=vehicle
def vehicle(vehicle_id):
 row=_av_vehicle_before_v5(vehicle_id)
 if row:
  with connection() as con:
   r=con.execute('SELECT n.raw_name FROM vehicles v JOIN models n ON v.model_id=n.model_id WHERE v.vehicle_id=?',(vehicle_id,)).fetchone()
  row['model_ko']=_av_final_model_name(row['maker_key'],row['model_ko'],r['raw_name'] if r else '')
  row['maker_ko']=_av_maker_name(row['maker_key'],row['maker_ko'])
 return row

_av_map_for_year_before_v5=map_for_year
@functools.lru_cache(maxsize=8)
def map_for_year(year):
 # A map feature sometimes has the correct name but no modern ISO code. Repair the
 # explicit geographic state, without assigning colonies or overseas territories to FR.
 data=_av_map_for_year_before_v5(year)
 for feature in data.get('features',[]):
  p=feature.get('properties') or {}
  name=str(p.get('name_ko') or p.get('name') or p.get('name_en') or '').strip()
  english=str(p.get('name') or p.get('name_en') or '').strip()
  codes=[_av_country_code(c) for c in p.get('country_codes',[])]
  codes=list(dict.fromkeys(c for c in codes if c!='UNKNOWN'))
  fr=bool(re.match(r'^(프랑스(?!령|어|계|만|계곡)|불란서)(?:\s|$|제|왕|공|제국)',name) or
    re.fullmatch(r'(?i)(?:France|French (?:Fifth|Fourth|Third|Second|First) Republic|French Republic|Kingdom of France|French Empire|First French Empire|Second French Empire)',english))
  gb=bool(re.search(r'(?:그레이트\s*브리튼|그레이트브리튼|영국|연합왕국)',name) or
    re.fullmatch(r'(?i)(?:Great Britain|Kingdom of Great Britain|United Kingdom(?: of Great Britain(?: and Ireland)?)?)',english))
  if fr and 'FR' not in codes:codes.append('FR')
  if gb and 'GB' not in codes and int(year)>=1707:codes.append('GB')
  if codes:p['country_codes']=codes
  if len(codes)==1 and codes[0]=='FR' and fr:p['name_ko']='프랑스'
  if int(year)>=1801 and len(codes)==1 and codes[0]=='GB' and gb:p['name_ko']='영국'
 return data


# V6: market-specific names, localized labels and regional identity.
# This section is intentionally data-preserving. Only the derived presentation index
# and result rows are changed, never the raw SQLite catalogue.
_AV_MODEL_BRAND_NAMES = {
 # Domestic names are canonical for models actually sold in Korea.
 ('kia','picanto'):'모닝',('kia','cerato'):'K3',('kia','optima'):'K5',
 ('kia','cadenza'):'K7',('kia','quoris'):'K9',('kia','sedona'):'카니발',
 ('kia','rondo'):'카렌스',('kia','borrego'):'모하비',
 ('kia','stonic'):'스토닉',('kia','xceed'):'XCeed',
 ('kia','telluride'):'텔루라이드',('kia','soul'):'쏘울',
 ('hyundai','sonata'):'쏘나타',('hyundai','verna'):'베르나',
 ('hyundai','venue'):'베뉴',('hyundai','bayon'):'BAYON',
 ('hyundai','santacruz'):'SANTA CRUZ',('hyundai','stargazer'):'STARGAZER',
 ('hyundai','inster'):'INSTER',('hyundai','creta'):'CRETA',
 ('hyundai','aura'):'AURA',('hyundai','exter'):'EXTER',
 ('hyundai','hb20s'):'HB20S',('hyundai','alcazar'):'ALCAZAR',
 ('hyundai','elexio'):'ELEXIO',
}
_AV_KOREAN_BAD_ROMANIZATION = {
 '소너트':('hyundai','sonata'), '소나트':('hyundai','sonata'),
 '솔':('kia','soul'),'쎄라토':('kia','cerato'),'세라토':('kia','cerato'),
 '에스티오엔아이씨':('kia','stonic'), '엑스씨이이디':('kia','xceed'),
 '텔어아이드':('kia','telluride'), '텔루라이드':('kia','telluride'),
 '버너':('hyundai','verna'),'벤우':('hyundai','venue'),
 '비에이와이오엔':('hyundai','bayon'), '샌터크루즈':('hyundai','santacruz'),
 '샌터 크루즈':('hyundai','santacruz'),'스타르게이저':('hyundai','stargazer'),
 '아이엔에스티이아르':('hyundai','inster'),
 '씨아르이티에이':('hyundai','creta'),
 '오러':('hyundai','aura'), '이엑스티이아르':('hyundai','exter'),
 '에이치비20에스':('hyundai','hb20s'), '에이치비 20 에스':('hyundai','hb20s'),
 '알커자':('hyundai','alcazar'), '이엘이엑스아이오':('hyundai','elexio'),
 '쏘나타':('hyundai','sonata'),
 '피칸토':('kia','picanto'), '모닝':('kia','picanto'),
 '씨드':('kia','ceed'), '엑씨드':('kia','xceed'),
}
_AV_MARKET_ALIASES = {
 'kia':{
  'morning':'picanto','picanto':'picanto','morningurban':'picanto',
  'cerato':'cerato','forte':'cerato','k3':'cerato',
  'optima':'optima','k5':'optima',
  'cadenza':'cadenza','k7':'cadenza',
  'k900':'quoris','quoris':'quoris','k9':'quoris',
  'sedona':'sedona','carnival':'sedona',
  'rondo':'rondo','carens':'rondo',
  'borrego':'borrego','mohave':'borrego',
  'xceed':'xceed','xcee d':'xceed',
 },
 'hyundai':{
  'sonata':'sonata','소너트':'sonata',
  'avante':'elantra','elantra':'elantra','아반떼':'elantra',
  'accent':'verna','verna':'verna',
  'hb20s':'hb20s','hb20':'hb20',
 },
}
_AV_STRIPPER = re.compile(r'[^a-z0-9가-힣]',re.I)
_AV_BRAND_LEGAL_ALIASES = {
 'kiamotors':'kia','kiacorporation':'kia','kiamotorscorporation':'kia',
 'kiamotorsamerica':'kia','kiamotorsindia':'kia','kiaindia':'kia',
 'hyundaimotor':'hyundai','hyundaimotors':'hyundai',
 'hyundaimotorcompany':'hyundai','hyundaimotorindia':'hyundai',
 'hyundaimotorsindia':'hyundai',
 'bmwag':'bmw','volkswagenag':'volkswagen',
 'mercedesbenzag':'mercedesbenz','aud iag':'audi',
 'peugeotautomobiles':'peugeot','automobilespeugeot':'peugeot',
 'citroencars':'citroen','automobilescitroen':'citroen',
}

_av_maker_token_v5=_av_maker_token
def _av_maker_token(s):
 import unicodedata
 z=unicodedata.normalize('NFKD',str(s or ''))
 z=''.join(c for c in z if not unicodedata.combining(c))
 return re.sub(r'[^a-z0-9]','',z.casefold())

_av_brand_for_record_v5=_av_brand_for_record
def _av_brand_for_record(maker,raw,ko):
 prev=_av_brand_for_record_v5(maker,raw,ko)
 return _AV_BRAND_LEGAL_ALIASES.get(prev,prev)

_av_root_v5=_av_root
@functools.lru_cache(maxsize=131072)
def _av_root(maker,raw,ko):
 brand=_av_brand_for_record(maker,raw,ko)
 original=_av_root_v5(maker,raw,ko)
 original=_AV_STRIPPER.sub('',original.casefold())
 # Explicitly recognized corrupt syllable-by-syllable transliterations.
 for candidate in (ko,raw):
  normalized=_AV_STRIPPER.sub('',str(candidate or '').casefold())
  mapping=_AV_KOREAN_BAD_ROMANIZATION.get(normalized)
  if mapping and mapping[0]==brand:
   return _AV_MARKET_ALIASES.get(brand,{}).get(mapping[1],mapping[1])
 table=_AV_MARKET_ALIASES.get(brand,{})
 if original in table:return table[original]
 # Some source models include a marque prefix; old scrub handles most of these.
 tokens=[_AV_STRIPPER.sub('',str(v or '').casefold()) for v in (raw,ko)]
 for token in tokens:
  if token in table:return table[token]
 return original

_av_scrub_v5=_av_scrub
def _av_scrub(text,maker=''):
 s=_av_scrub_v5(text,maker)
 # Dedicated to RV layout variants, not generic numeric passenger-car names.
 if _av_maker_token(maker) in _AV_CAMPER_MAKERS:
  s=re.sub(r'(?:[tlp]?\d{3,5}[a-z]{0,3})$','',s)
 return s

_av_final_model_name_v5=_av_final_model_name
def _av_final_model_name(maker,display,raw):
 brand=_AV_BRAND_LEGAL_ALIASES.get(_av_maker_token(maker),_av_maker_token(maker))
 key=_av_root(brand,raw,display)
 label=_AV_MODEL_BRAND_NAMES.get((brand,key))
 if label:return label
 return _av_final_model_name_v5(brand,display,raw)

_av_maker_name_v5=_av_maker_name
def _av_maker_name(maker,display):
 brand=_AV_BRAND_LEGAL_ALIASES.get(_av_maker_token(maker),_av_maker_token(maker))
 known=_AV_MAKER_NAMES.get(brand)
 if known:return known
 v=_av_maker_name_v5(maker,display)
 if sum('가'<=c<='힣' for c in v)>=6:
  # No additional warning, category or unknown-name list is generated.
  return re.sub(r'[_\-]+',' ',str(maker)).strip().title() or v
 return v

# Add search aliases to the same SQL predicate, if the query equals a known
# model name (e.g. Picanto must find domestic-only Morning records too).
_av_conditions_v5=conditions
def conditions(query='',year=None,countries=None,maker=None,strict_model=False,unknown_year=False):
 where,values=_av_conditions_v5(query,year,countries,maker,strict_model,unknown_year)
 q=normalize(query)
 target=None
 for brand,mappings in _AV_MARKET_ALIASES.items():
  if q in mappings:target=(brand,mappings[q]);break
  bad=_AV_KOREAN_BAD_ROMANIZATION.get(q)
  if bad and bad[0]==brand:target=(brand,mappings.get(bad[1],bad[1]));break
 if not target:return where,values
 phrase="(n.search_text LIKE ? ESCAPE '\\' OR n.initials LIKE ? ESCAPE '\\' OR m.search_text LIKE ? ESCAPE '\\')"
 if phrase not in where:return where,values
 where=where.replace(phrase,'('+phrase+' OR (k.brand=? AND k.root=?))')
 values.extend(target)
 return where,values

# The canonical map label logic intentionally applies to all post-1800 years;
# it does not replace names of unrelated historic states or overseas holdings.
_av_map_for_year_v5=map_for_year
@functools.lru_cache(maxsize=12)
def map_for_year(year):
 return _av_map_for_year_v5(year)


# V7: historically correct Korean domestic model names. For example the
# 2004 Cerato must NOT be relabelled as K3 (introduced years later).
def _av_local_model_label(maker,raw,ko,year):
 brand=_AV_BRAND_LEGAL_ALIASES.get(_av_maker_token(maker),_av_maker_token(maker))
 key=_av_root(brand,raw,ko)
 try:year=int(year)
 except (ValueError,TypeError):year=None
 if brand=='kia' and key=='cerato':
  if year is None:return '세라토 / 포르테 / K3'
  if year<2008:return '세라토'
  if year<2012:return '포르테'
  return 'K3'
 if brand=='kia' and key=='optima':
  if year is None:return '옵티마 / 로체 / K5'
  if year<2006:return '옵티마'
  if year<2010:return '로체'
  return 'K5'
 if brand=='hyundai' and key=='elantra' and year is not None and year<=1995:
  return '엘란트라'
 return _av_final_model_name(brand,ko,raw)

_av_search_v6=search
@functools.lru_cache(maxsize=512)
def search(query='',year=None,countries=None,maker=None,strict_model=False,unknown_year=False,page=1,page_size=18):
 result=_av_search_v6(query,year,countries,maker,strict_model,unknown_year,page,page_size)
 for row in result['rows']:
  row['model_ko']=_av_local_model_label(row['maker_key'],row.get('raw_model'),row.get('model_ko'),row.get('year'))
 return result

_av_vehicle_v6=vehicle
def vehicle(vehicle_id):
 row=_av_vehicle_v6(vehicle_id)
 if row:
  with connection() as con:
   raw=con.execute('SELECT n.raw_name FROM vehicles v JOIN models n ON v.model_id=n.model_id '
                   'WHERE v.vehicle_id=?',(vehicle_id,)).fetchone()
  row['model_ko']=_av_local_model_label(row['maker_key'],raw['raw_name'] if raw else '',row['model_ko'],row.get('year'))
 return row

# V8: GLOBAL (not Korea-only) model identity and year-dependent corporate identity.
# Treat raw rows as observations: never delete them. Canonical presentation and
# counts are derived from the same per-vehicle index, regardless of country.
_AV_GLOBAL_LEGAL_BRANDS={
 'kiamotors':'kia','kiacorporation':'kia','bmwag':'bmw',
 'audiag':'audi',
 'volkswagenag':'volkswagen','vw':'volkswagen',
 'mercedesbenzag':'mercedesbenz','mercedes':'mercedesbenz',
 'fordmotorcompany':'ford','fordmotorco':'ford',
 'toyotamotorcorporation':'toyota','toyotamotor':'toyota',
 'hondamotorco':'honda','hondamotor':'honda',
 'nissanmotor':'nissan','nissanmotorco':'nissan',
 'mazdamotorcorporation':'mazda','mazdamotor':'mazda',
 'subarucorporation':'subaru','fujiheavyindustries':'subaru',
 'opelautomobilegmbh':'opel','opelautomobile':'opel',
 'skodaauto':'skoda','skodaautoas':'skoda',
 'seat sa':'seat','seatsa':'seat',
 'peugeotautomobiles':'peugeot','automobilespeugeot':'peugeot',
 'automobilescitroen':'citroen','citroencars':'citroen',
 'hyundaimotorcompany':'hyundai','hyundaimotor':'hyundai',
 'hyundaimotors':'hyundai',
 'ssangyongmotorcompany':'ssangyong','ssangyongmotor':'ssangyong',
 'ssangyongmotors':'ssangyong',
 'kgmobility':'kgm','kgmobilitycorporation':'kgm','kgmotors':'kgm',
 'renaultsamsungmotors':'renaultsamsung','renaultsamsungmotor':'renaultsamsung',
 'renaultkoreamotors':'renaultkorea','renaultkorea':'renaultkorea',
 'samsungmotors':'samsungmotors',
}
_AV_MARKET_ALIASES.update({
 'toyota':{'vitz':'yaris','yaris':'yaris'},
 'honda':{'jazz':'fit','fit':'fit'},
 'mazda':{'demio':'mazda2','mazda2':'mazda2','axela':'mazda3','mazda3':'mazda3',
          'atenza':'mazda6','mazda6':'mazda6'},
 'nissan':{'dualis':'qashqai','qashqai':'qashqai'},
 'subaru':{'xv':'crosstrek','crosstrek':'crosstrek','xvcrosstrek':'crosstrek'},
 'volkswagen':{'rabbit':'golf','golf':'golf','golfgti':'golf','golfgtd':'golf',
               'golfgte':'golf','golfr':'golf','golfrline':'golf'},
 'peugeot':{'e208':'208','208':'208','e2008':'2008','2008':'2008',
            'e308':'308','308':'308'},
 'opel':{'corsae':'corsa','corsa':'corsa'},
 'skoda':{'octaviars':'octavia','octavia':'octavia'},
 'seat':{'leonfr':'leon','leon':'leon'},
 'mini':{'cooperse':'cooper','cooper':'cooper'},
})
_AV_MAKER_WORDS.update({
 'ssangyong':['ssangyong','ssang yong','쌍용','kgm','kg mobility','kg모빌리티'],
 'kgm':['ssangyong','ssang yong','쌍용','kgm','kg mobility','kg모빌리티'],
 'renaultsamsung':['renault samsung','renaultsamsung','르노삼성','삼성자동차'],
 'renaultkorea':['renault korea','renault korea motors','르노코리아','르노코리아자동차','르노삼성'],
 'volkswagen':['volkswagen','폭스바겐','vw'],
 'mazda':['mazda','마쓰다','마쯔다','마즈다'],
 'toyota':['toyota','도요타','토요타'],
 'honda':['honda','혼다'],
 'nissan':['nissan','닛산'],
 'subaru':['subaru','스바루'],
 'peugeot':['peugeot','푸조'],
 'ford':['ford','포드'],
 'skoda':['skoda','스코다'],
 'opel':['opel','오펠'],
})
_AV_KNOWN_BRANDS.update({
 'renaultsamsung':'KR','renaultkorea':'KR','samsungmotors':'KR',
 'kgmobility':'KR','ssangyongmotor':'KR',
 'fiat':'IT','ford':'US',
})
_AV_MAKER_NAMES.update({'renaultsamsung':'르노삼성','renaultkorea':'르노코리아','samsungmotors':'삼성자동차',
                        'ssangyong':'쌍용','kgm':'KGM'})

# These aliases are approved pairs of market names under the SAME manufacturer.
# Different marques, model lines and generations must not be joined by fuzzy name.
def _av_canonical_brand_year(maker,raw,ko,year):
 mk=_av_maker_token(maker)
 if re.search('쌍용|ssang',str(maker),re.I):mk='ssangyong'
 if re.search(r'kg\s*모빌리티|kg\s*mobility',str(maker),re.I):mk='kgm'
 if re.search('르노삼성|renault.?samsung',str(maker),re.I):mk='renaultsamsung'
 if re.search('르노코리아|renault.?korea',str(maker),re.I):mk='renaultkorea'
 mk=_AV_GLOBAL_LEGAL_BRANDS.get(mk,mk)
 # JLR corporate-name logic remains in force; the auto brands do not merge.
 if _av_is_jlr_legal(maker):return _av_brand_for_record(maker,raw,ko)
 if mk in ('ssangyong','kgm'):
  return 'kgm' if year is not None and int(year)>=2023 else 'ssangyong'
 if mk=='renault' and re.search(r'(?i)(?:^|\W)(?:sm[3567]|qm[356]|xm3)(?:\W|$)',str(raw or '')+' '+str(ko or '')):
  mk='renaultsamsung'
 if mk=='samsungmotors' and year is not None and int(year)<2000:return 'samsungmotors'
 if mk in ('renaultsamsung','renaultkorea','samsungmotors'):
  return 'renaultkorea' if year is not None and int(year)>=2022 else 'renaultsamsung'
 return mk

# Manufacturer legal-name variations should not become part of model identity.
# Only strip a recognized prefix when it is a separate word, never substrings
# within a real model name (e.g. MINI Clubman or Range Rover).
_AV_GLOBAL_MODEL_PREFIXES={
 'kgm':['KG Mobility','KG모빌리티','KGM','SsangYong','Ssang Yong','쌍용'],
 'ssangyong':['KG Mobility','KG모빌리티','KGM','SsangYong','Ssang Yong','쌍용'],
 'renaultsamsung':['Renault Samsung Motors','Renault Samsung','르노삼성자동차','르노삼성','Samsung Motors','삼성자동차','Renault'],
 'renaultkorea':['Renault Korea Motors','Renault Korea','르노코리아자동차','르노코리아','Renault Samsung','르노삼성','Renault'],
 'samsungmotors':['Samsung Motors','Samsung','삼성자동차'],
 'bmw':['BMW'], 'mercedesbenz':['Mercedes-Benz','Mercedes Benz','메르세데스 벤츠','메르세데스-벤츠','벤츠'],
 'volkswagen':['Volkswagen','VW','폭스바겐'],
 'toyota':['Toyota','토요타','도요타'], 'honda':['Honda','혼다'],
 'mazda':['Mazda','마쓰다','마즈다','마쯔다'],
 'nissan':['Nissan','닛산'], 'subaru':['Subaru','스바루'],
 'peugeot':['Peugeot','푸조'], 'ford':['Ford','포드'],
 'audi':['Audi','아우디'], 'opel':['Opel','오펠'],
 'skoda':['Škoda','Skoda','스코다'], 'seat':['SEAT'],
 'mini':['MINI'], 'kia':['Kia Motors','Kia','기아'],
 'hyundai':['Hyundai Motors','Hyundai Motor','Hyundai','현대'],
 'renault':['Renault','르노'],
}
def _av_global_strip_maker(text,brand):
 s=str(text or '').strip()
 for pre in sorted(_AV_GLOBAL_MODEL_PREFIXES.get(brand,()),key=len,reverse=True):
  pattern=r'(?i)^'+re.escape(pre)+r'(?=[\s:·/\-])[\s:·/\-]+'
  new=re.sub(pattern,'',s,count=1).strip()
  if new!=s:return new
 return s

_AV_GLOBAL_OLD_ROOT=_av_root
@functools.lru_cache(maxsize=262144)
def _av_global_root(maker,raw,ko,year=None):
 brand=_av_canonical_brand_year(maker,raw,ko,year)
 # Use source maker for prefix cleanup, not presentation maker that may be renamed.
 clean_raw=_av_global_strip_maker(raw,brand)
 clean_ko=_av_global_strip_maker(ko,brand)
 before=_AV_GLOBAL_OLD_ROOT(maker,clean_raw,clean_ko)
 names=(before,_av_scrub(clean_raw,maker),_av_scrub(clean_ko,maker))
 # Marketing aliases are exact matching; no approximate string edit distances.
 alias=_AV_MARKET_ALIASES.get(brand,{})
 for name in names:
  key=re.sub(r'[^a-z0-9가-힣]','',str(name or '').casefold())
  if key in alias:return alias[key]
 if brand in ('ssangyong','kgm'):
  for name in names:
   key=re.sub(r'[^a-z0-9가-힣]','',str(name or '').casefold())
   if key in ('tivoli','티볼리'):return 'tivoli'
   if key in ('musso','무쏘','mussosports','무쏘스포츠'):return 'musso'
   if key in ('korandoturismo','코란도투리스모','turismo','stavic','스타빅'):
    return 'korandoturismo'
   if key in ('rodius','로디우스'):
    return 'korandoturismo' if year is not None and int(year)>2013 else 'rodius'
  # Preserve ACTYON SPORTS distinct from ACTYON and KORANDO distinct from TURISMO.
 if brand in ('mercedesbenz','mercedes'):
  key=re.sub(r'[^a-z0-9]','',str(before).casefold())
  m=re.fullmatch(r'(cla|cls|gla|glb|glc|gle|gls|eqe|eqs|a|b|c|e|s|g)(?:\d{2,3})(?:d|e|i|cdi|cgi|amg|4matic)?',key)
  if m:
   family=m.group(1)
   return family+'class' if family in ('a','b','c','e','s','g') else family
  if key in ('aclass','bclass','cclass','eclass','sclass','gclass'):
   return key
 if brand=='bmw':
  key=re.sub(r'[^a-z0-9]','',str(before).casefold())
  m=re.fullmatch(r'm?([1-8])(?:[0-9]{2})(?:i|d|e|x|xi|xd|is|isx)?',key)
  if m:return m.group(1)+'series'
  if re.fullmatch('[1-8]series',key):return key
 return before

# Every entry uses the same precomputed global key, including the country map,
# manufacturer dropdown, nameplate list and linked specification aggregation.
@functools.lru_cache(maxsize=1)
def _av_index_path_v4():
 source=database_path();stat=source.stat()
 salt='av-v8-world-all-brands-temporal-families-20261109'
 fingerprint=hashlib.sha256((str(source.resolve())+':'+str(stat.st_size)+':'+str(stat.st_mtime_ns)+':'+salt).encode()).hexdigest()[:24]
 target=Path(tempfile.gettempdir())/('autoverse_display_index_'+fingerprint+'.sqlite')
 if target.is_file():
  try:
   with sqlite3.connect(target.as_uri()+'?mode=ro&immutable=1',uri=True) as c:
    if c.execute('SELECT fingerprint FROM av_meta').fetchone()==(fingerprint,):return target
  except (sqlite3.Error,OSError):pass
 with tempfile.TemporaryDirectory(prefix='autoverse_global_index_') as d:
  output=Path(d)/'display.sqlite'
  with sqlite3.connect(output) as dest,_av_prev_connection() as original:
   dest.execute('PRAGMA synchronous=OFF');dest.execute('PRAGMA journal_mode=OFF')
   dest.execute('CREATE TABLE vehicle_keys(vehicle_id TEXT PRIMARY KEY,root TEXT NOT NULL,gen TEXT,face TEXT,origin TEXT NOT NULL,brand TEXT NOT NULL)')
   cursor=original.execute('SELECT v.vehicle_id,v.year,m.maker_key,n.raw_name,n.name_ko,m.origin_code'+_av_base)
   def identities():
    for vid,year,maker,raw,ko,origin in cursor:
     brand=_av_canonical_brand_year(maker,raw,ko,year)
     # Preserve vehicle IDs and original data even when displayed manufacturer changes.
     country=_AV_KNOWN_BRANDS.get(brand) or _av_maker_origin(maker,origin)
     yield vid,_av_global_root(maker,raw,ko,year),_av_gen(raw,ko),_av_facelift(raw,ko),country,brand
   dest.executemany('INSERT INTO vehicle_keys VALUES(?,?,?,?,?,?)',identities())
   dest.execute('CREATE INDEX ix_av_root_year ON vehicle_keys(root,origin)')
   dest.execute('CREATE INDEX ix_av_brand_root ON vehicle_keys(brand,root)')
   dest.execute('CREATE TABLE av_meta(fingerprint TEXT NOT NULL)')
   dest.execute('INSERT INTO av_meta VALUES(?)',(fingerprint,));dest.commit()
  os.replace(output,target)
 return target

# Year-dependent Korean display names. Do not label 2004 Cerato as K3 or
# translate unknown international models into fabricated Korean spellings.
_AV_OLD_LOCAL_LABEL=_av_local_model_label
def _av_global_model_label(maker,raw,ko,year):
 brand=_AV_GLOBAL_LEGAL_BRANDS.get(_av_maker_token(maker),_av_maker_token(maker))
 key=_av_global_root(brand,raw,ko,year)
 if brand in ('ssangyong','kgm'):
  label={'tivoli':'티볼리','musso':'무쏘','rodius':'로디우스',
         'korandoturismo':'코란도 투리스모','korando':'코란도',
         'torres':'토레스','rexton':'렉스턴'}.get(key)
  if label:return label
 if brand in ('renaultsamsung','renaultkorea'):
  if key in ('sm3','sm5','sm6','sm7','qm3','qm5','qm6','xm3'):
   return key.upper()
 if brand=='bmw' and re.fullmatch('[1-8]series',key):return key[0]+'시리즈'
 if brand=='mercedesbenz' and key in ('aclass','bclass','cclass','eclass','sclass','gclass'):
  return key[0].upper()+'-클래스'
 known={
  ('toyota','yaris'):'야리스',('honda','fit'):'피트',
  ('mazda','mazda2'):'Mazda2',('mazda','mazda3'):'Mazda3',('mazda','mazda6'):'Mazda6',
  ('nissan','qashqai'):'캐시카이',('subaru','crosstrek'):'크로스트렉',
  ('volkswagen','golf'):'골프',('peugeot','208'):'208',('peugeot','2008'):'2008',
  ('peugeot','308'):'308',('opel','corsa'):'코르사',
  ('skoda','octavia'):'Octavia',('seat','leon'):'Leon',('mini','cooper'):'Cooper'
 }
 if (brand,key) in known:return known[(brand,key)]
 return _AV_OLD_LOCAL_LABEL(brand,raw,ko,year)

_AV_SEARCH_V7=search
@functools.lru_cache(maxsize=512)
def search(query='',year=None,countries=None,maker=None,strict_model=False,unknown_year=False,page=1,page_size=18):
 result=_AV_SEARCH_V7(query,year,countries,maker,strict_model,unknown_year,page,page_size)
 for row in result['rows']:
  brand=row['maker_key']
  row['maker_ko']=_av_maker_name(brand,row['maker_ko'])
  if brand=='renaultkorea' and row.get('year') in (2022,2023):row['maker_ko']='르노코리아자동차'
  row['model_ko']=_av_global_model_label(brand,row.get('raw_model'),row.get('model_ko'),row.get('year'))
 return result

_AV_VEHICLE_V7=vehicle
def vehicle(vehicle_id):
 row=_AV_VEHICLE_V7(vehicle_id)
 if row:
  with connection() as con:
   r=con.execute('SELECT n.raw_name FROM vehicles v JOIN models n ON v.model_id=n.model_id WHERE v.vehicle_id=?',(vehicle_id,)).fetchone()
  row['model_ko']=_av_global_model_label(row['maker_key'],r['raw_name'] if r else '',row.get('model_ko'),row.get('year'))
  row['maker_ko']=_av_maker_name(row['maker_key'],row.get('maker_ko'))
  if row['maker_key']=='renaultkorea' and row.get('year') in (2022,2023):row['maker_ko']='르노코리아자동차'
 return row

# The main screen uses the integrated manufacturer key (k.brand), not the
# incoming manufacturer's old legal entity name.
@functools.lru_cache(maxsize=256)
def maker_options(query='',year=None,countries=None,strict_model=False,unknown_year=False):
 countries=tuple(countries) if countries is not None else None
 where,values=conditions(query,year,countries,None,strict_model,unknown_year)
 with connection() as con:
  rows=con.execute('SELECT k.brand AS maker_key,MIN(m.name_ko) AS maker_display '+BASE+where+
                   ' GROUP BY k.brand ORDER BY maker_display',values).fetchall()
 return [{'maker_key':r['maker_key'],
          'name_ko':('르노코리아자동차' if r['maker_key']=='renaultkorea' and year in (2022,2023)
                     else maker_display_label(r['maker_key'],r['maker_display'],year))} for r in rows]

# Search for any established foreign/domestic name also locates the entire
# canonical model family. Matching aliases are an addition, not a replacement.
_AV_CONDITIONS_V7=conditions
def conditions(query='',year=None,countries=None,maker=None,strict_model=False,unknown_year=False):
 where,values=_AV_CONDITIONS_V7(query,year,countries,maker,strict_model,unknown_year)
 normalized=normalize(query)
 for brand,aliases in _AV_MARKET_ALIASES.items():
  if normalized in aliases:
   expr="(n.search_text LIKE ? ESCAPE '\\' OR n.initials LIKE ? ESCAPE '\\' OR m.search_text LIKE ? ESCAPE '\\')"
   if expr in where:
    where=where.replace(expr,'('+expr+' OR (k.brand=? AND k.root=?))')
    values.extend((brand,aliases[normalized]))
   break
 # Observed old model names (overseas variants) are preserved in source but
 # cannot appear as separate late-year display entries if explicitly ended.
 where+=(' AND ' if where else ' WHERE ')+"NOT (k.brand IN ('ssangyong','kgm') AND v.year>2013 AND k.root='rodius')"
 return where,values

# A territory code can contain multiple source aliases. Standardize the
# mainland UK label for the whole 1801+ interval, not just 2024/2025.
_AV_WORLD_MAP_BEFORE_V8=map_for_year
@functools.lru_cache(maxsize=16)
def map_for_year(year):
 import copy
 data=copy.deepcopy(_AV_WORLD_MAP_BEFORE_V8(year))
 if int(year)>=1801:
  uk_names={'그레이트브리튼 왕국','그레이트 브리튼 왕국','그레이트브리튼','연합왕국',
            'Kingdom of Great Britain','Great Britain',
            'United Kingdom','United Kingdom of Great Britain and Northern Ireland'}
  for feature in data.get('features',[]):
   p=feature.get('properties') or {}
   if 'GB' in p.get('country_codes',[]) and (
      str(p.get('name_ko') or '').strip() in uk_names or
      str(p.get('name') or p.get('name_en') or '').strip() in uk_names):
    p['name_ko']='영국'
 return data

# V9: stable, catalog-wide vehicle identities for every brand and every view.
# All original vehicle_id rows, model data, and source files are read-only.
# The deduplication group is materialized ONCE (per source catalog hash), not
# recomputed from the subset currently matching a search query.
_AV_V9_IDENTITY_VERSION = 'v9-stable-year-brand-model-generation-facelift-p2-20261109'

def _av_contextual_generation(maker,raw,ko):
    if _av_maker_token(maker)=='hyundai':
        chassis = re.search(r'(?<![a-z0-9])(?:mx5|sx2)(?![a-z0-9])',_av_nfkc(raw)+' '+_av_nfkc(ko))
        if chassis:
            return chassis.group()
    generation = _av_gen(raw,ko)
    ordinal = re.fullmatch(r'(?:gen(?:eration)?([1-9])|([1-9])세대|mk([1-9]))',generation)
    if ordinal:
        generation='gen'+next(value for value in ordinal.groups() if value)
    brand=_av_maker_token(maker)
    equivalents={
        ('kia','niro','gen1'):'de', ('kia','niro','gen2'):'sg2',
        ('hyundai','elantra','gen7'):'cn7', ('hyundai','grandeur','gen7'):'gn7',
    }
    if (brand,generation) in {('kia','gen1'),('kia','gen2'),('hyundai','gen7')}:
        root=_av_global_root(brand,raw,ko)
        generation=equivalents.get((brand,root,generation),generation)
    brand = _av_maker_token(maker)
    # 'SL', 'QL', 'DE' and similar tokens are platform codes for some
    # Hyundai/Kia vehicles, but denote layouts/trims for other manufacturers.
    # E.g. Adria Coral XL 670 SL must NOT be a different generation from 650 DK.
    korean_platforms = {'sl','ql','de','ad','md','lf','yf','tf','jf','ja',
                        'sk3','sp2','sp3','nm','ka4','mq4','cn7','nx4','nx5',
                        'nq5','dl3','gl3','dn8','bn7','gn7','sg2'}
    if generation in korean_platforms and brand not in {'kia','kiamotors','hyundai',
                'hyundaimotor','genesis','ssangyong','kgm','kgmobility'}:
        return ''
    return generation


# V11: synthetic source identifiers such as Raw748750097bdb42d9 are not car makers.
# Recognize only hashed Raw-prefixed IDs, never the legitimate marque named RAW.
_AV_RAW_MAKER_RE = re.compile(r'(?i)^raw[\s_-]?(?=[a-z0-9]*[0-9])[a-z0-9]{10,}$')

def _av_is_raw_maker_id(value):
    s = unicodedata.normalize('NFKC', str(value or '')).strip()
    return bool(_AV_RAW_MAKER_RE.fullmatch(s))

_AV_V11_BRAND_WORDS = {
    'hyundai':('hyundai','hyundai motor','현대자동차','현대'),
    'kia':('kia motors','kia','기아자동차','기아'),
    'genesis':('genesis','제네시스'),
    'kgm':('kg mobility','kgm','kg모빌리티'),
    'ssangyong':('ssangyong','쌍용자동차','쌍용'),
    'toyota':('toyota','토요타','도요타'),
    'lexus':('lexus','렉서스'),
    'honda':('honda','혼다'),
    'nissan':('nissan','닛산'),
    'mazda':('mazda','마쓰다','마즈다'),
    'subaru':('subaru','스바루'),
    'mitsubishi':('mitsubishi','미쓰비시'),
    'suzuki':('suzuki','스즈키'),
    'bmw':('bmw',),
    'mercedesbenz':('mercedes-benz','mercedes benz','벤츠','메르세데스벤츠'),
    'audi':('audi','아우디'),
    'volkswagen':('volkswagen','폭스바겐'),
    'porsche':('porsche','포르쉐'),
    'ford':('ford','포드'),
    'chevrolet':('chevrolet','쉐보레'),
    'cadillac':('cadillac','캐딜락'),
    'jeep':('jeep','지프'),
    'tesla':('tesla','테슬라'),
    'renault':('renault','르노'),
    'peugeot':('peugeot','푸조'),
    'citroen':('citroen','citroën','시트로엥'),
    'volvo':('volvo','볼보'),
    'jaguar':('jaguar','재규어'),
    'landrover':('land rover','랜드로버'),
    'mini':('mini','미니'),
    'fiat':('fiat','피아트'),
    'alfa':('alfa romeo','알파로메오'),
    'ferrari':('ferrari','페라리'),
    'lamborghini':('lamborghini','람보르기니'),
    'byd':('byd','비야디'),
}

def _av_v11_identify_brand(display_name, raw_model, model_ko):
    """Assign a Raw-ID only from an explicit manufacturer label/prefix.

    A matching standalone model name is NOT sufficient identification: many
    manufacturers use identical or near-identical model names.
    """
    display = unicodedata.normalize('NFKC',str(display_name or '')).strip().casefold()
    if display and not _av_is_raw_maker_id(display):
        normal = re.sub(r'[\s._-]+',' ',display).strip()
        for brand,names in _AV_V11_BRAND_WORDS.items():
            if normal in names:return brand
    for label in (raw_model,model_ko):
        text = unicodedata.normalize('NFKC',str(label or '')).strip().casefold()
        for brand,names in _AV_V11_BRAND_WORDS.items():
            for name in sorted(names,key=len,reverse=True):
                if text.startswith(name) and len(text)>len(name) and text[len(name)] in ' \t-:./':
                    if len(re.sub(r'\W+','',text[len(name):]))>=2:
                        return brand
    return None

# Keep incomplete source observations searchable without showing a fabricated
# manufacturer. Their raw identifiers are retained in the separate index's
# root field so two unrelated unknown makers are never merged together.
_AV_V11_UNRESOLVED_MAKER = 'unidentified'
_AV_V9_IDENTITY_VERSION = 'v11-raw-id-make-recovery-unknown-isolation-20261109'

@functools.lru_cache(maxsize=1)
def _av_index_path_v4():
    source = database_path()
    stat = source.stat()
    fingerprint = hashlib.sha256(
        f'{source.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{_AV_V9_IDENTITY_VERSION}'.encode()
    ).hexdigest()[:24]
    target = Path(tempfile.gettempdir()) / f'autoverse_display_index_{fingerprint}.sqlite'
    if target.is_file():
        try:
            with sqlite3.connect(target.as_uri() + '?mode=ro&immutable=1', uri=True) as con:
                correct = con.execute('SELECT fingerprint FROM av_meta').fetchone() == (fingerprint,)
                columns = {r[1] for r in con.execute('PRAGMA table_info(vehicle_keys)')}
                if correct and 'group_id' in columns:
                    return target
        except (sqlite3.Error, OSError):
            pass

    with tempfile.TemporaryDirectory(prefix='autoverse_stable_id_build_') as temporary:
        output = Path(temporary) / 'vehicle_index.sqlite'
        with sqlite3.connect(output) as dest, _av_prev_connection() as original:
            dest.execute('PRAGMA synchronous=OFF')
            dest.execute('PRAGMA journal_mode=OFF')
            dest.execute('CREATE TABLE vehicle_keys ('
                         'vehicle_id TEXT PRIMARY KEY, root TEXT NOT NULL, gen TEXT NOT NULL, '
                         'face TEXT NOT NULL, origin TEXT NOT NULL, brand TEXT NOT NULL, '
                         'year INTEGER, group_id TEXT)')
            cursor = original.execute(
                'SELECT v.vehicle_id,v.year,m.maker_key,n.raw_name,n.name_ko,m.origin_code,m.name_ko' + _av_base
            )
            def identities():
                for vehicle_id, year, maker, raw, ko, previous_origin, maker_display in cursor:
                    fake = _av_is_raw_maker_id(maker) or _av_is_raw_maker_id(maker_display)
                    verified = _av_v11_identify_brand(maker_display,raw,ko) if fake else None
                    if fake and not verified:
                        brand = _AV_V11_UNRESOLVED_MAKER
                        origin = 'UNKNOWN'
                        # Preserve distinct unknown source identifiers, rather
                        # than collapsing every unknown source into one model.
                        source_key = re.sub(r'[^a-z0-9]','',str(maker).casefold())
                        root = 'rawsource:' + source_key + ':' + (_av_global_root(maker,raw,ko,year) or str(vehicle_id))
                    else:
                        brand = verified or _av_canonical_brand_year(maker, raw, ko, year)
                        origin = _AV_KNOWN_BRANDS.get(brand) or _av_maker_origin(maker, previous_origin)
                        root = _av_global_root(brand if verified else maker, raw, ko, year)
                        if not root:
                            root = 'unidentified:' + str(vehicle_id)
                    yield (vehicle_id, root, _av_contextual_generation(brand, raw, ko), _av_facelift(raw, ko),
                           origin, brand, year, None)
            dest.executemany('INSERT INTO vehicle_keys VALUES (?,?,?,?,?,?,?,?)', identities())
            dest.execute('CREATE INDEX ix_vehicle_signal ON vehicle_keys(brand,root,year)')
            dest.execute('CREATE TEMP TABLE signals AS '
                         'SELECT brand,root,year,COUNT(DISTINCT gen) gen_variants,'
                         'COUNT(DISTINCT face) face_variants '
                         'FROM vehicle_keys WHERE year IS NOT NULL GROUP BY brand,root,year')
            dest.execute('CREATE INDEX ix_signals ON signals(brand,root,year)')
            scan = dest.execute('SELECT k.vehicle_id,k.brand,k.root,k.year,k.gen,k.face,'
                                'COALESCE(s.gen_variants,1),COALESCE(s.face_variants,1) '
                                'FROM vehicle_keys k LEFT JOIN signals s '
                                'ON s.brand=k.brand AND s.root=k.root AND s.year=k.year')
            while True:
                batch = scan.fetchmany(4096)
                if not batch:
                    break
                updates = []
                for vid,brand,root,year,gen,face,gen_variants,face_variants in batch:
                    if year is None:
                        # Unknown year may mix different generations; preserve it as unknown.
                        group_id = json.dumps(['unverified-year',vid],ensure_ascii=False,separators=(',',':'))
                    else:
                        # Only distinguish a version attribute if multiple values actually
                        # coexist in this model year. An explicit FL vs no FL is DISTINCT.
                        group_id = json.dumps([
                            brand,root,int(year),
                            gen if gen_variants > 1 else '',
                            face if face_variants > 1 else '',
                        ],ensure_ascii=False,separators=(',',':'))
                    updates.append((group_id,vid))
                dest.executemany('UPDATE vehicle_keys SET group_id=? WHERE vehicle_id=?',updates)
            scan.close()
            dest.execute('DROP TABLE signals')
            dest.execute('CREATE INDEX ix_vehicle_group ON vehicle_keys(group_id)')
            dest.execute('CREATE INDEX ix_vehicle_brand_origin ON vehicle_keys(brand,origin,year)')
            dest.execute('CREATE TABLE av_meta(fingerprint TEXT NOT NULL)')
            dest.execute('INSERT INTO av_meta VALUES (?)',(fingerprint,))
            dest.commit()
        # Atomic rename ensures incomplete builds never become the active index.
        os.replace(output,target)
    return target


def _av_cte(where):
    """One identity per displayed model, independent of matching search terms.

    Using the same group_id in search, country counts, and detail aggregation
    avoids the previous subset-dependent generation/facelift grouping.
    """
    return (
        'WITH filtered AS (SELECT ' + _AV_FIELDS +
        ',k.group_id AS av_group ' + BASE + where + '),'
        'ranked AS (SELECT filtered.*,'
        'ROW_NUMBER() OVER (PARTITION BY av_group '
        "ORDER BY year IS NULL,CASE WHEN year_kind='model' THEN 0 ELSE 1 END,"
        "CASE WHEN source_kind='master' THEN 0 ELSE 1 END,"
        'year DESC,LENGTH(model_ko),vehicle_id) AS rn,'
        'COUNT(*) OVER (PARTITION BY av_group) AS linked_record_count,'
        "COALESCE(NULLIF(av_gen,''),'unverified') AS kept_gen,"
        "COALESCE(NULLIF(av_face,''),'unverified') AS kept_face "
        'FROM filtered) '
    )


@functools.lru_cache(maxsize=1024)
def _av_group_members(vehicle_id):
    """Details use exactly the same ID as search, never a second heuristic."""
    with connection() as con:
        row = con.execute('SELECT group_id FROM av_idx.vehicle_keys WHERE vehicle_id=?',
                          (vehicle_id,)).fetchone()
        if not row:
            return ()
        members = con.execute(
            'SELECT v.vehicle_id,n.raw_name,n.name_ko FROM av_idx.vehicle_keys k '
            'JOIN vehicles v ON v.vehicle_id=k.vehicle_id '
            'JOIN models n ON n.model_id=v.model_id '
            'WHERE k.group_id=? ORDER BY v.vehicle_id', (row['group_id'],)
        ).fetchall()
        return tuple((r['vehicle_id'],r['raw_name'],r['name_ko']) for r in members)


# Stable representative: an arbitrary spelling is not allowed to become a new
# display entity. Every result still retains all source model names via its ID.
# Keep the existing local year-dependent display names and search aliases.

# V10 — manufacturer-scoped Korean / English model identity reconciliation.
# Display names never define vehicle identity. This layer enriches V9's stable
# group key, without editing vehicle_id, source records or linked specifications.
# No approximate/fuzzy matching: a near-spelling is not evidence of same model.
_AV_V9_IDENTITY_VERSION = 'v10-global-bilingual-source-bridges-20261109'

# Fields: brand | canonical root | Korean name | other approved Korean/English aliases.
# The catalog is intentionally brand-scoped: e.g. Jazz, Soul and Crown cannot
# collapse into another manufacturer's model by sharing a generic word.
_AV_V10_MODEL_DATA = r'''
toyota|camry|캠리
toyota|corolla|코롤라
toyota|corollacross|코롤라 크로스
toyota|rav4|라브4|라브 4|알에이브이4
toyota|prius|프리우스
toyota|yaris|야리스|비츠|Vitz
toyota|yariscross|야리스 크로스
toyota|highlander|하이랜더
toyota|landcruiser|랜드크루저|랜드 크루저
toyota|supra|수프라
toyota|crown|크라운
toyota|tacoma|타코마
toyota|tundra|툰드라
toyota|4runner|포러너|4러너
toyota|sienna|시에나
toyota|alphard|알파드
toyota|vellfire|벨파이어
toyota|hilux|하이럭스
toyota|ch-r|씨에이치알|C-HR
toyota|mirai|미라이
toyota|bz4x|비지포엑스|bZ4X
toyota|gr86|지알86|GR86
toyota|86|토요타86
toyota|century|센추리
toyota|avensis|아벤시스
toyota|aqua|아쿠아
toyota|aygo|아이고
honda|accord|어코드
honda|civic|시빅
honda|civictyper|시빅 타입 R|Civic Type R
honda|crv|씨알브이|CR-V
honda|hrv|에이치알브이|HR-V
honda|zrv|지알브이|ZR-V
honda|fit|피트|재즈|Jazz
honda|city|시티
honda|pilot|파일럿
honda|odyssey|오딧세이|오디세이
honda|insight|인사이트
honda|passport|패스포트
honda|ridgeline|릿지라인
honda|prelude|프렐류드
honda|legend|레전드
honda|nsx|엔에스엑스|NSX
honda|s2000|에스2000
honda|freed|프리드
honda|stepwgn|스텝왜건|스텝 와곤|Step WGN
nissan|altima|알티마
nissan|maxima|맥시마
nissan|sentra|센트라
nissan|versa|버사
nissan|leaf|리프
nissan|ariya|아리야
nissan|rogue|로그
nissan|qashqai|캐시카이|듀얼리스|Dualis
nissan|juke|쥬크|주크
nissan|xtrail|엑스트레일|X-Trail
nissan|murano|무라노
nissan|pathfinder|패스파인더
nissan|patrol|패트롤
nissan|navara|나바라
nissan|skyline|스카이라인
nissan|gtr|지티알|GT-R
nissan|z|페어레이디 Z|페어레이디z
mazda|mazda2|마쓰다2|마즈다2|데미오|Demio
mazda|mazda3|마쓰다3|마즈다3|악셀라|Axela
mazda|mazda6|마쓰다6|마즈다6|아텐자|Atenza
mazda|cx3|씨엑스3|CX-3
mazda|cx5|씨엑스5|CX-5
mazda|cx30|씨엑스30|CX-30
mazda|cx50|씨엑스50|CX-50
mazda|cx60|씨엑스60|CX-60
mazda|cx90|씨엑스90|CX-90
mazda|mx5|엠엑스5|MX-5|로드스터|Roadster
subaru|impreza|임프레자
subaru|legacy|레거시
subaru|outback|아웃백
subaru|forester|포레스터
subaru|crosstrek|크로스트렉|XV|엑스브이
subaru|brz|비알지|BRZ
subaru|wrx|더블유알엑스|WRX
subaru|solterra|솔테라
mitsubishi|outlander|아웃랜더
mitsubishi|eclipsecross|이클립스 크로스
mitsubishi|lancer|랜서
mitsubishi|pajero|파제로
mitsubishi|triton|트라이톤
suzuki|swift|스위프트
suzuki|jimny|짐니
suzuki|vitara|비타라
suzuki|ignis|이그니스
lexus|es|이에스|ES
lexus|is|아이에스|IS
lexus|ls|엘에스|LS
lexus|rx|알엑스|RX
lexus|nx|엔엑스|NX
lexus|ux|유엑스|UX
lexus|gx|지엑스|GX
lexus|lx|엘엑스|LX
lexus|rc|알씨|RC
lexus|lc|엘씨|LC
bmw|x1|엑스1|엑스원|X1
bmw|x2|엑스2|엑스투|X2
bmw|x3|엑스3|엑스쓰리|X3
bmw|x4|엑스4|엑스포|X4
bmw|x5|엑스5|엑스파이브|X5
bmw|x6|엑스6|엑스식스|X6
bmw|x7|엑스7|엑스세븐|X7
bmw|3series|3시리즈|삼시리즈|3 Series|3-Series
bmw|5series|5시리즈|오시리즈|5 Series|5-Series
bmw|7series|7시리즈|칠시리즈|7 Series|7-Series
bmw|1series|1시리즈|1 Series
bmw|2series|2시리즈|2 Series
bmw|4series|4시리즈|4 Series
bmw|6series|6시리즈|6 Series
bmw|8series|8시리즈|8 Series
bmw|i3|아이3|i3
bmw|i4|아이4|i4
bmw|i5|아이5|i5
bmw|i7|아이7|i7
bmw|ix|아이엑스|iX
bmw|ix1|아이엑스1|iX1
mercedesbenz|aclass|A클래스|A-Class|에이클래스
mercedesbenz|bclass|B클래스|B-Class|비클래스
mercedesbenz|cclass|C클래스|C-Class|씨클래스
mercedesbenz|eclass|E클래스|E-Class|이클래스
mercedesbenz|sclass|S클래스|S-Class|에스클래스
mercedesbenz|gclass|G클래스|G-Class|지클래스
mercedesbenz|cla|씨엘에이|CLA
mercedesbenz|cls|씨엘에스|CLS
mercedesbenz|gla|지엘에이|GLA
mercedesbenz|glb|지엘비|GLB
mercedesbenz|glc|지엘씨|GLC
mercedesbenz|gle|지엘이|GLE
mercedesbenz|gls|지엘에스|GLS
mercedesbenz|eqe|이큐이|EQE
mercedesbenz|eqs|이큐에스|EQS
mercedesbenz|eqa|이큐에이|EQA
mercedesbenz|eqb|이큐비|EQB
mercedesbenz|vclass|V클래스|V-Class
volkswagen|golf|골프
volkswagen|polo|폴로
volkswagen|passat|파사트
volkswagen|tiguan|티구안
volkswagen|touareg|투아렉
volkswagen|jetta|제타
volkswagen|arteon|아테온
volkswagen|touran|투란
volkswagen|beetle|비틀
volkswagen|troc|티록|T-Roc
volkswagen|tcross|티크로스|T-Cross
volkswagen|id3|아이디3|ID.3
volkswagen|id4|아이디4|ID.4
volkswagen|id5|아이디5|ID.5
volkswagen|id7|아이디7|ID.7
audi|a3|에이3|A3
audi|a4|에이4|A4
audi|a5|에이5|A5
audi|a6|에이6|A6
audi|a7|에이7|A7
audi|a8|에이8|A8
audi|q2|큐2|Q2
audi|q3|큐3|Q3
audi|q4|큐4|Q4
audi|q5|큐5|Q5
audi|q6|큐6|Q6
audi|q7|큐7|Q7
audi|q8|큐8|Q8
audi|tt|티티|TT
audi|r8|알8|R8
porsche|911|구일일|911
porsche|boxster|박스터
porsche|cayman|카이맨
porsche|cayenne|카이엔
porsche|macan|마칸
porsche|panamera|파나메라
porsche|taycan|타이칸
volvo|xc40|엑스씨40|XC40
volvo|xc60|엑스씨60|XC60
volvo|xc90|엑스씨90|XC90
volvo|s60|에스60|S60
volvo|s90|에스90|S90
volvo|v60|브이60|V60
volvo|v90|브이90|V90
ford|mustang|머스탱
ford|mustangmache|머스탱 마하-E|Mustang Mach-E
ford|explorer|익스플로러
ford|expedition|익스페디션
ford|bronco|브롱코
ford|broncosport|브롱코 스포츠|Bronco Sport
ford|escape|이스케이프
ford|focus|포커스
ford|fiesta|피에스타
ford|fusion|퓨전
ford|taurus|토러스
ford|ranger|레인저
ford|maverick|매버릭
ford|f150|에프150|F-150
ford|edge|엣지
ford|mondeo|몬데오
chevrolet|spark|스파크
chevrolet|malibu|말리부
chevrolet|cruze|크루즈
chevrolet|trax|트랙스
chevrolet|trailblazer|트레일블레이저|트레일 블레이저
chevrolet|equinox|이쿼녹스
chevrolet|traverse|트래버스
chevrolet|tahoe|타호
chevrolet|suburban|서버번
chevrolet|silverado|실버라도
chevrolet|camaro|카마로
chevrolet|corvette|콜벳
jeep|wrangler|랭글러
jeep|cherokee|체로키
jeep|grandcherokee|그랜드 체로키
jeep|compass|컴패스
jeep|renegade|레니게이드
jeep|gladiator|글래디에이터
tesla|model3|모델3|Model 3
tesla|modely|모델y|모델와이|Model Y
tesla|models|모델s|모델에스|Model S
tesla|modelx|모델x|모델엑스|Model X
tesla|cybertruck|사이버트럭|사이버 트럭
hyundai|sonata|쏘나타|소나타|소너트
hyundai|elantra|아반떼|엘란트라|Elantra|Avante
hyundai|tucson|투싼
hyundai|santafe|싼타페|Santa Fe
hyundai|grandeur|그랜저|Azera|아제라
hyundai|palisade|팰리세이드
hyundai|kona|코나
hyundai|venue|베뉴|벤우
hyundai|casper|캐스퍼
hyundai|ioniq5|아이오닉5|아이오닉 5|Ioniq 5
hyundai|ioniq6|아이오닉6|아이오닉 6|Ioniq 6
hyundai|ioniq9|아이오닉9|아이오닉 9|Ioniq 9
hyundai|accent|엑센트|액센트
hyundai|verna|베르나|버너
hyundai|stargazer|스타게이저|스타르게이저
hyundai|bayon|바이온|비에이와이오엔
hyundai|creta|크레타|씨아르이티에이
hyundai|exter|엑스터|이엑스티이아르
hyundai|elexio|일렉시오|이엘이엑스아이오
hyundai|santacruz|산타크루즈|샌터 크루즈
hyundai|alcazar|알카자르|알커자
hyundai|aura|아우라|오러
hyundai|inster|인스터|아이엔에스티이아르
kia|picanto|모닝|피칸토|Morning|Picanto
kia|niro|니로|Niro
kia|niroplus|니로 플러스|Niro Plus
kia|seltos|셀토스
kia|sportage|스포티지
kia|sorento|쏘렌토
kia|carnival|카니발|Sedona|세도나
kia|soul|쏘울|솔
kia|stonic|스토닉|에스티오엔아이씨
kia|ceed|씨드|Ceed|Cee'd
kia|xceed|엑씨드|엑스씨이이디|XCeed
kia|telluride|텔루라이드|텔어아이드
kia|cerato|세라토|쎄라토|Forte|포르테|K3
kia|optima|옵티마|로체|K5
kia|quoris|K9|K900|Quoris
kia|cadenza|카덴자|K7
kia|carens|카렌스|Rondo|론도
kia|mohave|모하비|Borrego|보레고
genesis|g70|지70|G70
genesis|g80|지80|G80|Electrified G80
genesis|g90|지90|G90
genesis|gv70|지브이70|GV70|Electrified GV70
genesis|gv80|지브이80|GV80
ssangyong|tivoli|티볼리|Tivoli
ssangyong|korando|코란도|Korando
ssangyong|korandoturismo|코란도 투리스모|Korando Turismo|로디우스|Rodius|Stavic
ssangyong|rexton|렉스턴|Rexton
kgm|tivoli|티볼리|Tivoli
kgm|korando|코란도|Korando
kgm|korandoturismo|코란도 투리스모|Korando Turismo|로디우스|Rodius|Stavic
kgm|rexton|렉스턴|Rexton
kgm|torres|토레스|Torres
kgm|musso|무쏘|Musso
renaultsamsung|sm3|에스엠3|SM3
renaultsamsung|sm5|에스엠5|SM5
renaultsamsung|sm6|에스엠6|SM6
renaultsamsung|sm7|에스엠7|SM7
renaultsamsung|qm3|큐엠3|QM3
renaultsamsung|qm5|큐엠5|QM5
renaultsamsung|qm6|큐엠6|QM6
renaultsamsung|xm3|엑스엠3|XM3
renaultkorea|sm3|에스엠3|SM3
renaultkorea|sm5|에스엠5|SM5
renaultkorea|sm6|에스엠6|SM6
renaultkorea|qm6|큐엠6|QM6
renaultkorea|xm3|엑스엠3|XM3
renault|clio|클리오
renault|captur|캡처|캡쳐
renault|megane|메간|메간느
renault|arkana|아르카나
renault|koleos|콜레오스
renault|scenic|세닉
renault|twingo|트윙고
peugeot|208|이백팔|e-208|e208
peugeot|2008|이천팔|e-2008|e2008
peugeot|308|삼백팔|e-308|e308
peugeot|3008|삼천팔
peugeot|5008|오천팔
citroen|c3|씨3|C3
citroen|c4|씨4|C4
citroen|c5|씨5|C5
citroen|berlingo|베를링고
citroen|c5aircross|C5 에어크로스|C5 Aircross
'''

# Brand canonicalization for legal company names must happen before language
# canonicalization, but do not fuse unrelated acquired brands.
_AV_GLOBAL_LEGAL_BRANDS.update({
    'toyotamotor':'toyota','toyotamotorcorporation':'toyota',
    'hondamotor':'honda','hondamotorcompany':'honda',
    'volkswagenag':'volkswagen','mercedesbenzgroup':'mercedesbenz',
    'fordmotor':'ford','fordmotorcompany':'ford',
    'generalchevrolet':'chevrolet','chevroletmotor':'chevrolet',
    'teslamotors':'tesla','lexusdivision':'lexus',
})

def _av_v10_token(text):
    norm=unicodedata.normalize('NFKD',str(text or '').casefold())
    norm=unicodedata.normalize('NFKC',''.join(c for c in norm if not unicodedata.combining(c)))
    return re.sub(r'[^a-z0-9가-힣]','',norm)

def _av_v10_build_aliases():
    alias={}; labels={}; collisions=[]
    for line in _AV_V10_MODEL_DATA.splitlines():
        if not line.strip() or line.startswith('#'):continue
        brand,root,*forms=[s.strip() for s in line.split('|')]
        labels[(brand,root)]=forms[0] if forms else root
        for form in (root,*forms):
            key=(brand,_av_v10_token(form))
            existing=alias.get(key)
            if existing is not None and existing!=root:
                collisions.append((key,existing,root))
                continue
            alias[key]=root
    if collisions:raise RuntimeError('Ambiguous bilingual model labels: '+repr(collisions[:8]))
    return alias,labels

_AV_V10_ALIASES,_AV_V10_LABELS=_av_v10_build_aliases()
_AV_V10_SOURCE_BRIDGES={}
_AV_V10_OLD_GLOBAL_ROOT=_av_global_root

@functools.lru_cache(maxsize=262144)
def _av_global_root(maker,raw,ko,year=None):
    brand=_av_canonical_brand_year(maker,raw,ko,year)
    original=_AV_V10_OLD_GLOBAL_ROOT(maker,raw,ko,year)
    if brand in ('ssangyong','kgm') and original in ('rodius','korandoturismo'):
        # Keep pre-2013 Rodius distinct from the later Korando Turismo.
        return original
    # Prioritize official/raw model name; translated short labels are only a
    # fallback when the raw name itself is Korean or missing. This protects
    # distinct derivatives (Camry vs hypothetical Camry Cross) if a source
    # incorrectly gives both the same Korean subtitle.
    cleaned_raw=_av_global_strip_maker(raw,brand)
    raw_has_latin=bool(re.search('[a-z]',cleaned_raw,re.I))
    candidates=[original,cleaned_raw]
    if not raw_has_latin:candidates.append(_av_global_strip_maker(ko,brand))
    for value in candidates:
        key=_av_v10_token(_av_scrub(value,brand))
        match=_AV_V10_ALIASES.get((brand,key))
        if match:return match
    # One-to-one paired source translations are used only when the original
    # source is Korean-only. The corresponding English record already has
    # the international source-model spelling as its key.
    for value in candidates:
        key=_av_v10_token(_av_scrub(value,brand))
        match=_AV_V10_SOURCE_BRIDGES.get((brand,key))
        if match:return match
    return original


def _av_v10_source_bridges(original_db):
    # A bilingual pair from one source record is the strongest *available*
    # catalog evidence; avoid generic descriptions and conflicting pairs.
    pairs={}; reverse={}
    cursor=original_db.execute('SELECT DISTINCT m.maker_key,n.raw_name,n.name_ko '
                               'FROM models n JOIN makers m ON m.maker_id=n.maker_id')
    for maker,raw,ko in cursor:
        brand=_av_canonical_brand_year(maker,raw,ko,None)
        r=_av_v10_token(_av_scrub(_av_global_strip_maker(raw,brand),brand))
        k=_av_v10_token(_av_scrub(_av_global_strip_maker(ko,brand),brand))
        if not (re.search('[a-z]',r) and re.search('[가-힣]',k)) or not (2<=len(r)<=35 and 2<=len(k)<=35):continue
        if r==k or k in ('자동차','승용차','승합차','상용차','모델','기타','차량'):continue
        pairs.setdefault((brand,k),set()).add(r)
        reverse.setdefault((brand,r),set()).add(k)
    bridge={}
    # Require both sides to be one-to-one within the brand. Never infer
    # across a partially translated multi-model label.
    for (brand,k),rs in pairs.items():
        if len(rs)!=1:continue
        r=next(iter(rs))
        if len(reverse.get((brand,r),()))!=1:continue
        canonical=_AV_V10_ALIASES.get((brand,r),r)
        if (brand,k) in _AV_V10_ALIASES and _AV_V10_ALIASES[(brand,k)]!=canonical:continue
        if (brand,r) in _AV_V10_ALIASES and _AV_V10_ALIASES[(brand,r)]!=canonical:continue
        bridge[(brand,k)]=canonical
    return bridge

# Source-bridge discovery belongs in the index build, once per catalog revision.
# The V9 stable index groups are reused unchanged by search, map counts and details.
_AV_V10_V9_INDEX_SOURCE=None
_AV_V10_V9_INDEX=_av_index_path_v4
@functools.lru_cache(maxsize=1)
def _av_index_path_v4():
    global _AV_V10_SOURCE_BRIDGES
    if not _AV_V10_SOURCE_BRIDGES:
        with _av_prev_connection() as con:
            _AV_V10_SOURCE_BRIDGES=_av_v10_source_bridges(con)
        _av_global_root.cache_clear()
    return _AV_V10_V9_INDEX()

_AV_V10_OLD_GLOBAL_LABEL=_av_global_model_label
def _av_global_model_label(maker,raw,ko,year):
    brand=_av_canonical_brand_year(maker,raw,ko,year)
    root=_av_global_root(maker,raw,ko,year)
    if brand=='kia' and root in ('cerato','optima'):
        return _AV_V10_OLD_GLOBAL_LABEL(maker,raw,ko,year)
    if brand=='mazda' and root in ('mazda2','mazda3','mazda6'):
        return 'M'+root[1:]
    if brand=='mercedesbenz' and root in ('aclass','bclass','cclass','eclass','sclass','gclass'):
        return root[0].upper()+'-클래스'
    if brand=='peugeot' and root in ('208','2008','308','3008','5008'):
        return root
    if brand in ('ssangyong','kgm') and root=='rodius':
        return '로디우스'
    if brand in ('renaultsamsung','renaultkorea') and root in ('sm3','sm5','sm6','sm7','qm3','qm5','qm6','xm3'):
        return root.upper()
    translated=_av_v10_token(_av_scrub(_av_global_strip_maker(ko,brand),brand))
    if (re.search('[a-z]',str(raw or ''),re.I) and
        (brand,translated) in _AV_V10_ALIASES and
        _AV_V10_ALIASES[(brand,translated)]!=root):
        # A misleading Korean subtitle must not rename a distinct model.
        return _av_display(_av_global_strip_maker(raw,brand),raw,brand)
    if (brand,root) in _AV_V10_LABELS:
        # Preserve the more familiar domestic name where one exists.
        # Overseas-only labels with awkward Korean transliterations are instead
        # displayed as official romanized model names.
        label=_AV_V10_LABELS[(brand,root)]
        if (brand,root) in {('ssangyong','korandoturismo'),('kgm','korandoturismo'),
                            ('chevrolet','trailblazer'),('jeep','grandcherokee')}:
            return label
        if sum('가'<=c<='힣' for c in label)>=6:
            # Honor the user-facing rule: avoid awkward long phonetic spellings.
            long_english={
                ('toyota','yariscross'):'Yaris Cross',
                ('toyota','corollacross'):'Corolla Cross',
                ('ford','broncosport'):'Bronco Sport',
                ('jeep','grandcherokee'):'Grand Cherokee',
                ('honda','civictyper'):'Civic Type R',
                ('hyundai','santacruz'):'SANTA CRUZ',
            }
            if (brand,root) in long_english:return long_english[(brand,root)]
            english=_av_global_strip_maker(raw,brand)
            if english and re.search('[a-z]',english,re.I):
                return _av_display(english,english,brand)
        return label
    return _AV_V10_OLD_GLOBAL_LABEL(maker,raw,ko,year)

# Build the search predicate afresh from the existing non-query filters.
# This avoids parameter-position bugs when several older alias patches have
# already wrapped the LIKE expression with their own placeholders.
_AV_V10_PREV_CONDITIONS=conditions
def conditions(query='',year=None,countries=None,maker=None,strict_model=False,unknown_year=False):
    where,values=_AV_V10_PREV_CONDITIONS('',year,countries,maker,strict_model,unknown_year)
    q=normalize(query)
    if not q:return where,values
    clause="(n.search_text LIKE ? ESCAPE '\\' OR n.initials LIKE ? ESCAPE '\\' OR m.search_text LIKE ? ESCAPE '\\'"
    additions=[]
    brand_constraint=_av_canonical_brand_year(maker,'','',year) if maker else None
    def add(brand,root):
        if brand_constraint is not None and brand_constraint!=brand:return
        pair=(brand,root)
        if pair not in additions:additions.append(pair)
    for (brand,alias),root in _AV_V10_ALIASES.items():
        if alias==q:add(brand,root)
    for (brand,alias),root in _AV_V10_SOURCE_BRIDGES.items():
        if alias==q:add(brand,root)
    for brand,names in _AV_MARKET_ALIASES.items():
        if q in names:add(brand,names[q])
    bad=_AV_KOREAN_BAD_ROMANIZATION.get(q)
    if bad:add(bad[0],_AV_MARKET_ALIASES.get(bad[0],{}).get(bad[1],bad[1]))
    for brand,root in additions:
        clause+=' OR (k.brand=? AND k.root=?)'
    clause+=')'
    values=list(values)+['%'+q+'%']*3+[value for pair in additions for value in pair]
    return where+(' AND ' if where else ' WHERE ')+clause,values

# V11 public labels: no synthetic IDs in car cards, detail or maker chooser.
_AV_V11_PREVIOUS_MAKER_NAME = _av_maker_name
def _av_maker_name(maker,display):
    if (str(maker or '') == _AV_V11_UNRESOLVED_MAKER or
        _av_is_raw_maker_id(maker) or _av_is_raw_maker_id(display)):
        # A confirmed real brand is handled by the known maker-name table.
        name = _AV_MAKER_NAMES.get(_av_maker_token(maker))
        return name or '제조사 미확인'
    return _AV_V11_PREVIOUS_MAKER_NAME(maker,display)

# Search text should not expose a fake maker key as a literal brand name.
# This does not delete or change any original model or source row.


# V12: conservative full-name model family normalization.
# No first-word deduplication. Only anchored, whitelisted *trailing* equipment,
# trim, year-label and marketing text is removed, after marque-prefix removal.
# Keep source vehicle IDs and make/generation/facelift/model-year group boundaries.
_AV_V12_CORE_PREVIOUS = _av_global_root
_AV_V9_IDENTITY_VERSION = 'v12-safe-complete-name-trim-suffix-20261109'

_AV_V12_TRAILING_PATTERNS = (
    # Documentation/model-year suffixes are not a separate nameplate.
    re.compile(r'(?i)(?:[\s,:;/()\[\]-]+|^)(?:MY[\s-]?(?:19|20)?\d{2}|MODEL[\s-]?YEAR[\s-]?(?:19|20)?\d{2})\s*$'),
    # Sales packages: anchored to the end, NOT arbitrary middle words.
    re.compile(r'(?i)(?:[\s,:;/()\[\]-]+|^)(?:X[\s-]?PRO(?:[\s-]+PRESTIGE)?|XRT(?:[\s-]+PRO)?|GT[\s-]?LINE|N[\s-]?LINE|S[\s-]?LINE|R[\s-]?LINE|BLACK[\s-]?EDITION|SX[\s-]?PRESTIGE)\s*$'),
    # Blue / stop-start / ISG variants as used in EPA/market catalogues.
    re.compile(r'(?i)(?:[\s,:;/()\[\]-]+|^)(?:W\s*/\s*STOP[\s/-]?START|WITH[\s-]+STOP[\s/-]?START|STOP[\s/-]?START|NON[\s-]?ISG|ISG|BLUE)\s*$'),
)

# Some terms are defensibly a marketing package only for select brands.
# This prevents accidental shortening of other marques' legitimate base models.
_AV_V12_PACKAGE_BRANDS = {'hyundai','kia','genesis','kgm','ssangyong'}


def _av_v12_clean_base_name(text,brand):
    s=unicodedata.normalize('NFKC',str(text or '')).strip()
    s=_av_global_strip_maker(s,brand)
    # Preserve original Romanization, multi-word model name, and all unknown
    # name suffixes. Only remove a known *entire suffix* (never startswith).
    if brand in _AV_V12_PACKAGE_BRANDS:
        for _ in range(4):
            before=s
            for pattern in _AV_V12_TRAILING_PATTERNS:
                s=pattern.sub('',s).strip(' \t,;:/-()[]')
            if before==s:break
    return s or _av_global_strip_maker(text,brand)


@functools.lru_cache(maxsize=262144)
def _av_global_root(maker,raw,ko,year=None):
    brand=_av_canonical_brand_year(maker,raw,ko,year)
    cleaned_raw=_av_v12_clean_base_name(raw,brand)
    cleaned_ko=_av_v12_clean_base_name(ko,brand)
    # Protect entire distinct multi-token names: Santa Fe != Santa Cruz,
    # Niro != Niro Plus, Yaris != Yaris Cross. Prior resolver accepts full name.
    result=_AV_V12_CORE_PREVIOUS(brand,cleaned_raw,cleaned_ko,year)
    return result


# Invalidate any pre-V12 precomputed index; the V11 index builder reads the
# V12 identity/version string dynamically at execution time.
# V10's bilingual source-pair resolver also observes this override at build.
_AV_V12_CORE_PREVIOUS.cache_clear()

# V13 — Recover synthetic RawXXXX manufacturer keys using independently
# named maker records + unique model evidence from the preserved Phase1 catalog.
# Every original vehicle_id and name is preserved. Never overwrite source DB.
import zlib as _av13_zlib
_AV13_MAKER_SOURCE = (_REFS / 'maker_evidence.zlib').read_bytes()

@functools.lru_cache(maxsize=1)
def _av13_evidence():
    return json.loads(_av13_zlib.decompress(_AV13_MAKER_SOURCE))

def _av13_word(s):
    return re.sub(r'[^a-z0-9가-힣]','',unicodedata.normalize('NFKC',str(s or '')).casefold())

def _av13_find_explicit_prefix(s):
    """A known manufacturer in an explicit first phrase, not any first word.
    E.g. FIAT/NIESMANN+BISCHOFF ARTO → body maker Niesmann+Bischoff.
    Does NOT make 'Santa Fe' equal to 'Santa Cruz'.
    """
    if not s or _av_is_raw_maker_id(s):return None
    evidence=_av13_evidence()['name_keys']
    text=unicodedata.normalize('NFKC',str(s)).strip()
    # Max 4 leading terms. A company name can contain +, / or dashes.
    chunks=text.split()
    prefix_candidates=[]
    for i in range(1,min(5,len(chunks))+1):
        pre=' '.join(chunks[:i]);key=_av13_word(pre)
        if key in evidence:
            prefix_candidates.append((len(key),evidence[key]))
        # A name can contain a slash company/chassis prefix.
        for frag in re.split(r'[/:]',pre):
            key=_av13_word(frag)
            if len(key)>=5 and key in evidence:
                prefix_candidates.append((len(key),evidence[key]))
    if prefix_candidates:
        return max(prefix_candidates,key=lambda x:x[0])[1]
    return None

def _av13_unique_model_brand(s):
    """Manufacturer must be unique for the *full model spelling* across the
    Phase1 branded reference records. No fuzzy/shared-first-token joining.
    """
    key=_av13_word(s)
    if not key:return None
    reference=_av13_evidence()['model_keys']
    return reference.get(key)

_AV13_PREVIOUS_IDENTIFY_BRAND=_av_v11_identify_brand

def _av_v11_identify_brand(display_name,raw_model,model_ko):
    """Evidence waterfall for placeholder makers.
    1. Explicit manufacturer display when not synthetic.
    2. Explicit manufacturer prefix in raw/model Korean text.
    3. Unique whole-model identity from 397,548 historical source records.
    Never rely on place of registration, first model word or guessed spelling.
    """
    ev=_av13_evidence()['name_keys']
    display=str(display_name or '').strip()
    if display and not _av_is_raw_maker_id(display):
        found=ev.get(_av13_word(display))
        if found:return found
    explicit=[]
    for candidate in (raw_model,model_ko):
        brand=_av13_find_explicit_prefix(candidate)
        if brand:explicit.append(brand)
    if explicit:
        if len(set(explicit))==1:return explicit[0]
        return None
    model_brands=[_av13_unique_model_brand(s) for s in (raw_model,model_ko)]
    model_brands=[b for b in model_brands if b]
    if model_brands:
        return model_brands[0] if len(set(model_brands))==1 else None
    # Retain the previously verified small-maker proof, never infer by a bare
    # shared model prefix or a nationality inferred from an importing country.
    return _AV13_PREVIOUS_IDENTIFY_BRAND(display_name,raw_model,model_ko)

# Brand aliases and user-facing spellings from confirmed trade names.
_AV13_DATA=_av13_evidence()
for _canon,_nice in _AV13_DATA['labels'].items():
    if _canon in {'niesmannbischoff','dethleffs','hymer','adria','buerstner',
                  'knaus','tabbert','weinsberg','morelo','hobby','lmc','carado',
                  'laika','sunlight','crosscamp','eriba','etrusco','poessl',
                  'rollerteam','carthago','capron','westfalia','winnebago',
                  'renaultsamsung','renaultkorea','sunliving','rapido','mclouis'}:
        _AV_MAKER_NAMES[_canon]=_nice
_AV_KNOWN_BRANDS.update(_AV13_DATA['origins'])
_AV_GLOBAL_LEGAL_BRANDS.update({
    'burstner':'buerstner', 'buerstnergmbh':'buerstner',
    'adriamobil':'adria','niesmannbischoffgmbh':'niesmannbischoff',
    'fiatniesmannbischoff':'niesmannbischoff',
    'fiatdethleffs':'dethleffs','fiathymer':'hymer',
    'fiatadria':'adria','fiatlmc':'lmc',
})
for _brand,_variants in {
    'niesmannbischoff':['Niesmann+Bischoff','Niesmann-Bischoff','Niesmann Bischoff',
                        'Niesmannbischoff','Fiat/Niesmann+Bischoff'],
    'dethleffs':['Dethleffs','Fiat-Dethleffs','Ford-Dethleffs'],
    'adria':['Adria Mobil','Adria','Fiat-Adria'],
    'hymer':['Hymer','Fiat-Hymer','Ford-Hymer'],
    'buerstner':['Bürstner','Burstner','Buerstner','Fiat-Burstner'],
    'knaus':['Knaus','Fiat-Knaus'],
    'lmc':['LMC','Fiat-LMC'],
    'sunlight':['Sunlight'],
    'rollerteam':['Roller Team'],
    'carthago':['Carthago'],
}.items():
    _AV_GLOBAL_MODEL_PREFIXES.setdefault(_brand,[])
    for _variant in _variants:
        if _variant not in _AV_GLOBAL_MODEL_PREFIXES[_brand]:
            _AV_GLOBAL_MODEL_PREFIXES[_brand].append(_variant)

# Hash-version changes force the active app to rebuild indexes for ALL rows,
# not to reuse the previous blanket unidentified classifications.
_AV_V9_IDENTITY_VERSION='v13-evidence-based-raw-maker-recovery-v1-20261109'

@functools.lru_cache(maxsize=1)
def manufacturer_recovery_diagnostics():
    """One-pass live catalog statistics, not a synthetic fixture count."""
    with connection() as con:
        return [dict(r) for r in con.execute(
            "SELECT k.brand,COUNT(*) AS rows,COUNT(DISTINCT k.root) AS models "
            "FROM av_idx.vehicle_keys k GROUP BY k.brand ORDER BY rows DESC LIMIT 300"
        )]

# V14: recover a synthetic maker identity using OTHER vehicles assigned to the
# same original maker key. Never expose fabricated RawNNN IDs as manufacturers.
# A model's provenance is preserved; this is a read-only display index overlay.
from collections import defaultdict as _av14_defaultdict

_AV_V9_IDENTITY_VERSION = 'v14-raw-maker-cluster-consensus-20261109'
_AV14_MAKER_GROUP_HINTS = {}
_AV14_MAKER_GROUP_EVIDENCE = {}
_AV14_MAKER_GROUP_CONFLICTS = {}
_AV14_PREV_IDENTITY = _av_v11_identify_brand
_AV14_PREV_INDEX = _av_index_path_v4

def _av14_key(text):
    return re.sub(r'[^a-z0-9가-힣]', '', unicodedata.normalize('NFKC', str(text or '')).casefold())

def _av14_reconcile_source_makers(original):
    """Inspect ALL distinct source model identities before indexing records.

    We never infer the manufacturer from import-market country, shared first
    model word, image appearances, or mere name similarity.
    Each synthetic maker key gets a consensus only if every independently
    identifiable model on that source maker agrees on the same manufacturer.
    """
    groups = _av14_defaultdict(lambda: _av14_defaultdict(set))
    origin_conflicts = _av14_defaultdict(set)
    scanned = 0
    sql = ('SELECT DISTINCT m.maker_key,m.name_ko,m.origin_code,n.raw_name,n.name_ko '
           'FROM models n JOIN makers m ON m.maker_id=n.maker_id')
    for fake,display,origin,raw,ko in original.execute(sql):
        if not (_av_is_raw_maker_id(fake) or _av_is_raw_maker_id(display)):
            continue
        scanned += 1
        # The exact model can be identified independently from the model
        # reference. Explicit *maker* prefixes are especially strong evidence.
        explicit = {_av13_find_explicit_prefix(z) for z in (raw,ko)} - {None}
        inferred = {_av13_unique_model_brand(z) for z in (raw,ko)} - {None}
        brands = explicit if explicit else inferred
        if len(brands) != 1:
            if len(brands)>1:
                origin_conflicts[str(fake)].update(brands)
            continue
        brand = next(iter(brands))
        # A registered vehicle's import country is never a maker's nationality.
        # This field is manufacturer origin when independently established;
        # treat conflicting codes as review signals, not forced assignments.
        model_identity = tuple(sorted({_av14_key(x) for x in (raw,ko) if x}))
        groups[str(fake)][brand].add(model_identity)
    result = {}
    report = {}
    for raw in set(groups) | set(origin_conflicts):
        brand_models = groups.get(raw, {})
        report[raw] = {brand:len(models) for brand,models in brand_models.items()}
        if raw in origin_conflicts or len(brand_models) != 1:
            continue
        brand = next(iter(brand_models))
        if not brand or brand == 'unidentified':
            continue
        # One independently unique whole-model name is evidence of maker
        # identity for other records sharing this *exact* source maker key.
        result[raw] = brand
    return result, report, {key:sorted(values) for key,values in origin_conflicts.items()}, scanned

def _av_v11_identify_brand(display_name, raw_model, model_ko):
    # Exact and explicit per-model proof always overrides cluster-level clues;
    # conflicts are excluded from source consensus entirely.
    found = _AV14_PREV_IDENTITY(display_name,raw_model,model_ko)
    if found:
        return found
    # Brand propagation is only used for genuinely hashed maker IDs; the
    # caller retrieves by the original maker_key in the index construction.
    return None

# The previous index builder gets its 'verified' key via _av_v11_identify_brand,
# but that interface does not receive raw maker_key. Instead we wrap it during
# indexing using a bounded context from the source maker's display label.
_AV14_LOCAL_SOURCE_MAKER = None

def _av14_choose_brand(source_maker,display_name,raw_model,model_ko):
    direct = _AV14_PREV_IDENTITY(display_name,raw_model,model_ko)
    group = _AV14_MAKER_GROUP_HINTS.get(str(source_maker))
    if direct and group and direct != group:
        return direct  # never overwrite independent evidence
    return direct or group

# Replace the final low-level V11 constructor with an exact copy that supplies
# original maker_key to the cluster-aware resolver (and adds an audit table).
def _av14_build_index():
    source=database_path()
    stat=source.stat()
    fingerprint=hashlib.sha256(
        f'{source.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{_AV_V9_IDENTITY_VERSION}'.encode()
    ).hexdigest()[:24]
    target=Path(tempfile.gettempdir()) / f'autoverse_display_index_{fingerprint}.sqlite'
    if target.is_file():
        try:
            with sqlite3.connect(target.as_uri()+'?mode=ro&immutable=1',uri=True) as con:
                if (con.execute('SELECT fingerprint FROM av_meta').fetchone()==(fingerprint,)
                    and 'group_id' in {r[1] for r in con.execute('PRAGMA table_info(vehicle_keys)')}):
                    return target
        except (sqlite3.Error,OSError):pass
    with tempfile.TemporaryDirectory(prefix='autoverse_identity_') as temp:
        output=Path(temp)/'vehicle_index.sqlite'
        with sqlite3.connect(output,uri=True) as dest,_av_prev_connection() as original:
            dest.execute('PRAGMA synchronous=OFF')
            dest.execute('PRAGMA journal_mode=OFF')
            dest.execute('CREATE TABLE vehicle_keys ('
                         'vehicle_id TEXT PRIMARY KEY, root TEXT NOT NULL, gen TEXT NOT NULL,'
                         'face TEXT NOT NULL, origin TEXT NOT NULL, brand TEXT NOT NULL,'
                         'year INTEGER, group_id TEXT, body TEXT NOT NULL)')
            global _AV14_MAKER_GROUP_HINTS, _AV14_MAKER_GROUP_EVIDENCE, _AV14_MAKER_GROUP_CONFLICTS
            (_AV14_MAKER_GROUP_HINTS,_AV14_MAKER_GROUP_EVIDENCE,
             _AV14_MAKER_GROUP_CONFLICTS,scanned) = _av14_reconcile_source_makers(original)
            cursor=original.execute(
                'SELECT v.vehicle_id,v.year,m.maker_key,n.raw_name,n.name_ko,m.origin_code,m.name_ko,v.year_kind,v.source_markets' + _av_base
            )
            def identities():
                for vid,year,maker,raw,ko,previous_origin,display,year_kind,market in cursor:
                    fake = _av_is_raw_maker_id(maker) or _av_is_raw_maker_id(display)
                    verified = ('adriausa1921' if fake and year in (1921,1922) and _av14_key(raw)=='adria' else
                                _av14_choose_brand(maker,display,raw,ko) if fake else None)
                    if fake and not verified:
                        brand='unidentified'
                        origin='UNKNOWN'
                        sourcekey=re.sub(r'[^a-z0-9]','',str(maker).casefold())
                        root,body=_av_name_identity(_av_maker_token(maker),raw,ko,year)
                        root='rawsource:'+sourcekey+':'+(root or str(vid))
                    else:
                        brand=verified or _av_canonical_brand_year(maker,raw,ko,year)
                        origin=_AV_KNOWN_BRANDS.get(brand) or _av_maker_origin(maker,previous_origin)
                        root,body=_av_name_identity(brand,raw,ko,year)
                        if not root:root='unidentified:'+str(vid)
                    gen,stage=_av_market_version(brand,root,raw,ko,year,year_kind,market)
                    yield (vid,root,gen,stage,origin,brand,year,None,body)
            dest.executemany('INSERT INTO vehicle_keys VALUES (?,?,?,?,?,?,?,?,?)',identities())
            _av_reconcile_trim_roots(dest)
            dest.execute('CREATE INDEX ix_v14_model ON vehicle_keys(brand,root,year)')
            from itertools import groupby
            scan=dest.execute('SELECT k.vehicle_id,k.year,k.brand,k.root,k.body,k.gen,k.face,'
                              'v.year_kind,v.source_markets FROM vehicle_keys k JOIN source.vehicles v '
                              'ON v.vehicle_id=k.vehicle_id ORDER BY k.brand,k.root,k.year')
            updates=[]
            for _,family in groupby(scan,key=lambda row:(row[2],row[3])):
                updates.extend(_av_assign_card_ids(list(family)))
                if len(updates)>=4096:
                    dest.executemany('UPDATE vehicle_keys SET body=?,gen=?,face=?,group_id=? WHERE vehicle_id=?',updates)
                    updates.clear()
            dest.executemany('UPDATE vehicle_keys SET body=?,gen=?,face=?,group_id=? WHERE vehicle_id=?',updates)
            scan.close()
            dest.execute('CREATE TABLE cards AS SELECT group_id,MIN(year) first_year,MAX(year) last_year,'
                         'COUNT(DISTINCT year) known_year_count,COUNT(*) source_count '
                         'FROM vehicle_keys GROUP BY group_id')
            dest.execute('CREATE UNIQUE INDEX ix_cards_group ON cards(group_id)')
            dest.execute('CREATE INDEX ix_v14_group ON vehicle_keys(group_id)')
            dest.execute('CREATE INDEX ix_v14_country ON vehicle_keys(brand,origin,year)')
            dest.execute('CREATE TABLE av_meta(fingerprint TEXT NOT NULL)')
            dest.execute('INSERT INTO av_meta VALUES (?)',(fingerprint,))
            dest.execute('CREATE TABLE manufacturer_recovery_audit(raw_maker_key TEXT PRIMARY KEY, '
                         'recovered_brand TEXT, evidence TEXT, conflicts TEXT)')
            makerkeys=set(_AV14_MAKER_GROUP_HINTS)|set(_AV14_MAKER_GROUP_EVIDENCE)|set(_AV14_MAKER_GROUP_CONFLICTS)
            dest.executemany('INSERT INTO manufacturer_recovery_audit VALUES (?,?,?,?)',[
                (mk,_AV14_MAKER_GROUP_HINTS.get(mk),
                 json.dumps(_AV14_MAKER_GROUP_EVIDENCE.get(mk,{}),ensure_ascii=False),
                 json.dumps(_AV14_MAKER_GROUP_CONFLICTS.get(mk,[]),ensure_ascii=False))
                for mk in sorted(makerkeys)])
            dest.commit()
        os.replace(output,target)
    return target

# Retain V10's one-to-one bilingual source-bridge initialization.
@functools.lru_cache(maxsize=1)
def _av_index_path_v4():
    global _AV_V10_SOURCE_BRIDGES
    if not _AV_V10_SOURCE_BRIDGES:
        with _av_prev_connection() as con:
            _AV_V10_SOURCE_BRIDGES=_av_v10_source_bridges(con)
        _av_global_root.cache_clear()
    return _av14_build_index()

@functools.lru_cache(maxsize=1)
def maker_recovery_full_report():
    """Exact figures of the data actually installed for this Streamlit app."""
    with connection() as con:
        total=con.execute('SELECT COUNT(*) FROM av_idx.vehicle_keys').fetchone()[0]
        missing=con.execute("SELECT COUNT(*) FROM av_idx.vehicle_keys WHERE brand='unidentified'").fetchone()[0]
        unresolved=con.execute('SELECT COUNT(DISTINCT m.maker_key) FROM av_idx.vehicle_keys k '
                               'JOIN vehicles v ON v.vehicle_id=k.vehicle_id '
                               'JOIN models n ON n.model_id=v.model_id '
                               'JOIN makers m ON m.maker_id=n.maker_id '
                               "WHERE k.brand='unidentified'").fetchone()[0]
        recovered=con.execute('SELECT COUNT(*) FROM av_idx.manufacturer_recovery_audit '
                              'WHERE recovered_brand IS NOT NULL').fetchone()[0]
        examples=[dict(x) for x in con.execute(
            'SELECT m.maker_key,n.raw_name,n.name_ko,COUNT(*) n '
            'FROM av_idx.vehicle_keys k JOIN vehicles v ON v.vehicle_id=k.vehicle_id '
            'JOIN models n ON n.model_id=v.model_id '
            'JOIN makers m ON m.maker_id=n.maker_id '
            "WHERE k.brand='unidentified' GROUP BY m.maker_key,n.raw_name,n.name_ko "
            'ORDER BY n DESC LIMIT 120')]
        return {'source_vehicle_records':total,'unresolved_records':missing,
                'resolved_records':total-missing,'unresolved_source_makers':unresolved,
                'recovered_raw_maker_groups':recovered,
                'unresolved_samples':examples}

# V15: independently sourced, EXACT model-to-builder evidence. Never match by first word.
# The original maker IDs, vehicle IDs and raw data are preserved.
_AV15_EXACT_MODELS = {
    '4strokerumen': 'fourstroke',
    'abtaudittr': 'abtsportsline',
    'aerolaz': 'laz',
    'angkor333': 'nheanphaloek',
    'arashaf10': 'arashmotorcompany',
    'apalstalker': 'apalrussia',
    'avatrvisionxpectra': 'avatr',
    'belgees50': 'belgee',
    'belgeex50': 'belgee',
    'belgeex70': 'belgee',
    'boldmencr4': 'boldmen',
    'corbellatimissile': 'corbellati',
    'caricemk1': 'carice',
    'cugnotsteamdraycnam106': 'nicolasjosephcugnot',
    'avtorosshaman': 'avtoros',
    'bovensiepenspider': 'bovensiepen',
    'bollorebluetram': 'bollore',
    'equusbass770': 'equusautomotive',
    'bruntonstalker': 'bruntonautomotive',
    'farizonfengrui': 'farizon',
    'exeedsterraet': 'exeed',
}
_AV15_SOURCES = {
    'fourstroke': 'https://globalautoindex.com/news_no-1223/',
    'abtsportsline': 'https://www.abt-america.com/motorsport/history',
    'laz': 'https://wikibus.blob.core.windows.net/sources256/Laz%20AeroLAZ.pdf',
    'nheanphaloek': 'https://thebettercambodia.com/nhean-phaloek-and-his-cambodias-locally-made-first-electric-car/',
    'arashmotorcompany': 'https://www.ncgcam.com/media/75443/ncg-cam-solutions-newsletter_2024.pdf',
    'apalrussia': 'https://auta5p.eu/lang/en/katalog/auto.php?idf=Apal-21541-Stalker-18091',
    'avatr': 'https://www.sttinfo.fi/tiedote/71434951/avatr-presents-the-avatr-vision-xpectra-at-iaa-mobility-2025-emotive-luxury-revolutionises-the-industry?lang=en&publisherId=69821500',
    'belgee': 'https://belgee.ru/about-belgee/',
    'boldmen': 'https://www.boldmen.de/en/boldmen-cr-4/',
    'corbellati': 'https://www.corbellati.com/specifications',
    'carice': 'https://nltimes.nl/2014/06/18/new-dutch-car-brand-debuts-electric-roadster',
    'nicolasjosephcugnot': 'https://commons.wikimedia.org/wiki/Category:Fardier_de_Cugnot_-_CnAM_106',
    'avtoros':'https://avtoros.com/en/about_company/',
    'bovensiepen':'https://www.bovensiepen.com/en/',
    'bollore':'https://www.bollore.com/bollo-content/uploads/2019/05/bollore_ddr_2018_gb_mel.pdf',
    'equusautomotive':'https://www.topgear.com/car-news/usa/equus-reveals-bass-770',
    'bruntonautomotive':'https://en.wikipedia-on-ipfs.org.ipns.s402.de/wiki/Brunton_Stalker',
    'farizon':'https://farizonauto.co.uk/about-farizon',
    'exeed':'https://edrive.am/en/make/exeed/sterra-et',
    'adriausa1921':'https://en.wikipedia.org/wiki/Adria_(automobile)',
}
_AV_MAKER_NAMES.update({
    'fourstroke':'Four Stroke',
    'abtsportsline':'ABT Sportsline',
    'laz':'LAZ',
    'nheanphaloek':'Nhean Phaloek (개인 제작)',
    'arashmotorcompany':'Arash Motor Company',
    'apalrussia':'APAL (러시아)',
    'avatr':'AVATR',
    'belgee':'Belgee',
    'boldmen':'BOLDMEN',
    'corbellati':'Corbellati',
    'carice':'Carice',
    'nicolasjosephcugnot':'니콜라 조제프 퀴뇨 (개인 제작)',
    'avtoros':'AVTOROS',
    'bovensiepen':'Bovensiepen',
    'bollore':'Bolloré',
    'equusautomotive':'Equus Automotive',
    'bruntonautomotive':'Brunton Automotive',
    'farizon':'Farizon',
    'exeed':'EXEED',
    'adriausa1921':'Adria (미국 자동차, 1921–1922)',
})
_AV_KNOWN_BRANDS.update({
    'abtsportsline':'DE', 'laz':'UA',
    'nheanphaloek':'KH', 'arashmotorcompany':'GB',
    'apalrussia':'RU',
    'avatr':'CN','belgee':'BY','boldmen':'DE','corbellati':'IT',
    'carice':'NL','nicolasjosephcugnot':'FR',
    'avtoros':'RU','bovensiepen':'DE','bollore':'FR',
    'equusautomotive':'US','bruntonautomotive':'US',
    'farizon':'CN','exeed':'CN','adriausa1921':'US',
    # 4 Stroke Rumen is documented as a French-built project, but until the
    # company's original home country is independently established, leave
    # nationality unknown rather than substituting factory location.
})

def _av15_verified_model_brand(raw,ko):
    matches = {
        _AV15_EXACT_MODELS[_av14_key(x)]
        for x in (raw,ko)
        if _av14_key(x) in _AV15_EXACT_MODELS
    }
    return next(iter(matches)) if len(matches) == 1 else None

_AV15_PREV_CHOOSE_BRAND=_av14_choose_brand

def _av14_choose_brand(source_maker,display_name,raw_model,model_ko):
    exact=_av15_verified_model_brand(raw_model,model_ko)
    previous=_AV15_PREV_CHOOSE_BRAND(source_maker,display_name,raw_model,model_ko)
    # Contradictory independent evidence must never be silently overwritten.
    if exact and previous and exact != previous:
        return None
    return exact or previous

_AV15_PREV_RECONCILE=_av14_reconcile_source_makers

def _av14_reconcile_source_makers(original):
    resolved,evidence,conflicts,scanned=_AV15_PREV_RECONCILE(original)
    additions={}
    # Cross-check independently verified model names against every other
    # model assigned to the same source maker key, before propagating.
    query=('SELECT DISTINCT m.maker_key,m.name_ko,n.raw_name,n.name_ko '
           'FROM models n JOIN makers m ON m.maker_id=n.maker_id')
    for maker,display,raw,ko in original.execute(query):
        if not (_av_is_raw_maker_id(maker) or _av_is_raw_maker_id(display)):
            continue
        verified=_av15_verified_model_brand(raw,ko)
        if not verified:continue
        additions.setdefault(str(maker),set()).add(verified)
    for maker,found in additions.items():
        base=resolved.get(maker)
        previous_brands=set(evidence.get(maker,{}))
        if (maker in conflicts or len(found) > 1 or (base and base not in found)
                or (previous_brands and previous_brands != found)):
            resolved.pop(maker,None)
            conflicts[maker]=sorted(set(conflicts.get(maker,[])) | found | previous_brands | ({base} if base else set()))
            continue
        verified=next(iter(found))
        resolved[maker]=verified
        evidence.setdefault(maker,{})[verified]=evidence.get(maker,{}).get(verified,0)+1
    return resolved,evidence,conflicts,scanned

_AV_V9_IDENTITY_VERSION='v15-specific-verified-makers-20261109'

# V16: Restore maker identity BEFORE display from same installed catalog evidence.
# This repairs V11's synthetic Raw->unidentified transition for records whose
# exact model has a single, independently known manufacturer in original data.
# Never merge brands from a shared first word, chassis, country or trim alone.
from collections import defaultdict as _av16_defaultdict

_AV_V9_IDENTITY_VERSION='v16-source-maker-restoration-20261109'
_AV16_RECORD_PROOF={}
_AV16_REFERENCE_STATS={}
_AV16_PREVIOUS_RECONCILE=_av14_reconcile_source_makers
_AV16_PREVIOUS_CHOOSE=_av14_choose_brand
_AV16_PREVIOUS_LABEL=_av_maker_name
_AV16_STOP_MODEL_KEYS={
 'car','auto','automobile','truck','van','bus','motorhome','camper',
 'roadster','suv','sedan','coupe','cabrio','electric','hybrid','special',
 'model','unknown','notavailable','other','commercialvehicle','conceptcar',
 'prototype','passengercar','passengervehicle','vehicle','minibus',
 '자동차','승용차','승합차','기타','미확인','모델','전기차','화물차',
}

def _av16_exact_key(s):
    return _av14_key(s)

@functools.lru_cache(maxsize=32768)
def _av16_reference_brand(maker,display):
    # A legal maker key or an independently catalogued company name counts as
    # evidence. A Raw hash, a company-less placeholder, or a model substring
    # is NEVER a manufacturer reference.
    if _av_is_raw_maker_id(maker):
        return None
    known=_av13_evidence()['name_keys']
    # The original maker_key can still be a real brand even when name_ko
    # was overwritten with a Raw hash by an earlier import.
    readable=(maker,) if _av_is_raw_maker_id(display) else (maker,display)
    found={known.get(_av16_exact_key(x)) for x in readable}-{None}
    canonical=_av_canonical_brand_year(maker,'','',None)
    if canonical in _AV_KNOWN_BRANDS:
        found.add(canonical)
    return next(iter(found)) if len(found)==1 else None

def _av16_scan_known_makers(original):
    """Whole-model, cross-manufacturer collision-aware evidence from live DB.

    A source's maker is authoritative only if that maker is identifiable by
    non-synthetic original maker fields. Each entire model spelling must be
    unique across all such manufacturers to be eligible for a Raw lookup.
    """
    refs=_av16_defaultdict(set)
    scan=original.execute('SELECT DISTINCT m.maker_key,m.name_ko,n.raw_name,n.name_ko '
        'FROM models n JOIN makers m ON m.maker_id=n.maker_id')
    examples=0
    for maker,display,raw,ko in scan:
        brand=_av16_reference_brand(maker,display)
        if not brand:continue
        examples+=1
        # Full names including multi-word Santa Fe/Cruz and Yaris/Cross are
        # kept separate. No startswith matching or model-suffix guessing.
        for name in (raw,ko):
            key=_av16_exact_key(name)
            if 5<=len(key)<=75 and key not in _AV16_STOP_MODEL_KEYS and len(set(key))>=3:
                refs[key].add(brand)
            # A verified original company-prefix can be removed at the
            # boundary, never a bare prefix lacking brand proof.
            no_maker=_av_global_strip_maker(name,brand)
            key=_av16_exact_key(no_maker)
            if 5<=len(key)<=75 and key not in _AV16_STOP_MODEL_KEYS and len(set(key))>=3:
                refs[key].add(brand)
    unique={k:next(iter(brands)) for k,brands in refs.items() if len(brands)==1}
    return unique,{'reference_maker_models':examples,
                   'unique_full_model_spellings':len(unique),
                   'ambiguous_full_model_spellings':len(refs)-len(unique)}

def _av14_reconcile_source_makers(original):
    global _AV16_RECORD_PROOF,_AV16_REFERENCE_STATS
    prior,evidence,conflicts,scanned=_AV16_PREVIOUS_RECONCILE(original)
    lookup,stats=_av16_scan_known_makers(original)
    _AV16_REFERENCE_STATS=stats
    record_proof={}
    proof_counts={}
    by_maker=_av16_defaultdict(set)
    raw_key_count=0
    sql='SELECT DISTINCT m.maker_key,m.name_ko,n.raw_name,n.name_ko FROM models n JOIN makers m ON m.maker_id=n.maker_id'
    for maker,display,raw,ko in original.execute(sql):
        if not (_av_is_raw_maker_id(maker) or _av_is_raw_maker_id(display)):
            continue
        raw_key_count+=1
        # Existing source display can legitimately contain a known maker even
        # if m.maker_key is RawHEX. Do not lose that field in display transform.
        named=(None if _av_is_raw_maker_id(display) else _av13_evidence()['name_keys'].get(_av16_exact_key(display)))
        model_candidates={lookup[_av16_exact_key(x)] for x in (raw,ko)
                          if _av16_exact_key(x) in lookup}
        matched={named} if named else model_candidates
        if len(matched)==1:
            found=next(iter(matched))
            # Explicit, contradictory model/maker fields are never overwritten.
            if model_candidates and model_candidates!={found}:
                conflicts.setdefault(str(maker),[])
                conflicts[str(maker)]=sorted(set(conflicts[str(maker)])|model_candidates|{found})
                continue
            key=(str(maker),_av16_exact_key(raw),_av16_exact_key(ko))
            if key not in record_proof:
                proof_counts[str(maker)]=proof_counts.get(str(maker),0)+1
            record_proof[key]=found
            by_maker[str(maker)].add(found)
        elif len(matched)>1:
            by_maker[str(maker)].update(matched)
    for maker,brands in by_maker.items():
        previous=prior.get(maker)
        prior_evidence=set(evidence.get(maker,{}))
        bad=conflicts.get(maker)
        if len(brands)!=1 or bad or (previous and previous not in brands) or (prior_evidence and prior_evidence!=brands):
            prior.pop(maker,None)
            conflicts[maker]=sorted(set(conflicts.get(maker,[]))|brands|prior_evidence|({previous} if previous else set()))
            continue
        found=next(iter(brands))
        prior[maker]=found
        evidence.setdefault(maker,{})[found]=proof_counts[maker]
    _AV16_RECORD_PROOF=record_proof
    stats.update({'raw_models_scanned':raw_key_count,
                  'raw_models_cross_source_match':len(record_proof),
                  'raw_makers_with_source_proof':len(by_maker),
                  'raw_makers_recovered_by_consensus':len([x for x in by_maker if x in prior])})
    return prior,evidence,conflicts,scanned

def _av14_choose_brand(source_maker,display_name,raw_model,model_ko):
    # First use V15's validated company/model resolution; only then the
    # current deployment catalog's unambiguous original maker-reference data.
    base=_AV16_PREVIOUS_CHOOSE(source_maker,display_name,raw_model,model_ko)
    source=_av16_reference_brand(source_maker,display_name)
    if source and not _av_is_raw_maker_id(source_maker):
        return source
    key=(str(source_maker),_av16_exact_key(raw_model),_av16_exact_key(model_ko))
    extra=_AV16_RECORD_PROOF.get(key)
    if base and extra and base!=extra:return None
    return base or extra

# V11 treated *the raw display string itself* as an overriding reason to
# return '제조사 미확인', even when k.brand had been successfully recovered.
# The resolved k.brand must be primary; source display can be a Raw hash.
def _av_maker_name(maker,display):
    key=_av_maker_token(maker)
    known=_AV_MAKER_NAMES.get(key)
    if known and maker!='unidentified':return known
    if maker=='unidentified':
        # The index should have already resolved verified entries. Never claim
        # an inferred brand here or alter the SQL grouping silently.
        return '제조사 미확인'
    if _av_is_raw_maker_id(maker) or _av_is_raw_maker_id(display):
        if not _av_is_raw_maker_id(display):
            matched=_av13_evidence()['name_keys'].get(_av16_exact_key(display))
            if matched and matched in _AV_MAKER_NAMES:
                return _AV_MAKER_NAMES[matched]
        return '제조사 미확인'
    return _AV16_PREVIOUS_LABEL(maker,display)

def maker_recovery_cross_source_stats():
    with connection(): pass
    return dict(_AV16_REFERENCE_STATS)

# Resolve a trim only when the full remaining suffix is a known configuration.
# This preserves standalone families such as Bronco Sport and Mustang Mach-E.
_AV_GLOBAL_MODEL_PREFIXES.update({
    'chevrolet':['Chevrolet','쉐보레','셰보레'],
    'jeep':['Jeep','지프'],
    'honda':['Honda','혼다'],
})
for _brand, _root_key, _names in (
    ('hyundai','ioniq3',('아이오닉 3','IONIQ 3')),
    ('hyundai','ioniq5robotaxi',('아이오닉 5 로보택시','Ioniq 5 Robo taxi')),
    ('kia','k4',('K4',)),
    ('kia','k4sportswagon',('K4 Sportswagon',)),
    ('chevrolet','blazer',('블레이저','브레이저','Blazer')),
    ('chevrolet','colorado',('콜로라도','Colorado')),
    ('jeep','avenger',('어벤저','Avenger')),
    ('jeep','grandcherokeel',('그랜드 체로키 L','Grand Cherokee L')),
    ('jeep','grandwagoneer',('그랜드 왜고니어','Grand Wagoneer')),
    ('jeep','grandwagoneerl',('그랜드 왜고니어 L','Grand Wagoneer L')),
    ('jeep','recon',('리콘','Recon')),
    ('honda','prologue',('프롤로그','Prologue')),
    ('mercedesbenz','aclass',('A-클래스','A-Class','A-Klasse')),
    ('mercedesbenz','bclass',('B-클래스','B-Class','B-Klasse')),
    ('mercedesbenz','cclass',('C-클래스','C-Class','C-Klasse')),
    ('mercedesbenz','eclass',('E-클래스','E-Class','E-Klasse')),
    ('mercedesbenz','sclass',('S-클래스','S-Class','S-Klasse')),
    ('mercedesbenz','gclass',('G-클래스','G-Class','G-Klasse')),
    ('mercedesbenz','sl',('SL', 'SL-Class')),
    *(('mercedesbenz',name,(name.upper(),name.upper()+'-Class')) for name in
      ('cla','cle','gla','glb','glc','gle','gls','eqa','eqb','eqe','eqs') if name not in ('eqe','eqs')),

    ('volkswagen','atlascrosssport',('Atlas Cross Sport',)),
    ('volkswagen','atlas',('Atlas',)),
    ('volkswagen','idbuzz',('ID. Buzz',)),
    ('volkswagen','idbuzzcargo',('ID. Buzz Cargo',)),
    ('volkswagen','id7tourer',('ID.7 Tourer',)),
    ('volkswagen','id3neo',('ID.3 Neo',)),
    ('volkswagen','taos',('Taos',)),
    ('volkswagen','idpolo',('ID. Polo',)),
    *(('volkswagen',f'id{n}',(f'ID.{n}',)) for n in (3,4,5,7)),
    *(('kia',f'ev{n}',(f'EV{n}',)) for n in (2,3,4,5,6,9)),
    *(('bmw',f'x{n}',(f'X{n}',)) for n in range(1,8)),
    *(('bmw',f'i{n}',(f'i{n}',)) for n in (4,5,7)),
    *(('bmw',f'ix{n}',(f'iX{n}',)) for n in (1,2,3,5)),
    *(('bmw',name,(name.upper(),)) for name in ('ix','xm','m2','m3','m4','m5','m8','z4')),
):
    _AV_V10_LABELS.setdefault((_brand,_root_key),_names[0])
    for _name in _names:
        _AV_V10_ALIASES.setdefault((_brand,_av_v10_token(_name)),_root_key)

# The normalized suffix vocabulary recognizes complete words/phrases. Keep
# names with unknown suffixes separate unless a known base + trim matches.
_AV_TRIM_TERMS = r'''
    [24]wd|[fr]wd|awd|4x4|4motion|4matic(?:plus)?|quattro|ffv|flexfuel|
    xdrive\d{0,2}[a-z]?|sdrive\d{0,2}[a-z]?|
    phev|mhev|hev|bev|ev|e[- ]?(?:hybrid|fcev)|electric|hybrid|diesel|gasoline|
    plug[- ]?in\s+hybrid|tdi|tsi|gdi|crdi|cvt|dct|turbo|i[- ]?mmd|
    \d[.,]\d\s*[lt]?|\d{1,3}(?:[.,]\d+)?\s*(?:kwh|kw|hp|ps)|
    \d{1,2}\s*(?:at|mt|dct)|m[5-9]|[245]\s*(?:dr|doors?)|
    \d{2}\s*(?:inch(?:es)?|in|인치)(?:\s*(?:wheels?|tires?|tyres?|휠|타이어))?|
    mud\s+terrain\s+tires?|(?:with\s+)?sport(?:\s+mode|\s*/\s*off\s*road)|charger|
    \bmy\s*(?:20)?\d{2}\b|\b(?:18|19|20)\d{2}\b|
    (?:standard|std|extended|ext|max|long)\s+range|
    (?:with(?:out)?|w)\s*(?:/\s*)?dms|without\s+dms|
    gt[- ]line|n[- ]line|r[- ]line|s[- ]line|x[- ]line|
    base|standard|prestige|premium|signature|exclusive|inspiration|
    luxury|limited|comfortline|highline|execline|business|elegan[ct]e|
    performance|edition|(?:se|sel|le|xle|lx|ex|sx|s|xse|lt|rs)|
    하이브리드|플러그인\s*하이브리드|전기차?|이브이|일렉트릭|가솔린|휘발유|디젤|
    사륜구동|이륜구동|전륜구동|후륜구동|프레스티지|프리미엄|인스퍼레이션|시그니처|노블레스
'''
_AV_BRAND_TRIM_TERMS = {
    'hyundai':r'n|xrt|calligraphy|blue|non[- ]isg|w\s*/\s*stop[- ]start',
    'kia':r'gt|light|wind|land|gt[- ]line|x[- ]pro(?:\s+prestige)?|fe|에프이|along\s+with\s+stop[- ]start',
    'honda':r'type\s+r|si|sport(?:[- ]l)?|touring|elite|black|trailsport|advance|crosstar|sedan|hatchback',
    'volkswagen':r'gtx|gti|gli|r|pro\s+s|pro|pure|kr|lr|perf|sport|prem|peak\s+edition|kombi|ehybrid',
    'chevrolet':r'zr1x|zr1|z06|zr2|bison|e[- ]ray|grand\s+sport|carbon\s+aero|ss|wt|hd',
    'ford':r'raptor(?:\s+r)?|badlands|outer\s+banks|sasquatch|tremor|lariat|lobo|gt|rally|dark\s+horse|gtd|extended',
    'jeep':r'4xe|classic|sahara|rubicon|willys|moab|overland|limited\s+x',
    'mercedesbenz':r'\d{2,3}(?:\s*(?:de|d|e|i))?|4\s*matic(?:\s*plus)?|sedan|roadster|coupe|with\s+eq\s+tech(?:nology)?|eq\s*boost|s\s+e\s+performance',
    'bmw':r'm\s*sport|m\s*xdrive|competition|cs|label|(?:m|edrive|xdrive)\s*\d{2}[ide]?|\d{2}[ide]?(?:\s+xdrive)?',
}
_AV_TRIM_TOKEN = re.compile(r'[a-z0-9가-힣]+',re.I)
_AV_TRIM_GENERATION = re.compile(r'(?i)\b(?:nx4|nx5|mq4|mx5|sx2|sg2|cn7|gn7|ka4|nq5|dn8|gl3|dl3|sp2|sp3)\b')
_AV_PROTECTED_ROOTS = {
    ('kia','niroplus'), ('kia','xceed'), ('kia','k4sportswagon'), ('kia','ev5plus'),
    ('hyundai','ioniq5robotaxi'), ('hyundai','santafexl'),
    ('ford','mustangmache'), ('ford','broncosport'),
    ('volkswagen','atlascrosssport'), ('volkswagen','idbuzzcargo'), ('volkswagen','id3neo'),
    ('chevrolet','trailblazer'), ('toyota','corollacross'), ('toyota','yariscross'),
}

def _av_trim_name_index():
    index={}
    for (brand,alias),root in _AV_V10_ALIASES.items():
        if len(alias)<2 or root=='civictyper':
            continue
        index.setdefault(brand,{}).setdefault(alias[0],{})[alias]=root
    return index

_AV_TRIM_MODELS=_av_trim_name_index()
_AV_TRIM_PATTERNS={
    brand:re.compile(r'(?:(?:'+_AV_TRIM_TERMS+r'|'+_AV_BRAND_TRIM_TERMS.get(brand,r'(?!)')+
                     r')(?:[\s/(),:;|·•+*\[\]._-]+|$))+',re.I|re.X)
    for brand in _AV_TRIM_MODELS
}
_AV_TRIM_ROOT_ALIASES = {
    ('kia','nirofe'):'niro', ('kia','니로에프이'):'niro',
    ('kia','니로일렉트릭'):'niro', ('kia','니로이브이'):'niro',
    ('hyundai','elantran'):'elantra', ('hyundai','avanten'):'elantra',
    ('hyundai','아반떼n'):'elantra', ('hyundai','아반떼엔'):'elantra',
    ('hyundai','ioniq5n'):'ioniq5', ('hyundai','ioniq6n'):'ioniq6',
    ('hyundai','아이오닉5n'):'ioniq5', ('hyundai','아이오닉6n'):'ioniq6',
    ('hyundai','아이오닉5엔'):'ioniq5', ('hyundai','아이오닉6엔'):'ioniq6',
    ('hyundai','konan'):'kona', ('honda','civictyper'):'civic',
    ('honda','cr'):'crv', ('honda','hr'):'hrv',
    ('kia','sportagemy26'):'sportage',
    ('mercedesbenz','claclass'):'cla', ('mercedesbenz','glaclass'):'gla',
    ('mercedesbenz','glbclass'):'glb', ('mercedesbenz','glcclass'):'glc',
    ('mercedesbenz','gleclass'):'gle', ('mercedesbenz','glsclass'):'gls',

}

@functools.lru_cache(maxsize=131072)
def _av_known_trim_root(brand,name):
    models=_AV_TRIM_MODELS.get(brand)
    if not models or not name:
        return None
    text=_av_global_strip_maker(_av_nfkc(name),brand)
    # Split only an explicit name/specification separator.
    text=re.split(r'\s*[·•|*]\s*',text,maxsplit=1)[0]
    if brand=='mercedesbenz':
        # AMG power outputs can be appended to a letter-coded model.
        # Keep AMG GT and Maybach as distinct nameplates.
        text=re.sub(r'^amg\s+(?!gt\b)', '', text)
        coded=re.fullmatch(r'(a|b|c|e|g|s|sl|cla|cle|gla|glb|glc|gle|gls)\s*(?=\d{2,3}(?!\d))(.+)',text)
        if coded and _AV_TRIM_PATTERNS[brand].fullmatch(coded[2]):
            root=coded[1]
            return root+'class' if len(root)==1 else root
    text=_AV_TRIM_GENERATION.sub(' ',_AV_FL.sub(' ',_AV_PRE.sub(' ',text)))
    words=list(_AV_TRIM_TOKEN.finditer(text))
    if not words:
        return None
    roots=models.get(words[0].group()[0],{})
    key=''
    best=None
    for word in words:
        key+=word.group()
        root=roots.get(key)
        if not root:
            continue
        tail=text[word.end():].strip(' \t/(),:;[]+._-')
        if not tail or _AV_TRIM_PATTERNS[brand].fullmatch(tail):
            best=root
        elif root=='niro' and re.match(r'^(?:fe|에프이|이브이|일렉트릭|\d[.,]\d)(?=\W|$)',tail):
            # The older Korean nameplate source transliterates the full
            # engine/gearbox description after an explicit Niro variant.
            if re.search(r'\d[.,]\d.*(?:지디아이|\bgdi\b|에이티|\b[1-9]at\b)',tail):
                best=root
    return best

_AV_ROOT_BEFORE_TRIMS=_av_global_root
@functools.lru_cache(maxsize=262144)
def _av_global_root(maker,raw,ko,year=None):
    brand=_av_canonical_brand_year(maker,raw,ko,year)
    original=_AV_ROOT_BEFORE_TRIMS(brand,raw,ko,year)
    explicit=_AV_TRIM_ROOT_ALIASES.get((brand,original))
    if explicit:
        return explicit
    if (brand,original) in _AV_PROTECTED_ROOTS:
        return original
    if (brand,original) in _AV_V10_LABELS:
        return original
    return _av_known_trim_root(brand,raw) or original

_AV_V9_IDENTITY_VERSION='v17-model-trim-identity-20261114-r3'

# Body, generation and facelift belong in the vehicle identity. Years describe
# appearances of that identity in the source catalogue.
_AV_GLOBAL_MODEL_PREFIXES.update({
    'porsche':['Porsche','포르쉐','포르셰'],
    'polestar':['Polestar','폴스타'],
    'ferrari':['Ferrari','페라리'],
})
for _brand,_label in {**_AV13_DATA['labels'],**_AV_MAKER_NAMES}.items():
    if len(_brand)<3 or len(_label)<2 or '(' in _label or _brand=='unidentified':
        continue
    _prefixes=_AV_GLOBAL_MODEL_PREFIXES.setdefault(_brand,[])
    for _prefix in (_brand,_label):
        if _prefix not in _prefixes:
            _prefixes.append(_prefix)
_AV_TRIM_PATTERNS['porsche']=re.compile(
    r'(?:(?:'+_AV_TRIM_TERMS+r'|[24]s?|gts|turbo\s+s|turbo\s+gt|turbo|'
    r'e[- ]?hybrid|(?:performance|perf\.?)\s+battery(?:\s+plus)?|'
    r'range\s+setup|all[- ]season(?:\s+tires?)?|ms|aero\s+design\s+wheels?)'
    r'(?:[\s/(),:;|·•+*\[\]._-]+|$))+',re.I|re.X
)
_AV_BODY_WORDS = {
    'wagon': r'station[ -]?wagon|sports[ -]?wagon|estate|touring[ -]?sports|sport[ -]?wagon|wagen|wagon|왜건|웨건|스테이션\s*왜건',
    'sedan': r'sedan|saloon|세단',
    'hatchback': r'hatchback|해치백',
    'fastback': r'fastback|liftback|패스트백|리프트백',
    'coupe': r'coup[eé]|쿠페',
    'convertible': r'convertible|cabriolet|cabrio|roadster|drophead|컨버터블|카브리올레|로드스터',
    'suv': r'crossover|suv|스포츠\s*유틸리티',
    'pickup': r'pick[ -]?up(?:[ -]?truck)?|픽업(?:트럭)?',
    'mpv': r'mpv|minivan|미니밴',
    'van': r'panel[ -]?van|cargo[ -]?van|van|밴',
    'chassis': r'cab[ -]?chassis|chassis[ -]?cab|섀시캡',
}
_AV_BODY_LABELS = dict(zip(_AV_BODY_WORDS,(
    '왜건','세단','해치백','패스트백','쿠페','컨버터블','SUV',
    '픽업','MPV','밴','섀시캡'
)))
_AV_BODY_WORD = re.compile(
    r'(?<![\w-])(?:'+ '|'.join(f'(?P<{k}>{v})' for k,v in _AV_BODY_WORDS.items()) + r')(?!\w)', re.I
)
_AV_BODY_BY_NAME = {
    ('kia','k4sportswagon'):('k4','wagon'),
    ('volkswagen','id7tourer'):('id7','wagon'),
    ('volkswagen','idbuzzcargo'):('idbuzz','van'),
    ('mercedesbenz','eqeclass'):('eqe','suv'),
    ('mercedesbenz','eqsclass'):('eqs','suv'),
}
_AV_BODY_DEFAULT = {
    ('kia','ev5'):'suv', ('kia','k4'):'sedan',
    ('honda','accord'):'sedan', ('honda','civic'):'sedan',
    ('hyundai','elantra'):'sedan', ('hyundai','grandeur'):'sedan',
    ('hyundai','ioniq5'):'suv', ('hyundai','sonata'):'sedan',
    ('toyota','corolla'):'sedan', ('volkswagen','golf'):'hatchback',
    ('skoda','octavia'):'fastback', ('kia','ceed'):'hatchback',
    ('chevrolet','camaro'):'coupe',
    ('porsche','cayenne'):'suv', ('porsche','taycan'):'sedan',
}
_AV_EXACT_ROOTS = {
    ('kia','ev5plus'):'ev5', ('kia','이브이5플러스'):'ev5',
    ('kia','이브이5'):'ev5', ('kia','k4hatchback'):'k4',
    ('kia','k4hatch'):'k4',
    ('hyundai','ioniq5robotaxi'):'ioniq5',
    ('hyundai','쏘나타디엣지'):'sonata', ('hyundai','sonatatheedge'):'sonata',
}
_AV_V10_LABELS[('kia','ev5')]='EV5'
_AV_V10_ALIASES.update({
    ('kia','ev5plus'):'ev5', ('kia','이브이5플러스'):'ev5', ('kia','이브이5'):'ev5',
})
for _number in range(1,8):
    _model=f'polestar{_number}'
    _AV_V10_LABELS[('polestar',_model)]=f'폴스타 {_number}'
    for _alias in (_model,f'폴스타{_number}'):
        _AV_V10_ALIASES[('polestar',_alias)]=_model
_AV_V10_LABELS[('ferrari','f80')]='F80'
_AV_V10_ALIASES[('ferrari','f80')]='f80'
_AV_V10_ALIASES[('ferrari','에프80')]='f80'
_AV_POLESTAR_TRIM = re.compile(
    r'(?:(?:'+_AV_TRIM_TERMS+r'|dual\s+motor|single\s+motor|performance\s+pack|'
    r'\d{2}"(?:\s+wheels?)?)(?:[\s/(),:;|·•+*\[\]._-]+|$))+',re.I|re.X
)
_AV_FAMILY_GENS = {
    ('kia','niro'):('de','sg2'), ('kia','carnival'):('kvii','vq','yp','ka4'),
    ('kia','sportage'):('nb7','km','sl','ql','nq5'), ('kia','seltos'):('sp2','sp3'),
    ('kia','sorento'):('bl','xm','um','mq4'),
    ('hyundai','elantra'):('j1','j2','xd','hd','md','ad','cn7'),
    ('hyundai','sonata'):('yf','lf','dn8'), ('hyundai','santafe'):('sm','cm','dm','tm','mx5'),
    ('hyundai','grandeur'):('xg','tg','hg','ig','gn7'),
    ('hyundai','tucson'):('jm','lm','tl','nx4','nx5'), ('hyundai','kona'):('os','sx2'),
    ('hyundai','ioniq5'):('ne',), ('kia','ev5'):('ov','ov1'),
    ('jeep','wrangler'):('yj','tj','jk','jl'),
    ('chevrolet','camaro'):(),
    ('honda','civic'):(),
    ('volkswagen','golf'):(),
}
_AV_GEN_CODE = {
    key:re.compile(r'(?<![\w])(?:'+'|'.join(sorted(codes,key=len,reverse=True))+r')(?![\w])')
    for key,codes in _AV_FAMILY_GENS.items() if codes
}
_AV_ORDINAL_GEN = re.compile(
    r'(?<!\w)(?:gen(?:eration)?[ -]*(\d{1,2})|mk[ -]*(\d{1,2}|viii|vii|vi|iv|iii|ii|ix|x|v|i))(?!\w)|(?<!\d)(\d{1,2})\s*세대'
)
_AV_ROMAN_GENERATIONS=dict(zip(('i','ii','iii','iv','v','vi','vii','viii','ix','x'),map(str,range(1,11))))
_AV_GENERATION_ALIASES = {
    ('kia','niro','1'):'de', ('kia','niro','2'):'sg2', ('kia','ev5','1'):'ov1',
    ('kia','carnival','3'):'yp', ('kia','carnival','4'):'ka4',
    ('kia','sorento','3'):'um', ('kia','sorento','4'):'mq4',
    ('kia','sportage','3'):'sl', ('kia','sportage','4'):'ql', ('kia','sportage','5'):'nq5',
    ('hyundai','grandeur','6'):'ig', ('hyundai','grandeur','7'):'gn7',
    ('hyundai','elantra','5'):'md', ('hyundai','elantra','6'):'ad', ('hyundai','elantra','7'):'cn7',
    ('hyundai','santafe','4'):'tm', ('hyundai','santafe','5'):'mx5',
    ('hyundai','kona','1'):'os', ('hyundai','kona','2'):'sx2',
    ('hyundai','tucson','3'):'tl', ('hyundai','tucson','4'):'nx4',
    ('hyundai','sonata','6'):'yf', ('hyundai','sonata','7'):'lf', ('hyundai','sonata','8'):'dn8',
}
_AV_FACELIFT_NUMBER = re.compile(r'(?<!\w)(?:face[ -]?lift[ -]*|lci[ -]+|f[ /-]l[ -]*|fl[ -]+)(\d)(?!\w)|(?<!\d)(\d)\s*차\s*(?:부분\s*변경|페이스리프트)')
_AV_BUILD_GENERATION = re.compile(r'(?<!\w)(?:[efg]\d{2}|w\d{3})(?!\w)')
_AV_NAME_BREAK = re.compile(r'\s*[·•|*]\s*')
_AV_BODY_QUERY = {normalize(label):body for body,label in _AV_BODY_LABELS.items()}
_AV_VERIFIED_KOREAN_VERSIONS = {
    # Hyundai domestic heritage pages, Hyundai Motor Group 2023 Seoul Mobility
    # Show release, and Kia's Sportage model history. A worldwide registration
    # year or a source maker's nationality alone is not a model-year signal.
    ('hyundai','elantra'):((2018,'ad','fl'),(2020,'cn7',''),(2023,'cn7','fl')),
    ('hyundai','grandeur'):((2016,'ig',''),(2019,'ig','fl'),(2022,'gn7','')),
    ('hyundai','sonata'):((2019,'dn8',''),(2023,'dn8','fl')),
    ('kia','niro'):((2016,'de',''),(2019,'de','fl'),(2022,'sg2',''),(2026,'sg2','fl')),
    ('kia','sportage'):((1993,'nb7',''),(1998,'nb7','fl'),(2004,'km',''),
                        (2010,'sl',''),(2015,'ql',''),(2018,'ql','fl'),
                        (2021,'nq5',''),(2024,'nq5','fl')),
}
_AV_CONFIRMED_VERSION_NAMES={
    ('hyundai','elantra','더뉴아반떼'):('cn7','fl'),
    ('hyundai','sonata','쏘나타디엣지'):('dn8','fl'),
    ('hyundai','sonata','sonatatheedge'):('dn8','fl'),
}

def _av_market_version(brand,root,raw,ko,year,year_kind,market):
    gen,stage=_av_version(brand,root,raw,ko)
    if stage or year is None:return gen,stage
    timeline=_AV_VERIFIED_KOREAN_VERSIONS.get((brand,root))
    if not timeline:return gen,stage
    label=_av_v10_token(_av_global_strip_maker(_AV_NAME_BREAK.split(_av_nfkc(raw),maxsplit=1)[0],brand))
    if (brand,root)==('kia','niro'):
        if label in {'더뉴니로','thenewniro'}:
            if year>=2026 and gen in {'','sg2'}:return 'sg2','fl'
            if 2019<=year<=2021 and gen in {'','de'}:return 'de','fl'
        if not gen:
            if 2016<=year<2022:
                gen='de'
            elif year==2022 and year_kind=='model' and market=='US':
                gen='de'
            elif year>=2023 and year_kind in {'model','generation','introduction'}:
                gen='sg2'
        if gen and year_kind=='model' and market=='US' and year>=2027 and gen=='sg2':
            return gen,'fl'
    named=_AV_CONFIRMED_VERSION_NAMES.get((brand,root,label))
    # The marketing prefix can repeat over multiple generations; date must
    # agree with the specific named version before it determines identity.
    if named and year>=2023 and (not gen or gen==named[0]):
        return named
    if year_kind=='generation':
        matches=(entry for entry in timeline if entry[0]==year)
    elif year_kind=='model' and market=='KR':
        matches=(entry for entry in reversed(timeline) if entry[0]<year)
        # A domestic model year at the launch boundary can include both
        # versions, so require direct generation/facelift evidence for it.
        if any(entry[0]==year for entry in timeline):return gen,stage
    else:
        return gen,stage
    match=next(matches,None)
    return (match[1],match[2]) if match and (not gen or gen==match[1]) else (gen,stage)

@functools.lru_cache(maxsize=65536)
def _av_body_head(brand, raw, korean):
    name=_av_global_strip_maker(_AV_NAME_BREAK.split(_av_nfkc(raw or korean),maxsplit=1)[0],brand)
    # Multiword vehicle body descriptions take precedence over the word "van".
    if brand=='skoda':
        name=re.sub(r'\bcombi\b','wagon',name)
    if brand in {'bmw','audi','volkswagen','mercedesbenz'}:
        name=re.sub(r'\b(?:touring|avant|variant|t[- ]modell)\b','wagon',name)
    if brand=='honda' and re.match(r'(?:civic|시빅)\b',name):
        if re.search(r'\bfl5\b',name):
            name=re.sub(r'\bfl5\b','hatchback',name)
        name=re.sub(r'\b(?:5dr|type\s+r)\b','hatchback',name)
        name=re.sub(r'\b4dr\b','sedan',name)
    if brand=='volkswagen' and re.match(r'(?:golf|골프)\b',name):
        name=re.sub(r'\b(?:gti|gt[ -]?d|gte)\b','hatchback',name)
    if brand=='porsche':
        name=re.sub(r'\b(?:cross|sport)\s+turismo\b','wagon',name)
        if re.search(r'\bcayenne\s+turbo\s+gt\b',name):
            name=name+' coupe'
    matches=list(_AV_BODY_WORD.finditer(name))
    if not matches:
        return name,''
    kinds={m.lastgroup for m in matches}
    precedence=('chassis','pickup','convertible','wagon','hatchback','fastback','sedan','coupe','mpv','van','suv')
    body=next(kind for kind in precedence if kind in kinds)
    stripped=_AV_BODY_WORD.sub(' ',name).strip(' ._-()')
    return stripped or name,body

@functools.lru_cache(maxsize=131072)
def _av_name_identity(brand,raw,ko,year):
    head,body=_av_body_head(brand,raw,ko)
    root=_av_global_root(brand,raw,ko,year)
    if brand=='polestar':
        label=re.sub(r'^(?:(?:polestar|폴스타)\s+)+','',head)
        model=re.fullmatch(r'([1-7])(?:\s+(.+))?',label)
        if model:
            tail=model[2]
            if not tail or _AV_POLESTAR_TRIM.fullmatch(tail.strip(' ()')):
                return 'polestar'+model[1],body
    if brand=='ferrari' and _av_v10_token(head) in {'f80','에프80'}:
        return 'f80',body
    explicit=_AV_BODY_BY_NAME.get((brand,root))
    if explicit:
        return explicit
    root=_AV_EXACT_ROOTS.get((brand,root),root)
    if body or brand=='porsche' or _AV_FACELIFT_NUMBER.search(head) or _AV_ORDINAL_GEN.search(head):
        # Strip explicit identity markers before normalizing trim descriptions.
        words=_AV_ORDINAL_GEN.sub(' ',_AV_FACELIFT_NUMBER.sub(' ',head))
        stripped=_av_global_root(brand,words,'',year)
        root=_AV_EXACT_ROOTS.get((brand,stripped),stripped) or root
    if (brand,root) not in _AV_FAMILY_GENS:
        # A chassis code alone does not identify a model. Only accept a code
        # attached to one of this manufacturer's known model families.
        for (maker,family),code in _AV_GEN_CODE.items():
            if maker!=brand or not root.startswith(family):continue
            found=code.search(head)
            if found:
                stripped=head[:found.start()]+' '+head[found.end():]
                model=_av_global_root(brand,stripped,'',year)
                if model==family:
                    root=family
                    break
    return root,body

@functools.lru_cache(maxsize=65536)
def _av_version(brand,root,raw,ko):
    names=' '.join(_AV_NAME_BREAK.split(_av_nfkc(s),maxsplit=1)[0] for s in (raw,ko))
    chassis=_AV_GEN_CODE.get((brand,root))
    found=chassis.search(names) if chassis else None
    gen=found.group() if found else ''
    if brand=='honda' and root=='civic' and re.search(r'(?<!\w)fl5(?!\w)',names):
        gen='gen11'
    if brand=='kia' and root=='ev5' and gen=='ov':
        gen='ov1'
    if not gen:
        ordinal=_AV_ORDINAL_GEN.search(names)
        if ordinal:
            number=next(n for n in ordinal.groups() if n)
            number=_AV_ROMAN_GENERATIONS.get(number,number)
            gen=_AV_GENERATION_ALIASES.get((brand,root,number),'gen'+number)
        elif brand in {'bmw','mercedesbenz'}:
            chassis=_AV_BUILD_GENERATION.search(names)
            gen=chassis.group() if chassis else ''
    facelift=_AV_FACELIFT_NUMBER.search(names)
    stage=('fl'+next(n for n in facelift.groups() if n)) if facelift else _av_facelift(raw,ko)
    if stage=='fl1':stage='fl'
    return gen,stage

# Infer an omitted body or generation only from the same family and compatible
# source evidence. Overlap stays unresolved unless there is a known default.
def _av_infer_version(rows,position,context,default=''):
    from collections import defaultdict
    observed=defaultdict(set)
    intervals={}
    for row,key in zip(rows,context):
        year,value=row[1],row[position]
        if value:
            observed[key].add(value)
            if year is not None:
                observed[(key,year)].add(value)
                lo,hi=intervals.get((key,value),(year,year))
                intervals[(key,value)]=(min(lo,year),max(hi,year))
    result=[]
    for row,key in zip(rows,context):
        year,value=row[1],row[position]
        if not value:
            choices=observed[(key,year)]
            if not choices and year is not None and len(observed[key])>1:
                choices={x for x in observed[key] if (key,x) in intervals
                         and intervals[(key,x)][0]<=year<=intervals[(key,x)][1]}
            if not choices:choices=observed[key]
            if default:
                value=default
            elif len(choices)==1:
                value=next(iter(choices))
        result.append(value)
    return result

def _av_assign_card_ids(rows):
    # Each invocation receives one normalized manufacturer + model family.
    from collections import defaultdict
    _,_,brand,root,*_=rows[0]
    family=(brand,root)
    default_body=_AV_BODY_DEFAULT.get(family,'')
    bodies=_av_infer_version(rows,4,['']*len(rows),default_body)
    gens=_av_infer_version(rows,5,bodies)
    launches=defaultdict(dict)
    earliest={}
    for row,body in zip(rows,bodies):
        _,year,_,_,_,gen,_,kind,market=row
        if gen and year is not None and kind in {'introduction','generation'}:
            earliest[(body,gen)]=min(earliest.get((body,gen),year),year)
            if market:
                starts=launches[(body,market)]
                starts[gen]=min(starts.get(gen,year),year)
    for i,(row,body,gen) in enumerate(zip(rows,bodies,gens)):
        _,year,_,_,_,explicit,_,kind,market=row
        started=earliest.get((body,gen))
        if gen and not explicit and year is not None and started is not None and year<started-1:
            gen=gens[i]=''
        if gen or year is None or kind not in {'model','generation','introduction'}:continue
        starts=launches.get((body,market),{})
        # Only bracket years between documented launches for the same
        # body and market. Transition years can contain both generations.
        if len(starts)<2 or year in starts.values():continue
        earlier=[(start,version) for version,start in starts.items() if start<year]
        if earlier and year<max(starts.values()):
            latest=max(start for start,_ in earlier)
            options={version for start,version in earlier if start==latest}
            if len(options)==1:gens[i]=next(iter(options))
    dated=defaultdict(set)
    first_facelift={}
    for row,body,gen in zip(rows,bodies,gens):
        year,stage=row[1],row[6]
        if stage and year is not None:
            dated[(body,gen,year)].add(stage)
            if stage!='pre':
                key=(body,gen)
                first_facelift[key]=min(year,first_facelift.get(key,year))
    for row,body,gen in zip(rows,bodies,gens):
        vid,year,_,_,_,_,stage=row[:7]
        if stage=='pre':
            stage=''
        elif not stage and year is not None:
            known=dated[(body,gen,year)]
            # An unchanged facelift identity can absorb model years sharing
            # explicit same-year facelift evidence after its first observation.
            if len(known)==1 and 'pre' not in known and year>first_facelift.get((body,gen),year):
                stage=next(iter(known))
        group=json.dumps([brand,root,body,gen,stage],ensure_ascii=False,separators=(',',':'))
        yield (body,gen,stage,group,vid)

# Reuse explicitly recognized trim phrasing for brands outside the curated
# alias list, but require an exact supported base name in that same catalogue.
_AV_GENERIC_TRIM = re.compile(r'(?:(?:'+_AV_TRIM_TERMS+r')(?:[\s/(),:;|·•+*\[\]._-]+|$))+',re.I|re.X)
_AV_GUARDED_NAME = re.compile(r'(?i)\b(?:concept|prototype|replica|kit\s*car|look|제작|콘셉트|컨셉|프로토타입)\b')

def _av_observed_base(brand,root,name,roots):
    if (brand,root) in _AV_PROTECTED_ROOTS or (brand,root) in _AV_V10_LABELS:
        return root
    if brand=='unidentified' or _AV_GUARDED_NAME.search(name):
        return root
    pattern=_AV_TRIM_PATTERNS.get(brand,_AV_GENERIC_TRIM)
    words=list(_AV_TRIM_TOKEN.finditer(name))
    key=''
    best=root
    for word in words[:-1]:
        key+=word.group()
        if len(key)<3:continue
        alias=_AV_V10_ALIASES.get((brand,key),key)
        if alias not in roots or alias==root:continue
        tail=name[word.end():].strip(' \t/(),:;[]+._-')
        if tail and pattern.fullmatch(tail):
            best=alias
    return best

def _av_reconcile_trim_roots(index):
    """Scan every source row for exact in-brand model plus configuration."""
    from collections import defaultdict
    names=defaultdict(set)
    for brand,root in index.execute('SELECT DISTINCT brand,root FROM vehicle_keys'):
        names[brand].add(root)
    with_change=[]
    index.execute('ATTACH DATABASE ? AS source',(database_path().as_uri()+'?mode=ro&immutable=1',))
    cursor=index.execute('SELECT k.vehicle_id,k.brand,k.root,n.raw_name,n.name_ko,k.year,v.year_kind,v.source_markets '
                         'FROM vehicle_keys k JOIN source.vehicles v ON v.vehicle_id=k.vehicle_id '
                         'JOIN source.models n ON n.model_id=v.model_id')
    for vid,brand,root,raw,ko,year,kind,market in cursor:
        if brand=='unidentified' or root in {'','unknown'}:continue
        head,_=_av_body_head(brand,raw,ko)
        model=_av_observed_base(brand,root,head,names[brand])
        if model==root:continue
        gen,stage=_av_market_version(brand,model,raw,ko,year,kind,market)
        with_change.append((vid,model,gen,stage))
    cursor.close()
    index.execute('CREATE TEMP TABLE trim_root_changes(vid TEXT PRIMARY KEY,root TEXT,gen TEXT,face TEXT)')
    index.executemany('INSERT INTO trim_root_changes VALUES (?,?,?,?)',with_change)
    index.execute('UPDATE vehicle_keys AS k SET (root,gen,face)=(SELECT root,gen,face FROM trim_root_changes WHERE vid=k.vehicle_id) '
                  'WHERE vehicle_id IN (SELECT vid FROM trim_root_changes)')
    index.execute('CREATE TABLE identity_audit(metric TEXT PRIMARY KEY,value INTEGER)')
    index.execute("INSERT INTO identity_audit VALUES('additional_trim_matches',?)",(len(with_change),))
    index.execute('DROP TABLE trim_root_changes')


_AV_BODY_CONDITIONS=conditions
_AV_EXACT_MODEL_SEARCH = {
    **{alias:('kia','ev5') for alias in ('ev5','ev5plus','이브이5','이브이5플러스')},
    **{alias:('kia','k4') for alias in ('k4','케이4')},
}
def conditions(query='',year=None,countries=None,maker=None,strict_model=False,unknown_year=False):
    name,sep,body=str(query or '').strip().rpartition(' ')
    shape=_AV_BODY_QUERY.get(normalize(body)) if sep else None
    q=normalize(name if shape else query)
    # Short known identifiers also occur inside unrelated vehicle codes.
    exact=_AV_EXACT_MODEL_SEARCH.get(q)
    if exact and maker in (None,'',exact[0]):
        where,values=_AV_BODY_CONDITIONS('',year,countries,maker,strict_model,unknown_year)
        where+=(' AND ' if where else ' WHERE ')+'k.brand=? AND k.root=?'
        values=list(values)+list(exact)
        return (where+' AND k.body=?',values+[shape]) if shape else (where,values)
    if not shape:
        return _AV_BODY_CONDITIONS(query,year,countries,maker,strict_model,unknown_year)
    where,values=_AV_BODY_CONDITIONS(name,year,countries,maker,strict_model,unknown_year)
    return where+(' AND ' if where else ' WHERE ')+'k.body=?',values+[shape]

_AV_YEAR_SPAN_SEARCH=search
@functools.lru_cache(maxsize=512)
def search(query='',year=None,countries=None,maker=None,strict_model=False,unknown_year=False,page=1,page_size=18):
    result=_AV_YEAR_SPAN_SEARCH(query,year,countries,maker,strict_model,unknown_year,page,page_size)
    rows=[]
    for row in result['rows']:
        label=_av_card_model_name(row['maker_key'],row['av_root'],row['model_ko'])
        rows.append({**row,'model_ko':label,'maker_ko':maker_display_label(row['maker_key'],row['maker_ko'],row.get('year'))})
    return {**result,'rows':rows}

def _av_card_model_name(brand,root,label):
    if (brand,root) in {('kia','cerato'),('kia','optima'),('ssangyong','korandoturismo')}:
        return label
    return _AV_V10_LABELS.get((brand,root),label)

def identity_badges(record):
    body=_AV_BODY_LABELS.get(record.get('av_body'),'')
    generation=record.get('kept_gen','')
    stage=record.get('kept_face','')
    version='부분변경'+(' '+stage[2:]+'차' if stage.startswith('fl') and stage[2:] else '') if stage.startswith('fl') else ''
    if generation=='unverified':generation=''
    elif generation.startswith('gen'):generation=generation[3:]+'세대'
    else:generation=generation.upper()
    return [text for text in (body,generation,version) if text]

def identity_year_label(record):
    first,last=record.get('first_year'),record.get('last_year')
    if first is None:return '연도 미확인'
    if first==last:return f'{first}년 자료'
    return f'{first}~{last}년 자료'

def classification_counts():
    with connection() as con:
        raw,groups,unclassified=con.execute(
            "SELECT COUNT(*),COUNT(DISTINCT group_id),"
            "SUM(CASE WHEN brand='unidentified' THEN 1 ELSE 0 END) FROM av_idx.vehicle_keys"
        ).fetchone()
        extra=con.execute("SELECT value FROM av_idx.identity_audit WHERE metric='additional_trim_matches'").fetchone()[0]
    return {'원자료':raw,'차량 카드':groups,'제조사 미확인 원자료':unclassified,'추가로 통합한 트림 표기 원자료':extra}

_AV_BODY_VEHICLE=vehicle
def vehicle(vehicle_id):
    row=_AV_BODY_VEHICLE(vehicle_id)
    if not row:return None
    with connection() as con:
        info=con.execute('SELECT k.root av_root,k.gen kept_gen,k.face kept_face,k.body av_body,'
                         'k.group_id av_group,c.first_year,c.last_year,c.known_year_count '
                         'FROM av_idx.vehicle_keys k JOIN av_idx.cards c ON c.group_id=k.group_id '
                         'WHERE k.vehicle_id=?',(vehicle_id,)).fetchone()
    row['maker_ko']=maker_display_label(row['maker_key'],row['maker_ko'],row.get('year'))
    if info:
        row.update(dict(info))
        row['model_ko']=_av_card_model_name(row['maker_key'],row['av_root'],row['model_ko'])
    return row

_AV_V9_IDENTITY_VERSION='v18-vehicle-body-and-version-20261115-r7'

# Calendar-year evidence accompanies the research catalog. Source model-year
# tags are retained as citations, never used as calendar-year sales keys.
import zlib as _sale_zlib
from collections import Counter as _SaleCounter, defaultdict as _SaleBuckets

_SALE_DATA = json.loads(_sale_zlib.decompress((_REFS / 'sale_evidence.zlib').read_bytes()))
_SALE_FIELDS = ('brand', 'root', 'label', 'body', 'year', 'origin', 'market',
                'url', 'units', 'generation', 'model_year', 'date')
_SALE_BODIES = {**_AV_BODY_LABELS, 'hardtop': '하드톱', 'mpv': 'MPV', 'pickup': '픽업',
                'suv': 'SUV', 'chassis': '섀시', 'bus': '버스', 'truck': '트럭'}
_SALE_MARKETS = {'EU': '유럽', 'GLOBAL': '글로벌', 'RELEASE': '제조사 출시 기록'}
_SALE_BRANDS = {'chery': '체리', 'changan': '창안', 'cupra': '쿠프라', 'deepal': '디팔',
                'geely': '지리', 'greatwall': '그레이트월', 'haval': '하발', 'jaecoo':'재쿠',
                'mahindra': '마힌드라', 'omoda':'오모다', 'vinfast':'빈패스트', 'xiaomi':'샤오미'}
_SALE_EXACT_GROUPS = _SALE_DATA.get('links', {})
_SALE_PERIODS = _SALE_DATA.get('periods', {})
_SALE_SPECIFICATIONS = _SALE_DATA.get('specs', {})

# Explicit source spellings retain the manufacturer and the model family.
# Door counts do not introduce another hatchback or sedan model.
_SALE_SOURCE_IDENTITIES = {
    ('mazda', '2'): ('mazda2', ''),
    ('mazda', '3'): ('mazda3', ''),
    ('subaru', 'forestereboxer'): ('forester', ''),
    ('renault', 'kangooze'): ('kangoo', ''),
    ('renault', 'kwidetech'): ('kwid', ''),
    ('renault', 'masteretechelectrico'): ('master', ''),
    ('chevrolet', 'chevy3ptas'): ('chevy', 'hatchback'),
    ('chevrolet', 'chevy4ptas'): ('chevy', 'sedan'),
    ('chevrolet', 'chevy5ptas'): ('chevy', 'hatchback'),
    ('chevrolet', 'corvette2pts'): ('corvette', 'convertible'),
    ('chevrolet', 'sonic5pts'): ('sonic', 'hatchback'),
    ('chevrolet', 'luvchasiscabina'): ('luv', 'chassis'),
    ('ford', 'ikonhatch'): ('ikon', 'hatchback'),
    ('nissan', 'almera4pts'): ('almera', 'sedan'),
    ('nissan', 'platina4pts'): ('platina', 'sedan'),
    ('nissan', 'sentra4pts'): ('sentra', 'sedan'),
    ('nissan', 'tsuru4pts'): ('tsuru', 'sedan'),
    ('volkswagen', 'crafterchasis'): ('crafter', 'chassis'),
    ('changan', 'hunterchasis'): ('hunter', 'chassis'),
}
_SALE_DISPLAY_NAMES = {
    ('mazda', 'mazda2'): '마쓰다2', ('mazda', 'mazda3'): '마쓰다3',
    ('mazda', 'mx5'): 'MX-5', ('mazda', 'cx3'): 'CX-3',
    ('mazda', 'cx30'): 'CX-30', ('mazda', 'cx5'): 'CX-5',
    ('mazda', 'cx50'): 'CX-50', ('mazda', 'cx70'): 'CX-70',
    ('mazda', 'cx90'): 'CX-90', ('subaru', 'brz'): 'BRZ',
    ('subaru', 'wrx'): 'WRX', ('kia', 'k3bl7'): 'K3',
}


def _sale_identity(record):
    root = record['root']
    brand = record['brand']
    if root == 'k3bl7':
        return root
    root = _SALE_SOURCE_IDENTITIES.get((brand, root), (root, ''))[0]
    return _AV_V10_ALIASES.get((brand, root), root)

def _sale_version(item):
    token = item['generation']
    if not token:
        return '', ''
    if isinstance(token, int):
        key = (item['brand'], _sale_identity(item), str(token))
        return _AV_GENERATION_ALIASES.get(key, 'gen'+str(token)), ''
    parts = token.lower().split(' ', 1)
    return parts[0], parts[1] if len(parts)>1 else ''

def _sale_market_name(code):
    return _SALE_MARKETS.get(code) or country_name(code)

def _sale_rank(item):
    gen, face = _sale_version(item)
    ordinal = re.fullmatch(r'gen(\d+)', gen)
    number = int(ordinal[1]) if ordinal else 0
    for (brand, root, candidate), code in _AV_GENERATION_ALIASES.items():
        if (brand, root, code)==(item['brand'], _sale_identity(item), gen):
            number = int(candidate)
            break
    facelift = int(face[2:] or '1') if re.fullmatch(r'fl\d*', face) else 0
    return (number, facelift, item['date'] or '', bool(item['generation']), item['market']=='KR',
            bool(item['units']), bool(item['body']))

def _sale_card_key(scope, brand, root, year, body):
    label='|'.join(map(str, (scope, brand, root, year, body)))
    return 'AVSALE-'+hashlib.sha256(label.encode()).hexdigest()[:24]

def _sale_terms(brand, root, names, maker, body):
    maker_aliases = _maker_display_search_terms(brand) | {normalize(maker)}
    words = {normalize(name) for name in (*names, root, brand)} | maker_aliases
    words.update(alias for (b, alias), target in _AV_V10_ALIASES.items()
                 if b == brand and target == root)
    for term in tuple(words):
        words.update(prefix+term for prefix in maker_aliases if prefix+term)
    label = normalize(_SALE_BODIES.get(body, ''))
    if body:
        words.update(term+suffix for term in tuple(words) for suffix in {normalize(body), label} if term)
    return tuple(sorted(word for word in words if word))

@functools.lru_cache(maxsize=1)
def _sale_cards():
    families = _SaleBuckets(list)
    for values in _SALE_DATA['records']:
        item = dict(zip(_SALE_FIELDS, values))
        source_identity = _SALE_SOURCE_IDENTITIES.get((item['brand'], item['root']))
        if source_identity and source_identity[1]:
            item['body'] = source_identity[1]
        scope = 'release' if item['market']=='RELEASE' else 'sale'
        families[(scope, item['brand'], _sale_identity(item), item['year'])].append(item)
    cards = {}
    for (scope, brand, root, year), items in families.items():
        bodies = {item['body'] for item in items if item['body']}
        shapes = bodies or {''}
        for body in sorted(shapes):
            exact = [item for item in items if item['body']==body]
            family = [item for item in items if not item['body']] if body else []
            # A calendar-year card represents the latest proven version for
            # that body. Undifferentiated annual totals remain family evidence.
            versioned = [item for item in exact if item['generation']]
            best = max(versioned or exact, key=_sale_rank)
            gen, face = _sale_version(best)
            if gen:
                selected = [item for item in exact if _sale_version(item)==(gen,face)]
                family.extend(item for item in exact if not item['generation'])
                exact = selected
            maker = maker_display_label(brand, _SALE_BRANDS.get(brand) or brand.upper(), year)
            all_names = {item['label'] for item in (*exact, *family)}
            label = _av_card_model_name(brand, root, best['label'])
            label = _SALE_DISPLAY_NAMES.get((brand, root), label)
            identifier = _sale_card_key(scope, brand, root, year, body)
            cards[identifier] = {
                'vehicle_id':identifier, 'year':year, 'sale_year':year if scope=='sale' else None,
                'origin_code':best['origin'], 'model_ko':label, 'maker_key':brand, 'maker_ko':maker,
                'av_root':root, 'av_body':body, 'kept_gen':gen, 'kept_face':face,
                'source_kind':'calendar_sale' if scope=='sale' else 'manufacturer_release',
                'first_year':year, 'last_year':year, 'raw_model':best['label'],
                'scope':scope, '_items':tuple(exact), '_family':tuple(family),
                '_terms':_sale_terms(brand, root, (*all_names, label,
                    'K3' if root=='k3bl7' else root), maker, body),
            }
    return cards

def _sale_matches(record, query):
    if not query:
        return True
    body_filter = next((shape for term, shape in _SALE_QUERY_SUFFIXES
                        if query.endswith(term) and len(query)>len(term)), '')
    if body_filter:
        if record['av_body']!=body_filter:
            return False
    if len(query)<=3 and query.isascii():
        return query in record['_terms']
    return any(query in term for term in record['_terms'])

_SALE_QUERY_SUFFIXES = sorted({(normalize(name), shape) for shape, name in _SALE_BODIES.items()}
                              | {(normalize(shape), shape) for shape in _SALE_BODIES},
                              key=lambda pair:-len(pair[0]))

@functools.lru_cache(maxsize=192)
def _sale_filtered(query='', year=None, countries=None, maker=None, scope='sale'):
    query=normalize(query)
    return tuple(row for row in _sale_cards().values()
                 if row['scope']==scope and (year is None or row['year']==year)
                 and (countries is None or row['origin_code'] in countries)
                 and (not maker or row['maker_key']==maker)
                 and _sale_matches(row,query))

def sales_search(query='', year=None, countries=None, maker=None, scope='sale', page=1, page_size=18):
    rows=_sale_filtered(query,year,countries,maker,scope)
    pages=max(1, math.ceil(len(rows)/page_size))
    page=max(1,min(pages,page))
    rows=sorted(rows,key=lambda row:(-row['year'], row['maker_ko'], row['model_ko'],
                                    row['av_root'],row['av_body']))
    return {'rows':rows[(page-1)*page_size:page*page_size], 'total':len(rows), 'page':page, 'pages':pages}

def sales_country_counts(query='', year=None, scope='sale'):
    return dict(_SaleCounter(row['origin_code'] for row in _sale_filtered(query,year,scope=scope)))

def sales_maker_options(query='', year=None, countries=None, scope='sale'):
    names={row['maker_key']:row['maker_ko'] for row in _sale_filtered(query,year,countries,scope=scope)}
    return [{'maker_key':key,'name_ko':names[key]} for key in sorted(names,key=lambda key:names[key])]

def sales_years():
    return {row['year'] for row in _sale_cards().values()}

def sales_totals():
    rows=tuple(_sale_cards().values())
    sales=[row for row in rows if row['scope']=='sale']
    return {'판매 확인 카드':len(sales), '제조사 브랜드':len({row['maker_key'] for row in sales}),
            '제조사 출시 카드':len(rows)-len(sales)}

_SALE_OLD_VEHICLE=vehicle
_SALE_OLD_DETAILS=load_details
_SALE_OLD_GROUP=load_group_details
_SALE_OLD_BADGES=identity_badges
_SALE_OLD_YEARS=identity_year_label

def vehicle(vehicle_id):
    if vehicle_id.startswith('AVSALE-'):
        return _sale_cards().get(vehicle_id)
    return _SALE_OLD_VEHICLE(vehicle_id)

def identity_badges(record):
    if record.get('scope') not in ('sale','release'):
        return _SALE_OLD_BADGES(record)
    badges=[_SALE_BODIES.get(record['av_body'], '')]
    badges.extend(_SALE_OLD_BADGES({**record,'av_body':''}))
    return [badge for badge in badges if badge]

def identity_year_label(record):
    if record.get('scope')=='sale':
        return str(record['year'])+'년 판매'
    if record.get('scope')=='release':
        return str(record['year'])+'년 출시'
    return _SALE_OLD_YEARS(record)

def load_details(vehicle_id):
    if vehicle_id.startswith('AVSALE-'):
        reference=_SALE_EXACT_GROUPS.get(vehicle_id)
        return _SALE_OLD_DETAILS(reference) if reference else {}
    return _SALE_OLD_DETAILS(vehicle_id)

@functools.lru_cache(maxsize=256)
def load_group_details(vehicle_id):
    if not vehicle_id.startswith('AVSALE-'):
        return _SALE_OLD_GROUP(vehicle_id)
    card=_sale_cards().get(vehicle_id)
    if card is None:
        return {}
    reference=_SALE_EXACT_GROUPS.get(vehicle_id)
    result=dict(_SALE_OLD_GROUP(reference)) if reference else {}
    specification_key='|'.join((card['maker_key'],card['av_root'],card['kept_gen'],
                                card['kept_face'],card['av_body']))
    verified=_SALE_SPECIFICATIONS.get(specification_key,{})
    if verified:
        result['specifications']=_av_merge_specs(
            list(result.get('specifications',[]))+verified.get('specifications',[]), [])
    sources={s.get('url'):s for s in result.get('sources',[]) if isinstance(s,dict) and s.get('url')}
    sources.update({source['url']:source for source in verified.get('sources',[])})
    evidence=[]
    # Keep totals from different authorities separate even for the same market.
    for item, family in [(row,False) for row in card['_items']]+[(row,True) for row in card['_family']]:
        market=_sale_market_name(item['market'])
        label=('모델 전체 · ' if family else '')+market
        amount=f"{item['units']:,}대" if item['units'] else ''
        period=_SALE_PERIODS.get(item['url']+'|'+str(item['year']))
        partial_october=('inegi.org.mx' in item['url'] or '302927617' in item['url'])
        if period and amount:
            amount+=f' ({period[0]}~{period[1]}월)'
        elif item['year']==2026 and partial_october and amount:
            amount+=' (1~10월)'
        if item['model_year']:
            amount=' · '.join(part for part in (amount, str(item['model_year'])+'년식') if part)
        if item['date']:
            amount=' · '.join(part for part in (amount,item['date']) if part)
        if not amount and not family:
            amount='판매 확인' if card['scope']=='sale' else '출시 확인'
        if amount and (label,amount,item['url']) not in evidence:
            evidence.append((label,amount,item['url']))
        sources[item['url']]={'url':item['url'],'label_ko':label+' · 원본 자료'}
    result['calendar_evidence']=tuple(evidence)
    result['sources']=list(sources.values())
    return result

_SALE_EXACT_GROUPS.update({'AVSALE-85e3137ad857596fc139f9ce': 'AV-68AA3BBCD382B3416445', 'AVSALE-3d1240454b733601bc0c0383': 'AV-6E14FDDFDFB103DB4F6B', 'AVSALE-bff8973b83ea4ca522b15a2c': 'AV-8FE6BCD343689C9C4321'})

# The deployment index contains source ranges and their provenance. Source
# registrations and approvals do not create calendar-year sales entries.
import lzma

@functools.lru_cache(maxsize=1)
def research_manifest():
    path = ROOT / 'research_data' / 'manifest.json'
    if not path.is_file():
        path = DATA / 'research' / 'manifest.json'
    return (path.parent, json.loads(path.read_text(encoding='utf-8'))) if path.is_file() else (None, {})


@functools.lru_cache(maxsize=1)
def _research_database():
    directory, info = research_manifest()
    if not info:
        return None
    identity = info['sqlite_sha256']
    target = Path(tempfile.gettempdir()) / ('autoverse_research_'+identity+'.sqlite')
    if target.is_file() and target.stat().st_size == info['sqlite_bytes']:
        return target
    with tempfile.TemporaryDirectory(prefix='autoverse_research_', dir=target.parent) as stage:
        packed = Path(stage) / 'research.gz'
        working = Path(stage) / 'research.sqlite'
        with packed.open('wb') as result:
            for part in info['parts']:
                path = directory / Path(part['file']).name
                if not path.is_file():
                    raise ValueError('조사 자료 업로드 누락 '+path.name)
                with path.open('rb') as source:
                    digest = hashlib.sha256()
                    while block := source.read(1024*1024):
                        digest.update(block)
                        result.write(block)
                if digest.hexdigest() != part['sha256']:
                    raise ValueError('조사 자료 파일 손상 '+path.name)
        decompress = lzma.open if info.get('compression')=='xz' else gzip.open
        with decompress(packed,'rb') as source, working.open('wb') as result:
            shutil.copyfileobj(source,result,1024*1024)
        with working.open('rb') as source:
            if hashlib.file_digest(source,'sha256').hexdigest() != identity:
                raise ValueError('조사 자료 무결성 확인 실패')
        os.replace(working,target)
    return target


@contextmanager
def _research_connection():
    path = _research_database()
    if not path:
        yield None
        return
    db = sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()


def _research_like(query):
    return '%'+normalize(query).replace('_','\\_')+'%'


@functools.lru_cache(maxsize=128)
def research_search(query='', source='', page=1, identity=(), page_size=20):
    clauses, params = [], []
    if identity:
        clauses += ['brand=?','family=?']
        params += list(identity)
    elif query:
        brands = _AV_PRESENTATION_BRAND_QUERY.get(normalize(query))
        if brands:
            clauses.append('(search_text LIKE ? OR brand IN ('+','.join('?' for _ in brands)+'))')
            params.extend([_research_like(query), *sorted(brands)])
        else:
            clauses.append('search_text LIKE ?')
            params.append(_research_like(query))
    if source:
        clauses.append('source=?')
        params.append(source)
    where = ' WHERE '+' AND '.join(clauses) if clauses else ''
    with _research_connection() as db:
        if db is None:
            return 0, (), 1
        total = db.execute('SELECT count(*) FROM observations'+where,params).fetchone()[0]
        page = max(1,min(page,max(1,(total+page_size-1)//page_size)))
        rows = db.execute('SELECT id,brand,maker,model,body,generation,recorded_year,report_year,market,year_basis,source,n '
                          'FROM observations'+where+' ORDER BY id LIMIT ? OFFSET ?',[*params,page_size,(page-1)*page_size])
        return total,tuple(dict(row) for row in rows),page


@functools.lru_cache(maxsize=256)
def research_record(record_id):
    with _research_connection() as db:
        if db is None:
            return None
        row = db.execute('SELECT * FROM observations WHERE id=?',(record_id,)).fetchone()
        if row is None:
            return None
        details = dict(row)
        _, info = research_manifest()
        details['specifications'] = _research_specs(json.loads(row['specs']),info,False)
        return details


def _research_specs(values, info, compact):
    output = []
    for index, (lo,hi) in values:
        label, unit = info['fields'][index]
        output.append({'label_ko':label,'unit':unit,'value':_av_format_number(lo) if lo==hi else
                       _av_format_number(lo)+'~'+_av_format_number(hi)} if compact else
                      {'항목':label,'단위':unit,'값':_av_format_number(lo) if lo==hi else
                       _av_format_number(lo)+'~'+_av_format_number(hi)})
    return output


@functools.lru_cache(maxsize=8192)
def _research_exact(vehicle_id):
    if not vehicle_id.startswith('AV-'):
        return {}
    with _research_connection() as db:
        if db is None:
            return {}
        row = db.execute('SELECT specs,fuel,urls,has_unsourced FROM exact_specs WHERE vehicle_id=?',(vehicle_id,)).fetchone()
        if row is None:
            return {}
        _, info = research_manifest()
        specs = _research_specs(json.loads(row['specs']),info,True)
        if row['fuel']:
            specs.append({'label_ko':'연료','value':row['fuel'],'unit':''})
        return {'specifications':specs,'sources':[{'url':url,'label_ko':'1·2단계 제원 원자료'}
                                                 for url in json.loads(row['urls'])],
                'research_unsourced':bool(row['has_unsourced'])}


_group_before_research = load_group_details


@functools.lru_cache(maxsize=128)
def load_group_details(vehicle_id):
    data = _group_before_research(vehicle_id)
    if not research_manifest()[1]:
        return data
    if vehicle_id.startswith('AVSALE-'):
        member = _SALE_EXACT_GROUPS.get(vehicle_id)
        if not member:
            return data
        exact = load_group_details(member)
    else:
        ids = tuple(row[0] for row in _av_group_members(vehicle_id)) or (vehicle_id,)
        observations = [_research_exact(identifier) for identifier in ids]
        exact = {'specifications': [v for item in observations for v in item.get('specifications',())],
                 'sources': [v for item in observations for v in item.get('sources',())],
                 'research_unsourced':any(item.get('research_unsourced') for item in observations)}
    if not exact.get('specifications') and not exact.get('sources'):
        return data
    summary = dict(data)
    summary['specifications'] = _av_merge_specs([*data.get('specifications',()),*exact.get('specifications',())],())
    summary['sources'] = list({item['url']:item for item in (*data.get('sources',()),*exact.get('sources',()))
                               if isinstance(item,dict) and item.get('url')}.values())
    summary['research_unsourced'] = bool(exact.get('research_unsourced'))
    return summary

# Display names confirmed in Korean manufacturer, importer, association, or
# automotive coverage. These labels do not change manufacturer identities.
_AV_KOREAN_MAKER_DISPLAY = {
    'abarth': '아바스',
    'acura': '아큐라',
    'adria': '아드리아',
    'alfaromeo': '알파 로메오',
    'astonmartin': '애스턴마틴',
    'bentley': '벤틀리',
    'buick': '뷰익',
    'chery': '체리',
    'chrysler': '크라이슬러',
    'cupra': '쿠프라',
    'dodge': '닷지',
    'fiat': '피아트',
    'geely': '지리자동차',
    'haval': '하발',
    'holden': '홀덴',
    'infiniti': '인피니티',
    'knaus': '크나우스',
    'koenigsegg': '코닉세그',
    'lancia': '란치아',
    'landrover': '랜드로버',
    'leapmotor': '립모터',
    'lincoln': '링컨',
    'lotus': '로터스',
    'lucid': '루시드',
    'mahindra': '마힌드라',
    'maruti': '마루티 스즈키',
    'mazda': '마쓰다',
    'maybach': '메르세데스-마이바흐',
    'mclaren': '맥라렌',
    'mercedes': '메르세데스-벤츠',
    'mercedesbenz': '메르세데스-벤츠',
    'nio': '니오',
    'pagani': '파가니',
    'perodua': '페로두아',
    'polestar': '폴스타',
    'proton': '프로톤',
    'ram': '램',
    'rivian': '리비안',
    'rollsroyce': '롤스로이스',
    'saab': '사브',
    'seat': '세아트',
    'skoda': '스코다',
    'tabbert': '타버트',
    'tata': '타타',
    'vauxhall': '복스홀',
    'weinsberg': '바인스버그',
    'xpeng': '샤오펑',
    'zeekr': '지커',
}

# These shorter Latin marks are widely displayed in Korea. Jeep is explicitly
# retained. Korean names here are for search only.
_AV_KEEP_LATIN_MAKER_DISPLAY = {
    'jeep': 'Jeep',
    'bmw': 'BMW',
    'mini': 'MINI',
    'byd': 'BYD',
    'gmc': 'GMC',
    'kgm': 'KGM',
    'mg': 'MG',
    'greatwall': 'GWM',
    'dsautomobiles': 'DS Automobiles',
}
_AV_KOREAN_MAKER_ALIASES = {
    'jeep': ('지프',),
    'bmw': ('비엠더블유',),
    'mini': ('미니',),
    'byd': ('비야디',),
    'gmc': ('지엠씨', '지엠시'),
    'kgm': ('케이지모빌리티', '케이지엠', 'KG모빌리티'),
    'mg': ('엠지',),
    'greatwall': ('GWM', '그레이트월', '장성자동차'),
    'dsautomobiles': ('DS', '디에스'),
    'mazda': ('마쯔다', '마즈다'),
    'acura': ('아쿠라',),
    'mercedesbenz': ('Mercedes', '벤츠'),
    'maybach': ('Maybach', '마이바흐'),
    'geely': ('지리',),
    'chery': ('체리자동차',),
    'tata': ('타타자동차',),
    'lotus': ('로투스',),
    'skoda': ('Skoda', 'Škoda', '슈코다'),
    'maruti': ('Maruti Suzuki', '마루티'),
    'weinsberg': ('바인스베르크',),
}
_AV_DISPLAY_BRANDS = {**_AV_KOREAN_MAKER_DISPLAY, **_AV_KEEP_LATIN_MAKER_DISPLAY}


def maker_display_label(brand, fallback, year=None):
    if brand == 'renaultkorea' and year in (2022, 2023):
        return '르노코리아자동차'
    return _AV_DISPLAY_BRANDS.get(brand) or _av_maker_name(brand, fallback)


def _maker_display_search_terms(brand):
    values = (brand, _AV_MAKER_NAMES.get(brand, ''), _AV_DISPLAY_BRANDS.get(brand, ''),
              *_AV_KOREAN_MAKER_ALIASES.get(brand, ()))
    return {normalize(value) for value in values if value}


_AV_PRESENTATION_BRAND_QUERY = {}
for _brand in _AV_DISPLAY_BRANDS:
    for _term in _maker_display_search_terms(_brand):
        _AV_PRESENTATION_BRAND_QUERY.setdefault(_term, set()).add(_brand)

_AV_MAKER_QUERY_CONDITIONS = conditions


def conditions(query='', year=None, countries=None, maker=None, strict_model=False, unknown_year=False):
    brands = _AV_PRESENTATION_BRAND_QUERY.get(normalize(query))
    if not brands:
        return _AV_MAKER_QUERY_CONDITIONS(query, year, countries, maker, strict_model, unknown_year)
    where, args = _AV_MAKER_QUERY_CONDITIONS('', year, countries, maker, strict_model, unknown_year)
    where += (' AND ' if where else ' WHERE ') + 'k.brand IN (' + ','.join('?' for _ in brands) + ')'
    return where, [*args, *sorted(brands)]
