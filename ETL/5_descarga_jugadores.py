import os
import time
import pandas as pd
from nba_api.stats.endpoints import commonplayerinfo
from requests.exceptions import RequestException

# ---- Configuración ----
DATA_DIR = "datos"
os.makedirs(DATA_DIR, exist_ok=True)

BOX_FILE = os.path.join(DATA_DIR, "boxscores.csv")  # entrada
OUTPUT_FILE = os.path.join(DATA_DIR, "jugadores.csv")  # salida
ERRORS_FILE = os.path.join(DATA_DIR, "errores_jugadores.csv")

SLEEP_TIME = 0.6
MAX_RETRIES = 3
FECHA_REFERENCIA = pd.Timestamp("2024-02-01")

# ---- Funciones auxiliares ----
def calcular_edad_desde_fecha(fecha_str, referencia=FECHA_REFERENCIA):
    """Devuelve edad en años a una fecha de referencia fija."""
    try:
        fecha = pd.to_datetime(fecha_str, errors="coerce")
        if pd.isna(fecha):
            return None
        edad = referencia.year - fecha.year - ((referencia.month, referencia.day) < (fecha.month, fecha.day))
        return int(edad)
    except Exception:
        return None


def obtener_columna_fecha(df):
    for col in df.columns:
        if "BIRTH" in col.upper():
            return col
    return None


def safe_get(df, colname):
    return df.loc[0, colname] if colname in df.columns else None


# ---- Leer boxscores ----
if not os.path.exists(BOX_FILE):
    raise SystemExit(f"No se encontró {BOX_FILE}.")

box_df = pd.read_csv(BOX_FILE, dtype={"PLAYER_ID": str})

# Verificamos columnas clave
if "PLAYER_ID" not in box_df.columns:
    raise SystemExit("❌ No se encontró la columna PLAYER_ID en boxscores.csv")

# obtener el equipo más reciente (usando orden de aparición si no hay fechas)
last_info = (
    box_df.drop_duplicates(subset=["PLAYER_ID"], keep="last")[["PLAYER_ID", "TEAM_ABBREVIATION"]]
    if "TEAM_ABBREVIATION" in box_df.columns
    else pd.DataFrame(columns=["PLAYER_ID", "TEAM_ABBREVIATION"])
)

player_ids = box_df["PLAYER_ID"].dropna().unique().tolist()
print(f"🔎 Encontrados {len(player_ids)} PLAYER_ID únicos en boxscores")

# ---- Reanudar descarga si existe jugadores.csv ----
if os.path.exists(OUTPUT_FILE):
    jugadores_df = pd.read_csv(OUTPUT_FILE, dtype={"PLAYER_ID": str})
    descargados_ids = set(jugadores_df["PLAYER_ID"].astype(str))
    print(f"🔁 Reanudando: {len(descargados_ids)} jugadores ya descargados.")
else:
    jugadores_df = pd.DataFrame()
    descargados_ids = set()

errores = []
remaining_ids = [pid for pid in player_ids if str(pid) not in descargados_ids]
print(f"📥 Descargando info para {len(remaining_ids)} jugadores restantes...")

# ---- Descargar info de jugadores ----
for idx, pid in enumerate(remaining_ids, start=1):
    pid_str = str(pid)
    for intento in range(1, MAX_RETRIES + 1):
        try:
            print(f"[{idx}/{len(remaining_ids)}] PLAYER_ID={pid_str}")
            info = commonplayerinfo.CommonPlayerInfo(player_id=pid_str)
            df_info = info.get_data_frames()[0]

            row = {"PLAYER_ID": pid_str}
            row["FIRST_NAME"] = safe_get(df_info, "FIRST_NAME")
            row["LAST_NAME"] = safe_get(df_info, "LAST_NAME")
            row["POSITION"] = safe_get(df_info, "POSITION")
            row["HEIGHT"] = safe_get(df_info, "HEIGHT")
            row["WEIGHT"] = safe_get(df_info, "WEIGHT")

            # equipo más reciente
            hist = last_info[last_info["PLAYER_ID"] == pid_str]
            row["TEAM_ABBREVIATION"] = hist["TEAM_ABBREVIATION"].values[0] if not hist.empty else safe_get(df_info, "TEAM_ABBREVIATION")

            # fecha de nacimiento y edad al 1 de febrero de 2024
            birth_col = obtener_columna_fecha(df_info)
            birth_val = safe_get(df_info, birth_col) if birth_col else None
            row["AGE"] = calcular_edad_desde_fecha(birth_val)

            # guardar al CSV directamente
            new_df = pd.DataFrame([row])
            new_df.to_csv(OUTPUT_FILE, mode="a", header=not os.path.exists(OUTPUT_FILE), index=False)

            descargados_ids.add(pid_str)
            time.sleep(SLEEP_TIME)
            break

        except RequestException as e:
            print(f"⚠️ Error de conexión {pid_str}: {e}")
            if intento < MAX_RETRIES:
                print("   Reintentando en 60s...")
                time.sleep(60)
            else:
                errores.append((pid_str, f"RequestException: {e}"))
        except Exception as e:
            print(f"❌ Error procesando {pid_str}: {e}")
            errores.append((pid_str, str(e)))
            break

# ---- Guardar errores ----
if errores:
    pd.DataFrame(errores, columns=["PLAYER_ID", "ERROR"]).to_csv(ERRORS_FILE, index=False)
    print(f"⚠️ Se guardaron {len(errores)} errores en {ERRORS_FILE}")

print(f"\n✅ Descarga finalizada. Total jugadores: {len(descargados_ids)} guardados en {OUTPUT_FILE}")

