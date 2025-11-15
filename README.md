# 🌱 Projeto de Análise de Dados — Horta Escolar - PROJETO INTERDISCIPLINAR UNIVESP

Este projeto tem como objetivo organizar, consolidar e analisar os dados de uma horta escolar, permitindo melhor acompanhamento dos plantios, colheitas, manejo e informações sobre espécies cultivadas. A solução foi construída utilizando Python, Streamlit e arquivos CSV como base de dados.

## 📁 Estrutura do Projeto

```
Csvs Horta - Projeto/
│
├── app.py
├── app2.py
├── app_enhanced.py
├── style.css
├── requirements.txt
├── requirements_enhanced.txt
│
├── plantios.csv
├── colheitas.csv
├── canteiros.csv
├── especies.csv
├── observacoes.csv
├── eventos_manejo.csv
├── photo_metadata.csv
│
├── Projeto Horta na  escola .docx
└── uploads/
```

## 🌿 Objetivo Geral

Criar um processo estruturado de análise e visualização de dados para uma horta escolar.

## 🧩 Componentes do Projeto

### 1. Aplicações (Python + Streamlit)
- app.py, app2.py, app_enhanced.py
- style.css

### 2. Bancos de Dados (CSV)

| Arquivo | Descrição |
|--------|-----------|
| plantios.csv | Registro de plantios |
| colheitas.csv | Registro de colheitas |
| canteiros.csv | Cadastro de canteiros |
| especies.csv | Dados das espécies |
| observacoes.csv | Observações da horta |
| eventos_manejo.csv | Registros de manejo |
| photo_metadata.csv | Metadados de fotos |

## 🚀 Funcionalidades
- Dashboard interativo
- Visualização de ciclos de plantio
- Indicadores de produção
- Registro de manejo
- Upload e consulta de imagens

## 🛠️ Tecnologias
- Python
- Streamlit
- Pandas
- Plotly / Matplotlib

## ▶️ Como Executar

```
pip install -r requirements_enhanced.txt
streamlit run app_enhanced.py
```

