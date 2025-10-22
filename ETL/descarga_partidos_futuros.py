# descarga_partidos_futuros.py
from nba_api.stats.endpoints import leaguegamefinder
import pandas as pd

# --------------------------
# Configuración
# --------------------------
SEASON = "2023-24"
SEASON_TYPE = "Regular Season"
FECHA_LIMITE = "2024-01-31"

# Lista de equipos NBA
equipos_nba = [
    "ATL","BOS","BKN","CHA","CHI","CLE","DAL","DEN","DET","GSW",
    "HOU","IND","LAC","LAL","MEM","MIA","MIL","MIN","NOP","NYK",
    "OKC","ORL","PHI","PHX","POR","SAC","SAS","TOR","UTA","WAS"
]

# --------------------------
# 1. Descargar partidos
# --------------------------
gamefinder = leaguegamefinder.LeagueGameFinder(
    season_nullable=SEASON,
    season_type_nullable=SEASON_TYPE
)
games_df = gamefinder.get_data_frames()[0]

# Convertir fechas
games_df["GAME_DATE"] = pd.to_datetime(games_df["GAME_DATE"])

# Filtrar solo NBA y MATCHUP no vacío
games_df = games_df.dropna(subset=["MATCHUP", "TEAM_ABBREVIATION"])
games_df = games_df[
    (games_df["TEAM_ABBREVIATION"].isin(equipos_nba)) &
    (games_df["MATCHUP"].str.strip() != "")
]

# Filtrar partidos posteriores a la fecha límite
fecha_limite = pd.to_datetime(FECHA_LIMITE)
games_df = games_df[games_df["GAME_DATE"] > fecha_limite]

# --------------------------
# 2. Unificar LOCAL y VISITANTE
# --------------------------
partidos = []

for game_id, group in games_df.groupby("GAME_ID"):
    visitante_rows = group[group["MATCHUP"].str.contains(" @ ", na=False)]
    
    if len(visitante_rows) == 0 or len(group) < 2:
        fecha = pd.to_datetime(group.iloc[0]["GAME_DATE"])
        partidos.append({
            "GAME_ID": game_id,
            "FECHA": fecha,
            "LOCAL": None,
            "VISITANTE": None
        })
        continue
    
    row_visitante = visitante_rows.iloc[0]
    row_local = group[group["TEAM_ABBREVIATION"] != row_visitante["TEAM_ABBREVIATION"]].iloc[0]

    fecha = pd.to_datetime(row_visitante["GAME_DATE"])
    visitante = row_visitante["TEAM_ABBREVIATION"]
    local = row_local["TEAM_ABBREVIATION"]

    partidos.append({
        "GAME_ID": game_id,
        "FECHA": fecha,
        "LOCAL": local,
        "VISITANTE": visitante
    })

# --------------------------
# 3. Crear DataFrame y guardar CSV
# --------------------------
partidos_futuros_df = pd.DataFrame(partidos)
partidos_futuros_df = partidos_futuros_df.sort_values("FECHA")
partidos_futuros_df.to_csv("./datos/partidos_futuros.csv", index=False, encoding="utf-8-sig")

print(f"✅ partidos_futuros.csv guardado con {len(partidos_futuros_df)} partidos posteriores a {FECHA_LIMITE}")
print(partidos_futuros_df.head())
