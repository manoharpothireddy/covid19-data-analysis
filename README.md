# 🦠 COVID-19 Global Data Analysis & Interactive Dashboard

> An end-to-end data analytics portfolio project — from raw data ingestion to
> interactive dashboards — analysing **395,311 records** across **237 countries**
> from **January 2020 to August 2024**, with a deep focus on India's pandemic
> waves and global comparisons against the USA, Brazil, and the UK.

---

## 📌 Table of Contents
1. [Project Overview](#-project-overview)
2. [Tools & Technologies](#-tools--technologies)
3. [Architecture](#-architecture)
4. [Folder Structure](#-folder-structure)
5. [Database Schema](#-database-schema)
6. [How to Run](#-how-to-run)
7. [Key Findings](#-key-findings)
8. [Dashboard Screenshots](#-dashboard-screenshots)
9. [SQL Highlights](#-sql-highlights)
10. [Dataset Source & Credits](#-dataset-source--credits)

---

## 🔍 Project Overview

This project performs a complete end-to-end COVID-19 data analysis using
the Our World in Data (OWID) dataset. The pipeline downloads, cleans,
transforms, and loads data into a PostgreSQL star schema, then visualizes
insights through Plotly Dash, Tableau, and Power BI dashboards.

| Stage | Tool | What Happens |
|-------|------|-------------|
| **Collection** | `data_collection.py` | Downloads OWID CSV with retry logic + fallback |
| **Cleaning** | `data_cleaning.py` | 10-step Pandas pipeline, 10 derived KPIs |
| **Analysis** | `analysis.py` | SciPy wave detection, correlation, risk scoring |
| **Storage** | `database.py` | PostgreSQL COPY bulk load into star schema |
| **SQL** | `analysis_queries.sql` | 10 queries: CTEs, window functions, DISTINCT ON |
| **Visualization** | Dash + Tableau + Power BI | Interactive dashboards |
| **EDA** | Jupyter Notebook | 7-cell exploratory analysis with Plotly charts |

---

## 🛠 Tools & Technologies

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.x | ETL pipeline and analysis |
| Pandas | ≥ 2.0.0 | Data cleaning and transformation |
| NumPy | ≥ 1.24.0 | Numerical computations |
| SciPy | ≥ 1.11.0 | Wave detection algorithm |
| psycopg2 | ≥ 2.9.9 | PostgreSQL connector |
| SQLAlchemy | ≥ 2.0.0 | ORM for Pandas read_sql |
| requests | ≥ 2.31.0 | OWID dataset download |
| tqdm | ≥ 4.66.0 | Download progress bar |
| python-dotenv | ≥ 1.0.0 | Environment variable management |
| Plotly | ≥ 5.15.0 | Interactive visualizations |
| Matplotlib | ≥ 3.7.0 | Static charts in notebook |
| Seaborn | ≥ 0.12.0 | Missing value heatmap |
| statsmodels | ≥ 0.14.0 | Statistical analysis |
| Jupyter | ≥ 1.0.0 | EDA notebook |
| PostgreSQL | 18 | Star schema database |
| Tableau Desktop | Latest | Executive dashboard |
| Power BI Desktop | Latest | BI dashboard with DAX |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────┐
│              DATA SOURCE                        │
│   OWID COVID-19 Dataset (CSV / HTTP)            │
│   395,311 rows · 237 countries · Jan2020-Aug2024│
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│           PYTHON ETL PIPELINE (run.py)          │
│                                                 │
│  data_collection.py  →  Download + validate     │
│  data_cleaning.py    →  Clean + transform       │
│  analysis.py         →  Wave detect + score     │
│  database.py         →  COPY bulk load to PG    │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│         POSTGRESQL STAR SCHEMA                  │
│                                                 │
│   staging_covid     (TEXT staging table)        │
│   dim_country       (237 rows)                  │
│   dim_date          (1,688 rows)                │
│   fact_covid_daily  (395,311 rows)              │
│   7 Dashboard Views                             │
└──────────┬───────────────────┬──────────────────┘
           ▼                   ▼
┌──────────────────┐  ┌────────────────────────────┐
│  JUPYTER         │  │        BI LAYER            │
│  NOTEBOOK        │  │                            │
│  7-cell EDA      │  │  Plotly Dash  :8050        │
│  Plotly charts   │  │  Tableau Desktop           │
│  Wave analysis   │  │  Power BI Desktop          │
└──────────────────┘  └────────────────────────────┘
```

---

## 📁 Folder Structure

```
covid19-data-analysis/
│
├── run.py                          # Master pipeline orchestrator
├── requirements.txt                # All Python dependencies
├── README.md                       # Project documentation
├── .env.example                    # Environment variables template
├── .gitignore                      # Git exclusion rules
│
├── src/                            # Python source code
│   ├── __init__.py                 # Package initializer
│   ├── data_collection.py          # OWID download with retry + fallback
│   ├── data_cleaning.py            # Cleaning, imputation, derived metrics
│   ├── analysis.py                 # Wave detection, correlation, risk scoring
│   └── database.py                 # PostgreSQL COPY bulk load + validation
│
├── sql/                            # SQL files
│   ├── create_tables.sql           # Star schema DDL
│   ├── views.sql                   # 7 dashboard-ready PostgreSQL views
│   └── analysis_queries.sql        # 10 advanced portfolio SQL queries
│
├── notebooks/
│   └── exploratory_analysis.ipynb  # 7-cell EDA with Plotly charts
│
├── dashboard/                      # Plotly Dash web app
│   ├── app.py                      # Dash entry point
│   ├── layouts.py                  # 4-page dashboard layouts
│   ├── callbacks.py                # 5 interactive callbacks
│   ├── assets/                     # CSS dark theme styles
│   └── COVID19_Dashboard.twb       # Tableau workbook
│
├── data/
│   ├── raw/                        # Original OWID CSV (unmodified)
│   └── processed/                  # Cleaned CSVs + SQL exports
│       ├── covid_cleaned.csv       # Global cleaned dataset (395,311 rows)
│       ├── india_covid.csv         # India-specific dataset (1,682 rows)
│       ├── country_summary.csv     # Latest snapshot per country (237 rows)
│       ├── analysis/
│       │   ├── risk_scores.csv     # Composite risk scores (212 countries)
│       │   ├── correlation_matrix.csv
│       │   └── india_with_waves.csv
│       └── sql_results/            # SQL view exports for BI tools
│
└── docs/
    └── screenshots/                # Dashboard screenshots
```

---

## 🗄 Database Schema

```
┌─────────────────┐         ┌──────────────────────┐
│   dim_country   │         │      dim_date        │
│─────────────────│         │──────────────────────│
│ iso_code (PK)   │         │ date_key (PK)        │
│ location        │         │ year                 │
│ continent       │         │ quarter              │
│ population      │         │ month / month_name   │
│ median_age      │         │ day_of_week          │
│ gdp_per_capita  │         │ week_of_year         │
│ human_dev_index │         └──────────┬───────────┘
└────────┬────────┘                    │
         └──────────────┬──────────────┘
                        ▼
           ┌────────────────────────┐
           │    fact_covid_daily    │
           │────────────────────────│
           │ iso_code (FK)          │
           │ date (FK)              │
           │ total_cases            │
           │ new_cases              │
           │ new_cases_smoothed     │
           │ total_deaths           │
           │ new_deaths             │
           │ total_vaccinations     │
           │ people_fully_vaccinated│
           │ vaccination_rate       │
           │ case_fatality_rate     │
           │ rolling_7day_cases     │
           │ rolling_14day_cases    │
           │ wave_number            │
           └────────────────────────┘
```

> ⚠ **IMPORTANT:** `total_*` columns are CUMULATIVE.
> Always use `MAX()` — never `SUM()` across dates.

---

## ▶ How to Run

### Prerequisites
- Python 3.9+
- PostgreSQL 18 installed and running
- Tableau Desktop (for .twb dashboard)
- Power BI Desktop (for Power BI dashboard)

### Step 1 — Clone Repository
```bash
git clone https://github.com/manoharpothireddy/covid19-data-analysis.git
cd covid19-data-analysis
```

### Step 2 — Create Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\Activate.ps1

# Mac/Linux
python -m venv venv
source venv/bin/activate
```

### Step 3 — Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Configure Environment
```bash
# Windows
copy .env.example .env

# Mac/Linux
cp .env.example .env
```

Open `.env` and fill in your PostgreSQL credentials:
```
DB_NAME=covid19_analysis
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

### Step 5 — Create PostgreSQL Database
```sql
-- Run in pgAdmin or psql
CREATE DATABASE covid19_analysis;
```

### Step 6 — Run Full Pipeline
```bash
python run.py
```

Expected output:
```
[1/4] Data Collection   ✔  PASSED  (93.8 MB downloaded)
[2/4] Data Cleaning     ✔  PASSED  (395,311 rows processed)
[3/4] Analysis          ✔  PASSED  (6 India waves detected)
[4/4] Database Load     ✔  PASSED  (star schema populated)
```

### Step 7 — Launch Dash Dashboard
```bash
cd dashboard
python app.py
# Open browser → http://127.0.0.1:8050
```

### Step 8 — Open Jupyter Notebook
```bash
jupyter notebook notebooks/exploratory_analysis.ipynb
# Kernel → Restart and Run All
```

### ⚙ Pipeline CLI Flags
```bash
python run.py --skip-download           # Use cached CSV
python run.py --skip-db                 # Offline mode (CSV only)
python run.py --skip-download --reload  # Fresh DB load
```

---

## 📊 Key Findings

### 🇮🇳 India — 6 Pandemic Waves Detected

| Wave | Peak Date | Peak Daily Cases | Variant |
|------|-----------|-----------------|---------|
| Wave 1 | 23 Sep 2020 | 92,323 | Original strain |
| Wave 2 | 12 May 2021 | 391,280 | Delta (deadliest) |
| Wave 3 | 08 Sep 2021 | 41,949 | Delta sub-variant |
| Wave 4 | 26 Jan 2022 | 302,157 | Omicron BA.1 |
| Wave 5 | 27 Jul 2022 | 19,737 | Omicron BA.4/5 |
| Wave 6 | 26 Apr 2023 | 10,553 | XBB sub-variants |

> Peaks detected using `scipy.signal.find_peaks` on 7-day smoothed cases
> with `distance=30` and `prominence=5000`.

### 💉 Vaccination Impact
- **Pearson r = −0.41** (p < 0.001) between vaccination rate and CFR
- **Spearman ρ = −0.55** (p < 0.001) — strong negative correlation
- Higher vaccination rates consistently linked to lower case fatality rates

### 🔺 High-Risk Country Scoring
```
Composite Risk Score =
    (CFR × 0.4) +
    (Deaths per Million normalized × 0.4) +
    (1 − Vaccination Rate × 0.2)
```

### 🌍 Global Statistics
- Total confirmed cases: **776M+**
- Total deaths: **7M+**
- Countries analyzed: **237**
- Date range: **Jan 2020 – Aug 2024**

---

## 📸 Dashboard Screenshots

### Plotly Dash — Interactive Web Dashboard
![Dash](docs/screenshots/dash_dashboard.png)

### Tableau — Global Executive Dashboard
![Tableau](docs/screenshots/tableau_dashboard.png)

### Power BI — Global Overview
![Power BI Global](docs/screenshots/powerbi_global.png)

### Power BI — India Deep Dive
![Power BI India](docs/screenshots/powerbi_india.png)

### Jupyter — India Wave Analysis
![Jupyter Waves](docs/screenshots/jupyter_india_waves.png)

### Jupyter — Vaccination vs CFR Scatter
![Jupyter Scatter](docs/screenshots/jupyter_vaccination_scatter.png)

---

## 🗂 SQL Highlights

### 7 Dashboard-Ready Views
| View | Purpose |
|------|---------|
| `v_country_latest` | Latest snapshot per country using DISTINCT ON |
| `v_global_daily_trend` | Daily global aggregates (SUM of new_* columns) |
| `v_india_timeline` | Complete India daily timeline |
| `v_continental_summary` | Continent-level rollup |
| `v_high_risk_countries` | Top 20 by composite risk score |
| `v_vaccination_progress` | Vaccination rate over time |
| `v_india_vs_benchmarks` | India vs USA, Brazil, UK comparison |

### Key SQL Techniques Used
```sql
-- 1. DISTINCT ON for latest row per country
SELECT DISTINCT ON (iso_code) *
FROM fact_covid_daily
ORDER BY iso_code, date DESC;

-- 2. LAG() for Month-over-Month growth
LAG(SUM(new_cases)) OVER (
    PARTITION BY location
    ORDER BY DATE_TRUNC('month', date)
) AS prev_month_cases

-- 3. Safe division with NULLIF
DIVIDE(total_deaths, NULLIF(total_cases, 0)) * 100 AS cfr_pct
```

---

## 📋 Dataset Source & Credits

| Item | Detail |
|------|--------|
| **Dataset** | Our World in Data COVID-19 Dataset |
| **URL** | https://github.com/owid/covid-19-data |
| **Coverage** | 237 countries, Jan 2020 – present |
| **Records** | 395,311 rows, 48 columns after cleaning |
| **License** | Creative Commons BY 4.0 |

**Citation:**
> Mathieu, E., Ritchie, H., Rodés-Guirao, L. et al.
> "Coronavirus Pandemic (COVID-19)." *Our World in Data* (2020).
> https://ourworldindata.org/coronavirus

---

## 👤 Author

**Manohar Pothireddy**
- GitHub: [@manoharpothireddy](https://github.com/manoharpothireddy)
- Project: [covid19-data-analysis](https://github.com/manoharpothireddy/covid19-data-analysis)

---

*Built as a portfolio project demonstrating end-to-end data analytics skills
using Python, SQL, PostgreSQL, Tableau, and Power BI.*
