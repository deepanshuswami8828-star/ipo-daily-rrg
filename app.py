"""
IPO Daily RRG app - 76 Indian IPOs (Top 20 of 2026, Robotics & Automation, 50 random mainboard IPOs) against NIFTY 50, each from its listing day.

Pages (Daily RRG only):
  Daily RRG   - RRG with a date slider for the tail, quadrant timeline, date lookup, quadrant periods,
                up/down cycles and every session
  Strategy    - Strategy 2 Version 3 rules on the Daily RRG (10% stop-loss) in rupees: profit/loss,
                why it happened, current BUY / HOLD / SELL / WAIT status, every trade
  All stocks  - every stock side by side (filter by sector) and a multi-stock RRG with a date slider
  Rules       - formula and strategy rules
A Data Status & Validation panel sits at the top of every page.

Run:  streamlit run app.py      (or double-click "Start IPO RRG App.bat")
"""
import warnings

warnings.filterwarnings("ignore")

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from plotly.subplots import make_subplots

import analysis as an
import rrg_core as core
from rrg_core import (INFO, STOCKS, QUAD_BG, QUAD_FG, SURFACE, INK_1, INK_2, INK_3, GRID, SERIES,
                      ORDER, BENCH, UP)

UP_FG, DOWN_FG = QUAD_FG["Leading"], QUAD_FG["Lagging"]
PALETTE = ["#2a78d6", "#eb6834", "#2e9e83", "#9b59b6", "#c0392b", "#16a085", "#d35400", "#7f8c8d",
           "#8e44ad", "#27ae60", "#e67e22", "#34495e", "#1abc9c", "#f39c12", "#2980b9", "#b03a2e",
           "#6c5ce7", "#00897b", "#795548", "#5d6d7e"]
COLOR = {s: PALETTE[i % len(PALETTE)] for i, (s, *_) in enumerate(STOCKS)}

st.set_page_config(page_title="IPO Daily RRG", page_icon="📈", layout="wide")
st.markdown("""<style>.block-container{padding-top:1.2rem;padding-bottom:1rem}
div[data-testid="stMetricValue"]{font-size:1.35rem}</style>""", unsafe_allow_html=True)

# Top navigation, as in the help folder app: "RRG charts" is the rest of this script, "Tags analysis" its own page.
nav = st.navigation([
    st.Page(lambda: None, title="RRG charts", icon="📈", url_path="rrg", default=True),
    st.Page("tags_analysis.py", title="Tags analysis", icon="🏷️", url_path="tags"),
    st.Page("vintage_analysis.py", title="Vintage", icon="📅", url_path="vintage"),
], position="top")
nav.run()
if nav.url_path in ("tags", "vintage"):
    st.stop()


def inr(v, sign=False):
    s = "₹" + format(abs(round(v)), ",d")
    return ("+" if v >= 0 else "-") + s if sign else ("-" + s if v < 0 else s)


def pct(v):
    return "%+.2f%%" % v


def quad_style(col):
    return ["background-color:%s;color:%s;font-weight:bold" % (QUAD_BG[v], QUAD_FG[v]) if v in QUAD_BG else ""
            for v in col]


def money_style(col):
    return ["color:%s;font-weight:bold" % (UP_FG if str(v).startswith("+") else
                                            DOWN_FG if str(v).startswith("-") else INK_2) for v in col]


def status_box(color, title, lines):
    body = "".join("<div style='margin-top:4px;color:%s'>%s</div>" % (INK_1, l) for l in lines)
    st.markdown("<div style='border:1px solid %s;border-left:6px solid %s;border-radius:8px;padding:10px 16px;"
                "background:%s'><div style='font-size:1.15rem;font-weight:700;color:%s'>%s</div>%s</div>"
                % (GRID, color, SURFACE, color, title, body), unsafe_allow_html=True)


# ---- data (cached) ------------------------------------------------------------
@st.cache_data(show_spinner="Loading prices...")
def load(symbol, token, sma=0):
    al, note = core.aligned(symbol, force=token > 0)
    rrg, warm = core.daily_rrg(al, sma)
    return al, rrg, warm, note, an.now_ist()


def safe_load(symbol, token, sma=0):
    try:
        return load(symbol, token, sma)
    except Exception:
        return None


# ---- single-stock RRG with date slider -----------------------------------------
def frame_range(xs, ys):
    spread = max(xs.max() - xs.min(), ys.max() - ys.min())
    pad, margin = max(0.35, 0.20 * spread), max(0.45, 0.25 * spread)
    return ([min(xs.min() - pad, 100 - margin), max(xs.max() + pad, 100 + margin)],
            [min(ys.min() - pad, 100 - margin), max(ys.max() + pad, 100 + margin)])


def r3(v):
    return [round(float(x), 3) for x in v]


KEYS_JS = """
var gd = document.getElementById('{plot_id}');
document.documentElement.style.height='100%'; document.body.style.height='100%';
document.body.style.margin='0'; gd.parentElement.style.height='100%'; gd.style.height='100%';
Plotly.Plots.resize(gd);
var names = gd._transitionData._frames.map(function(f){return f.name;});
var at = names.length - 1;
function go(i){ at = Math.max(0, Math.min(names.length-1, i));
  Plotly.animate(gd, [names[at]], {mode:'immediate', frame:{duration:0, redraw:true}, transition:{duration:0}}); }
gd.on('plotly_sliderchange', function(e){ at = names.indexOf(e.step.label); });
document.addEventListener('keydown', function(e){
  if (e.key==='ArrowLeft'){ go(at-1); e.preventDefault(); }
  if (e.key==='ArrowRight'){ go(at+1); e.preventDefault(); } });
"""


def quad_shapes():
    big = 1e4
    shapes = [dict(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, fillcolor=QUAD_BG[q], line=dict(width=0),
                   layer="below")
              for q, (x0, x1, y0, y1) in {"Improving": (-big, 100, 100, big), "Leading": (100, big, 100, big),
                                          "Lagging": (-big, 100, -big, 100),
                                          "Weakening": (100, big, -big, 100)}.items()]
    return shapes + [dict(type="line", x0=-big, x1=big, y0=100, y1=100, line=dict(color=INK_3, width=1.1)),
                     dict(type="line", x0=100, x1=100, y0=-big, y1=big, line=dict(color=INK_3, width=1.1))]


def corner_notes(xr, yr):
    corner = {"Improving": (xr[0], yr[1], "left", "top"), "Leading": (xr[1], yr[1], "right", "top"),
              "Lagging": (xr[0], yr[0], "left", "bottom"), "Weakening": (xr[1], yr[0], "right", "bottom")}
    return [dict(x=cx, y=cy, xanchor=xa, yanchor=ya, showarrow=False, xshift=8 if xa == "left" else -8,
                 yshift=-6 if ya == "top" else 6, text="<b>%s</b>" % q.upper(), font=dict(color=QUAD_FG[q], size=12))
            for q, (cx, cy, xa, ya) in corner.items()]


