"""Read-only vehicle search and optional, separately supplied detail records."""
from __future__ import annotations
import functools,gzip,hashlib,json,os,re,shutil,sqlite3,tempfile,urllib.parse
from pathlib import Path
from contextlib import contextmanager
ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('AUTOVERSE_DATA_DIR',ROOT/'data')).resolve()
@functools.lru_cache(maxsize=1)
def manifest():return json.loads((DATA/'catalog_manifest.json').read_text(encoding='utf-8'))
@functools.lru_cache(maxsize=1)
def database_path():
 m=manifest();digest=m['sqlite_sha256'];dest=Path(tempfile.gettempdir())/('autoverse_catalog_'+digest[:20]+'.sqlite')
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
