# Power BI Dashboard Setup Guide

## Overview
This guide walks you through building a professional COVID-19 analytics dashboard in Power BI Desktop using the processed data from this project.

---

## Step 1: Connect to Data

### Option A: Connect to PostgreSQL (Recommended)
1. Open Power BI Desktop → **Get Data** → **Database** → **PostgreSQL database**
2. Enter credentials:
   - Server: `localhost:5432`
   - Database: `covid19_analysis`
3. Select tables: `covid_data`, `country_summary`
4. Click **Load** (or **Transform Data** to preview first)

### Option B: Connect to CSV Files
1. Open Power BI Desktop → **Get Data** → **Text/CSV**
2. Navigate to `data/processed/`
3. Import `covid_cleaned.csv`
4. Import `country_summary.csv`
5. In **Model View**, create a relationship:
   - `covid_cleaned[iso_code]` → `country_summary[iso_code]` (Many-to-One)

---

## Step 2: Data Transformations (Power Query)

Open **Transform Data** (Power Query Editor):

### Date Table
```powerquery
// Create a dedicated Date table for time intelligence
DateTable = ADDCOLUMNS(
    CALENDAR(DATE(2020,1,1), DATE(2024,12,31)),
    "Year", YEAR([Date]),
    "Month", MONTH([Date]),
    "MonthName", FORMAT([Date], "MMM"),
    "Quarter", QUARTER([Date]),
    "WeekNum", WEEKNUM([Date]),
    "DayOfWeek", WEEKDAY([Date]),
    "YearMonth", FORMAT([Date], "YYYY-MM")
)
```

### Data Type Corrections
- Ensure `date` column is **Date** type
- Set `total_cases`, `total_deaths`, `new_cases`, `new_deaths` as **Whole Number**
- Set `case_fatality_rate`, `vaccination_rate` as **Decimal Number**
- Set `population` as **Whole Number**

---

## Step 3: Create DAX Measures

### KPI Measures
```dax
// Total Global Cases
Total Cases = SUM(covid_data[total_cases])

// Total Global Deaths  
Total Deaths = SUM(covid_data[total_deaths])

// Total Vaccinations
Total Vaccinations = SUM(covid_data[total_vaccinations])

// Case Fatality Rate (%)
CFR = 
DIVIDE(
    SUM(covid_data[total_deaths]),
    SUM(covid_data[total_cases]),
    0
) * 100

// Vaccination Rate (%)
Vaccination Rate = 
DIVIDE(
    SUM(covid_data[people_fully_vaccinated]),
    SUM(covid_data[population]),
    0
) * 100

// Recovery Rate Proxy (%)
Recovery Rate = 
(1 - DIVIDE(
    SUM(covid_data[total_deaths]),
    SUM(covid_data[total_cases]),
    0
)) * 100
```

### Rolling Averages
```dax
// 7-Day Moving Average - New Cases
7D Avg Cases = 
AVERAGEX(
    DATESINPERIOD(
        DateTable[Date],
        MAX(DateTable[Date]),
        -7,
        DAY
    ),
    CALCULATE(SUM(covid_data[new_cases]))
)

// 7-Day Moving Average - New Deaths
7D Avg Deaths = 
AVERAGEX(
    DATESINPERIOD(
        DateTable[Date],
        MAX(DateTable[Date]),
        -7,
        DAY
    ),
    CALCULATE(SUM(covid_data[new_deaths]))
)
```

### Comparison Measures
```dax
// India Cases
India Cases = 
CALCULATE(
    SUM(covid_data[total_cases]),
    covid_data[location] = "India"
)

// India vs World Index
India vs World = 
DIVIDE(
    [India Cases],
    [Total Cases],
    0
) * 100

// Month-over-Month Growth
MoM Growth = 
VAR CurrentMonth = SUM(covid_data[new_cases])
VAR PreviousMonth = CALCULATE(
    SUM(covid_data[new_cases]),
    DATEADD(DateTable[Date], -1, MONTH)
)
RETURN DIVIDE(CurrentMonth - PreviousMonth, PreviousMonth, 0) * 100
```

