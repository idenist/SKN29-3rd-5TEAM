import textwrap

import streamlit as st


def render_html(markup):
    """Render multiline HTML without Markdown treating indentation as code."""
    normalized = "\n".join(
        line.strip()
        for line in textwrap.dedent(markup).splitlines()
        if line.strip()
    )
    st.markdown(normalized, unsafe_allow_html=True)
