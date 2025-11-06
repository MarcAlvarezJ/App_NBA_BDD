import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# Conexión Supabase compartida
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# Cliente base anónimo (para acceso sin autenticación)
supabase_anon: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ==============================================================
# 🕐 FUNCIONES DE FORMATO DE MINUTOS
# ==============================================================

def minutos_decimal_a_mmss(minutos_decimal: float) -> str:
	"""
	Convierte minutos decimales (ej: 25.5) a formato mm:ss (ej: "25:30").
	
	Args:
		minutos_decimal: Minutos en formato decimal
		
	Returns:
		str: Formato mm:ss
	"""
	if minutos_decimal is None or pd.isna(minutos_decimal):
		return "0:00"
	
	try:
		minutos_decimal = float(minutos_decimal)
		minutos = int(minutos_decimal)
		segundos = int((minutos_decimal - minutos) * 60)
		return f"{minutos}:{segundos:02d}"
	except (ValueError, TypeError):
		return "0:00"


def mmss_a_minutos_decimal(mmss: str) -> float:
	"""
	Convierte formato mm:ss (ej: "25:30") a minutos decimales (ej: 25.5).
	
	Args:
		mmss: String en formato mm:ss o mm:ss
		
	Returns:
		float: Minutos en formato decimal
	"""
	if not mmss or mmss == "":
		return 0.0
	
	# Si ya es un número, retornarlo
	try:
		return float(mmss)
	except (ValueError, TypeError):
		pass
	
	# Intentar parsear formato mm:ss
	try:
		if ":" in str(mmss):
			parts = str(mmss).split(":")
			minutos = int(parts[0])
			segundos = int(parts[1]) if len(parts) > 1 else 0
			return minutos + segundos / 60.0
	except (ValueError, TypeError, IndexError):
		pass
	
	return 0.0


def get_supabase_client() -> Client:
	"""
	Obtiene el cliente de Supabase apropiado:
	- Si hay un token de autenticación, usa el cliente autenticado guardado
	- Si no, usa el cliente anónimo (respeta RLS automáticamente)
	"""
	init_session_state()
	
	# Si hay un cliente autenticado guardado, usarlo
	if "supabase_client_auth" in st.session_state and st.session_state.supabase_client_auth:
		return st.session_state.supabase_client_auth
	
	# Si no hay token, usar cliente anónimo (RLS se aplicará automáticamente)
	return supabase_anon


def fetch_all(table_name: str, batch_size: int = 1000) -> pd.DataFrame:
	"""
	Obtiene todos los registros de una tabla.
	Respeta las políticas RLS de Supabase:
	- Si el usuario está autenticado, aplica políticas para usuarios autenticados
	- Si es anónimo, aplica políticas para usuarios anónimos
	"""
	client = get_supabase_client()
	all_rows = []
	start = 0
	while True:
		try:
			batch = (
				client.table(table_name)
				.select("*")
				.range(start, start + batch_size - 1)
				.execute()
				.data
			)
			if not batch:
				break
			all_rows.extend(batch)
			start += batch_size
		except Exception as e:
			# Si hay error, probablemente por RLS o permisos
			st.warning(f"⚠️ Error al acceder a {table_name}: {str(e)}")
			break
	return pd.DataFrame(all_rows)


def get_cache_key() -> str:
	"""
	Genera una clave única para el cache basada en el estado de autenticación.
	Esto permite tener caches separados para usuarios anónimos y autenticados.
	"""
	init_session_state()
	if check_auth():
		user = get_current_user()
		if user:
			return f"auth_{user.id}"
	return "anon"


@st.cache_data(ttl=300)  # Cache por 5 minutos (300 segundos)
def _load_data_cached(cache_key: str):
	"""
	Función interna que carga los datos con cache.
	El parámetro cache_key asegura que usuarios anónimos y autenticados
	tengan caches separados.
	"""
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


def load_data():
	"""
	Carga los datos desde Supabase con cache inteligente.
	- Cache separado para usuarios anónimos y autenticados
	- TTL de 5 minutos para refresco automático
	- Se invalida automáticamente cuando cambia el estado de autenticación
	"""
	cache_key = get_cache_key()
	return _load_data_cached(cache_key)


def clear_cache():
	"""
	Invalida el cache de datos. Útil después de operaciones CRUD
	para asegurar que los datos mostrados estén actualizados.
	"""
	_load_data_cached.clear()


