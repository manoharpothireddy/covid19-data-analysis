import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "processed")

covid_df = pd.read_csv(os.path.join(DATA_DIR, "covid_cleaned.csv"), parse_dates=["date"])
india_df = pd.read_csv(os.path.join(DATA_DIR, "india_covid.csv"), parse_dates=["date"])
country_summary = pd.read_csv(os.path.join(DATA_DIR, "country_summary.csv"))
"""
dashboard/callbacks.py
======================
All five Dash callbacks for the COVID-19 Analytics Dashboard.

Data contract (from app.py)
---------------------------
  covid_df        — full cleaned global dataset (fact_covid_daily equivalent)
                    Required columns: date, continent, location, iso_code,
                    new_cases, new_cases_smoothed, new_deaths, total_cases,
                    total_deaths, people_fully_vaccinated, population,
                    case_fatality_rate, vaccination_rate, rolling_7day_cases
  india_df        — India-only time series
                    Required columns: date, new_cases, new_deaths,
                    vaccination_rate, rolling_7day_cases, rolling_7day_deaths,
                    wave_number
  country_summary — one row per country (latest snapshot)
                    Required columns: location, continent, population,
                    total_cases_per_million, total_deaths_per_million,
                    vaccination_rate, case_fatality_rate

Usage
-----
  # In app.py, after layout is defined:
  from dashboard.callbacks import register_callbacks
  register_callbacks(app)
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output
from plotly.subplots import make_subplots


# ---------------------------------------------------------------------------
# Theme constants
# ---------------------------------------------------------------------------
BG_COLOR    = "#1a1a2e"
PAPER_COLOR = "#16213e"
TEXT_COLOR  = "#e0e0f0"
GRID_COLOR  = "rgba(255,255,255,0.06)"
FONT_FAMILY = "Inter, system-ui, sans-serif"

CYAN    = "#00d2ff"
PURPLE  = "#7b2ff7"
EMERALD = "#10b981"
ORANGE  = "#f59e0b"
RED     = "#ef4444"
PINK    = "#ec4899"
BLUE    = "#3b82f6"

CONTINENT_PALETTE = {
    "Asia":          "#00d2ff",
    "Europe":        "#7b2ff7",
    "North America": "#10b981",
    "South America": "#ef4444",
    "Africa":        "#f59e0b",
    "Oceania":       "#3b82f6",
}

BASE_LAYOUT = dict(
    paper_bgcolor = PAPER_COLOR,
    plot_bgcolor  = BG_COLOR,
    font          = dict(family=FONT_FAMILY, color=TEXT_COLOR, size=12),
    margin        = dict(l=16, r=16, t=52, b=16),
    legend        = dict(
        bgcolor="rgba(22,33,62,0.8)", bordercolor="rgba(255,255,255,0.1)",
        borderwidth=1, font_size=11,
    ),
    xaxis = dict(gridcolor=GRID_COLOR, zeroline=False, showline=False,
                 tickfont=dict(color=TEXT_COLOR, size=11)),
    yaxis = dict(gridcolor=GRID_COLOR, zeroline=False, showline=False,
                 tickfont=dict(color=TEXT_COLOR, size=11)),
    hoverlabel = dict(bgcolor="#0f1120", bordercolor="rgba(255,255,255,0.15)",
                      font_size=12, font_family=FONT_FAMILY),
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _apply_base(fig, title="", height=400):
    layout = dict(**BASE_LAYOUT, height=height)
    if title:
        layout["title"] = dict(text=title, font_size=15,
                               font_color=TEXT_COLOR, x=0.01, xanchor="left")
    fig.update_layout(**layout)
    return fig


def _empty(message="No data for the selected filters"):
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper",
                       showarrow=False, font=dict(size=14, color="rgba(200,200,220,0.5)"))
    return _apply_base(fig)


def _fmt_big(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "N/A"
    if np.isnan(n): return "N/A"
    if n >= 1e9: return f"{n/1e9:.2f}B"
    if n >= 1e6: return f"{n/1e6:.2f}M"
    if n >= 1e3: return f"{n/1e3:.1f}K"
    return f"{n:,.0f}"


# ---------------------------------------------------------------------------
# CALLBACK REGISTRATION
# ---------------------------------------------------------------------------

def register_callbacks(app):

    # ── CALLBACK 1 — Global Trend Chart ────────────────────────────────────
    @app.callback(
        Output("global-trend-chart", "figure"),
        Input("continent-filter",    "value"),
        Input("date-range-slider",   "value"),
    )
    def update_global_trend(continent, date_range):
        df = covid_df.copy()
        if "date" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["date"]):
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])

        if continent and continent != "All" and "continent" in df.columns:
            df = df[df["continent"] == continent]

        if date_range and len(date_range) == 2:
            all_dates = df["date"].dt.normalize().drop_duplicates().sort_values()
            if len(all_dates) > 0:
                min_d, max_d = all_dates.min(), all_dates.max()
                total = (max_d - min_d).days or 1
                s = min_d + pd.Timedelta(days=int(date_range[0] / 100 * total))
                e = min_d + pd.Timedelta(days=int(date_range[1] / 100 * total))
                df = df[(df["date"] >= s) & (df["date"] <= e)]

        if df.empty:
            return _empty("No data for the selected continent / date range.")

        agg_dict = {
            "daily_cases":  ("new_cases",          "sum"),
            "daily_deaths": ("new_deaths",          "sum"),
            "avg_7d_cases": ("rolling_7day_cases",  "mean"),
        }
        if "rolling_7day_deaths" in df.columns:
            agg_dict["avg_7d_deaths"] = ("rolling_7day_deaths", "mean")

        agg = df.groupby("date", as_index=False).agg(**agg_dict).sort_values("date")

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            subplot_titles=(
                "Daily New Cases" + (f" — {continent}" if continent and continent != "All" else " — Global"),
                "Daily New Deaths",
            ),
            vertical_spacing=0.10, row_heights=[0.6, 0.4],
        )
        fig.add_trace(go.Bar(x=agg["date"], y=agg["daily_cases"], name="Daily Cases",
                             marker_color="rgba(0,210,255,0.20)", marker_line_width=0,
                             hovertemplate="%{x|%d %b %Y}<br>Cases: %{y:,.0f}<extra></extra>"),
                      row=1, col=1)
        fig.add_trace(go.Scatter(x=agg["date"], y=agg["avg_7d_cases"], name="7-Day Avg",
                                 line=dict(color=CYAN, width=2.5),
                                 hovertemplate="%{x|%d %b %Y}<br>7-Day Avg: %{y:,.0f}<extra></extra>"),
                      row=1, col=1)
        fig.add_trace(go.Bar(x=agg["date"], y=agg["daily_deaths"], name="Daily Deaths",
                             marker_color="rgba(239,68,68,0.22)", marker_line_width=0,
                             hovertemplate="%{x|%d %b %Y}<br>Deaths: %{y:,.0f}<extra></extra>"),
                      row=2, col=1)
        if "avg_7d_deaths" in agg.columns:
            fig.add_trace(go.Scatter(x=agg["date"], y=agg["avg_7d_deaths"],
                                     name="7-Day Avg Deaths", line=dict(color=RED, width=2.5),
                                     hovertemplate="%{x|%d %b %Y}<br>7-Day Avg: %{y:,.0f}<extra></extra>"),
                          row=2, col=1)

        _apply_base(fig, height=480)
        fig.update_xaxes(gridcolor=GRID_COLOR, tickfont_color=TEXT_COLOR)
        fig.update_yaxes(gridcolor=GRID_COLOR, tickfont_color=TEXT_COLOR)
        fig.update_annotations(font_color=TEXT_COLOR)
        return fig

    # ── CALLBACK 2 — India Wave Chart ───────────────────────────────────────
    @app.callback(
        Output("india-wave-chart",     "figure"),
        Input("india-metric-toggle",   "value"),
    )
    def update_india_wave_chart(metric):
        df = india_df.copy()
        if "date" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["date"]):
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date")
        if df.empty:
            return _empty("India data not loaded.")

        METRIC_MAP = {
            "new_cases":        dict(col="new_cases",        smooth_col="rolling_7day_cases",
                                     area="rgba(0,210,255,0.18)",   line=CYAN,    smooth="#00aacc",
                                     ylabel="Daily New Cases",       fmt=",.0f",
                                     title="India Daily New Cases — Wave Analysis"),
            "new_deaths":       dict(col="new_deaths",       smooth_col="rolling_7day_deaths",
                                     area="rgba(239,68,68,0.18)",   line=RED,     smooth="#cc2222",
                                     ylabel="Daily New Deaths",      fmt=",.0f",
                                     title="India Daily New Deaths — Wave Analysis"),
            "vaccination_rate": dict(col="vaccination_rate", smooth_col=None,
                                     area="rgba(16,185,129,0.18)",  line=EMERALD, smooth=None,
                                     ylabel="Vaccination Rate (%)",  fmt=".2f",
                                     title="India Vaccination Rate Progress"),
        }
        cfg = METRIC_MAP.get(metric, METRIC_MAP["new_cases"])
        col = cfg["col"]
        if col not in df.columns:
            return _empty(f"Column '{col}' not found in India dataset.")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[col], fill="tozeroy",
            name=col.replace("_", " ").title(),
            fillcolor=cfg["area"], line=dict(color=cfg["line"], width=1.5),
            hovertemplate=f"%{{x|%d %b %Y}}<br>{col.replace('_',' ').title()}: %{{y:{cfg['fmt']}}}<extra></extra>",
        ))
        if cfg["smooth_col"] and cfg["smooth_col"] in df.columns:
            fig.add_trace(go.Scatter(
                x=df["date"], y=df[cfg["smooth_col"]], name="7-Day Rolling Avg",
                line=dict(color=cfg["smooth"], width=2.5),
                hovertemplate=f"%{{x|%d %b %Y}}<br>7-Day Avg: %{{y:{cfg['fmt']}}}<extra></extra>",
            ))

        # Wave shading
        WAVE_REGIONS = {
            1: ("2020-01-30","2021-02-28","rgba(0,210,255,0.04)"),
            2: ("2021-03-01","2021-08-31","rgba(239,68,68,0.06)"),
            3: ("2021-12-15","2022-03-31","rgba(245,158,11,0.05)"),
        }
        if "wave_number" in df.columns:
            for wn, (_, _, color) in WAVE_REGIONS.items():
                wd = df[df["wave_number"] == wn]
                if not wd.empty:
                    fig.add_vrect(x0=wd["date"].min(), x1=wd["date"].max(),
                                  fillcolor=color, opacity=1, layer="below", line_width=0)
        else:
            for _, (s, e, color) in WAVE_REGIONS.items():
                fig.add_vrect(x0=s, x1=e, fillcolor=color, opacity=1, layer="below", line_width=0)

        # Peak annotations
        if metric in ("new_cases", "new_deaths"):
            for window, color, label, ax, ay in [
                (("2021-04-01","2021-06-30"), RED,    "<b>Δ Delta Peak</b>",   60, -55),
                (("2022-01-01","2022-03-31"), ORANGE, "<b>Ω Omicron Peak</b>", -70, -50),
            ]:
                win_df = df[(df["date"] >= window[0]) & (df["date"] <= window[1])]
                if not win_df.empty and col in win_df.columns:
                    pr = win_df.loc[win_df[col].idxmax()]
                    fig.add_annotation(
                        x=pr["date"], y=pr[col],
                        text=f"{label}<br>{pr[col]:,.0f}",
                        showarrow=True, arrowhead=2, arrowcolor=color, arrowwidth=1.5,
                        ax=ax, ay=ay, font=dict(color=color, size=11),
                        bgcolor="rgba(22,33,62,0.85)", bordercolor=color,
                        borderwidth=1, borderpad=4,
                    )

        _apply_base(fig, title=cfg["title"], height=440)
        fig.update_yaxes(title_text=cfg["ylabel"], title_font_color=TEXT_COLOR)
        fig.update_xaxes(title_text="Date", title_font_color=TEXT_COLOR)
        return fig

    # ── CALLBACK 3 — Country Comparison Bar Chart ───────────────────────────
    @app.callback(
        Output("country-bar-chart", "figure"),
        Input("metric-dropdown",    "value"),
    )
    def update_country_bar(metric):
        df = country_summary.copy()
        if df.empty:
            return _empty("Country summary data not loaded.")

        METRIC_LABELS = {
            "total_cases_per_million":  "Cases per Million Population",
            "total_deaths_per_million": "Deaths per Million Population",
            "vaccination_rate":         "Vaccination Rate (%)",
        }
        label = METRIC_LABELS.get(metric, metric.replace("_", " ").title())
        if metric not in df.columns:
            return _empty(f"Metric '{metric}' not found.")

        top15 = (df.dropna(subset=[metric])
                   .nlargest(15, metric)
                   .sort_values(metric, ascending=True))
        if top15.empty:
            return _empty(f"No data for: {label}")

        loc_col = "location" if "location" in top15.columns else "iso_code"
        colours = [CONTINENT_PALETTE.get(c, BLUE)
                   for c in top15.get("continent", pd.Series(["Unknown"] * len(top15)))]
        customdata = top15["population"].values if "population" in top15.columns else None
        hover = f"<b>%{{y}}</b><br>{label}: %{{x:,.2f}}"
        if customdata is not None:
            hover += "<br>Population: %{customdata:,.0f}"
        hover += "<extra></extra>"

        fig = go.Figure(go.Bar(
            x=top15[metric], y=top15[loc_col], orientation="h",
            marker=dict(color=colours, opacity=0.85,
                        line=dict(color="rgba(255,255,255,0.05)", width=0.5)),
            text=top15[metric].apply(lambda v: f"{v:,.1f}" if pd.notna(v) else ""),
            textposition="outside", textfont=dict(color=TEXT_COLOR, size=11),
            hovertemplate=hover, customdata=customdata,
        ))
        _apply_base(fig, title=f"Top 15 Countries — {label}", height=460)
        fig.update_xaxes(title_text=label, title_font_color=TEXT_COLOR)
        fig.update_yaxes(tickfont=dict(size=11, color=TEXT_COLOR))

        for cont, colour in CONTINENT_PALETTE.items():
            if cont in top15.get("continent", pd.Series()).values:
                fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                                         marker=dict(size=10, color=colour),
                                         name=cont, showlegend=True))
        return fig

    # ── CALLBACK 4 — Vaccination vs CFR Scatter ─────────────────────────────
    @app.callback(
        Output("vax-scatter-chart",       "figure"),
        Input("continent-scatter-filter", "value"),
    )
    def update_vax_scatter(continent):
        df = country_summary.copy()
        if df.empty:
            return _empty("Country summary data not loaded.")
        if "case_fatality_rate" not in df.columns:
            return _empty("case_fatality_rate column not found.")

        df["cfr_pct"] = (df["case_fatality_rate"] * 100
                         if df["case_fatality_rate"].dropna().max() <= 1
                         else df["case_fatality_rate"])
        vax_col = "vaccination_rate"
        if vax_col not in df.columns:
            return _empty("vaccination_rate column not found.")

        df = df.dropna(subset=[vax_col, "cfr_pct"])
        df = df[df[vax_col] > 0]
        if continent and continent != "All" and "continent" in df.columns:
            df = df[df["continent"] == continent]
        if df.empty:
            return _empty("No data for the selected continent.")

        fig = go.Figure()
        for cont in sorted(df["continent"].dropna().unique() if "continent" in df.columns else ["Unknown"]):
            sub = df[df["continent"] == cont] if "continent" in df.columns else df
            if "population" in sub.columns:
                pop = sub["population"].fillna(1e6)
                pop_norm = np.clip((pop - pop.min()) / (pop.max() - pop.min() + 1), 0, 1)
                msize = 5 + pop_norm * 43
            else:
                msize = 10
            loc_col  = "location" if "location" in sub.columns else "iso_code"
            loc_vals = sub[loc_col] if loc_col in sub.columns else [""] * len(sub)
            fig.add_trace(go.Scatter(
                x=sub[vax_col], y=sub["cfr_pct"], mode="markers", name=cont,
                marker=dict(size=msize, color=CONTINENT_PALETTE.get(cont, BLUE),
                            opacity=0.72, sizemode="diameter",
                            line=dict(color="rgba(255,255,255,0.08)", width=0.5)),
                text=loc_vals,
                hovertemplate="<b>%{text}</b><br>Vaccination Rate: %{x:.1f}%<br>CFR: %{y:.3f}%<extra></extra>",
            ))

        # India star — always shown
        india_row = (country_summary[country_summary["iso_code"] == "IND"]
                     if "iso_code" in country_summary.columns else pd.DataFrame())
        if not india_row.empty and vax_col in india_row.columns:
            i_cfr = india_row["case_fatality_rate"].values[0]
            if i_cfr <= 1: i_cfr *= 100
            fig.add_trace(go.Scatter(
                x=[india_row[vax_col].values[0]], y=[i_cfr],
                mode="markers+text", name="🇮🇳 India",
                marker=dict(size=22, color="#ffd700", symbol="star",
                            line=dict(color="#fff", width=1)),
                text=["  🇮🇳 India"], textposition="middle right",
                textfont=dict(color="#ffd700", size=12),
                hovertemplate="<b>🇮🇳 India</b><br>Vaccination: %{x:.1f}%<br>CFR: %{y:.3f}%<extra></extra>",
            ))

        # OLS trend line
        av = country_summary.dropna(subset=[vax_col, "case_fatality_rate"])
        av = av[av[vax_col] > 0]
        if len(av) > 5:
            cfr_s = av["case_fatality_rate"] * 100 if av["case_fatality_rate"].max() <= 1 else av["case_fatality_rate"]
            z = np.polyfit(av[vax_col], cfr_s, 1)
            xl = np.linspace(av[vax_col].min(), av[vax_col].max(), 100)
            fig.add_trace(go.Scatter(x=xl, y=np.polyval(z, xl), mode="lines", name="Trend (OLS)",
                                     line=dict(color="rgba(255,255,255,0.18)", width=1.5, dash="dash"),
                                     hoverinfo="skip", showlegend=True))

        _apply_base(fig, title="Vaccination Rate vs Case Fatality Rate", height=480)
        fig.update_xaxes(title_text="Vaccination Rate (%)", title_font_color=TEXT_COLOR)
        fig.update_yaxes(title_text="Case Fatality Rate (%)", title_font_color=TEXT_COLOR)
        fig.update_layout(legend_title_text="Continent", legend_title_font_color=TEXT_COLOR)
        return fig

    # ── CALLBACK 5 — KPI Cards ──────────────────────────────────────────────
    @app.callback(
        Output("kpi-total-cases",  "children"),
        Output("kpi-total-deaths", "children"),
        Output("kpi-vaccination",  "children"),
        Output("kpi-cfr",          "children"),
        Input("date-range-slider", "value"),
    )
    def update_kpi_cards(date_range):
        df = covid_df.copy()
        if "date" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["date"]):
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])

        if date_range and len(date_range) == 2:
            all_dates = df["date"].dt.normalize().drop_duplicates().sort_values()
            if len(all_dates) > 1:
                min_d, max_d = all_dates.min(), all_dates.max()
                total = (max_d - min_d).days or 1
                s = min_d + pd.Timedelta(days=int(date_range[0] / 100 * total))
                e = min_d + pd.Timedelta(days=int(date_range[1] / 100 * total))
                df = df[(df["date"] >= s) & (df["date"] <= e)]

        if df.empty:
            return "N/A", "N/A", "N/A", "N/A"

        group_col = "iso_code" if "iso_code" in df.columns else "location"
        if group_col in df.columns:
            agg_spec = {}
            agg_spec["max_cases"]  = ("total_cases",       "max") if "total_cases"       in df.columns else ("new_cases",  "sum")
            agg_spec["max_deaths"] = ("total_deaths",      "max") if "total_deaths"      in df.columns else ("new_deaths", "sum")
            agg_spec["max_vax"]    = ("vaccination_rate",  "max") if "vaccination_rate"  in df.columns else ("new_cases",  "count")
            agg_spec["population"] = ("population",        "max") if "population"        in df.columns else ("new_cases",  "count")
            pc = df.groupby(group_col, as_index=False).agg(**agg_spec)
            global_cases  = pc["max_cases"].sum()
            global_deaths = pc["max_deaths"].sum()
            vax_pct = ((pc["max_vax"] * pc["population"]).sum() / pc["population"].sum()
                       if "population" in pc.columns and pc["population"].sum() > 0
                       else pc["max_vax"].mean())
        else:
            last = df.sort_values("date").iloc[-1]
            global_cases  = last.get("total_cases",      0) or 0
            global_deaths = last.get("total_deaths",     0) or 0
            vax_pct       = last.get("vaccination_rate", 0) or 0

        cfr_pct = (global_deaths / max(global_cases, 1)) * 100
        return _fmt_big(global_cases), _fmt_big(global_deaths), f"{vax_pct:.1f}%", f"{cfr_pct:.3f}%"