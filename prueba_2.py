import streamlit as st
import pandas as pd
from io import BytesIO

# ----------------------------------------------------------------------
# Parámetros de negocio
# ----------------------------------------------------------------------
TIPO_CAMBIO = 3.4
IGV = 1.18

# ----------------------------------------------------------------------
# Mapeo de columnas
# ----------------------------------------------------------------------
COLUMN_MAP = {
    "Referencia del pedido/Fecha confirmación": "FECHA",
    "Producto/Nombre": "PRODUCTO",
    "Producto/Referencia interna": "CODIGO PRODUCTO",
    "Producto/Producto/Material": "MATERIAL",
    "Cliente/Entidad del nombre de la compañía": "CLIENTE",
    "Facturado": "FACTURADO",
    "Producto/Peso Neto Real": "PESO NETO UNITARIO",
    "Precio unitario": "PRECIO UNITARIO",
    "Moneda/Moneda": "MONEDA",
}

# ----------------------------------------------------------------------
# Funciones
# ----------------------------------------------------------------------
def renombrar_columnas(df):
    missing = [col for col in COLUMN_MAP if col not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas en el Excel: {missing}")

    return df.rename(columns=COLUMN_MAP)


def procesar_df(df):
    df = renombrar_columnas(df)

    df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
    df['AÑO'] = df['FECHA'].dt.year

    df['PESO_TOTAL'] = df['FACTURADO'] * df['PESO NETO UNITARIO']
    df['BASE'] = df['FACTURADO'] * df['PRECIO UNITARIO']
    df['TOTAL'] = df['BASE'] * IGV
    df.loc[df['MONEDA'] == 'USD', 'TOTAL'] *= TIPO_CAMBIO

    return df


# ----------------------------------------------------------------------
# APP
# ----------------------------------------------------------------------
st.set_page_config(page_title="Dashboard de Ventas", layout="wide")

st.title("📊 STEEL J.R.V S.A.C.")

archivo = st.file_uploader("Sube tu Excel de Odoo", type=["xlsx", "xls"])

if archivo:
    try:
        df = pd.read_excel(archivo)
        df = procesar_df(df)

        st.success("Archivo procesado correctamente")

        # ------------------------------------------------------------------
        # 🎛️ FILTROS
        # ------------------------------------------------------------------
        st.sidebar.header("Filtros")

        clientes = df["CLIENTE"].dropna().unique()
        cliente = st.sidebar.selectbox("Cliente", clientes)

        df_filtrado = df[df["CLIENTE"] == cliente]

        # ------------------------------------------------------------------
        # 📊 PROCESAMIENTO
        # ------------------------------------------------------------------
        pivot = df_filtrado.pivot_table(
            index=['PRODUCTO', 'CODIGO PRODUCTO', 'MATERIAL'],
            columns='AÑO',
            values='FACTURADO',
            aggfunc='sum',
            fill_value=0
        )

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
        # 🔝 KPIs
        # ------------------------------------------------------------------
        total_facturacion = resultado["Facturacion"].sum()
        total_peso = resultado["Peso"].sum()
        total_productos = resultado["PRODUCTO"].nunique()

        col1, col2, col3 = st.columns(3)

        col1.metric("💰 Facturación Total", f"S/ {total_facturacion:,.2f}")
        col2.metric("⚖️ Peso Total", f"{total_peso:,.2f}")
        col3.metric("📦 Productos", total_productos)

        st.divider()

        # ------------------------------------------------------------------
        # 📊 GRÁFICOS PRINCIPALES
        # ------------------------------------------------------------------
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📊 Facturación por producto")
            top_productos = resultado.sort_values(
                by="Facturacion", ascending=False
            ).head(10)

            st.bar_chart(
                top_productos.set_index("PRODUCTO")["Facturacion"]
            )

        with col2:
            st.subheader("📊 Facturación por material")
            material = resultado.groupby("MATERIAL")["Facturacion"].sum()

            st.bar_chart(material)

        # ------------------------------------------------------------------
        # 📈 EVOLUCIÓN
        # ------------------------------------------------------------------
        st.subheader("📈 Evolución de ventas por año")

        ventas_anuales = resultado[
            [2020, 2021, 2022, 2023, 2024, 2025, 2026]
        ].sum()

        st.line_chart(ventas_anuales)

        # ------------------------------------------------------------------
        # 🏆 TOP PRODUCTOS
        # ------------------------------------------------------------------
        st.subheader("🏆 Top productos")

        top = resultado.sort_values(
            by="Facturacion", ascending=False
        ).head(10)

        st.dataframe(top, use_container_width=True)

        # ------------------------------------------------------------------
        # 📋 TABLA COMPLETA
        # ------------------------------------------------------------------
        st.subheader("📋 Detalle completo")

        st.dataframe(resultado, use_container_width=True)

        # ------------------------------------------------------------------
        # 📥 DESCARGA
        # ------------------------------------------------------------------
        def convertir_a_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Reporte')
            return output.getvalue()
        
        excel_data = convertir_a_excel(resultado)
        
        st.download_button(
            label="📥 Descargar en Excel",
            data=excel_data,
            file_name=f"reporte_{cliente}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"Error: {str(e)}")