# Este es el ultimo codigo que se ha desarrollado 12-06-2026
import streamlit as st
import pandas as pd
from io import BytesIO
import plotly.express as px

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
    
    df["CLASIFICACION_PESO"] = df["PESO NETO UNITARIO"].apply(clasificar_peso)
    df['TOTAL'] = df['BASE'] * IGV
    df.loc[df['MONEDA'] == 'USD', 'TOTAL'] *= TIPO_CAMBIO

    # Limpieza de tipos
    df["MATERIAL"] = df["MATERIAL"].astype(str)
    df["PRODUCTO"] = df["PRODUCTO"].astype(str)
    df["CODIGO PRODUCTO"] = df["CODIGO PRODUCTO"].astype(str)
    df["CLIENTE"] = df["CLIENTE"].astype(str)

    return df

# ----------------------------------------------------------------------
# Clasificación por peso
# ----------------------------------------------------------------------
def clasificar_peso(peso):
    if peso < 10:
        return "Muy pequeños"
    elif peso < 20:
        return "Pequeños"
    elif peso < 50:
        return "Medianos"
    elif peso < 100:
        return "Grandes"
    elif peso < 700:
        return "Muy grandes"
    else:
        return "Jumbo"

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
        # 🚨 VALIDACIÓN DE DATOS
        # ------------------------------------------------------------------
        st.subheader("🚨 Detector de errores")

        inconsistencias = (
            df.groupby(["CLIENTE", "PRODUCTO"])
            .agg({"CODIGO PRODUCTO": "nunique"})
            .reset_index()
        )

        inconsistencias = inconsistencias[
            inconsistencias["CODIGO PRODUCTO"] > 1
        ]

        if not inconsistencias.empty:
            st.warning("⚠️ Se detectaron productos con múltiples códigos (posible inconsistencia)")

            detalle = df.merge(
                inconsistencias[["CLIENTE", "PRODUCTO"]],
                on=["CLIENTE", "PRODUCTO"],
                how="inner"
            )

            st.dataframe(
                detalle[
                    ["CLIENTE", "PRODUCTO", "CODIGO PRODUCTO", "FECHA"]
                ].sort_values(by=["CLIENTE", "PRODUCTO", "FECHA"]),
                width="stretch"
            )
        else:
            st.success("✅ No se detectaron inconsistencias en los productos")

        # ------------------------------------------------------------------
        # 🔵 GLOBAL: FACTURACIÓN POR CLIENTE
        # ------------------------------------------------------------------
        st.subheader("💰 Facturación total por cliente")

        facturacion_clientes = df.groupby("CLIENTE")["TOTAL"].sum().sort_values(ascending=False)

        fig = px.bar(
            facturacion_clientes.head(50).reset_index(),
            x="CLIENTE",
            y="TOTAL",
            title="Top clientes por facturación",
            labels={"TOTAL": "Facturación", "CLIENTE": "Cliente"}
        )

        fig.update_layout(xaxis_tickangle=-45)

        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(facturacion_clientes, width="stretch")
        # 🔽 Preparar para exportación
        facturacion_clientes_export = facturacion_clientes.reset_index()

        # ------------------------------------------------------------------
        # 🔵 GLOBAL: ANÁLISIS POR MATERIAL
        # ------------------------------------------------------------------
        st.subheader("📊 Materiales (Global)")

        material_global = df.groupby("MATERIAL").agg({
            "TOTAL": "sum",
            "PESO_TOTAL": "sum"
        }).rename(columns={
            "TOTAL": "Facturacion",
            "PESO_TOTAL": "Peso"
        }).sort_values(by="Facturacion", ascending=False)

        st.dataframe(material_global, width="stretch")
        
        # 🔽 Preparar para exportación
        material_global_export = material_global.reset_index()
        
        # ------------------------------------------------------------------
        # 🔵 PARETO GLOBAL (80/20)
        # ------------------------------------------------------------------
        st.subheader("📊 Pareto Global de Productos (80/20)")

        pareto_global = (
            df.groupby(["CODIGO PRODUCTO","PRODUCTO"])["TOTAL"]
            .sum()
            .reset_index()
            .sort_values(by="TOTAL", ascending=False)
        )

        # % participación
        pareto_global["%"] = (
            pareto_global["TOTAL"] / pareto_global["TOTAL"].sum()
        ) * 100

        # % acumulado
        pareto_global["% ACUMULADO"] = pareto_global["%"].cumsum()

        # Solo productos dentro del 80%
        pareto_80_global = pareto_global[
            pareto_global["% ACUMULADO"] <= 80
        ]

        # 📊 Gráfico
        fig = px.bar(
            pareto_80_global,
            x="CODIGO PRODUCTO",
            y="TOTAL",
            color="TOTAL",
            hover_data=["PRODUCTO"],
            title="Productos que representan el 80% de la facturación global"
        )

        fig.update_layout(xaxis_tickangle=-45)

        st.plotly_chart(fig, use_container_width=True)

        # 📋 Tabla
        st.dataframe(
            pareto_80_global,
            width="stretch"
        )

        
        # ------------------------------------------------------------------
        # 🔵 CLASIFICACIÓN GLOBAL DE PRODUCTOS POR PESO
        # ------------------------------------------------------------------
        st.subheader("📦 Clasificación Global de Productos por Peso")

        productos_peso_global = (
            df.groupby(
                ["PRODUCTO", "CLASIFICACION_PESO"]
            )
            .agg({
                "PESO NETO UNITARIO": "max",
                "FACTURADO": "sum",
                "TOTAL": "sum"
            })
            .reset_index()
            .rename(columns={
                "PESO NETO UNITARIO": "PESO UNITARIO",
                "FACTURADO": "CANTIDAD VENDIDA",
                "TOTAL": "FACTURACION"
            })
        )

        productos_peso_global = productos_peso_global.sort_values(
            by="PESO UNITARIO",
            ascending=False
        )

        st.dataframe(
            productos_peso_global,
            width="stretch"
        )
        
        st.subheader("📊 Cantidad Vendida por Categoría (Global)")
        cantidad_categoria_global = (
            productos_peso_global.groupby("CLASIFICACION_PESO")["CANTIDAD VENDIDA"]
            .sum()
            .reset_index()
        )
        
        orden = [
            "Muy pequeños",
            "Pequeños",
            "Medianos",
            "Grandes",
            "Muy grandes",
            "Jumbo"
        ]

        cantidad_categoria_global["CLASIFICACION_PESO"] = pd.Categorical(
            cantidad_categoria_global["CLASIFICACION_PESO"],
            categories=orden,
            ordered=True
        )

        cantidad_categoria_global = cantidad_categoria_global.sort_values(
            "CLASIFICACION_PESO"
        )
        
        fig = px.bar(
            cantidad_categoria_global,
            x="CLASIFICACION_PESO",
            y="CANTIDAD VENDIDA",
            color="CANTIDAD VENDIDA",
            title="Cantidad Vendida por Categoría"
        )

        st.plotly_chart(fig, width="stretch")
        
        st.subheader("💰 Facturación por Categoría (Global)")
        
        facturacion_categoria_global = (
            productos_peso_global.groupby("CLASIFICACION_PESO")["FACTURACION"]
            .sum()
            .reset_index()
        )
        
        facturacion_categoria_global["CLASIFICACION_PESO"] = pd.Categorical(
            facturacion_categoria_global["CLASIFICACION_PESO"],
            categories=orden,
            ordered=True
        )

        facturacion_categoria_global = facturacion_categoria_global.sort_values(
            "CLASIFICACION_PESO"
        )
        
        fig = px.bar(
            facturacion_categoria_global,
            x="CLASIFICACION_PESO",
            y="FACTURACION",
            color="FACTURACION",
            title="Facturación por Categoría"
        )

        st.plotly_chart(fig, width="stretch")
        
        st.subheader("⚖️ Peso Total por Categoría (Global)")
        
        peso_categoria_global = (
            df.groupby("CLASIFICACION_PESO")["PESO_TOTAL"]
            .sum()
            .reset_index()
        )
        
        peso_categoria_global["CLASIFICACION_PESO"] = pd.Categorical(
            peso_categoria_global["CLASIFICACION_PESO"],
            categories=orden,
            ordered=True
        )

        peso_categoria_global = peso_categoria_global.sort_values(
            "CLASIFICACION_PESO"
        )
        
        fig = px.bar(
            peso_categoria_global,
            x="CLASIFICACION_PESO",
            y="PESO_TOTAL",
            color="PESO_TOTAL",
            title="Peso Total por Categoría"
        )

        st.plotly_chart(fig, width="stretch")
        
        st.divider()

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
        # 🟢 KPIs
        # ------------------------------------------------------------------
        total_facturacion = resultado["Facturacion"].sum()
        total_peso = resultado["Peso"].sum()
        total_productos = resultado["PRODUCTO"].nunique()

        st.subheader(f"📊 Cliente: {cliente}")
        col1, col2, col3 = st.columns(3)
        

        col1.metric("💰 Facturación Total", f"S/ {total_facturacion:,.2f}")
        col2.metric("⚖️ Peso Total", f"{total_peso:,.2f}")
        col3.metric("📦 Productos", total_productos)

        st.divider()

        # ------------------------------------------------------------------
        # 📊 GRÁFICOS
        # ------------------------------------------------------------------
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📊 Facturación por producto")

            top_productos = (
                resultado
                .sort_values(by="Facturacion", ascending=False)
                .head(50)
            )

            df_plot = top_productos.set_index("PRODUCTO")

            # 👇 FORZAR ORDEN
            df_plot.index = pd.Categorical(
                df_plot.index,
                categories=df_plot.index,
                ordered=True
            )

            st.bar_chart(df_plot["Facturacion"])

        with col2:
            st.subheader("📊 Facturación por material")

            material = resultado.groupby("MATERIAL")["Facturacion"].sum().reset_index()

            material = material.sort_values(by="Facturacion", ascending=False)

            fig = px.bar(
                material,
                x="MATERIAL",
                y="Facturacion",
                color="Facturacion"
            )

            st.plotly_chart(fig, use_container_width=True)
            
        col3 = st.columns(1)[0]
        
        with col3:
            st.subheader("📊 Tabla facturación por material")

            material = (
                resultado
                .groupby("MATERIAL")["Facturacion"]
                .sum()
                .sort_values(ascending=False).head(50)
            )

            # 👇 FORZAR ORDEN
            material.index = pd.Categorical(
                material.index,
                categories=material.index,
                ordered=True
            )

            st.bar_chart(material)

        # ------------------------------------------------------------------
        # 🟢 MATERIAL POR CLIENTE
        # ------------------------------------------------------------------
        st.subheader(f"📊 Materiales para cliente: {cliente}")

        material_cliente = df_filtrado.groupby("MATERIAL").agg({
            "TOTAL": "sum",
            "PESO_TOTAL": "sum"
        }).rename(columns={
            "TOTAL": "Facturacion",
            "PESO_TOTAL": "Peso"
        }).sort_values(by="Facturacion", ascending=False)

        st.dataframe(material_cliente, width="stretch")
        # 🔽 Preparar para exportación
        material_cliente_export = material_cliente.reset_index()
        
        # ------------------------------------------------------------------
        # 📦 CLASIFICACIÓN DE PRODUCTOS POR PESO
        # ------------------------------------------------------------------
        st.subheader("📦 Clasificación de Productos por Peso")

        productos_peso = (
            df_filtrado.groupby(
                ["PRODUCTO", "CLASIFICACION_PESO"]
            )
            .agg({
                "PESO NETO UNITARIO": "max",
                "FACTURADO": "sum",
                "TOTAL": "sum"
            })
            .reset_index()
            .rename(columns={
                "PESO NETO UNITARIO": "PESO UNITARIO",
                "FACTURADO": "CANTIDAD VENDIDA",
                "TOTAL": "FACTURACION"
            })
        )

        productos_peso = productos_peso.sort_values(
            by="PESO UNITARIO",
            ascending=False
        )

        st.dataframe(productos_peso, width="stretch")
        
        # ------------------------------------------------------------------
        # 🟢 CANTIDAD DE PRODUCTOS POR CATEGORÍA
        # ------------------------------------------------------------------
        
        st.subheader("📊 Cantidad de Productos por Categoría")

        cantidad_categoria = (
            productos_peso.groupby("CLASIFICACION_PESO")["CANTIDAD VENDIDA"]
            .sum()
            .reset_index()
        )

        orden = [
            "Muy pequeños",
            "Pequeños",
            "Medianos",
            "Grandes",
            "Muy grandes",
            "Jumbo"
        ]

        cantidad_categoria["CLASIFICACION_PESO"] = pd.Categorical(
            cantidad_categoria["CLASIFICACION_PESO"],
            categories=orden,
            ordered=True
        )

        cantidad_categoria = cantidad_categoria.sort_values(
            "CLASIFICACION_PESO"
        )

        fig = px.bar(
            cantidad_categoria,
            x="CLASIFICACION_PESO",
            y="CANTIDAD VENDIDA",
            color="CANTIDAD VENDIDA",
            title="Cantidad Vendida por Categoría"
        )

        st.plotly_chart(fig, width="stretch")
        
        
        # ------------------------------------------------------------------
        # 🟢 FACTURACIÓN POR CATEGORÍA DE PESO
        # ------------------------------------------------------------------
        st.subheader("💰 Facturación por Categoría de Peso")

        facturacion_categoria = (
            productos_peso.groupby("CLASIFICACION_PESO")["FACTURACION"]
            .sum()
            .reset_index()
        )

        facturacion_categoria["CLASIFICACION_PESO"] = pd.Categorical(
            facturacion_categoria["CLASIFICACION_PESO"],
            categories=orden,
            ordered=True
        )

        facturacion_categoria = facturacion_categoria.sort_values(
            "CLASIFICACION_PESO"
        )

        fig = px.bar(
            facturacion_categoria,
            x="CLASIFICACION_PESO",
            y="FACTURACION",
            color="FACTURACION",
            title="Facturación por Categoría"
        )

        st.plotly_chart(fig, width="stretch")

        st.dataframe(
            facturacion_categoria,
            width="stretch"
        )
        
        
        
        # ------------------------------------------------------------------
        # 🟢 PARETO CLIENTE (80/20)
        # ------------------------------------------------------------------
        st.subheader(f"📊 Pareto de Productos - Cliente: {cliente}")

        pareto_cliente = (
            df_filtrado.groupby(["CODIGO PRODUCTO","PRODUCTO"])["TOTAL"]
            .sum()
            .reset_index()
            .sort_values(by="TOTAL", ascending=False)
        )

        # %
        pareto_cliente["%"] = (
            pareto_cliente["TOTAL"] / pareto_cliente["TOTAL"].sum()
        ) * 100

        # % acumulado
        pareto_cliente["% ACUMULADO"] = pareto_cliente["%"].cumsum()

        # 80%
        pareto_80_cliente = pareto_cliente[
            pareto_cliente["% ACUMULADO"] <= 80
        ]

        # 📊 Gráfico
        fig = px.bar(
            pareto_80_cliente,
            x="CODIGO PRODUCTO",
            y="TOTAL",
            color="TOTAL",
            hover_data=["PRODUCTO"],
            title=f"Productos que representan el 80% de {cliente}"
        )

        fig.update_layout(xaxis_tickangle=-45)

        st.plotly_chart(fig, use_container_width=True)

        # 📋 Tabla
        st.dataframe(
            pareto_80_cliente,
            width="stretch"
        )

        # ------------------------------------------------------------------
        # 📈 EVOLUCIÓN
        # ------------------------------------------------------------------
        st.subheader("📈 Evolución de ventas por año (Cantidad de Productos)")

        ventas_anuales = resultado[[2020, 2021, 2022, 2023, 2024, 2025, 2026]].sum().reset_index()
        ventas_anuales.columns = ["AÑO", "Cantidad"]

        fig = px.line(
            ventas_anuales,
            x="AÑO",
            y="Cantidad",
            markers=True,
            title="Evolución anual"
        )

        st.plotly_chart(fig, use_container_width=True)
        
        # ------------------------------------------------------------------
        # 🏆 TOP PRODUCTOS
        # ------------------------------------------------------------------
        st.subheader("🏆 Top productos")

        top = resultado.sort_values(
            by="Facturacion", ascending=False
        ).head(10)

        st.dataframe(top, use_container_width=True)

        # ------------------------------------------------------------------
        # 📋 TABLA FINAL
        # ------------------------------------------------------------------
        st.subheader("📋 Detalle completo")
        st.dataframe(resultado, width="stretch")

        # ------------------------------------------------------------------
        # 📥 DESCARGA
        # ------------------------------------------------------------------
        def convertir_a_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Reporte')
            return output.getvalue()

        excel_data = convertir_a_excel(resultado)
        excel_material_cliente = convertir_a_excel(material_cliente_export)
        excel_material_global = convertir_a_excel(material_global_export)
        excel_facturacion_clientes = convertir_a_excel(facturacion_clientes_export)

        # 🔽 Botones (ordenados)
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.download_button(
                label="📥 Reporte cliente",
                data=excel_data,
                file_name=f"reporte_{cliente}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with col2:
            st.download_button(
                label="📥 Material cliente",
                data=excel_material_cliente,
                file_name=f"material_cliente_{cliente}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with col3:
            st.download_button(
                label="📥 Material global",
                data=excel_material_global,
                file_name="material_global.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with col4:
            st.download_button(
                label="📥 Facturación Global",
                data=excel_facturacion_clientes,
                file_name=f"facturacion_global_por_clientes.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Error: {str(e)}")