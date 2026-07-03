-- =============================================================================
-- sql/analysis_queries.sql
-- COVID-19 Portfolio SQL — 17 Advanced Analytical Queries
-- Database: PostgreSQL 14+
-- =============================================================================
-- Demonstrates: Aggregations, CTEs, Window Functions (RANK/LAG/ROW_NUMBER),
--               Rolling windows, Self-joins, Subqueries, CASE expressions
-- =============================================================================
-- CRITICAL RULE:  Never SUM(total_*) across time.
--                 Always use MAX(total_*) or filter to the latest date.
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 1 ▸ Global Totals Snapshot (latest day)
-- Returns one row showing worldwide confirmed cases, deaths, vaccinations, tests
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
    MAX(total_cases)              AS global_total_cases,
    MAX(total_deaths)             AS global_total_deaths,
    MAX(total_vaccinations)       AS global_total_vaccinations,
    MAX(people_fully_vaccinated)  AS global_fully_vaccinated,
    MAX(total_tests)              AS global_total_tests,
    ROUND(
        MAX(total_deaths)::NUMERIC / NULLIF(MAX(total_cases), 0) * 100, 4
    )                             AS global_cfr_pct
FROM (
    -- Sub-select the latest row per country so we don't double-count
    SELECT DISTINCT ON (iso_code)
        iso_code, total_cases, total_deaths,
        total_vaccinations, people_fully_vaccinated, total_tests
    FROM fact_covid_daily
    WHERE iso_code IS NOT NULL
    ORDER BY iso_code, date DESC
) latest;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 2 ▸ Continental Breakdown
-- Latest totals grouped by continent with CFR and vaccination rate
-- ─────────────────────────────────────────────────────────────────────────────

WITH latest_per_country AS (
    -- Get each country's most recent record
    SELECT DISTINCT ON (f.iso_code)
        c.continent,
        c.population,
        f.total_cases,
        f.total_deaths,
        f.people_fully_vaccinated
    FROM fact_covid_daily f
    JOIN dim_country c USING (iso_code)
    WHERE c.continent IS NOT NULL
    ORDER BY f.iso_code, f.date DESC
)
SELECT
    continent,
    COUNT(*)                                          AS country_count,
    SUM(total_cases)                                  AS total_cases,        -- MAX per country, then SUM across countries is valid
    SUM(total_deaths)                                 AS total_deaths,
    SUM(population)                                   AS total_population,
    ROUND(
        SUM(total_deaths)::NUMERIC / NULLIF(SUM(total_cases), 0) * 100, 4
    )                                                 AS cfr_pct,
    ROUND(
        SUM(people_fully_vaccinated)::NUMERIC /
        NULLIF(SUM(population), 0) * 100, 2
    )                                                 AS avg_vaccination_rate_pct
FROM latest_per_country
GROUP BY continent
ORDER BY total_cases DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 3 ▸ Global Monthly Trend
-- Month-by-month sum of new cases and new deaths worldwide
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
    year,
    month,
    TO_CHAR(DATE_TRUNC('month', MIN(date)), 'Mon YYYY') AS month_label,
    SUM(new_cases)                                       AS monthly_new_cases,
    SUM(new_deaths)                                      AS monthly_new_deaths,
    ROUND(AVG(reproduction_rate), 3)                     AS avg_reproduction_rate
FROM fact_covid_daily
WHERE new_cases IS NOT NULL
GROUP BY year, month
ORDER BY year, month;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 4 ▸ Country Rankings — Window Function: RANK & DENSE_RANK
-- Rank every country by total cases per million population
-- ─────────────────────────────────────────────────────────────────────────────

