-- =============================================================================
-- sql/views.sql
-- COVID-19 Dashboard Views — Pre-aggregated for BI Consumption
-- Database: PostgreSQL 14+
-- =============================================================================
-- These views are consumed by:
--   1. Plotly Dash dashboard (via SQLAlchemy / psycopg2)
--   2. Tableau (direct PostgreSQL connection)
--   3. Power BI (direct PostgreSQL connection or CSV exports)
-- =============================================================================
-- View naming convention: v_<purpose>
-- All views use CREATE OR REPLACE so they are safe to re-run.
-- =============================================================================


-- =============================================================================
-- VIEW 1: v_global_daily_trend
-- Daily worldwide totals of new cases and new deaths (sum across all countries)
-- Use: Line chart — Global Cases & Deaths over time
-- =============================================================================

CREATE OR REPLACE VIEW v_global_daily_trend AS
SELECT
    date,
    SUM(new_cases)                          AS global_new_cases,
    SUM(new_deaths)                         AS global_new_deaths,
    ROUND(AVG(new_cases_smoothed), 2)       AS avg_smoothed_cases,     -- avg of country-level 7d MA
    ROUND(AVG(new_deaths_smoothed), 2)      AS avg_smoothed_deaths,
    ROUND(AVG(reproduction_rate), 3)        AS avg_reproduction_rate,
    ROUND(AVG(stringency_index), 2)         AS avg_stringency_index
FROM fact_covid_daily
GROUP BY date
ORDER BY date;

COMMENT ON VIEW v_global_daily_trend IS
    'Daily worldwide aggregates. new_* columns are safe to SUM across countries.';


-- =============================================================================
-- VIEW 2: v_continental_summary
-- Latest snapshot grouped by continent
-- Use: Donut chart, Stacked bar, Continental KPI cards
-- =============================================================================

CREATE OR REPLACE VIEW v_continental_summary AS
WITH latest AS (
    SELECT DISTINCT ON (f.iso_code)
        c.continent,
        c.population,
        f.total_cases,
        f.total_deaths,
        f.people_fully_vaccinated,
        f.vaccination_rate,
        f.case_fatality_rate
    FROM fact_covid_daily f
    JOIN dim_country c USING (iso_code)
    WHERE c.continent IS NOT NULL
    ORDER BY f.iso_code, f.date DESC
)
SELECT
    continent,
    COUNT(*)                                                             AS country_count,
    SUM(total_cases)                                                     AS total_cases,
    SUM(total_deaths)                                                    AS total_deaths,
    SUM(population)                                                      AS total_population,
    ROUND(SUM(total_cases)::NUMERIC / NULLIF(SUM(population), 0) * 1e6, 2) AS cases_per_million,
    ROUND(SUM(total_deaths)::NUMERIC / NULLIF(SUM(population), 0) * 1e6, 2) AS deaths_per_million,
    ROUND(SUM(total_deaths)::NUMERIC / NULLIF(SUM(total_cases), 0) * 100, 4) AS cfr_pct,
    ROUND(AVG(vaccination_rate), 2)                                      AS avg_vaccination_rate_pct
FROM latest
GROUP BY continent
ORDER BY total_cases DESC;

COMMENT ON VIEW v_continental_summary IS
    'Latest totals per continent. total_* are MAX per country then SUM across countries.';


-- =============================================================================
-- VIEW 3: v_country_latest
-- One row per country: the latest record available
-- Use: Choropleth map, Country ranking table, Country KPI cards
-- =============================================================================

CREATE OR REPLACE VIEW v_country_latest AS
SELECT DISTINCT ON (f.iso_code)
    f.iso_code,
    c.location,
    c.continent,
    c.population,
    c.gdp_per_capita,
    c.median_age,
    c.human_development_index,
    f.date                          AS latest_date,
    f.total_cases,
    f.total_deaths,
    f.total_vaccinations,
    f.people_fully_vaccinated,
    f.total_cases_per_million,
    f.total_deaths_per_million,
    ROUND(f.case_fatality_rate * 100, 4) AS cfr_pct,
    ROUND(f.vaccination_rate, 2)    AS vaccination_rate_pct,
    f.mortality_rate_per_million,
    f.rolling_7day_cases,
    f.rolling_7day_deaths