# ==============================================================
# 🔐 FUNCIONES DE AUTENTICACIÓN
# ==============================================================

def init_session_state():
	"""Inicializa el estado de sesión para autenticación"""
	if "authenticated" not in st.session_state:
		st.session_state.authenticated = False
	if "user" not in st.session_state:
		st.session_state.user = None
	if "access_token" not in st.session_state:
		st.session_state.access_token = None
	if "refresh_token" not in st.session_state:
		st.session_state.refresh_token = None


def check_auth():
	"""Verifica si el usuario está autenticado"""
	init_session_state()
	
	# Verificar si el usuario está autenticado
	if st.session_state.authenticated and st.session_state.access_token:
		# Opcional: verificar el token con Supabase (puede ser costoso)
		# Por ahora, confiamos en el estado de sesión de Streamlit
		# El token se validará automáticamente en las siguientes llamadas a Supabase
		return True
	
	return False


def login(email: str, password: str) -> tuple[bool, str]:
	"""
	Inicia sesión con email y contraseña
	
	Returns:
		tuple: (success: bool, message: str)
	"""
	try:
		# Crear un cliente temporal para el login
		temp_client = create_client(SUPABASE_URL, SUPABASE_KEY)
		response = temp_client.auth.sign_in_with_password({
			"email": email,
			"password": password
		})
		
		if response.user and response.session:
			# Guardar el cliente autenticado en session_state
			# Este cliente ya tiene la sesión configurada automáticamente
			st.session_state.supabase_client_auth = temp_client
			st.session_state.authenticated = True
			st.session_state.user = response.user
			st.session_state.access_token = response.session.access_token
			st.session_state.refresh_token = response.session.refresh_token
			return True, "Inicio de sesión exitoso"
		else:
			return False, "Error al iniciar sesión"
			
	except Exception as e:
		error_msg = str(e)
		# Mensajes de error más amigables
		if "Invalid login credentials" in error_msg or "invalid_credentials" in error_msg.lower():
			return False, "Email o contraseña incorrectos"
		return False, f"Error: {error_msg}"


def logout():
	"""Cierra la sesión del usuario"""
	try:
		# Intentar cerrar sesión con el cliente autenticado si existe
		if "supabase_client_auth" in st.session_state and st.session_state.supabase_client_auth:
			st.session_state.supabase_client_auth.auth.sign_out()
	except Exception:
		pass
	
	# Limpiar estado de autenticación
	st.session_state.authenticated = False
	st.session_state.user = None
	st.session_state.access_token = None
	st.session_state.refresh_token = None
	if "supabase_client_auth" in st.session_state:
		del st.session_state.supabase_client_auth


def get_current_user():
	"""Obtiene el usuario actual autenticado"""
	if check_auth():
		return st.session_state.user
	return None


# ==============================================================
# 📝 FUNCIONES CRUD (SOLO PARA USUARIOS AUTENTICADOS)
# ==============================================================

def insert_jugador(jugador_data: dict) -> tuple[bool, str]:
	"""
	Inserta un nuevo jugador en la tabla jugadores.
	Solo funciona si el usuario está autenticado.
	
	Args:
		jugador_data: Diccionario con los datos del jugador
		
	Returns:
		tuple: (success: bool, message: str)
	"""
	if not check_auth():
		return False, "❌ Debes estar autenticado para realizar esta operación"
	
	try:
		client = get_supabase_client()
		response = client.table("jugadores").insert(jugador_data).execute()
		
		if response.data:
			clear_cache()  # Invalidar cache después de modificar datos
			return True, f"✅ Jugador agregado exitosamente (ID: {response.data[0].get('PLAYER_ID', 'N/A')})"
		else:
			return False, "❌ Error: No se pudo insertar el jugador"
			
	except Exception as e:
		error_msg = str(e)
		if "duplicate" in error_msg.lower() or "unique" in error_msg.lower():
			return False, "❌ Error: Ya existe un jugador con ese PLAYER_ID"
		return False, f"❌ Error al insertar jugador: {error_msg}"


