import streamlit as st
from utils import load_data

st.set_page_config(page_title="Líderes | NBA Stats App", layout="wide")
_, _, boxscores, _, _ = load_data()

st.title("🏆 Líderes Estadísticos")

metricas = [m for m in ["PTS","REB","AST","STL","BLK"] if m in boxscores.columns]
if not metricas:
    st.info("No hay métricas disponibles para mostrar.")
else:
    leaders = (
        boxscores.groupby("PLAYER_NAME")[metricas]
        .mean()
        .reset_index()
        .sort_values(by=metricas, ascending=False)
    )
    st.dataframe(leaders)

