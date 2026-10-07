#!/usr/bin/env python3
"""Verify both published Maia corpora and build the casual/rated supplement.

Standard library only. All findings are derived from the CSV.gz files in this
repository; the private collection databases and Lichess token are not needed.
"""

import collections
import csv
import datetime as dt
import gzip
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOTS = ("maia1", "maia5", "maia9")
START = int(dt.datetime(2023, 10, 4, tzinfo=dt.timezone.utc).timestamp() * 1000)
END = int(dt.datetime(2026, 10, 4, 9, tzinfo=dt.timezone.utc).timestamp() * 1000)
MONTHS = [f"{year}-{month:02d}" for year in range(2023, 2027)
          for month in range(1, 13)
          if "2023-11" <= f"{year}-{month:02d}" <= "2026-09"]
EXPECTED = {"rated": 1425567, "casual": 2040728}
COLORS = {"rated": "#95684d", "casual": "#367451"}


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def control_label(initial, increment):
    if initial is None or increment is None:
        return "No recorded clock"
    return f"{initial // 60}+{increment}" if initial % 60 == 0 else f"{initial}s+{increment}s"


def scan(kind, seen):
    folder = ROOT / "data" / f"{kind}-games"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["records"] == EXPECTED[kind]
    result = {
        "entries": 0, "per_bot": collections.Counter(), "monthly": collections.Counter(),
        "monthly_accounts": collections.defaultdict(set),
        "sept_account_games": collections.Counter(),
        "sept_account_bot": collections.Counter(),
        "sept_account_clock": collections.Counter(),
        "speed": collections.Counter(), "controls": collections.Counter(),
        "accounts": collections.Counter(), "account_rating": collections.defaultdict(lambda: [0, 0]),
        "rating_sum": 0, "rating_n": 0, "bot_decisive": collections.Counter(),
        "bot_wins": collections.Counter(), "no_winner": collections.Counter(),
        "missing_opponent": 0, "missing_rating": 0, "missing_clock": 0,
        "source": collections.Counter(), "variant": collections.Counter(),
        "shards": [],
    }
    for shard in manifest["shards"]:
        path = folder / shard["file"]
        assert path.stat().st_size == shard["bytes"], path
        assert file_sha256(path) == shard["sha256"], path
        rows = 0
        with gzip.open(path, "rt", encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            assert reader.fieldnames == manifest["fields"]
            for row in reader:
                rows += 1
                game_id = row["game_id"]
                assert game_id and game_id not in seen, (kind, game_id)
                seen.add(game_id)
                bot = row["bot"]
                assert bot in BOTS
                timestamp = int(row["last_move_at_ms"])
                assert START <= timestamp < END
                month = dt.datetime.fromtimestamp(timestamp / 1000, dt.timezone.utc).strftime("%Y-%m")
                assert shard["file"] == f"{bot}_{month[:4]}.csv.gz"
                assert row["bot_color"] in ("white", "black")
                result["entries"] += 1
                result["per_bot"][bot] += 1
                result["monthly"][(month, bot)] += 1
                result["speed"][row["speed"]] += 1
                result["source"][row["source"]] += 1
                result["variant"][row["variant"]] += 1
                if row["clock_initial_seconds"] and row["clock_increment_seconds"]:
                    label = control_label(int(row["clock_initial_seconds"]),
                                          int(row["clock_increment_seconds"]))
                else:
                    label = "No recorded clock"
                    result["missing_clock"] += 1
                result["controls"][label] += 1
                opponent = row["opponent_id"]
                if opponent:
                    result["accounts"][opponent] += 1
                    result["monthly_accounts"][month].add(opponent)
                    if kind == "casual" and month == "2026-09":
                        result["sept_account_games"][opponent] += 1
                        result["sept_account_bot"][(opponent, bot)] += 1
                        result["sept_account_clock"][(opponent, label)] += 1
                else:
                    result["missing_opponent"] += 1
                if row["opponent_rating"]:
                    rating = int(row["opponent_rating"])
                    result["rating_sum"] += rating
                    result["rating_n"] += 1
                    if opponent:
                        cell = result["account_rating"][opponent]
                        cell[0] += rating
                        cell[1] += 1
                else:
                    result["missing_rating"] += 1
                winner = row["winner"]
                if winner in ("white", "black"):
                    result["bot_decisive"][bot] += 1
                    if winner == row["bot_color"]:
                        result["bot_wins"][bot] += 1
                else:
                    result["no_winner"][bot] += 1
        assert rows == shard["rows"]
        result["shards"].append({"file": shard["file"], "rows": rows, "sha256": shard["sha256"]})
    assert result["entries"] == manifest["records"] == EXPECTED[kind]
    assert len(seen) == sum(EXPECTED[x] for x in ("rated", "casual")
                            if x == kind or kind == "casual")
    return result


def summarize(raw):
    entries = raw["entries"]
    accounts = raw["accounts"]
    n_accounts = len(accounts)
    top_one = sum(sorted(accounts.values(), reverse=True)[:round(n_accounts * .01)])
    account_means = [total / count for total, count in raw["account_rating"].values()]
    months = {month: sum(raw["monthly"][(month, bot)] for bot in BOTS) for month in MONTHS}
    return {
        "bot_game_entries": entries, "unique_games": entries, "per_bot": dict(raw["per_bot"]),
        "opposing_accounts": n_accounts, "missing_opponent_ids": raw["missing_opponent"],
        "missing_opponent_ratings": raw["missing_rating"], "missing_clocks": raw["missing_clock"],
        "speed": dict(raw["speed"]), "top_controls": [
            {"label": label, "games": count} for label, count in raw["controls"].most_common(10)
        ],
        "rating": {
            "game_weighted_mean": round(raw["rating_sum"] / raw["rating_n"]),
            "account_weighted_mean": round(sum(account_means) / len(account_means)),
        },
        "accounts": {
            "one_game": sum(n == 1 for n in accounts.values()),
            "top_one_percent_game_share": round(top_one / entries, 4),
        },
        "bot_win_share_of_decisive": {
            bot: round(raw["bot_wins"][bot] / raw["bot_decisive"][bot], 4) for bot in BOTS
        },
        "games_without_winner": sum(raw["no_winner"].values()),
        "first_12_complete_months": sum(months[m] for m in MONTHS[:12]),
        "last_12_complete_months": sum(months[m] for m in MONTHS[-12:]),
        "partial_october": {
            month: sum(raw["monthly"][(month, bot)] for bot in BOTS)
            for month in ("2023-10", "2026-10")
        },
        "source": dict(raw["source"]), "variant": dict(raw["variant"]),
    }


def line_chart(months, accounts=False):
    width, height = 1000, 290
    left, right, top, bottom = 65, 25, 28, 43
    suffix = "_accounts" if accounts else ""
    step = 1000 if accounts else 10000
    high = max(point[kind + suffix] for point in months for kind in ("rated", "casual"))
    high = (high // step + 1) * step
    x = lambda idx: left + idx * (width - left - right) / (len(months) - 1)
    y = lambda value: height - bottom - value * (height - top - bottom) / high
    metric = "active opposing accounts" if accounts else "games"
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Monthly rated and casual Maia {metric}, November 2023 to September 2026">']
    for tick in range(0, high + 1, 2 * step):
        parts.append(f'<line x1="{left}" y1="{y(tick):.1f}" x2="{width-right}" y2="{y(tick):.1f}" stroke="#d8dfd6"/>')
        parts.append(f'<text x="{left-9}" y="{y(tick)+4:.1f}" text-anchor="end" font-size="11" fill="#65736a">{tick//1000}k</text>')
    for kind in ("rated", "casual"):
        points = " ".join(f"{x(i):.1f},{y(point[kind + suffix]):.1f}" for i, point in enumerate(months))
        parts.append(f'<polyline points="{points}" fill="none" stroke="{COLORS[kind]}" stroke-width="3" stroke-linejoin="round"/>')
    for i, point in enumerate(months):
        if point["month"].endswith("-01") or i in (0, len(months)-1):
            parts.append(f'<text x="{x(i):.1f}" y="{height-12}" text-anchor="middle" font-size="11" fill="#4c6257">{point["month"]}</text>')
    parts.append("</svg>")
    return "".join(parts)


def bar(label, rated, casual, max_value, suffix=""):
    esc = html.escape(label)
    return (f'<div class="bar-group"><div class="bar-label">{esc}</div>'
            f'<div class="bar-row"><span>Rated</span><i style="width:{100*rated/max_value:.1f}%;background:{COLORS["rated"]}"></i><b>{rated:,.0f}{suffix}</b></div>'
            f'<div class="bar-row"><span>Casual</span><i style="width:{100*casual/max_value:.1f}%;background:{COLORS["casual"]}"></i><b>{casual:,.0f}{suffix}</b></div></div>')


def render(data):
    rated, casual = data["rated"], data["casual"]
    overlap = data["account_overlap"]
    months = data["monthly_complete"]
    share = 100 * casual["bot_game_entries"] / (rated["bot_game_entries"] + casual["bot_game_entries"])
    bot_max = max(x for kind in (rated, casual) for x in kind["per_bot"].values())
    bot_bars = "".join(bar(bot.replace("maia", "Maia "), rated["per_bot"][bot], casual["per_bot"][bot], bot_max)
                       for bot in BOTS)
    speed_max = max(x for kind in (rated, casual) for x in kind["speed"].values())
    speed_bars = "".join(bar(speed.title(), rated["speed"].get(speed, 0), casual["speed"].get(speed, 0), speed_max)
                         for speed in ("rapid", "blitz", "classical", "bullet"))
    controls = "".join(
        f'<tr><td>{html.escape(kind.title())}</td><td>{html.escape(item["label"])}</td>'
        f'<td>{item["games"]:,}</td><td>{item["games"] / data[kind]["bot_game_entries"]:.1%}</td></tr>'
        for kind in ("rated", "casual") for item in data[kind]["top_controls"][:5]
    )
    monthly_rows = "".join(
        f'<tr><td>{point["month"]}</td><td>{point["rated"]:,}</td><td>{point["casual"]:,}</td>'
        f'<td>{point["casual_share_pct"]:.1f}%</td><td>{point["rated_accounts"]:,}</td>'
        f'<td>{point["casual_accounts"]:,}</td></tr>' for point in months
    )
    growth_r = 100 * (rated["last_12_complete_months"] / rated["first_12_complete_months"] - 1)
    growth_c = 100 * (casual["last_12_complete_months"] / casual["first_12_complete_months"] - 1)
    outlier = data["september_2026_concentration"]
    first_share = 100 * casual["first_12_complete_months"] / (casual["first_12_complete_months"] + rated["first_12_complete_months"])
    last_share = 100 * casual["last_12_complete_months"] / (casual["last_12_complete_months"] + rated["last_12_complete_months"])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Casual versus rated · Maia research supplement</title><style>
:root{{--ink:#193e32;--muted:#53695e;--paper:#f5f5ed;--line:#d7dfd4;--rated:{COLORS["rated"]};--casual:{COLORS["casual"]}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1060px;margin:auto;padding:0 32px}}a{{color:inherit}}h1,h2{{font-family:Georgia,serif;font-weight:400;line-height:1.06}}h1{{font-size:clamp(48px,7vw,78px);margin:12px 0 20px}}h2{{font-size:39px;margin:0 0 19px}}h3{{font-size:19px;margin:8px 0}}
p{{margin:0 0 18px}}.eyebrow{{font-size:11px;text-transform:uppercase;letter-spacing:2px;font-weight:800}}.muted,.note{{color:var(--muted)}}.note{{font-size:12px}}
header{{padding:58px 0 40px;border-bottom:1px solid var(--line)}}header p.lead{{font-size:21px;max-width:790px}}.legend{{display:flex;gap:20px;font-size:13px;font-weight:700;margin:17px 0}}.legend span:before{{content:"";display:inline-block;width:12px;height:12px;margin-right:7px;background:var(--rated)}}.legend span.casual:before{{background:var(--casual)}}
.stat-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:30px 0}}.stat{{background:#e8eee5;padding:18px;border-top:4px solid var(--ink)}}.stat b{{font:36px Georgia,serif;display:block}}.stat span{{font-size:12px}}section{{padding:49px 0;border-bottom:1px solid var(--line)}}figure{{margin:22px 0}}figure svg{{display:block;width:100%;background:#fff;padding:12px;border:1px solid var(--line)}}figcaption{{font-size:12px;color:var(--muted);margin-top:8px}}
.columns{{display:grid;grid-template-columns:1fr 1fr;gap:32px}}.bar-group{{margin:14px 0 20px}}.bar-label{{font-weight:750;margin-bottom:5px}}.bar-row{{display:grid;grid-template-columns:53px 1fr 85px;gap:10px;align-items:center;font-size:12px;margin:4px 0}}.bar-row i{{display:block;height:13px;min-width:1px}}.bar-row b{{text-align:right}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:18px 0}}th,td{{padding:7px 10px;border-bottom:1px solid var(--line);text-align:right}}th:first-child,td:first-child{{text-align:left}}th{{background:#e6ede4}}.scroll{{max-height:430px;overflow:auto;border:1px solid var(--line)}}.scroll table{{margin:0}}.callout{{padding:18px;background:#e5ecdf;border-left:4px solid var(--casual)}}.pill{{display:inline-block;background:#e1e9db;padding:3px 9px;font-size:12px;font-weight:700;margin-right:6px}}footer{{padding:30px 0 55px;font-size:12px;color:var(--muted)}}
@media(max-width:720px){{main{{padding:0 18px}}.stat-grid,.columns{{grid-template-columns:1fr}}h2{{font-size:32px}}}}
@media print{{@page{{size:A4;margin:14mm}}*{{print-color-adjust:exact;-webkit-print-color-adjust:exact}}body{{font-size:10px}}main{{padding:0}}header{{padding:5px 0 8px}}h1{{font-size:40px;margin:7px 0}}h2{{font-size:26px;margin:0 0 10px}}h3{{font-size:15px;margin:5px 0}}header p.lead{{font-size:12px;margin:0 0 7px}}p{{margin:0 0 9px}}.stat-grid{{gap:8px;margin:10px 0}}.stat{{padding:8px}}.stat b{{font-size:25px}}section{{padding:12px 0}}section:nth-of-type(2),section:nth-of-type(3){{break-before:page}}.columns{{gap:15px}}.bar-group{{margin:5px 0 8px}}figure{{margin:9px 0}}figure svg{{max-height:155px}}.callout{{padding:9px}}.scroll{{max-height:none;overflow:visible}}.monthly-table{{font-size:9px}}.monthly-table th,.monthly-table td{{padding:3px 6px}}table{{font-size:9px;margin:7px 0;break-inside:avoid}}th,td{{padding:3px 6px}}.note,figcaption,footer{{font-size:8px}}.stat,figure,.callout,.bar-group{{break-inside:avoid}}h2,h3,.eyebrow{{break-after:avoid}}footer{{padding:12px 0}}}}
</style></head><body><main><header><div class="eyebrow">Independent Maia research · October 2026 supplement</div>
<h1>Casual play changes the picture.</h1><p class="lead">A like-for-like three-year comparison of games against the official Maia 1, 5, and 9 Lichess accounts—same bots, same last-move window, separate rated and casual exports.</p>
<div class="stat-grid"><div class="stat"><b>{casual["bot_game_entries"]:,}</b><span>casual games</span></div><div class="stat"><b>{rated["bot_game_entries"]:,}</b><span>rated games</span></div><div class="stat"><b>{share:.1f}%</b><span>casual share of combined games</span></div></div>
<p class="note">One bot-game entry is a game attached to one Maia account. No game ID occurs in both exports or under two bots in this window, so entry counts equal unique games. Scope: last recorded move from 2023-10-04 00:00 UTC through before 2026-10-04 09:00 UTC. No moves/PGNs were collected.</p></header>
<section><div class="eyebrow">01 / Growth</div><h2>Both formats grew; rated grew faster.</h2><p>Across the first and last complete 12-month periods, casual play changed by <strong>{growth_c:+.1f}%</strong> ({casual["first_12_complete_months"]:,} → {casual["last_12_complete_months"]:,}); rated play changed by <strong>{growth_r:+.1f}%</strong> ({rated["first_12_complete_months"]:,} → {rated["last_12_complete_months"]:,}). Casual's share of combined games fell from <strong>{first_share:.1f}%</strong> to <strong>{last_share:.1f}%</strong>. These are counts, not a measure of unique people.</p>
<div class="legend"><span>Rated</span><span class="casual">Casual</span></div><figure>{line_chart(months)}<figcaption>Complete UTC months only, November 2023–September 2026. Partial October 2023 and October 2026 are excluded. Monthly values are bot-game entries; here they also equal unique games.</figcaption></figure>
<div class="callout"><strong>September's casual spike is concentrated.</strong> Public account <a href="https://lichess.org/@/{html.escape(outlier["handle"])}">{html.escape(outlier["handle"])}</a> recorded {outlier["games"]:,} casual games that month—{outlier["share_of_september_pct"]:.1f}% of all casual September games, mostly Maia 1 at 1+0. Without this one account, September has {outlier["september_without_account"]:,} casual games versus {outlier["august_games"]:,} in August; last-year casual growth would be {outlier["growth_excluding_account_pct"]:+.1f}% rather than {growth_c:+.1f}%. This is a sensitivity check, not a judgment about the account.</div>
<h3>Monthly active opposing accounts</h3><figure>{line_chart(months, accounts=True)}<figcaption>Distinct public handles observed in each UTC month, separately by format. The same account can appear in multiple months and both formats. September 2026 had {outlier["september_accounts"]:,} casual accounts versus {outlier["august_accounts"]:,} in August.</figcaption></figure>
<details><summary>Show all 35 complete months</summary><div class="scroll"><table class="monthly-table"><thead><tr><th>UTC month</th><th>Rated games</th><th>Casual games</th><th>Casual share</th><th>Rated accounts</th><th>Casual accounts</th></tr></thead><tbody>{monthly_rows}</tbody></table></div></details></section>
<section><div class="eyebrow">02 / Bot choice and time controls</div><h2>Casual play is not simply the rated pattern at larger scale.</h2><div class="columns"><div><h3>Games by Maia bot</h3>{bot_bars}</div><div><h3>Games by Lichess speed category</h3>{speed_bars}</div></div><h3>Most common exact clocks</h3><table><thead><tr><th>Format</th><th>Clock</th><th>Games</th><th>Share of format</th></tr></thead><tbody>{controls}</tbody></table><p class="note">Clock format is starting minutes + increment seconds. Counts describe chosen settings, not playing strength. The September account contributed {outlier["one_plus_zero_games"]:,} of the casual 1+0 games, so that clock's raw ranking is unusually sensitive to one account.</p></section>
<section><div class="eyebrow">03 / Who plays and how outcomes differ</div><h2>Account mix matters more than a raw win-rate comparison.</h2><div class="stat-grid"><div class="stat"><b>{casual["opposing_accounts"]:,}</b><span>opposing casual accounts</span></div><div class="stat"><b>{rated["opposing_accounts"]:,}</b><span>opposing rated accounts</span></div><div class="stat"><b>{overlap["both"]:,}</b><span>accounts found in both exports</span></div></div>
<p>{overlap["casual_only"]:,} handles appear only in casual games in this window; {overlap["rated_only"]:,} appear only in rated games. Handles are public Lichess account IDs, not verified unique people.</p>
<div class="columns"><div><h3>Opponent Lichess rating</h3><p><span class="pill">Per game</span> casual <strong>{casual["rating"]["game_weighted_mean"]:,}</strong> · rated <strong>{rated["rating"]["game_weighted_mean"]:,}</strong></p><p><span class="pill">Per account</span> casual <strong>{casual["rating"]["account_weighted_mean"]:,}</strong> · rated <strong>{rated["rating"]["account_weighted_mean"]:,}</strong></p><p class="note">Game-weighted means give frequent players more influence. Account-weighted means first average each handle's recorded ratings, then weight handles equally. These are Lichess ratings, not FIDE Elo.</p></div>
<div><h3>Maia wins among decisive games</h3><table><thead><tr><th>Bot</th><th>Rated</th><th>Casual</th></tr></thead><tbody>{''.join(f'<tr><td>Maia {bot[-1]}</td><td>{rated["bot_win_share_of_decisive"][bot]:.1%}</td><td>{casual["bot_win_share_of_decisive"][bot]:.1%}</td></tr>' for bot in BOTS)}</tbody></table><p class="note">Excludes games with no winning side. Rating, clock, opponent selection, and repeated players differ; these percentages do not isolate the effect of the rated setting.</p></div></div>
<p class="callout">The same players often use both formats, but a simple casual-versus-rated comparison is observational. It cannot show that a format causes improvement or changes Maia's playing strength.</p></section>
<section><div class="eyebrow">04 / Audit and access</div><h2>Rebuild the comparison from the published metadata.</h2><p>The <a href="data/casual-games/README.md">casual export</a> contains all {casual["bot_game_entries"]:,} collected metadata rows in 12 compressed bot/year files. The <a href="data/rated-games/README.md">rated export</a> contains {rated["bot_game_entries"]:,} rows. Both manifests include SHA-256 checksums, row counts, and field definitions. Run <code>python3 scripts/build_casual_comparison.py</code> at the repository root to recheck every shard and regenerate this page and the <a href="data/casual_comparison.json">aggregate JSON</a>.</p>
<p>Exports include game IDs, public handles where available, timestamps, results, speed, clock, opening labels, and recorded ratings. They do not include moves, PGNs, chat, or private identity mappings. The collection used date splitting below Lichess's observed response cap, then verified gap-free query-date coverage and in-scope last-move timestamps. A seven-day game-start lookback reduces—but cannot prove away—the possibility of an unusually long game that began earlier and finished inside the study window.</p>
<p class="note">Source: <a href="https://lichess.org/api#operation/apiGamesUser">Lichess user-game export</a>. The repository MIT license covers original code and report writing, not Lichess or player-originated game data. This is independent fan research, not an official Lichess/Maia publication.</p></section>
<footer>Supplement to <a href="index.html">How people play the Maia bots on Lichess</a>. Findings are descriptive and limited to the fixed three-year study window.</footer></main></body></html>'''


def main():
    seen = set()
    rated_raw = scan("rated", seen)
    rated_accounts = set(rated_raw["accounts"])
    casual_raw = scan("casual", seen)
    casual_accounts = set(casual_raw["accounts"])
    rated, casual = summarize(rated_raw), summarize(casual_raw)
    monthly = [{"month": month,
                "rated": sum(rated_raw["monthly"][(month, bot)] for bot in BOTS),
                "casual": sum(casual_raw["monthly"][(month, bot)] for bot in BOTS),
                "rated_accounts": len(rated_raw["monthly_accounts"][month]),
                "casual_accounts": len(casual_raw["monthly_accounts"][month])}
               for month in MONTHS]
    for point in monthly:
        point["casual_share_pct"] = round(100 * point["casual"] / (point["rated"] + point["casual"]), 1)
    top_handle, top_games = casual_raw["sept_account_games"].most_common(1)[0]
    sep = next(point for point in monthly if point["month"] == "2026-09")
    aug = next(point for point in monthly if point["month"] == "2026-08")
    concentration = {
        "handle": top_handle, "games": top_games,
        "share_of_september_pct": round(100 * top_games / sep["casual"], 1),
        "september_without_account": sep["casual"] - top_games,
        "august_games": aug["casual"],
        "september_accounts": sep["casual_accounts"],
        "august_accounts": aug["casual_accounts"],
        "one_plus_zero_games": casual_raw["sept_account_clock"][(top_handle, "1+0")],
        "by_bot": {bot: casual_raw["sept_account_bot"][(top_handle, bot)] for bot in BOTS},
        "growth_excluding_account_pct": round(100 * ((casual["last_12_complete_months"] - top_games) / casual["first_12_complete_months"] - 1), 1),
    }
    data = {
        "scope": {"start_utc_inclusive": "2023-10-04T00:00:00Z",
                  "end_utc_exclusive": "2026-10-04T09:00:00Z",
                  "time_basis": "last recorded move (last_move_at_ms)"},
        "rated": rated, "casual": casual,
        "combined_unique_games": rated["unique_games"] + casual["unique_games"],
        "account_overlap": {"both": len(rated_accounts & casual_accounts),
                            "rated_only": len(rated_accounts - casual_accounts),
                            "casual_only": len(casual_accounts - rated_accounts)},
        "monthly_complete": monthly,
        "september_2026_concentration": concentration,
        "limitations": [
            "Partial October 2023 and October 2026 are excluded from month comparisons.",
            "Account handles are not verified unique people; prolific accounts affect game-weighted metrics.",
            "A seven-day game-start lookback cannot guarantee capture of games lasting longer than seven days across the starting edge.",
            "No moves, PGNs, or chat were collected; opening names are source metadata.",
            "Rated and casual players, clocks, and bot choices differ. Descriptive comparisons are not causal effects.",
        ],
    }
    (ROOT / "data" / "casual_comparison.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (ROOT / "casual-vs-rated.html").write_text(render(data), encoding="utf-8")
    with (ROOT / "data" / "casual_comparison_monthly.csv").open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=("month", "rated", "casual", "casual_share_pct", "rated_accounts", "casual_accounts"), lineterminator="\n")
        writer.writeheader()
        writer.writerows(monthly)
    print(json.dumps({"rated": rated["bot_game_entries"], "casual": casual["bot_game_entries"],
                      "account_overlap": data["account_overlap"],
                      "growth_rated_pct": round(100 * (rated["last_12_complete_months"] / rated["first_12_complete_months"] - 1), 1),
                      "growth_casual_pct": round(100 * (casual["last_12_complete_months"] / casual["first_12_complete_months"] - 1), 1)}, indent=2))


if __name__ == "__main__":
    main()
