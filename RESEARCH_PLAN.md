# Maia research methods and remaining questions

## Status and scope

The **rated and casual three-year** collection runs have finished. Their published records form frozen observed datasets; completeness against every eligible Lichess game cannot be independently guaranteed. Both cover official `maia1`, `maia5`, and `maia9` games whose **last recorded move timestamp** falls from 2023-10-04 00:00 UTC through, but not including, 2026-10-04 09:00 UTC. The repo contains both metadata exports, checksum manifests, reproducible analysis, a rated-focused report, and a [casual/rated supplement](casual-vs-rated.html).

The earlier ambition—an **all-time game-level** study—is **not complete**. The separate all-time profile snapshot gives aggregate rated/casual counts, while the detailed exports cover only the frozen three-year window.

The last recorded move timestamp defines the export window, shard year, and monthly counts. It can precede resignation or flag fall and is not an exact game-end timestamp.

## Collection and validation

Lichess's [user-game export](https://lichess.org/api#operation/apiGamesUser) was requested sequentially with `rated=true`, `moves=false`, `clocks=false`, `evals=false`, and `opening=true`. A local SQLite database stored minimal fields; response bodies, credentials, and the working database are not published.

Filtered requests were observed to stop at 10,000 responses. The collector split date ranges until each completed request returned fewer than 9,900 raw responses. Its 342 final ranges cover the frozen interval without gaps for each bot. The local SQLite `quick_check` passed; all 1,425,567 rows had last recorded move timestamps within scope and had unique `(bot,game_id)` keys. No game ID appeared under two Maia bots in this rated interval. Unknown opponent handles: 147. The published-data verifier independently checks hashes, CSV row counts, last-move timestamp bounds, and unique game IDs.

**Coverage limitation:** raw response counts per final range were not retained in the public dataset. Cap protection depends on the completed collector run and its reviewed splitting logic; the public verifier cannot prove Lichess did not omit a game for another reason.

### Casual collection and comparison

The same Lichess endpoint was requested with `rated=false`, `moves=false`,
`clocks=false`, `evals=false`, and `opening=true`. Because API date filtering
uses game creation while this study uses last recorded move, the casual
requests began seven days before the study's starting edge. The collector
pre-sized Maia 1 requests to four days and Maia 5/9 requests to ten days, split
any request with at least 9,900 raw responses, deduplicated by `(bot,game_id)`,
and stored results in a separate private SQLite database. Its final checks
passed SQLite `quick_check`, gap-free query-date coverage under the response
cap, saved-count consistency, and all saved last-move timestamps in scope.
**An unusually long game created more than seven days before the first study
date could still be missed.** The public CSVs do not contain raw request logs,
so those collection checks cannot be re-proven from published metadata alone.

The [casual manifest](data/casual-games/manifest.json) pins 2,040,728 rows in
12 bot/year CSV.gz shards. The separate
[`build_casual_comparison.py`](scripts/build_casual_comparison.py) checks both
published manifests, every checksum/row count, UTC last-move scope, unique
game IDs within and across rated/casual, and rebuilds the
[supplement](casual-vs-rated.html), [aggregate JSON](data/casual_comparison.json),
and [monthly CSV](data/casual_comparison_monthly.csv). No game ID appears under
two bots or in both formats in these exports, so bot-game entries equal unique
games here. This equality is observed for these exports, not assumed generally.

Casual records include 118,056 `fromPosition` games and 1,922,672 standard games; all rated records are standard. All collected variants remain in volume, monthly, and overall descriptive aggregates. Matched behavior analyses use only standard games in both formats.

The supplement uses bot-game entries for volume and monthly charts; both
partial October months are excluded from its 35 complete-month series. Its
first/last 12-month comparisons are November 2023–October 2024 and October
2025–September 2026. Account overlap compares public Lichess handles, not
verified people. A game-weighted rating mean averages recorded opponent
ratings over games; the account-weighted mean averages each handle's own mean
once. Bot win share divides Maia wins by games with a white/black winner;
games without a winner are excluded. Casual/rated differences in opponents,
ratings, bot choice, and clocks are descriptive, not causal effects of the
game's rated setting.

Monthly active-account counts are distinct public handles *within each month
and format*; one handle can recur in many months. The September 2026 outlier
sensitivity subtracts that month's games from its single highest-volume
casual account, then recomputes the final 12-month casual total. It is not an
estimate of how the month would have evolved without that account, and it
does not label the account's behavior as improper.

### Behavior comparisons across formats

