# Tableau Dashboard Setup Guide

## Overview
This guide walks you through building a professional COVID-19 analytics dashboard in Tableau Desktop using the processed data from this project.

---

## Step 1: Connect to Data

### Option A: Connect to PostgreSQL (Recommended)
1. Open Tableau Desktop → **Connect** → **PostgreSQL**
2. Enter credentials:
   - Server: `localhost`
   - Port: `5432`
   - Database: `covid19_analysis`
   - Username: `postgres`
   - Password: `postgres`
3. Drag the `covid_data` table to the canvas
4. Also add `country_summary` table and create a relationship on `iso_code`

### Option B: Connect to CSV Files
1. Open Tableau Desktop → **Connect** → **Text file**
2. Navigate to `data/processed/`
3. Import `covid_cleaned.csv` as the primary data source
4. Add `country_summary.csv` as a secondary data source

---

## Step 2: Create Calculated Fields

Create the following calculated fields in Tableau:

### KPI Metrics
```
// Case Fatality Rate (%)
[Total Deaths] / [Total Cases] * 100

// Vaccination Rate (%)
[People Fully Vaccinated] / [Population] * 100

// Recovery Proxy (%)
([Total Cases] - [Total Deaths]) / [Total Cases] * 100

// Weekly Growth Rate (%)
(ZN([New Cases]) - LOOKUP(ZN([New Cases]), -7)) / LOOKUP(ZN([New Cases]), -7) * 100
```

### Rolling Averages (Table Calculations)
```
// 7-Day Moving Average Cases
WINDOW_AVG(SUM([New Cases]), -6, 0)

// 7-Day Moving Average Deaths
WINDOW_AVG(SUM([New Deaths]), -6, 0)

// 14-Day Moving Average Cases
WINDOW_AVG(SUM([New Cases]), -13, 0)
```

### Ranking
```
// Country Rank by Cases
RANK(SUM([Total Cases]))

// Country Rank by Deaths per Million
RANK(AVG([Total Deaths Per Million]))
```

### India Filter
```
// Is India
IF [Location] = "India" THEN "India" ELSE "Rest of World" END
```

---

## Step 3: Build Dashboard Sheets

### Sheet 1: Global Choropleth Map
1. Drag `Location` to the **Detail** mark
2. Double-click the map to generate geography
3. Drag `Total Cases Per Million` to **Color**
4. Color palette: **Red-Gold** (sequential)
5. Add tooltip: Location, Total Cases, Total Deaths, Vaccination Rate
6. Add a **Parameter** to toggle between Cases/Deaths/Vaccinations

### Sheet 2: Global Daily Trend
1. Drag `Date` to Columns (set to Day level)
2. Drag `SUM(New Cases)` to Rows
3. Add `7-Day Moving Average Cases` as a dual axis
4. Format: Bar chart for daily + Line for MA
5. Colors: Light blue bars, dark blue line

### Sheet 3: Continental Breakdown (Stacked Bar)
1. Drag `Date` to Columns (Month level)
2. Drag `SUM(New Cases)` to Rows
3. Drag `Continent` to Color
4. Chart type: Stacked Bar
5. Color palette: **Tableau 10**

### Sheet 4: Top 10 Countries (Bar Chart)
1. Drag `Location` to Rows
2. Drag `SUM(Total Cases)` to Columns
3. Sort descending
4. Add a **Top N filter** (Top 10 by Total Cases)
5. Color by `Continent`
6. Add a **Parameter**: Sort By (Cases / Deaths / Vaccination Rate)

### Sheet 5: India Daily Timeline
1. Filter: `Location = India`
2. Drag `Date` to Columns (Day)
3. Drag `SUM(New Cases)` to Rows (bar)
4. Dual axis with 7-Day MA (line)
5. Add **Reference Lines** for wave peaks (April 2021, Jan 2022)

