# Maia research methods and remaining questions

## Status and scope

The **rated-only three-year** collection run has finished. Its published records form a frozen observed dataset; completeness against every eligible Lichess game cannot be independently guaranteed. It covers official `maia1`, `maia5`, and `maia9` games whose **last recorded move timestamp** falls from 2023-10-04 00:00 UTC through, but not including, 2026-10-04 09:00 UTC. The repo contains all collected game metadata, a checksum manifest, reproducible analysis, and visual report.

The earlier ambition—an **all-time game-level** study including casual games—is **not complete**. The separate all-time profile snapshot gives aggregate rated/casual counts, not casual players or monthly casual play.

The last recorded move timestamp defines the export window, shard year, and monthly counts. It can precede resignation or flag fall and is not an exact game-end timestamp.

## Collection and validation

Lichess's [user-game export](https://lichess.org/api#operation/apiGamesUser) was requested sequentially with `rated=true`, `moves=false`, `clocks=false`, `evals=false`, and `opening=true`. A local SQLite database stored minimal fields; response bodies, credentials, and the working database are not published.

Filtered requests were observed to stop at 10,000 responses. The collector split date ranges until each completed request returned fewer than 9,900 raw responses. Its 342 final ranges cover the frozen interval without gaps for each bot. The local SQLite `quick_check` passed; all 1,425,567 rows had last recorded move timestamps within scope and had unique `(bot,game_id)` keys. No game ID appeared under two Maia bots in this rated interval. Unknown opponent handles: 147. The published-data verifier independently checks hashes, CSV row counts, last-move timestamp bounds, and unique game IDs.

**Coverage limitation:** raw response counts per final range were not retained in the public dataset. Cap protection depends on the completed collector run and its reviewed splitting logic; the public verifier cannot prove Lichess did not omit a game for another reason.

## Definitions

- **All-time bot-game entries:** sum of profile game counters, rated and casual. A Maia-vs-Maia game contributes twice.
- **All-time unique games:** entries minus 21 Maia-vs-Maia overlaps in the 2026-10-04 profile/crosstable snapshot. These moving server counters may not synchronize to the second.
- **Three-year rated bot-game entries:** one published CSV row per bot/game pair within the frozen last-move interval.
- **Three-year unique games:** distinct game IDs. Here they equal bot-game entries because no Maia-vs-Maia game occurred in the export.
- **Monthly popularity:** rated entries by UTC last-move month. Both October edge months are partial and excluded from the trend table and comparable 12-month totals.
- **Account-weighted rating:** average each opposing account's recorded Lichess ratings, then average those account means. The game-weighted mean lets frequent players count more. Neither is FIDE Elo.
- **Opening family:** Lichess's opening name before its first colon. This is a classification of the position reached by both sides, not the opponent's first move.
- **First-to-last bot:** among accounts with at least 20 games spanning 180 days, compare the first and last Maia opponent observed. This is descriptive and noisy, not proof of improvement or causality.

## Fan insights from the frozen export

The [fan-insight JSON](data/fan_insights.json) records its definitions alongside the results. Analyses use the opponent's perspective and count games rather than independent people.

- **Outcomes and color:** a white/black winner determines a win or loss relative to the opponent's color. A missing winner is a draw only for explicit `draw` or `stalemate` status; other missing winners remain unknown. Win percentage divides wins by all games. Score percentage divides wins plus half the draws by games with known outcomes.
- **Ratings and openings:** rating bands use the opponent's recorded game-time Lichess rating. They mix speed-specific rating pools. Opening comparisons use the 12 most common opening families separately for each bot and opponent color; both sides reached these positions, so observed outcomes do not measure an opening's causal advantage.
- **Quick returns:** an account starts its next observed rated game against any of the three Maia bots within 0–600 seconds after the previous game's last move. A same-Maia return also requires the bot to match. Eligible prior games have a known opponent ID, nonnegative duration, and have their last recorded move at least ten minutes before the export ends; games with no observed return stay in the denominator. This is observed return behavior, not proof of a formal Lichess rematch. Casual games, games against other accounts, and games whose last move falls outside the export are unobserved.
- **Account activity and gaps:** games are combined across the three bots by public opponent ID. Consecutive observed games are ordered by start time, breaking ties by game ID; the gap runs from the previous game's last move to the next game's start. Negative gaps are counted as overlaps. Frequent accounts contribute more games, and result/return associations can reflect differences in ratings, clocks, or individual habits.
- **UTC activity:** hourly counts use game start times in UTC. They do not establish the accounts' local times or locations.

## Early versus later play among persistent accounts

The [early/later analysis](data/learning_insights.json) matches each account with the same Maia bot, exact starting clock and increment, and Lichess speed category. It excludes unknown outcomes and `cheat` status. Valid games are ordered by start time, breaking ties by game ID. The main cohort requires at least 40 valid games in a matching group; its first 20 and last 20 never overlap, and at least 30 days separate the last early and first late game. Each account contributes once, using its eligible group with the most valid games; ties resolve by ascending bot, starting clock, increment, and speed.

The stricter comparison requires at least 60 valid games and a 90-day gap. Selection is repeated independently for this cohort. Each selected account has equal weight in mean and median score changes, with wins worth 1, draws 0.5, and losses 0. Ratings, bot ratings, and color mix in the two windows are also reported.

The main cohort represents about 1.15% of the 93,020 observed accounts. The 1,066-account main cohort gained an average 3.2 percentage points in score; the 649-account stricter cohort gained 2.9. Maia 1 had the largest consistent increase; Maia 9 showed no robust increase across the two comparisons. These are descriptions of a selected persistent subset. Survivorship and selection effects, regression to the mean, outside practice, changes to bots and color mix can affect results. This is not an estimate of the causal training effect of playing Maia.

## Limitations and follow-on work

1. Casual games were not downloaded at game level. There is no monthly **all-games** time series, casual-account leaderboard, or all-time opposing-account count. Do not extrapolate the rated trend to casual play.
2. No moves, PGNs, or clocks-by-move were downloaded. Opening metadata cannot establish first-move frequencies or chess-quality improvement.
3. Lichess handles are public, but an account is not necessarily a person, and every opponent's bot status was not verified. Leaderboards are descriptive only.
4. A credible individual improvement study needs matched time controls, colors, sufficient time-ordered games at each level, and outside-activity context. Even then, a causal claim would need a comparison design.
5. The all-time profile snapshot and rated export were collected at different times and cover different periods. Treat them as two views, not additive pieces of one population.

Run `python3 scripts/build_rated_report.py` to verify the published shards and regenerate `data/rated_summary.json`, `data/fan_insights.json`, `data/learning_insights.json`, and `index.html`. Run `python3 -m unittest discover -s scripts -p 'test_*.py'` for analysis regression checks. GitHub Actions runs these tests, verifies that regeneration matches committed outputs, and publishes the static report after validated changes reach `main`. The [manifest](data/rated-games/manifest.json) pins each CSV.gz SHA-256. `scripts/export_rated_games.py --db /path/to/games.sqlite3` creates deterministic gzip files (`mtime=0`) from a compatible private source. The older `data/summary.json`, `scripts/collect.py`, and `scripts/build_report.py` remain for historical snapshot reproducibility; the older PDF is superseded.
