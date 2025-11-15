# app.py (versão enriquecida)
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import numpy as np
import datetime
import os

# -----------------------
# Configuração e carreg.
# -----------------------
st.set_page_config(layout="wide", page_title="Horta Escolar - Painel V2")

DATA_DIR = Path(__file__).parent

@st.cache_data
def load_data():
    # tenta carregar os CSVs, se algum estiver faltando avisa
    files = {
        "canteiros": DATA_DIR / "canteiros.csv",
        "especies": DATA_DIR / "especies.csv",
        "plantios": DATA_DIR / "plantios.csv",
        "observacoes": DATA_DIR / "observacoes.csv",
        "colheitas": DATA_DIR / "colheitas.csv",
        "eventos": DATA_DIR / "eventos_manejo.csv",
    }
    for name, f in files.items():
        if not f.exists():
            st.error(f"Arquivo ausente: {f.name}. Coloque-o na mesma pasta do app.py")
    canteiros = pd.read_csv(files["canteiros"])
    especies = pd.read_csv(files["especies"])
    plantios = pd.read_csv(files["plantios"], parse_dates=["data_plantio"])
    observ = pd.read_csv(files["observacoes"], parse_dates=["data_observacao"])
    colheitas = pd.read_csv(files["colheitas"], parse_dates=["data_colheita"])
    eventos = pd.read_csv(files["eventos"], parse_dates=["data_evento"])
    return canteiros, especies, plantios, observ, colheitas, eventos

canteiros, especies, plantios, observ, colheitas, eventos = load_data()

# Normalize column names (caso)
plantios.columns = [c.strip() for c in plantios.columns]
observ.columns = [c.strip() for c in observ.columns]
colheitas.columns = [c.strip() for c in colheitas.columns]
eventos.columns = [c.strip() for c in eventos.columns]

# Join helpers
plantios = plantios.merge(canteiros[['canteiro_id','nome']].rename(columns={'nome':'canteiro_nome'}), on='canteiro_id', how='left')
plantios = plantios.merge(especies[['especie_id','nome_comum']].rename(columns={'nome_comum':'especie_nome'}), on='especie_id', how='left')

# -----------------------
# Sidebar: filtros
# -----------------------
st.sidebar.header("Filtros")
today = datetime.date.today()
default_start = (pd.to_datetime(plantios['data_plantio']).min().date()
                 if not plantios.empty else today - datetime.timedelta(days=180))
default_end = today + datetime.timedelta(days=30)
period = st.sidebar.date_input("Período plantio (início, fim)", value=(default_start, default_end))

especie_options = ["Todas"] + sorted(especies['nome_comum'].astype(str).unique().tolist())
especie_sel = st.sidebar.selectbox("Espécie", especie_options)

canteiro_options = ["Todos"] + sorted(canteiros['nome'].astype(str).unique().tolist())
canteiro_sel = st.sidebar.selectbox("Canteiro", canteiro_options)

responsavel_options = ["Todos"] + sorted(plantios['responsavel'].fillna("N/A").unique().tolist())
responsavel_sel = st.sidebar.selectbox("Responsável", responsavel_options)

metodo_options = ["Todos"] + sorted(plantios['metodo'].fillna("N/A").unique().tolist())
metodo_sel = st.sidebar.selectbox("Método de plantio", metodo_options)

tipo_evento_options = ["Todos"] + sorted(eventos['tipo_evento'].fillna("N/A").unique().tolist())
tipo_evento_sel = st.sidebar.selectbox("Tipo de evento (mecanização)", tipo_evento_options)

only_active = st.sidebar.checkbox("Mostrar apenas plantios sem colheita (ativos)", value=False)
search_text = st.sidebar.text_input("Buscar em notas / observações (palavra)", value="")

st.sidebar.markdown("---")
st.sidebar.info("Use filtros para ajustar período, canteiro, espécie e explorar os dados.\nVocê pode fazer upload de fotos para cada plantio na aba 'Fotos'.")

