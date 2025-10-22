# descargar_jugadores_robusto.py
import os
import time
import pandas as pd
from nba_api.stats.endpoints import commonplayerinfo
from requests.exceptions import RequestException
from datetime import datetime

# ---- Configuración ----
DATA_DIR = "datos"
os.makedirs(DATA_DIR, exist_ok=True)

BOX_FILE = os.path.join(DATA_DIR, "boxscores.csv")  # entrada: boxscores con PLAYER_ID
OUTPUT_FILE = os.path.join(DATA_DIR, "jugadores.csv")        # salida final
CHECKPOINT_FILE = os.path.join(DATA_DIR, "jugadores_parcial.csv")
ERRORS_FILE = os.path.join(DATA_DIR, "errores_jugadores.csv")

SLEEP_TIME = 0.6     # pausa entre requests
SAVE_INTERVAL = 50   # guardar cada N jugadores
MAX_RETRIES = 3

# ---- Funciones utilitarias ----
def calcular_edad_desde_fecha(fecha_str):
    """Intenta parsear fecha_str con pandas y devuelve años completos (int)."""
    try:
        fecha = pd.to_datetime(fecha_str, errors="coerce")
        if pd.isna(fecha):
            return None
        hoy = pd.Timestamp.now()
        edad = hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))
        return int(edad)
    except Exception:
        return None

def obtener_columna_fecha(df):
    """Devuelve el nombre de la columna que probablemente contiene la fecha de nacimiento,
       buscando cualquier columna que tenga 'BIRTH' en su nombre (case-insensitive)."""
    for col in df.columns:
        if "BIRTH" in col.upper():
            return col
    return None

# ---- Leer jugadores únicos desde el boxscore ----
if not os.path.exists(BOX_FILE):
    raise SystemExit(f"No se encontró {BOX_FILE}. Generá primero boxscores_filtrados.csv en {DATA_DIR}.")

box_df = pd.read_csv(BOX_FILE, dtype={"PLAYER_ID": str})
player_ids = box_df["PLAYER_ID"].dropna().unique().tolist()
print(f"🔎 Encontrados {len(player_ids)} PLAYER_ID únicos en {BOX_FILE}")

# ---- Cargar checkpoint si existe ----
if os.path.exists(CHECKPOINT_FILE):
    descargados_df = pd.read_csv(CHECKPOINT_FILE, dtype={"PLAYER_ID": str})
    descargados_ids = set(descargados_df["PLAYER_ID"].astype(str).tolist())
    players_data = descargados_df.to_dict("records")
    print(f"🔁 Reanudando desde checkpoint: {len(descargados_ids)} jugadores ya descargados.")
else:
    descargados_ids = set()
    players_data = []

errores = []

# ---- Descargar info de cada jugador ----
remaining_ids = [pid for pid in player_ids if str(pid) not in descargados_ids]
total = len(remaining_ids)
print(f"📥 Descargando info para {total} jugadores restantes...")

for idx, pid in enumerate(remaining_ids, start=1):
    pid_str = str(pid)
    success = False

    for intento in range(1, MAX_RETRIES + 1):
        try:
            print(f"[{idx}/{total}] PLAYER_ID={pid_str} (intento {intento})")
            info = commonplayerinfo.CommonPlayerInfo(player_id=pid_str)
            df_info = info.get_data_frames()[0]  # frame con una fila con datos generales

            # --- Extraer campos con robustez ---
            # columnas que queremos: PLAYER_ID, FIRST_NAME, LAST_NAME, POSITION, HEIGHT, WEIGHT, TEAM_ID, TEAM_ABBREVIATION, AGE
            row = {}
            # PLAYER_ID
            row["PLAYER_ID"] = pid_str

            def safe_get(colname):
                return df_info.loc[0, colname] if colname in df_info.columns else None

            row["FIRST_NAME"] = safe_get("FIRST_NAME")
            row["LAST_NAME"] = safe_get("LAST_NAME")
            row["POSITION"] = safe_get("POSITION")
            row["HEIGHT"] = safe_get("HEIGHT")
            row["WEIGHT"] = safe_get("WEIGHT")
            # Team actual del jugador (puede ser 0 o None si agente libre)
            row["TEAM_ID"] = safe_get("TEAM_ID")
            row["TEAM_ABBREVIATION"] = safe_get("TEAM_ABBREVIATION")

            # AGE: preferimos columna AGE si existe y no es nula
            age_val = safe_get("AGE")
            if pd.notna(age_val) and age_val not in ("", None):
                try:
                    row["AGE"] = int(age_val)
                except Exception:
                    # si AGE viene como '26' o '26.0' o string, intentar convertir
                    try:
                        row["AGE"] = int(float(age_val))
                    except Exception:
                        row["AGE"] = None
            else:
                # intentar calcular desde columna de nacimiento si existe
                fecha_col = obtener_columna_fecha(df_info)
                if fecha_col:
                    birth_val = safe_get(fecha_col)
                    edad_calc = calcular_edad_desde_fecha(birth_val)
                    row["AGE"] = edad_calc
                else:
                    row["AGE"] = None

            players_data.append(row)
            descargados_ids.add(pid_str)
            success = True
            time.sleep(SLEEP_TIME)
            break

        except RequestException as e:
            print(f"⚠️ Error de conexión para PLAYER_ID={pid_str}: {e}")
            if intento < MAX_RETRIES:
                espera = 60
                print(f"   Esperando {espera}s antes de reintentar...")
                time.sleep(espera)
            else:
                errores.append((pid_str, f"RequestException: {e}"))
        except Exception as e:
            print(f"❌ Error procesando PLAYER_ID={pid_str}: {e}")
            errores.append((pid_str, str(e)))
            break

    # Guardado periódico (checkpoint)
    if len(players_data) % SAVE_INTERVAL == 0:
        parcial_df = pd.DataFrame(players_data)
        parcial_df.to_csv(CHECKPOINT_FILE, index=False)
        print(f"💾 Checkpoint guardado: {CHECKPOINT_FILE} ({len(players_data)} jugadores)")

# ---- Guardado final ----
if players_data:
    final_df = pd.DataFrame(players_data)
    final_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ Jugadores guardados en: {OUTPUT_FILE} (total {len(final_df)})")
