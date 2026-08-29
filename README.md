# Explorador automático de datos

Aplicación web en Streamlit para cargar archivos CSV, XLSX o XLS y realizar automáticamente un análisis exploratorio de datos sin depender de un dataset predeterminado.

## Funcionalidades

- Carga de archivos desde el navegador y lectura en memoria.
- Limpieza de espacios en encabezados y reconocimiento prudente de columnas de fecha.
- Indicadores de filas, columnas, duplicados y celdas faltantes.
- Clasificación analítica de variables.
- Análisis de duplicados y valores faltantes.
- Estadísticas descriptivas numéricas y categóricas.
- Histogramas, diagramas de caja y gráficos de frecuencia con Plotly.
- Correlaciones de Pearson, Spearman y Kendall.
- Detección de valores atípicos mediante el método IQR.
- Filtros por fecha, categorías y rangos numéricos.
- Tabla interactiva, selección de columnas y descargas CSV con UTF-8 BOM.
- Interfaz completamente en español.

## Formatos admitidos

- `.csv`
- `.xlsx`, leído con `openpyxl`
- `.xls`, leído con `xlrd`

La aplicación analiza la primera hoja de los libros de Excel.

## Estructura del repositorio

```text
explorador-automatico-datos/
├── app.py
├── requirements.txt
└── README.md
```

No se incluye ningún dataset.

## Instalación

Se recomienda Python 3.11 o 3.12.

```bash
git clone https://github.com/TU-USUARIO/explorador-automatico-datos.git
cd explorador-automatico-datos
python -m venv .venv
```

Activa el entorno virtual:

**Windows PowerShell**

```powershell
.venv\Scripts\Activate.ps1
```

**macOS o Linux**

```bash
source .venv/bin/activate
```

Instala las dependencias:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Ejecución local

Desde la raíz del repositorio:

```bash
streamlit run app.py
```

Abre la dirección local mostrada por Streamlit, normalmente `http://localhost:8501`.

## Despliegue en Streamlit Community Cloud

1. Crea un repositorio en GitHub.
2. Sube `app.py`, `requirements.txt` y `README.md` a la raíz.
3. Inicia sesión en [Streamlit Community Cloud](https://share.streamlit.io/).
4. Selecciona **Create app**.
5. Elige el repositorio, la rama y `app.py` como archivo principal.
6. En la configuración avanzada, selecciona una versión de Python compatible, preferiblemente 3.12.
7. Selecciona **Deploy** y revisa los registros si la instalación falla.

La aplicación no necesita secretos, contraseñas ni variables de entorno.

## Privacidad y uso responsable

Los archivos se procesan durante la sesión y la aplicación no los guarda permanentemente. Aun así, evita cargar datos personales, sensibles, confidenciales o sujetos a restricciones legales. El análisis es exploratorio, no sustituye el criterio experto, una correlación no implica causalidad y un valor atípico no necesariamente es un error.

## Limitaciones conocidas

- En Excel se analiza únicamente la primera hoja.
- La inferencia de fechas se aplica a columnas cuyo nombre incluye `fecha` o `date` y solo se conserva si la conversión resulta suficientemente consistente.
- Los archivos grandes dependen de la memoria y del límite de carga configurado en Streamlit.
- Las correlaciones y el cálculo de Kendall pueden ser lentos en datasets grandes.
- Las variables categóricas con más de 30 categorías muestran solo las 30 más frecuentes en el gráfico.
- El método IQR puede no ser apropiado para todas las distribuciones o áreas de conocimiento.
- Los filtros categóricos conservan las categorías seleccionadas; los filtros numéricos y de fecha conservan valores faltantes según el diseño solicitado.

## Solución rápida de problemas

- Si un CSV aparece en una sola columna, verifica su separador y codificación.
- Si un XLS no abre, confirma que sea un archivo Excel binario válido y que `xlrd` esté instalado.
- Si el despliegue falla, consulta los logs de Community Cloud y revisa `requirements.txt`.
- Si no hay resultados, restablece o amplía los filtros laterales.