def slider(frames, prefix="Session: "):
    step = dict(mode="immediate", frame=dict(duration=0, redraw=True), transition=dict(duration=0))
    return [dict(active=len(frames) - 1, x=0, len=1, y=0, yanchor="top",
                 steps=[dict(method="animate", label=f["name"], args=[[f["name"]], step]) for f in frames],
                 pad=dict(t=34, b=0), currentvalue=dict(prefix=prefix, xanchor="left", font=dict(size=13, color=INK_1)),
                 ticklen=0, minorticklen=0, font=dict(size=1, color=SURFACE))]


def frame_parts(tail, xr, yr, trades):
    xs, ys = tail["RS_Ratio"].to_numpy(), tail["RS_Momentum"].to_numpy()
    quads = list(tail["Quadrant"])
    n = len(tail)
    buys = {t["buy"] for t in trades}
    sells = {t["sell"] for t in trades if t["sell"] is not None}
    fade = [round(0.3 + 0.7 * i / max(n - 1, 1), 2) for i in range(n)]
    hover = []
    for i, (d, r, m, q, c) in enumerate(zip(tail.index, xs, ys, quads, tail["Close"])):
        tag = "  · BUY" if d in buys else ("  · SELL" if d in sells else "")
        hover.append("<b>#%d  %s</b>%s<br>%s<br>RS-Ratio %.2f<br>RS-Momentum %.2f<br>Close ₹%.2f"
                     % (i + 1, d.strftime("%a %d %b %Y"), tag, q, r, m, c))
    labels = [d.strftime("%d %b") if i in (0, n - 1) else "" for i, d in enumerate(tail.index)]
    x, y = r3(xs), r3(ys)
    data = [
        dict(type="scatter", x=x, y=y, mode="lines", line=dict(color=SERIES, width=2), opacity=0.55, hoverinfo="skip"),
        dict(type="scatter", x=x, y=y, mode="markers+text", text=labels, textposition="top center",
             textfont=dict(color=INK_2, size=11),
             marker=dict(size=9, color=[QUAD_FG[q] for q in quads], opacity=fade, line=dict(color=SURFACE, width=1.2)),
             hovertext=hover, hoverinfo="text"),
        dict(type="scatter", x=x[-1:], y=y[-1:], mode="markers",
             marker=dict(size=17, color=QUAD_FG[quads[-1]], line=dict(color=SURFACE, width=2)),
             hovertext=hover[-1:], hoverinfo="text"),
    ]
    day = tail.index[-1]
    tag = " · BUY day" if day in buys else (" · SELL day" if day in sells else "")
    title = ("<b>%s</b>  ·  <span style='color:%s'><b>%s</b></span>  ·  RS-Ratio %.2f  ·  RS-Momentum %.2f%s"
             % (day.strftime("%a %d %b %Y"), QUAD_FG[quads[-1]], quads[-1].upper(), xs[-1], ys[-1], tag))
    return data, dict(xaxis=dict(range=r3(xr)), yaxis=dict(range=r3(yr)), annotations=corner_notes(xr, yr),
                      title=dict(text=title, y=0.985, yanchor="top", font=dict(size=13)))


def rrg_figure(rrg, tail_n, fixed, trades):
    n = len(rrg)
    fx = frame_range(rrg["RS_Ratio"].to_numpy(), rrg["RS_Momentum"].to_numpy()) if fixed else None
    frames = []
    for k in range(min(tail_n, n) - 1, n):
        tail = rrg.iloc[max(0, k - tail_n + 1):k + 1]
        xr, yr = fx or frame_range(tail["RS_Ratio"].to_numpy(), tail["RS_Momentum"].to_numpy())
        data, layout = frame_parts(tail, xr, yr, trades)
        frames.append(dict(name=rrg.index[k].strftime("%Y-%m-%d"), data=data, layout=layout))
    layout = dict(frames[-1]["layout"])
    layout["xaxis"] = dict(layout["xaxis"], gridcolor=GRID, zeroline=False,
                           title=dict(text="RS-Ratio (100 = in line with %s)" % BENCH, font=dict(size=12)))
    layout["yaxis"] = dict(layout["yaxis"], gridcolor=GRID, zeroline=False,
                           title=dict(text="RS-Momentum", font=dict(size=12)))
    layout.update(shapes=quad_shapes(), showlegend=False, hovermode="closest", autosize=True,
                  margin=dict(l=55, r=15, t=36, b=70), plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
                  font=dict(color=INK_2), sliders=slider(frames))
    return dict(data=frames[-1]["data"], layout=layout, frames=frames)


def to_html(fig):
    return pio.to_html(fig, validate=False, include_plotlyjs=True, full_html=True, auto_play=False,
                       default_width="100%", default_height="100%",
                       config={"displaylogo": False, "responsive": True}, post_script=KEYS_JS)


@st.cache_data(max_entries=8, show_spinner="Building the RRG chart...")
def rrg_html(symbol, token, tail_n, fixed, stop_loss, cost, sma=0):
    _, rrg, *_ = load(symbol, token, sma)
    trades, _, _ = core.run_strategy(rrg, stop_loss, cost)
    return to_html(rrg_figure(rrg, tail_n, fixed, trades))


@st.cache_data(max_entries=4, show_spinner="Building the multi-stock RRG...")
def multi_html(symbols, token, tail_n, sessions, sma=0):
    data = {}
    for s in symbols:
        got = safe_load(s, token, sma)
        if got is not None and len(got[1]) >= 10:
            data[s] = got[1]
    if not data:
        return None
    all_dates = sorted(set().union(*[set(d.index) for d in data.values()]))[-sessions:]
    frames = []
    for d in all_dates:
        traces = []
        for s, df in data.items():
            hist = df.loc[:d]
            if len(hist) < 2 or hist.index[-1] != d:
                continue
            tail = hist.tail(tail_n)
            xs, ys = r3(tail["RS_Ratio"]), r3(tail["RS_Momentum"])
            nm = INFO[s]["name"]
            traces.append(dict(type="scatter", x=xs, y=ys, mode="lines", line=dict(color=COLOR[s], width=2),
                               opacity=0.6, hoverinfo="skip", showlegend=False))
            traces.append(dict(type="scatter", x=xs[-1:], y=ys[-1:], mode="markers+text", text=[s],
                               textposition="top center", textfont=dict(color=INK_1, size=10),
                               marker=dict(size=12, color=COLOR[s], line=dict(color=SURFACE, width=1.5)),
                               hovertemplate="<b>%s</b><br>%s<br>%s<br>RS-Ratio %%{x:.2f}<br>RS-Momentum %%{y:.2f}"
                                             "<extra></extra>" % (nm, d.strftime("%d %b %Y"), tail["Quadrant"].iloc[-1]),
                               showlegend=False))
        frames.append(dict(name=d.strftime("%Y-%m-%d"), data=traces))
    # one fixed frame covering every point the slider can show
    pts = pd.concat([df.loc[all_dates[0] - pd.Timedelta(days=60):] for df in data.values()])
    xr, yr = frame_range(pts["RS_Ratio"].to_numpy(), pts["RS_Momentum"].to_numpy())
    # every frame must carry the same number of traces for Plotly animation; pad with empties
    width = max(len(f["data"]) for f in frames)
    for f in frames:
        f["data"] += [dict(type="scatter", x=[], y=[], mode="markers", showlegend=False)] * (width - len(f["data"]))
    layout = dict(shapes=quad_shapes(), annotations=corner_notes(xr, yr), showlegend=False, hovermode="closest",
                  autosize=True, margin=dict(l=55, r=15, t=20, b=70), plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
                  font=dict(color=INK_2),
                  xaxis=dict(range=r3(xr), gridcolor=GRID, zeroline=False, title="RS-Ratio (100 = in line with %s)" % BENCH),
                  yaxis=dict(range=r3(yr), gridcolor=GRID, zeroline=False, title="RS-Momentum"),
                  sliders=slider(frames))
    return to_html(dict(data=frames[-1]["data"], layout=layout, frames=frames))