### Ranking Measures
```dax
// Country Rank by Cases
Country Rank = 
RANKX(
    ALL(covid_data[location]),
    CALCULATE(MAX(covid_data[total_cases])),
    ,
    DESC,
    DENSE
)

// Continent Rank
Continent Rank = 
RANKX(
    ALL(covid_data[continent]),
    CALCULATE(SUM(covid_data[total_cases])),
    ,
    DESC,
    DENSE
)
```

---

## Step 4: Build Report Pages

### Page 1: Global Overview

#### Layout (1920 x 1080)
```
┌─────────────────────────────────────────────────────────┐
│  HEADER: 🦠 COVID-19 Global Analytics Dashboard        │
├─────────┬──────────┬──────────┬──────────┬──────────────┤
│ 📊 Total│ 💀 Total │ 💉 Total │ 📈 CFR   │ 🔄 Recovery │
│ Cases   │ Deaths   │ Vacc'd   │          │ Rate        │
├─────────┴──────────┴──────────┴──────────┴──────────────┤
│  ┌─────────────────────┐  ┌──────────────────────────┐  │
│  │ Map Visual          │  │ Donut Chart:             │  │
│  │ (Filled Map)        │  │ Cases by Continent       │  │
│  │ Color: Cases/M      │  │                          │  │
│  └─────────────────────┘  └──────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  Line & Clustered Column: Daily Cases + 7D MA          │
├─────────────────────────────────────────────────────────┤
│  Horizontal Bar: Top 10 Countries by Total Cases       │
└─────────────────────────────────────────────────────────┘
```

