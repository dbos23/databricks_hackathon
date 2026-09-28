# Blanche Lifestyle Magazine — Yelp Business Explorer

An interactive dashboard, deployed as a **Databricks App**, for exploring Yelp's Open Source Data. It combines filterable KPIs, a map, top-10 charts and a live reviews feed with an embedded **Databricks Genie** chat.

The entry point is `app_v3.py` (set in `app.yaml`). `app.py` and `app_v2.py` are earlier iterations and are not run by the deployment.

---

## Project structure

| File | Purpose |
|---|---|
| `app_v3.py` | The application: data loading, layout, callbacks and Genie client. This is what runs. |
| `app.yaml` | Databricks Apps config: start command, environment variables and the SQL warehouse resource. |
| `requirements.txt` | Python dependencies installed by Databricks Apps at deploy time. |
| `app.py`, `app_v2.py` | Earlier versions, kept for reference. Not used by `app.yaml`. |

---

## Requirements

### Python

Python **3.10+** 

### Libraries

| Library | Used for |
|---|---|
| `dash` | Web framework: layout (`dash.html`, `dash.dcc`), server-side and clientside callbacks, `dcc.Store` for state. Uses `allow_duplicate` outputs and `dash.ctx`, which need Dash ≥ 2.9. |
| `plotly` | `plotly.express` bar charts and the `scatter_map` business map (MapLibre-based, `carto-positron` style). |
| `pandas` | Holds the business table in memory; all filtering, sorting and top-N logic. |
| `numpy` | Square-root scaling of review counts for map marker sizes. |
| `databricks-sdk` | `WorkspaceClient` for authentication, the Statement Execution API (`w.statement_execution`) and the Genie API (`w.genie`). |

Standard library: `os` (env vars), `re` (bold-text parsing in Genie answers), `time` (Genie polling).

---

## Data sources

The data originally comes from https://business.yelp.com/data/resources/open-dataset/. The app pulls the data from our databricks tables after it's been through our pipeline. 

---

### Chat state

State lives in the browser in `dcc.Store` components, so each browser tab has its own independent Genie conversation:

- `genie-conv-id` — the Genie conversation ID for follow-ups. Reloading the page starts a new conversation.
- `genie-history` — list of `{role, text, sql, rows, cols}` entries used to re-render the thread.
- `genie-pending` — the question currently being answered.

### Genie and the dashboard are independent

The Genie chat does not read the sidebar filters or the selected business, and Genie answers don't change the dashboard. A question like "top rated pizza places in Tampa" is answered from Genie's own tables regardless of what's filtered on screen.

---

## Accessibility

The app was built with WCAG AA in mind:

- Skip-to-content link, semantic landmarks (`header`, `main`, `aside`, `section`) and a proper heading hierarchy.
- Theme colors adjusted for at least 4.5:1 text contrast; minimum font size 12px; a distinct category palette plus a map legend so color isn't the only cue.
- Visible `:focus-visible` outlines, including on dropdowns.
- Every chart has an `aria-label` summary and a "View as table" data table with a caption and scoped headers.
- Ratings read as "Rated 4.5 out of 5" instead of "four point five black star".
- Live regions announce Genie status/answers and changes to the selected-business panel.
- A keyboard-usable business picker as an alternative to clicking the map.
- Focus is moved to a sensible place when the detail panel closes.
- `prefers-reduced-motion` disables the typing-dots animation.

---

## Known limitations and notes

- **Port.** The app listens on `8050`. Databricks Apps provides the port to use in the `DATABRICKS_APP_PORT` environment variable (8000 by default). If the deployed app doesn't respond, change the last line to
  `app.run(host="0.0.0.0", port=int(os.environ.get("DATABRICKS_APP_PORT", 8050)), debug=False)`.
- **Plotly version.** `scatter_map` needs Plotly ≥ 5.24; see the version note above.
- **Genie space access** isn't declared in `app.yaml`, so it must be granted separately.
- **Startup load.** The whole business table is held in memory. This is fine for the Yelp dataset but won't scale to very large tables, and data refreshes require an app restart.
- **Reviews query size.** With no filters applied, every business ID goes into the `IN (...)` list. For very large tables this makes a long statement; a join against the same filter conditions in SQL, or a temp view, would scale better. IDs come from the app's own table rather than user input, but parameterized queries would be the more robust approach.
- **Blocking Genie calls.** `fetch_genie_answer` blocks a server worker for up to 120 seconds while polling. With many concurrent users, Dash background callbacks would avoid tying up workers.
- **Genie row cap.** Only the first 50 result rows are fetched and 25 are displayed.
- **Conversation lifetime.** Genie conversations are per browser tab and reset on page reload.