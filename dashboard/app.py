"""
COVID-19 Global Analytics Dashboard — Main Application
======================================================
Plotly Dash application with PostgreSQL + CSV fallback data loading.
"""

import os
import sys
from pathlib import Path
import dash
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import datetime

# ---------------------------------------------------------------------------
# App Initialization
# ---------------------------------------------------------------------------
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.DARKLY,
        "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Outfit:wght@400;500;600;700;800&display=swap",
    ],
    suppress_callback_exceptions=True,
    title="COVID-19 Global Analytics Dashboard",
    update_title="Loading…",
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        {"name": "description", "content": "Interactive COVID-19 analytics dashboard with India deep-dive, global trends, vaccination analysis, and SQL insights."},
        {"property": "og:title", "content": "COVID-19 Global Analytics Dashboard"},
        {"property": "og:type", "content": "website"},
        {"charset": "UTF-8"},
    ],
)

server = app.server  # For production WSGI deployment

# ---------------------------------------------------------------------------
# Data‑Loading Helpers
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "processed")


def _try_postgres():
    """Attempt to load data from PostgreSQL. Returns None on failure."""
    try:
        import psycopg2
        from sqlalchemy import create_engine

        engine = create_engine(
            "postgresql://postgres:postgres@localhost:5432/covid19_analysis"
        )
        covid_df = pd.read_sql("SELECT * FROM covid_data", engine, parse_dates=["date"])
        india_df = pd.read_sql(
            "SELECT * FROM covid_data WHERE location = 'India'",
            engine,
            parse_dates=["date"],
        )
        country_summary = pd.read_sql("SELECT * FROM country_summary", engine)
        print("[✓] Loaded data from PostgreSQL")
        return covid_df, india_df, country_summary
    except Exception as exc:
        print(f"[!] PostgreSQL unavailable ({exc}). Falling back to CSV files.")
        return None


def _try_csv():
    """Load from CSV files in data/processed/."""
    files = {
        "covid_cleaned.csv": "date",
        "india_covid.csv": "date",
        "country_summary.csv": None,
    }
    missing = [f for f in files if not os.path.isfile(os.path.join(DATA_DIR, f))]
    if missing:
        print(f"[✗] Missing CSV files: {missing}")
        return None

    covid_df = pd.read_csv(
        os.path.join(DATA_DIR, "covid_cleaned.csv"), parse_dates=["date"]
    )
    india_df = pd.read_csv(
        os.path.join(DATA_DIR, "india_covid.csv"), parse_dates=["date"]
    )
    country_summary = pd.read_csv(os.path.join(DATA_DIR, "country_summary.csv"))
    print("[✓] Loaded data from CSV files")
    return covid_df, india_df, country_summary


