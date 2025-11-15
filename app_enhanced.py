"""
app_enhanced.py - Horta Escolar (versão profissional)
Salve este arquivo como app.py ou rode com: streamlit run app_enhanced.py
Requer (ver requirements_enhanced.txt): streamlit, pandas, plotly, openpyxl, reportlab (opcional)
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import datetime
import plotly.express as px
import plotly.graph_objects as go
import io
import base64
import os

# --- Config & paths ---
st.set_page_config(page_title="Horta Escolar — Painel Profissional", layout="wide")
DATA_DIR = Path(__file__).parent
UPLOADS = DATA_DIR / "uploads"
UPLOADS.mkdir(exist_ok=True)
CSS_FILE = DATA_DIR / "style.css"

# --- Apply custom CSS (theme: natural green) ---
if CSS_FILE.exists():
    with open(CSS_FILE, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
else:
    # minimal inline style fallback
    st.markdown(
        """
        <style>
        .stButton>button { background-color: #2E8B57; color: white; }
        .stDownloadButton>button { background-color:#2E8B57; color:white; }
        .big-kpi {font-size:22px; font-weight:700}
        </style>
        """, unsafe_allow_html=True
    )

# --- Load CSVs with safe checks ---
def safe_load(name):
    p = DATA_DIR / name
    if not p.exists():
        st.error(f"Arquivo ausente: {name} — coloque-o na pasta do app e recarregue.")
        return pd.DataFrame()
    try:
        # attempt to detect date columns from header, then parse when reading
        sample = pd.read_csv(p, nrows=0)
        parse = [c for c in ["data_plantio","data_observacao","data_colheita","data_evento"] if c in sample.columns]
        return pd.read_csv(p, parse_dates=parse, encoding='utf-8', low_memory=False)
    except Exception as e:
        st.warning(f"Erro ao ler {name}: {e}. Tentando leitura sem parse de datas.")
        try:
            return pd.read_csv(p, encoding='utf-8', low_memory=False)
        except Exception as e2:
            st.error(f"Falha ao carregar {name}: {e2}")
            return pd.DataFrame()

canteiros = safe_load("canteiros.csv")
especies = safe_load("especies.csv")
plantios = safe_load("plantios.csv")
observ = safe_load("observacoes.csv")
colheitas = safe_load("colheitas.csv")
eventos = safe_load("eventos_manejo.csv")

# Basic joins / cleanup
if not plantios.empty and 'canteiro_id' in plantios.columns and not canteiros.empty:
    plantios = plantios.merge(canteiros[['canteiro_id','nome']].rename(columns={'nome':'canteiro_nome'}), on='canteiro_id', how='left')
if not plantios.empty and 'especie_id' in plantios.columns and not especies.empty:
    plantios = plantios.merge(especies[['especie_id','nome_comum']].rename(columns={'nome_comum':'especie_nome'}), on='especie_id', how='left')

# Sidebar: multi-page navigation
st.sidebar.title("📋 Menu")
page = st.sidebar.radio("Navegar", ["Dashboard", "Plantios", "Observações", "Colheitas", "Manejo", "Fotos", "Import/Export", "Relatórios"])

# Common filters in sidebar
st.sidebar.markdown("---")
st.sidebar.header("Filtros globais")
today = datetime.date.today()
min_plantio_date = pd.to_datetime(plantios['data_plantio']).min().date() if not plantios.empty else today - datetime.timedelta(days=365)
max_plantio_date = pd.to_datetime(plantios['data_plantio']).max().date() if not plantios.empty else today
date_range = st.sidebar.date_input("Período plantio (início, fim)", value=(min_plantio_date, max_plantio_date))
# normalize start/end for reliable comparisons
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    dr_start, dr_end = date_range
else:
    dr_start = dr_end = date_range
especie_options = ["Todas"] + (sorted(especies['nome_comum'].unique().tolist()) if not especies.empty else [])
especie_sel = st.sidebar.selectbox("Espécie", especie_options)
canteiro_options = ["Todos"] + (sorted(canteiros['nome'].unique().tolist()) if not canteiros.empty else [])
canteiro_sel = st.sidebar.selectbox("Canteiro", canteiro_options)
responsavel_options = ["Todos"] + (sorted(plantios['responsavel'].fillna("N/A").unique().tolist()) if not plantios.empty else [])
responsavel_sel = st.sidebar.selectbox("Responsável", responsavel_options)
st.sidebar.markdown("---")

# Helper: filter plantios by global filters
def filter_plantios(df):
    if df.empty:
        return df
    # ensure date_range is a tuple (start, end)
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        s, e = date_range
    else:
        s = date_range
        e = date_range
    s = pd.to_datetime(s).date()
    e = pd.to_datetime(e).date()
    # protect against missing column
    if 'data_plantio' not in df.columns:
        return df
    df = df[(pd.to_datetime(df['data_plantio'], errors='coerce').dt.date >= s) & (pd.to_datetime(df['data_plantio'], errors='coerce').dt.date <= e)]
    if especie_sel != "Todas" and 'especie_nome' in df.columns:
        df = df[df['especie_nome']==especie_sel]
    if canteiro_sel != "Todos" and 'canteiro_nome' in df.columns:
        df = df[df['canteiro_nome']==canteiro_sel]
    if responsavel_sel != "Todos" and 'responsavel' in df.columns:
        df = df[df['responsavel']==responsavel_sel]
    return df

# --- NORMALIZAÇÃO: converter colunas que devem ser inteiras ---
def normalize_dataframes():
    # plantios
    if not plantios.empty:
        if 'plantio_id' in plantios.columns:
            plantios['plantio_id'] = pd.to_numeric(plantios['plantio_id'], errors='coerce').astype('Int64')
        if 'canteiro_id' in plantios.columns:
            plantios['canteiro_id'] = pd.to_numeric(plantios['canteiro_id'], errors='coerce').astype('Int64')
        if 'especie_id' in plantios.columns:
            plantios['especie_id'] = pd.to_numeric(plantios['especie_id'], errors='coerce').astype('Int64')
    # colheitas: quantidades não devem ser fracionadas
    if not colheitas.empty:
        if 'plantio_id' in colheitas.columns:
            colheitas['plantio_id'] = pd.to_numeric(colheitas['plantio_id'], errors='coerce').astype('Int64')
        if 'quantidade_colhida' in colheitas.columns:
            colheitas['quantidade_colhida'] = pd.to_numeric(colheitas['quantidade_colhida'], errors='coerce').fillna(0).round().astype(int)
    # observacoes / eventos
    if not observ.empty and 'plantio_id' in observ.columns:
        observ['plantio_id'] = pd.to_numeric(observ['plantio_id'], errors='coerce').astype('Int64')
    if not eventos.empty and 'plantio_id' in eventos.columns:
        eventos['plantio_id'] = pd.to_numeric(eventos['plantio_id'], errors='coerce').astype('Int64')
    # canteiros / especies ids
    if not canteiros.empty and 'canteiro_id' in canteiros.columns:
        canteiros['canteiro_id'] = pd.to_numeric(canteiros['canteiro_id'], errors='coerce').astype('Int64')
    if not especies.empty and 'especie_id' in especies.columns:
        especies['especie_id'] = pd.to_numeric(especies['especie_id'], errors='coerce').astype('Int64')

normalize_dataframes()

# depois da normalização, aplique os filtros aos plantios
plantios_f = filter_plantios(plantios)

# --- ADIÇÃO: criar views filtradas para que os filtros sejam globais ---
# obtém conjunto de plantio_id visíveis na seleção
plantio_ids = set()
if not plantios_f.empty and 'plantio_id' in plantios_f.columns:
    plantio_ids = set(pd.to_numeric(plantios_f['plantio_id'], errors='coerce').dropna().astype(int).tolist())

def filter_by_plantios_table(df):
    """
    Retorna apenas as linhas de df cujos plantio_id estão em plantio_ids.
    Se plantio_ids estiver vazio, retorna DataFrame vazio (indica que não há plantios na seleção).
    """
    if df is None or df.empty:
        return pd.DataFrame()
    if 'plantio_id' in df.columns:
        # coerce com fallback para evitar erros de conversão e alinhar máscara ao índice original
        coerced = pd.to_numeric(df['plantio_id'], errors='coerce').fillna(-1)
        mask = coerced.astype(int).isin(plantio_ids) if plantio_ids else pd.Series([False]*len(df), index=df.index)
        return df.loc[mask].copy()
    # se não existe plantio_id na tabela, retornar cópia (sem filtro)
    return df.copy()

colheitas_f = filter_by_plantios_table(colheitas)
observ_f = filter_by_plantios_table(observ)
eventos_f = filter_by_plantios_table(eventos)

# ---------- ADICIONADO: helpers para download / relatório ----------
def df_to_csv_bytes(df):
    return df.to_csv(index=False).encode('utf-8')

def make_pdf_report_canteiro(canteiro_name):
    """
    Gera PDF vetorial (ReportLab) para o canteiro informado.
    Retorna bytes do PDF (sempre) — em caso de erro gera um PDF simples com a mensagem de erro.
    Implementação robusta: não usa ImageReader/BytesIO para imagens geradas dinamicamente.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        from reportlab.graphics.shapes import Drawing, String
        from reportlab.graphics.charts.barcharts import HorizontalBarChart
        from reportlab.graphics import renderPDF
        import io

        # canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        w, h = A4
        margin = 40
        x = margin
        y = h - margin

        # Header
        c.setFont("Helvetica-Bold", 16)
        c.drawString(x, y, f"Relatório — Canteiro: {canteiro_name}")
        y -= 20
        c.setFont("Helvetica", 10)
        try:
            c.drawString(x, y, f"Período (filtros): {dr_start} — {dr_end}")
        except Exception:
            c.drawString(x, y, "Período (filtros): -")
        y -= 18

        # Build subset safely (prioriza plantios_f quando disponível)
        if 'plantios_f' in globals() and isinstance(plantios_f, pd.DataFrame):
            plantio_src = plantios_f
        elif 'plantios' in globals() and isinstance(plantios, pd.DataFrame):
            plantio_src = plantios
        else:
            plantio_src = pd.DataFrame()

        subset = plantio_src[plantio_src.get('canteiro_nome', '') == canteiro_name] if not plantio_src.empty else pd.DataFrame()
        total_plantios = int(subset.shape[0]) if not subset.empty else 0

        # total colhido e por espécie (usa colheitas_f se existir)
        per_species = pd.DataFrame(columns=['especie_nome', 'quantidade_colhida'])
        total_colhido = 0
        try:
            if not subset.empty and 'plantio_id' in subset.columns:
                if 'colheitas_f' in globals() and isinstance(colheitas_f, pd.DataFrame) and not colheitas_f.empty:
                    ch = colheitas_f
                elif 'colheitas' in globals() and isinstance(colheitas, pd.DataFrame) and not colheitas.empty:
                    ch = colheitas
                else:
                    ch = pd.DataFrame()
                if not ch.empty:
                    merged = ch.merge(subset[['plantio_id','especie_nome']], on='plantio_id', how='inner')
                    if not merged.empty and 'quantidade_colhida' in merged.columns:
                        merged['quantidade_colhida'] = pd.to_numeric(merged['quantidade_colhida'], errors='coerce').fillna(0)
                        total_colhido = int(merged['quantidade_colhida'].sum())
                        per_species = merged.groupby('especie_nome', dropna=False).quantidade_colhida.sum().reset_index().rename(columns={'quantidade_colhida':'quantidade_colhida'}).sort_values('quantidade_colhida', ascending=False)
        except Exception:
            per_species = pd.DataFrame(columns=['especie_nome','quantidade_colhida'])

        # Summary
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x, y, f"Plantios na seleção: {total_plantios}")
        y -= 14
        c.drawString(x, y, f"Total colhido: {total_colhido}")
        y -= 18

        # Draw a small horizontal bar chart for top species (vector chart)
        if not per_species.empty and per_species['quantidade_colhida'].sum() > 0:
            top = per_species.head(8).copy()
            # normalize values to list of lists for chart
            data = [list(top['quantidade_colhida'].astype(float).tolist())]
            labels = [str(x) for x in top['especie_nome'].fillna("Sem nome").tolist()]
            chart_height = 14 * len(labels) + 40
            d = Drawing(w - 2*margin, chart_height)
            bc = HorizontalBarChart()
            bc.x = 70
            bc.y = 10
            bc.height = max(20, chart_height - 30)
            bc.width = d.width - 90
            bc.data = data
            bc.valueAxis.valueMin = 0
            bc.valueAxis.valueMax = float(max(top['quantidade_colhida'].max(), 1))
            bc.valueAxis.valueStep = max(1, int(bc.valueAxis.valueMax / 4))
            bc.categoryAxis.categoryNames = labels
            bc.barLabels.nudge = 7
            bc.bars.strokeColor = colors.black
            d.add(bc)
            # title
            d.add(String(0, bc.height + 20, "Produção por espécie (top)", fontSize=10))
            # render on canvas
            renderPDF.draw(d, c, x, y - chart_height)
            y -= (chart_height + 12)
        else:
            c.setFont("Helvetica-Oblique", 9)
            c.drawString(x, y, "Sem dados de colheita por espécie para este canteiro.")
            y -= 18

        # Small table: top species as text
        if not per_species.empty:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(x, y, "Top espécies:")
            y -= 14
            c.setFont("Helvetica", 9)
            for _, r in per_species.head(8).iterrows():
                line = f"• {r['especie_nome']}: {int(r['quantidade_colhida'])}"
                c.drawString(x + 6, y, line)
                y -= 12
                if y < 80:
                    c.showPage()
                    y = h - margin

        # Footer
        if y < 100:
            c.showPage()
            y = h - margin
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(margin, 30, f"Gerado em: {datetime.datetime.now().isoformat()}")

        c.save()
        buf.seek(0)
        data = buf.getvalue()
        buf.close()
        return data

    except Exception as e:
        # fallback: PDF with error text (still valid PDF)
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            import io
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=A4)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(40, 800, f"Relatório — Canteiro: {canteiro_name}")
            c.setFont("Helvetica", 10)
            c.drawString(40, 780, "Erro ao gerar relatório gráfico:")
            c.setFont("Helvetica", 9)
            c.drawString(40, 760, str(e))
            c.save()
            buf.seek(0)
            data = buf.getvalue()
            buf.close()
            return data
        except Exception:
            return f"Erro crítico ao gerar PDF: {e}".encode('utf-8')

