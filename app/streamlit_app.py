"""FireWatch Intelligence Assistant: starter. Neha extends the intent catalogue (8+ approved SQL templates)."""
import streamlit as st

st.set_page_config(page_title="FireWatch", layout="wide")
st.title("FireWatch Intelligence Assistant")
st.caption("Active fire detections (thermal anomalies), not confirmed wildfires. Monitoring and analytics only.")
st.info("Starter page. Connect BigQuery (read-only service account) and add the intent catalogue.")
