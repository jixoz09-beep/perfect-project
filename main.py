"""AUTOVERSE — GitHub 웹 업로드용 실행 파일.
필수 파일: main.py, requirements.txt, autoverse_data.xz (같은 폴더).
2,027개 제품 / 171개 엔진 / 34개 부품군 / 15개 공통 생성기.
사진·외형 반영: 부품 1,942개, 엔진 143개.
원본 다운로드 대기: 부품 85개, 엔진 28개.
478개 제공 ID-사진 URL 연결 원문을 전부 보존했습니다.
실행: streamlit run main.py"""
from pathlib import Path, PurePosixPath
import hashlib,io,lzma,os,runpy,shutil,sys,tempfile,zipfile

_PAYLOAD_SHA256='fd46ffad701e6cfcd17728ff57dac602057dd2e189b9cae876640142d2b93da3'
_PAYLOAD_FILE='autoverse_data.xz'
_PACKED_SHA256='0ad8bf91c3e7ccf7a5d25fb0bd1bcfc8597eb8a07b9b399f3d3214c9bebd6065'

def _restore_application():
    cache=Path(tempfile.gettempdir())/'autoverse_feature2'
    cache.mkdir(exist_ok=True)
    root=cache/_PAYLOAD_SHA256[:24]
    marker=root/'READY'
    if marker.is_file() and marker.read_text()==_PAYLOAD_SHA256:return root
    payload_file=Path(__file__).resolve().parent/_PAYLOAD_FILE
    if not payload_file.is_file():
        raise RuntimeError('autoverse_data.xz 파일을 main.py와 같은 폴더에 올려 주세요.')
    packed=payload_file.read_bytes()
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
# photos, fonts and Three.js modules are restored from autoverse_data.xz.
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

