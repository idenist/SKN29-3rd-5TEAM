import base64
from pathlib import Path

import streamlit as st


LOADING_IMAGE_PATH = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "policy_loading.png"
)


@st.cache_data(show_spinner=False)
def _loading_image_data_uri():
    image_bytes = LOADING_IMAGE_PATH.read_bytes()
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def show_policy_loading(container=None):
    target = container or st
    image_uri = _loading_image_data_uri()
    target.markdown(
        f"""
        <div class="policy-loading-overlay">
            <div class="policy-loading-panel">
                <img src="{image_uri}" alt="백구가 맞춤 정책을 찾고 있어요." />
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
