import io
import pandas as pd
import streamlit as st
from datetime import date
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

    st.subheader("🔒 Acceso Restringido - Base CCP")

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
st.title("📊 Base CCP - Control de Dotación")

DOTACION = "dotacion.xlsx"
CELULARES = "celulares.xlsx"
FLOTA = "flota.xlsx"

# Cargar datos desde Google Drive
df_dotacion = cargar_excel_desde_drive(DOTACION)
df_celulares = cargar_excel_desde_drive(CELULARES)
df_flota = cargar_excel_desde_drive(FLOTA)

# --- PESTAÑAS DE NAVEGACIÓN ---
tab_dotacion, tab_celulares, tab_flota, tab_hh, tab_epps = st.tabs(["👷🏻‍♂️ Dotacion", "📱 Celulares", "🚗 Flota", "🧰 Herramientas", "⛑️ EPPs"])

# --- DORACION ---
with tab_dotacion:
    if df_dotacion is not None:
        st.subheader(
            "👷🏻‍♂️ Registro de Dotación",
            icon=":material/router:",
            divider="blue",
            anchor="puerto-24"
        )
        st.write(f"Total de registros cargados: **{len(df_dotacion)}**")

        # --- RENOMBRAR COLUMNAS ---
        if "Business  Email Information Email Address" in df_dotacion.columns:
            df_dotacion.rename(
                columns={"Business  Email Information Email Address": "Email"},
                inplace=True,
            )
        
        # --- NORMALIZACION DE TIPO DE DATOS ---
        # Fecha de Nacimiento a dato date y con formato dd mm yyyy
        if "Fecha_Nac" in df_dotacion.columns:
            # Convertir a datetime y extraer únicamente la fecha (.dt.date)
            df_dotacion["Fecha_Nac"] = pd.to_datetime(
                df_dotacion["Fecha_Nac"], errors="coerce"
            ).dt.date

        # Calculamos la Edad
        # 1. Asegurar que Fecha_Nac sea datetime para la operación
        fecha_nac = pd.to_datetime(df_dotacion['Fecha_Nac'], errors='coerce')
        # 2. Fecha actual
        hoy = date.today()
        # 3. Fórmula para calcular la edad exacta en años cumplidos
        df_dotacion['Edad'] = fecha_nac.apply(
        lambda d: hoy.year - d.year - ((hoy.month, hoy.day) < (d.month, d.day)) if pd.notnull(d) else None
        ).astype("Int64")

        # Agregamos mes de cumpleaños
        df_dotacion['Cumpleaños'] = df_dotacion['Fecha_Nac'].date.month

        #Columnas deseadas a mostrar
        cols_deseadas_tecnicos = [
            "Legajo",
            "Técnico",
            "Apellido y Nombre",
            "Fecha_Nac",
            "Cumpleaños",
            "Edad",
            "DNI",
            "Email",
            "Subtarea"
        ]
        cols_tecnicos = [col for col in cols_deseadas_tecnicos if col in df_dotacion.columns]

        # Configuración de visualización de columnas en la tabla
        st.dataframe(
            df_dotacion[cols_tecnicos],
            column_config={
                "Fecha_Nac": st.column_config.DateColumn(
                    "Fecha Nacimiento", format="DD/MM/YYYY"
                ),
            },
            use_container_width=True,
        )


# --- CELULARES ---
with tab_celulares:
    if df_celulares is not None:
        st.subheader("📱 Registro de Celulares")
        st.write(f"Total de registros cargados: **{len(df_celulares)}**")

        st.dataframe(df_celulares, use_container_width=True)

    
    
