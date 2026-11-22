"""Load checked-in assets from disk so code and media can be updated separately."""
import base64
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parent


def text(name):
    return (ASSETS / name).read_text(encoding="utf-8")


@st.cache_data(show_spinner=False)
def _data_url(path, mime_type, revision):
    encoded = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def data_url(name, mime_type):
    path = ASSETS / name
    info = path.stat()
    return _data_url(str(path), mime_type, (info.st_size, info.st_mtime_ns))
