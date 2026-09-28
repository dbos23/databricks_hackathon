import os
import re
import dash
from dash import dcc, html, Input, Output, State, no_update
import plotly.express as px
import pandas as pd
import numpy as np
import time
from databricks.sdk import WorkspaceClient

WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "401941d60f2786b9")
w = WorkspaceClient()


# ── Theme: warm cream & mauve ──
# TEXT_LIGHT and ACCENT were darkened slightly so they pass WCAG AA (4.5:1) on
# white, the cream page background, and HIGHLIGHT_BG.
BG = "#F7F3EF"
CARD = "#FFFFFF"
BORDER = "#DCD4D9"
PRIMARY = "#5B4A5E"
TEXT_DARK = "#2D1F30"
TEXT_MED = "#6B5B6E"
TEXT_LIGHT = "#736676"   # was #9B8E9E (3.1:1 on white)
ACCENT = "#80606D"       # was #8B6B78 (3.9:1 on HIGHLIGHT_BG)
HIGHLIGHT_BG = "#F0EAE6"

MAP_STYLE = "carto-positron"

# Category colors for the map. The old palette was fifteen near-identical mauves,
# so categories could only be told apart by hovering. These are muted enough to
# sit with the theme but distinct in hue, and each has at least 3:1 contrast
# against the light basemap.
CATEGORY_PALETTE = [
    "#5B4A5E", "#B5673F", "#3F7A74", "#A07F2A", "#6B7F3A",
    "#4A6A8F", "#A04F63", "#8C6440", "#5F87A6", "#8F6BA0",
    "#4F7050", "#B0706F", "#2F5560", "#9A5E88", "#7A7A52",
]

SANS = "'Inter', -apple-system, sans-serif"
SERIF = "'DM Serif Display', serif"

# Smallest text size used anywhere is 12px (was 9–11px).
SECTION_HEADING_STYLE = {
    "color": TEXT_LIGHT, "fontSize": "12px", "fontWeight": "600",
    "letterSpacing": "1.5px", "textTransform": "uppercase",
    "margin": "0 0 8px", "fontFamily": SANS,
}
# Selected-business panel: one fixed width no matter how long the name or
# subcategory list is. Long words wrap inside it instead of stretching it.
DETAIL_PANEL_WIDTH = "280px"
DETAIL_PANEL_STYLE = {
    "flex": f"0 0 {DETAIL_PANEL_WIDTH}", "width": DETAIL_PANEL_WIDTH,
    "maxWidth": "100%", "boxSizing": "border-box",
    "background": CARD, "border": f"1px solid {BORDER}", "borderRadius": "4px",
    "padding": "20px", "overflowWrap": "anywhere", "wordBreak": "break-word",
}
DETAIL_PANEL_HIDDEN = dict(DETAIL_PANEL_STYLE, display="none")

FIELD_LABEL_STYLE = {
    "color": TEXT_MED, "fontSize": "12px", "fontWeight": "500", "display": "block",
    "marginBottom": "4px", "textTransform": "uppercase", "letterSpacing": "0.5px",
    "fontFamily": SANS,
}


def run_query(sql_text: str) -> pd.DataFrame:
    resp = w.statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID, statement=sql_text, wait_timeout="50s"
    )
    if resp.status and resp.status.error:
        raise RuntimeError(f"SQL error: {resp.status.error.message}")
    if resp.manifest is None:
        raise RuntimeError(f"Query returned no manifest. Status: {resp.status}")
    cols = [c.name for c in resp.manifest.schema.columns]
    rows = resp.result.data_array if resp.result and resp.result.data_array else []
    return pd.DataFrame(rows, columns=cols)


print("Loading business data ...")
df = run_query("""
    SELECT business_id, business_name, category, subcategories,
           city, state, address, postal_code,
           latitude, longitude, review_count, rating, checkin_count
    FROM genieology.gold.business
""")
print(f"Loaded {len(df):,} businesses")