# --- Page: Dashboard ---
if page == "Dashboard":
    st.title("🌿 Dashboard Geral — Horta Escolar")
    col1, col2, col3, col4 = st.columns(4)
    # use filtered datasets so dashboard reflects selection
    total_colhido = pd.to_numeric(colheitas_f.get('quantidade_colhida', pd.Series(dtype=float)), errors='coerce').sum() if not colheitas_f.empty else 0
    total_plantios = plantios_f.shape[0] if not plantios_f.empty else 0
    plantios_colhidos = int(colheitas_f['plantio_id'].nunique()) if not colheitas_f.empty and 'plantio_id' in colheitas_f.columns else 0
    try:
        avg_per_plantio = colheitas_f.groupby('plantio_id').quantidade_colhida.sum().mean() if not colheitas_f.empty and 'quantidade_colhida' in colheitas_f.columns else 0
    except Exception:
        avg_per_plantio = 0
    num_observ = observ_f.shape[0] if not observ_f.empty else 0

    col1.metric("Total colhido", f"{float(total_colhido):.1f}")
    col2.metric("Plantios (seleção)", f"{total_plantios}")
    col3.metric("Plantios com colheita", f"{plantios_colhidos}")
    col4.metric("Observações registradas", f"{num_observ}")

    st.markdown("### Produção — visões rápidas")
    # merge colheitas filtradas com plantios filtrados para ter canteiro/especie
    merged = pd.DataFrame()
    if not colheitas_f.empty and not plantios_f.empty and 'plantio_id' in colheitas_f.columns and 'plantio_id' in plantios_f.columns:
        merged = colheitas_f.merge(plantios_f[['plantio_id','especie_nome','canteiro_nome']], on='plantio_id', how='left')
    # ensure numeric quantidade_colhida
    if not merged.empty and 'quantidade_colhida' in merged.columns:
        merged['quantidade_colhida'] = pd.to_numeric(merged['quantidade_colhida'], errors='coerce').fillna(0)
    # two charts side-by-side: donut by canteiro (quantidade) and pie by espécie (quantidade)
    c1, c2 = st.columns(2)
    # Donut: distribuição por canteiro (soma quantidade)
    with c1:
        st.subheader("Distribuição por canteiro (quantidade)")
        if not merged.empty and 'canteiro_nome' in merged.columns and 'quantidade_colhida' in merged.columns:
            by_canteiro = merged.groupby('canteiro_nome').quantidade_colhida.sum().reset_index().sort_values('quantidade_colhida', ascending=False)
            if not by_canteiro.empty and by_canteiro['quantidade_colhida'].sum() > 0:
                fig1 = px.pie(by_canteiro, names='canteiro_nome', values='quantidade_colhida', hole=0.45,
                              title="Total colhido por canteiro", labels={'canteiro_nome':'Canteiro','quantidade_colhida':'Quantidade'})
                fig1.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig1, use_container_width=True)
            else:
                st.info("Sem colheitas com quantidade para mostrar por canteiro.")
        else:
            st.info("Dados insuficientes para distribuição por canteiro.")
    # Pie: produção por espécie
    with c2:
        st.subheader("Produção por espécie")
        if not merged.empty and 'especie_nome' in merged.columns and 'quantidade_colhida' in merged.columns:
            by_especie = merged.groupby('especie_nome').quantidade_colhida.sum().reset_index().sort_values('quantidade_colhida', ascending=False)
            if not by_especie.empty and by_especie['quantidade_colhida'].sum() > 0:
                fig2 = px.pie(by_especie, names='especie_nome', values='quantidade_colhida',
                              title="Produção por espécie", labels={'especie_nome':'Espécie','quantidade_colhida':'Quantidade'})
                fig2.update_traces(textposition='inside', textinfo='label+percent')
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Sem produção por espécie na seleção.")
        else:
            st.info("Dados insuficientes para produção por espécie.")

    st.markdown("### Mapa esquemático (status por canteiro)")
    # Legend and improved spacing/colors
    st.markdown("""
    <div style="display:flex;gap:12px;margin-bottom:8px">
      <div style="background:#1B5E20;color:#fff;padding:6px 10px;border-radius:8px;font-weight:600">≥ 60% colhido</div>
      <div style="background:#F57F17;color:#fff;padding:6px 10px;border-radius:8px;font-weight:600">25–60% colhido</div>
      <div style="background:#B71C1C;color:#fff;padding:6px 10px;border-radius:8px;font-weight:600">&lt; 25% colhido</div>
    </div>
    """, unsafe_allow_html=True)

    if not canteiros.empty:
        # compute totals based on filtered plantios
        totals = {}
        harvested = {}
        if not plantios_f.empty and 'canteiro_id' in plantios_f.columns:
            totals = plantios_f.groupby('canteiro_id').plantio_id.nunique().to_dict()
        if not colheitas_f.empty and 'plantio_id' in colheitas_f.columns and not plantios_f.empty and 'plantio_id' in plantios_f.columns:
            merged = colheitas_f.merge(plantios_f[['plantio_id','canteiro_id']], on='plantio_id', how='inner')
            harvested = merged.groupby('canteiro_id').plantio_id.nunique().to_dict()
        # present canteiros that exist in the canteiros table but respect filtered totals (show zero if none)
        cols = st.columns(3)
        for i, c in canteiros.reset_index(drop=True).iterrows():
            with cols[i % 3]:
                cid = c.get('canteiro_id')
                total = int(totals.get(cid, 0))
                harvested_cnt = int(harvested.get(cid, 0)) if harvested else 0
                rate = harvested_cnt / total if total > 0 else 0
                # more contrasting palette
                color = "#1B5E20" if rate >= 0.6 else ("#F57F17" if rate >= 0.25 else "#B71C1C")
                # bigger spacing and shadow for better readability
                card = f"""
                <div style="background:{color};padding:16px;margin:10px;border-radius:12px;color:white;min-height:100px;
                            box-shadow: 0 4px 14px rgba(0,0,0,0.12);">
                  <h4 style="margin:2px 0 6px 0">{c.get('nome','-')}</h4>
                  <div style="opacity:0.95">Área: {c.get('area_m2','-')} m²</div>
                  <div style="margin-top:8px;font-weight:600">{total} plantios • {harvested_cnt} colhidos</div>
                </div>
                """
                st.markdown(card, unsafe_allow_html=True)
    else:
        st.info("Nenhum canteiro cadastrado.")

    st.markdown("### Visões adicionais")

    # 1) Série temporal mensal de produção (soma por mês)
    if not colheitas_f.empty and 'data_colheita' in colheitas_f.columns and 'quantidade_colhida' in colheitas_f.columns:
        df_ts = colheitas_f.copy()
        df_ts['data_colheita_dt'] = pd.to_datetime(df_ts['data_colheita'], errors='coerce')
        df_ts = df_ts[df_ts['data_colheita_dt'].notna()]
        # aplicar janela de filtros
        s = pd.to_datetime(dr_start).date()
        e = pd.to_datetime(dr_end).date()
        df_ts = df_ts[(df_ts['data_colheita_dt'].dt.date >= s) & (df_ts['data_colheita_dt'].dt.date <= e)]
        if not df_ts.empty:
            monthly = df_ts.set_index('data_colheita_dt').resample('M')['quantidade_colhida'].sum().reset_index()
            monthly['month'] = monthly['data_colheita_dt'].dt.to_period('M').dt.to_timestamp()
            fig_ts = px.line(monthly, x='month', y='quantidade_colhida', title='Produção mensal (soma)', markers=True, labels={'quantidade_colhida':'Quantidade','month':'Mês'})
            st.plotly_chart(fig_ts, use_container_width=True)
        else:
            st.info("Sem colheitas no período selecionado para série temporal.")
    else:
        st.info("Sem dados de colheita para série temporal.")

    # 2) Top espécies por produção (barra horizontal)
    try:
        if 'merged' in locals() and not merged.empty and 'quantidade_colhida' in merged.columns:
            top_sp = merged.groupby('especie_nome').quantidade_colhida.sum().reset_index().sort_values('quantidade_colhida', ascending=False).head(10)
            if not top_sp.empty and top_sp['quantidade_colhida'].sum() > 0:
                fig_top = px.bar(top_sp, x='quantidade_colhida', y='especie_nome', orientation='h', title='Top espécies por produção', labels={'quantidade_colhida':'Quantidade','especie_nome':'Espécie'})
                st.plotly_chart(fig_top, use_container_width=True)
    except Exception:
        pass

    # 3) Tempo médio até a 1ª colheita por espécie (dias)
    if not plantios_f.empty and not colheitas_f.empty:
        ph = plantios_f[['plantio_id','data_plantio','especie_nome']].copy()
        ch = colheitas_f[['plantio_id','data_colheita']].copy()
        ch['data_colheita_dt'] = pd.to_datetime(ch['data_colheita'], errors='coerce')
        first = ch.groupby('plantio_id')['data_colheita_dt'].min().reset_index()
        merged_time = ph.merge(first, on='plantio_id', how='left')
        merged_time['data_plantio_dt'] = pd.to_datetime(merged_time['data_plantio'], errors='coerce')
        merged_time = merged_time[merged_time['data_colheita_dt'].notna() & merged_time['data_plantio_dt'].notna()]
        if not merged_time.empty:
            merged_time['days_to_first'] = (merged_time['data_colheita_dt'] - merged_time['data_plantio_dt']).dt.days
            avg_time = merged_time.groupby('especie_nome')['days_to_first'].mean().reset_index().dropna().sort_values('days_to_first')
            if not avg_time.empty:
                fig_time = px.bar(avg_time, x='days_to_first', y='especie_nome', orientation='h', title='Tempo médio (dias) até 1ª colheita por espécie', labels={'days_to_first':'Dias','especie_nome':'Espécie'})
                st.plotly_chart(fig_time, use_container_width=True)

    # 4) Eventos de manejo por mês (stacked area)
    if not eventos_f.empty and 'data_evento' in eventos_f.columns and 'tipo_evento' in eventos_f.columns:
        ev = eventos_f.copy()
        ev['data_evento_dt'] = pd.to_datetime(ev['data_evento'], errors='coerce')
        ev = ev[ev['data_evento_dt'].notna()]
        if not ev.empty:
            ev['month'] = ev['data_evento_dt'].dt.to_period('M').dt.to_timestamp()
            ev_pivot = ev.pivot_table(index='month', columns='tipo_evento', values='plantio_id', aggfunc='count').fillna(0)
            if not ev_pivot.empty:
                fig_ev = px.area(ev_pivot.reset_index(), x='month', y=ev_pivot.columns.tolist(), title='Eventos de manejo por mês (contagem)')
                st.plotly_chart(fig_ev, use_container_width=True)

    # 5) Produtividade por área (quantidade / m²) por canteiro
    try:
        if 'merged' in locals() and not merged.empty and not canteiros.empty and 'area_m2' in canteiros.columns:
            prod = merged.groupby('canteiro_nome').quantidade_colhida.sum().reset_index()
            can = canteiros[['nome','area_m2']].rename(columns={'nome':'canteiro_nome'}).copy()
            can['area_m2'] = pd.to_numeric(can['area_m2'], errors='coerce').fillna(0)
            prod_area = prod.merge(can, on='canteiro_nome', how='left')
            prod_area['kg_m2'] = prod_area.apply(lambda r: r['quantidade_colhida'] / r['area_m2'] if r['area_m2']>0 else np.nan, axis=1)
            prod_area = prod_area.dropna(subset=['kg_m2']).sort_values('kg_m2', ascending=False)
            if not prod_area.empty:
                fig_pa = px.bar(prod_area, x='canteiro_nome', y='kg_m2', title='Produtividade (quantidade / m²) por canteiro', labels={'kg_m2':'Quantidade/m²','canteiro_nome':'Canteiro'})
                st.plotly_chart(fig_pa, use_container_width=True)
    except Exception:
        pass

