import os
import dash
from dash import dcc, html, dash_table, Input, Output
import plotly.express as px
import pandas as pd
import numpy as np
from databricks.sdk import WorkspaceClient

# ═══════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════
WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "401941d60f2786b9")

# ═══════════════════════════════════════════════════════════
#  DATA LAYER
# ═══════════════════════════════════════════════════════════
w = WorkspaceClient()


def run_query(sql_text: str) -> pd.DataFrame:
    """Execute SQL via Databricks Statement Execution API."""
    resp = w.statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID,
        statement=sql_text,
        wait_timeout="50s",
    )
    if resp.status and resp.status.error:
        raise RuntimeError(f"SQL error: {resp.status.error.message}")
    if resp.manifest is None:
        raise RuntimeError(f"Query returned no manifest. Status: {resp.status}")
    cols = [c.name for c in resp.manifest.schema.columns]
    rows = resp.result.data_array if resp.result and resp.result.data_array else []
    return pd.DataFrame(rows, columns=cols)


print("Loading business data from genieology.gold.business ...")
df = run_query("""
    SELECT business_id, business_name, category, subcategories,
           city, state, address, postal_code,
           latitude, longitude, review_count, rating, checkin_count
    FROM genieology.gold.business
""")
print(f"Loaded {len(df):,} businesses")

