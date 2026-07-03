"""
src/database.py
===============
Handles all PostgreSQL operations for the COVID-19 pipeline.

Responsibilities
----------------
1. Connect to PostgreSQL using credentials from .env
2. Execute DDL from sql/create_tables.sql
3. Bulk-load cleaned CSV into a staging table using PostgreSQL COPY
4. Populate star-schema tables (dim_country, dim_date, fact_covid_daily)
   from staging using INSERT ... SELECT
5. Create indexes on frequently-queried columns
6. Validate: assert CSV row count == PostgreSQL row count
7. Export SQL view results to data/processed/sql_results/

Why COPY instead of executemany?
---------------------------------
  psycopg2's cursor.copy_expert() streams the CSV directly into PostgreSQL
  using the server-side COPY protocol.  For 100k+ rows this is 10-50x faster
  than row-by-row INSERT and avoids Python-layer overhead entirely.
"""

import csv
import io
import logging
import os
from pathlib import Path

import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   os.getenv("DB_NAME",     "covid19_analysis"),
    "user":     os.getenv("DB_USER",     "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}

SQL_DIR       = Path(os.getenv("SQL_DIR", "sql"))
PROCESSED_DIR = Path(os.getenv("PROCESSED_DATA_DIR", "data/processed"))
SQL_RESULTS   = PROCESSED_DIR / "sql_results"

CLEANED_FILE = PROCESSED_DIR / "covid_cleaned.csv"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def get_connection() -> psycopg2.extensions.connection:
    """
    Open and return a psycopg2 connection using DB_CONFIG.
    Raises psycopg2.OperationalError if the connection fails.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False        # we manage transactions explicitly
        log.info(
            "Connected to PostgreSQL: host=%s  db=%s  user=%s",
            DB_CONFIG["host"], DB_CONFIG["dbname"], DB_CONFIG["user"],
        )
        return conn
    except psycopg2.OperationalError as exc:
        log.error("Cannot connect to PostgreSQL: %s", exc)
        log.error(
            "Ensure PostgreSQL is running and credentials in .env are correct.\n"
            "  host=%s  port=%s  db=%s  user=%s",
            DB_CONFIG["host"], DB_CONFIG["port"],
            DB_CONFIG["dbname"], DB_CONFIG["user"],
        )
        raise


def create_database_if_not_exists() -> None:
    """
    Connect to the default 'postgres' database and create covid19_analysis if
    it does not already exist.  Must run before get_connection() targets our DB.
    """
    admin_cfg = {**DB_CONFIG, "dbname": "postgres"}
    target_db = DB_CONFIG["dbname"]

    conn = psycopg2.connect(**admin_cfg)
    conn.autocommit = True            # CREATE DATABASE cannot run in a transaction

    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s;", (target_db,)
        )
        exists = cur.fetchone()
        if not exists:
            cur.execute(f'CREATE DATABASE "{target_db}";')
            log.info("Created database: %s", target_db)
        else:
            log.info("Database '%s' already exists.", target_db)

    conn.close()


# ---------------------------------------------------------------------------
# DDL helpers
# ---------------------------------------------------------------------------

def execute_sql_file(conn: psycopg2.extensions.connection, sql_path: Path) -> None:
    """
    Read a .sql file and execute it as a single batch.
    Commits on success; rolls back and re-raises on failure.
    """
    log.info("Executing SQL file: %s", sql_path)
    sql = sql_path.read_text(encoding="utf-8")

    with conn.cursor() as cur:
        try:
            cur.execute(sql)
            conn.commit()
            log.info("SQL file executed successfully: %s", sql_path.name)
        except Exception as exc:
            conn.rollback()
            log.error("Failed to execute %s: %s", sql_path.name, exc)
            raise


def create_schema(conn: psycopg2.extensions.connection, reload: bool = False) -> None:
    """
    Create all tables, views, and indexes.
    If reload=True, drop and recreate everything (useful during development).
    """
    if reload:
        log.info("--reload flag set: dropping existing tables ...")
        with conn.cursor() as cur:
            cur.execute("""
                DROP TABLE IF EXISTS fact_covid_daily CASCADE;
                DROP TABLE IF EXISTS dim_country     CASCADE;
                DROP TABLE IF EXISTS dim_date        CASCADE;
                DROP TABLE IF EXISTS staging_covid   CASCADE;
            """)
            conn.commit()
        log.info("Existing tables dropped.")

    create_tables_path = SQL_DIR / "create_tables.sql"
    views_path         = SQL_DIR / "views.sql"

    execute_sql_file(conn, create_tables_path)

    if views_path.exists():
        execute_sql_file(conn, views_path)
    else:
        log.warning("views.sql not found at %s — skipping.", views_path)


# ---------------------------------------------------------------------------
# COPY bulk load
# ---------------------------------------------------------------------------

def _df_to_csv_buffer(df: pd.DataFrame) -> io.StringIO:
    """
    Serialise a DataFrame to an in-memory CSV buffer suitable for
    psycopg2's copy_expert.

    Notes
    -----
    • NULL values are written as empty strings (PostgreSQL's COPY default).
    • We do NOT write the header row — COPY expects data only.
    • quoting=csv.QUOTE_NONNUMERIC ensures strings are quoted, preventing
      comma-in-value issues for country names.
    """
    buf = io.StringIO()
    df.to_csv(
        buf,
        index=False,
        header=False,
        na_rep="",                    # NaN → empty string → NULL in PG
        quoting=csv.QUOTE_NONNUMERIC,
    )
    buf.seek(0)
    return buf


def bulk_load_staging(conn: psycopg2.extensions.connection,
                      csv_path: Path = CLEANED_FILE) -> int:
    """
    Stream the cleaned CSV into staging_covid using PostgreSQL COPY.

    Steps
    -----
    1. Read the CSV into a DataFrame (we need column names to build COPY SQL).
    2. Truncate the staging table to ensure idempotency.
    3. Stream rows via copy_expert with a CSV buffer.
    4. Return the number of rows loaded.
    """
    log.info("Loading staging table from: %s", csv_path)
    df = pd.read_csv(csv_path, low_memory=False)

    # Replace NaN with None so to_csv writes empty strings (→ PG NULL)
    df = df.where(pd.notna(df), other=None)

    columns_csv  = ", ".join(f'"{c}"' for c in df.columns)
    copy_sql     = f'COPY staging_covid ({columns_csv}) FROM STDIN WITH (FORMAT CSV, NULL \'\')'

    buf = _df_to_csv_buffer(df)

    with conn.cursor() as cur:
        try:
            # Truncate first so re-runs stay idempotent
            cur.execute("TRUNCATE TABLE staging_covid;")

            cur.copy_expert(sql=copy_sql, file=buf)
            conn.commit()
        except Exception as exc:
            conn.rollback()
            log.error("COPY into staging_covid failed: %s", exc)
            raise

    row_count = len(df)
    log.info("Staging table loaded: %s rows.", f"{row_count:,}")
    return row_count


# ---------------------------------------------------------------------------
# Populate dimension and fact tables from staging
# ---------------------------------------------------------------------------

def populate_dim_country(conn: psycopg2.extensions.connection) -> None:
    """
    Upsert country dimension from staging using the latest non-null values.
    ON CONFLICT DO NOTHING avoids duplicates on re-runs.
    """
    log.info("Populating dim_country ...")
    sql = """
        INSERT INTO dim_country (
            iso_code, continent, location, population,
            population_density, median_age, aged_65_older,
            gdp_per_capita, cardiovasc_death_rate,
            diabetes_prevalence, life_expectancy, human_development_index
        )
        SELECT DISTINCT ON (iso_code)
            iso_code, continent, location,
            NULLIF(population,            '')::BIGINT,
            NULLIF(population_density,    '')::NUMERIC,
            NULLIF(median_age,            '')::NUMERIC,
            NULLIF(aged_65_older,         '')::NUMERIC,
            NULLIF(gdp_per_capita,        '')::NUMERIC,
            NULLIF(cardiovasc_death_rate, '')::NUMERIC,
            NULLIF(diabetes_prevalence,   '')::NUMERIC,
            NULLIF(life_expectancy,       '')::NUMERIC,
            NULLIF(human_development_index,'')::NUMERIC
        FROM staging_covid
        WHERE iso_code IS NOT NULL
          AND iso_code != ''
        ORDER BY iso_code, date DESC          -- pick the most recent demographic row
        ON CONFLICT (iso_code) DO NOTHING;
    """
    with conn.cursor() as cur:
        try:
            cur.execute(sql)
            conn.commit()
            cur.execute("SELECT COUNT(*) FROM dim_country;")
            count = cur.fetchone()[0]
            log.info("dim_country populated: %s countries.", f"{count:,}")
        except Exception as exc:
            conn.rollback()
            log.error("dim_country population failed: %s", exc)
            raise


def populate_dim_date(conn: psycopg2.extensions.connection) -> None:
    """
    Generate a complete calendar dimension from the min to max date in staging.
    Uses generate_series — a PostgreSQL set-returning function — so no Python
    loop is needed.
    """
    log.info("Populating dim_date ...")
    sql = """
        INSERT INTO dim_date (
            date_key, year, quarter, month, month_name,
            day_of_month, day_of_week, day_name, week_of_year
        )
        SELECT
            d::DATE                              AS date_key,
            EXTRACT(YEAR    FROM d)::INT         AS year,
            EXTRACT(QUARTER FROM d)::INT         AS quarter,
            EXTRACT(MONTH   FROM d)::INT         AS month,
            TO_CHAR(d, 'Month')                  AS month_name,
            EXTRACT(DAY     FROM d)::INT         AS day_of_month,
            EXTRACT(ISODOW  FROM d)::INT         AS day_of_week,   -- 1=Mon 7=Sun
            TO_CHAR(d, 'Day')                    AS day_name,
            EXTRACT(WEEK    FROM d)::INT         AS week_of_year
        FROM (
            SELECT generate_series(
                (SELECT MIN(date::DATE) FROM staging_covid WHERE date <> ''),
                (SELECT MAX(date::DATE) FROM staging_covid WHERE date <> ''),
                INTERVAL '1 day'
            ) AS d
        ) sub
        ON CONFLICT (date_key) DO NOTHING;
    """
    with conn.cursor() as cur:
        try:
            cur.execute(sql)
            conn.commit()
            cur.execute("SELECT COUNT(*) FROM dim_date;")
            count = cur.fetchone()[0]
            log.info("dim_date populated: %s date rows.", f"{count:,}")
        except Exception as exc:
            conn.rollback()
            log.error("dim_date population failed: %s", exc)
            raise


def populate_fact_table(conn: psycopg2.extensions.connection) -> None:
    """
    Move metrics from staging into fact_covid_daily.
    NULLIF(col, '')::TYPE safely casts empty strings to NULL.
    ON CONFLICT (iso_code, date) DO NOTHING makes re-runs safe.
    """
    log.info("Populating fact_covid_daily ...")
    sql = """
        INSERT INTO fact_covid_daily (
            iso_code, date,
            total_cases, new_cases, new_cases_smoothed,
            total_deaths, new_deaths, new_deaths_smoothed,
            total_cases_per_million, total_deaths_per_million,
            new_cases_per_million, new_deaths_per_million,
            total_tests, new_tests, positive_rate,
            total_vaccinations, people_vaccinated,
            people_fully_vaccinated, total_boosters,
            new_vaccinations, new_vaccinations_smoothed,
            stringency_index, reproduction_rate,
            case_fatality_rate, vaccination_rate,
            tests_per_case, mortality_rate_per_million,
            rolling_7day_cases, rolling_7day_deaths,
            rolling_14day_cases, rolling_14day_deaths,
            year, month, week, day_of_week, wave_number
        )
        SELECT
            iso_code,
            NULLIF(date,                     '')::DATE,
            NULLIF(total_cases,              '')::NUMERIC,
            NULLIF(new_cases,                '')::NUMERIC,
            NULLIF(new_cases_smoothed,       '')::NUMERIC,
            NULLIF(total_deaths,             '')::NUMERIC,
            NULLIF(new_deaths,               '')::NUMERIC,
            NULLIF(new_deaths_smoothed,      '')::NUMERIC,
            NULLIF(total_cases_per_million,  '')::NUMERIC,
            NULLIF(total_deaths_per_million, '')::NUMERIC,
            NULLIF(new_cases_per_million,    '')::NUMERIC,
            NULLIF(new_deaths_per_million,   '')::NUMERIC,
            NULLIF(total_tests,              '')::NUMERIC,
            NULLIF(new_tests,                '')::NUMERIC,
            NULLIF(positive_rate,            '')::NUMERIC,
            NULLIF(total_vaccinations,       '')::NUMERIC,
            NULLIF(people_vaccinated,        '')::NUMERIC,
            NULLIF(people_fully_vaccinated,  '')::NUMERIC,
            NULLIF(total_boosters,           '')::NUMERIC,
            NULLIF(new_vaccinations,         '')::NUMERIC,
            NULLIF(new_vaccinations_smoothed,'')::NUMERIC,
            NULLIF(stringency_index,         '')::NUMERIC,
            NULLIF(reproduction_rate,        '')::NUMERIC,
            NULLIF(case_fatality_rate,       '')::NUMERIC,
            NULLIF(vaccination_rate,         '')::NUMERIC,
            NULLIF(tests_per_case,           '')::NUMERIC,
            NULLIF(mortality_rate_per_million,'')::NUMERIC,
            NULLIF(rolling_7day_cases,       '')::NUMERIC,
            NULLIF(rolling_7day_deaths,      '')::NUMERIC,
            NULLIF(rolling_14day_cases,      '')::NUMERIC,
            NULLIF(rolling_14day_deaths,     '')::NUMERIC,
            NULLIF(year,                     '')::INTEGER,
            NULLIF(month,                    '')::INTEGER,
            NULLIF(week,                     '')::INTEGER,
            NULLIF(day_of_week,              '')::INTEGER,
            NULLIF(wave_number,              '')::INTEGER
        FROM staging_covid
        WHERE iso_code IS NOT NULL
          AND iso_code != ''
          AND date    IS NOT NULL
          AND date    != ''
        ON CONFLICT (iso_code, date) DO NOTHING;
    """
    with conn.cursor() as cur:
        try:
            cur.execute(sql)
            conn.commit()
            cur.execute("SELECT COUNT(*) FROM fact_covid_daily;")
            count = cur.fetchone()[0]
            log.info("fact_covid_daily populated: %s rows.", f"{count:,}")
        except Exception as exc:
            conn.rollback()
            log.error("fact_covid_daily population failed: %s", exc)
            raise


# ---------------------------------------------------------------------------
# Index creation
# ---------------------------------------------------------------------------

def create_indexes(conn: psycopg2.extensions.connection) -> None:
    """
    Create performance indexes after bulk load.
    Creating indexes AFTER insert is significantly faster than maintaining
    them during bulk writes.
    IF NOT EXISTS avoids errors on re-runs.
    """
    log.info("Creating indexes ...")
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_fact_iso      ON fact_covid_daily (iso_code);",
        "CREATE INDEX IF NOT EXISTS idx_fact_date     ON fact_covid_daily (date);",
        "CREATE INDEX IF NOT EXISTS idx_fact_iso_date ON fact_covid_daily (iso_code, date);",
        "CREATE INDEX IF NOT EXISTS idx_fact_year     ON fact_covid_daily (year);",
        "CREATE INDEX IF NOT EXISTS idx_fact_month    ON fact_covid_daily (year, month);",
    ]

    with conn.cursor() as cur:
        for stmt in index_statements:
            try:
                cur.execute(stmt)
                conn.commit()
            except Exception as exc:
                conn.rollback()
                log.warning("Index creation skipped (%s): %s", stmt[:60], exc)

    log.info("Index creation complete.")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_load(conn: psycopg2.extensions.connection,
                  csv_path: Path = CLEANED_FILE) -> bool:
    """
    Compare CSV row count against fact_covid_daily row count.

    Returns True if counts match (or are within a 1% tolerance for rows
    that may be filtered by the WHERE clause in populate_fact_table).
    Raises AssertionError if the discrepancy is greater than 1%.
    """
    log.info("--- Validating load ---")

    # CSV row count (minus header)
    csv_count = sum(1 for _ in open(csv_path, encoding="utf-8")) - 1

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM fact_covid_daily;")
        db_count = cur.fetchone()[0]

    log.info("CSV rows        : %s", f"{csv_count:,}")
    log.info("fact_covid rows : %s", f"{db_count:,}")

    difference  = abs(csv_count - db_count)
    tolerance   = max(1, int(csv_count * 0.01))   # allow up to 1% discrepancy

    if difference > tolerance:
        msg = (
            f"Row count mismatch: CSV={csv_count:,}  DB={db_count:,}  "
            f"diff={difference:,}  tolerance={tolerance:,}"
        )
        log.error(msg)
        raise AssertionError(msg)

    log.info(
        "Validation PASSED. Difference: %s row(s) (within 1%% tolerance).",
        f"{difference:,}",
    )
    return True


# ---------------------------------------------------------------------------
# SQL View exports
# ---------------------------------------------------------------------------

def export_view_results(conn: psycopg2.extensions.connection) -> None:
    """
    Run each analytical SQL view and export its result to a CSV file.
    These CSVs are what Tableau and Power BI will fall back to if a direct
    DB connection is not available.
    """
    SQL_RESULTS.mkdir(parents=True, exist_ok=True)

    views = {
        "v_global_daily_trend":     "query_global_daily_trend.csv",
        "v_continental_summary":    "query_continent_summary.csv",
        "v_country_latest":         "query_country_latest.csv",
        "v_india_timeline":         "query_india_timeline.csv",
        "v_vaccination_progress":   "query_vaccination_progress.csv",
        "v_high_risk_countries":    "query_high_risk_countries.csv",
    }

    for view_name, filename in views.items():
        try:
            df = pd.read_sql(f"SELECT * FROM {view_name};", conn)
            out = SQL_RESULTS / filename
            df.to_csv(out, index=False)
            log.info("Exported view %-30s → %s  (%s rows)", view_name, out.name, f"{len(df):,}")
        except Exception as exc:
            log.warning("Could not export view '%s': %s", view_name, exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_database_pipeline(reload: bool = False) -> None:
    """
    Full database ETL:
      1. Create DB if needed
      2. Connect
      3. Create schema (DDL)
      4. COPY staging
      5. Populate star-schema tables
      6. Build indexes
      7. Validate
      8. Export view CSVs
    """
    create_database_if_not_exists()
    conn = get_connection()

    try:
        create_schema(conn, reload=reload)
        csv_rows = bulk_load_staging(conn)
        populate_dim_country(conn)
        populate_dim_date(conn)
        populate_fact_table(conn)
        create_indexes(conn)
        validate_load(conn)
        export_view_results(conn)
        log.info("=== Database pipeline complete. ===")
    finally:
        conn.close()
        log.info("Database connection closed.")


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="COVID-19 Database Loader")
    parser.add_argument(
        "--reload", action="store_true",
        help="Drop and recreate all tables before loading."
    )
    args = parser.parse_args()
    run_database_pipeline(reload=args.reload)