def update_jugador_team(player_id: str, team_abbreviation: str) -> tuple[bool, str]:
	"""
	Actualiza el TEAM_ABBREVIATION de un jugador existente.
	Solo funciona si el usuario está autenticado.
	
	Args:
		player_id: ID del jugador a actualizar
		team_abbreviation: Nueva abreviación del equipo
		
	Returns:
		tuple: (success: bool, message: str)
	"""
	if not check_auth():
		return False, "❌ Debes estar autenticado para realizar esta operación"
	
	try:
		client = get_supabase_client()
		response = (
			client.table("jugadores")
			.update({"TEAM_ABBREVIATION": team_abbreviation})
			.eq("PLAYER_ID", player_id)
			.execute()
		)
		
		if response.data:
			clear_cache()  # Invalidar cache después de modificar datos
			return True, f"✅ Equipo actualizado exitosamente para el jugador {player_id}"
		else:
			return False, f"❌ No se encontró un jugador con PLAYER_ID: {player_id}"
			
	except Exception as e:
		error_msg = str(e)
		return False, f"❌ Error al actualizar jugador: {error_msg}"


def delete_jugador(player_id: str) -> tuple[bool, str]:
	"""
	Elimina un jugador de la tabla jugadores.
	Solo funciona si el usuario está autenticado.
	
	Args:
		player_id: ID del jugador a eliminar
		
	Returns:
		tuple: (success: bool, message: str)
	"""
	if not check_auth():
		return False, "❌ Debes estar autenticado para realizar esta operación"
	
	try:
		client = get_supabase_client()
		response = (
			client.table("jugadores")
			.delete()
			.eq("PLAYER_ID", player_id)
			.execute()
		)
		
		if response.data:
			clear_cache()  # Invalidar cache después de modificar datos
			return True, f"✅ Jugador eliminado exitosamente (ID: {player_id})"
		else:
			return False, f"❌ No se encontró un jugador con PLAYER_ID: {player_id}"
			
	except Exception as e:
		error_msg = str(e)
		return False, f"❌ Error al eliminar jugador: {error_msg}"


def get_jugador_by_id(player_id: str) -> dict:
	"""
	Obtiene un jugador por su PLAYER_ID.
	
	Args:
		player_id: ID del jugador
		
	Returns:
		dict: Datos del jugador o None si no existe
	"""
	try:
		client = get_supabase_client()
		response = (
			client.table("jugadores")
			.select("*")
			.eq("PLAYER_ID", player_id)
			.execute()
		)
		
		if response.data and len(response.data) > 0:
			return response.data[0]
		return None
			
	except Exception as e:
		return None


def get_partido_futuro(game_id: str) -> dict:
	"""
	Obtiene un partido futuro por su GAME_ID.
	
	Args:
		game_id: ID del partido
		
	Returns:
		dict: Datos del partido o None si no existe
	"""
	try:
		client = get_supabase_client()
		response = (
			client.table("partidos_futuros")
			.select("*")
			.eq("GAME_ID", game_id)
			.execute()
		)
		
		if response.data and len(response.data) > 0:
			return response.data[0]
		return None
			
	except Exception as e:
		return None


def get_jugadores_por_equipo(team_abbr: str) -> list:
	"""
	Obtiene todos los jugadores de un equipo.
	
	Args:
		team_abbr: Abreviación del equipo
		
	Returns:
		list: Lista de jugadores del equipo
	"""
	try:
		client = get_supabase_client()
		response = (
			client.table("jugadores")
			.select("*")
			.eq("TEAM_ABBREVIATION", team_abbr)
			.execute()
		)
		
		return response.data if response.data else []
			
	except Exception as e:
		return []


def insert_boxscores(boxscores_data: list) -> tuple[bool, str]:
	"""
	Inserta múltiples registros de boxscore.
	Solo funciona si el usuario está autenticado.
	
	Args:
		boxscores_data: Lista de diccionarios con los datos de boxscore
		
	Returns:
		tuple: (success: bool, message: str)
	"""
	if not check_auth():
		return False, "❌ Debes estar autenticado para realizar esta operación"
	
	try:
		client = get_supabase_client()
		response = client.table("boxscores").insert(boxscores_data).execute()
		
		if response.data:
			clear_cache()  # Invalidar cache después de modificar datos
			return True, f"✅ {len(response.data)} boxscore(s) insertado(s) exitosamente"
		else:
			return False, "❌ Error: No se pudieron insertar los boxscores"
			
	except Exception as e:
		error_msg = str(e)
		if "duplicate" in error_msg.lower() or "unique" in error_msg.lower():
			return False, "❌ Error: Ya existen boxscores para este partido/jugador"
		return False, f"❌ Error al insertar boxscores: {error_msg}"