# -----------------------
# Filtragem dos plantios
# -----------------------
start_date, end_date = period
mask = (pd.to_datetime(plantios['data_plantio']).dt.date >= start_date) & (pd.to_datetime(plantios['data_plantio']).dt.date <= end_date)
p = plantios[mask].copy()

if especie_sel != "Todas":
    p = p[p['especie_nome'] == especie_sel]
if canteiro_sel != "Todos":
    p = p[p['canteiro_nome'] == canteiro_sel]
if responsavel_sel != "Todos":
    p = p[p['responsavel'] == responsavel_sel]
if metodo_sel != "Todos":
    p = p[p['metodo'] == metodo_sel]
if only_active:
    # plantios sem registro de colheita
    harvested_ids = colheitas['plantio_id'].unique().tolist()
    p = p[~p['plantio_id'].isin(harvested_ids)]
if search_text.strip() != "":
    s = search_text.strip().lower()
    # busca em notas do plantio e em observações
    p_mask = p['notas'].fillna("").str.lower().str.contains(s)
    obs_mask = observ['comentarios'].fillna("").str.lower().str.contains(s)
    plantios_with_obs = observ.loc[obs_mask, 'plantio_id'].unique()
    p = p[p_mask | p['plantio_id'].isin(plantios_with_obs)]

# -----------------------
# Top KPIs
# -----------------------
col1, col2, col3, col4, col5 = st.columns([1,1,1,1,1])
total_colhido = colheitas['quantidade_colhida'].sum() if not colheitas.empty else 0
num_plantios = plantios.shape[0]
plantios_com_colheita = colheitas['plantio_id'].nunique() if not colheitas.empty else 0
k_media_por_plantio = (colheitas.groupby('plantio_id').quantidade_colhida.sum().mean() 
                      if not colheitas.empty else 0)
num_observacoes = observ.shape[0]
pragas_pct = (observ['pragas_observadas'].sum()/num_observacoes) if num_observacoes>0 else 0

col1.metric("Total colhido (soma)", f"{total_colhido:.1f}")
col2.metric("Plantios cadastrados", f"{num_plantios}")
col3.metric("Plantios com colheita", f"{plantios_com_colheita} ({(plantios_com_colheita/num_plantios if num_plantios>0 else 0):.0%})")
col4.metric("Média colhida por plantio", f"{k_media_por_plantio:.1f}")
col5.metric("Observações registradas", f"{num_observacoes} — pragas: {pragas_pct:.0%}")

st.markdown("---")

# -----------------------
# Layout principal
# -----------------------
left_col, mid_col, right_col = st.columns([1.2,1.5,1])

# ---------- MAPA ESQUEMÁTICO (grid) ----------
with left_col:
    st.subheader("Mapa esquemático da horta")
    # Criar um status por canteiro: sucesso média (plantios com colheita/total)
    status = []
    for _, c in canteiros.iterrows():
        cid = c['canteiro_id']
        total = plantios[plantios['canteiro_id']==cid].shape[0]
        colh = colheitas.merge(plantios[['plantio_id','canteiro_id']], on='plantio_id', how='right')
        colh_cnt = colh[colh['canteiro_id']==cid]['plantio_id'].nunique()
        taxa = (colh_cnt / total) if total>0 else 0
        status.append({"canteiro": c['nome'], "area": c.get('area_m2', ''), "taxa_sucesso": taxa, "total": total, "colh": colh_cnt})
    status_df = pd.DataFrame(status)
    # Mostrar em grid simples: 2 colunas
    n = len(status_df)
    cols = st.columns(2)
    for i, row in status_df.iterrows():
        target = cols[i % 2]
        with target:
            color = "#2ECC71" if row['taxa_sucesso']>=0.6 else ("#F1C40F" if row['taxa_sucesso']>=0.25 else "#E74C3C")
            st.markdown(f"""
                <div style="border-radius:12px;padding:12px;background:{color};color:white">
                <h4 style="margin:4px">{row['canteiro']}</h4>
                <div>Área: {row['area']} m²</div>
                <div>Plantios: {int(row['total'])} • Colheitas: {int(row['colh'])}</div>
                <div>Sucesso: {row['taxa_sucesso']:.0%}</div>
                </div>
            """, unsafe_allow_html=True)

    st.markdown("**Legenda:** verde = boa taxa de sucesso • amarelo = atenção • vermelho = precisa ação")

