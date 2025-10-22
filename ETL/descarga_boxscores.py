import pandas as pd
import time
import os
from nba_api.stats.endpoints import boxscoretraditionalv2, boxscorescoringv2
from requests.exceptions import RequestException

# ==============================
# CONFIGURACIÓN
# ==============================
DATA_DIR = "./datos"
os.makedirs(DATA_DIR, exist_ok=True)

PARTIDOS_CSV = os.path.join(DATA_DIR, "partido.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "boxscores.csv")
CHECKPOINT_FILE = os.path.join(DATA_DIR, "boxscores.csv")
ERRORS_FILE = os.path.join(DATA_DIR, "errores_boxscores.csv")

MAX_RETRIES = 3
SAVE_INTERVAL = 50  # cada 50 partidos se guarda el progreso
SLEEP_TIME = 0.6

# ==============================
# CARGAR PARTIDOS FILTRADOS
# ==============================
partidos_df = pd.read_csv(PARTIDOS_CSV, dtype={"GAME_ID": str})
game_ids = partidos_df["GAME_ID"].unique().tolist()
print(f"📅 Se cargarán {len(game_ids)} partidos desde {PARTIDOS_CSV}")

# ==============================
# CARGAR PROGRESO (si existe)
# ==============================
if os.path.exists(CHECKPOINT_FILE):
    box_parcial = pd.read_csv(CHECKPOINT_FILE, dtype={"GAME_ID": str})
    descargados = set(box_parcial["GAME_ID"].unique())
    print(f"🔁 Reanudando desde {CHECKPOINT_FILE} ({len(descargados)} partidos ya descargados)")
else:
    box_parcial = pd.DataFrame()
    descargados = set()

# ==============================
# DESCARGA DE BOXSCORES
# ==============================
all_data = [box_parcial] if not box_parcial.empty else []
errores = []
contador = len(descargados)

for i, game_id in enumerate(game_ids, 1):
    if game_id in descargados:
        print(f"⏩ Partido {game_id} ya descargado, se salta.")
        continue

    success = False

    for intento in range(1, MAX_RETRIES + 1):
        try:
            print(f"Descargando boxscore {i}/{len(game_ids)}: {game_id} (intento {intento})")

            # --- Estadísticas tradicionales
            trad = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id).get_data_frames()[0]

            # --- Estadísticas de tiro
            scoring = boxscorescoringv2.BoxScoreScoringV2(game_id=game_id).get_data_frames()[0]

            # --- Merge
            merged = trad.merge(scoring, on=["GAME_ID", "TEAM_ID", "PLAYER_ID"], suffixes=("", "_scoring"))

            # --- Filtrar columnas relevantes
            cols = [
                "GAME_ID", "TEAM_ABBREVIATION", "PLAYER_ID", "PLAYER_NAME", "MIN", "PTS",
                "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "REB", "AST", "STL", "BLK", "TO", "PF"
            ]
            merged = merged[cols]

            # --- Eliminar jugadores sin minutos
            merged = merged[merged["MIN"].notna()]
            merged = merged[merged["MIN"] != "0:00"]

            all_data.append(merged)
            contador += 1
            success = True
            descargados.add(game_id)

            time.sleep(SLEEP_TIME)
            break  # sale del bucle de reintentos si tuvo éxito

        except RequestException as e:
            print(f"⚠️ Error de conexión en {game_id}: {e}. Reintentando...")
            time.sleep(2)
        except Exception as e:
            print(f"❌ Error procesando {game_id}: {e}")
            errores.append((game_id, str(e)))
            break  # no reintentar errores lógicos (ej. sin datos)

    if not success:
        errores.append((game_id, "No se pudo descargar tras múltiples intentos."))

    # --- Guardado periódico
    if contador % SAVE_INTERVAL == 0 and all_data:
        parcial_df = pd.concat(all_data, ignore_index=True)
        parcial_df.to_csv(CHECKPOINT_FILE, index=False)
        print(f"💾 Progreso guardado ({contador} partidos) en {CHECKPOINT_FILE}")

# ==============================
# GUARDADO FINAL
# ==============================
if all_data:
    final_df = pd.concat(all_data, ignore_index=True)

    # --- Convertir "MM:SS" → minutos decimales ---
    def convert_minutes(min_value):
        # Si ya es numérico (float o int), no tocar
        if isinstance(min_value, (int, float)):
            return min_value

        # Si está vacío o es "0" o "00:00"
        if pd.isna(min_value) or str(min_value) in ["0", "00:00"]:
            return 0.0

        try:
            mins, secs = map(int, str(min_value).split(":"))
            return mins + secs / 60
        except Exception:
            return 0.0

    final_df["MIN"] = final_df["MIN"].apply(convert_minutes)

    # --- Renombrar columna TO → TOV ---
    if "TO" in final_df.columns:
        final_df.rename(columns={"TO": "TOV"}, inplace=True)

    # --- Convertir todas las columnas numéricas a enteros donde sea posible ---
    numeric_cols = final_df.select_dtypes(include=["float", "int"]).columns
    for col in numeric_cols:
        if col not in ["GAME_ID", "PLAYER_ID"]:
            if (final_df[col].dropna() % 1 == 0).all():
                final_df[col] = final_df[col].astype("Int64")

    final_df = final_df.drop_duplicates(subset=["GAME_ID", "PLAYER_ID"])
    final_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ Boxscores guardados en '{OUTPUT_FILE}' con {len(final_df)} registros.")
else:
    print("\n❌ No se descargaron datos correctamente.")

# Guardar errores si hubo
if errores:
    pd.DataFrame(errores, columns=["GAME_ID", "ERROR"]).to_csv(ERRORS_FILE, index=False)
    print(f"⚠️ Se guardaron {len(errores)} errores en '{ERRORS_FILE}'")