FROM fact_covid_daily f
JOIN dim_country c USING (iso_code)
ORDER BY f.iso_code, f.date DESC;

COMMENT ON VIEW v_country_latest IS
    'Most recent record for every country. Use this view for any "current state" analysis.';


-- =============================================================================
-- VIEW 4: v_india_timeline
-- Full daily time-series for India with wave annotations
-- Use: India daily trend chart, Wave annotation, Vaccination progress
-- =============================================================================

CREATE OR REPLACE VIEW v_india_timeline AS
SELECT
    f.date,
    f.new_cases,
    f.new_deaths,
    f.new_cases_smoothed,
    f.new_deaths_smoothed,
    f.total_cases,
    f.total_deaths,
    f.total_vaccinations,
    f.people_vaccinated,
    f.people_fully_vaccinated,
    f.new_vaccinations,
    ROUND(f.vaccination_rate, 4)        AS vaccination_rate_pct,
    ROUND(f.case_fatality_rate * 100, 4) AS cfr_pct,
    f.rolling_7day_cases,
    f.rolling_7day_deaths,
    f.rolling_14day_cases,
    f.wave_number,
    f.stringency_index,
    f.reproduction_rate,
    d.month_name,
    d.quarter,
    f.year,
    f.month
FROM fact_covid_daily f
JOIN dim_date d ON f.date = d.date_key
WHERE f.iso_code = 'IND'
ORDER BY f.date;

COMMENT ON VIEW v_india_timeline IS
    'Complete India daily time-series including wave numbers. Ideal for annotated charts.';


-- =============================================================================
-- VIEW 5: v_monthly_cases_by_continent
-- Monthly new cases broken down by continent for stacked charts
-- Use: Stacked area chart, Monthly heatmap by continent
-- =============================================================================

CREATE OR REPLACE VIEW v_monthly_cases_by_continent AS
SELECT
    f.year,
    f.month,
    TO_CHAR(DATE_TRUNC('month', MIN(f.date)), 'Mon YYYY') AS month_label,
    c.continent,
    SUM(f.new_cases)                                       AS monthly_new_cases,
    SUM(f.new_deaths)                                      AS monthly_new_deaths,
    ROUND(AVG(f.rolling_7day_cases), 0)                   AS avg_7day_cases
FROM fact_covid_daily f
JOIN dim_country c USING (iso_code)
WHERE c.continent IS NOT NULL
  AND f.new_cases IS NOT NULL
GROUP BY f.year, f.month, c.continent
ORDER BY f.year, f.month, c.continent;

COMMENT ON VIEW v_monthly_cases_by_continent IS
    'Monthly case and death totals grouped by continent. Use for stacked area/bar charts.';


-- =============================================================================
-- VIEW 6: v_vaccination_progress
-- Vaccination rate over time for the top 20 most-vaccinated countries
-- Use: Line chart — vaccination race over time
-- =============================================================================

CREATE OR REPLACE VIEW v_vaccination_progress AS
WITH top20 AS (
    -- Find the 20 countries with the highest final vaccination rate
    SELECT DISTINCT ON (iso_code)
        iso_code
    FROM fact_covid_daily
    WHERE vaccination_rate IS NOT NULL
    ORDER BY iso_code, date DESC, vaccination_rate DESC
    LIMIT 20
)
SELECT
    f.iso_code,
    c.location,
    f.date,
    ROUND(f.vaccination_rate, 4)            AS vaccination_rate_pct,
    f.people_fully_vaccinated,
    f.total_boosters
FROM fact_covid_daily f
JOIN dim_country c USING (iso_code)
WHERE f.iso_code IN (SELECT iso_code FROM top20)
  AND f.vaccination_rate IS NOT NULL
ORDER BY f.iso_code, f.date;