# ---- other charts -------------------------------------------------------------
def timeline_figure(seg):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.04)
    fig.add_hline(y=100, line_color=INK_3, line_width=1, row=1, col=1)
    fig.add_trace(go.Scatter(x=seg.index, y=seg["RS_Ratio"], name="RS-Ratio", line=dict(color=SERIES, width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=seg.index, y=seg["RS_Momentum"], name="RS-Momentum", line=dict(color="#d0782a", width=2)),
                  row=1, col=1)
    for q in ORDER:
        part = seg[seg["Quadrant"] == q]
        fig.add_trace(go.Bar(x=part.index, y=[1] * len(part), name=q, marker_color=QUAD_FG[q], marker_line_width=0,
                             customdata=part[["RS_Ratio", "RS_Momentum"]].to_numpy(),
                             hovertemplate="%{x|%a %d %b %Y}<br><b>" + q + "</b><br>RS-Ratio %{customdata[0]:.2f}"
                                           "<br>RS-Momentum %{customdata[1]:.2f}<extra></extra>"), row=2, col=1)
    fig.update_layout(height=330, bargap=0, barmode="stack", hovermode="x unified", margin=dict(l=55, r=15, t=10, b=10),
                      plot_bgcolor=SURFACE, paper_bgcolor=SURFACE, font=dict(color=INK_2),
                      legend=dict(orientation="h", y=1.1, x=0))
    holidays = pd.bdate_range(seg.index[0], seg.index[-1]).difference(seg.index)
    fig.update_xaxes(gridcolor=GRID, rangebreaks=[dict(bounds=["sat", "mon"]), dict(values=list(holidays))])
    fig.update_yaxes(gridcolor=GRID, row=1, col=1)
    fig.update_yaxes(visible=False, row=2, col=1)
    return fig


def cycle_strip(df, name):
    fig = go.Figure()
    end = df.index[-1]
    for p in an.phases(df):
        x1 = p["next"] or end + pd.Timedelta(days=1)
        fig.add_shape(type="rect", x0=p["start"], x1=x1, y0=0.12, y1=0.88, opacity=0.85, line_width=0,
                      fillcolor=UP_FG if p["up"] else DOWN_FG)
        fig.add_trace(go.Scatter(x=[p["start"] + (x1 - p["start"]) / 2], y=[0.5], mode="markers",
                                 marker=dict(size=18, opacity=0), showlegend=False,
                                 hovertemplate="<b>%s</b><br>%s → %s<br>%d sessions<br>%s<extra></extra>"
                                               % ("UP" if p["up"] else "DOWN", p["start"].strftime("%d %b %Y"),
                                                  p["next"].strftime("%d %b %Y") if p["next"] else "now",
                                                  p["bars"], " → ".join(p["route"]))))
    for label, color in (("Up: Improving / Leading", UP_FG), ("Down: Weakening / Lagging", DOWN_FG)):
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=label,
                                 marker=dict(size=12, symbol="square", color=color)))
    fig.update_layout(height=150, margin=dict(l=55, r=15, t=30, b=25), plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
                      font=dict(color=INK_2), legend=dict(orientation="h", y=1.05, yanchor="bottom", x=0))
    fig.update_yaxes(range=[0, 1], tickvals=[0.5], ticktext=["<b>Daily</b>"], showgrid=False, zeroline=False)
    fig.update_xaxes(gridcolor=GRID)
    return fig


def strategy_figure(al, rrg, book, value, bh_value, issue):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.5, 0.36, 0.14], vertical_spacing=0.04,
                        subplot_titles=("Price with buys and sells", "₹ value: strategy vs buy & hold", ""))
    fig.add_trace(go.Scatter(x=al.index, y=al["Close"], name="Close", line=dict(color=SERIES, width=2),
                             hovertemplate="%{x|%a %d %b %Y}<br>Close ₹%{y:.2f}<extra></extra>"), row=1, col=1)
    if issue:
        fig.add_hline(y=issue, line=dict(color=INK_3, width=1, dash="dot"), row=1, col=1,
                      annotation_text="Issue ₹%g" % issue, annotation_position="bottom right")
    if book:
        fig.add_trace(go.Scatter(x=[b["buy"] for b in book], y=[b["buy_px"] for b in book], mode="markers", name="Buy",
                                 marker=dict(symbol="triangle-up", size=13, color=UP_FG, line=dict(color="white", width=1)),
                                 customdata=[[b["shares"]] for b in book],
                                 hovertemplate="BUY %{x|%d %b %Y}<br>₹%{y:.2f} × %{customdata[0]} sh<extra></extra>"),
                      row=1, col=1)
        for stop, nm, sym, col in ((False, "Sell (Daily RRG)", "triangle-down", DOWN_FG),
                                   (True, "Sell (stop-loss)", "x", "#111111")):
            s = [b for b in book if b["sell"] is not None and bool(b.get("stop")) == stop]
            if s:
                fig.add_trace(go.Scatter(x=[b["sell"] for b in s], y=[b["sell_px"] for b in s], mode="markers", name=nm,
                                         marker=dict(symbol=sym, size=12, color=col),
                                         customdata=[[inr(b["pnl"], sign=True), pct(b["pnl_pct"])] for b in s],
                                         hovertemplate="SELL %{x|%d %b %Y}<br>₹%{y:.2f}<br>%{customdata[0]} "
                                                       "(%{customdata[1]})<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=value.index, y=value, name="Strategy ₹", line=dict(color=UP_FG, width=2),
                             hovertemplate="%{x|%d %b %Y}<br>Strategy ₹%{y:,.0f}<extra></extra>"), row=2, col=1)
    fig.add_trace(go.Scatter(x=bh_value.index, y=bh_value, name="Buy & hold ₹", line=dict(color=INK_3, width=2, dash="dot"),
                             hovertemplate="%{x|%d %b %Y}<br>Buy & hold ₹%{y:,.0f}<extra></extra>"), row=2, col=1)
    for q in ORDER:
        part = rrg[rrg["Quadrant"] == q]
        fig.add_trace(go.Bar(x=part.index, y=[1] * len(part), name=q, marker_color=QUAD_FG[q], marker_line_width=0,
                             showlegend=False, hovertemplate="%{x|%d %b %Y}<br><b>" + q + "</b><extra></extra>"),
                      row=3, col=1)
    fig.update_layout(height=620, bargap=0, barmode="stack", hovermode="closest", margin=dict(l=60, r=15, t=40, b=10),
                      plot_bgcolor=SURFACE, paper_bgcolor=SURFACE, font=dict(color=INK_2),
                      legend=dict(orientation="h", y=1.07, x=0))
    holidays = pd.bdate_range(al.index[0], al.index[-1]).difference(al.index)
    fig.update_xaxes(gridcolor=GRID, rangebreaks=[dict(bounds=["sat", "mon"]), dict(values=list(holidays))])
    fig.update_yaxes(gridcolor=GRID)
    fig.update_yaxes(visible=False, row=3, col=1)
    return fig


