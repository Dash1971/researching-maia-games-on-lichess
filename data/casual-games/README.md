# Three-year casual game metadata

**2,040,728 collected bot-game records** from official Lichess `maia1`,
`maia5`, and `maia9`, with last recorded move timestamps in
`[2023-10-04T00:00:00Z, 2026-10-04T09:00:00Z)`. The Lichess export was
requested with `rated=false`. One CSV row represents one bot/game pair. No
game ID appears under two Maia bots in this interval, so the row count also
equals the number of unique game IDs. This is **casual-only**, not all-time
play. The separate [rated export](../rated-games/README.md) uses the same
window and field layout. The casual files include 1,922,672 `standard` games and 118,056 `fromPosition` games; the rated files contain only standard games. All collected games contribute to volume charts; matched behavior comparisons use standard games from both formats.

The 12 files are split by bot and **UTC last-move year**, gzip-compressed CSV
with a header, UTF-8 and LF line endings. [`manifest.json`](manifest.json)
records field names, row counts, byte counts, and SHA-256 hashes. Gzip
timestamps are zeroed for deterministic exports.

| Field | Meaning |
| --- | --- |
| `bot` | `maia1`, `maia5`, or `maia9` |
| `game_id` | Public Lichess game ID; URL: `https://lichess.org/<game_id>` |
| `opponent_id` | Public opposing Lichess account handle; blank in two rows |
| `created_at_ms`, `last_move_at_ms` | Unix milliseconds UTC for game start and last recorded move. The latter determines study scope and month; it can precede resignation or flag fall. |
| `bot_color`, `winner` | Bot side and winning side (`white`, `black`, or blank when no winner is recorded) |
| `status` | Lichess status, for example `mate`, `resign`, `draw`, or `outoftime` |
| `speed`, `perf` | Lichess speed/performance categories |
| `variant`, `source` | Lichess variant and game origin |
| `opening_eco`, `opening_name` | Lichess ECO/opening label for the position reached; **not** a first-move list |
| `bot_rating`, `opponent_rating` | Recorded Lichess ratings at game time, not FIDE Elo |
| `clock_initial_seconds`, `clock_increment_seconds` | Starting clock and increment; 600 and 0 means 10+0 |

Blank CSV cells mean missing/null source values. There are no moves, PGNs,
chat messages, private account mappings, credentials, or internal download
window IDs. The [supplemental aggregates](../casual_comparison.json) and
[behavior comparisons](../comparison_behaviour.json) and [monthly CSV](../casual_comparison_monthly.csv) compare these records with the
rated export. Partial October 2023 and October 2026 are excluded from its
complete-month trend.

Run `python3 scripts/build_casual_comparison.py` from the repository root to
verify both sets of published shards and rebuild the comparison. To re-export
from a compatible, privately obtained SQLite source, use
`python3 scripts/export_casual_games.py --db /path/to/games.sqlite3`. The
working database and access token are **not** published.

Source: [Lichess user-game export](https://lichess.org/api#operation/apiGamesUser).
This is independent research, not an official Lichess dataset. The
repository MIT license does not relicense Lichess or player-originated data;
see [Lichess's terms](https://lichess.org/terms-of-service).
