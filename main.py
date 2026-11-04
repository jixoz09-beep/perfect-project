"""AUTOVERSE — GitHub 웹 업로드용 실행 파일.
필수 파일: main.py, requirements.txt, autoverse_data_001.bin~005.bin (같은 폴더).
2,027개 제품 / 171개 엔진 / 34개 부품군 / 15개 공통 생성기.
사진·외형 반영: 부품 1,942개, 엔진 143개.
원본 다운로드 대기: 부품 85개, 엔진 28개.
478개 제공 ID-사진 URL 연결 원문을 전부 보존했습니다.
실행: streamlit run main.py"""
from pathlib import Path, PurePosixPath
import hashlib,io,lzma,os,runpy,shutil,sys,tempfile,zipfile

_PAYLOAD_SHA256='fd46ffad701e6cfcd17728ff57dac602057dd2e189b9cae876640142d2b93da3'
_PAYLOAD_FILE='autoverse_data.xz'
_PAYLOAD_PARTS=[('autoverse_data_001.bin', 5000000, '0690f4009416b4bde7321791d4aff70049a7d19c8ee17415b7ba90d4967af400'), ('autoverse_data_002.bin', 5000000, '8c02b6bdbf59dc0e016f250efc16311d4ab31d35cb1397280fcbb7fe265a2328'), ('autoverse_data_003.bin', 5000000, 'd61c9c87dbb4ca6939f21d80a4a45452a220c4a1165f704a9f9cdbe2cba0787c'), ('autoverse_data_004.bin', 5000000, '7fcd289411cc0af6e89b3ae502c43b46918bc1ea37f9258ad53ce6b774f7fc08'), ('autoverse_data_005.bin', 4770824, '66e9b62e235b6d41680b6649ba0a40da58583615a64794652ee678d99c5b0255')]
_PACKED_SHA256='0ad8bf91c3e7ccf7a5d25fb0bd1bcfc8597eb8a07b9b399f3d3214c9bebd6065'

def _read_packed_data():
    directory=Path(__file__).resolve().parent
    present=[(directory/name).is_file() for name,_,_ in _PAYLOAD_PARTS]
    if any(present):
        missing=[name for (name,_,_),exists in zip(_PAYLOAD_PARTS,present) if not exists]
        if missing:
            raise RuntimeError('같은 폴더에 자료 조각을 모두 올려 주세요. 빠진 파일: '+', '.join(missing))
        chunks=[]
        for name,size,digest in _PAYLOAD_PARTS:
            path=directory/name
            if path.stat().st_size!=size:
                raise RuntimeError(name+'의 크기가 맞지 않습니다. 새 ZIP에서 받은 파일을 다시 올려 주세요.')
            body=path.read_bytes()
            if hashlib.sha256(body).hexdigest()!=digest:
                raise RuntimeError(name+'가 손상되었습니다. 새 ZIP에서 받은 파일을 다시 올려 주세요.')
            chunks.append(body)
        return b''.join(chunks)
    legacy=directory/_PAYLOAD_FILE
    if legacy.is_file():
        return legacy.read_bytes()
    raise RuntimeError('autoverse_data_001.bin부터 autoverse_data_005.bin까지 다섯 파일을 main.py와 같은 폴더에 올려 주세요.')

def _restore_application():
    cache=Path(tempfile.gettempdir())/'autoverse_feature2'
    cache.mkdir(exist_ok=True)
    root=cache/_PAYLOAD_SHA256[:24]
    marker=root/'READY'
    if marker.is_file() and marker.read_text()==_PAYLOAD_SHA256:return root
    packed=_read_packed_data()
    if hashlib.sha256(packed).hexdigest()!=_PACKED_SHA256:
        raise RuntimeError('autoverse_data.xz가 손상되었습니다. 받은 파일 전체를 다시 올려 주세요.')
    blob=lzma.decompress(packed,format=lzma.FORMAT_XZ)
    if hashlib.sha256(blob).hexdigest()!=_PAYLOAD_SHA256:
        raise RuntimeError('main.py의 내장 자료가 손상되었습니다. 파일 전체를 다시 복사해 주세요.')
    stage=Path(tempfile.mkdtemp(prefix='staging_',dir=cache))
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            for entry in archive.infolist():
                path=PurePosixPath(entry.filename)
                if path.is_absolute() or '..' in path.parts or (entry.external_attr>>16)&0o170000==0o120000:
                    raise RuntimeError('잘못된 내장 자료 경로입니다.')
            archive.extractall(stage)
        (stage/'READY').write_text(_PAYLOAD_SHA256)
        try:os.rename(stage,root)
        except OSError:
            if not marker.is_file() or marker.read_text()!=_PAYLOAD_SHA256:raise
    finally:
        if stage.exists():shutil.rmtree(stage)
    return root

_root=_restore_application()
# Vehicle research stays in the user's existing data folder. Feature 2's data,
# photos, fonts and Three.js modules are restored from verified data parts.
_external_data=Path(__file__).resolve().parent/'data'
if _external_data.is_dir() and not (_root/'data').exists():
    try:(_root/'data').symlink_to(_external_data,target_is_directory=True)
    except OSError:pass
if str(_root) not in sys.path:sys.path.insert(0,str(_root))
for _name,_module in list(sys.modules.items()):
    if _name=='feature2' or _name.startswith('feature2.'):
        _file=getattr(_module,'__file__',None)
        if _file and not Path(_file).resolve().is_relative_to(_root):sys.modules.pop(_name,None)
runpy.run_path(str(_root/'main.py'),run_name='__main__')
