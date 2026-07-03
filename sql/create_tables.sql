-- =============================================================================
-- sql/create_tables.sql
-- COVID-19 Data Analysis — Star Schema DDL
-- Database: PostgreSQL 14+
-- =============================================================================
-- Table hierarchy (load order matters for FK constraints):
--   1. staging_covid      ← raw CSV dump (no FK constraints)
--   2. dim_country        ← country/demographic dimension
--   3. dim_date           ← calendar dimension
--   4. fact_covid_daily   ← daily metrics fact table (FKs to both dims)
-- =============================================================================


-- =============================================================================
-- STAGING TABLE
-- =============================================================================
-- All columns are TEXT so that the raw CSV can be loaded without type coercion.
-- The ETL Python code casts values during the INSERT ... SELECT into the fact
-- table.  This avoids COPY failures caused by malformed numeric strings.
-- =============================================================================

CREATE TABLE IF NOT EXISTS staging_covid (
    iso_code                    TEXT,
    continent                   TEXT,
    location                    TEXT,
    date                        TEXT,   -- kept as TEXT; cast to DATE in fact load
    -- Cases
    total_cases                 TEXT,
    new_cases                   TEXT,
    new_cases_smoothed          TEXT,
    total_cases_per_million     TEXT,
    new_cases_per_million       TEXT,
    -- Deaths
    total_deaths                TEXT,
    new_deaths                  TEXT,
    new_deaths_smoothed         TEXT,
    total_deaths_per_million    TEXT,
    new_deaths_per_million      TEXT,
    -- Testing
    total_tests                 TEXT,
    new_tests                   TEXT,
    positive_rate               TEXT,
    -- Hospitalisation
    icu_patients                TEXT,
    hosp_patients               TEXT,
    -- Vaccinations
    total_vaccinations          TEXT,
    people_vaccinated           TEXT,
    people_fully_vaccinated     TEXT,
    total_boosters              TEXT,
    new_vaccinations            TEXT,
    new_vaccinations_smoothed   TEXT,
    -- Demographics (static per country; repeated on every row in OWID)
    population                  TEXT,
    population_density          TEXT,
    median_age                  TEXT,
    aged_65_older               TEXT,
    gdp_per_capita              TEXT,
    cardiovasc_death_rate       TEXT,
    diabetes_prevalence         TEXT,
    life_expectancy             TEXT,
    human_development_index     TEXT,
    -- Policy
    stringency_index            TEXT,
    reproduction_rate           TEXT,
    -- Derived metrics computed in Python
    case_fatality_rate          TEXT,
    vaccination_rate            TEXT,
    tests_per_case              TEXT,
    mortality_rate_per_million  TEXT,
    rolling_7day_cases          TEXT,
    rolling_7day_deaths         TEXT,
    rolling_14day_cases         TEXT,
    rolling_14day_deaths        TEXT,
    -- Date parts
    year                        TEXT,
    month                       TEXT,
    week                        TEXT,
    day_of_week                 TEXT,
    wave_number                 TEXT
);


-- =============================================================================
-- DIMENSION TABLE: dim_country
-- =============================================================================
-- One row per country.  Demographic and socio-economic attributes are stored
-- here rather than on every fact row to avoid repeating 100k+ times.
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_country (
    iso_code                TEXT        PRIMARY KEY,   -- e.g. "IND", "USA"
    continent               TEXT,
    location                TEXT        NOT NULL,      -- human-readable country name
    population              BIGINT,
    population_density      NUMERIC,            -- people per km²
    median_age              NUMERIC,
    aged_65_older           NUMERIC,            -- % of population aged ≥65
    gdp_per_capita          NUMERIC,            -- USD, PPP adjusted
    cardiovasc_death_rate   NUMERIC,            -- deaths per 100k
    diabetes_prevalence     NUMERIC,            -- % of population
    life_expectancy         NUMERIC,
    human_development_index NUMERIC             -- 0.0 – 1.0
);

COMMENT ON TABLE  dim_country IS
    'Country-level demographic and socio-economic attributes. '
    'One row per country. Join to fact_covid_daily on iso_code.';
COMMENT ON COLUMN dim_country.aged_65_older IS
    'Percentage of the country population aged 65 or older.';
COMMENT ON COLUMN dim_country.human_development_index IS
    'UNDP HDI score (0 = lowest development, 1 = highest).';