def crear_partido_jugado(game_id: str, pts_local: int, pts_visitante: int) -> tuple[bool, str]:
	"""
	Crea un partido en la tabla partidos (sin eliminarlo de partidos_futuros).
	Útil para crear el partido antes de insertar boxscores.
	Solo funciona si el usuario está autenticado.
	
	Args:
		game_id: ID del partido
		pts_local: Puntos del equipo local
		pts_visitante: Puntos del equipo visitante
		
	Returns:
		tuple: (success: bool, message: str)
	"""
	if not check_auth():
		return False, "❌ Debes estar autenticado para realizar esta operación"
	
	try:
		client = get_supabase_client()
		
		# Obtener datos del partido futuro
		partido_futuro = get_partido_futuro(game_id)
		if not partido_futuro:
			return False, f"❌ No se encontró el partido futuro con GAME_ID: {game_id}"
		
		# Verificar si el partido ya existe en partidos
		partido_existente = get_partido_jugado(game_id)
		if partido_existente:
			# Ya existe, actualizar puntos
			response_update = (
				client.table("partidos")
				.update({
					"PTS_LOCAL": pts_local,
					"PTS_VISITANTE": pts_visitante
				})
				.eq("GAME_ID", game_id)
				.execute()
			)
			if response_update.data:
				return True, f"✅ Partido {game_id} actualizado exitosamente"
			else:
				return False, "❌ Error al actualizar el partido"
		
		# Crear registro en partidos
		partido_data = {
			"GAME_ID": game_id,
			"FECHA": partido_futuro.get("FECHA"),
			"LOCAL": partido_futuro.get("LOCAL"),
			"VISITANTE": partido_futuro.get("VISITANTE"),
			"PTS_LOCAL": pts_local,
			"PTS_VISITANTE": pts_visitante
		}
		
		# Insertar en partidos
		response_insert = client.table("partidos").insert(partido_data).execute()
		
		if not response_insert.data:
			return False, "❌ Error al insertar el partido en la tabla partidos"
		
		return True, f"✅ Partido {game_id} creado exitosamente en partidos"
			
	except Exception as e:
		error_msg = str(e)
		return False, f"❌ Error al crear partido: {error_msg}"


def mover_partido_futuro_a_jugado(game_id: str, pts_local: int, pts_visitante: int) -> tuple[bool, str]:
	"""
	Mueve un partido de partidos_futuros a partidos y calcula los puntos.
	NOTA: Esta función crea el partido en partidos y luego lo elimina de partidos_futuros.
	Para insertar boxscores, primero debe existir el partido en partidos.
	Solo funciona si el usuario está autenticado.
	
	Args:
		game_id: ID del partido
		pts_local: Puntos del equipo local
		pts_visitante: Puntos del equipo visitante
		
	Returns:
		tuple: (success: bool, message: str)
	"""
	if not check_auth():
		return False, "❌ Debes estar autenticado para realizar esta operación"
	
	try:
		client = get_supabase_client()
		
		# Obtener datos del partido futuro
		partido_futuro = get_partido_futuro(game_id)
		if not partido_futuro:
			return False, f"❌ No se encontró el partido futuro con GAME_ID: {game_id}"
		
		# Crear registro en partidos (si no existe)
		partido_existente = get_partido_jugado(game_id)
		if not partido_existente:
			partido_data = {
				"GAME_ID": game_id,
				"FECHA": partido_futuro.get("FECHA"),
				"LOCAL": partido_futuro.get("LOCAL"),
				"VISITANTE": partido_futuro.get("VISITANTE"),
				"PTS_LOCAL": pts_local,
				"PTS_VISITANTE": pts_visitante
			}
			
			# Insertar en partidos
			response_insert = client.table("partidos").insert(partido_data).execute()
			
			if not response_insert.data:
				return False, "❌ Error al insertar el partido en la tabla partidos"
		
		# Eliminar de partidos_futuros
		response_delete = (
			client.table("partidos_futuros")
			.delete()
			.eq("GAME_ID", game_id)
			.execute()
		)
		
		clear_cache()  # Invalidar cache después de modificar datos
		return True, f"✅ Partido {game_id} movido exitosamente de futuros a jugados"
			
	except Exception as e:
		error_msg = str(e)
		return False, f"❌ Error al mover partido: {error_msg}"