def _generate_sample_data():
    """Generate minimal sample data so the dashboard can still render."""
    import numpy as np

    print("[⚑] Generating sample demo data for preview purposes.")
    dates = pd.date_range("2020-01-01", "2023-12-31", freq="D")
    countries = ["India", "United States", "Brazil", "United Kingdom", "Germany",
                 "France", "Russia", "Japan", "South Korea", "Italy",
                 "Spain", "Turkey", "Mexico", "Indonesia", "Argentina"]
    continents = {"India": "Asia", "United States": "North America", "Brazil": "South America",
                  "United Kingdom": "Europe", "Germany": "Europe", "France": "Europe",
                  "Russia": "Europe", "Japan": "Asia", "South Korea": "Asia",
                  "Italy": "Europe", "Spain": "Europe", "Turkey": "Asia",
                  "Mexico": "North America", "Indonesia": "Asia", "Argentina": "South America"}
    iso_codes = {"India": "IND", "United States": "USA", "Brazil": "BRA",
                 "United Kingdom": "GBR", "Germany": "DEU", "France": "FRA",
                 "Russia": "RUS", "Japan": "JPN", "South Korea": "KOR",
                 "Italy": "ITA", "Spain": "ESP", "Turkey": "TUR",
                 "Mexico": "MEX", "Indonesia": "IDN", "Argentina": "ARG"}
    populations = {"India": 1.4e9, "United States": 3.31e8, "Brazil": 2.13e8,
                   "United Kingdom": 6.7e7, "Germany": 8.3e7, "France": 6.7e7,
                   "Russia": 1.44e8, "Japan": 1.26e8, "South Korea": 5.18e7,
                   "Italy": 6.04e7, "Spain": 4.73e7, "Turkey": 8.43e7,
                   "Mexico": 1.29e8, "Indonesia": 2.74e8, "Argentina": 4.52e7}

    rows = []
    for country in countries:
        np.random.seed(hash(country) % 2**31)
        pop = populations[country]
        cum_cases = 0
        cum_deaths = 0
        cum_vacc = 0
        for d in dates:
            day_idx = (d - dates[0]).days
            # Simulate waves
            wave1 = max(0, np.sin((day_idx - 100) / 80) * 0.6) if 60 < day_idx < 300 else 0
            wave2 = max(0, np.sin((day_idx - 400) / 60) * 1.0) if 350 < day_idx < 600 else 0
            wave3 = max(0, np.sin((day_idx - 750) / 50) * 0.8) if 700 < day_idx < 900 else 0
            intensity = (wave1 + wave2 + wave3) * pop / 1e6
            new_cases = max(0, int(intensity * (1 + np.random.normal(0, 0.3))))
            new_deaths = max(0, int(new_cases * np.random.uniform(0.01, 0.03)))
            new_vacc = max(0, int(pop * 0.003 * max(0, (day_idx - 365) / 365) * np.random.uniform(0.5, 1.5))) if day_idx > 365 else 0
            cum_cases += new_cases
            cum_deaths += new_deaths
            cum_vacc += new_vacc
            rows.append({
                "date": d,
                "location": country,
                "iso_code": iso_codes[country],
                "continent": continents[country],
                "population": pop,
                "new_cases": new_cases,
                "new_deaths": new_deaths,
                "total_cases": cum_cases,
                "total_deaths": cum_deaths,
                "new_vaccinations": new_vacc,
                "total_vaccinations": cum_vacc,
                "people_vaccinated": int(cum_vacc * 0.6),
                "people_fully_vaccinated": int(cum_vacc * 0.45),
                "new_cases_smoothed": new_cases,
                "new_deaths_smoothed": new_deaths,
            })

    covid_df = pd.DataFrame(rows)

    # Smoothed columns via rolling
    for country in countries:
        mask = covid_df["location"] == country
        covid_df.loc[mask, "new_cases_smoothed"] = (
            covid_df.loc[mask, "new_cases"].rolling(7, min_periods=1).mean().values
        )
        covid_df.loc[mask, "new_deaths_smoothed"] = (
            covid_df.loc[mask, "new_deaths"].rolling(7, min_periods=1).mean().values
        )

    india_df = covid_df[covid_df["location"] == "India"].copy().reset_index(drop=True)

    # Country summary
    summary_rows = []
    for country in countries:
        cdf = covid_df[covid_df["location"] == country]
        last = cdf.iloc[-1]
        pop = populations[country]
        summary_rows.append({
            "location": country,
            "iso_code": iso_codes[country],
            "continent": continents[country],
            "population": pop,
            "total_cases": last["total_cases"],
            "total_deaths": last["total_deaths"],
            "total_vaccinations": last["total_vaccinations"],
            "people_vaccinated": last["people_vaccinated"],
            "people_fully_vaccinated": last["people_fully_vaccinated"],
            "case_fatality_rate": round(last["total_deaths"] / max(1, last["total_cases"]) * 100, 2),
            "cases_per_million": round(last["total_cases"] / pop * 1e6, 1),
            "deaths_per_million": round(last["total_deaths"] / pop * 1e6, 1),
            "vaccination_rate": round(last["people_vaccinated"] / pop * 100, 1),
        })
    country_summary = pd.DataFrame(summary_rows)

    return covid_df, india_df, country_summary


def load_all_data():
    """Try PostgreSQL → CSV → sample data."""
    result = _try_postgres()
    if result is not None:
        return result

    result = _try_csv()
    if result is not None:
        return result

    return _generate_sample_data()


# ---------------------------------------------------------------------------
# Load Data into Module‑Level Variables
# ---------------------------------------------------------------------------
covid_df, india_df, country_summary = load_all_data()

# Ensure essential columns exist with safe defaults
for col in ["new_cases_smoothed", "new_deaths_smoothed"]:
    if col not in covid_df.columns:
        base = col.replace("_smoothed", "")
        if base in covid_df.columns:
            covid_df[col] = (
                covid_df.groupby("location")[base]
                .transform(lambda s: s.rolling(7, min_periods=1).mean())
            )
        else:
            covid_df[col] = 0

DATA_LOADED = True
LAST_UPDATED = datetime.now().strftime("%B %d, %Y at %I:%M %p")

# ---------------------------------------------------------------------------
# Import Layout & Callbacks (AFTER data is loaded)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))
from layouts import build_layout  # noqa: E402
from callbacks import register_callbacks  # noqa: E402

app.layout = build_layout(app)
register_callbacks(app)

# ---------------------------------------------------------------------------
# Run Dev Server
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n🦠  COVID-19 Global Analytics Dashboard")
    print(f"   Data rows  : {len(covid_df):,}")
    print(f"   Countries  : {covid_df['location'].nunique()}")
    print(f"   Date range : {covid_df['date'].min().date()} → {covid_df['date'].max().date()}\n")
    app.run(debug=True, host="127.0.0.1", port=8050)