The [behavior JSON](data/comparison_behaviour.json), built by `scripts/comparison_behaviour.py`, verifies both published corpora and distinguishes all collected games from standard-only comparisons.

- Activity concentration counts games per public account within each format. Median activity includes one-game accounts. The top 1% uses `max(1, round(account_count × 0.01))` accounts, with all games in that format as the share denominator.
- Quick returns find the first next observed Maia game for the account across both formats, ordered by creation timestamp and game ID. A return starts 0–600 seconds after the prior last recorded move. Eligible prior games have a known account, a last move no earlier than creation, and a last move at least ten minutes before the window ends. No-next games stay in the denominator. The standard-only version requires both prior and next games to be standard; it never skips an intervening custom-position game. These are observed returns, not formal rematches or complete account histories.
- Shared regular accounts have at least ten eligible standard games in each format. Account-equal rates give each selected account equal weight; game-weighted rates count their eligible games. Outcome-specific account means use selected accounts with at least one eligible prior game of that outcome.
- Matched outcome comparisons require known outcomes, non-cheat standard games, the same account, Maia, exact clock, speed, and opponent color, with at least ten games in each format. Each account contributes the eligible group maximizing the smaller of its two format counts first, then combined games; ties resolve by ascending bot, clock string, speed, and color. Means weight accounts equally. Formats are compared over the entire window and need not occur at the same time, so matching does not establish causality.
- Two outlier checks answer different questions. The monthly growth check excludes only the largest September 2026 casual account’s games in that month. The clock/speed sensitivity removes that account’s casual games across the full window. In these exports both exclusions remove the same 63,504 games because all that account’s collected casual games fall in September 2026; the definitions remain different. Neither identifies the account’s motives or treats its games as invalid.

The 2,982 shared regular standard-game accounts have virtually identical account-equal quick-return rates: 50.6297% rated and 50.6120% casual. Game-weighting the same cohort instead gives 50.7% and 53.9%, showing that frequent-account weighting changes the comparison. Among 900 matched accounts, mean opponent score is 42.6% rated and 38.7% casual (casual minus rated: −3.9 percentage points). The median absolute gap between the formats’ mean game-start dates is 39.8 days. These games can occur at different stages of an account’s chess activity, and matching does not prove a format effect or training benefit.

## Definitions

- **All-time bot-game entries:** sum of profile game counters, rated and casual. A Maia-vs-Maia game contributes twice.
- **All-time unique games:** entries minus 21 Maia-vs-Maia overlaps in the 2026-10-04 profile/crosstable snapshot. These moving server counters may not synchronize to the second.
- **Three-year bot-game entries:** one published CSV row per bot/game pair in either rated or casual format, within the frozen last-move interval.
- **Three-year unique games:** distinct game IDs. In both exports, these equal bot-game entries because no Maia-vs-Maia game occurred in the window; no game ID occurs in both formats.
- **Monthly popularity:** rated and casual entries by UTC last-move month. Both October edge months are partial and excluded from trend tables and comparable 12-month totals.
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

1. Both rated and casual three-year exports are available at game level. They still do not supply an **all-time game-level** series or all-time opposing-account count. Do not extrapolate three-year trends to all time.
2. No moves, PGNs, or clocks-by-move were downloaded. Opening metadata cannot establish first-move frequencies or chess-quality improvement.
3. Lichess handles are public, but an account is not necessarily a person, and every opponent's bot status was not verified. Leaderboards are descriptive only.
4. A credible individual improvement study needs matched time controls, colors, sufficient time-ordered games at each level, and outside-activity context. Even then, a causal claim would need a comparison design.
5. The all-time profile snapshot and rated export were collected at different times and cover different periods. Treat them as two views, not additive pieces of one population.

Run `python3 scripts/build_rated_report.py` to verify the published shards and regenerate `data/rated_summary.json`, `data/fan_insights.json`, `data/learning_insights.json`, and `index.html`. Run `python3 -m unittest discover -s scripts -p 'test_*.py'` for analysis regression checks. GitHub Actions runs these tests, verifies that regeneration matches committed outputs, and publishes the static report after validated changes reach `main`. The [manifest](data/rated-games/manifest.json) pins each CSV.gz SHA-256. `scripts/export_rated_games.py --db /path/to/games.sqlite3` creates deterministic gzip files (`mtime=0`) from a compatible private source. The older `data/summary.json`, `scripts/collect.py`, and `scripts/build_report.py` remain for historical snapshot reproducibility; the older PDF is superseded.