WITH latest AS (
    SELECT DISTINCT ON (iso_code)
        iso_code, total_cases_per_million, total_deaths_per_million,
        vaccination_rate, case_fatality_rate
    FROM fact_covid_daily
    ORDER BY iso_code, date DESC
),
ranked AS (
    SELECT
        c.location,
        c.continent,
        l.total_cases_per_million,
        l.total_deaths_per_million,
        l.vaccination_rate,
        ROUND(l.case_fatality_rate * 100, 4)  AS cfr_pct,
        RANK()       OVER (ORDER BY l.total_cases_per_million DESC NULLS LAST)  AS rank_cases_per_million,
        DENSE_RANK() OVER (ORDER BY l.vaccination_rate          DESC NULLS LAST) AS dense_rank_vaccination
    FROM latest l
    JOIN dim_country c USING (iso_code)
    WHERE l.total_cases_per_million IS NOT NULL
)
SELECT *
FROM ranked
ORDER BY rank_cases_per_million
LIMIT 30;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 5 ▸ Day-over-Day New Case Growth Rate — Window Function: LAG
-- Compute daily change and growth % using the previous day's value
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
    iso_code,
    date,
    new_cases,
    LAG(new_cases) OVER (PARTITION BY iso_code ORDER BY date)   AS prev_day_cases,
    new_cases - LAG(new_cases) OVER (
        PARTITION BY iso_code ORDER BY date
    )                                                           AS daily_change,
    ROUND(
        (new_cases - LAG(new_cases) OVER (PARTITION BY iso_code ORDER BY date))::NUMERIC
        / NULLIF(LAG(new_cases) OVER (PARTITION BY iso_code ORDER BY date), 0) * 100
    , 2)                                                        AS growth_pct
FROM fact_covid_daily
WHERE iso_code IN ('IND', 'USA', 'BRA', 'GBR', 'DEU')
  AND date >= '2021-01-01'
ORDER BY iso_code, date;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 6 ▸ 7-Day Rolling Average — Window Frame: ROWS BETWEEN
-- In-database rolling average (cross-check against Python-computed column)
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
    iso_code,
    date,
    new_cases,
    ROUND(
        AVG(new_cases) OVER (
            PARTITION BY iso_code
            ORDER BY date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        )
    , 2)                     AS rolling_7day_avg_cases,
    rolling_7day_cases       AS python_rolling_7day_cases   -- for validation
FROM fact_covid_daily
WHERE iso_code = 'IND'
ORDER BY date;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 7 ▸ Peak Day per Country — Window Function: ROW_NUMBER
-- Identify the single day with the highest new cases for each country
-- ─────────────────────────────────────────────────────────────────────────────

WITH ranked_days AS (
    SELECT
        iso_code,
        date,
        new_cases,
        new_cases_smoothed,
        ROW_NUMBER() OVER (
            PARTITION BY iso_code
            ORDER BY new_cases_smoothed DESC NULLS LAST
        ) AS rn
    FROM fact_covid_daily
)
SELECT
    c.location,
    c.continent,
    r.date              AS peak_date,
    r.new_cases         AS peak_new_cases,
    r.new_cases_smoothed AS peak_smoothed_cases
FROM ranked_days r
JOIN dim_country c USING (iso_code)
WHERE r.rn = 1
  AND c.population >= 1_000_000       -- exclude micro-states
ORDER BY r.new_cases DESC
LIMIT 20;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 8 ▸ Top 10 Countries by CFR — Multi-step CTE
-- Filters to countries with population > 1M and > 10k cases
-- ─────────────────────────────────────────────────────────────────────────────

WITH
-- Step 1: Get latest snapshot per country
latest AS (
    SELECT DISTINCT ON (iso_code)
        iso_code, total_cases, total_deaths, case_fatality_rate, vaccination_rate
    FROM fact_covid_daily
    ORDER BY iso_code, date DESC
),
-- Step 2: Join with demographic dimension to apply population filter
with_demo AS (
    SELECT
        c.location, c.continent, c.population,
        l.total_cases, l.total_deaths,
        ROUND(l.case_fatality_rate * 100, 4) AS cfr_pct,
        ROUND(l.vaccination_rate, 2)          AS vaccination_rate_pct
    FROM latest l
    JOIN dim_country c USING (iso_code)
    WHERE c.population >= 1_000_000
      AND l.total_cases >= 10_000
),
-- Step 3: Rank by CFR and pick top 10
ranked AS (
    SELECT *, RANK() OVER (ORDER BY cfr_pct DESC) AS cfr_rank
    FROM with_demo
    WHERE cfr_pct IS NOT NULL
)
SELECT *
FROM ranked
WHERE cfr_rank <= 10
ORDER BY cfr_rank;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 9 ▸ Vaccination Milestone Dates — CTE
-- For each country, find the date they crossed 25%, 50%, 75% vaccination
-- ─────────────────────────────────────────────────────────────────────────────

