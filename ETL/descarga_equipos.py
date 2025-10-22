from nba_api.stats.static import teams
import pandas as pd
import os

# ==============================
# CONFIGURACIÓN
# ==============================
DATA_DIR = "./datos"
os.makedirs(DATA_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(DATA_DIR, "equipos.csv")

# ==============================
# DESCARGAR EQUIPOS NBA
# ==============================
nba_teams = teams.get_teams()  # lista de diccionarios con la info de cada equipo
teams_df = pd.DataFrame(nba_teams)

# Seleccionamos columnas clave
teams_df = teams_df[["abbreviation", "full_name"]]
teams_df.columns = ["TEAM_ABBREVIATION", "TEAM_NAME"]

# ==============================
# GUARDAR CSV
# ==============================
teams_df.to_csv(OUTPUT_FILE, index=False)
print(f"✅ Equipos guardados en: {OUTPUT_FILE}")
print(teams_df.head())
