import streamlit as st
import pandas as pd

# ----------------------------------------------------------------------
# Parámetros de negocio
# ----------------------------------------------------------------------
TIPO_CAMBIO = 3.4
IGV = 1.18

# ----------------------------------------------------------------------
# Mapeo de columnas (igual que tu script + CLIENTE agregado)
# ----------------------------------------------------------------------
COLUMN_MAP = {
    "Referencia del pedido/Fecha confirmación": "FECHA",
    "Producto/Nombre": "PRODUCTO",
    "Producto/Referencia interna": "CODIGO PRODUCTO",
    "Producto/Producto/Material": "MATERIAL",
    "Cliente/Entidad del nombre de la compañía": "CLIENTE",  # 🔥 NUEVO
    "Facturado": "FACTURADO",
    "Producto/Peso Neto Real": "PESO NETO UNITARIO",
    "Precio unitario": "PRECIO UNITARIO",
    "Moneda/Moneda": "MONEDA",
}

# ----------------------------------------------------------------------
# Función para renombrar columnas
# ----------------------------------------------------------------------
def renombrar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    missing = [col for col in COLUMN_MAP if col not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas en el Excel: {missing}")

    rename_dict = {col: COLUMN_MAP[col] for col in COLUMN_MAP}
    df = df.rename(columns=rename_dict)

    return df

# ----------------------------------------------------------------------
# Procesamiento (tu lógica)
# ----------------------------------------------------------------------
def procesar_df(df: pd.DataFrame) -> pd.DataFrame:
    df = renombrar_columnas(df)

    df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
    df['AÑO'] = df['FECHA'].dt.year

    df['PESO_TOTAL'] = df['FACTURADO'] * df['PESO NETO UNITARIO']
    df['BASE'] = df['FACTURADO'] * df['PRECIO UNITARIO']
    df['TOTAL'] = df['BASE'] * IGV

    # Conversión USD → PEN
    df.loc[df['MONEDA'] == 'USD', 'TOTAL'] *= TIPO_CAMBIO

    return df

# ----------------------------------------------------------------------
# APP STREAMLIT
# ----------------------------------------------------------------------
st.set_page_config(page_title="Dashboard de Ventas", layout="wide")

st.title("📊 STEEL J.R.V S.A.C.")

# 📂 Subida de archivo
archivo = st.file_uploader("Sube tu Excel de Odoo", type=["xlsx", "xls"])

if archivo:
    try:
        df = pd.read_excel(archivo)

        # Procesar datos
        df = procesar_df(df)

        st.success("Archivo procesado correctamente")

        # ------------------------------------------------------------------
        # 🔽 FILTROS
        # ------------------------------------------------------------------
        st.sidebar.header("Filtros")

        # Cliente
        clientes = df["CLIENTE"].dropna().unique()
        cliente = st.sidebar.selectbox("Selecciona cliente", clientes)

        df_filtrado = df[df["CLIENTE"] == cliente]

        # ------------------------------------------------------------------
        # 📊 PROCESAMIENTO FINAL (igual que tu script)
        # ------------------------------------------------------------------
        pivot = df_filtrado.pivot_table(
            index=['PRODUCTO', 'CODIGO PRODUCTO', 'MATERIAL'],
            columns='AÑO',
            values='FACTURADO',
            aggfunc='sum',
            fill_value=0
        )

        # Asegurar años
        for año in range(2020, 2027):
            pivot[año] = pivot.get(año, 0)

        pivot = pivot[[2020, 2021, 2022, 2023, 2024, 2025, 2026]]

        peso = df_filtrado.groupby(
            ['PRODUCTO', 'CODIGO PRODUCTO', 'MATERIAL']
        )['PESO_TOTAL'].sum()

        facturacion = df_filtrado.groupby(
            ['PRODUCTO', 'CODIGO PRODUCTO', 'MATERIAL']
        )['TOTAL'].sum()

        resultado = pivot.copy()
        resultado['Peso'] = peso
        resultado['Facturacion'] = facturacion
        resultado = resultado.reset_index()

        # ------------------------------------------------------------------
        # 📈 MOSTRAR RESULTADOS
        # ------------------------------------------------------------------
        st.subheader(f"📋 Resultado para cliente: {cliente}")
        st.dataframe(resultado, use_container_width=True)

        # Gráfico
        st.subheader("📊 Facturación por producto")
        st.bar_chart(resultado.set_index("PRODUCTO")["Facturacion"])

        # ------------------------------------------------------------------
        # 📥 DESCARGA
        # ------------------------------------------------------------------
        st.download_button(
            label="📥 Descargar resultado en Excel",
            data=resultado.to_csv(index=False).encode('utf-8'),
            file_name=f"reporte_{cliente}.csv",
            mime='text/csv'
        )

    except Exception as e:
        st.error(f"Error: {str(e)}")