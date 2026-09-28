# Blanche Lifestyle Magazine: Yelp business dashboard
#
# A Dash app that loads Yelp business data from a Databricks SQL warehouse and
# shows it as KPI cards, a map, top-10 bar charts and a feed of reviews and tips.
# Everything on the page follows the same sidebar filters. Selecting a business
# (by clicking the map or a bar, or through the picker dropdown) narrows the
# page to that business and opens a detail panel. The "Ask Genie" panel sends
# plain-language questions to a Databricks Genie space.
#
# Configuration: DATABRICKS_WAREHOUSE_ID (optional). Databricks credentials are
# picked up by WorkspaceClient from the environment or Databricks config.

import os
import re
import dash
from dash import dcc, html, Input, Output, State, no_update
import plotly.express as px
import pandas as pd
import numpy as np
import time
from databricks.sdk import WorkspaceClient

# ── Databricks connection ──
# SQL warehouse used for every query. Falls back to a default ID if the
# environment variable isn't set.
WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "401941d60f2786b9")
w = WorkspaceClient()


# ── Theme: warm cream and mauve ──
# Every text color meets WCAG AA contrast (4.5:1) against white, the cream page
# background (BG) and HIGHLIGHT_BG.
BG = "#F7F3EF"           # page background
CARD = "#FFFFFF"         # cards and panels
BORDER = "#DCD4D9"       # card borders and dividers
PRIMARY = "#5B4A5E"      # header, buttons, selected items
TEXT_DARK = "#2D1F30"    # headings and main text
TEXT_MED = "#6B5B6E"     # body text
TEXT_LIGHT = "#736676"   # labels and secondary text
ACCENT = "#80606D"       # ratings, highlights, disclosure arrows
HIGHLIGHT_BG = "#F0EAE6" # chat background and code blocks

MAP_STYLE = "carto-positron"  # light, low-detail basemap

# One color per category on the map. Muted to suit the theme but clearly
# different in hue, so categories can be told apart without hovering. Each has
# at least 3:1 contrast against the basemap. Colors repeat after 15 categories.
CATEGORY_PALETTE = [
    "#5B4A5E", "#B5673F", "#3F7A74", "#A07F2A", "#6B7F3A",
    "#4A6A8F", "#A04F63", "#8C6440", "#5F87A6", "#8F6BA0",
    "#4F7050", "#B0706F", "#2F5560", "#9A5E88", "#7A7A52",
]

# Font stacks. Inter and DM Serif Display are loaded from Google Fonts in
# app.index_string below.
SANS = "'Inter', -apple-system, sans-serif"
SERIF = "'DM Serif Display', serif"

# ── Shared styles ──
# The smallest text anywhere in the app is 12px.
SECTION_HEADING_STYLE = {
    "color": TEXT_LIGHT, "fontSize": "12px", "fontWeight": "600",
    "letterSpacing": "1.5px", "textTransform": "uppercase",
    "margin": "0 0 8px", "fontFamily": SANS,
}
# Selected-business panel. The width is fixed so a long name or subcategory
# list wraps inside the panel instead of stretching it.
DETAIL_PANEL_WIDTH = "280px"
DETAIL_PANEL_STYLE = {
    "flex": f"0 0 {DETAIL_PANEL_WIDTH}", "width": DETAIL_PANEL_WIDTH,
    "maxWidth": "100%", "boxSizing": "border-box",
    "background": CARD, "border": f"1px solid {BORDER}", "borderRadius": "4px",
    "padding": "20px", "overflowWrap": "anywhere", "wordBreak": "break-word",
}
# Same panel, hidden. Used when no business is selected.
DETAIL_PANEL_HIDDEN = dict(DETAIL_PANEL_STYLE, display="none")

# Label above each sidebar filter.
FIELD_LABEL_STYLE = {
    "color": TEXT_MED, "fontSize": "12px", "fontWeight": "500", "display": "block",
    "marginBottom": "4px", "textTransform": "uppercase", "letterSpacing": "0.5px",
    "fontFamily": SANS,
}


# ── Data loading ──

def run_query(sql_text: str) -> pd.DataFrame:
    """Run a SQL statement on the warehouse and return the rows as a DataFrame.

    Waits up to 50 seconds for results. Raises RuntimeError if the query fails
    or returns no schema. Values come back as strings, so callers convert
    numeric columns themselves.
    """
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