### Sheet 6: India Vaccination Progress
1. Filter: `Location = India`
2. Drag `Date` to Columns
3. Drag `Total Vaccinations` and `People Fully Vaccinated` to Rows
4. Dual axis, area fill
5. Colors: Green gradient

### Sheet 7: Vaccination vs CFR Scatter
1. Drag `AVG(Vaccination Rate)` to Columns
2. Drag `AVG(Case Fatality Rate)` to Rows
3. Drag `Location` to Detail
4. Drag `Population` to Size
5. Drag `Continent` to Color
6. Add **Trend Line** (linear regression)
7. Highlight India with a reference line or annotation

### Sheet 8: Monthly Heatmap
1. Drag `Month` to Columns, `Year` to Rows
2. Drag `SUM(New Cases)` to Color
3. Mark type: **Square**
4. Filter to India
5. Color palette: **Blue-Teal** sequential

---

## Step 4: Assemble the Dashboard

### Dashboard Layout (1920 x 1080)

```
┌─────────────────────────────────────────────────────────┐
│  HEADER: COVID-19 Global Analytics Dashboard            │
│  KPIs: Total Cases | Total Deaths | Vaccinated | CFR    │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐  ┌──────────────────────────┐  │
│  │ Choropleth Map      │  │ Continental Breakdown    │  │
│  │ (Sheet 1)           │  │ (Sheet 3)                │  │
│  └─────────────────────┘  └──────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  Global Daily Trend (Sheet 2)                           │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐  ┌──────────────────────────┐  │
│  │ Top 10 Countries    │  │ Vaccination vs CFR       │  │
│  │ (Sheet 4)           │  │ Scatter (Sheet 7)        │  │
│  └─────────────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### India Dashboard (Separate Tab)
```
┌─────────────────────────────────────────────────────────┐
│  HEADER: India COVID-19 Deep Dive                       │
│  KPIs: India Cases | Deaths | Vaccinated | CFR          │
├─────────────────────────────────────────────────────────┤
│  India Daily Cases Timeline (Sheet 5)                   │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐  ┌──────────────────────────┐  │
│  │ Vaccination Progress│  │ Monthly Heatmap          │  │
│  │ (Sheet 6)           │  │ (Sheet 8)                │  │
│  └─────────────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Step 5: Add Interactivity

1. **Filters**: Add Date Range filter, Continent filter, Country filter as dashboard actions
2. **Highlight Actions**: Clicking a country on the map highlights it across all sheets
3. **URL Actions**: Link to country-specific data sources (optional)
4. **Parameters**: Metric toggle (Cases/Deaths/Vaccinations)
5. **Tooltips**: Customize with Viz in Tooltip for mini charts

---

## Step 6: Formatting & Polish

1. **Dark Theme**: Dashboard → Format → Workbook Theme → "Dark"
2. **Fonts**: Use Tableau Book or a clean sans-serif
3. **Color Palette**: Create a custom palette matching the project:
   - Cyan: `#00d2ff`
   - Purple: `#7b2ff7`  
   - Emerald: `#10b981`
   - Orange: `#f59e0b`
   - Red: `#ef4444`
4. **Title Formatting**: Bold, larger font, with data last-updated timestamp
5. **Borders**: Minimal, use whitespace for separation
6. **Loading Screen**: Add a cover page with project title

---

## Step 7: Publish (Optional)

1. **Tableau Public**: File → Save to Tableau Public → Share link
2. **Tableau Server**: File → Publish → Select your server
3. **Export**: Dashboard → Export Image for portfolio screenshots

---

## Validation Checklist

- [ ] Total cases in Tableau matches Python output
- [ ] Top 10 countries list matches SQL Query 1 results
- [ ] India total cases matches `india_covid.csv` last row
- [ ] Date range covers full pandemic timeline
- [ ] All calculated fields produce valid results (no nulls in KPIs)
- [ ] Filters work across all sheets in the dashboard
- [ ] Color scheme is consistent across all visualizations