#### Visual Types:
1. **KPI Cards** (5): Use Card visual with conditional formatting
   - Total Cases: Blue (#3b82f6)
   - Total Deaths: Red (#ef4444)
   - Total Vaccinated: Green (#10b981)
   - CFR: Orange (#f59e0b)
   - Recovery Rate: Purple (#7b2ff7)

2. **Filled Map**: 
   - Location: `location`
   - Color saturation: `total_cases_per_million`
   - Tooltip: Location, Cases, Deaths, Vaccination Rate

3. **Donut Chart**:
   - Legend: `continent`
   - Values: `SUM(total_cases)`
   - Colors: Custom palette

4. **Line & Clustered Column**:
   - Axis: `date`
   - Column: `SUM(new_cases)` (light blue)
   - Line: `[7D Avg Cases]` (dark blue)

5. **Bar Chart (Horizontal)**:
   - Axis: `location` (Top 10 filter)
   - Values: `MAX(total_cases)`
   - Color: By `continent`

### Page 2: India Deep Dive

#### Layout
```
┌─────────────────────────────────────────────────────────┐
│  HEADER: 🇮🇳 India COVID-19 Deep Dive                  │
├─────────┬──────────┬──────────┬──────────┬──────────────┤
│ India   │ India    │ India    │ India    │ India vs     │
│ Cases   │ Deaths   │ Vacc'd   │ CFR      │ World %     │
├─────────┴──────────┴──────────┴──────────┴──────────────┤
│  India Daily Cases + 7-Day Moving Average               │
│  (Line & Column Chart with wave annotations)            │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐  ┌──────────────────────────┐  │
│  │ Vaccination Progress│  │ Monthly Cases Heatmap    │  │
│  │ (Area Chart)        │  │ (Matrix with conditional │  │
│  │                     │  │  formatting)             │  │
│  └─────────────────────┘  └──────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  India vs Top 10 Countries Comparison (Clustered Bar)   │
└─────────────────────────────────────────────────────────┘
```

### Page 3: Trends & Analysis

#### Layout
```
┌─────────────────────────────────────────────────────────┐
│  HEADER: 📈 Trends & Risk Analysis                     │
├─────────────────────────────────────────────────────────┤
│  Scatter: Vaccination Rate vs CFR (bubble = population) │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐  ┌──────────────────────────┐  │
│  │ Matrix: Monthly     │  │ Table: High-Risk         │  │
│  │ Growth Rate Heatmap │  │ Countries (sorted by     │  │
│  │ (conditional format)│  │ risk score)              │  │
│  └─────────────────────┘  └──────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  Line: Top 5 Countries Daily Cases Comparison           │
└─────────────────────────────────────────────────────────┘
```

---

## Step 5: Formatting & Theme

### Custom Theme JSON
Save this as `covid_dashboard_theme.json` and import via **View → Themes → Browse for themes**:

```json
{
  "name": "COVID19_Analytics_Dark",
  "dataColors": ["#00d2ff", "#7b2ff7", "#10b981", "#f59e0b", "#ef4444", "#3b82f6", "#ec4899", "#8b5cf6"],
  "background": "#0a0a1a",
  "foreground": "#ffffff",
  "tableAccent": "#00d2ff",
  "textClasses": {
    "callout": {
      "fontSize": 28,
      "fontFace": "Segoe UI Semibold",
      "color": "#ffffff"
    },
    "title": {
      "fontSize": 16,
      "fontFace": "Segoe UI Semibold",
      "color": "#e0e0e0"
    },
    "header": {
      "fontSize": 12,
      "fontFace": "Segoe UI",
      "color": "#a0a0a0"
    },
    "label": {
      "fontSize": 10,
      "fontFace": "Segoe UI",
      "color": "#808080"
    }
  },
  "visualStyles": {
    "*": {
      "*": {
        "background": [{"color": {"solid": {"color": "#1a1a2e"}}}],
        "border": [{"color": {"solid": {"color": "#2a2a4a"}}}],
        "outlineColor": [{"color": {"solid": {"color": "#2a2a4a"}}}]
      }
    }
  }
}
```

### Formatting Guidelines:
1. **Page Background**: `#0a0a1a` (very dark navy)
2. **Visual Background**: `#1a1a2e` (dark navy)
3. **Visual Border**: `#2a2a4a` (subtle border), rounded corners
4. **Title Color**: `#ffffff`
5. **Subtitle/Label Color**: `#a0a0a0`
6. **Grid Lines**: `#2a2a4a` (very subtle)
7. **KPI Card Accent**: Use colored left borders matching the metric

---

## Step 6: Add Interactivity

1. **Slicers**:
   - Date Range Slicer (Between type)
   - Continent Dropdown Slicer
   - Country Dropdown Slicer (with search)
   
2. **Cross-Filtering**: 
   - Enable cross-filtering between map and charts
   - Set Bar chart to cross-highlight (not cross-filter)

3. **Drill-Through**:
   - Create a Country Detail page
   - Right-click on any country → Drill through to detail

4. **Bookmarks**:
   - Create bookmarks for "Global View" and "India View"
   - Add bookmark navigator buttons

5. **Tooltips**:
   - Create a Report Page Tooltip showing mini time series
   - Apply to Map and Bar chart visuals

---

## Step 7: Publish & Share

1. **Save as .pbix**: File → Save As → `COVID19_Dashboard.pbix`
2. **Publish to Power BI Service**: Home → Publish → Select workspace
3. **Export as PDF**: File → Export → PDF (for portfolio)
4. **Take Screenshots**: For README and resume

---

## Validation Checklist

- [ ] Total cases in Power BI matches Python output
- [ ] Total cases in Power BI matches Tableau dashboard
- [ ] India metrics match `india_covid.csv` last row values
- [ ] Top 10 countries ranking matches SQL Query 4 results
- [ ] CFR calculated field matches Python-computed `case_fatality_rate`
- [ ] Date range covers Jan 2020 to latest available data
- [ ] All slicers filter correctly across all pages
- [ ] Cross-filtering works between map and charts
- [ ] Custom theme applies consistently
- [ ] KPI cards show correct values with no errors
