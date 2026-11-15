import streamlit as st

from firewatch_bi.dashboard import main

st.set_page_config(
    page_title="FireWatch | Active-Fire Intelligence",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

if __name__ == "__main__":
    main()