# ---------- Produção por espécie / histograma de colheitas ----------
with mid_col:
    st.subheader("Produção por espécie / Distribuição das colheitas")
    prod = colheitas.merge(plantios[['plantio_id','especie_id']], on='plantio_id', how='left').merge(especies[['especie_id','nome_comum']], on='especie_id', how='left')
    if especie_sel != "Todas":
        prod = prod[prod['nome_comum']==especie_sel]
    prod_sum = prod.groupby('nome_comum').quantidade_colhida.sum().reset_index().sort_values('quantidade_colhida', ascending=False)
    if not prod_sum.empty:
        fig = px.bar(prod_sum, x='nome_comum', y='quantidade_colhida', title="Produção total por espécie", labels={'nome_comum':'Espécie','quantidade_colhida':'Quantidade'})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados de colheita para os filtros selecionados.")

    st.markdown("### Distribuição de tamanhos de colheita")
    if not prod.empty:
        fig2 = px.histogram(prod, x='quantidade_colhida', nbins=20, title="Histograma de quantidades colhidas")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Sem registros de colheita para gerar histograma.")

# ---------- Heatmap de eventos (canterio x dia) ----------
with right_col:
    st.subheader("Eventos de manejo (heatmap)")
    ev = eventos.copy()
    if tipo_evento_sel != "Todos":
        ev = ev[ev['tipo_evento']==tipo_evento_sel]
    # restringe por período de plantios selecionado para foco
    ev = ev[(pd.to_datetime(ev['data_evento']).dt.date >= start_date) & (pd.to_datetime(ev['data_evento']).dt.date <= end_date)]
    # juntar canteiro
    ev = ev.merge(plantios[['plantio_id','canteiro_nome']].drop_duplicates(), on='plantio_id', how='left')
    if canteiro_sel != "Todos":
        ev = ev[ev['canteiro_nome']==canteiro_sel]
    if ev.empty:
        st.info("Sem eventos para os filtros atuais.")
    else:
        # agregação por data x canteiro (contagem)
        ev['dia'] = pd.to_datetime(ev['data_evento']).dt.date
        pivot = ev.pivot_table(index='canteiro_nome', columns='dia', values='evento_id', aggfunc='count', fill_value=0)
        # limitar colunas (dias) para evitar muita largura
        pivot = pivot.reindex(sorted(pivot.columns), axis=1)
        fig3 = px.imshow(pivot, aspect="auto", origin='lower', title="Eventos (contagem) por canteiro × dia")
        st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# -----------------------
# Seção avançada: séries temporais e sucesso por espécie
# -----------------------
st.subheader("Séries e taxa de sucesso por espécie")

# Crescimento médio ao longo do tempo (altura)
obs = observ.merge(plantios[['plantio_id','especie_id','canteiro_nome','responsavel']], on='plantio_id', how='left').merge(especies[['especie_id','nome_comum']], on='especie_id', how='left')
if especie_sel != "Todas":
    obs = obs[obs['nome_comum']==especie_sel]
if not obs.empty:
    avg = obs.groupby('data_observacao').altura_cm.mean().reset_index()
    figg = px.line(avg, x='data_observacao', y='altura_cm', title="Altura média ao longo do tempo", markers=True)
    st.plotly_chart(figg, use_container_width=True)
else:
    st.info("Sem observações disponíveis para esta seleção.")