# ---- Data Status & Validation panel -------------------------------------------
@st.cache_data(show_spinner=False)
def coverage(token):
    rows = []
    for s, name, *_ in STOCKS:
        tags = core.tag_text(s)
        got = safe_load(s, token)
        if got is None:
            rows.append({"Stock": name, "Symbol": s, "Tags": tags, "Sector": an.sector(s),
                         "Status": "NEEDS NSE CSV" if INFO[s]["source"] == "nse_csv" else "NO DATA"})
            continue
        al = got[0]
        v = an.validate(al, INFO[s]["listed"])
        exp = an.expected_latest_session(an.now_ist())
        rows.append({"Stock": name, "Symbol": s, "Tags": tags, "Sector": an.sector(s), "Rows": v["rows"],
                     "First date": v["first"].strftime("%d %b %Y"), "Latest date": v["last"].strftime("%d %b %Y"),
                     "Status": "LIVE" if v["last"] >= exp else "STALE",
                     "Checks": "%d/%d pass" % (sum(ok for _, ok in v["checks"]), len(v["checks"])),
                     "Flagged moves": len(v["flagged"])})
    return pd.DataFrame(rows)


def data_panel(sym, al, note, fetched, token):
    v = an.validate(al, INFO[sym]["listed"])
    now = an.now_ist()
    exp = an.expected_latest_session(now)
    with st.expander("📊 Data Status & Validation Panel", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown("**Selected stock:** %s" % INFO[sym]["name"])
        c1.caption("Ticker: `%s` · Tags: %s · Benchmark: `%s`" % (INFO[sym]["ticker"], core.tag_text(sym), BENCH))
        c2.markdown("**Last sync:** %s IST" % fetched.strftime("%d %b %Y %H:%M"))
        c2.caption("Provider: %s" % note)
        status = "LIVE" if v["last"] >= exp else "STALE"
        c3.markdown("**Status:** <span style='color:%s;font-weight:700'>%s</span>"
                    % (UP_FG if status == "LIVE" else "#d0782a", status), unsafe_allow_html=True)
        c3.caption("Latest session in data: %s" % v["last"].strftime("%a %d %b %Y"))
        c4.markdown("**Expected latest session:** %s" % exp.strftime("%d %b %Y"))
        c4.caption("%s · sessions after 15:45 IST count as complete" % ("🟢 NSE open" if an.market_open(now) else "⚪ NSE closed"))
        st.markdown("**Validation checks for %s** (%d rows, %s → %s):"
                    % (INFO[sym]["name"], v["rows"], v["first"].strftime("%d %b %Y"), v["last"].strftime("%d %b %Y")))
        st.markdown("  ".join("%s %s" % ("✅" if ok else "❌", label) for label, ok in v["checks"]))
        if v["weekend"]:
            st.caption("Weekend sessions in the data (NIFTY 50 traded too, so they are real special sessions): %s"
                       % ", ".join(v["weekend"]))
        if v["first_vs_listing"] != 0:
            st.caption("First data row is %d day(s) after the listing date in the stock list." % v["first_vs_listing"])
        if v["flagged"]:
            st.markdown("**Flagged one-day moves (> ±%g%%):**" % an.SUSPICIOUS_MOVE_PCT)
            st.dataframe(pd.DataFrame(v["flagged"]), hide_index=True)
        else:
            st.caption("No one-day move larger than ±%g%%." % an.SUSPICIOUS_MOVE_PCT)
        st.markdown("**All %d stocks — coverage & alignment:**" % len(STOCKS))
        st.dataframe(coverage(token), hide_index=True, width="stretch")


# ---- sidebar -------------------------------------------------------------------
if "token" not in st.session_state:
    st.session_state.token = 0
with st.sidebar:
    # as in the help folder app: the RRG pages list every stock; tags have their own "Tags analysis" tab
    st.header("Stock & View Selection")
    all_syms = [s for s, _ in STOCKS]
    labels = {s: "%d. %s (%s)" % (i + 1, INFO[s]["name"], an.sector(s)) for i, s in enumerate(all_syms)}
    query = st.text_input("🔍 Search stock", key="search", placeholder="name, ticker, sector, city or tag",
                          help="Every word must match — e.g. 'kaynes', 'jewel', 'robotics', 'technology pune'.")
    found = an.search_stocks(all_syms, query)
    if query and not found:
        st.warning("No stock matches “%s” — showing all %d." % (query, len(all_syms)))
        found = all_syms
    elif query:
        st.caption("%d of %d stocks match" % (len(found), len(all_syms)))
    sym = st.selectbox("Select Stock", found, format_func=labels.get, key="stock")
    st.caption("**Selected:** %s · Sector: *%s* · Tags: %s" % (INFO[sym]["name"], an.sector(sym), core.tag_text(sym)))
    page = st.radio("Page", ["Daily RRG", "Strategy", "All stocks", "Rules"], key="page")
    st.divider()
    tail_n = st.slider("Tail length (sessions)", 3, 40, 10)
    chart_h = st.slider("Chart height (px)", 380, 800, 500, 20)
    full_w = st.toggle("Full-width chart", value=False)
    fixed = st.toggle("Fixed axes while sliding", value=False,
                      help="Off: each date framed on its own trail. On: one scale for the whole slider.")
    st.divider()
    basis = st.radio("RRG built on", ["Daily close", "SMA price"], horizontal=True,
                     help="Daily close: RS = stock close ÷ NIFTY close (original).  SMA price: RS = stock N-day SMA "
                          "÷ NIFTY N-day SMA — smoother, fewer false signals, but slower. Trades always use real prices.")
    sma = int(st.number_input("SMA days", 2, 200, core.SMA_DEFAULT, 1)) if basis == "SMA price" else 0
    st.divider()
    capital = st.number_input("Amount (₹)", 1000.0, 1e8, 100000.0, 10000.0, format="%.0f")
    stop_loss = st.radio("Stop-loss", core.STOP_LOSS_OPTIONS, horizontal=True, format_func=lambda v: "%g%%" % v)
    cost = st.number_input("Charges per side (%)", 0.0, 1.0, core.COST_PCT, 0.01)
    if st.button("Refresh data now", width="stretch"):
        st.session_state.token += 1
    st.caption("Benchmark: NIFTY 50 (^NSEI). Data: Yahoo Finance daily, auto-adjusted.")

token = st.session_state.token


def chart_frame(html):
    if full_w:
        st.iframe(html, height=chart_h)
    else:
        _, mid, _ = st.columns([1, 6, 1])
        with mid:
            st.iframe(html, height=chart_h)


info = INFO[sym]
sec, ind, city = an.PROFILE.get(sym, ("—", "—", "—"))
got = safe_load(sym, token, sma)
BASIS = ("SMA %d price" % sma) if sma else "daily close"
if got is None and page in ("Daily RRG", "Strategy"):
    st.markdown("#### %s (%s)" % (info["name"], sym))
    if sym in an.NOTES:
        st.caption("ℹ️ " + an.NOTES[sym])
    if info["source"] == "nse_csv":
        st.warning("**%s is an NSE SME stock — Yahoo Finance has no price history for it.** To add it:" % info["name"])
        st.markdown("""
1. Open **nseindia.com**, search **%s**, and open its quote page.
2. Go to **Historical Data**, choose the series **SM** / **ST**, and pick a date range (NSE allows about one year
   per download). Start from the listing date, **%s**.
3. Click **Download (.csv)**. Repeat for each year up to today.
4. Put the files in the app folder under `data/nse_csv/`, named starting with **%s** — for example
   `%s_2025.csv`, `%s_2026.csv`.
5. Press **Refresh data now** in the sidebar.

NSE prices are as traded (not adjusted for splits or bonuses); the validation panel flags any one-day move over ±25%%.
""" % (sym, info["listed"].strftime("%d %b %Y"), sym, sym, sym))
    else:
        st.error("No price data for %s and no saved copy. Check the internet connection and press Refresh." % sym)
    st.stop()
if got is not None:
    al, rrg, warm, note, fetched = got
    trades, pend, pend_x = core.run_strategy(rrg, stop_loss, cost) if not rrg.empty else ([], None, None)


def issue_text(i):
    if not i["issue"]:
        return "no IPO issue price"
    return "issue ₹%g%s" % (i["issue"], " · issue size ₹%s cr" % format(i["size"], ",.2f") if i["size"] else "")


def stock_header(title):
    now = an.now_ist()
    st.markdown("#### %s (%s) against %s — %s" % (info["name"], sym, BENCH, title))
    st.caption("%s · %s · %s, %s · tags: %s · listed %s · %s · %d sessions · first %d used as EMA warm-up · %s"
               % ("🟢 NSE open" if an.market_open(now) else "⚪ NSE closed", sec, ind, city, core.tag_text(sym),
                  info["listed"].strftime("%d %b %Y"), issue_text(info), len(al), warm, note))
    if sym in an.NOTES:
        st.caption("ℹ️ " + an.NOTES[sym])


# ================================================================ DAILY RRG PAGE
if page == "Daily RRG":
    stock_header("daily RRG since listing · built on %s" % BASIS)
    data_panel(sym, al, note, fetched, token)
    if rrg.empty:
        st.warning("%s has only %d sessions since listing — too few for a Daily RRG. Check back later."
                   % (info["name"], len(al)))
        st.stop()
    if len(rrg) < 30:
        st.info("Short history: only %d RRG sessions so far. Early readings move fast and are less reliable." % len(rrg))
    last, prev = rrg.iloc[-1], rrg.iloc[-2]
    runs = an.periods(rrg)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Quadrant on %s" % rrg.index[-1].strftime("%d %b"), last["Quadrant"],
              "%d session%s in a row" % (runs.iloc[0]["Sessions"], "" if runs.iloc[0]["Sessions"] == 1 else "s"),
              delta_color="off")
    c2.metric("RS-Ratio", "%.2f" % last["RS_Ratio"], "%+.2f" % (last["RS_Ratio"] - prev["RS_Ratio"]))
    c3.metric("RS-Momentum", "%.2f" % last["RS_Momentum"], "%+.2f" % (last["RS_Momentum"] - prev["RS_Momentum"]))
    c4.metric("Close", "₹%.2f" % last["Close"], "%+.2f%% vs previous" % (100 * (last["Close"] / prev["Close"] - 1))
              + (" · %+.1f%% vs issue" % (100 * (last["Close"] / info["issue"] - 1)) if info["issue"] else ""))
    chart_frame(rrg_html(sym, token, tail_n, fixed, stop_loss, cost, sma))
    st.caption("Drag the slider under the chart to move the tail back and forward, or click the chart and use ← / →. "
               "Dots are coloured by the quadrant of their own day; the big dot is the selected session.")

    st.subheader("Up / down cycles since the RRG started")
    st.caption("▲ Up = the day it moved into Improving or Leading.  ▼ Down = the day it moved into Weakening or "
               "Lagging.  *Price till next move* = close on that day to close on the next move (or today).")
    st.plotly_chart(cycle_strip(rrg, info["name"]), width="stretch", theme=None,
                    config={"displaylogo": False, "displayModeBar": False})
    mv = an.moves(rrg)
    cur = an.phases(rrg)[-1]
    ups = [m["bars"] for m in mv if m["up"] and not m["open"]]
    downs = [m["bars"] for m in mv if not m["up"] and not m["open"]]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Now", "%s · %s" % ("Up" if cur["up"] else "Down", cur["route"][-1]),
              "since %s" % cur["start"].strftime("%d %b %Y"), delta_color="normal" if cur["up"] else "inverse")
    c2.metric("Moves up", sum(m["up"] for m in mv))
    c3.metric("Average stay up", "%.1f sessions" % (sum(ups) / len(ups)) if ups else "—")
    c4.metric("Average stay down", "%.1f sessions" % (sum(downs) / len(downs)) if downs else "—")
    if mv:
        tb = pd.DataFrame([{"#": i + 1, "Date": m["date"].strftime("%a %d %b %Y"),
                            "Move": "▲ Up" if m["up"] else "▼ Down", "From": m["frm"], "Into": m["to"],
                            "Stayed": "%d session%s%s" % (m["bars"], "" if m["bars"] == 1 else "s",
                                                          " (still there)" if m["open"] else ""),
                            "Until": m["until"].strftime("%d %b %Y") if m["until"] is not None else "now",
                            "Close": "₹%.2f" % m["close"], "Price till next move": pct(m["change"])}
                           for i, m in enumerate(mv)])
        st.dataframe(tb.style.apply(quad_style, subset=["From", "Into"]).apply(money_style, subset=["Price till next move"]),
                     hide_index=True, width="stretch", height=38 + 35 * min(12, len(tb)))

    st.subheader("Which quadrant on which date")
    st.plotly_chart(timeline_figure(rrg), width="stretch", theme=None, config={"displaylogo": False})
    left, right = st.columns(2)
    with left:
        st.markdown("**Look up a date**")
        pick = st.date_input("Date", value=rrg.index[-1].date(), min_value=rrg.index[0].date(),
                             max_value=rrg.index[-1].date(), label_visibility="collapsed")
        hit = rrg.loc[:pd.Timestamp(pick)]
        d = hit.index[-1]
        row = hit.iloc[-1]
        extra = "" if d.date() == pick else " (no trading on %s; showing the previous session)" % pick.strftime("%d %b %Y")
        st.markdown("**%s** — <span style='color:%s;font-weight:700'>%s</span> · RS-Ratio %.2f · RS-Momentum %.2f · "
                    "Close ₹%.2f%s" % (d.strftime("%a %d %b %Y"), QUAD_FG[row["Quadrant"]], row["Quadrant"].upper(),
                                       row["RS_Ratio"], row["RS_Momentum"], row["Close"], extra), unsafe_allow_html=True)
        counts = rrg["Quadrant"].value_counts().reindex(ORDER, fill_value=0)
        st.markdown("**Sessions per quadrant (%d sessions)**" % len(rrg))
        st.dataframe(pd.DataFrame({"Quadrant": counts.index, "Sessions": counts.values,
                                   "Share": ["%.0f%%" % (100 * v / len(rrg)) for v in counts.values]})
                     .style.apply(quad_style, subset=["Quadrant"]), hide_index=True, width="stretch")
    with right:
        st.markdown("**Quadrant periods (newest first)**")
        show = runs.assign(From=runs["From"].dt.strftime("%d %b %Y"), To=runs["To"].dt.strftime("%d %b %Y"))
        st.dataframe(show.style.apply(quad_style, subset=["Quadrant"]), hide_index=True, width="stretch", height=380)

    with st.expander("Every session, one by one"):
        rows = rrg.iloc[::-1]
        table = pd.DataFrame({"Date": rows.index.strftime("%a %d %b %Y"), "Close": rows["Close"].round(2).to_numpy(),
                              "RS-Ratio": rows["RS_Ratio"].round(2).to_numpy(),
                              "RS-Mom.": rows["RS_Momentum"].round(2).to_numpy(), "Quadrant": rows["Quadrant"].to_numpy()})
        st.dataframe(table.style.apply(quad_style, subset=["Quadrant"]), hide_index=True, width="stretch", height=450)
        st.download_button("Download as CSV", rrg.to_csv(float_format="%.4f"),
                           file_name="rrg_%s_daily.csv" % sym.lower(), mime="text/csv")
    st.caption(("RS = SMA%d(stock) ÷ SMA%d(NIFTY) · " % (sma, sma) if sma else "RS = close ÷ NIFTY close · ") +
               "RS-Ratio = 100 × EMA(SMA(RS,5),5) / EMA(SMA(RS,5),30) · RS-Momentum = 100 × EMA(RS-Ratio,3) / "
               "EMA(RS-Ratio,14) · periods are sessions · Yahoo quotes may lag the exchange by a few minutes")

