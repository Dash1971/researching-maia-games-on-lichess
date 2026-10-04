# Full-history Maia research plan — approval draft

**Status:** planning only. No full-history games have been downloaded. The public [snapshot report](index.html) uses Lichess profile totals and limited, stale Insights slices; it is **not** a lifetime game-level study.

## Scope and questions

Study every available **finished** game of the three official Lichess accounts `maia1`, `maia5`, and `maia9`, from each account's creation through a frozen cutoff chosen when the run is approved. Include **rated and casual** games and all time controls. Retain the distinction between standard-start games, games from a custom position, and any other variants.

The study should answer:

1. How many distinct opposing Lichess **accounts** played at least one of the bots, per bot and across all three? An account is not necessarily a unique person.
2. How many games did an opposing account play on average? Report mean, median, percentiles, and the one-game share; the mean alone may be misleading.
3. Which accounts played the most games, and how many? Separate human and bot opponents. Named-account publication will be reviewed separately before it goes public.
4. Are there **plausible** examples of improvement and progression from Maia 1 to Maia 5 or 9? Show time-ordered results and enough games per level, compare like-for-like time controls and colors, and avoid claiming that Maia caused improvement.
5. Which openings and first moves occur most often against each bot? Split by human color, time control, and standard versus nonstandard starts.
6. How often does each Maia bot play White or Black over its **full history**? Compare this with the current Insights-slice result.
7. Additional descriptive patterns: rated/casual mix, time controls, changes by year, rematches, and concentration of games among heavy users.

## Source and collection method

Use Lichess's [user-game export](https://github.com/lichess-org/api/blob/master/doc/specs/tags/games/api-games-user-username.yaml) with `Accept: application/x-ndjson`, an identifying User-Agent, and the least-privilege OAuth token. The endpoint documents a **30-games/second** OAuth stream for games of other accounts, compared with 20 games/second anonymously. It supports `since`, `until`, `sort`, `moves`, and `opening` parameters. The key is held outside this repository; the collector must never log it.

Proposed fields: game ID, bot ID, opposing account ID, timestamp, players and color, result, rated/casual status, time control/variant, opening name/ECO if available, and opponent rating if available. Request `moves=false`, `clocks=false`, `evals=false`, and `opening=true` initially. A small pilot must verify that those parameters really preserve all needed fields; otherwise revise before scaling. Do not save the full NDJSON response or PGN move text by default.

Process **one API request at a time**, in bounded date windows, with a durable checkpoint only after each window completes. Deduplicate on game ID (a Maia-versus-Maia game appears in two bot exports). Reconcile window totals with profile counts captured at the cutoff, allowing for games finished around the boundary and API exclusions. A 429 response means stop requesting for at least one minute and reduce the pace; repeated 429s should pause the run and be reported, not looped through. This follows [Lichess API guidance](https://lichess.org/page/api-tips).

## Size and time budget before a download

The October 4 profile snapshot contained **6,486,805 bot-account game entries**: Maia 1, 3,661,291; Maia 5, 1,430,845; Maia 9, 1,394,669. These counters keep moving. Subtracting the 21 games between two of these bots gives 6,486,784 distinct games at that snapshot; the API will still need to export both account entries for those 21 matches.

At Lichess's documented 30 games/second OAuth rate, the **mathematical minimum** is about **33.9 hours for Maia 1**, **13.3 hours for Maia 5**, and **12.9 hours for Maia 9**—**60.1 hours total**. This is a floor, not a completion promise. It assumes an uninterrupted stream at the full allowance, with no 429s, connection failures, processing, or re-reads. Plan operationally for **3–5 days**, and reassess from measured pilot throughput. An anonymous export's corresponding floor is about **90.1 hours**.

**Storage is an estimate, not a measurement.** With 6.49 million records, 250–1,000 bytes of compact retained data per game would be **1.6–6.5 GB before SQLite indexes and overhead**. Budget **2–10 GB** for the private game-level database and **15 GB free-space headroom** for indexing, checkpoints, and rework. The machine had about **63 GiB free** during this planning review; recheck before any approved run. Do not put raw games, opponent IDs, a database, a token, or local paths in the public repo.

### Gate 1 — small calibration, separately approved

After review, make one small, sequential export pilot (proposed **1,000 games**, not a full run). Confirm token acceptance, fields, record bytes, actual throughput, date-window boundaries, and whether `moves=false` preserves opening data. Estimate database bytes per game using a real private SQLite prototype. Publish only aggregate measurements and a revised time/storage budget. **Do not continue automatically to millions of games.**

### Gate 2 — full run, separately approved

Only after Dash reviews Gate 1, freeze the cutoff and launch the resumable full-history export. Store minimal game-level records in a private local data area with restrictive permissions, outside this repo. Monitor Lichess rate limits and disk headroom. Stop on repeated 429s, sustained schema errors, an unexpectedly high storage estimate, or less than the agreed free-space reserve. A multi-day run should have durable progress and an explicit stop procedure.

### Gate 3 — analysis and publication review

Validate unique game IDs, per-bot counts, opponent normalization, color/result logic, opening coverage, and missing/closed accounts. Report both raw counts and limitations. Produce a new visual report and reproducible aggregate tables. Review any proposed named-account examples or leaderboards for privacy, accuracy, and fair framing **before** a separate public update. No credential, raw game record, opponent-level database, or private identity mapping goes to GitHub.

## Current blockers and decision requested

Two small anonymous export probes returned HTTP 429, including one after a 15-minute wait. An earlier generic-User-Agent request returned 404, which did **not** prove the endpoint was down. The supplied OAuth token has been stored securely, but it has **not been used for a game export** and its Lichess validity has not yet been tested. The next decision is whether to authorize **Gate 1 only**, after reviewing this plan. Publishing this plan does **not** authorize Gate 1 or Gate 2.
