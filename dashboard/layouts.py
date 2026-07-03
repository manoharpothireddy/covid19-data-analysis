"""
COVID-19 Global Analytics Dashboard — Layouts
==============================================
All page layouts: Header, Global Overview, India Deep Dive,
Trends & Analysis, SQL Insights.
"""

import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table


# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
CYAN = "#00d2ff"
PURPLE = "#7b2ff7"
EMERALD = "#10b981"
ORANGE = "#f59e0b"
RED = "#ef4444"
BLUE = "#3b82f6"
BG_CARD = "rgba(255,255,255,0.03)"
TRANSPARENT = "rgba(0,0,0,0)"


# ═══════════════════════════════════════════════════════════════════════════
#  HEADER  (common across all pages)
# ═══════════════════════════════════════════════════════════════════════════
def _header():
    return html.Div(
        className="dashboard-header",
        children=[
            html.H1("🦠 COVID-19 Global Analytics", className="gradient-text"),
            html.P(
                "Real-time pandemic insights · India focus · Global comparison",
                className="header-subtitle",
            ),
            html.Span(id="last-updated-badge", className="last-updated"),
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════
#  GLOBAL KPI ROW
# ═══════════════════════════════════════════════════════════════════════════
def _kpi_row():
    kpis = [
        ("total-cases-kpi", "Total Cases", "cyan"),
        ("total-deaths-kpi", "Total Deaths", "red"),
        ("total-vaccinated-kpi", "Total Vaccinated", "emerald"),
        ("global-cfr-kpi", "Global CFR", "orange"),
    ]
    cols = []
    for kid, label, color in kpis:
        cols.append(
            dbc.Col(
                html.Div(
                    className=f"kpi-card kpi-{color}",
                    children=[
                        html.Div(label, className="kpi-label"),
                        html.Div(id=kid, className=f"kpi-value {color}", children="—"),
                    ],
                ),
                xs=6, sm=6, md=3, lg=3,
            )
        )
    return dbc.Row(cols, className="g-3 row-gap")


# ═══════════════════════════════════════════════════════════════════════════
#  TAB  WRAPPERS
# ═══════════════════════════════════════════════════════════════════════════

# ----- Page 1 : Global Overview ------------------------------------------
def _page_global():
    return html.Div([
        # -- Filters --
        html.Div(className="filter-bar", children=[
            dbc.Row([
                dbc.Col([
                    html.Div("Date Range", className="filter-label"),
                    dcc.DatePickerRange(
                        id="global-date-range",
                        display_format="MMM D, YYYY",
                        style={"width": "100%"},
                    ),
                ], md=4),
                dbc.Col([
                    html.Div("Continent", className="filter-label"),
                    dcc.Dropdown(
                        id="continent-filter",
                        options=[],
                        placeholder="All Continents",
                        multi=False,
                        clearable=True,
                        style={"background": "transparent"},
                    ),
                ], md=3),
                dbc.Col([
                    html.Div("Map Metric", className="filter-label"),
                    dcc.Dropdown(
                        id="map-metric",
                        options=[
                            {"label": "Total Cases", "value": "total_cases"},
                            {"label": "Total Deaths", "value": "total_deaths"},
                            {"label": "Vaccination Rate", "value": "vaccination_rate"},
                            {"label": "Case Fatality Rate", "value": "case_fatality_rate"},
                        ],
                        value="total_cases",
                        clearable=False,
                        style={"background": "transparent"},
                    ),
                ], md=3),
                dbc.Col([
                    html.Div("Top N Countries", className="filter-label"),
                    dcc.Slider(
                        id="top-n-slider",
                        min=5, max=20, step=5, value=10,
                        marks={i: str(i) for i in range(5, 25, 5)},
                        tooltip={"placement": "bottom"},
                    ),
                ], md=2),
            ], className="g-3 align-items-end"),
        ]),

        # -- Row 1 : Choropleth --
        html.Div(className="chart-container", children=[
            html.Div("🌍 Global Choropleth Map", className="chart-title"),
            dcc.Loading(
                dcc.Graph(id="choropleth-map", style={"height": "520px"},
                          config={"displayModeBar": True, "scrollZoom": True}),
                type="dot", color=CYAN,
            ),
        ]),

        # -- Row 2 : Daily trend --
        html.Div(className="chart-container", children=[
            html.Div("📈 Global Daily Trend (7-Day Moving Average)", className="chart-title"),
            dcc.Loading(
                dcc.Graph(id="global-trend-chart", style={"height": "400px"},
                          config={"displayModeBar": True}),
                type="dot", color=CYAN,
            ),
        ]),

        # -- Row 3 : Continental breakdown --
        dbc.Row([
            dbc.Col(
                html.Div(className="chart-container", children=[
                    html.Div("🌐 Cases by Continent (Stacked)", className="chart-title"),
                    dcc.Loading(
                        dcc.Graph(id="continent-bar-chart", style={"height": "400px"},
                                  config={"displayModeBar": False}),
                        type="dot", color=PURPLE,
                    ),
                ]),
                md=7,
            ),
            dbc.Col(
                html.Div(className="chart-container", children=[
                    html.Div("🍩 Continental Share", className="chart-title"),
                    dcc.Loading(
                        dcc.Graph(id="continent-pie-chart", style={"height": "400px"},
                                  config={"displayModeBar": False}),
                        type="dot", color=PURPLE,
                    ),
                ]),
                md=5,
            ),
        ], className="g-3 row-gap"),

        # -- Row 4 : Top countries --
        html.Div(className="chart-container", children=[
            html.Div("🏆 Top Countries", className="chart-title"),
            dcc.Loading(
                dcc.Graph(id="top-countries-chart", style={"height": "420px"},
                          config={"displayModeBar": False}),
                type="dot", color=EMERALD,
            ),
        ]),
    ])


# ----- Page 2 : India Deep Dive ------------------------------------------
def _page_india():
    india_kpis = [
        ("india-cases-kpi", "Total Cases", "cyan"),
        ("india-deaths-kpi", "Total Deaths", "red"),
        ("india-vaccinated-kpi", "Vaccinated", "emerald"),
        ("india-cfr-kpi", "CFR", "orange"),
        ("india-recovery-kpi", "Recovery Rate", "blue"),
    ]
    kpi_cols = [
        dbc.Col(
            html.Div(className=f"kpi-card kpi-{c}", children=[
                html.Div(l, className="kpi-label"),
                html.Div(id=kid, className=f"kpi-value {c}", children="—"),
            ]),
            xs=6, sm=4, md=True,
        )
        for kid, l, c in india_kpis
    ]

    return html.Div([
        # Filters
        html.Div(className="filter-bar", children=[
            dbc.Row([
                dbc.Col([
                    html.Div("India Date Range", className="filter-label"),
                    dcc.DatePickerRange(
                        id="india-date-range",
                        display_format="MMM D, YYYY",
                    ),
                ], md=5),
            ]),
        ]),

        # KPIs
        dbc.Row(kpi_cols, className="g-3 row-gap"),

        # Row 2: Daily cases timeline with wave annotations
        html.Div(className="chart-container", children=[
            html.Div("🇮🇳 India Daily Cases Timeline with Wave Annotations", className="chart-title"),
            dcc.Loading(
                dcc.Graph(id="india-timeline-chart", style={"height": "420px"},
                          config={"displayModeBar": True}),
                type="dot", color=CYAN,
            ),
        ]),

        # Row 3: Vaccination progress
        html.Div(className="chart-container", children=[
            html.Div("💉 India Vaccination Progress", className="chart-title"),
            dcc.Loading(
                dcc.Graph(id="india-vaccination-chart", style={"height": "400px"},
                          config={"displayModeBar": True}),
                type="dot", color=EMERALD,
            ),
        ]),

        # Row 4: India vs World Radar
        html.Div(className="chart-container", children=[
            html.Div("🕸️ India vs World — Key Metrics Comparison", className="chart-title"),
            dcc.Loading(
                dcc.Graph(id="india-radar-chart", style={"height": "480px"},
                          config={"displayModeBar": False}),
                type="dot", color=PURPLE,
            ),
        ]),

        # Row 5: Monthly Heatmap
        html.Div(className="chart-container", children=[
            html.Div("🗓️ India Monthly Case Intensity Heatmap", className="chart-title"),
            dcc.Loading(
                dcc.Graph(id="india-heatmap-chart", style={"height": "360px"},
                          config={"displayModeBar": False}),
                type="dot", color=ORANGE,
            ),
        ]),
    ])


# ----- Page 3 : Trends & Analysis ----------------------------------------
def _page_trends():
    return html.Div([
        # Filters
        html.Div(className="filter-bar", children=[
            dbc.Row([
                dbc.Col([
                    html.Div("Countries", className="filter-label"),
                    dcc.Dropdown(
                        id="trends-country-filter",
                        options=[],
                        multi=True,
                        placeholder="Select countries…",
                        style={"background": "transparent"},
                    ),
                ], md=6),
                dbc.Col([
                    html.Div("Date Range", className="filter-label"),
                    dcc.DatePickerRange(
                        id="trends-date-range",
                        display_format="MMM D, YYYY",
                    ),
                ], md=6),
            ], className="g-3"),
        ]),

        # Row 1: Wave-highlighted time series
        html.Div(className="chart-container", children=[
            html.Div("🌊 Pandemic Waves — Global New Cases with Wave Bands", className="chart-title"),
            dcc.Loading(
                dcc.Graph(id="wave-timeline-chart", style={"height": "420px"},
                          config={"displayModeBar": True}),
                type="dot", color=CYAN,
            ),
        ]),

        # Row 2: Growth rate heatmap
        html.Div(className="chart-container", children=[
            html.Div("🔥 Weekly Growth Rate Heatmap (Countries × Months)", className="chart-title"),
            dcc.Loading(
                dcc.Graph(id="growth-heatmap-chart", style={"height": "480px"},
                          config={"displayModeBar": False}),
                type="dot", color=ORANGE,
            ),
        ]),

        # Row 3: Scatter
        html.Div(className="chart-container", children=[
            html.Div("💊 Vaccination Rate vs Case Fatality Rate", className="chart-title"),
            dcc.Loading(
                dcc.Graph(id="vaccination-scatter-chart", style={"height": "460px"},
                          config={"displayModeBar": True}),
                type="dot", color=EMERALD,
            ),
        ]),

        # Row 4: High-risk table
        html.Div(className="chart-container", children=[
            html.Div("⚠️ Top 15 High-Risk Countries", className="chart-title"),
            dcc.Loading(
                html.Div(id="risk-table-container"),
                type="dot", color=RED,
            ),
        ]),
    ])


# ----- Page 4 : SQL Insights ---------------------------------------------
def _page_sql():
    return html.Div([
        html.Div(className="filter-bar", children=[
            dbc.Row([
                dbc.Col([
                    html.Div("SQL Query", className="filter-label"),
                    dcc.Dropdown(
                        id="sql-query-selector",
                        options=[
                            {"label": "📊 Top 10 Countries by Total Cases", "value": "top_cases"},
                            {"label": "💀 Highest CFR Countries", "value": "high_cfr"},
                            {"label": "💉 Vaccination Leaders", "value": "vacc_leaders"},
                            {"label": "📈 Monthly Global Trend", "value": "monthly_trend"},
                            {"label": "🌍 Continental Summary", "value": "continent_summary"},
                        ],
                        value="top_cases",
                        clearable=False,
                        style={"background": "transparent"},
                    ),
                ], md=6),
            ]),
        ]),

        # Insight callouts
        html.Div(id="sql-insight-cards"),

        # Chart from SQL
        html.Div(className="chart-container", children=[
            html.Div("📊 SQL Query Visualization", className="chart-title"),
            dcc.Loading(
                dcc.Graph(id="sql-bar-chart", style={"height": "420px"},
                          config={"displayModeBar": False}),
                type="dot", color=PURPLE,
            ),
        ]),

        # DataTable
        html.Div(className="chart-container", children=[
            html.Div("🗃️ Query Results", className="chart-title"),
            dcc.Loading(
                html.Div(id="sql-table-container"),
                type="dot", color=CYAN,
            ),
        ]),
    ])


# ═══════════════════════════════════════════════════════════════════════════
#  FOOTER
# ═══════════════════════════════════════════════════════════════════════════
def _footer():
    return html.Div(
        className="dashboard-footer",
        children=[
            html.P([
                "Built with ",
                html.A("Plotly Dash", href="https://plotly.com/dash/", target="_blank"),
                " · Data sourced from ",
                html.A("Our World in Data", href="https://ourworldindata.org/covid-deaths", target="_blank"),
            ]),
            html.P("© 2026 COVID-19 Analytics Project"),
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN LAYOUT BUILDER
# ═══════════════════════════════════════════════════════════════════════════
def build_layout(app):
    """Return the full app layout."""
    return html.Div(className="dashboard-container", children=[
        # Interval for potential live refresh (every 5 min)
        dcc.Interval(id="refresh-interval", interval=300_000, n_intervals=0),

        _header(),
        _kpi_row(),

        # Tabs
        dcc.Tabs(
            id="main-tabs",
            value="tab-global",
            className="custom-tabs",
            children=[
                dcc.Tab(label="🌍 Global Overview", value="tab-global", className="custom-tab tab"),
                dcc.Tab(label="🇮🇳 India Deep Dive", value="tab-india", className="custom-tab tab"),
                dcc.Tab(label="📊 Trends & Analysis", value="tab-trends", className="custom-tab tab"),
                dcc.Tab(label="🗄️ SQL Insights", value="tab-sql", className="custom-tab tab"),
            ],
        ),

        # Tab content container
        html.Div(id="tab-content", style={"marginTop": "8px"}),

        _footer(),
    ])


# ═══════════════════════════════════════════════════════════════════════════
#  PAGE RENDERERS (used by callback)
# ═══════════════════════════════════════════════════════════════════════════
PAGE_MAP = {
    "tab-global": _page_global,
    "tab-india": _page_india,
    "tab-trends": _page_trends,
    "tab-sql": _page_sql,
}
