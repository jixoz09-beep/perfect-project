import streamlit as st

st.set_page_config(
    page_title="AUTOVERSE · 자동차 탐색·제작·주행",
    page_icon="🚘",
    layout="wide",
    initial_sidebar_state="collapsed",
)

try:
    from autoverse_app import run
except ModuleNotFoundError as error:
    if error.name != "autoverse_app":
        raise
    st.error("저장소에서 main.py 옆에 autoverse_app 폴더를 올려 주세요.")
    st.stop()

run()
