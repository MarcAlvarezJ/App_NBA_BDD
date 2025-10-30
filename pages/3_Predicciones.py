import streamlit as st
from utils import load_data

st.set_page_config(page_title="Predicciones | NBA Stats App", layout="wide")

_, partidos_futuros, _, _, _ = load_data()

st.title("🔮 Predicciones")
st.write("Aquí se mostrarán los modelos y predicciones futuras.")

if not partidos_futuros.empty:
	st.subheader("Partidos futuros")
	st.dataframe(partidos_futuros)