# Taxa de sucesso por espécie
st.markdown("### Taxa de sucesso por espécie (plantios que geraram ≥1 colheita)")
joined = plantios[['plantio_id','especie_nome']].merge(colheitas[['plantio_id']].drop_duplicates(), on='plantio_id', how='left', indicator=True)
rate = joined.groupby('especie_nome').apply(lambda df: (df['_merge']=="both").sum() / df.shape[0] if df.shape[0]>0 else np.nan).reset_index().rename(columns={0:'sucesso_rate'})
rate = rate.sort_values('sucesso_rate', ascending=False)
rate = rate.dropna()
if not rate.empty:
    fig_rate = px.bar(rate, x='especie_nome', y=0, labels={'x':'Espécie','y':'Taxa de sucesso'}, title="Taxa de sucesso por espécie")
    # px created column name 0 in some versions; fix:
    fig_rate.update_layout(yaxis_title="Taxa (0-1)")
    st.plotly_chart(fig_rate, use_container_width=True)
else:
    st.info("Sem dados suficientes para calcular taxa de sucesso.")

st.markdown("---")

# -----------------------
# Tabelas e downloads
# -----------------------
st.subheader("Dados filtrados / Explorador")

tab1, tab2 = st.tabs(["Plantios (filtrados)", "Observações & Colheitas"])

with tab1:
    st.write("Tabela de plantios resultantes dos filtros (você pode exportar os dados):")
    st.dataframe(p.reset_index(drop=True), height=300)
    csv = p.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar CSV de plantios filtrados", csv, file_name="plantios_filtrados.csv", mime="text/csv")

with tab2:
    st.write("Observações relacionadas aos plantios filtrados")
    obs_f = obs[obs['plantio_id'].isin(p['plantio_id'])]
    st.dataframe(obs_f.sort_values('data_observacao', ascending=False).reset_index(drop=True), height=300)
    st.write("Colheitas relacionadas aos plantios filtrados")
    col_f = colheitas[colheitas['plantio_id'].isin(p['plantio_id'])]
    st.dataframe(col_f.sort_values('data_colheita', ascending=False).reset_index(drop=True), height=200)
    st.download_button("📥 Baixar CSV Observações filtradas", obs_f.to_csv(index=False).encode('utf-8'), file_name="observacoes_filtradas.csv", mime="text/csv")
    st.download_button("📥 Baixar CSV Colheitas filtradas", col_f.to_csv(index=False).encode('utf-8'), file_name="colheitas_filtradas.csv", mime="text/csv")

st.markdown("---")

# -----------------------
# Fotos: upload simples por plantio_id
# -----------------------
st.subheader("Fotos — adicionar imagem por plantio")
st.write("Faça upload de fotos para associar a um plantio (arquivo será salvo em `uploads/` local).")

uploads_dir = DATA_DIR / "uploads"
uploads_dir.mkdir(exist_ok=True)

col_a, col_b = st.columns([1,1])
with col_a:
    plantio_for_photo = st.number_input("Plantio ID (use um plantio existente)", min_value=int(plantios['plantio_id'].min()), max_value=int(plantios['plantio_id'].max()), value=int(plantios['plantio_id'].min()))
with col_b:
    photo = st.file_uploader("Escolha foto (jpg/png)", type=['png','jpg','jpeg'])

if st.button("Salvar foto"):
    if photo is None:
        st.warning("Escolha um arquivo antes de salvar.")
    else:
        target = uploads_dir / f"plantio_{plantio_for_photo}_{int(datetime.datetime.now().timestamp())}_{photo.name}"
        with open(target, "wb") as f:
            f.write(photo.getbuffer())
        st.success(f"Foto salva em: {target.name}")

# Mostrar thumbs de fotos do plantio selecionado
st.write("Fotos já carregadas (por plantio)")
if uploads_dir.exists():
    all_files = sorted(uploads_dir.iterdir(), key=os.path.getmtime, reverse=True)
    thumbs = [p for p in all_files if f"plantio_{plantio_for_photo}_" in p.name]
    if thumbs:
        cols = st.columns(min(4, len(thumbs)))
        for i, t in enumerate(thumbs):
            with cols[i % 4]:
                st.image(str(t), caption=t.name, use_column_width=True)
    else:
        st.info("Sem fotos para este plantio.")

st.markdown("---")
st.caption("Painel gerado localmente — substitua/edite os CSVs para ver outros cenários.")
