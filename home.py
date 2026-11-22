"""Homepage and widescreen/portrait opening film."""
import streamlit as st

from . import EXPLORE, FEATURE_1, FEATURE_2, WORKSHOP, navigate
from .asset_files import data_url, text

POSTERS = ("first.webp", "final.webp", "first-tall.webp", "final-tall.webp")


def _styles():
    css = text("opening/opening.css")
    for name in POSTERS:
        css = css.replace(f"__{name}__", data_url("opening/" + name, "image/webp"))
    return css


def _player():
    html = text("opening/opening.html")
    for name in ("wide.mp4", "tall.mp4"):
        html = html.replace(f"__{name}__", data_url("opening/" + name, "video/mp4"))
    return html + "<script>\n" + text("opening/player.js") + "</script>"


def show():
    with st.container(key="av_home"):
        st.html(f"<style>{_styles()}</style>")
        if st.session_state.get("_av_home_visited"):
            st.html(text("opening/finished.html"))
        else:
            st.html(_player(), unsafe_allow_javascript=True)

        with st.container(key="av_home_choices"):
            explore, workshop = st.columns(2, gap="medium")
            explore.button(FEATURE_1, key="av_enter_explore", on_click=navigate,
                           args=(EXPLORE,), width="stretch")
            workshop.button(FEATURE_2, key="av_enter_workshop", on_click=navigate,
                            args=(WORKSHOP,), width="stretch")
