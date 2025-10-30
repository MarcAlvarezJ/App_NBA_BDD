import streamlit as st
import pandas as pd
from supabase import create_client, Client

# Conexión Supabase compartida
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_all(table_name: str, batch_size: int = 1000) -> pd.DataFrame:
	all_rows = []
	start = 0
	while True:
		batch = (
			supabase.table(table_name)
			.select("*")
			.range(start, start + batch_size - 1)
			.execute()
			.data
		)
		if not batch:
			break
		all_rows.extend(batch)
		start += batch_size
	return pd.DataFrame(all_rows)


@st.cache_data
def load_data():
	partidos = fetch_all("partidos")
	partidos_futuros = fetch_all("partidos_futuros")
	boxscores = fetch_all("boxscores")
	equipos = fetch_all("equipos")
	jugadores = fetch_all("jugadores")

	# Crear columna PLAYER_NAME si hace falta
	if "FIRST_NAME" in jugadores.columns and "LAST_NAME" in jugadores.columns:
		jugadores["PLAYER_NAME"] = (
			jugadores["FIRST_NAME"].astype(str) + " " + jugadores["LAST_NAME"].astype(str)
		)
	elif "PLAYER_NAME" not in jugadores.columns:
		jugadores["PLAYER_NAME"] = ""

	return partidos, partidos_futuros, boxscores, equipos, jugadores