for c in ["latitude", "longitude", "rating"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
for c in ["review_count", "checkin_count"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

CATEGORIES = sorted(df["category"].dropna().unique())
CITIES = sorted(df["city"].dropna().unique())
STATES = sorted(df["state"].dropna().unique())
CAT_COLORS = {cat: CATEGORY_PALETTE[i % len(CATEGORY_PALETTE)] for i, cat in enumerate(CATEGORIES)}


def parse_subcategories(series: pd.Series) -> list:
    """Subcategories are stored as a comma-separated string per row; explode into
    a flat, deduplicated, sorted list of individual subcategory values."""
    values = set()
    for v in series.dropna():
        for piece in str(v).split(","):
            piece = piece.strip()
            if piece:
                values.add(piece)
    return sorted(values)


def row_has_subcategory(value, wanted: set) -> bool:
    if pd.isna(value) or not value:
        return False
    items = {s.strip() for s in str(value).split(",")}
    return bool(items & wanted)


SUBCATEGORIES = parse_subcategories(df["subcategories"])

GENIE_SPACE_ID = "01f1b8f39ea115aabb24013a946478b9"


def _poll_genie_message(conv_id: str, msg_id: str, timeout: int = 120):
    """Poll Genie until the message reaches a terminal status."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = w.genie.get_message(GENIE_SPACE_ID, conv_id, msg_id)
        status = str(getattr(msg, "status", "")).upper()
        if any(s in status for s in ("COMPLETED", "FAILED", "CANCELLED")):
            return msg
        time.sleep(2)
    return msg  # return whatever we have on timeout


def ask_genie(question: str, conv_id: str | None = None):
    """Send a question to the Genie space and return structured results.

    Returns (conv_id, answer_text, sql, result_rows, result_cols).
    """
    try:
        if conv_id:
            resp = w.genie.create_message(GENIE_SPACE_ID, conv_id, question)
        else:
            resp = w.genie.start_conversation(GENIE_SPACE_ID, question)

        # Handle Wait-style vs direct return
        if hasattr(resp, "bind"):
            resp = resp.result()  # Wait object

        cid = getattr(resp, "conversation_id", None) or conv_id
        mid = getattr(resp, "message_id", None) or getattr(resp, "id", None)

        # Poll until terminal
        if mid and cid:
            msg = _poll_genie_message(cid, mid)
        else:
            msg = resp

        # Extract answer text and SQL from attachments
        answer_text = ""
        sql = ""
        attachments = getattr(msg, "attachments", None) or []
        for att in attachments:
            if hasattr(att, "text") and att.text:
                answer_text += str(getattr(att.text, "content", att.text)) + "\n"
            if hasattr(att, "query") and att.query:
                q = att.query
                sql = getattr(q, "query", "") or getattr(q, "sql", "") or ""

        # Fetch query result rows if available
        result_rows, result_cols = [], []
        if sql and mid and cid:
            try:
                for att in attachments:
                    if hasattr(att, "query") and att.query:
                        qid = getattr(att.query, "query_id", None) or getattr(att.query, "id", None)
                        if qid:
                            qr = w.genie.get_message_query_result(GENIE_SPACE_ID, cid, mid, qid)
                            if hasattr(qr, "columns"):
                                result_cols = [str(c.name) if hasattr(c, "name") else str(c)
                                               for c in qr.columns]
                            stmt = getattr(qr, "statement_response", None)
                            if stmt:
                                res = getattr(stmt, "result", None)
                                if res and hasattr(res, "data_array") and res.data_array:
                                    result_rows = [list(r) for r in res.data_array[:50]]
                            break
            except Exception:
                pass  # query result fetch is best-effort

        answer_text = answer_text.strip() or ("Here are the results:" if result_rows else "I couldn't find an answer.")
        return cid, answer_text, sql.strip(), result_rows, result_cols

    except Exception as e:
        return conv_id, f"Sorry, something went wrong: {e}", "", [], []


# ── Small accessibility helpers ──

def sr_only(text):
    """Text that screen readers announce but that isn't shown on screen."""
    return html.Span(text, className="sr-only")


def rating_children(value):
    """'4.5 ★' visually, 'Rated 4.5 out of 5' to a screen reader
    (instead of 'four point five black star')."""
    try:
        r = f"{float(value):.1f}"
    except (ValueError, TypeError):
        return ["No rating"]
    return [html.Span(f"{r} ", **{"aria-hidden": "true"}),
            html.Span("\u2605", **{"aria-hidden": "true"}),
            sr_only(f"Rated {r} out of 5")]


def section_heading(text, id_=None, level=2, extra_style=None):
    style = dict(SECTION_HEADING_STYLE, **(extra_style or {}))
    tag = html.H2 if level == 2 else html.H3
    return tag(text, id=id_, style=style) if id_ else tag(text, style=style)


def filter_field(label, control_id, control):
    """A labeled filter. html.Label's htmlFor connects directly to text inputs;
    the role=group + aria-labelledby wrapper names the dropdowns, whose inner
    input isn't directly addressable from Dash."""
    label_id = f"{control_id}-label"
    return html.Div(
        role="group", style={"marginBottom": "14px"},
        **{"aria-labelledby": label_id},
        children=[html.Label(label, id=label_id, htmlFor=control_id, style=FIELD_LABEL_STYLE),
                  control],
    )


def data_table(cols, rows, caption, max_rows=None):
    """A real HTML table with a caption and column-scoped headers."""
    shown = rows[:max_rows] if max_rows else rows
    th_style = {"padding": "6px 10px", "fontSize": "12px", "fontWeight": "600",
                "color": TEXT_DARK, "borderBottom": f"2px solid {BORDER}",
                "fontFamily": SANS, "textAlign": "left", "whiteSpace": "nowrap"}
    td_style = {"padding": "5px 10px", "fontSize": "12px", "color": TEXT_MED,
                "borderBottom": f"1px solid {BORDER}", "fontFamily": SANS}
    return html.Table(
        style={"width": "100%", "borderCollapse": "collapse", "background": CARD},
        children=[
            html.Caption(caption, className="sr-only"),
            html.Thead(html.Tr([html.Th(c, scope="col", style=th_style) for c in cols])),
            html.Tbody([html.Tr([html.Td(str(v), style=td_style) for v in r]) for r in shown]),
        ],
    )


BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)


def render_bold(text: str):
    """Turn **text** into bold. Everything else stays plain text (not parsed as
    HTML), so Genie output can't inject markup."""
    parts = BOLD_RE.split(text)
    # re.split with one capture group alternates: plain, bold, plain, bold, ...
    return [html.Strong(part, style={"color": TEXT_DARK, "fontWeight": "700"}) if i % 2 else part
            for i, part in enumerate(parts) if part]


def strip_bold(text: str) -> str:
    """Remove ** markers, e.g. for the screen-reader announcement."""
    return BOLD_RE.sub(r"\1", text)


def _render_user_bubble(text: str):
    return html.Div(style={"display": "flex", "justifyContent": "flex-end",
                            "marginBottom": "12px"}, children=[
        html.Div([sr_only("You asked: "), text], style={
            "background": PRIMARY, "color": "white", "padding": "10px 16px",
            "borderRadius": "12px 12px 2px 12px", "maxWidth": "70%",
            "fontSize": "14px", "fontFamily": SANS,
        }),
    ])


def _render_genie_bubble(msg: dict):
    """Render a Genie response bubble from a history dict."""
    children = [
        html.P("Genie", style={"color": ACCENT, "fontWeight": "600",
                "fontSize": "12px", "margin": "0 0 6px",
                "textTransform": "uppercase", "letterSpacing": "1px"}),
    ]
    if msg.get("text"):
        children.append(
            html.P(render_bold(msg["text"]), style={"color": TEXT_MED, "fontSize": "14px",
                    "margin": "0 0 8px", "fontFamily": SANS, "lineHeight": "1.5",
                    "whiteSpace": "pre-wrap"}))
    if msg.get("sql"):
        children.append(
            html.Details(style={"marginBottom": "8px"}, children=[
                html.Summary("SQL query", className="disclosure",
                             style={"color": ACCENT, "fontSize": "12px",
                                    "fontFamily": SANS, "fontWeight": "600",
                                    "letterSpacing": "0.5px", "textTransform": "uppercase"}),
                html.Pre(msg["sql"], tabIndex="0", style={
                    "background": HIGHLIGHT_BG, "padding": "10px 12px",
                    "borderRadius": "4px", "fontSize": "12px", "fontFamily": "monospace",
                    "color": TEXT_DARK, "overflowX": "auto", "margin": "6px 0 0",
                    "border": f"1px solid {BORDER}"}),
            ]))
    if msg.get("cols") and msg.get("rows"):
        total = len(msg["rows"])
        overflow_note = (
            html.P(f"Showing 25 of {total} rows",
                   style={"color": TEXT_LIGHT, "fontSize": "12px", "margin": "4px 0 0",
                          "fontFamily": SANS})
            if total > 25 else None
        )
        children.append(
            html.Div(style={"overflowX": "auto", "marginTop": "4px"}, tabIndex="0",
                     role="region", **{"aria-label": "Genie query results"}, children=[
                data_table(msg["cols"], msg["rows"], "Genie query results", max_rows=25),
                overflow_note,
            ]))

    return html.Div(style={"display": "flex", "justifyContent": "flex-start",
                            "marginBottom": "12px"}, children=[
        html.Div(style={
            "background": CARD, "border": f"1px solid {BORDER}",
            "padding": "14px 18px",
            "borderRadius": "12px 12px 12px 2px", "maxWidth": "85%",
        }, children=children),
    ])


def _render_history(history):
    """Render the whole chat history as bubbles."""
    return [
        _render_user_bubble(e["text"]) if e["role"] == "user" else _render_genie_bubble(e)
        for e in history
    ]


def kpi_card(label, value, subtitle=""):
    return html.Div([
        html.P(label, style={"color": TEXT_LIGHT, "fontSize": "12px", "margin": "0 0 6px",
                              "textTransform": "uppercase", "letterSpacing": "1.5px",
                              "fontFamily": SANS, "fontWeight": "600"}),
        html.P(value, style={"color": TEXT_DARK, "margin": "0", "fontSize": "28px",
                              "fontWeight": "700", "fontFamily": SANS}),
        html.P(subtitle, style={"color": ACCENT, "fontSize": "13px",
                                 "margin": "6px 0 0", "fontFamily": SANS}) if subtitle else None,
    ], style={"background": CARD, "border": f"1px solid {BORDER}",
              "borderRadius": "4px", "padding": "20px 24px",
              "flex": "1 1 180px", "minWidth": "160px", "textAlign": "center"})


def highlight_card(label, name, detail):
    return html.Div([
        html.P(label, style={"color": TEXT_LIGHT, "fontSize": "12px", "textTransform": "uppercase",
                              "letterSpacing": "1.5px", "margin": "0 0 6px", "fontFamily": SANS,
                              "fontWeight": "600"}),
        html.P(name, style={"color": TEXT_DARK, "fontWeight": "600", "fontSize": "15px",
                             "margin": "0 0 4px", "whiteSpace": "nowrap",
                             "overflow": "hidden", "textOverflow": "ellipsis",
                             "fontFamily": SANS}, title=name),
        html.P(detail, style={"color": ACCENT, "fontSize": "13px", "margin": "0", "fontFamily": SANS}),
    ], style={"background": CARD, "border": f"1px solid {BORDER}",
              "borderRadius": "4px", "padding": "16px", "flex": "1 1 200px", "minWidth": "160px"})


def review_card(row):
    """Build an expandable card for a single review or tip."""
    full_text = str(row["full_text"]) if pd.notna(row["full_text"]) else ""
    preview = full_text[:160] + ("\u2026" if len(full_text) > 160 else "")
    posted = row["posted_at"].strftime("%b %d, %Y") if pd.notna(row["posted_at"]) else ""
    is_review = str(row.get("type", "")).lower() == "review"
    badge_bg = ACCENT if is_review else TEXT_LIGHT
    badge_label = "Review" if is_review else "Tip"
    r_val = row.get("rating")

    return html.Details(style={
        "background": CARD, "border": f"1px solid {BORDER}", "borderRadius": "4px",
        "marginBottom": "8px",
    }, children=[
        html.Summary(className="disclosure", style={
            "padding": "16px 20px", "display": "flex",
            "alignItems": "flex-start", "gap": "12px",
        }, children=[
            html.Div(style={"flex": "1", "minWidth": "0"}, children=[
                html.Div(style={"display": "flex", "alignItems": "center", "gap": "8px",
                                 "marginBottom": "6px", "flexWrap": "wrap"}, children=[
                    html.Span(str(row["business_name"]), style={
                        "color": TEXT_DARK, "fontWeight": "600", "fontSize": "15px",
                        "fontFamily": SANS}),
                    html.Span(badge_label, style={
                        "background": badge_bg, "color": "white", "textTransform": "uppercase",
                        "fontSize": "12px", "padding": "2px 6px", "borderRadius": "2px",
                        "letterSpacing": "0.5px", "fontFamily": SANS, "fontWeight": "600"}),
                    html.Span(rating_children(r_val), style={
                        "color": ACCENT, "fontSize": "13px", "fontWeight": "600",
                        "fontFamily": SANS}) if pd.notna(r_val) else None,
                ]),
                html.P(preview, style={"color": TEXT_MED, "fontSize": "13px",
                        "margin": "0", "lineHeight": "1.5", "fontFamily": SANS}),
            ]),
            html.Span([sr_only("Posted "), posted], style={
                "color": TEXT_LIGHT, "fontSize": "12px",
                "whiteSpace": "nowrap", "fontFamily": SANS, "paddingTop": "2px"}),
        ]),
        html.Div(style={"padding": "0 20px 16px", "borderTop": f"1px solid {BORDER}"}, children=[
            html.P(full_text, style={"color": TEXT_DARK, "fontSize": "14px",
                    "lineHeight": "1.7", "margin": "16px 0 12px", "fontFamily": SANS,
                    "whiteSpace": "pre-wrap"}),
            html.Div(style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}, children=[
                html.Span(f"{row['city']}, {row['state']}", style={
                    "color": TEXT_MED, "fontSize": "12px", "fontFamily": SANS}),
                html.Span(str(row["category"]), style={
                    "color": TEXT_MED, "fontSize": "12px", "fontFamily": SANS}),
            ]),
        ]),
    ])


