import streamlit as st
import pandas as pd
from supabase import create_client, Client

# Conexión Supabase compartida
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# Cliente base anónimo (para acceso sin autenticación)
supabase_anon: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


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


def load_data():
	"""
	Carga los datos desde Supabase.
	Nota: No usar @st.cache_data porque los datos pueden variar según
	el estado de autenticación y las políticas RLS.
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