WITH milestones AS (
    SELECT
        f.iso_code,
        c.location,
        MIN(CASE WHEN f.vaccination_rate >= 25 THEN f.date END) AS date_25pct,
        MIN(CASE WHEN f.vaccination_rate >= 50 THEN f.date END) AS date_50pct,
        MIN(CASE WHEN f.vaccination_rate >= 75 THEN f.date END) AS date_75pct,
        MAX(f.vaccination_rate)                                  AS max_vaccination_rate
    FROM fact_covid_daily f
    JOIN dim_country c USING (iso_code)
    WHERE f.vaccination_rate IS NOT NULL
    GROUP BY f.iso_code, c.location
)
SELECT
    location,
    ROUND(max_vaccination_rate, 2) AS max_vax_rate_pct,
    date_25pct,
    date_50pct,
    date_75pct,
    -- Days between milestones
    date_50pct - date_25pct  AS days_25_to_50,
    date_75pct - date_50pct  AS days_50_to_75
FROM milestones
WHERE date_25pct IS NOT NULL
ORDER BY date_50pct NULLS LAST;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 10 ▸ Top 3 Countries per Continent by Vaccination Rate — CTE + RANK
-- ─────────────────────────────────────────────────────────────────────────────

WITH
latest AS (
    SELECT DISTINCT ON (iso_code)
        iso_code, vaccination_rate
    FROM fact_covid_daily
    WHERE vaccination_rate IS NOT NULL
    ORDER BY iso_code, date DESC
),
ranked AS (
    SELECT
        c.continent,
        c.location,
        ROUND(l.vaccination_rate, 2) AS vaccination_rate_pct,
        RANK() OVER (
            PARTITION BY c.continent
            ORDER BY l.vaccination_rate DESC
        ) AS continent_rank
    FROM latest l
    JOIN dim_country c USING (iso_code)
    WHERE c.continent IS NOT NULL
      AND c.population >= 500_000     -- exclude very small territories
)
SELECT *
FROM ranked
WHERE continent_rank <= 3
ORDER BY continent, continent_rank;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 11 ▸ India Monthly Progression
-- Month-by-month: new cases, deaths, vaccinations, CFR for India only
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
    year,
    month,
    TO_CHAR(DATE_TRUNC('month', MIN(date)), 'Mon YYYY') AS period,
    SUM(new_cases)                                       AS monthly_cases,
    SUM(new_deaths)                                      AS monthly_deaths,
    MAX(total_vaccinations)                              AS cumulative_vaccinations_eom, -- end of month
    MAX(people_fully_vaccinated)                         AS fully_vaccinated_eom,
    ROUND(AVG(rolling_7day_cases), 0)                    AS avg_daily_cases_7d,
    ROUND(MAX(case_fatality_rate) * 100, 4)              AS cfr_pct_eom
FROM fact_covid_daily
WHERE iso_code = 'IND'
GROUP BY year, month
ORDER BY year, month;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 12 ▸ India vs Global Average — Key Metric Comparison
-- ─────────────────────────────────────────────────────────────────────────────