COMMENT ON VIEW v_vaccination_progress IS
    'Vaccination rate over time for top 20 countries. Use for the vaccination race line chart.';


-- =============================================================================
-- VIEW 7: v_high_risk_countries
-- Risk-ranked countries with composite score components
-- Use: Risk table, Bubble plot, High-risk map layer
-- =============================================================================

CREATE OR REPLACE VIEW v_high_risk_countries AS
WITH latest AS (
    SELECT DISTINCT ON (iso_code)
        iso_code,
        total_cases_per_million,
        mortality_rate_per_million,
        vaccination_rate,
        case_fatality_rate
    FROM fact_covid_daily
    ORDER BY iso_code, date DESC
),
normalised AS (
    SELECT
        l.*,
        -- Min-max normalise each component to [0,1]
        (l.total_cases_per_million - MIN(l.total_cases_per_million) OVER())
            / NULLIF(MAX(l.total_cases_per_million) OVER() - MIN(l.total_cases_per_million) OVER(), 0)
            AS score_cases,
        (l.mortality_rate_per_million - MIN(l.mortality_rate_per_million) OVER())
            / NULLIF(MAX(l.mortality_rate_per_million) OVER() - MIN(l.mortality_rate_per_million) OVER(), 0)
            AS score_deaths,
        1 - (l.vaccination_rate - MIN(l.vaccination_rate) OVER())
            / NULLIF(MAX(l.vaccination_rate) OVER() - MIN(l.vaccination_rate) OVER(), 0)
            AS score_unvax      -- invert: low vaccination = high risk
    FROM latest l
    WHERE l.total_cases_per_million  IS NOT NULL
      AND l.mortality_rate_per_million IS NOT NULL
      AND l.vaccination_rate           IS NOT NULL
)
SELECT
    RANK() OVER (ORDER BY (n.score_cases + n.score_deaths + n.score_unvax) / 3 DESC) AS risk_rank,
    c.location,
    c.continent,
    c.population,
    ROUND(n.total_cases_per_million, 0)       AS cases_per_million,
    ROUND(n.mortality_rate_per_million, 2)    AS deaths_per_million,
    ROUND(n.vaccination_rate, 2)              AS vaccination_rate_pct,
    ROUND(n.case_fatality_rate * 100, 4)     AS cfr_pct,
    ROUND((n.score_cases + n.score_deaths + n.score_unvax) / 3, 4) AS composite_risk_score
FROM normalised n
JOIN dim_country c USING (iso_code)
WHERE c.population >= 1_000_000
ORDER BY composite_risk_score DESC;

COMMENT ON VIEW v_high_risk_countries IS
    'Countries ranked by composite risk score (cases + deaths + unvaccinated, each 0-1 normalised).';


-- =============================================================================
-- VIEW 8: v_wave_summary
-- Wave-level summary per country: start/end dates, peak cases, total in wave
-- Use: Wave timeline chart, Heatmap by wave number
-- =============================================================================

CREATE OR REPLACE VIEW v_wave_summary AS
SELECT
    c.location,
    c.continent,
    f.wave_number,
    MIN(f.date)                          AS wave_start,
    MAX(f.date)                          AS wave_end,
    MAX(f.date) - MIN(f.date)           AS wave_duration_days,
    MAX(f.new_cases_smoothed)           AS peak_smoothed_daily_cases,
    SUM(f.new_cases)                    AS total_new_cases_in_wave,
    SUM(f.new_deaths)                   AS total_new_deaths_in_wave,
    ROUND(
        SUM(f.new_deaths)::NUMERIC /
        NULLIF(SUM(f.new_cases), 0) * 100, 4
    )                                   AS wave_cfr_pct
FROM fact_covid_daily f
JOIN dim_country c USING (iso_code)
WHERE f.wave_number IS NOT NULL
  AND f.wave_number > 0
  AND c.population >= 1_000_000
GROUP BY c.location, c.continent, f.wave_number
ORDER BY c.location, f.wave_number;

COMMENT ON VIEW v_wave_summary IS
    'Wave-level summaries per country showing start/end dates, peak, and CFR per wave.';
