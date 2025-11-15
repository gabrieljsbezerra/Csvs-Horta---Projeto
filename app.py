import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

DATA_DIR = Path(__file__).parent

st.set_page_config(layout="wide", page_title="Horta Escolar - Painel")

st.title("🌱 Horta Escolar — Painel Interativo")

# Load data
@st.cache_data
def load():
    canteiros = pd.read_csv(DATA_DIR/"canteiros.csv", parse_dates=[])
    especies = pd.read_csv(DATA_DIR/"especies.csv")
    plantios = pd.read_csv(DATA_DIR/"plantios.csv", parse_dates=["data_plantio"])
    observ = pd.read_csv(DATA_DIR/"observacoes.csv", parse_dates=["data_observacao"])
    colheitas = pd.read_csv(DATA_DIR/"colheitas.csv", parse_dates=["data_colheita"])
    eventos = pd.read_csv(DATA_DIR/"eventos_manejo.csv", parse_dates=["data_evento"])
    return canteiros, especies, plantios, observ, colheitas, eventos

canteiros, especies, plantios, observ, colheitas, eventos = load()

# KPIs
total_colhido = colheitas['quantidade_colhida'].sum() if not colheitas.empty else 0
num_plantios = plantios.shape[0]
plantios_colhidos = colheitas['plantio_id'].nunique()
taxa_sucesso = (plantios_colhidos / num_plantios) if num_plantios>0 else 0

k1, k2, k3 = st.columns(3)
k1.metric("Total colhido (kg/unid)", f"{total_colhido:.1f}")
k2.metric("Plantios cadastrados", f"{num_plantios}")
k3.metric("Plantios com colheita", f"{plantios_colhidos} ({taxa_sucesso:.0%})")

# Filters
with st.sidebar:
    st.header("Filtros")
    periodo = st.date_input("Período (início, fim)", value=(pd.to_datetime("2025-07-01").date(), pd.to_datetime("2025-12-31").date()))
    especie_sel = st.selectbox("Espécie", options=["Todas"] + especies['nome_comum'].tolist())
    canteiro_sel = st.selectbox("Canteiro", options=["Todos"] + canteiros['nome'].tolist())
    mostrar_mapa = st.checkbox("Mostrar mapa esquemático (grid)", value=True)

# Apply filters
p = plantios.copy()
if especie_sel and especie_sel!="Todas":
    ids = especies.loc[especies['nome_comum']==especie_sel,'especie_id']
    if not ids.empty:
        p = p[p['especie_id']==int(ids.iloc[0])]
if canteiro_sel and canteiro_sel!="Todos":
    cid = canteiros.loc[canteiros['nome']==canteiro_sel,'canteiro_id']
    if not cid.empty:
        p = p[p['canteiro_id']==int(cid.iloc[0])]

start_date, end_date = periodo
p = p[(pd.to_datetime(p['data_plantio']).dt.date >= start_date) & (pd.to_datetime(p['data_plantio']).dt.date <= end_date)]

# Left column: map schematic (simple)
left, right = st.columns([1,2])
with left:
    st.subheader("Mapa esquemático")
    if mostrar_mapa:
        # Simple grid of canteiros
        grid = canteiros[['nome','localizacao','area_m2']].copy()
        st.table(grid)

with right:
    st.subheader("Produção por espécie")
    prod = colheitas.merge(plantios, on='plantio_id', how='left').merge(especies, on='especie_id', how='left')
    if especie_sel!="Todas":
        prod = prod[prod['nome_comum']==especie_sel]
    prod_sum = prod.groupby('nome_comum', dropna=False).quantidade_colhida.sum().reset_index().sort_values('quantidade_colhida', ascending=False)
    if prod_sum.empty:
        st.info("Sem dados de colheita para os filtros aplicados.")
    else:
        fig = px.bar(prod_sum, x='nome_comum', y='quantidade_colhida', title="Produção (soma)")
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("Linha de crescimento média por espécie")
# growth chart: average altura over time for selected especie
obs = observ.merge(plantios[['plantio_id','especie_id']], on='plantio_id', how='left').merge(especies, on='especie_id', how='left')
if especie_sel!="Todas":
    obs = obs[obs['nome_comum']==especie_sel]
if obs.empty:
    st.info("Sem observações para os filtros aplicados.")
else:
    avg = obs.groupby('data_observacao').altura_cm.mean().reset_index()
    fig2 = px.line(avg, x='data_observacao', y='altura_cm', markers=True, title="Altura média (cm) ao longo do tempo")
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("### Tabelas (visualização rápida)")
st.dataframe(plantios.head(50))
st.caption("Arquivos usados: canteiros.csv, especies.csv, plantios.csv, observacoes.csv, colheitas.csv, eventos_manejo.csv")