def apply_filters(name_query, categories, subcategories, cities, states, min_rating, min_reviews):
    """Apply sidebar filters to the business DataFrame."""
    filtered = df.copy()
    if name_query and name_query.strip():
        filtered = filtered[filtered["business_name"].str.contains(
            name_query.strip(), case=False, na=False, regex=False)]
    if categories:
        filtered = filtered[filtered["category"].isin(categories)]
    if subcategories:
        wanted = set(subcategories)
        filtered = filtered[filtered["subcategories"].apply(row_has_subcategory, wanted=wanted)]
    if cities:
        filtered = filtered[filtered["city"].isin(cities)]
    if states:
        filtered = filtered[filtered["state"].isin(states)]
    if min_rating and min_rating > 1:
        filtered = filtered[filtered["rating"] >= min_rating]
    if min_reviews and min_reviews > 0:
        filtered = filtered[filtered["review_count"] >= min_reviews]
    return filtered


def build_bar_chart(data, x_col, hover_fmt, selected_id=None):
    """Create a themed horizontal bar chart with optional cross-filter highlight."""
    data = data.copy()
    data["_label"] = data["business_name"].apply(
        lambda x: (str(x)[:28] + "\u2026") if len(str(x)) > 28 else str(x))

    fig = px.bar(data, x=x_col, y="_label", orientation="h",
                 custom_data=["business_id", "business_name", "rating", "review_count", "checkin_count"])

    if selected_id and selected_id in data["business_id"].values:
        # Selected bar: dark fill plus an outline, so it's marked by shape and
        # not only by color. Others stay visible instead of fading to near-white.
        colors = [PRIMARY if bid == selected_id else "#C9BCC4" for bid in data["business_id"]]
        line_w = [2 if bid == selected_id else 0 for bid in data["business_id"]]
    else:
        colors = [ACCENT] * len(data)
        line_w = [0] * len(data)

    fig.update_traces(
        marker_color=colors, marker_opacity=1.0,
        marker_line_color=TEXT_DARK, marker_line_width=line_w,
        hovertemplate=hover_fmt,
    )
    fig.update_layout(
        margin=dict(l=0, r=12, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, showticklabels=True,
                   tickfont=dict(color=TEXT_MED, size=12, family="Inter"), title=None),
        yaxis=dict(showgrid=False, automargin=True,
                   tickfont=dict(color=TEXT_DARK, size=12, family="Inter"), title=None),
        height=320, bargap=0.25,
        hoverlabel=dict(bgcolor=CARD, bordercolor=BORDER,
                        font=dict(color=TEXT_DARK, size=13, family="Inter")),
    )
    return fig


def chart_data_table(data, value_col, value_label, caption):
    """Text version of a bar chart, largest value first."""
    rows = []
    for _, r in data.sort_values(value_col, ascending=False).iterrows():
        rating = f"{r['rating']:.1f}" if pd.notna(r["rating"]) else "N/A"
        value = f"{r[value_col]:.1f}" if value_col == "rating" else f"{int(r[value_col]):,}"
        rows.append([r["business_name"], value, rating,
                     f"{int(r['review_count']):,}", f"{int(r['checkin_count']):,}"])
    if not rows:
        return html.P("No businesses match the current filters.",
                      style={"color": TEXT_MED, "fontSize": "13px", "fontFamily": SANS})
    cols = ["Business", value_label, "Rating", "Reviews", "Visits"]
    return html.Div(style={"overflowX": "auto"}, tabIndex="0", role="region",
                    **{"aria-label": caption},
                    children=data_table(cols, rows, caption))