-- =============================================================================
-- DIMENSION TABLE: dim_date
-- =============================================================================
-- Full calendar dimension generated by Python from the date range in staging.
-- Avoids repeated EXTRACT() calls in every analytical query.
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_date (
    date_key        DATE    PRIMARY KEY,
    year            INTEGER NOT NULL,
    quarter         INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month           INTEGER NOT NULL CHECK (month   BETWEEN 1 AND 12),
    month_name      TEXT    NOT NULL,   -- e.g. "January"
    day_of_month    INTEGER NOT NULL,
    day_of_week     INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),  -- ISO: 1=Mon
    day_name        TEXT    NOT NULL,   -- e.g. "Monday"
    week_of_year    INTEGER NOT NULL
);

COMMENT ON TABLE dim_date IS
    'Calendar dimension for time-intelligence queries. '
    'Join to fact_covid_daily on date = date_key.';


-- =============================================================================
-- FACT TABLE: fact_covid_daily
-- =============================================================================
-- One row per (country, date).  Contains all measurable daily metrics plus
-- derived and rolling metrics computed in Python.
--
-- IMPORTANT AGGREGATION RULE:
--   Total_* columns are CUMULATIVE. NEVER use SUM() on them.
--   Always use MAX() or filter to the latest date when aggregating.
--   Only new_* columns (daily deltas) are safe to SUM across time.
-- =============================================================================

CREATE TABLE IF NOT EXISTS fact_covid_daily (
    -- Natural composite key: one record per country per day
    iso_code                    TEXT    NOT NULL REFERENCES dim_country(iso_code),
    date                        DATE    NOT NULL REFERENCES dim_date(date_key),

    -- Cumulative Case metrics (use MAX / latest-date, never SUM across time)
    total_cases                 BIGINT,
    total_cases_per_million     NUMERIC,

    -- Daily Case metrics (safe to SUM across time)
    new_cases                   INTEGER,
    new_cases_smoothed          NUMERIC,
    new_cases_per_million       NUMERIC,

    -- Cumulative Death metrics
    total_deaths                BIGINT,
    total_deaths_per_million    NUMERIC,

    -- Daily Death metrics
    new_deaths                  INTEGER,
    new_deaths_smoothed         NUMERIC,
    new_deaths_per_million      NUMERIC,

    -- Testing metrics
    total_tests                 BIGINT,
    new_tests                   INTEGER,
    positive_rate               NUMERIC,      -- 0–1 fraction

    -- Vaccination metrics (cumulative)
    total_vaccinations          BIGINT,
    people_vaccinated           BIGINT,
    people_fully_vaccinated     BIGINT,
    total_boosters              BIGINT,

    -- Daily vaccination
    new_vaccinations            INTEGER,
    new_vaccinations_smoothed   NUMERIC,

    -- Policy & epidemiology
    stringency_index            NUMERIC,      -- 0–100
    reproduction_rate           NUMERIC,

    -- Python-derived metrics
    case_fatality_rate          NUMERIC,      -- total_deaths / total_cases
    vaccination_rate            NUMERIC,      -- fully_vaccinated / pop * 100
    tests_per_case              NUMERIC,      -- total_tests / total_cases
    mortality_rate_per_million  NUMERIC,

    -- Rolling averages (computed by Pandas per country)
    rolling_7day_cases          NUMERIC,
    rolling_7day_deaths         NUMERIC,
    rolling_14day_cases         NUMERIC,
    rolling_14day_deaths        NUMERIC,

    -- Date parts (denormalised for fast GROUP BY without joining dim_date)
    year                        INTEGER,
    month                       INTEGER,
    week                        INTEGER,
    day_of_week                 INTEGER,

    -- Pandemic wave label assigned by wave-detection algorithm
    wave_number                 INTEGER,

    -- Composite PK prevents duplicate (country, date) inserts
    PRIMARY KEY (iso_code, date)
);

COMMENT ON TABLE  fact_covid_daily IS
    'Daily COVID-19 metrics per country. '
    'Cumulative (total_*) columns must use MAX() or latest-date filtering. '
    'Daily (new_*) columns are safe to SUM across a date range.';
COMMENT ON COLUMN fact_covid_daily.case_fatality_rate IS
    'Proportion of confirmed cases that resulted in death (total_deaths / total_cases). '
    'Not a percentage — multiply by 100 for CFR%.';
COMMENT ON COLUMN fact_covid_daily.vaccination_rate IS
    'Percentage of country population that is fully vaccinated.';
COMMENT ON COLUMN fact_covid_daily.wave_number IS
    'Pandemic wave label, assigned by scipy.signal.find_peaks on smoothed new cases.';
