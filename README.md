# How people play the Maia bots on Lichess

Independent research on official [Maia 1](https://lichess.org/@/maia1), [Maia 5](https://lichess.org/@/maia5), and [Maia 9](https://lichess.org/@/maia9).

**[Read the visual report](https://dash1971.github.io/researching-maia-games-on-lichess/)** · **[Download the PDF](maia-fan-report.pdf)** · [Game-level data and field guide](data/rated-games/README.md) · [Aggregate results](data/rated_summary.json) · [Fan insights](data/fan_insights.json) · [Early/later analysis](data/learning_insights.json) · [Methods and limits](RESEARCH_PLAN.md)

**New supplement:** [Casual versus rated visual comparison](casual-vs-rated.html) · [Supplement PDF](20261008_v0_maia_casual_comparison.pdf) · [Casual game metadata](data/casual-games/README.md) · [Comparison aggregates](data/casual_comparison.json)

In the three-year exports, casual games number **2,040,728** versus **1,425,567** rated games. Across comparable complete-year periods, rated games grew **79.4%** and casual games **37.7%**; one public account generated over half of September 2026's casual games, so the [supplement](casual-vs-rated.html) also shows the trend without that account. These are observed game counts, not counts of people or evidence that one format causes different outcomes.

## Three scopes

| Scope | Contents | Use |
| --- | --- | --- |
| **All-time profile snapshot**, 2026-10-04 07:12 UTC | 6,486,805 summed bot-game entries, rated **and casual**. Twenty-one Maia-vs-Maia games appear twice, leaving 6,486,784 unique games. | Historical scale and rated/casual mix. Not a monthly series or count of people. |
| **Three-year rated export**, games with last recorded move 2023-10-04 00:00 UTC to before 2026-10-04 09:00 UTC | 1,425,567 game-level metadata records. There is no Maia-vs-Maia overlap in this window, so all 1,425,567 are unique games. | Monthly rated play, opponent accounts and ratings, exact clocks, color, and openings. **Not casual or all-time play.** |
| **Three-year casual export**, same last-move window and bots | 2,040,728 game-level metadata records, all with unique game IDs within and across the rated export. | Like-for-like casual/rated volume, accounts, clocks, ratings, and outcomes. **Not all-time play.** |

“Bot-game entry” means one game attached to one bot account. “Unique game” means one game ID counted once even if two Maia bots played each other. The report never switches denominator without saying so. The last recorded move timestamp sets the export's scope and monthly counts; it can precede resignation or flag fall. October 2023 and October 2026 are partial months, omitted from the monthly chart/table and growth comparison.

## What is published

- All **rated and casual game metadata** saved by the downloaders: 12 year/bot CSV.gz shards per format with public Lichess opponent handles and game IDs. Row counts and SHA-256 hashes are in the [rated](data/rated-games/manifest.json) and [casual](data/casual-games/manifest.json) manifests. No moves, PGNs, chat, private identity mapping, or credentials were collected or included.
- A [field guide](data/rated-games/README.md), [aggregate JSON](data/rated_summary.json), [fan-insight JSON](data/fan_insights.json), and Python standard-library scripts to export and rebuild the report.
- A more visual report: all-time rated/casual bars, monthly rated-game chart, public-account leaderboard, repeat-play concentration, clocks, ratings, and openings, plus results by color, rating bands, and quick returns after wins or losses.
- A separate [casual/rated supplement](casual-vs-rated.html) with a complete-month trend, bot and clock comparisons, account overlap, rating perspectives, and outcome caveats. The original rated-focused report is unchanged.

From the repository root, verify the frozen dataset and reproduce all three JSON outputs and the HTML offline:

```sh
python3 scripts/build_rated_report.py
python3 scripts/build_casual_comparison.py
```

These scripts check shard hashes and row counts, game time windows and unique IDs, and final record counts. The supplement builder also checks that no game ID occurs in both formats. To re-export shards from compatible, privately obtained SQLite sources, run `python3 scripts/export_rated_games.py --db /path/to/rated.sqlite3` and `python3 scripts/export_casual_games.py --db /path/to/casual.sqlite3`. The working databases and access token are **not** in this repository.

The static report is self-contained: its charts and interactions work without remote assets, analytics, or tracking. GitHub Actions runs the analysis tests and checks that rebuilding produces no changes to the committed HTML or JSON. Validated changes on `main` publish the report and data to GitHub Pages.

Both PDFs are A4 print renderings of their generated HTML pages, made with headless Chrome and its `--no-pdf-header-footer` option. The HTML pages are the reproducible report sources; they require no remote assets.

The older profile/Insights [snapshot JSON](data/summary.json), [PDF](https://github.com/Dash1971/researching-maia-games-on-lichess/blob/main/20261004_v1_researching_maia_games_report.pdf), and scripts are retained for provenance. **That PDF is superseded** by the new rated-game report.

## Do regular players score better later?

In a selected group of 1,066 persistent accounts (about 1.15% of the 93,020 observed accounts) playing the same Maia at the same exact clock and speed, mean score rose from 45.1% in their first 20 observed games to 48.3% in their last 20: **+3.2 percentage points**. A stricter group of 649 accounts showed **+2.9 points**. Maia 1 had the strongest consistent increase; Maia 9 showed no robust increase across both comparisons. These accounts are a persistent subset, and outside practice, changing opponents and selection effects remain possible explanations. This does not show that Maia caused improvement. The [methods](RESEARCH_PLAN.md) and [complete results](data/learning_insights.json) explain selection and matching.

## Sources and caution

Sources: Lichess [profiles](https://lichess.org/api#operation/apiUser), [bot crosstables](https://lichess.org/api#operation/apiCrosstable), and [user-game export](https://lichess.org/api#operation/apiGamesUser). The old Insights slices were stale and are **not** used for the three-year analysis. The filtered export's observed 10,000-response cap was handled with smaller date ranges; see the [methods](RESEARCH_PLAN.md).

Public account handles are not proof of distinct people. Neither ratings nor movement between bot levels show that Maia caused improvement. Casual/rated comparisons are observational: account mix, clocks, and bot choices differ. Opening names are Lichess metadata, reached by both players; first moves cannot be recovered without moves. The three-year exports are frozen sets of observed games, not guaranteed censuses: public metadata cannot independently prove that the API returned every eligible game. The all-time profile counters are a moving snapshot, not a complete all-time game-level archive.

The MIT license applies to original code, report writing, and visuals—not to Lichess or player-originated data. Consult [Lichess's terms](https://lichess.org/terms-of-service) and the [Lichess open database's separate license statement](https://database.lichess.org/). Independent fan research; not an official Lichess or Maia publication.
