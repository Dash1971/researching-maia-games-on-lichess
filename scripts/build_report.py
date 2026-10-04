"""Build a self-contained, plain-language HTML report from aggregate data."""

import html
import json
import datetime as dt
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "data" / "summary.json").read_text(encoding="utf-8"))
ACCOUNTS = DATA["accounts"]
_local_date = dt.datetime.fromisoformat(DATA["collected_utc"]).astimezone(dt.timezone(dt.timedelta(hours=9)))
REPORT_DATE = f"{_local_date.strftime('%B')} {_local_date.day}, {_local_date.year}"
BOT_NAMES = {"maia1": "Maia 1", "maia5": "Maia 5", "maia9": "Maia 9"}
COLORS = {"maia1": "#4a9f8a", "maia5": "#d59a48", "maia9": "#866bb3"}


def number(value):
    return f"{value:,}"


def pct(value, total, digits=1):
    return f"{100 * value / total:.{digits}f}%"


def stack(parts):
    return '<div class="stack">' + "".join(
        f'<span style="width:{100 * value / total:.3f}%;background:{color}" title="{html.escape(label)}: {number(value)}"></span>'
        for label, value, total, color in parts
    ) + '</div>'


all_games = sum(row["profile_count"]["all"] for row in ACCOUNTS.values())
rated_games = sum(row["profile_count"]["rated"] for row in ACCOUNTS.values())
casual_games = all_games - rated_games
cross_bot_games = sum(DATA["cross_bot_games"].values())
distinct_games = all_games - cross_bot_games
bot_one_share = ACCOUNTS["maia1"]["profile_count"]["all"] / all_games

volume_cards = []
color_cards = []
speed_cards = []
opening_cards = []
for bot, row in ACCOUNTS.items():
    name, color = BOT_NAMES[bot], COLORS[bot]
    counts = row["profile_count"]
    casual = counts["all"] - counts["rated"]
    volume_cards.append(f'''<article class="bot-card" style="--accent:{color}">
      <div class="bot-title"><span class="dot"></span><h3>{name}</h3><a href="https://lichess.org/@/{bot}">Lichess profile ↗</a></div>
      <strong class="big">{number(counts["all"])}</strong><small>all recorded games at collection time</small>
      {stack([("Rated", counts["rated"], counts["all"], color), ("Casual", casual, counts["all"], "#dfe5e8")])}
      <p class="legend"><b style="color:{color}">■</b> {pct(counts["rated"], counts["all"])} rated &nbsp; <b style="color:#a6b5be">■</b> {pct(casual, counts["all"])} casual</p>
      <p class="micro">Bot wins {pct(counts["win"], counts["all"])} · draws {pct(counts["draw"], counts["all"])} · losses {pct(counts["loss"], counts["all"])}</p>
    </article>''')

    color_data = row["insights"]["color"]
    colors = dict(zip(color_data["categories"], color_data["counts"]))
    color_cards.append(f'''<div class="chart-row"><b>{name}</b>
      {stack([("Maia White", colors["White"], 15000, color), ("Maia Black", colors["Black"], 15000, "#293b55")])}
      <span>{pct(colors["White"], 15000)} White / {pct(colors["Black"], 15000)} Black</span></div>''')

    speed = row["insights"]["time_control"]
    speed_map = dict(zip(speed["categories"], speed["counts"]))
    speed_colors = {"Bullet": "#c3d3d5", "Blitz": "#8dbbb0", "Rapid": color, "Classical": "#34455c"}
    speed_cards.append(f'''<div class="chart-row"><b>{name}</b>
      {stack([(label, speed_map[label], 15000, speed_colors[label]) for label in ("Bullet", "Blitz", "Rapid", "Classical")])}
      <span>{pct(speed_map["Rapid"], 15000)} rapid · {pct(speed_map["Blitz"], 15000)} blitz</span></div>''')

    op = row["insights"]["opening_all"]
    openings = []
    for label, count in list(zip(op["categories"], op["counts"]))[:6]:
        openings.append(f'''<div class="opening-line"><span>{html.escape(label)}</span>
          <div class="track"><i style="width:{100 * count / 15000:.2f}%;background:{color}"></i></div>
          <b>{pct(count, 15000)}</b></div>''')
    opening_cards.append(f'''<article class="opening-card"><h3 style="color:{color}">{name}</h3>{"".join(openings)}</article>''')

sicilian = {bot: dict(zip(row["insights"]["opening_all"]["categories"], row["insights"]["opening_all"]["counts"]))["Sicilian Defense"] for bot, row in ACCOUNTS.items()}
sample_end = ", ".join(f'{BOT_NAMES[bot]}: {row["sample_newest_bin_date_utc"]}' for bot, row in ACCOUNTS.items())