WITH india_latest AS (
    SELECT DISTINCT ON (iso_code)
        vaccination_rate, case_fatality_rate,
        total_cases_per_million, total_deaths_per_million
    FROM fact_covid_daily
    WHERE iso_code = 'IND'
    ORDER BY iso_code, date DESC
),
world_avg AS (
    SELECT
        AVG(vaccination_rate)          AS avg_vaccination_rate,
        AVG(case_fatality_rate)        AS avg_cfr,
        AVG(total_cases_per_million)   AS avg_cases_per_million,
        AVG(total_deaths_per_million)  AS avg_deaths_per_million
    FROM (
        SELECT DISTINCT ON (iso_code)
            vaccination_rate, case_fatality_rate,
            total_cases_per_million, total_deaths_per_million
        FROM fact_covid_daily
        ORDER BY iso_code, date DESC
    ) l
)
SELECT
    'India'                                                         AS entity,
    ROUND(i.vaccination_rate, 2)                                    AS vaccination_rate_pct,
    ROUND(i.case_fatality_rate * 100, 4)                           AS cfr_pct,
    ROUND(i.total_cases_per_million, 0)                             AS cases_per_million,
    ROUND(i.total_deaths_per_million, 2)                            AS deaths_per_million
FROM india_latest i

UNION ALL

SELECT
    'World Average'                             AS entity,
    ROUND(w.avg_vaccination_rate, 2)            AS vaccination_rate_pct,
    ROUND(w.avg_cfr * 100, 4)                  AS cfr_pct,
    ROUND(w.avg_cases_per_million, 0)           AS cases_per_million,
    ROUND(w.avg_deaths_per_million, 2)          AS deaths_per_million
FROM world_avg w;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 13 ▸ India Pandemic Waves — Peak Periods
-- Using window LAG to identify rising/falling phases
-- ─────────────────────────────────────────────────────────────────────────────

WITH india AS (
    SELECT
        date,
        new_cases_smoothed,
        LAG(new_cases_smoothed, 7) OVER (ORDER BY date)  AS cases_7d_ago,
        wave_number
    FROM fact_covid_daily
    WHERE iso_code = 'IND'
      AND new_cases_smoothed IS NOT NULL
)
SELECT
    wave_number,
    MIN(date)                                     AS wave_start,
    MAX(date)                                     AS wave_end,
    MAX(date) - MIN(date)                         AS wave_duration_days,
    MAX(new_cases_smoothed)                       AS peak_smoothed_cases,
    SUM(new_cases_smoothed)::BIGINT               AS total_smoothed_cases_in_wave
FROM india
WHERE wave_number IS NOT NULL
GROUP BY wave_number
ORDER BY wave_number;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 14 ▸ Vaccination Rate vs Death Rate Correlation Proxy
-- Countries with both metrics available, sorted by vaccination_rate
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
    c.location,
    c.continent,
    ROUND(l.vaccination_rate, 2)             AS vaccination_rate_pct,
    ROUND(l.case_fatality_rate * 100, 4)    AS cfr_pct,
    ROUND(l.total_deaths_per_million, 2)    AS deaths_per_million,
    c.median_age,
    c.gdp_per_capita,
    -- Classify countries into vaccination tiers for easier BI filtering
    CASE
        WHEN l.vaccination_rate >= 70 THEN 'High (≥70%)'
        WHEN l.vaccination_rate >= 40 THEN 'Medium (40–70%)'
        WHEN l.vaccination_rate >= 10 THEN 'Low (10–40%)'
        ELSE 'Very Low (<10%)'
    END AS vaccination_tier
FROM (
    SELECT DISTINCT ON (iso_code)
        iso_code, vaccination_rate, case_fatality_rate,
        total_deaths_per_million
    FROM fact_covid_daily
    ORDER BY iso_code, date DESC
) l
JOIN dim_country c USING (iso_code)
WHERE l.vaccination_rate IS NOT NULL
  AND l.case_fatality_rate IS NOT NULL
  AND c.population >= 1_000_000
ORDER BY l.vaccination_rate DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 15 ▸ High-Risk Countries
-- Countries with above-average deaths per million AND below-average vaccination
-- ─────────────────────────────────────────────────────────────────────────────

