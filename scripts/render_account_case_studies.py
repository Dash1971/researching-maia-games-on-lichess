#!/usr/bin/env python3
"""Render the validated high-volume account comparison as standalone HTML."""

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "account-cases" / "summary.json"
OUT = ROOT / "maia-account-patterns.html"


def n(value):
    return f"{value:,}"


def pct(part, whole):
    return f"{100 * part / whole:.2f}%"


def day_chart(days, limit=10):
    maximum = max(days.values())
    return "".join(
        f'<div class="bar"><span>{html.escape(day[5:])}</span><i style="width:{100*count/maximum:.1f}%"></i><b>{n(count)}</b></div>'
        for day, count in sorted(days.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    )


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    replay = json.loads((ROOT / "data/account-cases/replay_verification.json").read_text())
    a = data["accounts"]["scissorsharpness"]
    b = data["accounts"]["top1mostplayedgames"]
    a_short = pct(a["plies"]["at_most_six"], a["games"])
    b_one = pct(b["plies"]["one"], b["games"])
    b_zero = pct(b["account_moves"]["zero"], b["games"])
    a_resign = pct(a["status"].get("resign", 0), a["games"])
    b_mate = pct(b["status"].get("mate", 0), b["games"])
    top = b["top_position_and_move"][0]
    setup_rows = "".join(
        f'<tr><td>Setup {i}</td><td>{n(item["games"])}</td><td><code>{html.escape(next((pair["moves"] for pair in b["top_position_and_move"] if pair["fen"] == item["fen"]), "see raw data"))}</code></td></tr>'
        for i, item in enumerate(b["top_initial_positions"], 1)
    )
    html_doc = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Two high-volume Maia accounts · evidence review</title><style>
@page{{size:A4;margin:15mm}}*{{box-sizing:border-box;print-color-adjust:exact;-webkit-print-color-adjust:exact}}
body{{margin:0;background:#f6f5ef;color:#1c3032;font:15px/1.42 Arial,sans-serif}}main{{max-width:880px;margin:auto;padding:35px 28px}}
a{{color:#245c58}}h1,h2{{font-family:Georgia,serif;font-weight:400;line-height:1.07}}h1{{font-size:46px;margin:8px 0 13px}}h2{{font-size:27px;margin:0 0 11px}}
p{{margin:0 0 12px}}.eyebrow{{font-size:11px;letter-spacing:2px;text-transform:uppercase;font-weight:bold;color:#697771}}
.lead{{font-size:19px;color:#415654}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:24px 0}}
.stat{{background:#e3e9dd;padding:14px;border-top:4px solid #3b7867}}.stat b{{display:block;font:29px Georgia,serif}}.stat span{{font-size:11px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}.grid>*{{min-width:0}}.card code{{word-break:break-all}}.card{{border-top:2px solid #618475;padding-top:12px;break-inside:avoid}}
.card h3{{font:23px Georgia,serif;margin:0 0 8px}}.small{{font-size:12px;color:#536664}}.bar{{display:grid;grid-template-columns:47px 1fr 52px;gap:7px;align-items:center;margin:4px 0;font-size:11px}}
.bar i{{height:10px;background:#4d806e;display:block}}.bar b{{text-align:right;font-weight:600}}.bar.alt i{{background:#b47752}}
.rule{{border-top:1px solid #abbcb3;margin:24px 0}}.callout{{background:#e8e6dd;border-left:4px solid #b47752;padding:14px;margin:17px 0;break-inside:avoid}}
.investigation{{margin-top:26px}}.investigation h2{{margin-top:16px}}.steps{{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:15px 0}}.steps div{{background:#e9eee5;padding:10px;font-size:11px}}
code{{font-size:12px;overflow-wrap:anywhere}}.methods{{background:#e9eee5;padding:16px;margin-top:24px;font-size:12px;break-inside:avoid}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:12px 0 20px}}th,td{{text-align:left;padding:7px;border-bottom:1px solid #cbd5cc}}th{{font-weight:600}}
@media(max-width:650px){{main{{padding:25px 18px}}h1{{font-size:36px}}.stats,.grid,.steps{{grid-template-columns:1fr 1fr}}.grid{{grid-template-columns:1fr}}table{{display:block;overflow-x:auto;font-size:12px}}.stats .stat b{{font-size:26px}}}}
@media print{{.report-nav{{display:none}}.stats{{margin:16px 0}}.rule{{margin:10px 0!important}}.investigation{{break-before:page}}.grid{{break-inside:avoid}}body{{font-size:12px}}main{{padding:0}}h1{{font-size:35px}}h2{{font-size:22px}}.lead{{font-size:14px}}.stat{{padding:9px}}.stat b{{font-size:23px}}.card h3{{font-size:19px}}.bar{{margin:3px 0}}.rule{{margin:16px 0}}.methods{{margin-top:14px}}.investigation{{margin-top:18px}}}}
</style></head><body><main>
<p class="small report-nav"><a href="casual-vs-rated.html#case-evidence">← Back to the casual supplement</a> · <a href="20261008_v1_maia_account_patterns.pdf">Download PDF ↗</a></p><div class="eyebrow">Maia research / supplemental evidence / 8 October 2026</div>
<h1>Two huge game counts.<br>Two different loops.</h1>
<p class="lead">The two busiest accounts in our three-year <em>casual Maia</em> collection did not play tens of thousands of ordinary full-length games. Public moves and starting boards show how their totals accumulated. Neither pattern establishes who controlled an account or why either profile shows a disabled flag.</p>
<div class="stats"><div class="stat"><b>{n(a['games'])}</b><span>standard games, account 1</span></div><div class="stat"><b>{n(b['games'])}</b><span>custom-position games, account 2</span></div><div class="stat"><b>{a_short}</b><span>account 1: six plies or fewer</span></div><div class="stat"><b>{b_one}</b><span>account 2: exactly one ply</span></div></div>
<table><thead><tr><th>Observed in Maia games</th><th><a href="https://lichess.org/@/scissorsharpness">scissorsharpness</a></th><th><a href="https://lichess.org/@/top1mostplayedgames">top1mostplayedgames</a></th></tr></thead><tbody>
<tr><td>Active UTC dates</td><td>{a['active_utc_days']} (Sep 8–22)</td><td>{b['active_utc_days']} (Apr 28–May 6)</td></tr>
<tr><td>Game setup</td><td>Standard, all 1+0</td><td>From a chosen position</td></tr>
<tr><td>Dominant ending</td><td>{a_resign} resignation</td><td>{n(b['status'].get('mate',0))} checkmates; 1 resignation</td></tr>
<tr><td>Median moves in a game</td><td>{a['plies']['median']} half-moves</td><td>{b['plies']['median']} half-move</td></tr>
<tr><td>Median gap between starts</td><td>{a['start_gap_seconds']['median']:.2f}s</td><td>{b['start_gap_seconds']['median']:.2f}s</td></tr>
<tr><td>Busiest rolling hour</td><td>{n(a['peak_rolling_hour']['games'])} starts</td><td>{n(b['peak_rolling_hour']['games'])} starts</td></tr>
</tbody></table>
<div class="grid"><section class="card"><h3>1 · Short games, then resign</h3><p><b>{n(a['status'].get('resign',0))}</b> games ended by resignation. The account made a median of <b>{a['account_moves']['median']} moves</b>; the median time between game starts was {a['start_gap_seconds']['median']:.2f} seconds. The 1+0 clock was a limit, not the time each game lasted.</p><p class="small">The last-move timestamp may come <em>before</em> resignation. Its difference from creation is not exact game duration. <a href="https://lichess.org/pPOh9GPD">Example game ↗</a></p></section>
<section class="card"><h3>2 · A position that ends at once</h3><p><b>{b_zero}</b> of these games contain no move by the account. Their opening boards are custom FENs; the most common board was used {n(top['games'])} times and the recorded move is <b>{html.escape(top['moves'])}</b>—Maia's move. <a href="https://lichess.org/q5dZdoEl">Example game ↗</a></p><p class="small">Most common starting FEN: <code>{html.escape(top['fen'])}</code>. There are {n(b['unique_initial_positions'])} initial positions across this account's collected games.</p></section></div>
<div class="rule"></div><div class="grid"><section><h2>Account 1 · busiest UTC dates</h2>{day_chart(a['by_utc_day'])}</section><section><h2>Account 2 · busiest UTC dates</h2>{day_chart(b['by_utc_day'])}</section></div>
<section class="investigation"><div class="eyebrow">Evidence review / not an enforcement finding</div><h2>What the second account actually repeated</h2>
<p>Every one of its {n(b['games'])} games was tagged <code>fromPosition</code>—{pct(b['games'],data['casual_from_position_games'])} of all collected casual Maia games with that tag. Six exact starting FENs account for the entire set. {n(b['plies']['one'])} games ended after one half-move, with Maia moving first; the account made no move in those games. Only two games reached three half-moves. A separate chess-rule replay confirms that all {n(replay['checkmates_on_supplied_boards'])} mate-tagged games end in checkmate on their supplied boards. However, {n(replay['invalid_initial_boards'])} games use a starting board with 17 white pieces, including eight pawns: it fails a basic standard-chess validity check. This is not proof that every starting board is a legal standard-chess position.</p>
<table><thead><tr><th>Exact starting board</th><th>Games</th><th>Most common continuation</th></tr></thead><tbody>{setup_rows}</tbody></table>
<p class="small">The complete FEN strings, moves, and public game IDs are in the compressed data. A repeated setup and rapid cadence may be consistent with scripted challenge creation, but cannot identify how these games were initiated or who initiated them.</p>
<div class="callout"><strong>Were they banned for breaking the rules?</strong> Both public account-API responses returned <code>disabled: true</code> on October 8. They expose no reason. These records cannot establish a moderator ban, cheating, automation, or a Terms-of-Service finding. Lichess <a href="https://lichess.org/page/fair-play">Fair Play</a> distinguishes forbidden programmatic GUI moves from permitted official API methods; the game exports do not identify the input method. <a href="https://lichess.org/terms-of-service">Terms and possible account actions ↗</a></div>
<h2>How to check the claims</h2><div class="steps"><div><b>01 / Rank</b><br>Count all published casual Maia records by opponent.</div><div><b>02 / Match</b><br>Verify all 91,010 selected game IDs against the corpus.</div><div><b>03 / Inspect</b><br>Read moves, FENs, timestamps, outcomes and clocks from public game JSON.</div><div><b>04 / Replay</b><br>Replay the supplied boards to checkmate, and separately test starting-board validity.</div></div>
<div class="methods"><strong>Scope and reproducibility.</strong> Only casual games against official Maia 1, 5 and 9 in the repository's fixed three-year window; not either account's complete Lichess history. Both account-wide user exports returned HTTP 404 at collection time. The two accounts were ranked by all {n(data['casual_corpus_games'])} published casual Maia records; their {n(a['games']+b['games'])} full game JSON objects were recovered by known IDs. The <a href="data/account-cases/README.md">game data, hashes, definitions and rebuild instructions</a> accompany this page. Public handles are not verified people. Independent research, not a Lichess enforcement decision.</div>
</section>
</main></body></html>'''
    OUT.write_text(html_doc, encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
