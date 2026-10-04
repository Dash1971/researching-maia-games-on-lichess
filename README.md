# Researching Maia games on Lichess

A visual, plain-language snapshot of play against the three [official Maia bots](https://lichess.org/team/maia-bots): [Maia 1](https://lichess.org/@/maia1), [Maia 5](https://lichess.org/@/maia5), and [Maia 9](https://lichess.org/@/maia9).

**[Read the visual report](index.html)** · [Download the corrected PDF](20261004_v1_researching_maia_games_report.pdf) · [Review the full-history research plan](RESEARCH_PLAN.md) · [Inspect the aggregate data](data/summary.json)

## What this snapshot can answer

- How many games each bot account has recorded, and what share was rated or casual.
- How often Maia played White or Black **in the available Insights slices**.
- The leading opening families and time controls **in those same slices**.

It **cannot** yet answer how many unique Lichess accounts played the bots, average games per opposing account, who played the most, or whether particular accounts improved and progressed from Maia 1 to Maia 5 and Maia 9. Those require a complete game-level export with opponent IDs and dates. This report does not substitute profile game totals for player counts or present sampled users as a lifetime leaderboard.

## Sources and scope

1. The public [user profile API](https://lichess.org/api#operation/apiUser) supplies each bot's cumulative game and rated-game counters, plus win/draw/loss counters. These are moving totals.
2. The public [head-to-head crosstable API](https://lichess.org/api#operation/apiCrosstable) supplies pairwise game counts among the three Maia accounts. A game between two of these bots appears in both profile totals, so the report subtracts the cross-bot overlap once when giving a distinct-game headline.
3. [Lichess Insights](https://lichess.org/insights/maia1) provides a 15,000-rated-account-game overview slice for each bot (45,000 account-game records in all). Its own indexed collections were marked **stale** when collected. These slices span different periods and are not random lifetime samples. The date labels in `data/summary.json` are chart-bin labels, not exact first/last game times.

The [documented user-game export](https://lichess.org/api#operation/apiGamesUser) initially returned HTTP 404 with a generic User-Agent; that did **not** establish that export was down. A later small request with a custom User-Agent and `Accept: application/x-ndjson` returned HTTP 429 (`Please only run 1 request(s) at a time`) at 2026-10-04 07:39 UTC. Full-history export remains **unverified and incomplete**, not known to be unavailable. The HTML and PDF in this repository carry that corrected status. Lichess's [monthly database](https://database.lichess.org/) contains rated games only, so it excludes most games in the three profile totals. Its CC0 publication does not solve the missing casual-game problem.

**Definitions:** “casual” means all profile games minus rated profile games. A “unique account” would be a distinct opposing Lichess ID, not necessarily a distinct person. Opening families describe the resulting position and reflect both players' moves. A bot-vs-bot game could appear twice among the 45,000 Insights account-game records.

## Reproduce or refresh

Python 3, standard library only:

```sh
python3 scripts/collect.py
python3 scripts/build_report.py
```

The first command makes sequential, read-only calls to Lichess and writes only aggregate values to `data/summary.json`; no opponent usernames or raw games are retained. The second command builds a self-contained `index.html` with no external scripts, fonts, or tracking. A later run will produce different profile totals and potentially different Insights slices. The Insights POST endpoint is a site endpoint rather than a stable documented API, so future Lichess changes may require updating the collector.

## Next study, not yet authorized

The [full-history research plan](RESEARCH_PLAN.md) estimates at least 60 hours of OAuth export time and proposes a small calibration before any multi-day download. Neither the calibration nor the full export has started. Publication of this snapshot and plan does not authorize either download.

This is independent fan research, not an official Maia or Lichess publication. Original code, writing, and visuals are [MIT licensed](LICENSE); Lichess source data retain their own terms.
