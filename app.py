"""Explorador automático de datos construido con Streamlit."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Explorador automático de datos",
    page_icon="📊",
    layout="wide",
)

PALABRAS_FECHA = ("fecha", "date")


@st.cache_data(show_spinner=False)
def leer_csv(contenido: bytes) -> pd.DataFrame:
    """Lee un CSV probando combinaciones comunes de codificación y separador."""
    errores: list[str] = []
    for codificacion in ("utf-8", "utf-8-sig", "latin-1"):
        for separador in (None, ",", ";", "\t", "|"):
            try:
                opciones = {"encoding": codificacion}
                if separador is None:
                    opciones.update({"sep": None, "engine": "python"})
                else:
                    opciones["sep"] = separador
                df = pd.read_csv(BytesIO(contenido), **opciones)
                if len(df.columns) > 1 or separador == ",":
                    return df
            except Exception as error:  # Se intenta una alternativa antes de fallar.
                errores.append(str(error))
    raise ValueError("No fue posible interpretar el CSV. Verifica su codificación y separador.")


@st.cache_data(show_spinner=False)
def leer_excel(contenido: bytes, extension: str) -> pd.DataFrame:
    """Lee la primera hoja de un libro Excel con el motor correspondiente."""
    motor = "openpyxl" if extension == ".xlsx" else "xlrd"
    return pd.read_excel(BytesIO(contenido), engine=motor)


@st.cache_data(show_spinner=False)
def cargar_datos(contenido: bytes, nombre_archivo: str) -> pd.DataFrame:
    """Carga, normaliza encabezados e intenta reconocer columnas de fecha."""
    extension = Path(nombre_archivo).suffix.lower()
    if extension == ".csv":
        df = leer_csv(contenido)
    elif extension in {".xlsx", ".xls"}:
        df = leer_excel(contenido, extension)
    else:
        raise ValueError("Formato no admitido. Usa CSV, XLSX o XLS.")

    df.columns = [str(columna).strip() for columna in df.columns]
    for columna in df.columns:
        nombre = columna.lower()
        if any(palabra in nombre for palabra in PALABRAS_FECHA):
            convertida = pd.to_datetime(df[columna], errors="coerce")
            no_nulos_originales = int(df[columna].notna().sum())
            convertidos = int(convertida.notna().sum())
            # Evita destruir una columna cuyo nombre parece fecha, pero cuyos valores no lo son.
            if no_nulos_originales == 0 or convertidos / max(no_nulos_originales, 1) >= 0.60:
                df[columna] = convertida
    return df


def tipo_analitico(serie: pd.Series) -> str:
    """Interpreta el tipo técnico de Pandas como un tipo útil para el análisis."""
    if pd.api.types.is_bool_dtype(serie):
        return "Booleana"
    if pd.api.types.is_datetime64_any_dtype(serie):
        return "Fecha/hora"
    if pd.api.types.is_numeric_dtype(serie):
        return "Numérica"
    if isinstance(serie.dtype, pd.CategoricalDtype):
        return "Categórica"
    no_nulos = serie.dropna()
    if no_nulos.empty:
        return "Texto"
    proporcion_unicos = no_nulos.nunique(dropna=True) / len(no_nulos)
    return "Categórica" if no_nulos.nunique() <= 50 or proporcion_unicos <= 0.20 else "Texto"


def columnas_por_tipo(df: pd.DataFrame) -> dict[str, list[str]]:
    """Agrupa columnas según su tipo analítico."""
    resultado = {tipo: [] for tipo in ("Numérica", "Categórica", "Texto", "Booleana", "Fecha/hora")}
    for columna in df.columns:
        resultado[tipo_analitico(df[columna])].append(columna)
    return resultado


def resumen_tipos(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Variable": df.columns,
            "Tipo Pandas": [str(df[c].dtype) for c in df.columns],
            "Tipo analítico": [tipo_analitico(df[c]) for c in df.columns],
            "Valores no nulos": [int(df[c].notna().sum()) for c in df.columns],
            "Valores únicos": [int(df[c].nunique(dropna=True)) for c in df.columns],
        }
    )


def tabla_faltantes(df: pd.DataFrame) -> pd.DataFrame:
    faltantes = df.isna().sum()
    porcentaje = faltantes.div(len(df)).mul(100) if len(df) else faltantes.astype(float)
    return (
        pd.DataFrame({"Variable": df.columns, "Valores faltantes": faltantes.values,
                      "Porcentaje faltante": porcentaje.values})
        .sort_values(["Valores faltantes", "Variable"], ascending=[False, True])
        .reset_index(drop=True)
    )


def a_csv(df: pd.DataFrame) -> bytes:
    """Genera un CSV en memoria, con BOM y sin índice."""
    return df.to_csv(index=False).encode("utf-8-sig")


def opciones_legibles(valores: Iterable[object]) -> list[object]:
    return sorted(valores, key=lambda valor: str(valor).casefold())


def aplicar_filtros(df: pd.DataFrame, tipos: dict[str, list[str]]) -> pd.DataFrame:
    """Construye filtros laterales y devuelve una copia filtrada."""
    filtrado = df.copy()
    st.sidebar.header("Filtros interactivos")

    for columna in tipos["Fecha/hora"]:
        serie = df[columna]
        validas = serie.dropna()
        if validas.empty:
            st.sidebar.caption(f"{columna}: sin fechas válidas")
            continue
        minimo, maximo = validas.min().date(), validas.max().date()
        seleccion = st.sidebar.date_input(
            f"Rango de {columna}", value=(minimo, maximo), min_value=minimo,
            max_value=maximo, key=f"fecha_{columna}"
        )
        if isinstance(seleccion, (tuple, list)) and len(seleccion) == 2:
            inicio, fin = pd.Timestamp(seleccion[0]), pd.Timestamp(seleccion[1])
            mascara = filtrado[columna].isna() | filtrado[columna].between(
                inicio, fin + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
            )
            filtrado = filtrado.loc[mascara]

    candidatas_cat = tipos["Categórica"] + tipos["Booleana"]
    filtros_cat = st.sidebar.multiselect(
        "Variables categóricas para filtrar", candidatas_cat, key="filtros_cat"
    )
    for columna in filtros_cat:
        disponibles = opciones_legibles(df[columna].dropna().unique().tolist())
        elegidas = st.sidebar.multiselect(
            f"Categorías de {columna}", disponibles, default=disponibles,
            key=f"cat_{columna}"
        )
        if elegidas:
            filtrado = filtrado.loc[filtrado[columna].isin(elegidas)]
        else:
            filtrado = filtrado.iloc[0:0]

    filtros_num = st.sidebar.multiselect(
        "Variables numéricas para filtrar", tipos["Numérica"], key="filtros_num"
    )
    for columna in filtros_num:
        validos = df[columna].dropna()
        if validos.empty:
            st.sidebar.caption(f"{columna}: sin valores numéricos válidos")
            continue
        minimo, maximo = float(validos.min()), float(validos.max())
        if minimo == maximo:
            st.sidebar.caption(f"{columna}: valor constante ({minimo:g})")
            continue
        rango = st.sidebar.slider(
            f"Rango de {columna}", minimo, maximo, (minimo, maximo),
            key=f"num_{columna}"
        )
        mascara = filtrado[columna].isna() | filtrado[columna].between(*rango)
        filtrado = filtrado.loc[mascara]

    st.sidebar.success(f"Registros resultantes: {len(filtrado):,}")
    return filtrado


def detectar_atipicos(df: pd.DataFrame, variables: list[str], factor: float) -> pd.DataFrame:
    """Devuelve una fila por cada detección usando el criterio IQR."""
    resultados: list[pd.DataFrame] = []
    for variable in variables:
        serie = df[variable].dropna()
        if serie.empty:
            continue
        q1, q3 = serie.quantile([0.25, 0.75])
        iqr = q3 - q1
        inferior, superior = q1 - factor * iqr, q3 + factor * iqr
        mascara = df[variable].notna() & ~df[variable].between(inferior, superior)
        if mascara.any():
            hallazgos = df.loc[mascara].copy()
            hallazgos.insert(0, "Fila original", hallazgos.index)
            hallazgos.insert(1, "Variable atípica", variable)
            hallazgos.insert(2, "Límite inferior", inferior)
            hallazgos.insert(3, "Límite superior", superior)
            resultados.append(hallazgos)
    if not resultados:
        return pd.DataFrame(columns=["Fila original", "Variable atípica", "Límite inferior", "Límite superior"])
    return pd.concat(resultados, ignore_index=True)


st.title("📊 Explorador automático de datos")
st.write(
    "Carga un archivo y obtén un análisis exploratorio automático, interactivo y adaptable "
    "a conjuntos de datos de distintas áreas del conocimiento."
)

st.sidebar.header("Carga del dataset")
archivo = st.sidebar.file_uploader(
    "Selecciona un archivo", type=["csv", "xlsx", "xls"],
    help="Formatos admitidos: CSV, XLSX y XLS."
)

if archivo is None:
    st.info("Para comenzar, carga un archivo desde la barra lateral.")
    c1, c2, c3 = st.columns(3)
    c1.subheader("1. Cargar")
    c1.write("Selecciona un archivo CSV, XLSX o XLS desde tu computador.")
    c2.subheader("2. Explorar")
    c2.write("Revisa tipos, calidad, estadísticas, distribuciones, correlaciones y atípicos.")
    c3.subheader("3. Descargar")
    c3.write("Exporta los datos filtrados y los valores atípicos en CSV.")
    st.subheader("Análisis disponibles")
    st.markdown(
        "- Dimensiones, tipos de variables e indicadores generales.\n"
        "- Duplicados, valores faltantes y estadísticas descriptivas.\n"
        "- Distribuciones, correlaciones y detección de valores atípicos por IQR.\n"
        "- Filtros interactivos, tabla ordenable y descargas."
    )
    st.warning("No se generan datos ficticios. Debes proporcionar tu propio conjunto de datos.")
    st.stop()

try:
    df_original = cargar_datos(archivo.getvalue(), archivo.name)
except Exception as error:
    st.error(f"No fue posible procesar el archivo: {error}")
    st.stop()

if df_original.empty or len(df_original.columns) == 0:
    st.warning("El archivo está vacío o no contiene una tabla utilizable.")
    st.stop()

st.sidebar.success(f"Archivo cargado: {archivo.name}")
tipos_originales = columnas_por_tipo(df_original)
df = aplicar_filtros(df_original, tipos_originales)

if df.empty:
    st.warning("Los filtros no producen registros. Ajusta los filtros en la barra lateral para continuar.")
    st.stop()

tipos = columnas_por_tipo(df)

st.subheader("Indicadores generales")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Filas", f"{df.shape[0]:,}")
m2.metric("Columnas", f"{df.shape[1]:,}")
m3.metric("Duplicados completos", f"{int(df.duplicated().sum()):,}")
m4.metric("Celdas faltantes", f"{int(df.isna().sum().sum()):,}")
st.caption(f"Archivo: {archivo.name} | Dimensiones filtradas: {df.shape[0]:,} filas × {df.shape[1]:,} columnas")

st.download_button(
    "Descargar datos filtrados", data=a_csv(df), file_name="datos_filtrados.csv",
    mime="text/csv", key="descarga_superior"
)

pestanas = st.tabs([
    "Resumen y tipos", "Calidad de datos", "Estadísticas", "Distribuciones",
    "Correlaciones", "Valores atípicos", "Tabla ordenable"
])

with pestanas[0]:
    st.subheader("Dimensiones del dataset")
    st.write(f"**Archivo:** {archivo.name}")
    st.write(f"**Filas:** {df.shape[0]:,} | **Columnas:** {df.shape[1]:,}")
    st.subheader("Tipos de variables")
    st.dataframe(resumen_tipos(df), width="stretch", hide_index=True)

with pestanas[1]:
    st.subheader("Registros duplicados")
    cantidad_duplicados = int(df.duplicated().sum())
    st.metric("Filas duplicadas adicionales", cantidad_duplicados)
    involucrados = df.loc[df.duplicated(keep=False)]
    if involucrados.empty:
        st.success("No se encontraron registros completamente duplicados.")
    else:
        st.write(f"Registros involucrados en grupos duplicados: {len(involucrados):,}")
        st.dataframe(involucrados, width="stretch")

    st.subheader("Valores faltantes")
    faltantes = tabla_faltantes(df)
    st.dataframe(
        faltantes.style.format({"Porcentaje faltante": "{:.2f}%"}),
        width="stretch", hide_index=True
    )
    fig_faltantes = px.bar(
        faltantes, x="Variable", y="Porcentaje faltante",
        title="Porcentaje de valores faltantes por variable",
        labels={"Porcentaje faltante": "Porcentaje (%)"}
    )
    st.plotly_chart(fig_faltantes, width="stretch")

with pestanas[2]:
    st.subheader("Estadísticas descriptivas")
    alcance = st.radio(
        "Variables a incluir", ["Todas las variables", "Solo variables numéricas", "Solo variables categóricas"],
        horizontal=True
    )
    traduccion = {
        "count": "Conteo", "mean": "Media", "std": "Desviación estándar",
        "min": "Mínimo", "25%": "Primer cuartil", "50%": "Mediana",
        "75%": "Tercer cuartil", "max": "Máximo", "unique": "Valores únicos",
        "top": "Categoría más frecuente", "freq": "Frecuencia dominante"
    }
    try:
        if alcance == "Solo variables numéricas":
            columnas = tipos["Numérica"]
            if not columnas:
                raise ValueError("El dataset filtrado no tiene variables numéricas.")
            estadisticas = df[columnas].describe().T
        elif alcance == "Solo variables categóricas":
            columnas = tipos["Categórica"] + tipos["Texto"] + tipos["Booleana"]
            if not columnas:
                raise ValueError("El dataset filtrado no tiene variables categóricas o de texto.")
            estadisticas = df[columnas].describe(include="all").T
        else:
            estadisticas = df.describe(include="all", datetime_is_numeric=True).T
        estadisticas = estadisticas.rename(columns=traduccion)
        st.dataframe(estadisticas, width="stretch")
    except TypeError:
        # Compatibilidad con versiones de Pandas que no acepten datetime_is_numeric.
        st.dataframe(df.describe(include="all").T.rename(columns=traduccion), width="stretch")
    except Exception as error:
        st.info(str(error))

with pestanas[3]:
    st.subheader("Distribuciones")
    variable = st.selectbox("Selecciona una variable", df.columns)
    tipo = tipo_analitico(df[variable])
    if tipo == "Numérica":
        intervalos = st.slider("Número de intervalos", 5, 100, 30)
        histograma = px.histogram(df, x=variable, nbins=intervalos, title=f"Histograma de {variable}")
        st.plotly_chart(histograma, width="stretch")
        agrupadoras = ["Sin agrupación"] + tipos["Categórica"] + tipos["Booleana"]
        agrupadora = st.selectbox("Agrupar diagrama de caja por", agrupadoras)
        caja = px.box(
            df, x=None if agrupadora == "Sin agrupación" else agrupadora,
            y=variable, points="outliers", title=f"Diagrama de caja de {variable}"
        )
        st.plotly_chart(caja, width="stretch")
    else:
        categorias = df[variable].astype("object").where(df[variable].notna(), "(Faltante)").astype(str)
        frecuencias = categorias.value_counts(dropna=False).head(30).rename_axis("Categoría").reset_index(name="Frecuencia")
        if categorias.nunique(dropna=False) > 30:
            st.info("Se muestran las 30 categorías más frecuentes.")
        barras = px.bar(frecuencias, x="Categoría", y="Frecuencia", title=f"Frecuencias de {variable}")
        st.plotly_chart(barras, width="stretch")

with pestanas[4]:
    st.subheader("Correlaciones")
    numericas = tipos["Numérica"]
    seleccionadas = st.multiselect("Variables numéricas", numericas, default=numericas)
    metodo = st.selectbox("Método", ["Pearson", "Spearman", "Kendall"])
    if len(seleccionadas) < 2:
        st.info("Selecciona al menos dos variables numéricas para calcular correlaciones.")
    else:
        matriz = df[seleccionadas].corr(method=metodo.lower())
        mapa = go.Figure(go.Heatmap(
            z=matriz.values, x=matriz.columns, y=matriz.index,
            zmin=-1, zmax=1, colorscale="RdBu", reversescale=True,
            text=np.round(matriz.values, 2), texttemplate="%{text}",
            hovertemplate="%{y} / %{x}: %{z:.3f}<extra></extra>"
        ))
        mapa.update_layout(title=f"Correlación de {metodo}")
        st.plotly_chart(mapa, width="stretch")
        st.dataframe(matriz.style.format("{:.3f}"), width="stretch")
        st.caption("Recuerda: una correlación no implica causalidad.")

with pestanas[5]:
    st.subheader("Valores atípicos por rango intercuartílico")
    numericas = tipos["Numérica"]
    if not numericas:
        st.info("El dataset filtrado no contiene variables numéricas.")
        atipicos = pd.DataFrame()
    else:
        variables_iqr = st.multiselect("Variables para analizar", numericas, default=numericas)
        factor = st.slider("Factor IQR", 1.0, 3.0, 1.5, 0.1)
        atipicos = detectar_atipicos(df, variables_iqr, factor)
        st.metric("Detecciones", len(atipicos))
        if atipicos.empty:
            st.success("No se detectaron valores atípicos con la configuración actual.")
        else:
            conteo = atipicos["Variable atípica"].value_counts().rename_axis("Variable").reset_index(name="Cantidad")
            grafico = px.bar(conteo, x="Variable", y="Cantidad", title="Cantidad de atípicos por variable")
            st.plotly_chart(grafico, width="stretch")
            st.dataframe(atipicos, width="stretch", hide_index=True)
        st.download_button(
            "Descargar valores atípicos", data=a_csv(atipicos), file_name="valores_atipicos.csv",
            mime="text/csv", disabled=atipicos.empty
        )
    st.caption("Un valor atípico no necesariamente representa un error y requiere interpretación contextual.")

with pestanas[6]:
    st.subheader("Tabla interactiva y ordenable")
    visibles = st.multiselect("Columnas visibles", df.columns, default=list(df.columns))
    if not visibles:
        st.info("Selecciona al menos una columna para mostrar la tabla.")
    else:
        st.dataframe(df[visibles], width="stretch", height=520, hide_index=True)
    st.download_button(
        "Descargar datos filtrados", data=a_csv(df), file_name="datos_filtrados.csv",
        mime="text/csv", key="descarga_tabla"
    )

st.divider()
st.warning(
    "Tratamiento responsable: los datos se procesan durante la sesión de la aplicación. "
    "Evita cargar información personal, confidencial o sensible. Este análisis exploratorio "
    "no reemplaza la interpretación experta. Una correlación no implica causalidad y un valor "
    "atípico no necesariamente representa un error."
)
