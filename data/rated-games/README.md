# Three-year rated game metadata

**1,425,567 records** from official Lichess `maia1`, `maia5`, and `maia9`, with last recorded move timestamps in `[2023-10-04T00:00:00Z, 2026-10-04T09:00:00Z)`. One CSV row represents one bot/game pair. There were no Maia-vs-Maia games in this interval, so every row has a distinct game ID. This is **rated-only** data; it does not contain all-time or casual games.

The 12 files are split by bot and **UTC last-move year**, gzip-compressed CSV with a header, UTF-8 and LF line endings. [`manifest.json`](manifest.json) records the field list, row counts, byte counts, and SHA-256 checksums. Gzip timestamps are zeroed for deterministic exports.

| Field | Meaning |
| --- | --- |
| `bot` | `maia1`, `maia5`, or `maia9` |
| `game_id` | Public Lichess game ID; game URL is `https://lichess.org/<game_id>` |
| `opponent_id` | Public opposing Lichess account handle; blank in 147 rows |
| `created_at_ms`, `last_move_at_ms` | Unix milliseconds in UTC for game start and last recorded move. The latter determines scope and month; it can precede resignation or flag fall. |
| `bot_color`, `winner` | Bot side and winning side (`white`, `black`, or blank for no winner) |
| `status` | Lichess game-end status, such as `mate`, `resign`, `draw`, or `outoftime` |
| `speed`, `perf` | Lichess speed/performance categories |
| `variant`, `source` | Lichess variant and origin; all retained games report `standard` and `friend` |
| `opening_eco`, `opening_name` | Lichess ECO and named opening for the position reached; **not** a verified first-move list |
| `bot_rating`, `opponent_rating` | Recorded Lichess ratings at game time; not FIDE Elo |
| `clock_initial_seconds`, `clock_increment_seconds` | Exact clock setting, e.g. 600 and 0 = 10+0 |

Blank CSV cells mean a missing/null source value. There are no moves, PGNs, game chat, private account mappings, tokens, or internal downloader window IDs. The separate [`rated_summary.json`](../rated_summary.json) has derived aggregates. **Do not add these records to the all-time profile totals**: the time periods and rated/casual coverage differ.

To verify checksums and reproduce the report from these files (Python standard library only), run `python3 scripts/build_rated_report.py` from the repository root. To inspect a file manually: `gzip -dc data/rated-games/maia1_2026.csv.gz | head`.

Source: [Lichess user-game export](https://lichess.org/api#operation/apiGamesUser). Lichess account handles and games are public, but this collection is independent research, not an official Lichess dataset. The repository MIT license does not relicense Lichess or player-originated data; see [Lichess's terms](https://lichess.org/terms-of-service).
