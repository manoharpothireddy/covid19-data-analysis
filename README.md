# 🦠 COVID-19 Global Data Analysis & Interactive Dashboard

> An end-to-end data analytics portfolio project — from raw data ingestion to
> interactive dashboards — analysing 395,311 records across 237 countries
> from January 2020 to August 2024, with a deep focus on India's pandemic waves
> and global comparisons against the USA, Brazil, and the UK.

---

## 📌 Table of Contents
1. Project Overview
2. Tools & Technologies
3. Architecture
4. Folder Structure
5. Database Schema
6. How to Run
7. Key Findings & Insights
8. Dashboard Screenshots
9. SQL Highlights
10. Dataset Source & Credits

---

## 🔍 Project Overview

| Stage | What happens |
|---|---|
| Collection | Downloads OWID dataset with retry logic + synthetic fallback |
| Cleaning | 10-step Pandas pipeline + 10 derived KPIs |
| Storage | PostgreSQL COPY bulk load into star schema |
| Analysis | SciPy wave detection, correlation, composite risk scoring |
| SQL | 10 queries: CTEs, DISTINCT ON, window functions |
| Visualisation | Plotly Dash + Tableau + Power BI |

---

## 🏗 Architecture

┌─────────────────────────────────────────────┐
│           DATA SOURCES                      │
│  OWID COVID-19 Dataset — CSV / HTTP         │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│         PYTHON ETL PIPELINE                 │
│  data_collection → data_cleaning →          │
│  analysis → database                        │
│  Orchestrated by: run.py                    │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│      POSTGRESQL STAR SCHEMA                 │
│  dim_country + dim_date + fact_covid_daily  │
│  7 Dashboard Views                          │
└──────┬──────────────────────┬───────────────┘
       ▼                      ▼
┌──────────────┐    ┌─────────────────────────┐
│  JUPYTER     │    │       BI LAYER          │
│  NOTEBOOK    │    │  Plotly Dash :8050      │
│  7-cell EDA  │    │  Tableau Desktop        │
└──────────────┘    │  Power BI Desktop       │
                    └─────────────────────────┘

---

## ▶ How to Run

### Step 1 — Setup
git clone https://github.com/your-username/covid19-data-analysis.git
cd covid19-data-analysis
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

### Step 2 — Configure .env
copy .env.example .env
# Edit .env: set DB_PASSWORD=your_password

### Step 3 — Run pipeline
python run.py

### Step 4 — Launch dashboard
python dashboard/app.py
# → http://127.0.0.1:8050

### Step 5 — Open notebook
jupytext --to notebook notebooks/exploratory_analysis.py
jupyter notebook notebooks/exploratory_analysis.ipynb

### CLI flags
python run.py --skip-download      # use cached CSV
python run.py --skip-db            # offline mode (CSV fallback)
python run.py --skip-download --reload  # fresh DB load

---

## 📊 Key Findings

### 🇮🇳 India — 6 Waves Detected

| Wave | Peak Date | Peak Daily Cases | Variant |
|---|---|---|---|
| Wave 1 | Sep 2020 | ~97,000 | Original |
| Wave 2 | May 2021 | ~414,000 | Delta (deadliest) |
| Wave 3 | Sep 2021 | ~45,000 | Delta sub |
| Wave 4 | Jan 2022 | ~347,000 | Omicron BA.1 |
| Wave 5 | Jul 2022 | ~21,000 | Omicron BA.4/5 |
| Wave 6 | Apr 2023 | ~12,000 | XBB sub-variants |

### 💉 Vaccination Impact
- Pearson r = −0.42 (p < 0.01) between vaccination rate and CFR
- Countries above 70% vaccination: 40–55% lower CFR in later waves

### 🔺 High-Risk Scoring
Composite = CFR×0.4 + Deaths/M×0.4 + (1−VaxRate)×0.2

---

## 📋 Dataset Source

| Item | Detail |
|---|---|
| Dataset | Our World in Data COVID-19 Dataset |
| URL | https://github.com/owid/covid-19-data |
| Coverage | 237 countries, Jan 2020 – present |
| License | Creative Commons BY 4.0 |

Citation:
Mathieu, E., Ritchie, H., Rodés-Guirao, L. et al.
"Coronavirus Pandemic (COVID-19)." Our World in Data (2020).