# ================================================================ STRATEGY PAGE
elif page == "Strategy":
    stock_header("strategy (Daily RRG on %s, %g%% stop-loss)" % (BASIS, stop_loss))
    data_panel(sym, al, note, fetched, token)
    st.markdown(
        "<div style='background:%s;border:1px solid %s;border-left:5px solid %s;padding:14px 18px;border-radius:8px;"
        "margin:6px 0 14px'>"
        "<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px'>"
        "<span style='font-size:1.15rem;font-weight:700;color:%s'>Strategy 2 · Version 3 rules on the Daily RRG — "
        "%g%% Stop-Loss</span><span style='background:#e8f5e9;color:#2e7d32;padding:3px 10px;border-radius:12px;"
        "font-size:0.82rem;font-weight:600'>Daily Only</span></div>"
        "<div style='margin-top:6px;color:%s;font-size:0.93rem'><b>Kya karti hai:</b> Har trading din ka Daily RRG "
        "(<b>%s</b> par bana) dekhti hai. Leading/Improving me buy, Weakening/Lagging me sell, aur close buy price se %g%% neeche gaya to "
        "stop-loss. Weekly RRG use nahi hota. Charges %.2f%% har side.</div>"
        "<div style='margin-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:12px'>"
        "<div style='background:#f1f8e9;padding:10px 14px;border-radius:6px'><b style='color:#2e7d32'>🟢 Kharidne ka "
        "Niyam:</b><div style='font-size:0.9rem;margin-top:4px'>Jis din Daily RRG Leading ya Improving ho, agle "
        "trading din (open + close) ÷ 2 par buy. Stop-loss ke baad: Daily pehle Weakening/Lagging me jaaye, phir upar "
        "aaye tabhi dobara buy.</div></div>"
        "<div style='background:#fbe9e7;padding:10px 14px;border-radius:6px'><b style='color:#c62828'>🔴 Bechne ka "
        "Niyam:</b><div style='font-size:0.9rem;margin-top:4px'>Jis din Daily RRG Weakening ya Lagging ho, agle din "
        "(open + close) ÷ 2 par sell. Ya kisi bhi din close ≤ buy price ka %g%% to usi din close par sell.</div></div>"
        "</div><div style='margin-top:10px;padding:8px 12px;background:#f8f9fa;border-radius:6px;font-size:0.88rem;"
        "color:%s'>🎯 <b>Kab accha kaam karegi:</b> jab naya IPO lagatar NIFTY se behtar chal raha ho.<br>"
        "⚠️ <b>Savdhani:</b> Daily RRG jaldi badalta hai, isliye jhoote signal zyada aate hain; gap-down par loss %g%% "
        "se thoda zyada ho sakta hai; naye IPO me data kam hai.</div></div>"
        % (SURFACE, GRID, UP_FG, INK_1, stop_loss, INK_2, BASIS, stop_loss, cost, 100 - stop_loss, INK_2, stop_loss),
        unsafe_allow_html=True)
    if rrg.empty:
        st.warning("%s has only %d sessions — not enough for the Daily RRG strategy yet." % (info["name"], len(al)))
        st.stop()

    book, cash, value, bh_value, bh_shares = an.simulate(rrg, trades, capital, cost)
    m = an.metrics(book, value, bh_value, capital)
    start = rrg.index[0]
    made = m["pnl"] >= 0
    status_box(UP_FG if made else DOWN_FG, "%s %s" % ("PROFIT" if made else "LOSS", inr(m["pnl"], sign=True)),
               ["You put in <b>%s</b> on %s → worth <b>%s</b> on %s (%s)."
                % (inr(capital), start.strftime("%d %b %Y"), inr(m["final"]), rrg.index[-1].strftime("%d %b %Y"), pct(m["ret"])),
                "Buying %d shares on %s and holding would be worth <b>%s</b> (%s, %s)."
                % (bh_shares, start.strftime("%d %b %Y"), inr(m["bh_final"]), inr(m["bh_final"] - capital, sign=True), pct(m["bh_ret"])),
                "The strategy did <b>%s</b> than buy & hold by %s."
                % ("better" if m["final"] >= m["bh_final"] else "worse", inr(abs(m["final"] - m["bh_final"])))])
    st.write("")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Money now", inr(m["final"]), "%s on %s" % (inr(m["pnl"], sign=True), inr(capital)))
    c2.metric("Charges paid", inr(m["charges"]), "%.2f%% per buy/sell" % cost, delta_color="off")
    c3.metric("Trades won / lost", "%d / %d" % (m["wins"], m["losses"]),
              "%d closed%s · %d stop-loss" % (m["closed"], " + 1 open" if book and book[-1]["sell"] is None else "", m["stops"]),
              delta_color="off")
    c4.metric("Money in the stock", "%.0f%% of days" % (100 * m["days_in"] / max(1, m["days"])), delta_color="off")
    c5.metric("Max drawdown", "%.1f%%" % m["max_dd"], delta_color="off")

    ex = an.explain(book, m, info["name"])
    with st.expander("🔍 **Why Profit / Loss Happened (Kyo Profit ya Loss Hua?) — %s**" % ex["headline"], expanded=True):
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Gross profit from wins", inr(m["gross_profit"]), "%d wins (avg %s)" % (m["wins"], pct(m["avg_win"])))
        k2.metric("Gross loss from losers", "-" + inr(m["gross_loss"]), "%d losses (avg %s)" % (m["losses"], pct(m["avg_loss"])),
                  delta_color="inverse")
        k3.metric("Profit factor", "%.2fx" % m["profit_factor"] if m["profit_factor"] < 999 else "no losses",
                  "Gross win / gross loss", delta_color="off")
        k4.metric("Win rate (closed)", "%.0f%%" % m["win_rate"] if m["closed"] else "—", delta_color="off")
        st.markdown("**Asal wajah:**")
        for en, hi in ex["bullets"]:
            st.markdown("• **%s**<br>&nbsp;&nbsp;↳ *Hinglish:* %s" % (en, hi), unsafe_allow_html=True)

    # current status
    dq = rrg["Quadrant"].iloc[-1]
    state = "Daily now: %s <b style='color:%s'>%s</b> — RS-Ratio %.2f, RS-Momentum %.2f (%s)" % (
        "✅" if dq in UP else "❌", QUAD_FG[dq], dq, rrg["RS_Ratio"].iloc[-1], rrg["RS_Momentum"].iloc[-1],
        rrg.index[-1].strftime("%a %d %b %Y"))
    open_b = book[-1] if book and book[-1]["sell"] is None else None
    last_px = rrg["Close"].iloc[-1]
    st.write("")
    if pend is not None:
        sh = int(cash // (last_px * (1 + cost / 100)))
        status_box(UP_FG, "▲ BUY signal on %s" % pend["signal"].strftime("%a %d %b %Y"),
                   ["Daily RRG moved into %s. Buy on the next trading day at (open + close) ÷ 2 — about %d shares at "
                    "today's ₹%.2f." % (pend["into"], sh, last_px), state])
    elif open_b and pend_x is not None:
        status_box(DOWN_FG, "▼ SELL signal on %s" % pend_x["exit_signal"].strftime("%a %d %b %Y"),
                   ["%s. Sell all %d shares on the next trading day at (open + close) ÷ 2. At today's close that is %s "
                    "(%s)." % (pend_x["exit_reason"], open_b["shares"], inr(open_b["got"]), inr(open_b["pnl"], sign=True)), state])
    elif open_b:
        status_box(UP_FG, "HOLD — %d shares since %s" % (open_b["shares"], open_b["buy"].strftime("%a %d %b %Y")),
                   ["Bought at ₹%.2f (paid %s). Today ₹%.2f — selling now would give %s: %s."
                    % (open_b["buy_px"], inr(open_b["paid"]), last_px, inr(open_b["got"]), inr(open_b["pnl"], sign=True)),
                    "Stop-loss at ₹%.2f (%g%% below the buy price)." % (open_b["stop_px"], stop_loss), state])
    elif book and book[-1]["sell"] == rrg.index[-1]:
        b = book[-1]
        status_box(DOWN_FG, "▼ SOLD today", ["Sold %d shares at ₹%.2f → %s (%s). Reason: %s"
                                             % (b["shares"], b["sell_px"], inr(b["got"]), inr(b["pnl"], sign=True),
                                                b["exit_reason"]), state])
    else:
        status_box(INK_3, "WAIT — all %s is in cash" % inr(cash),
                   ["Waiting for the Daily RRG to move into Improving or Leading%s."
                    % (" (after a stop-loss it must first go down and come back up)" if book and book[-1].get("stop") else ""),
                    state])

    st.plotly_chart(strategy_figure(al, rrg, book, value, bh_value, info["issue"]), width="stretch", theme=None,
                    config={"displaylogo": False})

    st.subheader("Every trade in rupees, oldest first")
    if book:
        table = pd.DataFrame([{
            "#": i + 1, "Signal": b["signal"].strftime("%d %b %Y"), "Daily at signal": b["into"],
            "Buy date": b["buy"].strftime("%d %b %Y"), "Buy price": "₹%.2f" % b["buy_px"], "Shares": b["shares"],
            "You paid": inr(b["paid"]), "Stop at": "₹%.2f" % b["stop_px"],
            "Sell date": b["sell"].strftime("%d %b %Y") if b["sell"] is not None else "still holding",
            "Sell price": "₹%.2f%s" % (b["sell_px"], "" if b["sell"] is not None else " (today)"),
            "You got": inr(b["got"]) + ("" if b["sell"] is not None else " (if sold)"),
            "Profit / loss": inr(b["pnl"], sign=True), "%": pct(b["pnl_pct"]), "Sessions": b["held"],
            "Kyo profit ya loss": an.trade_reason(b), "Exit reason": b["exit_reason"],
            "Charges": inr(b["charges"]), "Money after": inr(b["cash_after"]),
        } for i, b in enumerate(book)])
        st.dataframe(table.style.apply(money_style, subset=["Profit / loss", "%"]).apply(quad_style, subset=["Daily at signal"]),
                     hide_index=True, width="stretch", height=38 + 35 * min(15, len(table)))
        st.download_button("Download trades as CSV", table.to_csv(index=False),
                           file_name="%s_daily_rrg_strategy_trades.csv" % sym.lower(), mime="text/csv")
    else:
        st.info("No buy signal since %s, so the money stayed in cash." % start.strftime("%d %b %Y"))
    st.caption("Starts on the first RRG session after the warm-up (%s). Whole shares only; value marked at each "
               "day's close after sell charges. Historical test, not advice." % start.strftime("%d %b %Y"))

# ================================================================ ALL STOCKS PAGE
elif page == "All stocks":
    st.markdown("#### All Stocks Comparison (Daily RRG on %s) against %s" % (BASIS, BENCH))
    c1, c2, c3 = st.columns([1, 1.4, 1.2])
    tag = c1.selectbox("Show tag", ["All"] + core.TAGS, format_func=lambda t: "%s (%d)" % (t, len(core.stocks_for_tag(t))))
    tag_syms = core.stocks_for_tag(tag)
    sectors = sorted({an.sector(s) for s in tag_syms})
    pick = c2.multiselect("Filter by sector", sectors, default=sectors)
    q_all = c3.text_input("🔍 Search", key="search_all", placeholder="name, ticker, sector, tag")
    syms = an.search_stocks([s for s in tag_syms if an.sector(s) in pick], q_all)
    if q_all and not syms:
        st.warning("No stock matches “%s”." % q_all)
        st.stop()
    rows = []
    for s in syms:
        g = safe_load(s, token, sma)
        name = INFO[s]["name"]
        base = {"Stock": name, "Symbol": s, "Tags": core.tag_text(s), "Sector": an.sector(s),
                "Listed": INFO[s]["listed"].strftime("%d %b %Y")}
        if g is None:
            rows.append(dict(base, Note="NSE SME stock — add NSE CSV files" if INFO[s]["source"] == "nse_csv"
                             else "No data"))
            continue
        a, r = g[0], g[1]
        last_px = a["Close"].iloc[-1]
        iss = INFO[s]["issue"]
        base.update({"Issue ₹": iss if iss else None, "Last ₹": round(last_px, 2),
                     "Gain vs issue": pct(100 * (last_px / iss - 1)) if iss else "—"})
        if r.empty:
            rows.append(dict(base, Note="Only %d sessions — too few for RRG" % len(a)))
            continue
        tr, p, px = core.run_strategy(r, stop_loss, cost)
        bk, cs, val, bh, _ = an.simulate(r, tr, capital, cost)
        mm = an.metrics(bk, val, bh, capital)
        rows.append(dict(base, **{"Daily quad": r["Quadrant"].iloc[-1], "RS-Ratio": round(r["RS_Ratio"].iloc[-1], 2),
                                  "RS-Mom": round(r["RS_Momentum"].iloc[-1], 2),
                                  "Days in quad": int(an.periods(r).iloc[0]["Sessions"]),
                                  "Latest date": r.index[-1].strftime("%d %b %Y"),
                                  "Strategy": pct(mm["ret"]), "Buy & hold": pct(mm["bh_ret"]),
                                  "Trades": len(tr), "Now": "BUY next day" if p else ("SELL next day" if px else
                                                                                     ("HOLD" if tr and tr[-1]["open"] else "WAIT")),
                                  "Note": ""}))
    df = pd.DataFrame(rows)
    sty = df.style
    if "Daily quad" in df:
        sty = sty.apply(quad_style, subset=["Daily quad"]).apply(money_style, subset=["Gain vs issue", "Strategy", "Buy & hold"])
    st.dataframe(sty, hide_index=True, width="stretch", height=38 + 35 * len(df))
    st.caption("Strategy and buy & hold use %s from each stock's first RRG session (after the warm-up), after charges."
               % inr(capital))

    st.subheader("All selected stocks on one RRG")
    c1, c2 = st.columns(2)
    m_tail = c1.slider("Tail (sessions)", 3, 20, 8, key="mtail")
    m_sess = c2.slider("Slider covers last N sessions", 20, 200, 60, 10, key="msess")
    html = multi_html(tuple(syms), token, m_tail, m_sess, sma)
    if html is None:
        st.warning("No selected stock has enough history for the RRG.")
    else:
        chart_frame(html)
        st.caption("Drag the slider (or click the chart and use ← / →) to move every stock's tail through time. "
                   "Labels are NSE symbols; hover a dot for the name, date and quadrant. A stock appears from its "
                   "first RRG session.")

# ================================================================ RULES PAGE
else:
    st.markdown("""
#### How the Daily RRG is calculated
- **RS** = stock close ÷ NIFTY 50 close (only dates both traded; nothing filled in)
- **SMA price option** (sidebar → *RRG built on* → *SMA price*): RS = N-day SMA of the stock close ÷ N-day SMA of the
  NIFTY 50 close (14 days by default). The rest of the formula is the same. This smooths out day-to-day noise, so
  quadrants change less often (fewer false buys/sells), but signals come a few days later. Buys, sells and the
  stop-loss still use the real prices, and the RRG starts on the same date as the daily-close version.
- **RS-Ratio** = 100 × EMA(SMA(RS, 5), 5) ÷ EMA(SMA(RS, 5), 30)
- **RS-Momentum** = 100 × EMA(RS-Ratio, 3) ÷ EMA(RS-Ratio, 14)
- Quadrants: **Leading** (Ratio ≥ 100, Momentum ≥ 100), **Weakening** (Ratio ≥ 100, Momentum < 100),
  **Lagging** (both < 100), **Improving** (Ratio < 100, Momentum ≥ 100)
- A new IPO has no history before listing, so the first third of its sessions (at most 200) are only used to
  warm up the EMAs and are not shown.

#### Strategy — Strategy 2 Version 3 rules on the **Daily** RRG
- **Buy** on the first day the Daily RRG is in **Leading** or **Improving**: bought on the next trading day at the
  average of that day's open and close.
- **Sell** on the first day the Daily RRG is in **Weakening** or **Lagging**: sold on the next trading day at the
  average of its open and close.
- **Stop-loss:** any day's close at or below the buy price minus the stop-loss % (10% or 15%, chosen in the sidebar) sells that day at that
  close. After a stop-loss it buys again only after the Daily RRG has gone into Weakening/Lagging and come back up.
- One position at a time, whole shares, charges per side as set in the sidebar.

#### Data checks (same as the help folder)
Positive prices, no missing values, no duplicate dates, dates in order, nothing before listing, latest date not in the
future, no weekend dates; one-day moves larger than ±25% are flagged. Stock and NIFTY 50 are joined only on dates
both traded — no forward-fill, no interpolation.

Formula, rules and checks come from the help folder (*RRG Graph app*); the only change is Daily instead of Weekly RRG.
This is a historical test, not advice.
""")
