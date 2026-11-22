"""Streamlit routing and common appearance for AUTOVERSE."""
import streamlit as st

from .asset_files import data_url, text

HOME = "home"
EXPLORE = "explore"
WORKSHOP = "workshop"
DRIVE = "drive"
FEATURE_1 = "기능 1 · 세계 자동차 탐색"
FEATURE_2 = "기능 2 · 자동차 제작"


def navigate(page):
    if st.session_state.get("_av_page") == EXPLORE:
        from .explorer import DEFAULTS

        st.session_state.explorer_settings = {
            key: st.session_state.get(key, default) for key, default in DEFAULTS.items()
        }
    st.session_state._av_page = page
    st.session_state._av_home_visited = True


def _navigation(page):
    with st.container(key="av_feature_nav"):
        home, other, _ = st.columns([1, 2, 4], gap="small")
        home.button("← 처음 화면", key="av_to_home", on_click=navigate,
                    args=(HOME,), width="stretch")
        label, target = (FEATURE_2, WORKSHOP) if page == EXPLORE else (FEATURE_1, EXPLORE)
        other.button(label, key="av_switch_feature", on_click=navigate,
                     args=(target,), width="stretch")


def run():
    css = text("site.css").replace("__SITE_BACKGROUND__", data_url("site-background.webp", "image/webp"))
    st.html(f"<style>{css}</style>")

    page = st.session_state.get("_av_page", HOME)
    if page == HOME:
        from . import home

        home.show()
        return

    _navigation(page)
    if page in (WORKSHOP, DRIVE):
        from . import workshop

        workshop.show(page)
    else:
        from . import explorer

        explorer.show()
