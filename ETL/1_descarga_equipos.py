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
nba_teams = teams.get_teams()
teams_df = pd.DataFrame(nba_teams)

# Seleccionamos columnas clave
teams_df = teams_df[["id", "abbreviation", "full_name"]]
teams_df.columns = ["TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME"]

# ==============================
# AGREGAR CONFERENCIA Y DIVISIÓN
# ==============================
# Mapeo de equipos a conferencia y división (información estable)
conferencia_map = {
    # Eastern Conference
    "ATL": {"CONFERENCE": "East", "DIVISION": "Southeast"},
    "BOS": {"CONFERENCE": "East", "DIVISION": "Atlantic"},
    "BKN": {"CONFERENCE": "East", "DIVISION": "Atlantic"},
    "CHA": {"CONFERENCE": "East", "DIVISION": "Southeast"},
    "CHI": {"CONFERENCE": "East", "DIVISION": "Central"},
    "CLE": {"CONFERENCE": "East", "DIVISION": "Central"},
    "DET": {"CONFERENCE": "East", "DIVISION": "Central"},
    "IND": {"CONFERENCE": "East", "DIVISION": "Central"},
    "MIA": {"CONFERENCE": "East", "DIVISION": "Southeast"},
    "MIL": {"CONFERENCE": "East", "DIVISION": "Central"},
    "NYK": {"CONFERENCE": "East", "DIVISION": "Atlantic"},
    "ORL": {"CONFERENCE": "East", "DIVISION": "Southeast"},
    "PHI": {"CONFERENCE": "East", "DIVISION": "Atlantic"},
    "TOR": {"CONFERENCE": "East", "DIVISION": "Atlantic"},
    "WAS": {"CONFERENCE": "East", "DIVISION": "Southeast"},
    # Western Conference
    "DAL": {"CONFERENCE": "West", "DIVISION": "Southwest"},
    "DEN": {"CONFERENCE": "West", "DIVISION": "Northwest"},
    "GSW": {"CONFERENCE": "West", "DIVISION": "Pacific"},
    "HOU": {"CONFERENCE": "West", "DIVISION": "Southwest"},
    "LAC": {"CONFERENCE": "West", "DIVISION": "Pacific"},
    "LAL": {"CONFERENCE": "West", "DIVISION": "Pacific"},
    "MEM": {"CONFERENCE": "West", "DIVISION": "Southwest"},
    "MIN": {"CONFERENCE": "West", "DIVISION": "Northwest"},
    "NOP": {"CONFERENCE": "West", "DIVISION": "Southwest"},
    "OKC": {"CONFERENCE": "West", "DIVISION": "Northwest"},
    "PHX": {"CONFERENCE": "West", "DIVISION": "Pacific"},
    "POR": {"CONFERENCE": "West", "DIVISION": "Northwest"},
    "SAC": {"CONFERENCE": "West", "DIVISION": "Pacific"},
    "SAS": {"CONFERENCE": "West", "DIVISION": "Southwest"},
    "UTA": {"CONFERENCE": "West", "DIVISION": "Northwest"},
}

# Aplicar mapeo
teams_df["CONFERENCE"] = teams_df["TEAM_ABBREVIATION"].map(
    lambda x: conferencia_map.get(x, {}).get("CONFERENCE", "")
)
teams_df["DIVISION"] = teams_df["TEAM_ABBREVIATION"].map(
    lambda x: conferencia_map.get(x, {}).get("DIVISION", "")
)

# ==============================
# AGREGAR URL DEL LOGO NBA
# ==============================
teams_df["LOGO_URL"] = teams_df["TEAM_ID"].apply(
    lambda tid: f"https://cdn.nba.com/logos/nba/{tid}/primary/L/logo.svg"
)

teams_df.drop(columns=["TEAM_ID"], inplace=True)

# ==============================
# GUARDAR CSV
# ==============================
teams_df.to_csv(OUTPUT_FILE, index=False)
print(f"✅ Equipos guardados en: {OUTPUT_FILE}")
print(teams_df.head())

