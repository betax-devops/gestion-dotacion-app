import io
import pandas as pd
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión de OTs - Dotación", layout="wide")


# --- MÓDULO DE AUTENTICACIÓN ---
def verificar_password():
    """Retorna True si el usuario ingresó la contraseña correcta."""
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if st.session_state.autenticado:
        return True

    st.subheader("🔒 Acceso Restringido - AnálisisRED")

    try:
        correct_password = st.secrets["APP_PASSWORD"]
    except KeyError:
        st.error(
            "⚠️ La contraseña del sistema no está configurada en los Secrets de Streamlit."
        )
        return False

    password_ingresada = st.text_input(
        "Ingresa la contraseña de acceso:", type="password"
    )

    if st.button("Ingresar"):
        if password_ingresada == correct_password:
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta")

    return False


# Bloquear la ejecución si el usuario no ingresó la contraseña
if not verificar_password():
    st.stop()


# --- FUNCIÓN PARA DESCARGAR Y CARGAR EXCEL DESDE GOOGLE DRIVE ---
@st.cache_data(ttl=300)  # Guarda en caché durante 5 minutos
def cargar_excel_desde_drive(nombre_archivo):
    # 1. Autenticación vía Service Account en Secrets
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    service = build("drive", "v3", credentials=creds)

    # 2. Buscar archivo en Google Drive por nombre
    query = f"name = '{nombre_archivo}' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get("files", [])

    if not items:
        st.error(f"No se encontró el archivo '{nombre_archivo}' en Google Drive.")
        return None

    file_id = items[0]["id"]

    # 3. Descargar el archivo Excel a la memoria
    request = service.files().get_media(fileId=file_id)
    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    file_stream.seek(0)

    # 4. Leer el archivo Excel usando pandas y openpyxl
    return pd.read_excel(file_stream, engine="openpyxl")


# --- PANEL PRINCIPAL ---
st.title("📊 AnálisisRED - Control de Dotación")

NOMBRE_ARCHIVO_EXCEL = "dotacion.xlsx"

# Cargar datos desde Google Drive
df_dotacion = cargar_excel_desde_drive(NOMBRE_ARCHIVO_EXCEL)

if df_dotacion is not None:
    st.subheader("📋 Registro de Dotación")
    st.write(f"Total de registros cargados: **{len(df_dotacion)}**")

    # Mostrar la tabla en Streamlit

    #Convertir a entero
    #df_dotacion['Edad'] = pd.to_numeric(df_dotacion['Edad'], errors='coerce').astype('float')
    if 'Edad' in df_dotacion.columns:df_dotacion['Edad'] = pd.to_numeric(df_dotacion['Edad'], errors='coerce').astype('Int64')
    #Convertir a Fecha sin hora
    df_dotacion['Fecha_Nac'] = pd.to_datetime(df_dotacion['Fecha_Nac'], errors='coerce').dt.date
    #Columnas deseadas a mostrar
    cols_deseadas_tecnicos = [
        "Legajo",
        "Técnico",
        "Apellido y Nombre",
        "Edad",
        "Fecha_Nac",
        "DNI",
        "Business  Email Information Email Address"
    ]
    cols_tecnicos = [col for col in cols_deseadas_tecnicos if col in df_dotacion.columns]
    st.dataframe(df_dotacion[cols_tecnicos], use_container_width=True)
    #st.dataframe(df_dotacion,column_config={"Edad": st.column_config.NumberColumn("Edad", format="%d")},use_container_width=True,)