def chart_card(title, heading_id, graph_id, table_id, summary):
    """A chart with a heading, a screen-reader description, and a
    'view as table' disclosure that works for everyone."""
    return html.Section(
        style={"flex": "1 1 300px", "background": CARD, "border": f"1px solid {BORDER}",
               "borderRadius": "4px", "padding": "16px", "minWidth": "0"},
        **{"aria-labelledby": heading_id},
        children=[
            section_heading(title, heading_id, level=3),
            # role=img collapses Plotly's SVG (which reads as noise) into one
            # described image; the table below carries the actual data.
            html.Div(role="img", **{"aria-label": summary}, children=[
                dcc.Graph(id=graph_id, config={"displayModeBar": False},
                          style={"height": "320px"}),
            ]),
            html.Details(style={"marginTop": "8px"}, children=[
                html.Summary("View as table", className="disclosure", style={
                    "color": ACCENT, "fontSize": "13px", "fontWeight": "600",
                    "fontFamily": SANS}),
                html.Div(id=table_id, style={"marginTop": "8px"}),
            ]),
        ],
    )


app = dash.Dash(__name__, title="Blanche Lifestyle Magazine")
app.config.suppress_callback_exceptions = True

app.index_string = """<!DOCTYPE html>
<html lang="en">
<head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { margin: 0; background: #F7F3EF; }

        /* Screen-reader-only text */
        .sr-only { position: absolute !important; width: 1px; height: 1px; padding: 0;
                   margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0);
                   white-space: nowrap; border: 0; }

        /* Skip link: hidden until a keyboard user tabs to it */
        .skip-link { position: absolute; left: -9999px; top: 12px; z-index: 1000;
                     background: #FFFFFF; color: #5B4A5E; padding: 10px 16px;
                     font-family: 'Inter', sans-serif; font-weight: 600; border-radius: 4px;
                     border: 2px solid #5B4A5E; text-decoration: none; }
        .skip-link:focus { left: 16px; }

        /* Visible keyboard focus everywhere */
        :focus-visible { outline: 3px solid #5B4A5E; outline-offset: 2px; }
        header :focus-visible { outline-color: #FFFFFF; }
        .Select.is-focused > .Select-control { border-color: #5B4A5E !important;
                     box-shadow: 0 0 0 3px rgba(91, 74, 94, 0.45) !important; }

        .Select-control { background-color: #FFFFFF !important; border-color: #B9ADB5 !important; color: #2D1F30 !important; border-radius: 2px !important; }
        .Select-menu-outer { background-color: #FFFFFF !important; border-color: #DCD4D9 !important; }
        .VirtualizedSelectOption { background-color: #FFFFFF; color: #2D1F30; }
        .VirtualizedSelectFocusedOption { background-color: #F0EAE6 !important; }
        .Select-value-label { color: #2D1F30 !important; }
        .Select-placeholder { color: #736676 !important; }
        .Select-input input { color: #2D1F30 !important; }
        .Select--multi .Select-value { background-color: #5B4A5E !important; border-color: #5B4A5E !important; color: white !important; border-radius: 2px !important; }
        .Select--multi .Select-value-icon { border-color: rgba(255,255,255,0.3) !important; }
        .Select--multi .Select-value-icon:hover { background-color: #4A3A4D !important; color: white !important; }
        .Select-arrow { border-color: #736676 transparent transparent !important; }
        .Select.is-open > .Select-control .Select-arrow { border-color: transparent transparent #736676 !important; }
        .Select-clear { color: #736676 !important; }
        .Select-noresults { color: #736676; background: #FFFFFF; }
        input::placeholder { color: #736676; opacity: 1; }
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #F7F3EF; }
        ::-webkit-scrollbar-thumb { background: #B9ADB5; border-radius: 4px; }

        /* Disclosures: keep a visible open/closed marker (was hidden) */
        details > summary { list-style: none; cursor: pointer; }
        details > summary::-webkit-details-marker { display: none; }
        summary.disclosure::before { content: "\\25B8"; content: "\\25B8" / ""; color: #80606D;
                                     margin-right: 6px; display: inline-block; flex-shrink: 0; }
        details[open] > summary.disclosure::before { content: "\\25BE"; content: "\\25BE" / ""; }
        details:hover { box-shadow: 0 1px 4px rgba(0,0,0,0.06); }

        /* Genie typing indicator */
        .typing-dots { display: flex; gap: 5px; align-items: center; height: 16px; padding: 2px 0; }
        .typing-dots span { width: 7px; height: 7px; border-radius: 50%; background: #80606D;
                            opacity: 0.3; animation: genie-bounce 1.2s infinite ease-in-out; }
        .typing-dots span:nth-child(2) { animation-delay: 0.15s; }
        .typing-dots span:nth-child(3) { animation-delay: 0.3s; }
        @keyframes genie-bounce {
            0%, 80%, 100% { opacity: 0.3; transform: translateY(0); }
            40%           { opacity: 1;   transform: translateY(-4px); }
        }
        #genie-input[readonly] { background: #F0EAE6 !important; }

        /* Respect reduced-motion preferences */
        @media (prefers-reduced-motion: reduce) {
            .typing-dots span { animation: none; opacity: 0.7; }
            * { scroll-behavior: auto !important; transition: none !important; }
        }
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

app.layout = html.Div(
    style={"backgroundColor": BG, "fontFamily": SANS, "minHeight": "100vh", "color": TEXT_DARK},
    children=[
        html.A("Skip to main content", href="#main-content", className="skip-link"),

        # ── Header ──
        html.Header(style={"background": PRIMARY, "padding": "28px 40px", "color": "white"}, children=[
            html.H1("Blanche", style={"fontFamily": SERIF, "fontSize": "38px",
                     "fontWeight": "400", "margin": "0", "letterSpacing": "6px",
                     "textTransform": "uppercase"}),
            html.P("Lifestyle Magazine", style={"fontFamily": SANS, "fontSize": "12px",
                    "letterSpacing": "5px", "margin": "4px 0 0", "opacity": "0.85",
                    "textTransform": "uppercase"}),
            html.P("Yelp business overview", style={"fontFamily": SANS, "fontSize": "14px",
                    "margin": "14px 0 0", "opacity": "0.85"}),
        ]),

        html.Main(id="main-content", tabIndex="-1", style={"outline": "none"}, children=[

            # ── KPI Row ──
            html.Section(**{"aria-labelledby": "kpi-heading"}, children=[
                html.H2("Key figures", id="kpi-heading", className="sr-only"),
                html.Div(id="kpi-row", style={"display": "flex", "flexWrap": "wrap",
                                               "gap": "16px", "padding": "24px 40px 0"}),
            ]),

            # ── Highlights Row ──
            html.Section(style={"padding": "16px 40px 0"},
                         **{"aria-labelledby": "highlights-heading"}, children=[
                section_heading("Highlights", "highlights-heading"),
                html.Div(id="highlights-row", style={"display": "flex", "flexWrap": "wrap",
                                                      "gap": "16px"}),
            ]),

            # ── Main: Filters sidebar | Map + detail panel ──
            html.Div(style={"display": "flex", "flexWrap": "wrap", "gap": "20px",
                             "padding": "20px 40px", "alignItems": "flex-start"}, children=[
                # ── Filters sidebar ──
                html.Aside(style={"flex": "0 0 220px", "background": CARD,
                                   "border": f"1px solid {BORDER}", "borderRadius": "4px",
                                   "padding": "20px", "boxSizing": "border-box"},
                           **{"aria-labelledby": "filters-heading"}, children=[
                    section_heading("Filters", "filters-heading", extra_style={"margin": "0 0 16px"}),
                    filter_field("Business name", "filter-name",
                        dcc.Input(id="filter-name", type="text", placeholder="Search by name\u2026",
                                  debounce=True,
                                  style={"width": "100%", "boxSizing": "border-box",
                                          "padding": "8px 10px", "border": "1px solid #B9ADB5",
                                          "borderRadius": "2px", "fontSize": "14px",
                                          "fontFamily": SANS, "color": TEXT_DARK,
                                          "background": CARD})),
                    filter_field("Category", "filter-category",
                        dcc.Dropdown(id="filter-category",
                                     options=[{"label": c, "value": c} for c in CATEGORIES],
                                     multi=True, placeholder="All")),
                    filter_field("Subcategory", "filter-subcategory",
                        dcc.Dropdown(id="filter-subcategory",
                                     options=[{"label": s, "value": s} for s in SUBCATEGORIES],
                                     multi=True, placeholder="All")),
                    filter_field("City", "filter-city",
                        dcc.Dropdown(id="filter-city",
                                     options=[{"label": c, "value": c} for c in CITIES],
                                     multi=True, placeholder="All")),
                    filter_field("State", "filter-state",
                        dcc.Dropdown(id="filter-state",
                                     options=[{"label": s, "value": s} for s in STATES],
                                     multi=True, placeholder="All")),
                    filter_field("Minimum rating", "filter-rating",
                        dcc.Dropdown(id="filter-rating",
                                     options=[{"label": f"{r} stars or more", "value": r}
                                              for r in [1, 2, 2.5, 3, 3.5, 4, 4.5]],
                                     value=1, clearable=False)),
                    filter_field("Minimum reviews", "filter-min-reviews",
                        dcc.Dropdown(id="filter-min-reviews",
                                     options=[{"label": f"{r:,}+", "value": r}
                                              for r in [0, 10, 25, 50, 100, 250, 500, 1000, 2500]],
                                     value=0, clearable=False)),
                ]),

                # ── Map ──
                html.Section(style={"flex": "1 1 400px", "minWidth": "0"},
                             **{"aria-labelledby": "map-heading"}, children=[
                    section_heading("Business map", "map-heading", extra_style={"margin": "0 0 4px"}),
                    html.P("Points are colored by category and sized by number of reviews. "
                           "Pick a business below or click a point to see its details.",
                           style={"color": TEXT_MED, "fontSize": "13px", "margin": "0 0 10px",
                                  "fontFamily": SANS}),
                    # Keyboard- and screen-reader-friendly way to select a business,
                    # doing the same thing as clicking the map or a bar.
                    filter_field("Select a business", "business-picker",
                        dcc.Dropdown(id="business-picker", options=[], value=None,
                                     searchable=True, clearable=True,
                                     placeholder="Type to search businesses\u2026")),
                    html.Div(role="img",
                             **{"aria-label": "Map of businesses matching the current filters. "
                                              "Use the Select a business field to choose one."},
                             children=[
                        dcc.Graph(id="map-graph", style={"height": "480px", "borderRadius": "4px",
                                  "overflow": "hidden", "border": f"1px solid {BORDER}"},
                                  config={"displayModeBar": False}),
                    ]),
                ]),

                # ── Selected-business panel (announced when it changes) ──
                # Always in the layout (hidden when nothing is selected) so the
                # close button has a fixed id and the width is set on the flex item itself.
                html.Section(id="detail-panel", style=DETAIL_PANEL_HIDDEN,
                             **{"aria-labelledby": "selected-heading"}, children=[
                    html.Div(style={"display": "flex", "justifyContent": "space-between",
                                     "alignItems": "center", "margin": "0 0 12px"}, children=[
                        section_heading("Selected business", "selected-heading",
                                        extra_style={"margin": "0"}),
                        html.Button([html.Span("\u00d7", **{"aria-hidden": "true"})],
                                    id="clear-selection", n_clicks=0, type="button",
                                    title="Close",
                                    **{"aria-label": "Close and clear selected business"},
                                    style={"background": "transparent", "border": "none",
                                           "color": TEXT_MED, "fontSize": "22px",
                                           "lineHeight": "1", "cursor": "pointer",
                                           "padding": "4px 8px", "minWidth": "32px",
                                           "minHeight": "32px", "fontFamily": SANS,
                                           "flexShrink": "0"}),
                    ]),
                    html.Div(id="click-detail", **{"aria-live": "polite"}),
                ]),
            ]),

            # ── Genie Chat Section ──
            html.Section(style={"padding": "0 40px 20px"},
                         **{"aria-labelledby": "genie-heading"}, children=[
                section_heading("Ask Genie", "genie-heading"),
                # Announces "thinking" and each answer to screen readers
                html.Div(id="genie-status", className="sr-only", role="status",
                         **{"aria-live": "polite"}),
                html.Div(style={"background": CARD, "border": f"1px solid {BORDER}",
                                 "borderRadius": "4px", "overflow": "hidden"}, children=[
                    # Messages area (focusable so keyboard users can scroll it)
                    html.Div(id="genie-messages", tabIndex="0", role="region",
                             **{"aria-label": "Genie conversation"}, style={
                        "padding": "24px", "minHeight": "160px", "maxHeight": "360px",
                        "overflowY": "auto", "background": HIGHLIGHT_BG,
                    }, children=[
                        html.Div(id="genie-welcome", style={"textAlign": "center", "padding": "32px 20px"}, children=[
                            html.Div("\u2728", style={"fontSize": "32px", "marginBottom": "12px"},
                                     **{"aria-hidden": "true"}),
                            html.P("Databricks Genie", style={"color": TEXT_DARK, "fontWeight": "600",
                                    "fontSize": "16px", "margin": "0 0 8px", "fontFamily": SANS}),
                            html.P("Ask questions about the Yelp business data in plain language.",
                                   style={"color": TEXT_MED, "fontSize": "14px", "margin": "0",
                                          "fontFamily": SANS, "maxWidth": "420px",
                                          "marginLeft": "auto", "marginRight": "auto"}),
                        ]),
                        html.Div(id="genie-thread"),
                        html.Div(id="genie-pending-view"),
                    ]),
                    # Input area
                    html.Div(style={"display": "flex", "padding": "12px 16px", "gap": "10px",
                                     "borderTop": f"1px solid {BORDER}", "alignItems": "center"}, children=[
                        html.Label("Ask Genie a question", htmlFor="genie-input", className="sr-only"),
                        dcc.Input(id="genie-input", type="text",
                                  placeholder="Ask a question about this data\u2026",
                                  style={"flex": "1", "padding": "10px 14px",
                                          "border": "1px solid #B9ADB5", "borderRadius": "4px",
                                          "fontSize": "14px", "fontFamily": SANS,
                                          "color": TEXT_DARK, "background": CARD},
                                  debounce=True),
                        html.Button([html.Span("\u2192", **{"aria-hidden": "true"})],
                                    id="genie-send", n_clicks=0,
                                    **{"aria-label": "Send question"},
                                    style={"background": PRIMARY, "color": "white", "border": "none",
                                            "borderRadius": "4px", "padding": "10px 16px",
                                            "fontSize": "16px", "cursor": "pointer",
                                            "fontWeight": "600"}),
                    ]),
                ]),
            ]),

            dcc.Store(id="chart-selection", data=None),
            dcc.Store(id="genie-conv-id", data=None),
            dcc.Store(id="genie-history", data=[]),
            dcc.Store(id="genie-pending", data=None),
            dcc.Store(id="genie-scroll-dummy"),
            dcc.Store(id="detail-focus-dummy"),

            # ── Business Charts ──
            html.Section(style={"padding": "0 40px 20px"},
                         **{"aria-labelledby": "charts-heading"}, children=[
                section_heading("Business charts", "charts-heading", extra_style={"margin": "0 0 12px"}),
                html.Div(style={"display": "flex", "flexWrap": "wrap", "gap": "16px"}, children=[
                    chart_card("Top 10 highest rated", "rated-heading", "chart-rated", "table-rated",
                               "Bar chart of the 10 highest rated businesses. "
                               "Open View as table below for the data."),
                    chart_card("Top 10 most visited", "visited-heading", "chart-visited", "table-visited",
                               "Bar chart of the 10 businesses with the most visits. "
                               "Open View as table below for the data."),
                    chart_card("Top 10 most reviewed", "reviewed-heading", "chart-reviewed", "table-reviewed",
                               "Bar chart of the 10 businesses with the most reviews. "
                               "Open View as table below for the data."),
                ]),
            ]),

            # ── Reviews & Tips ──
            html.Section(style={"padding": "0 40px 40px"},
                         **{"aria-labelledby": "reviews-heading"}, children=[
                html.Div(style={"display": "flex", "justifyContent": "space-between",
                                 "alignItems": "center", "marginBottom": "12px",
                                 "flexWrap": "wrap", "gap": "8px"}, children=[
                    section_heading("Reviews & tips", "reviews-heading", extra_style={"margin": "0"}),
                    html.P(id="reviews-count", style={"color": TEXT_MED, "fontSize": "13px",
                            "margin": "0", "fontFamily": SANS}),
                ]),
                html.Div(id="reviews-container"),
            ]),
        ]),
    ],
)


# ── Callback: filters + selection -> KPIs, map, highlights, reviews ──
@app.callback(
    Output("kpi-row", "children"),
    Output("map-graph", "figure"),
    Output("highlights-row", "children"),
    Output("reviews-container", "children"),
    Output("reviews-count", "children"),
    Input("filter-name", "value"),
    Input("filter-category", "value"),
    Input("filter-subcategory", "value"),
    Input("filter-city", "value"),
    Input("filter-state", "value"),
    Input("filter-rating", "value"),
    Input("filter-min-reviews", "value"),
    Input("chart-selection", "data"),
)
def update_dashboard(name_query, categories, subcategories, cities, states, min_rating, min_reviews, selection):
    filtered = apply_filters(name_query, categories, subcategories, cities, states, min_rating, min_reviews)

    n = len(filtered)
    avg_r = filtered["rating"].mean() if n else 0
    tot_rev = int(filtered["review_count"].sum())
    tot_chk = int(filtered["checkin_count"].sum())

    kpis = [
        kpi_card("Total businesses", f"{n:,}", f"across {filtered['city'].nunique()} cities"),
        kpi_card("Average rating", rating_children(avg_r) if n else "N/A",
                 f"{filtered['category'].nunique()} categories"),
        kpi_card("Total reviews", f"{tot_rev:,}", f"{tot_rev // max(n, 1)} average per business"),
        kpi_card("Total visits", f"{tot_chk:,}", f"{tot_chk // max(n, 1)} average per business"),
    ]

    map_df = filtered.dropna(subset=["latitude", "longitude"]).copy()
    if len(map_df) > 0:
        map_df["_size"] = np.sqrt(map_df["review_count"].fillna(0).clip(lower=1)) + 2
        fig = px.scatter_map(
            map_df, lat="latitude", lon="longitude",
            color="category", color_discrete_map=CAT_COLORS,
            size="_size", size_max=14, zoom=9,
            map_style=MAP_STYLE,
            custom_data=["business_id", "business_name", "category", "city", "state", "address",
                         "postal_code", "rating", "review_count", "checkin_count",
                         "subcategories"],
        )
        fig.update_traces(
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>"
                "%{customdata[2]} \u2013 %{customdata[10]}<br>"
                "%{customdata[3]}, %{customdata[4]}<br>"
                "\u2605 %{customdata[7]:.1f} \u00b7 %{customdata[8]:,} reviews"
                "<extra></extra>"
            ),
        )
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor=CARD,
            # Legend is now shown so category colors can be decoded without hovering.
            showlegend=True,
            legend=dict(title=dict(text="Category", font=dict(size=12, color=TEXT_DARK)),
                        bgcolor="rgba(255,255,255,0.92)", bordercolor=BORDER, borderwidth=1,
                        font=dict(size=12, color=TEXT_DARK, family="Inter"),
                        x=0.01, y=0.99, xanchor="left", yanchor="top", itemsizing="constant"),
            hoverlabel=dict(bgcolor=CARD, bordercolor=BORDER,
                             font=dict(color=TEXT_DARK, size=13, family="Inter")),
            map_center=dict(lat=map_df["latitude"].mean(),
                             lon=map_df["longitude"].mean()),
        )
    else:
        fig = px.scatter_map(
            pd.DataFrame({"lat": [39.5], "lon": [-98.35]}),
            lat="lat", lon="lon", zoom=3, map_style=MAP_STYLE)
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor=CARD, showlegend=False)

    # ── Highlight selected business on map ──
    if selection and len(map_df) > 0:
        sel_df = map_df[map_df["business_id"] == selection]
        if len(sel_df) > 0:
            fig.update_traces(marker_opacity=0.3)
            sel_pt = sel_df.iloc[0]
            pin = px.scatter_map(
                sel_df.head(1), lat="latitude", lon="longitude", map_style=MAP_STYLE
            )
            r_str = f"{sel_pt['rating']:.1f}" if pd.notna(sel_pt["rating"]) else "N/A"
            pin.update_traces(
                marker=dict(size=18, color=PRIMARY, opacity=1),
                showlegend=False,
                customdata=[[selection]],
                hovertemplate=f"<b>{sel_pt['business_name']}</b><br>\u2605 {r_str}<extra></extra>",
            )
            fig.add_trace(pin.data[0])
            fig.update_layout(
                map_center=dict(lat=float(sel_pt["latitude"]),
                                lon=float(sel_pt["longitude"])),
                map_zoom=13,
            )

    highlights = []
    if n > 0:
        top = filtered.sort_values(["rating", "review_count"], ascending=[False, False]).iloc[0]
        most_rev = filtered.nlargest(1, "review_count").iloc[0]
        most_act = filtered.nlargest(1, "checkin_count").iloc[0]
        highlights = [
            highlight_card("Top rated", str(top["business_name"]),
                           rating_children(top["rating"]) + [f" \u00b7 {top['category']}"]),
            highlight_card("Most reviewed", str(most_rev["business_name"]),
                           f"{most_rev['review_count']:,} reviews \u00b7 {most_rev['city']}"),
            highlight_card("Most visited", str(most_act["business_name"]),
                           f"{most_act['checkin_count']:,} visits \u00b7 {most_act['city']}"),
        ]

    # ── Review cards: live query filtered to the current business set ──
    filtered_ids = list(filtered["business_id"])
    selected_ids = [selection] if selection and selection in set(filtered_ids) else filtered_ids
    if selected_ids:
        id_literals = ", ".join(f"'{bid}'" for bid in selected_ids)
        rev_df = run_query(f"""
            SELECT r.text_id, r.business_id, r.type, r.posted_at, r.full_text,
                   b.business_name, b.category, b.city, b.state, b.rating, b.review_count
            FROM genieology.gold.reviews_and_tips r
            JOIN genieology.gold.business b ON r.business_id = b.business_id
            WHERE r.business_id IN ({id_literals})
            ORDER BY r.posted_at DESC
            LIMIT 50
        """)
        rev_df["posted_at"] = pd.to_datetime(rev_df["posted_at"], errors="coerce")
        rev_df["rating"] = pd.to_numeric(rev_df["rating"], errors="coerce")
        rev_df["review_count"] = pd.to_numeric(rev_df["review_count"], errors="coerce").fillna(0).astype(int)
    else:
        rev_df = pd.DataFrame()

    cards = [review_card(row) for _, row in rev_df.iterrows()] if len(rev_df) > 0 else [
        html.P("No reviews match the current filters. Try removing a filter.",
               style={"color": TEXT_MED, "fontSize": "14px", "fontFamily": SANS,
                      "textAlign": "center", "padding": "40px 0"}),
    ]
    count_text = f"Showing {len(rev_df)} reviews"

    return kpis, fig, highlights, cards, count_text


# ── Callback: selection -> side detail panel (contents + show/hide) ──
@app.callback(
    Output("click-detail", "children"),
    Output("detail-panel", "style"),
    Input("chart-selection", "data"),
)
def show_click_detail(selection):
    if not selection:
        return None, DETAIL_PANEL_HIDDEN
    sel_df = df[df["business_id"] == selection]
    if len(sel_df) == 0:
        return None, DETAIL_PANEL_HIDDEN

    row = sel_df.iloc[0]
    safe_addr = str(row["address"]) if pd.notna(row["address"]) and row["address"] else ""
    safe_postal = str(row["postal_code"]) if pd.notna(row["postal_code"]) and row["postal_code"] else ""
    safe_subcats = str(row["subcategories"]) if pd.notna(row["subcategories"]) and row["subcategories"] else "N/A"

    def fmt_num(v):
        try:
            return f"{int(float(v)):,}"
        except (ValueError, TypeError):
            return str(v)

    def detail_row(label, value):
        return html.Div(style={"marginBottom": "14px"}, children=[
            html.Dt(label, style={"color": TEXT_LIGHT, "fontSize": "12px", "fontWeight": "600",
                    "textTransform": "uppercase", "letterSpacing": "1px", "margin": "0 0 4px",
                    "fontFamily": SANS}),
            html.Dd(value, style={"color": TEXT_DARK, "fontSize": "14px",
                    "fontWeight": "600", "margin": "0", "fontFamily": SANS}),
        ])

    contents = [
        html.H3(str(row["business_name"]), style={"color": TEXT_DARK, "margin": "0 0 4px",
                 "fontSize": "17px", "fontWeight": "700", "fontFamily": SANS,
                 "lineHeight": "1.3"}),
        html.P(rating_children(row["rating"]), style={"color": ACCENT, "fontSize": "18px",
                "fontWeight": "700", "margin": "0 0 4px", "fontFamily": SANS}),
        html.P(f"{safe_addr}, {row['city']}, {row['state']} {safe_postal}",
               style={"color": TEXT_MED, "fontSize": "13px", "margin": "0 0 16px",
                      "fontFamily": SANS, "lineHeight": "1.4"}),
        html.Hr(style={"border": "none", "borderTop": f"1px solid {BORDER}", "margin": "0 0 16px"}),
        html.Dl(style={"margin": "0"}, children=[
            detail_row("Category", str(row["category"])),
            detail_row("Subcategories", safe_subcats),
            detail_row("Reviews", fmt_num(row["review_count"])),
            detail_row("Visits", fmt_num(row["checkin_count"])),
        ]),
    ]
    return contents, DETAIL_PANEL_STYLE


# ── Callback: business picker options (search-as-you-type, respects filters) ──
@app.callback(
    Output("business-picker", "options"),
    Input("business-picker", "search_value"),
    Input("filter-name", "value"),
    Input("filter-category", "value"),
    Input("filter-subcategory", "value"),
    Input("filter-city", "value"),
    Input("filter-state", "value"),
    Input("filter-rating", "value"),
    Input("filter-min-reviews", "value"),
    State("business-picker", "value"),
)
def update_picker_options(search, name_query, categories, subcategories, cities, states,
                          min_rating, min_reviews, current):
    filtered = apply_filters(name_query, categories, subcategories, cities, states,
                             min_rating, min_reviews)
    if search:
        filtered = filtered[filtered["business_name"].str.contains(
            search, case=False, na=False, regex=False)]
    # Cap the list so large datasets stay fast; typing narrows it further.
    top = filtered.nlargest(50, "review_count")
    if current and current not in set(top["business_id"]):
        top = pd.concat([df[df["business_id"] == current], top])
    return [{"label": f"{r['business_name']} ({r['city']}, {r['state']})",
             "value": r["business_id"]} for _, r in top.iterrows()]


# ── Callback: Genie chat, step 1 (instant, runs in the browser) ──
# The input is set to read-only rather than disabled while Genie is thinking,
# so keyboard focus stays in it. Extra sends are ignored until the answer lands.
GENIE_SEND_JS = """
function(n_clicks, n_submit, question) {
    const nu = window.dash_clientside.no_update;
    var inputEl = document.getElementById('genie-input');
    if (inputEl && inputEl.readOnly) { return [nu, nu, nu, nu, nu, nu]; }
    var q = (inputEl ? inputEl.value : (question || '')).trim();
    if (!q) { return [nu, nu, nu, nu, nu, nu]; }
    const el = (type, props) => ({type: type, namespace: 'dash_html_components', props: props});

    const userBubble = el('Div', {
        style: {display: 'flex', justifyContent: 'flex-end', marginBottom: '12px'},
        children: el('Div', {children: q, style: {
            background: '__PRIMARY__', color: 'white', padding: '10px 16px',
            borderRadius: '12px 12px 2px 12px', maxWidth: '70%',
            fontSize: '14px', fontFamily: "__SANS__"}})
    });
    const thinking = el('Div', {
        style: {display: 'flex', justifyContent: 'flex-start', marginBottom: '12px'},
        children: el('Div', {
            style: {background: '__CARD__', border: '1px solid __BORDER__',
                    padding: '14px 18px', borderRadius: '12px 12px 12px 2px'},
            children: [
                el('P', {children: 'Genie', style: {color: '__ACCENT__', fontWeight: '600',
                    fontSize: '12px', margin: '0 0 8px', textTransform: 'uppercase',
                    letterSpacing: '1px'}}),
                el('Div', {className: 'typing-dots', 'aria-hidden': 'true',
                           children: [el('Span', {}), el('Span', {}), el('Span', {})]})
            ]
        })
    });

    return [
        [userBubble, thinking],           // genie-pending-view
        '',                               // clear the input
        {question: q, ts: Date.now()},    // hand off to step 2
        true,                             // input read-only while waiting
        {display: 'none'},                // hide the welcome message
        'Question sent. Genie is working on an answer.'   // screen reader status
    ];
}
"""
for key, val in {"__PRIMARY__": PRIMARY, "__CARD__": CARD, "__BORDER__": BORDER,
                 "__ACCENT__": ACCENT, "__SANS__": SANS}.items():
    GENIE_SEND_JS = GENIE_SEND_JS.replace(key, val)

app.clientside_callback(
    GENIE_SEND_JS,
    Output("genie-pending-view", "children"),
    Output("genie-input", "value"),
    Output("genie-pending", "data"),
    Output("genie-input", "readOnly"),
    Output("genie-welcome", "style"),
    Output("genie-status", "children"),
    Input("genie-send", "n_clicks"),
    Input("genie-input", "n_submit"),
    State("genie-input", "value"),
    prevent_initial_call=True,
)


# ── Callback: Genie chat, step 2 (server) ──
@app.callback(
    Output("genie-thread", "children"),
    Output("genie-history", "data"),
    Output("genie-conv-id", "data"),
    Output("genie-pending-view", "children", allow_duplicate=True),
    Output("genie-input", "readOnly", allow_duplicate=True),
    Output("genie-status", "children", allow_duplicate=True),
    Input("genie-pending", "data"),
    State("genie-conv-id", "data"),
    State("genie-history", "data"),
    prevent_initial_call=True,
)
def fetch_genie_answer(pending, conv_id, history):
    if not pending or not pending.get("question"):
        return (no_update,) * 6

    question = pending["question"]
    new_conv_id, answer_text, sql, rows, cols = ask_genie(question, conv_id)

    history = list(history or [])
    history.append({"role": "user", "text": question})
    history.append({
        "role": "genie",
        "text": answer_text,
        "sql": sql,
        "rows": rows,
        "cols": cols,
    })

    status = f"Genie answered: {strip_bold(answer_text)}"
    if rows and cols:
        status += f" A results table with {len(rows)} rows follows."

    return _render_history(history), history, new_conv_id, None, False, status


# ── Clientside: keep the chat scrolled to the newest message ──
app.clientside_callback(
    """
    function(thread, pending) {
        setTimeout(function () {
            var el = document.getElementById('genie-messages');
            if (el) { el.scrollTop = el.scrollHeight; }
        }, 50);
        return window.dash_clientside.no_update;
    }
    """,
    Output("genie-scroll-dummy", "data"),
    Input("genie-thread", "children"),
    Input("genie-pending-view", "children"),
    prevent_initial_call=True,
)


# ── Callback: filters + selection -> 3 bar charts and their table versions ──
@app.callback(
    Output("chart-rated", "figure"),
    Output("chart-visited", "figure"),
    Output("chart-reviewed", "figure"),
    Output("table-rated", "children"),
    Output("table-visited", "children"),
    Output("table-reviewed", "children"),
    Input("filter-name", "value"),
    Input("filter-category", "value"),
    Input("filter-subcategory", "value"),
    Input("filter-city", "value"),
    Input("filter-state", "value"),
    Input("filter-rating", "value"),
    Input("filter-min-reviews", "value"),
    Input("chart-selection", "data"),
)
def update_charts(name_query, categories, subcategories, cities, states,
                  min_rating, min_reviews, selection):
    filtered = apply_filters(name_query, categories, subcategories,
                             cities, states, min_rating, min_reviews)
    sel = selection if selection else None

    top_rated = (filtered
                 .sort_values(["rating", "review_count"], ascending=[False, False])
                 .head(10)
                 .sort_values("rating", ascending=True))
    top_visited = filtered.nlargest(10, "checkin_count").sort_values("checkin_count", ascending=True)
    top_reviewed = filtered.nlargest(10, "review_count").sort_values("review_count", ascending=True)

    hover_fmt = (
        "<b>%{customdata[1]}</b><br>"
        "Average rating: %{customdata[2]:.1f}<br>"
        "Reviews: %{customdata[3]:,}<br>"
        "Visits: %{customdata[4]:,}<extra></extra>"
    )

    return (
        build_bar_chart(top_rated, "rating", hover_fmt, sel),
        build_bar_chart(top_visited, "checkin_count", hover_fmt, sel),
        build_bar_chart(top_reviewed, "review_count", hover_fmt, sel),
        chart_data_table(top_rated, "rating", "Rating", "Top 10 highest rated businesses"),
        chart_data_table(top_visited, "checkin_count", "Visits", "Top 10 most visited businesses"),
        chart_data_table(top_reviewed, "review_count", "Reviews", "Top 10 most reviewed businesses"),
    )


# ── Callback: chart/map click, business picker, close button, or filter change
#    -> cross-filter store (and keep the picker in sync) ──
# Closing the panel or changing a filter also resets every chart's and the map's
# clickData. Without that, a graph keeps its last click, so clicking the same
# business again after closing wouldn't register as a new selection.
@app.callback(
    Output("chart-selection", "data"),
    Output("business-picker", "value"),
    Output("chart-rated", "clickData"),
    Output("chart-visited", "clickData"),
    Output("chart-reviewed", "clickData"),
    Output("map-graph", "clickData"),
    Input("chart-rated", "clickData"),
    Input("chart-visited", "clickData"),
    Input("chart-reviewed", "clickData"),
    Input("map-graph", "clickData"),
    Input("business-picker", "value"),
    Input("clear-selection", "n_clicks"),
    Input("filter-name", "value"),
    Input("filter-category", "value"),
    Input("filter-subcategory", "value"),
    Input("filter-city", "value"),
    Input("filter-state", "value"),
    Input("filter-rating", "value"),
    Input("filter-min-reviews", "value"),
    prevent_initial_call=True,
)
def handle_selection(click_rated, click_visited, click_reviewed, map_click, picked, clear_clicks,
                     name_query, categories, subcategories, cities, states, min_rating, min_reviews):
    triggered = dash.ctx.triggered_id
    nu = no_update
    clear_all = (None, None, None, None, None, None)

    filter_ids = {
        "filter-name", "filter-category", "filter-subcategory", "filter-city",
        "filter-state", "filter-rating", "filter-min-reviews",
    }
    if triggered in filter_ids or triggered == "clear-selection":
        return clear_all

    if triggered == "business-picker":
        return picked, nu, nu, nu, nu, nu

    click_map = {
        "chart-rated": click_rated,
        "chart-visited": click_visited,
        "chart-reviewed": click_reviewed,
        "map-graph": map_click,
    }
    click_data = click_map.get(triggered)
    if not click_data or not click_data.get("points"):
        # clickData was just reset to None by this callback; nothing to select.
        return nu, nu, nu, nu, nu, nu
    cd = click_data["points"][0].get("customdata", [])
    if not cd:
        return nu, nu, nu, nu, nu, nu
    return cd[0], cd[0], nu, nu, nu, nu


# ── Clientside: after closing the panel, move keyboard focus somewhere sensible
#    (the business picker) instead of losing it when the panel disappears ──
app.clientside_callback(
    """
    function(n) {
        if (n) {
            setTimeout(function () {
                var el = document.querySelector('#business-picker input');
                if (el) { el.focus(); }
            }, 50);
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("detail-focus-dummy", "data"),
    Input("clear-selection", "n_clicks"),
    prevent_initial_call=True,
)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)