# --- Page: Plantios ---
elif page == "Plantios":
    st.title("🌱 Plantios")
    st.write(f"Plantios na seleção: {plantios_f.shape[0]}")
    if not plantios_f.empty:
        st.dataframe(plantios_f.sort_values('data_plantio', ascending=False).reset_index(drop=True), height=300)
    else:
        st.info("Nenhum plantio na seleção.")

    st.markdown("### Gantt simplificado (plantio → colheita)")

    # build gantt from filtered plantios and filtered colheitas so filters apply
    gantt_df = plantios_f.copy()
    if not gantt_df.empty:
        # last harvest from filtered colheitas
        last_harvest = pd.DataFrame()
        if not colheitas_f.empty and 'plantio_id' in colheitas_f.columns:
            last_harvest = colheitas_f.groupby('plantio_id')['data_colheita'].max().reset_index().rename(columns={'data_colheita':'last_colheita'})
        gantt_df = gantt_df.merge(last_harvest, on='plantio_id', how='left')

        # ensure datetime columns and safe fallbacks
        gantt_df['start'] = pd.to_datetime(gantt_df['data_plantio'], errors='coerce')
        gantt_df['end'] = pd.to_datetime(gantt_df['last_colheita'], errors='coerce').fillna(pd.Timestamp.now())

        # normalize canteiro names (strip) and ensure string type
        if 'canteiro_nome' in gantt_df.columns:
            gantt_df['canteiro_nome'] = gantt_df['canteiro_nome'].astype(str).str.strip()
        else:
            gantt_df['canteiro_nome'] = gantt_df.get('canteiro_id', '').astype(str)

        # create a unique row per plantio to avoid color ambiguity when same species has multiple plantios
        gantt_df['plantio_row'] = gantt_df['plantio_id'].astype(str) + " — " + gantt_df['especie_nome'].fillna('').astype(str)

        # color map: normalized keys to avoid mismatches
        unique_canteiros = sorted(gantt_df['canteiro_nome'].dropna().unique().tolist())
        palette = ["#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd","#8c564b","#e377c2","#7f7f7f","#bcbd22","#17becf"]
        color_map = {str(name).strip(): palette[i % len(palette)] for i, name in enumerate(unique_canteiros)}

        # draw timeline, color by canteiro_nome and include useful hover info
        fig = px.timeline(
            gantt_df.sort_values('start'),
            x_start="start",
            x_end="end",
            y="plantio_row",
            color="canteiro_nome",
            color_discrete_map=color_map,
            hover_data={'plantio_id':True,'canteiro_nome':True,'start':True,'end':True,'especie_nome':True}
        )

        # visual improvements: spacing, outlines, legend, hover template
        fig.update_traces(marker_line_color='black', marker_line_width=0.6)
        fig.update_layout(
            bargap=0.25,
            legend_title_text="Canteiro",
            yaxis_title="Plantio (ID — Espécie)",
            xaxis_title="Data",
            margin=dict(l=120, r=20, t=40, b=40),
            height=max(420, len(gantt_df) * 32)
        )
        fig.update_yaxes(autorange="reversed")
        # stronger contrast for dark themes
        fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhum plantio na seleção.")

    st.download_button("📥 Baixar plantios filtrados (CSV)", df_to_csv_bytes(plantios_f), file_name="plantios_filtrados.csv", mime="text/csv")