# Type conversions
for c in ["latitude", "longitude", "rating"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
for c in ["review_count", "checkin_count"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

CATEGORIES = sorted(df["category"].dropna().unique())
CITIES = sorted(df["city"].dropna().unique())
STATES = sorted(df["state"].dropna().unique())

# ═══════════════════════════════════════════════════════════
#  THEME
# ═══════════════════════════════════════════════════════════
BG = "#0B0D13"
CARD = "#151821"
BORDER = "#1F2333"
ACCENT = "#6366F1"
TEXT = "#E2E8F0"
MUTED = "#64748B"
GREEN = "#10B981"

PALETTE = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#F7DC6F", "#BB8FCE",
    "#F1948A", "#82E0AA", "#F0B27A", "#AED6F1", "#A3E4D7",
    "#D7BDE2", "#85929E", "#F9E79F", "#76D7C4", "#ABEBC6",
]
CAT_COLORS = {cat: PALETTE[i % len(PALETTE)] for i, cat in enumerate(CATEGORIES)}


# ═══════════════════════════════════════════════════════════
#  COMPONENT BUILDERS
# ═══════════════════════════════════════════════════════════
def kpi_card(title, value, subtitle=""):
    return html.Div(
        [
            html.P(title, style={"color": MUTED, "fontSize": "12px", "margin": "0 0 8px",
                                  "textTransform": "uppercase", "letterSpacing": "0.5px"}),
            html.H3(value, style={"color": TEXT, "margin": "0", "fontSize": "26px", "fontWeight": "700"}),
            html.P(subtitle, style={"color": GREEN, "fontSize": "12px", "margin": "6px 0 0"}) if subtitle else None,
        ],
        style={
            "background": CARD, "border": f"1px solid {BORDER}",
            "borderRadius": "12px", "padding": "20px 24px",
            "flex": "1", "minWidth": "160px",
        },
    )


def highlight_card(label, name, detail):
    return html.Div(
        [
            html.P(label, style={"color": MUTED, "fontSize": "11px", "textTransform": "uppercase",
                                  "letterSpacing": "0.5px", "margin": "0 0 8px"}),
            html.P(name, style={"color": TEXT, "fontWeight": "600", "fontSize": "14px",
                                 "margin": "0 0 4px", "whiteSpace": "nowrap",
                                 "overflow": "hidden", "textOverflow": "ellipsis"}, title=name),
            html.P(detail, style={"color": GREEN, "fontSize": "12px", "margin": "0"}),
        ],
        style={
            "background": CARD, "border": f"1px solid {BORDER}",
            "borderRadius": "10px", "padding": "16px", "marginBottom": "10px",
        },
    )


# ═══════════════════════════════════════════════════════════
#  DASH APP
# ═══════════════════════════════════════════════════════════
app = dash.Dash(__name__, title="Yelp Business Overview")
app.config.suppress_callback_exceptions = True

app.index_string = """<!DOCTYPE html>
<html>
<head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { margin: 0; background: #0B0D13; }
        .Select-control { background-color: #1A1D29 !important; border-color: #1F2333 !important; color: #E2E8F0 !important; }
        .Select-menu-outer { background-color: #1A1D29 !important; border-color: #1F2333 !important; }
        .VirtualizedSelectOption { background-color: #1A1D29; color: #E2E8F0; }
        .VirtualizedSelectFocusedOption { background-color: #2A2D3A !important; }
        .Select-value-label { color: #E2E8F0 !important; }
        .Select-placeholder { color: #64748B !important; }
        .Select-input input { color: #E2E8F0 !important; }
        .Select--multi .Select-value { background-color: #6366F1 !important; border-color: #6366F1 !important; color: white !important; border-radius: 4px !important; }
        .Select--multi .Select-value-icon { border-color: rgba(255,255,255,0.2) !important; }
        .Select--multi .Select-value-icon:hover { background-color: #4F46E5 !important; color: white !important; }
        .Select-arrow { border-color: #64748B transparent transparent !important; }
        .Select.is-open > .Select-control .Select-arrow { border-color: transparent transparent #64748B !important; }
        .Select-clear { color: #64748B !important; }
        .Select-noresults { color: #64748B; background: #1A1D29; }
        .rc-slider-track { background-color: #6366F1; }
        .rc-slider-handle { border-color: #6366F1; background-color: #6366F1; }
        .rc-slider-rail { background-color: #1F2333; }
        .rc-slider-dot { background-color: #1F2333; border-color: #1F2333; }
        .dash-spreadsheet .dash-filter input { background-color: #151821 !important; color: #E2E8F0 !important; border-color: #1F2333 !important; }
        .previous-next-container button { color: #E2E8F0 !important; background: transparent !important; }
        .page-number { color: #E2E8F0 !important; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #0B0D13; }
        ::-webkit-scrollbar-thumb { background: #2A2D3A; border-radius: 3px; }
    </style>
</head>
<body>
    {%app_entry%}
    <footer>
        {%config%}
        {%scripts%}
        {%renderer%}
    </footer>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════
#  LAYOUT
# ═══════════════════════════════════════════════════════════
app.layout = html.Div(
    style={"backgroundColor": BG, "fontFamily": "'Inter', -apple-system, sans-serif",
           "minHeight": "100vh", "color": TEXT},
    children=[
        # ── Header ──
        html.Div(
            style={"display": "flex", "alignItems": "center", "justifyContent": "space-between",
                    "padding": "14px 32px", "borderBottom": f"1px solid {BORDER}"},
            children=[
                html.Div(style={"display": "flex", "alignItems": "center", "gap": "12px"}, children=[
                    html.Div("Y", style={
                        "background": f"linear-gradient(135deg, {ACCENT}, #8B5CF6)",
                        "color": "white", "borderRadius": "10px", "width": "38px", "height": "38px",
                        "display": "flex", "alignItems": "center", "justifyContent": "center",
                        "fontWeight": "bold", "fontSize": "18px",
                    }),
                    html.Span("Yelp Business Overview", style={"fontSize": "18px", "fontWeight": "700"}),
                ]),
                html.Div(style={"display": "flex", "gap": "28px"}, children=[
                    html.A("Overview", href="#", style={"color": ACCENT, "textDecoration": "none", "fontWeight": "600", "fontSize": "14px"}),
                    html.A("Analytics", href="#", style={"color": MUTED, "textDecoration": "none", "fontSize": "14px"}),
                    html.A("About", href="#", style={"color": MUTED, "textDecoration": "none", "fontSize": "14px"}),
                ]),
            ],
        ),

        # ── KPI Row ──
        html.Div(id="kpi-row", style={"display": "flex", "gap": "16px", "padding": "24px 32px 0"}),

        # ── Main Content: Filters | Map | Highlights ──
        html.Div(
            style={"display": "flex", "gap": "20px", "padding": "20px 32px", "alignItems": "flex-start"},
            children=[
                # Filters sidebar
                html.Div(style={"width": "220px", "flexShrink": "0"}, children=[
                    html.P("Filters", style={"color": TEXT, "fontWeight": "600", "fontSize": "15px", "marginBottom": "16px"}),
                    html.Label("Category", style={"color": MUTED, "fontSize": "12px", "display": "block", "marginBottom": "4px"}),
                    dcc.Dropdown(id="filter-category",
                                 options=[{"label": c, "value": c} for c in CATEGORIES],
                                 multi=True, placeholder="All categories"),
                    html.Div(style={"height": "12px"}),
                    html.Label("City", style={"color": MUTED, "fontSize": "12px", "display": "block", "marginBottom": "4px"}),
                    dcc.Dropdown(id="filter-city",
                                 options=[{"label": c, "value": c} for c in CITIES],
                                 multi=True, placeholder="All cities"),
                    html.Div(style={"height": "12px"}),
                    html.Label("State", style={"color": MUTED, "fontSize": "12px", "display": "block", "marginBottom": "4px"}),
                    dcc.Dropdown(id="filter-state",
                                 options=[{"label": s, "value": s} for s in STATES],
                                 multi=True, placeholder="All states"),
                    html.Div(style={"height": "16px"}),
                    html.Label("Min Rating", style={"color": MUTED, "fontSize": "12px", "display": "block", "marginBottom": "8px"}),
                    dcc.Slider(id="filter-rating", min=1, max=5, step=0.5, value=1,
                               marks={i: {"label": str(i), "style": {"color": MUTED}} for i in range(1, 6)}),
                ]),

                # Map
                html.Div(style={"flex": "1", "minWidth": "0"}, children=[
                    dcc.Graph(id="map-graph", style={"height": "500px", "borderRadius": "12px", "overflow": "hidden"}),
                ]),

                # Highlights sidebar
                html.Div(style={"width": "240px", "flexShrink": "0"}, children=[
                    html.P("Highlights", style={"color": TEXT, "fontWeight": "600", "fontSize": "15px", "marginBottom": "16px"}),
                    html.Div(id="highlights-panel"),
                ]),
            ],
        ),

        # ── Data Table ──
        html.Div(style={"padding": "0 32px 32px"}, children=[
            html.P("Business Directory", style={"color": TEXT, "fontWeight": "600", "fontSize": "15px", "marginBottom": "12px"}),
            html.Div(id="data-table-container"),
        ]),
    ],
)


# ═══════════════════════════════════════════════════════════
#  CALLBACKS
# ═══════════════════════════════════════════════════════════
@app.callback(
    Output("kpi-row", "children"),
    Output("map-graph", "figure"),
    Output("highlights-panel", "children"),
    Output("data-table-container", "children"),
    Input("filter-category", "value"),
    Input("filter-city", "value"),
    Input("filter-state", "value"),
    Input("filter-rating", "value"),
)
def update_dashboard(categories, cities, states, min_rating):
    filtered = df.copy()
    if categories:
        filtered = filtered[filtered["category"].isin(categories)]
    if cities:
        filtered = filtered[filtered["city"].isin(cities)]
    if states:
        filtered = filtered[filtered["state"].isin(states)]
    if min_rating and min_rating > 1:
        filtered = filtered[filtered["rating"] >= min_rating]

    n = len(filtered)
    avg_r = filtered["rating"].mean() if n else 0
    tot_rev = int(filtered["review_count"].sum())
    tot_chk = int(filtered["checkin_count"].sum())

    # ── KPIs ──
    kpis = [
        kpi_card("Total Businesses", f"{n:,}", f"across {filtered['city'].nunique()} cities"),
        kpi_card("Avg Rating", f"{avg_r:.2f} \u2605", f"{filtered['category'].nunique()} categories"),
        kpi_card("Total Reviews", f"{tot_rev:,}", f"{tot_rev // max(n, 1)} avg per business"),
        kpi_card("Total Check-ins", f"{tot_chk:,}", f"{tot_chk // max(n, 1)} avg per business"),
    ]

    # ── Map ──
    map_df = filtered.dropna(subset=["latitude", "longitude"]).copy()
    if len(map_df) > 0:
        map_df["_size"] = np.sqrt(map_df["review_count"].fillna(0).clip(lower=1)) + 2
        fig = px.scatter_mapbox(
            map_df, lat="latitude", lon="longitude",
            color="category", color_discrete_map=CAT_COLORS,
            hover_name="business_name",
            hover_data={"rating": ":.1f", "review_count": ":,", "city": True,
                        "category": True, "latitude": False, "longitude": False, "_size": False},
            size="_size", size_max=16,
            zoom=9, mapbox_style="carto-darkmatter",
        )
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor=CARD,
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT, size=10),
                        orientation="h", yanchor="top", y=-0.02, xanchor="center", x=0.5),
            mapbox_center=dict(lat=map_df["latitude"].mean(), lon=map_df["longitude"].mean()),
        )
    else:
        fig = px.scatter_mapbox(
            pd.DataFrame({"lat": [39.5], "lon": [-98.35]}),
            lat="lat", lon="lon", zoom=3, mapbox_style="carto-darkmatter",
        )
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor=CARD)

    # ── Highlights ──
    highlights = []
    if n > 0:
        top = filtered.nlargest(1, "rating").iloc[0]
        most_rev = filtered.nlargest(1, "review_count").iloc[0]
        most_act = filtered.nlargest(1, "checkin_count").iloc[0]
        highlights = [
            highlight_card("Top Rated", str(top["business_name"]),
                           f"\u2605 {top['rating']:.1f} \u00b7 {top['category']}"),
            highlight_card("Most Reviewed", str(most_rev["business_name"]),
                           f"{most_rev['review_count']:,} reviews \u00b7 {most_rev['city']}"),
            highlight_card("Most Active", str(most_act["business_name"]),
                           f"{most_act['checkin_count']:,} check-ins \u00b7 {most_act['city']}"),
        ]

    # ── Table ──
    t = filtered[["business_name", "category", "city", "state", "rating",
                   "review_count", "checkin_count"]].copy()
    t.columns = ["Business", "Category", "City", "State", "Rating", "Reviews", "Check-ins"]
    t = t.sort_values("Reviews", ascending=False).head(200)

    table = dash_table.DataTable(
        data=t.to_dict("records"),
        columns=[{"name": c, "id": c} for c in t.columns],
        page_size=12, sort_action="native", filter_action="native",
        style_header={"backgroundColor": CARD, "color": MUTED, "fontWeight": "600",
                       "fontSize": "12px", "border": f"1px solid {BORDER}", "textTransform": "uppercase"},
        style_cell={"backgroundColor": BG, "color": TEXT, "border": f"1px solid {BORDER}",
                     "fontSize": "13px", "padding": "10px 14px", "textAlign": "left",
                     "maxWidth": "200px", "overflow": "hidden", "textOverflow": "ellipsis"},
        style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#111320"}],
        style_table={"borderRadius": "12px", "overflow": "hidden", "border": f"1px solid {BORDER}"},
    )

    return kpis, fig, highlights, table


# ═══════════════════════════════════════════════════════════
#  ENTRYPOINT
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