def cargar_partido_completo(game_id: str, boxscores_data: list, pts_local: int, pts_visitante: int) -> tuple[bool, str]:
	"""
	Carga un partido completo en el orden correcto:
	1. Crea el partido en partidos (para que exista la FK)
	2. Inserta los boxscores
	3. Elimina el partido de partidos_futuros
	Solo funciona si el usuario está autenticado.
	
	Args:
		game_id: ID del partido
		boxscores_data: Lista de diccionarios con los datos de boxscore
		pts_local: Puntos del equipo local
		pts_visitante: Puntos del equipo visitante
		
	Returns:
		tuple: (success: bool, message: str)
	"""
	if not check_auth():
		return False, "❌ Debes estar autenticado para realizar esta operación"
	
	try:
		# 1. Crear el partido en partidos primero (para que exista la FK)
		success_create, msg_create = crear_partido_jugado(game_id, pts_local, pts_visitante)
		if not success_create:
			return False, f"❌ Error al crear partido: {msg_create}"
		
		# 2. Insertar boxscores
		success_box, msg_box = insert_boxscores(boxscores_data)
		if not success_box:
			# Si falla, intentar limpiar el partido creado (opcional, pero recomendable)
			# Por ahora, solo retornamos el error
			return False, f"❌ Error al insertar boxscores: {msg_box}"
		
		# 3. Mover de partidos_futuros a partidos (eliminar de futuros)
		success_move, msg_move = mover_partido_futuro_a_jugado(game_id, pts_local, pts_visitante)
		if not success_move:
			# Los boxscores ya están insertados, pero el partido sigue en futuros
			# Esto es un estado inconsistente, pero no crítico
			return False, f"⚠️ Boxscores insertados pero error al mover partido: {msg_move}"
		
		return True, f"✅ Partido {game_id} cargado exitosamente con {len(boxscores_data)} boxscore(s)"
			
	except Exception as e:
		error_msg = str(e)
		return False, f"❌ Error al cargar partido completo: {error_msg}"


def get_partido_jugado(game_id: str) -> dict:
	"""
	Obtiene un partido jugado por su GAME_ID.
	
	Args:
		game_id: ID del partido
		
	Returns:
		dict: Datos del partido o None si no existe
	"""
	try:
		client = get_supabase_client()
		response = (
			client.table("partidos")
			.select("*")
			.eq("GAME_ID", game_id)
			.execute()
		)
		
		if response.data and len(response.data) > 0:
			return response.data[0]
		return None
			
	except Exception as e:
		return None


def eliminar_partido(game_id: str) -> tuple[bool, str]:
	"""
	Elimina un partido jugado:
	1. Borra todas las instancias del partido en boxscores
	2. Mueve el partido de partidos a partidos_futuros
	Solo funciona si el usuario está autenticado.
	
	Args:
		game_id: ID del partido a eliminar
		
	Returns:
		tuple: (success: bool, message: str)
	"""
	if not check_auth():
		return False, "❌ Debes estar autenticado para realizar esta operación"
	
	try:
		client = get_supabase_client()
		
		# Obtener datos del partido jugado
		partido_jugado = get_partido_jugado(game_id)
		if not partido_jugado:
			return False, f"❌ No se encontró el partido jugado con GAME_ID: {game_id}"
		
		# 1. Eliminar todos los boxscores del partido
		response_delete_boxscores = (
			client.table("boxscores")
			.delete()
			.eq("GAME_ID", game_id)
			.execute()
		)
		
		# 2. Crear registro en partidos_futuros
		partido_futuro_data = {
			"GAME_ID": game_id,
			"FECHA": partido_jugado.get("FECHA"),
			"LOCAL": partido_jugado.get("LOCAL"),
			"VISITANTE": partido_jugado.get("VISITANTE")
		}
		
		# Insertar en partidos_futuros
		response_insert = client.table("partidos_futuros").insert(partido_futuro_data).execute()
		
		if not response_insert.data:
			return False, "❌ Error al insertar el partido en la tabla partidos_futuros"
		
		# 3. Eliminar de partidos
		response_delete = (
			client.table("partidos")
			.delete()
			.eq("GAME_ID", game_id)
			.execute()
		)
		
		clear_cache()  # Invalidar cache después de modificar datos
		return True, f"✅ Partido {game_id} eliminado exitosamente. Boxscores eliminados y partido movido a futuros."
			
	except Exception as e:
		error_msg = str(e)
		return False, f"❌ Error al eliminar partido: {error_msg}"