# --- Page: Observações ---
elif page == "Observações":
    st.title("🔎 Observações (Crescimento)")
    obsf = observ.copy()
    if not obsf.empty:
        obsf = obsf[obsf['plantio_id'].isin(plantios_f['plantio_id'])] if 'plantio_id' in obsf.columns and 'plantio_id' in plantios_f.columns else obsf
        if not obsf.empty:
            st.dataframe(obsf.sort_values('data_observacao', ascending=False).reset_index(drop=True), height=300)
            if 'altura_cm' in obsf.columns and 'data_observacao' in obsf.columns:
                avg = obsf.groupby('data_observacao').altura_cm.mean().reset_index()
                fig = px.line(avg, x='data_observacao', y='altura_cm', title="Altura média (cm) por data", markers=True)
                st.plotly_chart(fig, use_container_width=True)
            # handle pragas: accept booleans or truthy strings
            if 'pragas_observadas' in obsf.columns:
                pragas_mask = obsf['pragas_observadas'].astype(str).str.lower().isin(['true','1','sim','s','yes']) if obsf['pragas_observadas'].dtype == object else obsf['pragas_observadas'] == True
                pragas = obsf[pragas_mask]
                if not pragas.empty and 'plantio_id' in pragas.columns and 'plantio_id' in plantios.columns:
                    pragas = pragas.merge(plantios[['plantio_id','especie_nome']], on='plantio_id', how='left')
                    pr_count = pragas.groupby('especie_nome').size().reset_index(name='count').sort_values('count', ascending=False)
                    fig2 = px.bar(pr_count, x='especie_nome', y='count', title="Observações com pragas por espécie")
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("Nenhuma observação com pragas no período/seleção.")
            else:
                st.info("Campo 'pragas_observadas' não disponível nos dados.")
        else:
            st.info("Nenhuma observação na seleção atual.")
    else:
        st.info("Nenhuma observação cadastrada.")