# Load every business once at startup. All filtering after this happens in
# pandas; only reviews are queried live.
print("Loading business data ...")
df = run_query("""
    SELECT business_id, business_name, category, subcategories,
           city, state, address, postal_code,
           latitude, longitude, review_count, rating, checkin_count
    FROM genieology.gold.business
""")
print(f"Loaded {len(df):,} businesses")

# Convert numeric columns from strings. Missing coordinates and ratings stay
# NaN; missing counts become 0.
for c in ["latitude", "longitude", "rating"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
for c in ["review_count", "checkin_count"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

# Options for the filter dropdowns, plus a fixed category-to-color mapping so
# each category keeps the same map color whatever the filters are.
CATEGORIES = sorted(df["category"].dropna().unique())
CITIES = sorted(df["city"].dropna().unique())
STATES = sorted(df["state"].dropna().unique())
CAT_COLORS = {cat: CATEGORY_PALETTE[i % len(CATEGORY_PALETTE)] for i, cat in enumerate(CATEGORIES)}


def parse_subcategories(series: pd.Series) -> list:
    """Return every distinct subcategory, sorted.

    Each row stores its subcategories as one comma-separated string, so this
    splits them apart. Used to build the Subcategory filter options.
    """
    values = set()
    for v in series.dropna():
        for piece in str(v).split(","):
            piece = piece.strip()
            if piece:
                values.add(piece)
    return sorted(values)


def row_has_subcategory(value, wanted: set) -> bool:
    """True if a row's comma-separated subcategories include any in `wanted`."""
    if pd.isna(value) or not value:
        return False
    items = {s.strip() for s in str(value).split(",")}
    return bool(items & wanted)


SUBCATEGORIES = parse_subcategories(df["subcategories"])


# ── Genie ──

GENIE_SPACE_ID = "01f1b8f39ea115aabb24013a946478b9"


def _poll_genie_message(conv_id: str, msg_id: str, timeout: int = 120):
    """Check the message every 2 seconds until it completes, fails or is
    cancelled. After `timeout` seconds, return it in whatever state it's in."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = w.genie.get_message(GENIE_SPACE_ID, conv_id, msg_id)
        status = str(getattr(msg, "status", "")).upper()
        if any(s in status for s in ("COMPLETED", "FAILED", "CANCELLED")):
            return msg
        time.sleep(2)
    return msg


def ask_genie(question: str, conv_id: str | None = None):
    """Ask Genie a question and return its answer.

    Continues conversation `conv_id` if given, so follow-up questions keep
    context; otherwise starts a new conversation.

    Returns (conv_id, answer_text, sql, result_rows, result_cols). result_rows
    is capped at 50. This never raises: errors are returned as the answer text
    so they appear in the chat.
    """
    try:
        if conv_id:
            resp = w.genie.create_message(GENIE_SPACE_ID, conv_id, question)
        else:
            resp = w.genie.start_conversation(GENIE_SPACE_ID, question)

        # Depending on the SDK version, the call returns either a Wait object
        # or the message itself. Unwrap the Wait object.
        if hasattr(resp, "bind"):
            resp = resp.result()

        # The IDs live under different attribute names in different SDK versions.
        cid = getattr(resp, "conversation_id", None) or conv_id
        mid = getattr(resp, "message_id", None) or getattr(resp, "id", None)

        # Wait for Genie to finish before reading the answer.
        if mid and cid:
            msg = _poll_genie_message(cid, mid)
        else:
            msg = resp

        # An answer can have a text attachment, a query attachment (the SQL
        # Genie generated), or both.
        answer_text = ""
        sql = ""
        attachments = getattr(msg, "attachments", None) or []
        for att in attachments:
            if hasattr(att, "text") and att.text:
                answer_text += str(getattr(att.text, "content", att.text)) + "\n"
            if hasattr(att, "query") and att.query:
                q = att.query
                sql = getattr(q, "query", "") or getattr(q, "sql", "") or ""

        # If Genie ran a query, fetch its result rows for the results table.
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
                pass  # The table is optional; the text answer still shows if this fails.

        # Fall back to a generic message if Genie returned no text.
        answer_text = answer_text.strip() or ("Here are the results:" if result_rows else "I couldn't find an answer.")
        return cid, answer_text, sql.strip(), result_rows, result_cols

    except Exception as e:
        return conv_id, f"Sorry, something went wrong: {e}", "", [], []


# ── Accessibility helpers ──

def sr_only(text):
    """Text that screen readers announce but that isn't shown on screen.
    Styled by the .sr-only class in app.index_string."""
    return html.Span(text, className="sr-only")


def rating_children(value):
    """Show a rating as '4.5 ★' on screen, while screen readers hear
    'Rated 4.5 out of 5' instead of 'four point five black star'.

    Returns a list of children to put inside another element, or
    ['No rating'] if the value isn't a number.
    """
    try:
        r = f"{float(value):.1f}"
    except (ValueError, TypeError):
        return ["No rating"]
    return [html.Span(f"{r} ", **{"aria-hidden": "true"}),
            html.Span("\u2605", **{"aria-hidden": "true"}),
            sr_only(f"Rated {r} out of 5")]


def section_heading(text, id_=None, level=2, extra_style=None):
    """An h2 (or h3 with level=3) in the section heading style. Give it an
    id_ so its section can point to it with aria-labelledby."""
    style = dict(SECTION_HEADING_STYLE, **(extra_style or {}))
    tag = html.H2 if level == 2 else html.H3
    return tag(text, id=id_, style=style) if id_ else tag(text, style=style)


def filter_field(label, control_id, control):
    """A filter control with a visible label above it.

    htmlFor links the label to plain text inputs. Dash dropdowns don't expose
    the id of their inner input, so the wrapper also gets role=group and
    aria-labelledby, which names the dropdown for screen readers.
    """
    label_id = f"{control_id}-label"
    return html.Div(
        role="group", style={"marginBottom": "14px"},
        **{"aria-labelledby": label_id},
        children=[html.Label(label, id=label_id, htmlFor=control_id, style=FIELD_LABEL_STYLE),
                  control],
    )


def data_table(cols, rows, caption, max_rows=None):
    """A proper HTML table with a screen-reader caption and column headers
    marked scope=col. Pass max_rows to show only the first N rows."""
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


# ── Chat rendering ──

# Matches **bold** markdown in Genie's answers.
BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)


def render_bold(text: str):
    """Render **text** as bold and keep everything else as plain strings.

    Genie's text is never parsed as HTML, so it can't inject markup.
    """
    # With one capture group, re.split returns plain and bold pieces in turn:
    # plain at even indexes, bold at odd ones.
    parts = BOLD_RE.split(text)
    return [html.Strong(part, style={"color": TEXT_DARK, "fontWeight": "700"}) if i % 2 else part
            for i, part in enumerate(parts) if part]


def strip_bold(text: str) -> str:
    """Remove the ** markers, e.g. for the plain-text screen-reader announcement."""
    return BOLD_RE.sub(r"\1", text)


def _render_user_bubble(text: str):
    """Right-aligned chat bubble for a question the user asked."""
    return html.Div(style={"display": "flex", "justifyContent": "flex-end",
                            "marginBottom": "12px"}, children=[
        html.Div([sr_only("You asked: "), text], style={
            "background": PRIMARY, "color": "white", "padding": "10px 16px",
            "borderRadius": "12px 12px 2px 12px", "maxWidth": "70%",
            "fontSize": "14px", "fontFamily": SANS,
        }),
    ])


def _render_genie_bubble(msg: dict):
    """Left-aligned chat bubble for a Genie answer, built from a history entry.

    Shows the answer text, the generated SQL in a collapsed section, and the
    query results as a table (first 25 rows), each only when present.
    """
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
        # The SQL block scrolls sideways, so tabIndex makes it reachable by keyboard.
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
        # Show at most 25 rows, with a note when there are more.
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
    """Render the whole chat history as bubbles, oldest first."""
    return [
        _render_user_bubble(e["text"]) if e["role"] == "user" else _render_genie_bubble(e)
        for e in history
    ]


# ── Cards ──

def kpi_card(label, value, subtitle=""):
    """Summary card with a small label, a large value and an optional subtitle."""
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
    """Card naming one standout business. A long name is cut off with an
    ellipsis; the full name shows as a tooltip."""
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
    """Expandable card for one review or tip.

    Collapsed, it shows the business name, a Review/Tip badge, the rating, the
    first 160 characters and the date. Expanded, it adds the full text, the
    city and the category.
    """
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
        # Collapsed view
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
        # Expanded view
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


# ── Filtering and charts ──

def apply_filters(name_query, categories, subcategories, cities, states, min_rating, min_reviews):
    """Return the businesses that match the sidebar filters.

    Empty filters are skipped. The name search is a case-insensitive substring
    match. The rating and review minimums are skipped at their defaults
    (1 star, 0 reviews).
    """
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
    """Horizontal bar chart with one bar per business, sized by x_col.

    The business_id is the first custom_data value, so clicking a bar can
    select that business. If selected_id is among the bars, it is highlighted.
    """
    data = data.copy()
    # Shorten long names so the axis labels don't crowd the chart.
    data["_label"] = data["business_name"].apply(
        lambda x: (str(x)[:28] + "\u2026") if len(str(x)) > 28 else str(x))

    fig = px.bar(data, x=x_col, y="_label", orientation="h",
                 custom_data=["business_id", "business_name", "rating", "review_count", "checkin_count"])

    if selected_id and selected_id in data["business_id"].values:
        # The selected bar gets a dark fill and an outline, so it stands out by
        # shape as well as color. The other bars turn light gray but stay visible.
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
    """Table version of a bar chart, largest value first. Gives screen reader
    and keyboard users the same data the chart shows."""
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
    """Chart panel: a heading, the graph, and a 'View as table' section with
    the same data. The table is filled in by the update_charts callback."""
    return html.Section(
        style={"flex": "1 1 300px", "background": CARD, "border": f"1px solid {BORDER}",
               "borderRadius": "4px", "padding": "16px", "minWidth": "0"},
        **{"aria-labelledby": heading_id},
        children=[
            section_heading(title, heading_id, level=3),
            # Plotly's SVG is unreadable to screen readers, so role=img presents
            # the chart as a single image described by `summary`. The table
            # below carries the actual numbers.
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


# ── App ──

app = dash.Dash(__name__, title="Blanche Lifestyle Magazine")
app.config.suppress_callback_exceptions = True

# Page template: sets the page language, loads the fonts and holds the global
# CSS. Hex values in the CSS match the theme constants at the top of the file.
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

        /* Text for screen readers only (see sr_only() in the Python) */
        .sr-only { position: absolute !important; width: 1px; height: 1px; padding: 0;
                   margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0);
                   white-space: nowrap; border: 0; }

        /* Skip link: off screen until a keyboard user tabs to it */
        .skip-link { position: absolute; left: -9999px; top: 12px; z-index: 1000;
                     background: #FFFFFF; color: #5B4A5E; padding: 10px 16px;
                     font-family: 'Inter', sans-serif; font-weight: 600; border-radius: 4px;
                     border: 2px solid #5B4A5E; text-decoration: none; }
        .skip-link:focus { left: 16px; }

        /* Visible keyboard focus everywhere (white on the dark header) */
        :focus-visible { outline: 3px solid #5B4A5E; outline-offset: 2px; }
        header :focus-visible { outline-color: #FFFFFF; }
        .Select.is-focused > .Select-control { border-color: #5B4A5E !important;
                     box-shadow: 0 0 0 3px rgba(91, 74, 94, 0.45) !important; }

        /* Dropdown theming (Dash dropdowns use react-select's .Select classes) */
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

        /* Placeholders and scrollbars */
        input::placeholder { color: #736676; opacity: 1; }
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #F7F3EF; }
        ::-webkit-scrollbar-thumb { background: #B9ADB5; border-radius: 4px; }

        /* Expandable sections: the browser's default marker is replaced with a
           right/down arrow. The second `content` line gives the arrow empty alt
           text so screen readers skip it; the first is a fallback for browsers
           that don't support that syntax. */
        details > summary { list-style: none; cursor: pointer; }
        details > summary::-webkit-details-marker { display: none; }
        summary.disclosure::before { content: "\\25B8"; content: "\\25B8" / ""; color: #80606D;
                                     margin-right: 6px; display: inline-block; flex-shrink: 0; }
        details[open] > summary.disclosure::before { content: "\\25BE"; content: "\\25BE" / ""; }
        details:hover { box-shadow: 0 1px 4px rgba(0,0,0,0.06); }

        /* Genie typing indicator: three dots bouncing in sequence */
        .typing-dots { display: flex; gap: 5px; align-items: center; height: 16px; padding: 2px 0; }
        .typing-dots span { width: 7px; height: 7px; border-radius: 50%; background: #80606D;
                            opacity: 0.3; animation: genie-bounce 1.2s infinite ease-in-out; }
        .typing-dots span:nth-child(2) { animation-delay: 0.15s; }
        .typing-dots span:nth-child(3) { animation-delay: 0.3s; }
        @keyframes genie-bounce {
            0%, 80%, 100% { opacity: 0.3; transform: translateY(0); }
            40%           { opacity: 1;   transform: translateY(-4px); }
        }

        /* Grayed-out chat input while Genie is answering */
        #genie-input[readonly] { background: #F0EAE6 !important; }

        /* Turn off animation for users who prefer reduced motion */
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

# ── Layout ──
# Top to bottom: header, KPI cards, highlights, filters + map + detail panel,
# Genie chat, bar charts, reviews and tips.
app.layout = html.Div(
    style={"backgroundColor": BG, "fontFamily": SANS, "minHeight": "100vh", "color": TEXT_DARK},
    children=[
        # First thing a keyboard user reaches; jumps past the header.
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

        # tabIndex=-1 lets the skip link move focus here.
        html.Main(id="main-content", tabIndex="-1", style={"outline": "none"}, children=[

            # ── KPI cards ──
            # The heading is hidden on screen but lets screen reader users
            # jump to this section.
            html.Section(**{"aria-labelledby": "kpi-heading"}, children=[
                html.H2("Key figures", id="kpi-heading", className="sr-only"),
                html.Div(id="kpi-row", style={"display": "flex", "flexWrap": "wrap",
                                               "gap": "16px", "padding": "24px 40px 0"}),
            ]),

            # ── Highlights ──
            html.Section(style={"padding": "16px 40px 0"},
                         **{"aria-labelledby": "highlights-heading"}, children=[
                section_heading("Highlights", "highlights-heading"),
                html.Div(id="highlights-row", style={"display": "flex", "flexWrap": "wrap",
                                                      "gap": "16px"}),
            ]),

            # ── Filters sidebar | map | selected-business panel ──
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
                    # Choosing a business here does the same as clicking the map
                    # or a bar, but works with a keyboard and screen reader.
                    filter_field("Select a business", "business-picker",
                        dcc.Dropdown(id="business-picker", options=[], value=None,
                                     searchable=True, clearable=True,
                                     placeholder="Type to search businesses\u2026")),
                    # The map is presented to screen readers as a single image;
                    # the picker above is their way to choose a business.
                    html.Div(role="img",
                             **{"aria-label": "Map of businesses matching the current filters. "
                                              "Use the Select a business field to choose one."},
                             children=[
                        dcc.Graph(id="map-graph", style={"height": "480px", "borderRadius": "4px",
                                  "overflow": "hidden", "border": f"1px solid {BORDER}"},
                                  config={"displayModeBar": False}),
                    ]),
                ]),

                # ── Selected-business panel ──
                # Always in the layout and hidden with display:none when nothing
                # is selected, so the close button always exists for callbacks.
                # The contents are an aria-live region, so screen readers
                # announce each new selection.
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

            # ── Genie chat ──
            html.Section(style={"padding": "0 40px 20px"},
                         **{"aria-labelledby": "genie-heading"}, children=[
                section_heading("Ask Genie", "genie-heading"),
                # Hidden status line. Screen readers announce it when a question
                # is sent and when the answer arrives.
                html.Div(id="genie-status", className="sr-only", role="status",
                         **{"aria-live": "polite"}),
                html.Div(style={"background": CARD, "border": f"1px solid {BORDER}",
                                 "borderRadius": "4px", "overflow": "hidden"}, children=[
                    # Message area. Focusable so keyboard users can scroll it.
                    html.Div(id="genie-messages", tabIndex="0", role="region",
                             **{"aria-label": "Genie conversation"}, style={
                        "padding": "24px", "minHeight": "160px", "maxHeight": "360px",
                        "overflowY": "auto", "background": HIGHLIGHT_BG,
                    }, children=[
                        # Welcome message, hidden once the first question is sent.
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
                        # Answered questions, rendered on the server from genie-history.
                        html.Div(id="genie-thread"),
                        # The question being answered plus the typing indicator,
                        # rendered in the browser.
                        html.Div(id="genie-pending-view"),
                    ]),
                    # Question input and send button
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

            # ── Browser-side state ──
            # chart-selection:    business_id of the selected business, or None
            # genie-conv-id:      current Genie conversation, so follow-ups keep context
            # genie-history:      chat messages as dicts (role, text, sql, rows, cols)
            # genie-pending:      the question waiting for an answer; setting it
            #                     triggers the server call
            # genie-scroll-dummy,
            # detail-focus-dummy: placeholder outputs for clientside callbacks
            #                     that only have side effects
            dcc.Store(id="chart-selection", data=None),
            dcc.Store(id="genie-conv-id", data=None),
            dcc.Store(id="genie-history", data=[]),
            dcc.Store(id="genie-pending", data=None),
            dcc.Store(id="genie-scroll-dummy"),
            dcc.Store(id="detail-focus-dummy"),

            # ── Bar charts ──
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

            # ── Reviews and tips ──
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


# ── Callback: filters or selection change → KPIs, map, highlights, reviews ──
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
    """Rebuild the KPI cards, map, highlight cards and review list."""
    filtered = apply_filters(name_query, categories, subcategories, cities, states, min_rating, min_reviews)

    # KPI cards
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

    # Map: one point per business that has coordinates, colored by category.
    # Point size uses the square root of the review count so the busiest
    # businesses don't swamp everything else.
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
            # The legend lets users read the category colors without hovering.
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
        # Nothing to plot: show an empty map centered on the continental US.
        fig = px.scatter_map(
            pd.DataFrame({"lat": [39.5], "lon": [-98.35]}),
            lat="lat", lon="lon", zoom=3, map_style=MAP_STYLE)
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor=CARD, showlegend=False)

    # If a business is selected, fade the other points, draw a larger pin on
    # top of it, and zoom in on it.
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

    # Highlight cards: top rated (ties go to the one with more reviews), most
    # reviewed and most visited.
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

    # Reviews are queried live: the newest 50 for the selected business, or for
    # all filtered businesses if nothing is selected. A selection is only used
    # if it's in the filtered set, so every ID put into the SQL comes from the
    # business table rather than from the browser.
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


# ── Callback: selection → detail panel contents and visibility ──
@app.callback(
    Output("click-detail", "children"),
    Output("detail-panel", "style"),
    Input("chart-selection", "data"),
)
def show_click_detail(selection):
    """Fill in and show the detail panel for the selected business, or hide
    the panel when nothing is selected."""
    if not selection:
        return None, DETAIL_PANEL_HIDDEN
    sel_df = df[df["business_id"] == selection]
    if len(sel_df) == 0:
        return None, DETAIL_PANEL_HIDDEN

    # Missing values show as blank (or N/A for subcategories) rather than "nan".
    row = sel_df.iloc[0]
    safe_addr = str(row["address"]) if pd.notna(row["address"]) and row["address"] else ""
    safe_postal = str(row["postal_code"]) if pd.notna(row["postal_code"]) and row["postal_code"] else ""
    safe_subcats = str(row["subcategories"]) if pd.notna(row["subcategories"]) and row["subcategories"] else "N/A"

    def fmt_num(v):
        """Format a count with thousands separators, or return it as-is."""
        try:
            return f"{int(float(v)):,}"
        except (ValueError, TypeError):
            return str(v)

    def detail_row(label, value):
        """One label/value pair in the panel's description list."""
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


# ── Callback: options for the business picker ──
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
    """List businesses that match the filters and whatever is typed in the
    picker, top 50 by review count. The list is capped to stay fast; typing
    narrows it. The current selection is always kept so the picker can still
    display it."""
    filtered = apply_filters(name_query, categories, subcategories, cities, states,
                             min_rating, min_reviews)
    if search:
        filtered = filtered[filtered["business_name"].str.contains(
            search, case=False, na=False, regex=False)]
    top = filtered.nlargest(50, "review_count")
    if current and current not in set(top["business_id"]):
        top = pd.concat([df[df["business_id"] == current], top])
    return [{"label": f"{r['business_name']} ({r['city']}, {r['state']})",
             "value": r["business_id"]} for _, r in top.iterrows()]


# ── Genie chat ──
# Asking a question happens in two steps so the page responds instantly:
#   1. This clientside callback runs in the browser. It shows the question and
#      a typing indicator, clears and locks the input, and writes the question
#      to the genie-pending store.
#   2. fetch_genie_answer (below) runs on the server whenever genie-pending
#      changes. It calls Genie, adds the answer to the history and unlocks the
#      input.
# The input is made read-only rather than disabled while waiting, so keyboard
# focus stays in it. Any sends in the meantime are ignored.
# The __NAME__ placeholders in the JavaScript are filled with theme values below.
GENIE_SEND_JS = """
function(n_clicks, n_submit, question) {
    const nu = window.dash_clientside.no_update;
    var inputEl = document.getElementById('genie-input');
    // Ignore sends while an answer is pending, and ignore empty questions.
    if (inputEl && inputEl.readOnly) { return [nu, nu, nu, nu, nu, nu]; }
    var q = (inputEl ? inputEl.value : (question || '')).trim();
    if (!q) { return [nu, nu, nu, nu, nu, nu]; }
    // Shorthand for building a Dash html component in JavaScript.
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
        [userBubble, thinking],           // genie-pending-view: question + typing dots
        '',                               // genie-input: clear it
        {question: q, ts: Date.now()},    // genie-pending: triggers step 2 (ts makes repeat questions count as a change)
        true,                             // genie-input read-only while waiting
        {display: 'none'},                // genie-welcome: hide
        'Question sent. Genie is working on an answer.'   // genie-status: screen reader announcement
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
    """Ask Genie the pending question, add the question and answer to the
    history, and redraw the thread. Also clears the pending view, unlocks the
    input and announces the answer to screen readers."""
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


# ── Clientside: scroll the chat to the newest message ──
# Runs whenever the thread or pending view changes. The short delay lets the
# new message render before scrolling.
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


# ── Callback: filters or selection change → bar charts and their tables ──
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
    """Build the top-10 charts by rating (ties go to the one with more
    reviews), visits and reviews, plus a table version of each."""
    filtered = apply_filters(name_query, categories, subcategories,
                             cities, states, min_rating, min_reviews)
    sel = selection if selection else None

    # Each top 10 is re-sorted ascending because Plotly draws horizontal bars
    # from the bottom up; this puts the largest bar at the top.
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


# ── Callback: decide which business is selected ──
# Clicking the map or a bar, or choosing in the picker, selects a business (and
# keeps the picker in sync). Closing the panel or changing any filter clears
# the selection.
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
    """Update the selection based on whichever input fired.

    Returns (selection, picker value, rated/visited/reviewed chart clickData,
    map clickData).
    """
    triggered = dash.ctx.triggered_id
    nu = no_update
    clear_all = (None, None, None, None, None, None)

    # Clearing also resets every graph's clickData. A graph otherwise
    # remembers its last click, so clicking the same business again after
    # closing the panel wouldn't count as a new click.
    filter_ids = {
        "filter-name", "filter-category", "filter-subcategory", "filter-city",
        "filter-state", "filter-rating", "filter-min-reviews",
    }
    if triggered in filter_ids or triggered == "clear-selection":
        return clear_all

    # The picker already shows the choice; only the selection needs updating.
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
        # Fired because this callback just reset clickData to None; nothing to select.
        return nu, nu, nu, nu, nu, nu
    # The first custom_data value on every bar and map point is the business_id.
    cd = click_data["points"][0].get("customdata", [])
    if not cd:
        return nu, nu, nu, nu, nu, nu
    return cd[0], cd[0], nu, nu, nu, nu


# ── Clientside: move focus after the panel closes ──
# The close button disappears along with the panel, which would drop keyboard
# focus back to the top of the page. Move it to the business picker instead.
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
