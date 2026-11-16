from pathlib import Path

import streamlit as st

from firewatch_bi.dashboard import main

st.set_page_config(
    page_title="FireWatch | Active-Fire Intelligence",
    page_icon=str(Path(__file__).with_name("fire.webp")),
    layout="wide",
    initial_sidebar_state="expanded",
)

if __name__ == "__main__":
    main()
