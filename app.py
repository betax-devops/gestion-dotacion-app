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

# --- DOTACION ---
with tab_dotacion:
    if df_dotacion is not None:
        st.subheader(
            "👷🏻‍♂️ Registro de Dotación",
            icon=":material/router:",
            divider="blue",
            anchor="puerto-24",
        )

        # --- RENOMBRAR COLUMNAS ---
        if "Business  Email Information Email Address" in df_dotacion.columns:
            df_dotacion.rename(
                columns={"Business  Email Information Email Address": "Email"},
                inplace=True,
            )

        # --- NORMALIZACIÓN Y CÁLCULO DE CAMPOS DERIVADOS ---
        if "Fecha_Nac" in df_dotacion.columns:
            fecha_nac_dt = pd.to_datetime(
                df_dotacion["Fecha_Nac"], errors="coerce"
            )
            df_dotacion["Fecha_Nac"] = fecha_nac_dt.dt.date

            hoy = date.today()
            df_dotacion["Edad"] = fecha_nac_dt.apply(
                lambda d: hoy.year
                - d.year
                - ((hoy.month, hoy.day) < (d.month, d.day))
                if pd.notnull(d)
                else None
            ).astype("Int64")

            df_dotacion["Cumpleaños"] = fecha_nac_dt.dt.month.astype("Int64")

        # --- SECCIÓN DE GESTIÓN INDIVIDUAL (BÚSQUEDA / AGREGAR / EDITAR / BORRAR) ---
        with st.expander("🛠️ **Gestión Individual de Técnico (Búsqueda / ABM)**", expanded=False):
            opcion_accion = st.radio(
                "Selecciona la acción:",
                ["🔍 Buscar / Editar", "➕ Agregar Nuevo Técnico", "🗑️ Eliminar Técnico"],
                horizontal=True,
            )

            lista_legajos = df_dotacion["Legajo"].dropna().unique().tolist() if "Legajo" in df_dotacion.columns else []

            # 1. BUSCAR / EDITAR REGISTRO POR LEGAJO
            if opcion_accion == "🔍 Buscar / Editar":
                legajo_sel = st.selectbox("Selecciona o busca por Legajo:", sorted(lista_legajos))
                
                if legajo_sel:
                    # Extraer fila seleccionada
                    fila_idx = df_dotacion[df_dotacion["Legajo"] == legajo_sel].index[0]
                    tecnico_info = df_dotacion.loc[fila_idx]

                    with st.form("form_editar_tecnico"):
                        st.markdown(f"**Editando Legajo:** `{legajo_sel}`")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            nom_edit = st.text_input("Apellido y Nombre", value=str(tecnico_info.get("Apellido y Nombre", "")))
                            dni_edit = st.text_input("DNI", value=str(tecnico_info.get("DNI", "")))
                            fnac_val = tecnico_info.get("Fecha_Nac")
                            fnac_edit = st.date_input(
                                "Fecha de Nacimiento",
                                value=fnac_val if isinstance(fnac_val, date) else date(1990, 1, 1)
                            )

                        with col2:
                            tec_edit = st.text_input("Técnico / Código", value=str(tecnico_info.get("Técnico", "")))
                            email_edit = st.text_input("Email", value=str(tecnico_info.get("Email", "")))
                            subtarea_edit = st.text_input("Subtarea", value=str(tecnico_info.get("Subtarea", "")))

                        btn_guardar = st.form_submit_button("💾 Guardar Cambios")

                        if btn_guardar:
                            # Actualizar datos en el DataFrame
                            df_dotacion.at[fila_idx, "Apellido y Nombre"] = nom_edit
                            df_dotacion.at[fila_idx, "DNI"] = dni_edit
                            df_dotacion.at[fila_idx, "Fecha_Nac"] = fnac_edit
                            df_dotacion.at[fila_idx, "Técnico"] = tec_edit
                            df_dotacion.at[fila_idx, "Email"] = email_edit
                            df_dotacion.at[fila_idx, "Subtarea"] = subtarea_edit
                            
                            st.success(f"¡Registro `{legajo_sel}` actualizado correctamente!")
                            st.rerun()

            # 2. AGREGAR NUEVO REGISTRO
            elif opcion_accion == "➕ Agregar Nuevo Técnico":
                with st.form("form_nuevo_tecnico"):
                    col1, col2 = st.columns(2)
                    with col1:
                        nuevo_legajo = st.text_input("Legajo *")
                        nuevo_nombre = st.text_input("Apellido y Nombre *")
                        nuevo_dni = st.text_input("DNI")
                        nueva_fnac = st.date_input("Fecha de Nacimiento", value=date(1995, 1, 1))

                    with col2:
                        nuevo_tec = st.text_input("Técnico / Código")
                        nuevo_email = st.text_input("Email")
                        nueva_subtarea = st.text_input("Subtarea")

                    btn_crear = st.form_submit_button("➕ Registrar Técnico")

                    if btn_crear:
                        if not nuevo_legajo or not nuevo_nombre:
                            st.error("El Legajo y Nombre son campos obligatorios.")
                        else:
                            nueva_fila = {
                                "Legajo": nuevo_legajo,
                                "Técnico": nuevo_tec,
                                "Apellido y Nombre": nuevo_nombre,
                                "Fecha_Nac": nueva_fnac,
                                "DNI": nuevo_dni,
                                "Email": nuevo_email,
                                "Subtarea": nueva_subtarea,
                            }
                            df_dotacion = pd.concat([df_dotacion, pd.DataFrame([nueva_fila])], ignore_index=True)
                            st.success(f"Técnico `{nuevo_nombre}` agregado correctamente.")
                            st.rerun()

            # 3. ELIMINAR REGISTRO
            elif opcion_accion == "🗑️ Eliminar Técnico":
                legajo_del = st.selectbox("Selecciona Legajo a eliminar:", sorted(lista_legajos), key="del_legajo")
                if legajo_del:
                    tecnico_del = df_dotacion[df_dotacion["Legajo"] == legajo_del]["Apellido y Nombre"].values[0]
                    st.warning(f"¿Confirmas eliminar a **{tecnico_del}** (Legajo `{legajo_del}`)?")
                    
                    if st.button("❌ Confirmar Eliminación"):
                        df_dotacion = df_dotacion[df_dotacion["Legajo"] != legajo_del].reset_index(drop=True)
                        st.success("Técnico eliminado del DataFrame.")
                        st.rerun()

        st.write(f"Total de registros cargados: **{len(df_dotacion)}**")

        # --- COLUMNAS Y TABLA GENERAL ---
        cols_deseadas_tecnicos = [
            "Legajo",
            "Técnico",
            "Apellido y Nombre",
            "Fecha_Nac",
            "Cumpleaños",
            "Edad",
            "DNI",
            "Email",
            "Subtarea",
        ]
        cols_tecnicos = [col for col in cols_deseadas_tecnicos if col in df_dotacion.columns]

        st.dataframe(
            df_dotacion[cols_tecnicos],
            column_config={
                "Fecha_Nac": st.column_config.DateColumn(
                    "Fecha Nacimiento", format="DD/MM/YYYY"
                ),
                "Cumpleaños": st.column_config.NumberColumn(
                    "Mes Cumpleaños", format="%d"
                ),
                "Edad": st.column_config.NumberColumn(
                    "Edad", format="%d años"
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


# --- FLOTA ---
with tab_flota:
    if df_flota is not None:
        st.subheader("🚗 Flota")
        st.write(f"Flota total de la Base: **{len(df_flota)}**")

        st.dataframe(df_flota, use_container_width=True)

    
    
# --- CONEXIÓN A GOOGLE DRIVE VÍA SECRETS ---
# --- FUNCIÓN PARA CONECTAR A GOOGLE DRIVE Y CARGAR EL CSV ---
@st.cache_data(ttl=300)  # Reutiliza los datos cargados durante 5 minutos
def cargar_csv_desde_drive(nombre_archivo):
    # 1. Autenticación con las credenciales guardadas en Secrets
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    service = build("drive", "v3", credentials=creds)

    # 2. Buscar el id del archivo en Google Drive
    query = f"name = '{nombre_archivo}' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get("files", [])

    if not items:
        st.error(f"No se encontró el archivo '{nombre_archivo}' en Google Drive.")
        return None

    file_id = items[0]["id"]

    # 3. Descargar el contenido del archivo a la memoria
    request = service.files().get_media(fileId=file_id)
    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    file_stream.seek(0)

    # 4. Leer el CSV con Pandas (ajustando separador de punto y coma)
    try:
        # Intenta primero con utf-8-sig / utf-8
        return pd.read_csv(file_stream, sep=";", quotechar='"', encoding="utf-8-sig")
    except (UnicodeDecodeError, Exception):
        file_stream.seek(0)
        try:
            # Si falla, intenta con latin1 (muy común en Windows / Latinoamérica)
            return pd.read_csv(file_stream, sep=";", quotechar='"', encoding="latin1")
        except Exception:
            file_stream.seek(0)
            # Como último recurso, lee ignorando errores de caracteres extraños
            return pd.read_csv(file_stream, sep=";", quotechar='"', encoding="utf-8", encoding_errors="ignore")

# --- CARGA Y VISUALIZACIÓN DE TABLA ---
NOMBRE_ARCHIVO = "report.csv"

# Cargar el dataframe desde Google Drive
df = cargar_csv_desde_drive(NOMBRE_ARCHIVO)

if df is not None:
    st.subheader("📋 Todos los Resultados")
    st.write(f"Resultados encontrados: **{len(df)}**")
    st.dataframe(df, use_container_width=True)
