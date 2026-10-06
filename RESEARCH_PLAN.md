# Maia research methods and remaining questions

## Status and scope

The **rated-only three-year** export is complete. It covers official `maia1`, `maia5`, and `maia9` games **finished** from 2023-10-04 00:00 UTC through, but not including, 2026-10-04 09:00 UTC. The repo contains all collected game metadata, a checksum manifest, reproducible analysis, and visual report.

The earlier ambition—an **all-time game-level** study including casual games—is **not complete**. The separate all-time profile snapshot gives aggregate rated/casual counts, not casual players or monthly casual play.

## Collection and validation

Lichess's [user-game export](https://lichess.org/api#operation/apiGamesUser) was requested sequentially with `rated=true`, `moves=false`, `clocks=false`, `evals=false`, and `opening=true`. A local SQLite database stored minimal fields; response bodies, credentials, and the working database are not published.

Filtered requests were observed to stop at 10,000 responses. The collector split date ranges until each completed request returned fewer than 9,900 raw responses. Its 342 final ranges cover the frozen interval without gaps for each bot. The local SQLite `quick_check` passed; all 1,425,567 rows finished within scope and had unique `(bot,game_id)` keys. No game ID appeared under two Maia bots in this rated interval. Unknown opponent handles: 147. The published-data verifier independently checks hashes, CSV row counts, finish-time bounds, and unique game IDs.

**Coverage limitation:** raw response counts per final range were not retained in the public dataset. Cap protection depends on the completed collector run and its reviewed splitting logic; the public verifier cannot prove Lichess did not omit a game for another reason.

## Definitions

- **All-time bot-game entries:** sum of profile game counters, rated and casual. A Maia-vs-Maia game contributes twice.
- **All-time unique games:** entries minus 21 Maia-vs-Maia overlaps in the 2026-10-04 profile/crosstable snapshot. These moving server counters may not synchronize to the second.
- **Three-year rated bot-game entries:** one published CSV row per bot/game pair within the frozen finish-time interval.
- **Three-year unique games:** distinct game IDs. Here they equal bot-game entries because no Maia-vs-Maia game occurred in the export.
- **Monthly popularity:** rated entries by UTC finish month. Both October edge months are partial and excluded from the trend table and comparable 12-month totals.
- **Account-weighted rating:** average each opposing account's recorded Lichess ratings, then average those account means. The game-weighted mean lets frequent players count more. Neither is FIDE Elo.
- **Opening family:** Lichess's opening name before its first colon. This is a classification of the position reached by both sides, not the opponent's first move.
- **First-to-last bot:** among accounts with at least 20 games spanning 180 days, compare the first and last Maia opponent observed. This is descriptive and noisy, not proof of improvement or causality.

## Limitations and follow-on work

1. Casual games were not downloaded at game level. There is no monthly **all-games** time series, casual-account leaderboard, or all-time opposing-account count. Do not extrapolate the rated trend to casual play.
2. No moves, PGNs, or clocks-by-move were downloaded. Opening metadata cannot establish first-move frequencies or chess-quality improvement.
3. Lichess handles are public, but an account is not necessarily a person, and every opponent's bot status was not verified. Leaderboards are descriptive only.
4. A credible individual improvement study needs matched time controls, colors, sufficient time-ordered games at each level, and outside-activity context. Even then, a causal claim would need a comparison design.
5. The all-time profile snapshot and rated export were collected at different times and cover different periods. Treat them as two views, not additive pieces of one population.

Run `python3 scripts/build_rated_report.py` to verify the published shards and regenerate aggregate JSON/HTML. The [manifest](data/rated-games/manifest.json) pins each CSV.gz SHA-256. `scripts/export_rated_games.py --db /path/to/games.sqlite3` creates deterministic gzip files (`mtime=0`) from a compatible private source. The older `data/summary.json`, `scripts/collect.py`, and `scripts/build_report.py` remain for historical snapshot reproducibility; the older PDF is superseded.
