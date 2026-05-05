import streamlit as st
import pandas as pd
from io import BytesIO
import plotly.express as px

# ----------------------------------------------------------------------
# Parámetros
# ----------------------------------------------------------------------
TIPO_CAMBIO = 3.4
IGV = 1.18

# ----------------------------------------------------------------------
# Mapeo
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
        raise ValueError(f"Faltan columnas: {missing}")
    return df.rename(columns=COLUMN_MAP)


def procesar_df(df):
    df = renombrar_columnas(df)

    df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
    df['AÑO'] = df['FECHA'].dt.year

    df['PESO_TOTAL'] = df['FACTURADO'] * df['PESO NETO UNITARIO']
    df['BASE'] = df['FACTURADO'] * df['PRECIO UNITARIO']
    df['TOTAL'] = df['BASE'] * IGV
    df.loc[df['MONEDA'] == 'USD', 'TOTAL'] *= TIPO_CAMBIO

    # Limpieza
    for col in ["MATERIAL", "PRODUCTO", "CODIGO PRODUCTO", "CLIENTE"]:
        df[col] = df[col].astype(str)

    return df

# ----------------------------------------------------------------------
# APP
# ----------------------------------------------------------------------
st.set_page_config(page_title="Dashboard Ventas", layout="wide")
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

        # 📅 Filtro fechas
        fecha_min = df["FECHA"].min()
        fecha_max = df["FECHA"].max()

        rango = st.sidebar.date_input("Rango de fechas", [fecha_min, fecha_max])

        df = df[
            (df["FECHA"] >= pd.to_datetime(rango[0])) &
            (df["FECHA"] <= pd.to_datetime(rango[1]))
        ]

        # 👥 Multiselect clientes
        clientes = st.sidebar.multiselect(
            "Clientes",
            df["CLIENTE"].unique()
        )

        if clientes:
            df_filtrado = df[df["CLIENTE"].isin(clientes)]
        else:
            df_filtrado = df

        # ------------------------------------------------------------------
        # 🔵 FACTURACIÓN CLIENTES (GLOBAL)
        # ------------------------------------------------------------------
        st.subheader("💰 Facturación por cliente")

        facturacion_clientes = df.groupby("CLIENTE")["TOTAL"].sum().sort_values(ascending=False)
        fc_df = facturacion_clientes.reset_index()

        fig = px.bar(fc_df.head(350), x="CLIENTE", y="TOTAL", title="Top clientes")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(fc_df.head(350), width="stretch")

        # ------------------------------------------------------------------
        # 🔵 MATERIAL GLOBAL
        # ------------------------------------------------------------------
        material_global = df.groupby("MATERIAL").agg({
            "TOTAL": "sum",
            "PESO_TOTAL": "sum"
        }).rename(columns={"TOTAL": "Facturacion", "PESO_TOTAL": "Peso"})

        st.subheader("📊 Materiales (Global)")
        st.dataframe(material_global)

        # ------------------------------------------------------------------
        # 🟢 RESULTADO CLIENTES
        # ------------------------------------------------------------------
        resultado = df_filtrado.groupby(
            ["PRODUCTO", "CODIGO PRODUCTO", "MATERIAL"]
        ).agg({
            "FACTURADO": "sum",
            "PESO_TOTAL": "sum",
            "TOTAL": "sum"
        }).rename(columns={
            "PESO_TOTAL": "Peso",
            "TOTAL": "Facturacion"
        }).reset_index()

        # KPIs
        total_fact = resultado["Facturacion"].sum()
        total_peso = resultado["Peso"].sum()
        total_productos = resultado["PRODUCTO"].nunique()

        col1, col2, col3 = st.columns(3)
        col1.metric("💰 Facturación", f"S/ {total_fact:,.2f}")
        col2.metric("⚖️ Peso", f"{total_peso:,.2f}")
        col3.metric("📦 Productos únicos", f"{total_productos}")

        # ------------------------------------------------------------------
        # 📊 GRÁFICOS PLOTLY
        # ------------------------------------------------------------------
        col1, col2 = st.columns(2)

        with col1:
            top_prod = resultado.sort_values("Facturacion", ascending=False).head(10)
            fig = px.bar(top_prod, x="PRODUCTO", y="Facturacion", title="Top productos")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            mat = resultado.groupby("MATERIAL")["Facturacion"].sum().reset_index()
            fig = px.bar(mat, x="MATERIAL", y="Facturacion", title="Material")
            st.plotly_chart(fig, use_container_width=True)

        # ------------------------------------------------------------------
        # 📈 EVOLUCIÓN
        # ------------------------------------------------------------------
        ventas_anuales = df_filtrado.groupby("AÑO")["TOTAL"].sum().reset_index()
        st.subheader("📈 Evolución de ventas por año")
        fig = px.line(ventas_anuales, x="AÑO", y="TOTAL", markers=True)
        st.plotly_chart(fig, use_container_width=True)

        # KPI crecimiento
        if len(ventas_anuales) > 1:
            crecimiento = (
                (ventas_anuales.iloc[-1]["TOTAL"] - ventas_anuales.iloc[-2]["TOTAL"]) /
                ventas_anuales.iloc[-2]["TOTAL"]
            ) * 100

            st.metric("📈 Crecimiento último año", f"{crecimiento:.2f}%")

        # ------------------------------------------------------------------
        # 📋 TABLA
        # ------------------------------------------------------------------
        st.subheader("📋 Detalle")
        st.dataframe(resultado, width="stretch")

        # ------------------------------------------------------------------
        # 📥 EXPORT
        # ------------------------------------------------------------------
        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False)
            return output.getvalue()

        st.download_button(
            "📥 Descargar Excel",
            data=to_excel(resultado),
            file_name="reporte.xlsx"
        )

    except Exception as e:
        st.error(str(e))