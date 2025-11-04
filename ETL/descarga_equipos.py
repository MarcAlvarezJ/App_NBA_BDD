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

# ==============================from nba_api.stats.static import teams
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

# GUARDAR CSV
# ==============================
teams_df.to_csv(OUTPUT_FILE, index=False)
print(f"✅ Equipos guardados en: {OUTPUT_FILE}")
print(teams_df.head())