WITH latest AS (
    SELECT DISTINCT ON (iso_code)
        iso_code, mortality_rate_per_million, vaccination_rate, case_fatality_rate
    FROM fact_covid_daily
    ORDER BY iso_code, date DESC
),
thresholds AS (
    SELECT
        AVG(mortality_rate_per_million) AS avg_mortality,
        AVG(vaccination_rate)           AS avg_vaccination
    FROM latest
    WHERE mortality_rate_per_million IS NOT NULL
      AND vaccination_rate IS NOT NULL
)
SELECT
    c.location,
    c.continent,
    ROUND(l.mortality_rate_per_million, 2)   AS deaths_per_million,
    ROUND(l.vaccination_rate, 2)             AS vaccination_rate_pct,
    ROUND(l.case_fatality_rate * 100, 4)    AS cfr_pct,
    t.avg_mortality,
    t.avg_vaccination
FROM latest l
JOIN dim_country c USING (iso_code)
CROSS JOIN thresholds t
WHERE l.mortality_rate_per_million > t.avg_mortality
  AND l.vaccination_rate           < t.avg_vaccination
  AND c.population >= 1_000_000
ORDER BY l.mortality_rate_per_million DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 16 ▸ Pandemic Timeline — First Case, Peak, Current Status
-- Summary for top 20 most-affected countries
-- ─────────────────────────────────────────────────────────────────────────────

WITH
first_case AS (
    SELECT iso_code, MIN(date) AS first_case_date
    FROM fact_covid_daily
    WHERE new_cases > 0
    GROUP BY iso_code
),
peak_day AS (
    SELECT DISTINCT ON (iso_code)
        iso_code, date AS peak_date, new_cases_smoothed AS peak_cases
    FROM fact_covid_daily
    WHERE new_cases_smoothed IS NOT NULL
    ORDER BY iso_code, new_cases_smoothed DESC
),
current AS (
    SELECT DISTINCT ON (iso_code)
        iso_code, date AS latest_date,
        total_cases, total_deaths, vaccination_rate
    FROM fact_covid_daily
    ORDER BY iso_code, date DESC
)
SELECT
    c.location,
    c.continent,
    f.first_case_date,
    p.peak_date,
    ROUND(p.peak_cases, 0)             AS peak_daily_cases_smoothed,
    cur.latest_date,
    cur.total_cases,
    cur.total_deaths,
    ROUND(cur.vaccination_rate, 2)     AS vaccination_rate_pct
FROM current cur
JOIN dim_country c USING (iso_code)
JOIN first_case  f USING (iso_code)
JOIN peak_day    p USING (iso_code)
ORDER BY cur.total_cases DESC
LIMIT 20;


-- ─────────────────────────────────────────────────────────────────────────────
-- QUERY 17 ▸ Testing Efficiency — Positivity Rate vs Test Volume
-- Countries with highest positivity rates and their testing coverage
-- ─────────────────────────────────────────────────────────────────────────────

WITH latest AS (
    SELECT DISTINCT ON (iso_code)
        iso_code, positive_rate, tests_per_case, total_tests,
        total_cases_per_million
    FROM fact_covid_daily
    WHERE positive_rate IS NOT NULL
      AND tests_per_case IS NOT NULL
    ORDER BY iso_code, date DESC
)
SELECT
    c.location,
    c.continent,
    ROUND(l.positive_rate * 100, 2)           AS positivity_rate_pct,
    ROUND(l.tests_per_case, 1)                AS tests_per_confirmed_case,
    l.total_tests                             AS cumulative_tests,
    ROUND(l.total_cases_per_million, 0)       AS cases_per_million,
    -- WHO guideline: positivity < 5% for 14 days signals adequate testing
    CASE
        WHEN l.positive_rate < 0.05 THEN '✔ Adequate (<5%)'
        WHEN l.positive_rate < 0.10 THEN '⚠ Moderate (5–10%)'
        ELSE '✗ Under-tested (>10%)'
    END AS testing_adequacy
FROM latest l
JOIN dim_country c USING (iso_code)
WHERE c.population >= 1_000_000
ORDER BY l.positive_rate DESC
LIMIT 20;