# --- Page: Colheitas ---
elif page == "Colheitas":
    st.title("🧺 Colheitas")
    cf = colheitas.copy()
    if not cf.empty:
        # aplica filtro global de plantios
        if 'plantio_id' in cf.columns and not plantios_f.empty and 'plantio_id' in plantios_f.columns:
            cf = cf[cf['plantio_id'].isin(plantios_f['plantio_id'])]
        st.dataframe(cf.sort_values('data_colheita', ascending=False).reset_index(drop=True), height=300)

        # stats por plantio → resumo por espécie
        try:
            stats = cf.groupby('plantio_id').quantidade_colhida.sum().reset_index().merge(
                plantios[['plantio_id','especie_nome','canteiro_nome']], on='plantio_id', how='left'
            ) if not cf.empty and 'plantio_id' in cf.columns and 'plantio_id' in plantios.columns else pd.DataFrame()
            summary = stats.groupby('especie_nome').quantidade_colhida.agg(['sum','mean','count']).reset_index().rename(
                columns={'sum':'total','mean':'media','count':'n_plantios'}
            )
            # formatar média como inteiro quando aplicável
            if 'media' in summary.columns:
                summary['media'] = summary['media'].round(0).astype('Int64')
            st.dataframe(summary, height=200)
        except Exception:
            st.warning("Não foi possível calcular o resumo por espécie.")

        # Boxplot melhorado: por espécie com marcação da média (x)
        try:
            # garante quantidade numérica
            if 'quantidade_colhida' in cf.columns:
                cf['quantidade_colhida'] = pd.to_numeric(cf['quantidade_colhida'], errors='coerce').fillna(0)
            # se houver coluna de espécie, plotar por espécie e adicionar médias
            if 'especie_nome' in cf.columns and cf['especie_nome'].notna().any():
                fig = px.box(
                    cf,
                    x='quantidade_colhida',
                    y='especie_nome',
                    orientation='h',
                    points="outliers",
                    title="Distribuição das quantidades colhidas por espécie",
                    labels={'quantidade_colhida':'Quantidade','especie_nome':'Espécie'}
                )
                # calcular médias por espécie e sobrepor com 'x'
                means = cf.groupby('especie_nome')['quantidade_colhida'].mean().reset_index()
                fig.add_trace(go.Scatter(
                    x=means['quantidade_colhida'],
                    y=means['especie_nome'],
                    mode='markers',
                    marker_symbol='x',
                    marker=dict(size=12, color='black'),
                    name='Média'
                ))
                fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig, use_container_width=True)
            else:
                # box único com linha vertical para média e anotação
                fig = px.box(cf, x='quantidade_colhida', points="outliers", title="Distribuição das quantidades colhidas", labels={'quantidade_colhida':'Quantidade'})
                mean = float(cf['quantidade_colhida'].mean()) if 'quantidade_colhida' in cf.columns else 0.0
                fig.add_vline(x=mean, line_dash="dash", line_color="black",
                              annotation_text=f"Média: {mean:.0f}", annotation_position="top left")
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao gerar boxplot: {e}")

        st.download_button("📥 Baixar colheitas filtradas (CSV)", df_to_csv_bytes(cf), file_name="colheitas_filtradas.csv", mime="text/csv")
    else:
        st.info("Nenhuma colheita registrada.")

