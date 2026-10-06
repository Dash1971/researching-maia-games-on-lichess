# How people play the Maia bots on Lichess

Independent research on official [Maia 1](https://lichess.org/@/maia1), [Maia 5](https://lichess.org/@/maia5), and [Maia 9](https://lichess.org/@/maia9).

**[Visual report](index.html)** · **[New PDF](20261006_v2_maia_games_report.pdf)** · [Game-level data and field guide](data/rated-games/README.md) · [Aggregate results](data/rated_summary.json) · [Methods and limits](RESEARCH_PLAN.md)

## Two scopes

| Scope | Contents | Use |
| --- | --- | --- |
| **All-time profile snapshot**, 2026-10-04 07:12 UTC | 6,486,805 summed bot-game entries, rated **and casual**. Twenty-one Maia-vs-Maia games appear twice, leaving 6,486,784 unique games. | Historical scale and rated/casual mix. Not a monthly series or count of people. |
| **Three-year rated export**, games finished 2023-10-04 00:00 UTC to before 2026-10-04 09:00 UTC | 1,425,567 game-level metadata records. There is no Maia-vs-Maia overlap in this window, so all 1,425,567 are unique games. | Monthly rated play, opponent accounts and ratings, exact clocks, color, and openings. **Not casual or all-time play.** |

“Bot-game entry” means one game attached to one bot account. “Unique game” means one game ID counted once even if two Maia bots played each other. The report never switches denominator without saying so. October 2023 and October 2026 are partial months, omitted from the monthly chart/table and growth comparison.

## What is published in this review

- All **rated game metadata** saved by the downloader: 12 year/bot CSV.gz shards with public Lichess opponent handles and game IDs. Row counts and SHA-256 hashes are in the [manifest](data/rated-games/manifest.json). No moves, PGNs, chat, private identity mapping, or credentials were collected or included.
- A [field guide](data/rated-games/README.md), complete [aggregate JSON](data/rated_summary.json), and Python standard-library scripts to export and rebuild the report.
- A more visual report: all-time rated/casual bars, monthly rated-game chart, public-account leaderboard, repeat-play concentration, clocks, ratings, and openings.

From the repository root, reproduce the aggregate JSON and HTML offline:

```sh
python3 scripts/build_rated_report.py
```

The script checks every shard hash and row count, every game's time window and unique ID, and the final record count. To re-export shards from a compatible, privately obtained SQLite source, run `python3 scripts/export_rated_games.py --db /path/to/games.sqlite3`. The original working database and access token are **not** in this repository.

The PDF is an A4 print rendering of the generated `index.html`, made with headless Chrome and its `--no-pdf-header-footer` option. The HTML is the reproducible report source; it requires no remote assets.

The older profile/Insights [snapshot JSON](data/summary.json), [PDF](20261004_v1_researching_maia_games_report.pdf), and scripts are retained for provenance. **That PDF is superseded** by the new rated-game report.

## Sources and caution

Sources: Lichess [profiles](https://lichess.org/api#operation/apiUser), [bot crosstables](https://lichess.org/api#operation/apiCrosstable), and [user-game export](https://lichess.org/api#operation/apiGamesUser). The old Insights slices were stale and are **not** used for the three-year analysis. The filtered export's observed 10,000-response cap was handled with smaller date ranges; see the [methods](RESEARCH_PLAN.md).

Public account handles are not proof of distinct people. Neither ratings nor movement between bot levels show that Maia caused improvement. Opening names are Lichess metadata, reached by both players; first moves cannot be recovered without moves. The all-time profile counters are a moving snapshot, not a complete all-time game-level archive.

The MIT license applies to original code, report writing, and visuals—not to Lichess or player-originated data. Consult [Lichess's terms](https://lichess.org/terms-of-service) and the [Lichess open database's separate license statement](https://database.lichess.org/). Independent fan research; not an official Lichess or Maia publication.
