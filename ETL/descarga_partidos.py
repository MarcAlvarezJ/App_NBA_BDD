# descarga_partido_filtrado.py
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

# Filtrar por fecha
fecha_limite = pd.to_datetime(FECHA_LIMITE)
games_df = games_df[games_df["GAME_DATE"] <= fecha_limite]

# --------------------------
# 2. Unificar LOCAL y VISITANTE
# --------------------------
partidos = []

for game_id, group in games_df.groupby("GAME_ID"):
    # Buscar visitante (fila con "@")
    visitante_rows = group[group["MATCHUP"].str.contains(" @ ", na=False)]
    
    if len(visitante_rows) == 0 or len(group) < 2:
        # Partidos incompletos
        fecha = pd.to_datetime(group.iloc[0]["GAME_DATE"])
        partidos.append({
            "GAME_ID": game_id,
            "FECHA": fecha,
            "LOCAL": None,
            "VISITANTE": None,
            "PTS_LOCAL": None,
            "PTS_VISITANTE": None
        })
        continue
    
    # Asignar visitante y local
    row_visitante = visitante_rows.iloc[0]
    row_local = group[group["TEAM_ABBREVIATION"] != row_visitante["TEAM_ABBREVIATION"]].iloc[0]

    fecha = pd.to_datetime(row_visitante["GAME_DATE"])
    visitante = row_visitante["TEAM_ABBREVIATION"]
    pts_visitante = row_visitante["PTS"]
    local = row_local["TEAM_ABBREVIATION"]
    pts_local = row_local["PTS"]

    partidos.append({
        "GAME_ID": game_id,
        "FECHA": fecha,
        "LOCAL": local,
        "VISITANTE": visitante,
        "PTS_LOCAL": pts_local,
        "PTS_VISITANTE": pts_visitante
    })

# --------------------------
# 3. Crear DataFrame y guardar CSV
# --------------------------
partidos_df = pd.DataFrame(partidos)
partidos_df = partidos_df.sort_values("FECHA")
partidos_df.to_csv("./datos/partido.csv", index=False, encoding="utf-8-sig")
print(f"✅ partido.csv guardado con {len(partidos_df)} partidos hasta {FECHA_LIMITE}")