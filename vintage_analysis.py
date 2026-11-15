"""
Vintage tab (own page in the top navigation of app.py).

Every stock is lined up on its own clock: month 0 = the stock's first Daily RRG session (the day the RRG chart
starts, after the EMA warm-up), up to month 6. For each stock the Daily RRG strategy's cumulative profit % is
marked to market every day (open trades at that day's close, charges included), and a bold line shows the
average over the stocks that have reached that point. Works on the daily-close or SMA-price RRG.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

import analysis as an
import compute as cp
import results as RES
import rrg_core as core
from rrg_core import INFO

MONTH_DAYS, MAX_MONTHS, TAKE_PROFITS = cp.MONTH_DAYS, cp.MAX_MONTHS, cp.TAKE_PROFITS
AXIS_MONTHS = 12            # x-axis shown: month 0 to 12
PAL = ["#2a78d6", "#eb6834", "#2e9e83", "#9b59b6", "#c0392b", "#16a085", "#d35400", "#7f8c8d", "#8e44ad",
       "#27ae60", "#e67e22", "#34495e", "#1abc9c", "#f39c12", "#2980b9", "#b03a2e", "#6c5ce7", "#00897b",
       "#795548", "#5d6d7e", "#ad1457", "#558b2f", "#0277bd", "#ff8f00", "#4e342e", "#283593"]
in_window, average_line = cp.in_window, cp.average_line


@st.cache_data(show_spinner=False, max_entries=4000)
def vintage(symbol, sma, stop_loss, cost, token, take_profit=None):
    """compute.vintage, cached per session settings (fast: prices and RRG are read/built once)."""
    return cp.vintage(symbol, sma, stop_loss, cost, take_profit)


def saved_ok(sma, cost):
    """True when this setting is in the saved results (daily close or SMA 14, default charges)."""
    return sma in RES.SMAS and RES.is_default_cost(cost)


# ---- page -------------------------------------------------------------------------------------
st.title("📅 Vintage chart — month 0 to 6 of the RRG")
st.caption("Each stock on its own clock: **month 0 = the day its Daily RRG chart starts** (first RRG session after the "
           "warm-up), up to month 6. Line = the Daily RRG strategy's cumulative profit %, marked to market every day.")
token = st.session_state.get("token", 0)
_m = RES.meta()
st.caption(("⚡ Using results saved on %s (data up to %s) — settings other than daily close / SMA %d with %.2f%% "
            "charges are calculated live." % (_m["built_at"], _m["data_through"].strftime("%d %b %Y"), core.SMA_DEFAULT,
                                               core.COST_PCT)) if _m else
           "⏳ No saved results for the current data — calculating live (slower). Run build_cache.py or press "
           "*Refresh data now* on the RRG charts page to save them.")

c1, c2, c3, c4, c5 = st.columns([2.2, 1.6, 0.9, 1.2, 1])
tag = c1.selectbox("Tag", ["All"] + core.TAGS, key="vin_tag",
                   format_func=lambda g: "%s (%d stocks)" % ("All stocks" if g == "All" else g, len(core.stocks_for_tag(g))))
basis = c2.radio("RRG built on", ["Daily close", "SMA price"], horizontal=True, key="vin_basis")
sma = int(c3.number_input("SMA days", 2, 200, core.SMA_DEFAULT, 1, key="vin_sma")) if basis == "SMA price" else 0
stop_loss = c4.radio("Stop-loss", core.STOP_LOSS_OPTIONS, horizontal=True, key="vin_sl", format_func=lambda v: "%g%%" % v)
cost = c5.number_input("Charges / side (%)", 0.0, 1.0, core.COST_PCT, 0.01, key="vin_cost")
basis_txt = "SMA %d price" % sma if sma else "daily close"
q = st.text_input("🔍 Search stock", key="vin_search", placeholder="name, ticker, sector, city or tag — leave empty for the whole tag",
                  help="Every word must match, e.g. 'kaynes', 'jewel', 'technology'. Charts, averages and tables below "
                       "then use only the matching stocks.")
members = an.search_stocks(core.stocks_for_tag(tag), q)
if q and not members:
    st.warning("No stock matches “%s”." % q)
    st.stop()
if q:
    st.caption("🔍 %d of %d stocks match “%s”: %s" % (len(members), len(core.stocks_for_tag(tag)), q, ", ".join(members)))

curves, starts, trades_by, left_out = {}, {}, {}, {}
with st.spinner("Building every stock's first 6 months..."):
    for s in members:
        status, start, df, trs = vintage(s, sma, stop_loss, cost, token)
        if status:
            left_out[s] = status
        else:
            curves[s], starts[s], trades_by[s] = df, start, trs
if left_out:
    st.caption("Not included: " + " · ".join("%s (%s)" % (s, why) for s, why in left_out.items()))
if not curves:
    st.warning("No stock in this tag has an RRG yet.")
    st.stop()

avg = average_line(curves, "strategy")
avg_bh = average_line(curves, "buyhold")
avg_daily = average_line(curves, "daily")

# headline numbers
tag_daily = []                                  # Tags-page method: closed trades only, days held in the trade
for s, trs in trades_by.items():
    closed = in_window(trs, starts[s])
    d = sum(int((t["sell"] - t["buy"]).days) for t in closed)
    if d > 0:
        tag_daily.append(sum(t["ret"] for t in closed) / d)
m1, m2, m4 = st.columns(3)
m1.metric("Stocks", len(curves))
m2.metric("Avg profit % at month 6 / latest", "%+.2f%%" % np.mean([df["strategy"].iloc[-1] for df in curves.values()]))
m4.metric("Avg daily profit %", "%+.4f%%" % np.mean(tag_daily) if tag_daily else "—",
          help="As on the Tags analysis page: each stock's closed trades in the first 6 months, sum of profit % ÷ "
               "sum of calendar days held in those trades; simple average over stocks with a closed trade.")

o1, o3 = st.columns(2)
show_bh = o1.toggle("Also show buy & hold average", value=True, key="vin_bh")
show_daily = o3.toggle("Show average daily profit % line", value=False, key="vin_daily",
                       help="The same line (no take-profit) is in its own chart below, with one line per profit exit point.")
fig = go.Figure()                                           # averages only (each stock's numbers: tables below)
fig.add_trace(go.Scatter(x=avg["month"], y=avg["avg"], mode="lines", name="Average strategy profit",
                         line=dict(width=4, color="black"), customdata=avg["n"],
                         hovertemplate="<b>Average strategy</b><br>month %{x:.1f}<br>%{y:+.2f}%<br>%{customdata} stocks"
                                       "<extra></extra>"))
if show_bh:
    fig.add_trace(go.Scatter(x=avg_bh["month"], y=avg_bh["avg"], mode="lines", name="Average buy & hold",
                             line=dict(width=3, color="#2a6fdb", dash="dash"), customdata=avg_bh["n"],
                             hovertemplate="<b>Average buy & hold</b><br>month %{x:.1f}<br>%{y:+.2f}%<br>%{customdata} stocks"
                                           "<extra></extra>"))
if show_daily:
    fig.add_trace(go.Scatter(x=avg_daily["month"], y=avg_daily["avg"], mode="lines", name="Average daily profit % (right axis)",
                             line=dict(width=3, color="#e65100"), yaxis="y2", customdata=avg_daily["n"],
                             hovertemplate="<b>Average daily profit</b><br>month %{x:.1f}<br>%{y:+.4f}% per day"
                                           "<br>%{customdata} stocks with a closed trade<extra></extra>"))
    lim =np.nanmax(np.abs(avg_daily["avg"].iloc[7:])) if avg_daily["avg"].iloc[7:].notna().any() else 1
    fig.update_layout(yaxis2=dict(title="Average daily profit % (per day)", overlaying="y", side="right",
                                  ticksuffix="%", showgrid=False, zeroline=True, zerolinecolor="#e65100",
                                  range=[-lim * 1.6, lim * 1.6], color="#e65100"))
fig.add_hline(y=0, line_color="#999", line_width=1)
for m in range(1, AXIS_MONTHS + 1):
    fig.add_vline(x=m, line_color="#ddd", line_width=1)
fig.update_layout(height=600, margin=dict(l=10, r=10, t=40, b=10),
                  title=dict(text="%s · Daily RRG on %s · %g%% stop-loss · %d stocks"
                             % ("All stocks" if tag == "All" else tag, basis_txt, stop_loss, len(curves)), font=dict(size=15)),
                  xaxis=dict(title="Months since the RRG chart started (month 0)", range=[0, AXIS_MONTHS], dtick=1),
                  yaxis=dict(title="Cumulative profit %", ticksuffix="%"), hovermode="closest",
                  plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb", legend=dict(font=dict(size=10)))
st.plotly_chart(fig, width="stretch", key="vin_chart")
st.caption("Black line = simple average of the strategy's profit % over the stocks that have reached that month "
           "(hover for how many). A stock whose RRG started less than 6 months ago stops at its latest session, so "
           "later months average fewer stocks. Each stock's own numbers are in the trades table below.")

# ---- vintage view of the average daily profit %, one line per profit exit point ---------------------
st.markdown("### Average daily profit % — vintage view, one line per profit exit point")
st.caption("Same stocks and month-0 clock as above. For every stock, **daily profit %%** on a given day = sum of profit %% "
           "of the trades closed so far (bought and sold after month 0) ÷ sum of calendar days held in them — the Tags "
           "analysis method. The line is the average over the stocks that have a closed trade by then. One line per profit "
           "exit point: **black = RRG exit only (no take-profit)**; coloured = sell when the daily close is up x%%. "
           "Daily RRG on %s · %g%% stop-loss (change it at the top)." % (basis_txt, stop_loss))
EXIT_COL = {None: "#111111", 5: "#9e0142", 7: "#d53e4f", 10: "#f46d43", 12: "#fdae61", 15: "#e6c229",
            17: "#abdda4", 20: "#66c2a5", 25: "#3288bd", 30: "#5e4fa2"}
EXIT_LBL = {tp: ("RRG exit (no take-profit)" if tp is None else "Take-profit %d%%" % tp) for tp in cp.EXITS}
pick_exits = st.multiselect("Profit exit points to show", cp.EXITS, default=cp.EXITS, key="vin_daily_exits",
                            format_func=EXIT_LBL.get)


def daily_curves(tp):
    """{symbol: DataFrame[day, daily]} for the stocks shown, at this exit point (saved results when available)."""
    out = {}
    for s in curves:
        if tp is None:
            out[s] = curves[s][["day", "daily"]]
            continue
        got = RES.get(("daily", s, sma, stop_loss, tp), "missing") if saved_ok(sma, cost) else "missing"
        if got == "missing":
            v = vintage(s, sma, stop_loss, cost, token, tp)
            got = cp.daily_series(v)
        if got is not None:
            out[s] = pd.DataFrame({"day": got[0].astype(int), "daily": got[1].astype(float)})
    return out


with st.spinner("Building the daily profit % lines..."):
    dlines = {tp: average_line(daily_curves(tp), "daily") for tp in pick_exits}
dfig = go.Figure()
vals_all = []
for tp in pick_exits:
    d = dlines[tp]
    vals_all += list(d.loc[d["month"] >= 0.5, "avg"].dropna())
    dfig.add_trace(go.Scatter(x=d["month"], y=d["avg"], mode="lines", name=EXIT_LBL[tp],
                              line=dict(width=4 if tp is None else 2.2, color=EXIT_COL.get(tp, "#777"),
                                        dash="solid"), customdata=d["n"],
                              hovertemplate="<b>%s</b><br>month %%{x:.1f}<br>avg daily profit %%{y:+.3f}%%<br>"
                                            "%%{customdata} stocks with a closed trade<extra></extra>" % EXIT_LBL[tp]))
dfig.add_hline(y=0, line_color="#999", line_width=1)
for m in range(1, AXIS_MONTHS + 1):
    dfig.add_vline(x=m, line_color="#ddd", line_width=1)
yr = None
if vals_all:                                    # early days are noisy (a 1-day trade = a huge daily %): scale on month 0.5+
    lo, hi = np.percentile(vals_all, 1), np.percentile(vals_all, 99)
    pad = (hi - lo) * 0.15 or 0.1
    yr = [min(lo, 0) - pad, max(hi, 0) + pad]
dfig.update_layout(height=560, margin=dict(l=10, r=10, t=40, b=10), hovermode="closest",
                   title=dict(text="%s · Daily RRG on %s · %g%% stop-loss · %d stocks — average daily profit %%"
                              % ("All stocks" if tag == "All" else tag, basis_txt, stop_loss, len(curves)), font=dict(size=15)),
                   xaxis=dict(title="Months since the RRG chart started (month 0)", range=[0, AXIS_MONTHS], dtick=1),
                   yaxis=dict(title="Average daily profit % (per day held)", ticksuffix="%", range=yr),
                   legend=dict(font=dict(size=11)), plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb")
st.plotly_chart(dfig, width="stretch", key="vin_daily_chart")
# month-end values, one row per exit point
mrows = []
for tp in pick_exits:
    d = dlines[tp]
    row = {"Profit exit point": EXIT_LBL[tp]}
    for mth in range(1, MAX_MONTHS + 1):
        day = int(round(mth * MONTH_DAYS))
        hit = d[(d["month"] * MONTH_DAYS).round() <= day]
        v = hit["avg"].iloc[-1] if len(hit) else np.nan
        row["M%d" % mth] = None if pd.isna(v) or hit["n"].iloc[-1] == 0 else round(float(v), 4)
    row["Stocks at M6"] = int(d["n"].iloc[-1])
    mrows.append(row)
mt = pd.DataFrame(mrows)
mcols_d = ["M%d" % m for m in range(1, MAX_MONTHS + 1)]
st.dataframe(mt.style.map(lambda v: ("color:%s" % ("#2e7d32" if v > 0 else "#c62828" if v < 0 else "inherit"))
                          if isinstance(v, (int, float)) and not pd.isna(v) else "", subset=mcols_d)
             .format({c: "{:+.4f}" for c in mcols_d}, na_rep="—"), hide_index=True, width="stretch")
st.caption("Average daily profit % at the end of each month after month 0 (— = no stock with a closed trade yet). "
           "Early months average few trades, so they move a lot. The y-axis is scaled on month 0.5 onwards; hover a "
           "line for its exact value and how many stocks it averages. Click a name in the legend to hide it.")

# ---- trades in the first 6 months (same columns as the Tags analysis table) ------------------------
def colour(v):
    if isinstance(v, (int, float)) and not pd.isna(v):
        return "color:%s" % ("#2e7d32" if v > 0 else "#c62828" if v < 0 else "inherit")
    return ""


st.markdown("#### Every trade in the first 6 months")
rows = []
for s, df in curves.items():
    end6 = starts[s] + pd.Timedelta(days=round(MAX_MONTHS * MONTH_DAYS))
    closed = [t for t in trades_by[s] if not t["open"] and t["sell"] is not None and t["sell"] <= end6]
    still = [t for t in trades_by[s] if t not in closed]
    profits = [t["ret"] for t in closed]
    days = [int((t["sell"] - t["buy"]).days) for t in closed]
    rows.append({
        "Ticker": s, "Stock": INFO[s]["name"], "Sector": an.sector(s), "RRG from": starts[s].strftime("%d %b %Y"),
        "Number of trades": len(closed),
        "Profit % per trade": ", ".join("%.2f" % p for p in profits) or "—",
        "Days held per trade": ", ".join(str(d) for d in days) or "—",
        "Sum of profit %": round(sum(profits), 2), "Sum of days held": sum(days),
        "Daily profit %": round(sum(profits) / sum(days), 4) if sum(days) > 0 else None,
        "Open / after 6 m": len(still),
    })
tbl = pd.DataFrame(rows)
with_d = tbl["Daily profit %"].dropna()
avg_row = {"Ticker": "TOTAL / AVG", "Stock": "%d stocks" % len(tbl), "Sector": "", "RRG from": "",
           "Number of trades": int(tbl["Number of trades"].sum()), "Profit % per trade": "", "Days held per trade": "",
           "Sum of profit %": round(tbl["Sum of profit %"].sum(), 2), "Sum of days held": int(tbl["Sum of days held"].sum()),
           "Daily profit %": round(with_d.mean(), 4) if len(with_d) else None,
           "Open / after 6 m": int(tbl["Open / after 6 m"].sum())}
full = pd.concat([tbl, pd.DataFrame([avg_row])], ignore_index=True)
st.dataframe(full.style.map(colour, subset=["Sum of profit %", "Daily profit %"])
             .format({"Sum of profit %": "{:+.2f}", "Daily profit %": "{:+.4f}"}, na_rep="—"),
             hide_index=True, width="stretch", height=38 + 35 * len(full),
             column_config={"Profit % per trade": st.column_config.TextColumn(width="large"),
                            "Days held per trade": st.column_config.TextColumn(width="medium")})
st.caption("Closed trades bought and sold within the first 6 months after month 0, with the settings above "
           "(%s, %g%% stop-loss, charges %g%% per side). Daily profit %% = sum of profit %% ÷ sum of calendar days "
           "held; the last row's Daily profit %% is the simple average over stocks with a closed trade. "
           "'Open / after 6 m' = trades still open or sold after month 6 (not counted). Historical test, not advice."
           % (basis_txt, stop_loss, cost))


# ---- take-profit exit points x stop-loss -----------------------------------------------------------
def tp_stock(s, sma, stop_loss, cost, token, tp):
    """Saved result when available, else calculated (compute.tp_stock)."""
    if saved_ok(sma, cost):
        key = ("tp", s, sma, stop_loss, tp)
        hit = RES.get(key, "missing")
        if hit != "missing":
            return hit
    return cp.tp_stock(s, sma, stop_loss, cost, tp)


st.markdown("---")
st.markdown("### Take-profit threshold analysis by stop-loss — one chart")
st.caption("Built like the *Take-profit threshold analysis* chart of the help folder app (Tags analysis tab). "
           "On any day after the buy, if the **daily close** reaches the buy price + x%%, the stock is sold that day "
           "at that close (x%% profit booked); after that it buys again only once the Daily RRG has gone into "
           "Weakening/Lagging and come back up, as after a stop-loss. One colour per stop-loss: **solid line = with "
           "take-profit (average of all stocks)**, **dashed line = base strategy without take-profit** at the same "
           "stop-loss, faint dots = each stock. First 6 months from month 0 · RRG on %s · charges as above. "
           "Hover a point for the average days held per trade and the trades." % basis_txt)
metric_lbl = {"tag": "Avg daily profit %",
              "final": "Avg profit % (month 6 / latest)"}
y_key = st.radio("Y-axis", list(metric_lbl), format_func=metric_lbl.get, horizontal=True, key="vin_tp_y",
                 help="Avg daily profit % = as on the Tags analysis page: each stock's closed trades, sum of profit % ÷ "
                      "sum of calendar days held; simple average over stocks with a closed trade.")
EXITS = [None] + TAKE_PROFITS
with st.spinner("Testing %d take-profit thresholds x %d stop-loss levels for every stock..."
                % (len(TAKE_PROFITS), len(core.STOP_LOSS_OPTIONS))):
    per = {sl: {tp: {s: tp_stock(s, sma, sl, cost, token, tp) for s in curves} for tp in EXITS}
           for sl in core.STOP_LOSS_OPTIONS}


def val(r):
    return None if r is None else r[y_key]


def avg_of(sl, tp):
    v = [val(r) for r in per[sl][tp].values() if val(r) is not None]
    return float(np.mean(v)) if v else None


def held_and_trades(sl, tp):
    rs = [r for r in per[sl][tp].values() if r]
    closed = sum(r["closed"] for r in rs)
    return (sum(r["days"] for r in rs) / closed if closed else 0.0), closed, sum(r["tp_hits"] for r in rs)


dec = 2 if y_key == "final" else 4
lab = lambda v: ("%+." + str(dec) + "f%%") % v
SL_COL = {10.0: "#2a78d6", 15.0: "#e65100"}
GAP = 0.45                                         # x shift: 10% SL a little left, 15% SL a little right
SL_SHIFT = {core.STOP_LOSS_OPTIONS[0]: -GAP, core.STOP_LOSS_OPTIONS[-1]: +GAP}
SL_LIGHT = {10.0: "rgba(42,120,214,0.30)", 15.0: "rgba(230,81,0,0.30)"}
lf = go.Figure()
all_v = []
for sl in core.STOP_LOSS_OPTIONS:                  # average of all stocks: bold line in the same colour
    col, dx = SL_COL.get(sl, "#555"), SL_SHIFT.get(sl, 0)
    pts = [(tp, avg_of(sl, tp)) + held_and_trades(sl, tp) for tp in TAKE_PROFITS]
    pts = [p for p in pts if p[1] is not None]
    all_v += [p[1] for p in pts]
    lf.add_trace(go.Scatter(x=[p[0] + dx for p in pts], y=[p[1] for p in pts], mode="lines+markers+text",
                            name="<b>AVERAGE · %g%% stop-loss</b>" % sl, line=dict(color=col, width=5),
                            marker=dict(size=12, color=col, line=dict(color="white", width=1.5)),
                            text=["<b>%s</b>" % lab(p[1]) for p in pts],
                            textposition="bottom center" if dx < 0 else "top center",
                            textfont=dict(color=col, size=12), customdata=[[p[0], p[2], p[3], p[4]] for p in pts],
                            hovertemplate="<b>Average · %g%% stop-loss</b><br>Take-profit %%{customdata[0]}%%<br>%s "
                                          "%%{y:.%df}%%<br>Avg days held per trade %%{customdata[1]:.1f}<br>Closed trades "
                                          "%%{customdata[2]}<br>Sold by take-profit %%{customdata[3]}<extra></extra>"
                                          % (sl, metric_lbl[y_key], dec)))
    b = avg_of(sl, None)
    if b is not None:
        all_v.append(b)
        lf.add_trace(go.Scatter(x=[2, TAKE_PROFITS[-1] + 3], y=[b, b], mode="lines",
                                name="Base, no take-profit · %g%% SL: %s" % (sl, lab(b)),
                                line=dict(color=col, width=2, dash="dash"), hoverinfo="skip"))
for tp in TAKE_PROFITS:                            # light band per exit point: 10% left half, 15% right half
    lf.add_vrect(x0=tp - 0.85, x1=tp + 0.85, fillcolor="#eef1f6", opacity=0.6, line_width=0, layer="below")
lf.add_hline(y=0, line_color="#999", line_width=1)
lo, hi = (min(all_v + [0]), max(all_v + [0]))
pad = (hi - lo) * 0.06 or 1
lf.update_layout(height=650, margin=dict(l=70, r=20, t=60, b=10), hovermode="closest",
                 title=dict(text="%s · %d stocks · first 6 months  —  at every exit point: <span style='color:%s'>"
                                 "<b>10%% stop-loss on the left</b></span>, <span style='color:%s'><b>15%% stop-loss on the "
                                 "right</b></span>" % ("All stocks" if tag == "All" else tag, len(curves),
                                                       SL_COL[10.0], SL_COL[15.0]), font=dict(size=14)),
                 xaxis=dict(title="Profit exit point — take-profit (%)", range=[2, TAKE_PROFITS[-1] + 3],
                            tickvals=TAKE_PROFITS, ticktext=["<b>%d%%</b>" % x for x in TAKE_PROFITS], showgrid=False),
                 yaxis=dict(title=metric_lbl[y_key], ticksuffix="%", range=[lo - pad, hi + pad]),
                 legend=dict(orientation="h", y=-0.12, font=dict(size=11)),
                 plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb")
st.plotly_chart(lf, width="stretch", key="vin_tp_lines")
st.caption("Blue = average of all stocks with 10% stop-loss, orange = with 15% stop-loss; dashed = the same average "
           "without take-profit. At each exit point the two sit side by side with a small gap (10% left, 15% right). "
           "Every stock's own numbers are in the grid and tables below.")

st.markdown("#### Every stock at every exit point — 10% stop-loss block on top, 15% block below")
SHOW_X = [None] + TAKE_PROFITS                     # first column = base (no take-profit)
X_LBL = ["No take-profit<br>(RRG exit)"] + ["<b>%d%%</b>" % x for x in TAKE_PROFITS]
stocks_order = sorted(curves, key=lambda s: -(val(per[core.STOP_LOSS_OPTIONS[0]][None][s]) or -1e9))
ylab, zrows, trows, hrows = [], [], [], []
for k, sl in enumerate(core.STOP_LOSS_OPTIONS):
    if k:                                          # gap between the two stop-loss lanes
        ylab.append(" " * k); zrows.append([None] * len(SHOW_X)); trows.append([""] * len(SHOW_X))
        hrows.append([""] * len(SHOW_X))
    avg_vals = [avg_of(sl, tp) for tp in SHOW_X]
    ylab.append("<b>%g%% SL · AVERAGE</b>" % sl)
    zrows.append(avg_vals)
    trows.append(["<b>%s</b>" % lab(v) if v is not None else "—" for v in avg_vals])
    hrows.append(["Average of %d stocks" % len(curves)] * len(SHOW_X))
    for s in stocks_order:
        vals = [val(per[sl][tp][s]) for tp in SHOW_X]
        ylab.append("%g%% SL · %s" % (sl, s))
        zrows.append(vals)
        trows.append([lab(v) if v is not None else "—" for v in vals])
        hrows.append([INFO[s]["name"]] * len(SHOW_X))
flat = [v for r in zrows for v in r if v is not None]
cap = float(np.percentile(np.abs(flat), 90)) if flat else 1.0
cap = cap or 1.0
hm = go.Figure(go.Heatmap(
    z=zrows, x=X_LBL, y=ylab, text=trows, texttemplate="%{text}", textfont=dict(size=11),
    customdata=hrows, zmin=-cap, zmax=cap, zmid=0, xgap=3, ygap=1,
    colorscale=[[0, "#c62828"], [0.35, "#ef9a9a"], [0.5, "#f5f5f2"], [0.65, "#a5d6a7"], [1, "#2e7d32"]],
    colorbar=dict(title=dict(text=metric_lbl[y_key]), ticksuffix="%", len=0.5),
    hovertemplate="<b>%{y}</b><br>%{customdata}<br>Take-profit: %{x}<br>" + metric_lbl[y_key] + " %{z:+."
                  + str(dec) + "f}%<extra></extra>", hoverongaps=False))
n_rows = len(ylab)
for k, sl in enumerate(core.STOP_LOSS_OPTIONS):        # lane titles on the left edge
    first = ylab.index("<b>%g%% SL · AVERAGE</b>" % sl)
    hm.add_shape(type="rect", xref="paper", yref="y", x0=-0.005, x1=1.0, y0=first - 0.5, y1=first + len(curves) + 0.5,
                 line=dict(color=SL_COL.get(sl, "#555"), width=2.5), fillcolor="rgba(0,0,0,0)", layer="above")
hm.update_layout(height=140 + 24 * n_rows, margin=dict(l=170, r=10, t=110, b=10),
                 title=dict(text="%s · %d stocks · Daily RRG on %s · first 6 months  —  top: %g%% stop-loss · bottom: "
                                 "%g%% stop-loss" % ("All stocks" if tag == "All" else tag, len(curves), basis_txt,
                                                     core.STOP_LOSS_OPTIONS[0], core.STOP_LOSS_OPTIONS[-1]),
                            font=dict(size=14), y=0.995, yanchor="top"),
                 xaxis=dict(side="top", tickfont=dict(size=13)),
                 yaxis=dict(autorange="reversed", tickfont=dict(size=11)),
                 plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb")
st.plotly_chart(hm, width="stretch", key="vin_tp_grid")
st.caption("One chart, two blocks with a gap: **top block (blue frame) = 10% stop-loss, bottom block (orange frame) = "
           "15% stop-loss**. Each row is one stock across the exit points; the first row of each block is the average "
           "of all stocks. First column = no take-profit (sold only on the Daily RRG). Green = profit, red = loss; "
           "the value is written in every cell. Stocks are sorted by their no-take-profit result.")
XLBL = ["Base (no take-profit)"] + ["%d%%" % x for x in TAKE_PROFITS]
XTXT = XLBL

# ---- per-stock tables: how much profit at each exit point ----
st.markdown("#### How much profit at each exit point — every stock")
for tab, sl in zip(st.tabs(["%g%% stop-loss" % sl for sl in core.STOP_LOSS_OPTIONS]), core.STOP_LOSS_OPTIONS):
    rows = []
    for s in curves:
        row = {"Ticker": s, "Stock": INFO[s]["name"]}
        for tp, xl in zip(EXITS, XTXT):
            row[xl] = val(per[sl][tp][s])
        vals = {k: row[k] for k in XTXT if row[k] is not None}
        row["Best exit"] = max(vals, key=vals.get) if vals else "—"
        rows.append(row)
    avg_row = {"Ticker": "AVERAGE", "Stock": "%d stocks" % len(curves)}
    for tp, xl in zip(EXITS, XTXT):
        avg_row[xl] = avg_of(sl, tp)
    av = {k: avg_row[k] for k in XTXT if avg_row[k] is not None}
    avg_row["Best exit"] = max(av, key=av.get) if av else "—"
    tbl = pd.DataFrame(rows + [avg_row])
    f = "{:+.2f}" if y_key == "final" else "{:+.4f}"
    tab.dataframe(tbl.style.map(colour, subset=XTXT).format({c: f for c in XTXT}, na_rep="—"),
                  hide_index=True, width="stretch", height=38 + 35 * len(tbl))
    hits = []
    for tp, xl in zip(EXITS[1:], XTXT[1:]):
        rs = [r for r in per[sl][tp].values() if r]
        hits.append("%s: %d of %d trades" % (xl, sum(r["tp_hits"] for r in rs), sum(r["trades"] for r in rs)))
    tab.caption("Values = %s. Sold by take-profit — %s." % (metric_lbl[y_key], " · ".join(hits)))


# ---- rule check: a stop-loss that comes first is taken, the take-profit is then never taken ----------
def rule_check():
    tot = [0, 0, 0, 0]
    for s in curves:
        r = RES.get(("rule", s, sma)) if saved_ok(sma, cost) else None
        if r is None:
            r = cp.rule_check_stock(s, sma, cost)
        tot = [a + b for a, b in zip(tot, r)]
    return tuple(tot)


with st.spinner("Checking the stop-loss / take-profit order on every trade..."):
    ck, n_sl, n_tp, n_bad = rule_check()
(st.success if n_bad == 0 else st.error)(
    "**Rule check — stop-loss first:** %d trades checked (%d stop-loss exits, %d take-profit exits, every stop-loss and "
    "exit point above). %s Each day the stop-loss is tested before the take-profit, and a trade ends on the first level "
    "the close reaches — so once the stop-loss is hit, the profit exit can no longer happen for that trade."
    % (ck, n_sl, n_tp, "No trade took a profit exit after its stop-loss had already been reached, and no stop-loss trade "
                       "had reached its profit exit earlier." if n_bad == 0 else "%d trades break the rule!" % n_bad))

# ---- realistic replay: 10% take-profit + 10% stop-loss with real orders ---------------------------------
st.markdown("---")
st.markdown("### Realistic replay — take-profit + stop-loss with orders you could actually place")
st.caption("The charts above use the app's simple rules (trade at (open + close) ÷ 2, levels checked on the close). Here the "
           "same Daily RRG signals are traded the way a broker would fill them, using each day's Open / High / Low / Close "
           "/ Volume: **buy at the next day's open**; a **stop-loss order** fills when the day's low reaches it (at the open "
           "if the stock gaps below it); a **take-profit limit** fills when the day's high reaches it (at the open if it "
           "gaps above); if one day touches both, the stop-loss is assumed first; RRG exits sell at the next day's open. "
           "Each trade is ₹1,00,000 in whole shares. Practical barriers are flagged on every trade.")
r1, r2, r3, r4 = st.columns(4)
rtp = r1.number_input("Take-profit %", 1.0, 100.0, 10.0, 1.0, key="rp_tp")
rsl = r2.number_input("Stop-loss %", 1.0, 50.0, 10.0, 1.0, key="rp_sl")
r6m = r3.toggle("Only the first 6 months", value=True, key="rp_6m")
ramt = r4.number_input("₹ per trade", 1000.0, 1e8, 100000.0, 10000.0, format="%.0f", key="rp_amt")


@st.cache_data(show_spinner=False)
def replay(symbol, sma, tp, sl, cost, amount, only6, token):
    d = cp.REPLAY_DEFAULT
    if saved_ok(sma, cost) and (tp, sl, amount, only6) == (d["tp"], d["sl"], d["amount"], d["only6"]):
        hit = RES.get(("replay", symbol, sma))
        if hit is not None:
            return hit
    return cp.replay(symbol, sma, tp, sl, cost, amount, only6)


_dflt = cp.REPLAY_DEFAULT
_rp_saved = saved_ok(sma, cost) and bool(RES.meta()) and (rtp, rsl, ramt, r6m) == (_dflt["tp"], _dflt["sl"], _dflt["amount"], _dflt["only6"])
if not st.toggle("▶ Run the realistic replay", value=_rp_saved, key="rp_run",
                 help="Downloads daily Open/High/Low/Close/Volume for every stock shown (about a minute the first "
                      "time each day for the whole list; search for one stock to make it quick)."):
    st.info("Switch on **Run the realistic replay** to replay the %d stocks shown above with real orders and see the "
            "practical barriers on every trade. Tip: search for one stock first to make it quick." % len(curves))
    st.stop()
with st.spinner("Replaying every stock with real orders..."):
    rp = {s: replay(s, sma, rtp, rsl, cost, ramt, r6m, token) for s in curves}
rows, all_flags = [], {}
for s, (trs, why) in rp.items():
    if trs is None:
        rows.append({"Ticker": s, "Stock": INFO[s]["name"], "Note": why}); continue
    closed = [t for t in trs if t["sell"] is not None]
    ideal_status, _, _, ideal = vintage(s, sma, rsl, cost, token, rtp) if not r6m else (None, None, None, None)
    gaps = sum(1 for t in closed if "gap-down" in t["exit"])
    both = sum(1 for t in closed if "both levels" in t["exit"])
    nfl = sum(len(t["flags"]) for t in trs)
    all_flags[s] = trs
    rows.append({
        "Ticker": s, "Stock": INFO[s]["name"], "Trades": len(closed),
        "Take-profit exits": sum(1 for t in closed if t["kind"] == "tp"),
        "Stop-loss exits": sum(1 for t in closed if t["kind"] == "stop"),
        "RRG exits": sum(1 for t in closed if t["kind"] == "rrg"),
        "Profit % per trade": ", ".join("%.2f" % t["ret"] for t in closed) or "—",
        "Days held per trade": ", ".join(str(t["days"]) for t in closed) or "—",
        "Sum of profit %": round(sum(t["ret"] for t in closed), 2),
        "Daily profit %": round(sum(t["ret"] for t in closed) / sum(t["days"] for t in closed), 4)
        if sum(t["days"] for t in closed) > 0 else None,
        "Gap-downs past stop": gaps, "Both levels same day": both, "Barrier flags": nfl,
        "Open trade": "yes (%+.2f%%)" % trs[-1]["ret"] if trs and trs[-1]["sell"] is None else "",
    })
rtab = pd.DataFrame(rows)
if "Trades" in rtab:
    tot = {"Ticker": "TOTAL / AVG", "Stock": "", "Trades": int(rtab["Trades"].sum()),
           "Take-profit exits": int(rtab["Take-profit exits"].sum()), "Stop-loss exits": int(rtab["Stop-loss exits"].sum()),
           "RRG exits": int(rtab["RRG exits"].sum()), "Sum of profit %": round(rtab["Sum of profit %"].sum(), 2),
           "Daily profit %": round(rtab["Daily profit %"].dropna().mean(), 4) if rtab["Daily profit %"].notna().any() else None,
           "Gap-downs past stop": int(rtab["Gap-downs past stop"].sum()),
           "Both levels same day": int(rtab["Both levels same day"].sum()), "Barrier flags": int(rtab["Barrier flags"].sum())}
    rtab = pd.concat([rtab, pd.DataFrame([tot])], ignore_index=True)
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Closed trades", tot["Trades"])
    k2.metric("Take-profit / stop-loss / RRG exits", "%d / %d / %d" % (tot["Take-profit exits"], tot["Stop-loss exits"], tot["RRG exits"]))
    k3.metric("Avg daily profit %", "%+.4f%%" % tot["Daily profit %"] if tot["Daily profit %"] is not None else "—")
    k4.metric("Gap-downs past the stop", tot["Gap-downs past stop"],
              help="Opened below the stop-loss: sold at the open, so the loss is bigger than the stop %.")
    k5.metric("Trades with a barrier flag", sum(1 for trs in all_flags.values() for t in trs if t["flags"]))
st.dataframe(rtab.style.map(colour, subset=[c for c in ["Sum of profit %", "Daily profit %"] if c in rtab])
             .format({"Sum of profit %": "{:+.2f}", "Daily profit %": "{:+.4f}"}, na_rep="—"),
             hide_index=True, width="stretch", height=38 + 35 * len(rtab),
             column_config={"Profit % per trade": st.column_config.TextColumn(width="large")})

if all_flags:
    pick_r = st.selectbox("Trade-by-trade replay for one stock", list(all_flags), key="rp_pick",
                          format_func=lambda s: "%s — %s" % (s, INFO[s]["name"]))
    trs = all_flags[pick_r]
    if trs:
        st.dataframe(pd.DataFrame([{
            "#": i + 1, "RRG signal": t["signal"].strftime("%d %b %Y"), "Buy (open)": t["buy"].strftime("%d %b %Y"),
            "Buy ₹": round(t["buy_px"], 2), "Shares": t["shares"],
            "Stop ₹": round(t["buy_px"] * (1 - rsl / 100), 2), "Target ₹": round(t["buy_px"] * (1 + rtp / 100), 2),
            "Sell": t["sell"].strftime("%d %b %Y") if t["sell"] is not None else "open",
            "Sell ₹": round(t["sell_px"], 2), "Exit": t["exit"], "Days": t["days"], "Profit %": round(t["ret"], 2),
            "Practical barriers": " | ".join(t["flags"]) or "none",
        } for i, t in enumerate(trs)]).style.map(colour, subset=["Profit %"]).format({"Profit %": "{:+.2f}"}),
            hide_index=True, width="stretch",
            column_config={"Practical barriers": st.column_config.TextColumn(width="large")})
    else:
        st.info("No trade for %s in this window." % INFO[pick_r]["name"])

st.markdown("""
**Practical barriers this replay checks (and the ones it can't):**
- **Gap-down past the stop** — if the stock opens below the stop-loss, a stop order fills at the open, so the loss is bigger than the stop %. Flagged on the trade.
- **Both levels in one day** — daily data can't tell whether the high or the low came first; the replay assumes the stop-loss (the worse case). Flagged.
- **Circuit limits** — a day with High = Low (price locked) or a ±20% move: buy / sell orders may not fill. Flagged.
- **Thin liquidity** — if ₹ per trade is more than 2% of the day's traded value (volume × close), expect slippage. Flagged.
- **Price of one share above ₹ per trade** — no whole share can be bought; the signal is skipped.
- *Not covered by daily data:* the exact intraday order of moves, bid-ask spread, auction/pre-open price, T+1 settlement (cash from a sale is usable for a new buy the next day — fine here because a new buy always waits for a fresh RRG signal), and taxes beyond the charges set above.
""")