# --- Page: Manejo ---
elif page == "Manejo":
    st.title("🛠️ Manejo — Regas, adubos e tratamentos")
    ev = eventos.copy() if not eventos.empty else pd.DataFrame()
    if not ev.empty:
        if 'plantio_id' in ev.columns and not plantios_f.empty and 'plantio_id' in plantios_f.columns:
            ev = ev[ev['plantio_id'].isin(plantios_f['plantio_id'])]
        st.dataframe(ev.sort_values('data_evento', ascending=False).reset_index(drop=True), height=300)

        # safe counts: preenche NaN, normaliza para string, gera contagem única
        ev_count = (
            ev['tipo_evento']
            .fillna('Não informado')
            .astype(str)
            .value_counts()
            .reset_index(name='count')
            .rename(columns={'index': 'tipo_evento'})
        )

        if not ev_count.empty:
            fig = px.bar(
                ev_count,
                x='tipo_evento',
                y='count',
                labels={'tipo_evento': 'Tipo', 'count': 'Contagem'},
                title="Eventos por tipo"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nenhum evento disponível na seleção.")
    else:
        st.info("Nenhum evento cadastrado.")

# --- Page: Fotos ---
elif page == "Fotos":
    st.title("📸 Fotos e Evolução Visual")
    # safer plantio selection: use available IDs
    if not plantios.empty and 'plantio_id' in plantios.columns:
        pids = sorted([int(x) for x in pd.to_numeric(plantios['plantio_id'], errors='coerce').dropna().unique()])
        plantio_id = int(st.selectbox("Plantio ID", options=pids, index=0)) if pids else st.number_input("Plantio ID", min_value=1, value=1)
    else:
        plantio_id = int(st.number_input("Plantio ID", min_value=1, value=1))
    file = st.file_uploader("Escolha foto (jpg/png)", type=['jpg','jpeg','png'])
    caption = st.text_input("Legenda (opcional)")
    if st.button("Salvar foto"):
        if file is None:
            st.warning("Escolha uma foto antes.")
        else:
            ts = int(datetime.datetime.now().timestamp())
            safe_name = "".join(ch for ch in file.name if ch.isalnum() or ch in (" ", ".", "_")).rstrip()
            fname = f"plantio_{plantio_id}_{ts}_{safe_name}"
            target = UPLOADS / fname
            with open(target, "wb") as f:
                f.write(file.getbuffer())
            meta = DATA_DIR / "photo_metadata.csv"
            row = {"plantio_id":plantio_id,"file":fname,"caption":caption,"timestamp":datetime.datetime.now().isoformat()}
            if meta.exists():
                try:
                    md = pd.read_csv(meta)
                    md = pd.concat([md, pd.DataFrame([row])], ignore_index=True)
                    md.to_csv(meta, index=False)
                except Exception:
                    pd.DataFrame([row]).to_csv(meta, index=False)
            else:
                pd.DataFrame([row]).to_csv(meta, index=False)
            st.success("Foto salva com sucesso.")
    st.markdown("Galeria do plantio selecionado")
    if (DATA_DIR / "photo_metadata.csv").exists():
        md = pd.read_csv(DATA_DIR / "photo_metadata.csv")
        thumbs = md[md['plantio_id']==plantio_id] if 'plantio_id' in md.columns else pd.DataFrame()
        if not thumbs.empty:
            cols = st.columns(min(4, len(thumbs)))
            for i, r in thumbs.reset_index(drop=True).iterrows():
                with cols[i % 4]:
                    path = UPLOADS / r.get('file','')
                    if path.exists():
                        st.image(str(path), caption=r.get('caption',''), use_container_width=True)
                    else:
                        st.text("Arquivo não encontrado")
        else:
            st.info("Sem fotos para este plantio.")
    else:
        st.info("Nenhuma foto enviada ainda.")

# --- Page: Import/Export ---
elif page == "Import/Export":
    st.title("🔁 Importar / Exportar dados")
    st.markdown("Downloads rápidos e export Excel:")
    if not plantios_f.empty:
        st.download_button("📥 Plantios (CSV)", df_to_csv_bytes(plantios_f), file_name="plantios_filtrados.csv")
    if not colheitas.empty:
        st.download_button("📥 Colheitas (CSV)", df_to_csv_bytes(colheitas), file_name="colheitas.csv")
    if st.button("📥 Exportar tudo (Excel)"):
        try:
            bio = io.BytesIO()
            with pd.ExcelWriter(bio, engine='openpyxl') as writer:
                plantios.to_excel(writer, sheet_name='plantios', index=False)
                colheitas.to_excel(writer, sheet_name='colheitas', index=False)
                observ.to_excel(writer, sheet_name='observacoes', index=False)
                canteiros.to_excel(writer, sheet_name='canteiros', index=False)
                especies.to_excel(writer, sheet_name='especies', index=False)
            bio.seek(0)
            st.download_button("📥 Baixar Excel", data=bio.getvalue(), file_name="horta_dados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception as e:
            st.error(f"Erro ao gerar Excel: {e}")

# --- Page: Relatórios ---
elif page == "Relatórios":
    st.title("📄 Relatórios — geração robusta")

    # Use safe view (plantios_f preferred)
    if 'plantios_f' in globals() and isinstance(plantios_f, pd.DataFrame):
        plantios_view = plantios_f
    elif 'plantios' in globals() and isinstance(plantios, pd.DataFrame):
        plantios_view = plantios
    else:
        plantios_view = pd.DataFrame()

    # Build available canteiros for selection
    available_canteiros = []
    if not plantios_view.empty and 'canteiro_nome' in plantios_view.columns:
        available_canteiros = sorted(plantios_view['canteiro_nome'].dropna().unique().tolist())
    if not available_canteiros and not canteiros.empty and 'nome' in canteiros.columns:
        available_canteiros = sorted(canteiros['nome'].dropna().unique().tolist())

    if not available_canteiros:
        st.info("Nenhum canteiro disponível para gerar relatório. Ajuste filtros ou cadastre canteiros.")
    else:
        can_sel = st.selectbox("Canteiro", options=available_canteiros)

        # quick summary
        with st.expander("Resumo rápido do canteiro"):
            subset = plantios_view[plantios_view.get('canteiro_nome','') == can_sel] if not plantios_view.empty else pd.DataFrame()
            st.write(f"- Plantios na seleção: **{int(subset.shape[0]) if not subset.empty else 0}**")
            # total colhido (use colheitas_f if available)
            total_colhido = 0
            if not subset.empty and 'plantio_id' in subset.columns:
                ch = colheitas_f if ('colheitas_f' in globals() and isinstance(colheitas_f, pd.DataFrame) and not colheitas_f.empty) else (colheitas if not colheitas.empty else pd.DataFrame())
                if not ch.empty:
                    merged = ch.merge(subset[['plantio_id']], on='plantio_id', how='inner')
                    if not merged.empty and 'quantidade_colhida' in merged.columns:
                        total_colhido = int(pd.to_numeric(merged['quantidade_colhida'], errors='coerce').fillna(0).sum())
            st.write(f"- Total colhido (na seleção): **{total_colhido}**")
            if not subset.empty:
                st.dataframe(subset.sort_values('data_plantio', ascending=False).reset_index(drop=True), height=220)
            else:
                st.info("Nenhum plantio no canteiro dentro dos filtros atuais.")

        if st.button("Gerar PDF do canteiro"):
            try:
                pdf_bytes = make_pdf_report_canteiro(can_sel)
                if isinstance(pdf_bytes, (bytes, bytearray)) and pdf_bytes.startswith(b"%PDF"):
                    st.success("PDF gerado com sucesso. Use o botão abaixo para baixar.")
                    st.download_button("📥 Baixar PDF", data=pdf_bytes, file_name=f"relatorio_canteiro_{can_sel}.pdf", mime="application/pdf")
                else:
                    # caso a função retorne algo diferente, abrir em modo texto para debug
                    st.error("Falha ao gerar PDF válido. Saída:")
                    st.code(str(pdf_bytes)[:500])
            except Exception as e:
                st.error(f"Erro ao gerar PDF: {e}")

# Footer
st.markdown("---")
st.caption("Painel local — personalize os CSVs para ajustar dados. Tema natural (verde).")
