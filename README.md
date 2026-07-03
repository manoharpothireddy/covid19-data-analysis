🦠 COVID-19 Global Data Analysis & Interactive Dashboard

An end-to-end data analytics portfolio project — from raw data ingestion to interactive dashboards — analysing 395,311 records across 237 countries from January 2020 to August 2024, with a deep focus on India's pandemic waves and global comparisons against the USA, Brazil, and the UK.


📌 Table of Contents

Project Overview
Tools & Technologies
Architecture
Folder Structure
How to Run
Key Findings & Insights
Dashboard Screenshots
Dataset Source & Credits


🔍 Project Overview
StageWhat happensCollectionDownloads OWID dataset with retry logicCleaning10-step Pandas pipeline + 10 derived KPIsStoragePostgreSQL COPY bulk load into star schemaAnalysisSciPy wave detection, correlation, risk scoringSQL10 queries: CTEs, DISTINCT ON, window functionsVisualisationPlotly Dash + Tableau + Power BI

🛠 Tools & Technologies
ToolPurposePython 3.xETL pipeline and analysisPandas / NumPyData cleaning and transformationSciPyWave detection algorithmPostgreSQLStar schema databaseSQLAnalytics queries and viewsPlotly DashInteractive web dashboardTableau DesktopExecutive dashboardPower BI DesktopBI dashboard with DAX measuresJupyter NotebookEDA and visualizations

🏗 Architecture
DATA SOURCES → PYTHON ETL → POSTGRESQL → BI LAYER
OWID CSV → data_collection.py → dim_country → Plotly Dash
         → data_cleaning.py  → dim_date   → Tableau
         → analysis.py       → fact_covid → Power BI
         → database.py       → 7 Views    → Jupyter

📁 Folder Structure
covid19-data-analysis/
├── run.py
├── requirements.txt
├── README.md
├── .env.example
├── data/
│   ├── raw/
│   └── processed/
├── src/
│   ├── data_collection.py
│   ├── data_cleaning.py
│   ├── analysis.py
│   └── database.py
├── sql/
│   ├── create_tables.sql
│   ├── views.sql
│   └── analysis_queries.sql
├── notebooks/
│   └── exploratory_analysis.ipynb
├── dashboard/
│   ├── app.py
│   ├── layouts.py
│   └── callbacks.py
└── docs/
    └── screenshots/

▶ How to Run
Step 1 — Clone repository
git clone https://github.com/manoharpothireddy/covid19-data-analysis.git
cd covid19-data-analysis
Step 2 — Setup
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Step 3 — Configure .env
copy .env.example .env
set DB_PASSWORD=your_password
Step 4 — Run pipeline
python run.py
Step 5 — Launch dashboard
python dashboard/app.py
Step 6 — Open notebook
jupyter notebook notebooks/exploratory_analysis.ipynb

📊 Key Findings
🇮🇳 India — 6 Waves Detected
WavePeak DatePeak Daily CasesVariantWave 1Sep 2020~97,000OriginalWave 2May 2021~414,000DeltaWave 3Sep 2021~45,000Delta subWave 4Jan 2022~347,000Omicron BA.1Wave 5Jul 2022~21,000Omicron BA.4/5Wave 6Apr 2023~12,000XBB variants
💉 Vaccination Impact

Pearson r = −0.42 between vaccination rate and CFR
Countries above 70% vaccination had 40-55% lower CFR

🔺 High-Risk Scoring
Composite = CFR×0.4 + Deaths/M×0.4 + (1−VaxRate)×0.2

📸 Dashboard Screenshots
Tableau Dashboard
Show Image
Power BI Global Overview
Show Image
India Deep Dive
Show Image
Jupyter Notebook
Show Image

📋 Dataset Source
ItemDetailDatasetOur World in Data COVID-19 DatasetURLhttps://github.com/owid/covid-19-dataCoverage237 countries, Jan 2020 – presentLicenseCreative Commons BY 4.0
Citation: Mathieu, E., Ritchie, H., Rodés-Guirao, L. et al. "Coronavirus Pandemic (COVID-19)." Our World in Data (2020).