document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Millions of games with Maia · Lichess research snapshot</title>
<style>
:root {{ font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:#172638; background:#f5f3ed; }}
* {{ box-sizing:border-box }} body {{ margin:0 }} .wrap {{ max-width:1120px;margin:auto;padding:0 30px }}
a {{ color:#236d70 }} a:hover {{ color:#123c4d }} h1,h2,h3,p {{ margin-top:0 }}
.hero {{ background:#14283b;color:#fff;padding:54px 0 48px;position:relative;overflow:hidden }}
.hero:after {{ content:"♞";position:absolute;font-size:360px;right:4%;top:-105px;color:#ffffff0c;line-height:1 }}
.eyebrow {{ text-transform:uppercase;letter-spacing:.15em;font-size:12px;font-weight:800;color:#96d3c1 }}
h1 {{ font-size:clamp(38px,6vw,66px);line-height:1.02;letter-spacing:-.045em;max-width:730px;margin:15px 0 20px }}
.dek {{ font-size:19px;line-height:1.55;color:#d5e1e8;max-width:700px }}
.hero-meta {{ font-size:12px;color:#a8c0ca;margin-top:28px }}
main {{ padding:32px 0 64px }} section {{ margin:30px 0 42px;break-inside:avoid }}
.metrics {{ display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:-60px;position:relative }}
.metric {{ background:#fff;border-radius:18px;padding:20px 22px;box-shadow:0 7px 25px #13263b13 }}
.metric strong {{ font-size:33px;letter-spacing:-.04em;display:block }} .metric span {{ color:#5d6a78;font-size:13px;line-height:1.45 }}
.section-head {{ display:flex;align-items:baseline;justify-content:space-between;gap:20px;border-bottom:1px solid #d9dedb;padding-bottom:10px;margin-bottom:18px }}
h2 {{ font-size:27px;letter-spacing:-.025em;margin:0 }} .section-head p {{ margin:0;color:#667582;font-size:12px }}
.three {{ display:grid;grid-template-columns:repeat(3,1fr);gap:14px }}
.bot-card,.opening-card,.panel,.answer {{ background:#fff;border:1px solid #e3e8e6;border-radius:15px;padding:19px;break-inside:avoid }}
.bot-title {{ display:flex;gap:8px;align-items:center }} .bot-title h3 {{ margin:0;flex:1;font-size:18px }} .bot-title a {{ font-size:11px;white-space:nowrap }}
.dot {{ background:var(--accent);width:10px;height:10px;border-radius:50% }} .big {{ display:block;font-size:32px;margin:16px 0 0;letter-spacing:-.03em }}
small,.micro {{ color:#657582;font-size:12px }} .micro {{ margin:14px 0 0;line-height:1.45 }}
.stack {{ height:16px;width:100%;display:flex;overflow:hidden;border-radius:9px;background:#e5ebed;margin:14px 0 6px }} .stack span {{ height:100%;display:block }}
.legend {{ font-size:12px;color:#596a77;margin:0 }}
.panel {{ padding:24px }} .chart-row {{ display:grid;grid-template-columns:80px 1fr 215px;gap:16px;align-items:center;margin:14px 0 }}
.chart-row .stack {{ margin:0;height:20px }} .chart-row span:last-child {{ color:#61727e;font-size:13px }}
.key {{ display:flex;gap:18px;flex-wrap:wrap;font-size:12px;color:#687782;margin-top:14px }} .swatch {{ display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:5px }}
.opening-card h3 {{ font-size:20px;margin-bottom:18px }} .opening-line {{ display:grid;grid-template-columns:1fr 88px 41px;gap:9px;align-items:center;margin:10px 0;font-size:12px;line-height:1.3 }}
.opening-line .track {{ background:#edf1f1;border-radius:5px;height:10px;overflow:hidden }} .opening-line i {{ display:block;height:100%;min-width:2px;border-radius:5px }} .opening-line b {{ text-align:right }}
.insight {{ border-left:4px solid #d89b44;background:#fff8ec;padding:15px 19px;border-radius:0 12px 12px 0;line-height:1.5;margin:18px 0 }}
.answers {{ display:grid;grid-template-columns:repeat(2,1fr);gap:12px }} .answer h3 {{ font-size:16px;margin:0 0 8px }} .answer p {{ font-size:13px;color:#526474;line-height:1.55;margin:0 }}
.badge {{ font-size:10px;text-transform:uppercase;letter-spacing:.08em;font-weight:800;border-radius:20px;padding:5px 8px;display:inline-block;margin-bottom:10px }}
.yes {{ background:#d8eee7;color:#245c50 }} .no {{ background:#fae9d5;color:#8a5b23 }}
.method {{ background:#e7eceb;border-radius:15px;padding:20px 24px;color:#405565;font-size:13px;line-height:1.65 }} .method p:last-child {{ margin-bottom:0 }}
.sources {{ font-size:12px;line-height:1.8;color:#667582 }} footer {{ border-top:1px solid #dce1df;padding:22px 0 40px;color:#647481;font-size:12px }}
@media(max-width:800px) {{ .metrics,.three,.answers {{ grid-template-columns:1fr }} .metrics {{ margin-top:-25px }} .chart-row {{ grid-template-columns:70px 1fr;gap:8px }} .chart-row span:last-child {{ grid-column:2 }} }}
@media print {{ @page {{ size:A4; margin:14mm }} body {{ background:#fff }} .hero {{ padding:30px 0;color:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact }} .metrics {{ margin-top:12px;grid-template-columns:repeat(3,1fr) }} .metric,.bot-card,.opening-card,.panel,.answer {{ box-shadow:none }} .three {{ grid-template-columns:repeat(3,1fr) }} .answers {{ grid-template-columns:repeat(2,1fr) }} .chart-row {{ grid-template-columns:80px 1fr 215px }} .chart-row span:last-child {{ grid-column:auto }} section {{ margin:22px 0;break-inside:auto }} .section-head {{ break-after:avoid }} .opening-card,.bot-card,.answer {{ break-inside:avoid }} }}
</style></head><body>
<header class="hero"><div class="wrap"><div class="eyebrow">A public-data research snapshot · {REPORT_DATE}</div>
<h1>Millions of games with Maia</h1><p class="dek">What Lichess can tell us about Maia 1, 5, and 9—and what it cannot yet tell us about the people practicing against them.</p>
<p class="hero-meta">Official bot accounts only · Public profile totals plus three stale rated-game Insights samples · Collected {html.escape(DATA["collected_utc"])} UTC</p></div></header>
<main class="wrap"><div class="metrics">
<div class="metric"><strong>{distinct_games / 1_000_000:.2f} million</strong><span>distinct games involving the three bots, after removing their head-to-head overlap</span></div>
<div class="metric"><strong>{pct(casual_games, all_games, 0)}</strong><span>of their recorded games were casual, not rated</span></div>
<div class="metric"><strong>45,000</strong><span>rated account-game records in three Insights overview slices</span></div>
</div>
<section><div class="section-head"><h2>1 · The scale of Maia play</h2><p>Live profile counters; they keep changing</p></div>
<div class="three">{"".join(volume_cards)}</div>
<p class="insight"><b>The headline:</b> Maia 1 accounts for {pct(ACCOUNTS["maia1"]["profile_count"]["all"], all_games)} of bot-account game entries. {number(casual_games)} entries are casual. Only {cross_bot_games} games were between two of these Maia bots; removing that double-counting leaves {number(distinct_games)} distinct games in this snapshot.</p>
</section>
<section><div class="section-head"><h2>2 · Which side does Maia play?</h2><p>15,000 rated games per bot, not lifetime totals</p></div>
<div class="panel">{"".join(color_cards)}<div class="key"><span><i class="swatch" style="background:#6e9e9a"></i>Maia White (bot-specific colors in bars)</span><span><i class="swatch" style="background:#293b55"></i>Maia Black</span></div></div>
<p class="micro">In each available sample, Maia plays Black slightly more often: about 53–54% of games. This may reflect how challengers choose colors; the data does not establish why.</p></section>
<section><div class="section-head"><h2>3 · What kind of games?</h2><p>Same 15,000-game slices</p></div>
<div class="panel">{"".join(speed_cards)}<div class="key"><span><i class="swatch" style="background:#c3d3d5"></i>Bullet</span><span><i class="swatch" style="background:#8dbbb0"></i>Blitz</span><span><i class="swatch" style="background:#d59a48"></i>Rapid (bot-specific colors in bars)</span><span><i class="swatch" style="background:#34455c"></i>Classical</span></div></div>
<p class="micro">Rapid dominates Maia 1’s sample ({pct(ACCOUNTS["maia1"]["insights"]["time_control"]["counts"][2], 15000)}), but Maia 9 has a much larger blitz share ({pct(ACCOUNTS["maia9"]["insights"]["time_control"]["counts"][1], 15000)}). These samples cover different periods, so do not read this as a controlled comparison of bot strength.</p></section>
<section><div class="section-head"><h2>4 · Openings people see against Maia</h2><p>Top families among 15,000 rated games per bot</p></div>
<div class="three">{"".join(opening_cards)}</div>
<p class="insight"><b>An opening pattern:</b> the Sicilian Defense appears in {pct(sicilian["maia1"], 15000)} of Maia 1’s sample, {pct(sicilian["maia5"], 15000)} of Maia 5’s, and {pct(sicilian["maia9"], 15000)} of Maia 9’s. That is a difference in these samples, not evidence that moving to a harder Maia causes people to change openings.</p>
<p class="micro">Opening families describe the resulting position and include moves from both players. These are the top categories returned by Insights, not a complete opening census. Color-filtered queries select a different 15,000-game slice, so they should not be added to these counts.</p></section>
<section><div class="section-head"><h2>5 · Your people questions</h2><p>Answerability is part of the result</p></div>
<div class="answers">
<div class="answer"><span class="badge no">Not measurable yet</span><h3>How many unique accounts played Maia?</h3><p>The public profile counters count games, not distinct opponents. A person can also use multiple accounts. We need game-level opponents for all three bots to count unique Lichess accounts reliably.</p></div>
<div class="answer"><span class="badge no">Not measurable yet</span><h3>Average games per account?</h3><p>That is total bot games divided by unique opposing accounts, after de-duplicating games and deciding how to handle bot opponents. The denominator is unavailable from the working endpoints.</p></div>
<div class="answer"><span class="badge no">Not measurable yet</span><h3>Who plays Maia the most?</h3><p>No honest lifetime leaderboard is possible from aggregate profiles or Insights. Any names from a small visible page would be a biased sample, not the heaviest users.</p></div>
<div class="answer"><span class="badge no">Not established</span><h3>Can we see players improving and graduating?</h3><p>Not without opponent-level games in date order. Even rising win rates could mean repeatable opening tricks or changed time controls. A convincing example would show enough games at each bot level, stronger results over time, and a move to Maia 5 or 9.</p></div>
</div></section>
<section><div class="section-head"><h2>How to read this</h2></div><div class="method">
<p><b>Three public data sources.</b> Game totals, rated totals, and lifetime bot results come from the three <a href="https://lichess.org/api/user/maia1">public profile APIs</a>. Pairwise <a href="https://lichess.org/api/crosstable/maia1/maia5">crosstables</a> identify {cross_bot_games} games between the three bots, which were subtracted once from the sum of profile games. The color, speed, and opening charts come from <a href="https://lichess.org/insights/maia1">Lichess Insights</a> for each account. Insights returned a 15,000-game rated slice for each bot; the indexed collections were marked <i>stale</i>. A game between bots could appear in two Insights slices; 45,000 means account-game records, not necessarily unique game IDs.</p>
<p><b>Not current game samples.</b> The last displayed date-bin labels were {sample_end}. These are chart-bin labels, not exact latest-game timestamps. The samples span different periods and are not random lifetime samples. Do not generalize their percentages to all {number(all_games)} games.</p>
<p><b>Why the missing answers?</b> The documented <a href="https://lichess.org/api#operation/apiGamesUser">user-game export</a> initially returned HTTP 404 with a generic User-Agent; that did not establish an outage. A later two-game request with a custom User-Agent returned HTTP 429 (“Please only run 1 request(s) at a time”) at 2026-10-04 07:39 UTC. A complete lifetime export has not yet been obtained. The <a href="https://database.lichess.org/">monthly open database</a> contains rated games only and would exclude most Maia games; reconstructing opponent histories from it would still be incomplete.</p>
<p><b>Definitions.</b> “Casual” = all profile games minus rated profile games. “Win” means a bot win. “Unique accounts” is not the same as unique people. Official-bot identity was checked against the <a href="https://lichess.org/team/maia-bots">Maia Bots team</a> and <a href="https://lichess.org/player/bots">Lichess featured-bots listing</a>.</p>
</div></section>
<section class="sources"><b>Source links:</b> <a href="https://lichess.org/@/maia1">Maia 1</a> · <a href="https://lichess.org/@/maia5">Maia 5</a> · <a href="https://lichess.org/@/maia9">Maia 9</a> · <a href="https://lichess.org/insights/maia1">Maia 1 Insights</a> · <a href="https://lichess.org/insights/maia5">Maia 5 Insights</a> · <a href="https://lichess.org/insights/maia9">Maia 9 Insights</a> · <a href="https://database.lichess.org/">Lichess open database</a>.<br>Data and reproducible collection code accompany this report. <a href="https://github.com/Dash1971/researching-maia-games-on-lichess/blob/main/RESEARCH_PLAN.md">Read the proposed full-history research plan.</a> No opponent usernames were collected or published.</section>
</main><footer><div class="wrap">Independent fan research · Snapshot, not an official Maia or Lichess publication · Report built {REPORT_DATE}</div></footer></body></html>'''
(ROOT / "index.html").write_text(document, encoding="utf-8")
print(f"Wrote {ROOT / 'index.html'}")
