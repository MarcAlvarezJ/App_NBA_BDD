import streamlit as st
from utils import load_data

st.set_page_config(page_title="Partidos | NBA Stats App", layout="wide")

partidos, _, _, _, _ = load_data()

st.title("📅 Partidos")
st.dataframe(partidos)


