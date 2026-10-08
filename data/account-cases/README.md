# Two high-volume Maia account case studies

This supplement examines the two public accounts with the most **collected
casual games against Maia 1, 5, and 9** in the repository's fixed three-year
window. These are not account-wide histories. The public user-game export
returned HTTP 404 for both accounts when checked on October 8, 2026; game
records were recovered by their known IDs through Lichess's
[bulk game-ID export](https://lichess.org/api#operation/gamesExportIds).

| File | Content |
| --- | --- |
| `scissorsharpness.ndjson.gz` | Full public Lichess game JSON, including moves and available clocks, for 63,504 identified casual Maia games |
| `top1mostplayedgames.ndjson.gz` | The same for 27,506 identified casual Maia games |
| `manifest.json` | Byte sizes, row counts, and SHA-256 hashes for both files |
| `profile_status_20261008.json` | Minimal public profile-API snapshots, with retrieval time |
| `summary.json` | Reproducible comparisons and daily counts |
| `replay_verification.json` | Move replay, checkmate and starting-board validity checks |

## Observed patterns

- `scissorsharpness`: 63,504 standard 1+0 games, 63,343 resignations,
  median four half-moves and a 3.71-second median gap between starts.
- `top1mostplayedgames`: 27,506 games from six chosen initial positions.
  Maia won every game; 27,504 ended after one half-move, 27,505 by checkmate
  and one by resignation. This account contributed 23.3% of the broader
  casual corpus's `fromPosition` games. Its median gap between starts was
  2.09 seconds.

All 27,505 mate-tagged games replay to checkmate on their supplied boards. However, 10,052 games use a starting board with 17 white pieces, including eight pawns; it fails basic orthodox validity. Passing basic validity for the other five boards does not prove historical reachability.

These are behavioral descriptions, **not** findings of rule violations.

One NDJSON line is one Lichess game object. The `id` joins to the public
[`casual-games`](../casual-games/) CSV's `game_id`. `createdAt` and
`lastMoveAt` are Unix milliseconds UTC; `moves` is a space-separated SAN move
list, one token per half-move. A `fromPosition` game's `initialFen` records its
chosen starting board and side to move. Lichess's `clocks` array is in
centiseconds when present. The repository's MIT license applies to original
code and writing, **not** as a relicensing claim over Lichess or player data.

The raw records were downloaded sequentially, at most 300 known IDs per
request, with exact-ID, player, and casual-status checks before each batch was
persisted. An incomplete response was retried rather than counted as coverage.
Run `python3 scripts/build_account_case_studies.py` from the repository root
to verify the existing casual CSV manifest, both raw-game file hashes, every
selected game ID and core metadata field, and regenerate `summary.json`.
The analysis does not need a private database, API credentials, or new network
requests.
For a separate move/checkmate replay and starting-board validity audit of every custom-position game,
install the optional `chess==1.11.2` Python package and run
`python3 scripts/verify_account_mates.py`. The published CI does this check;
the library is not bundled into the repository.

## Interpretation limits

- `lastMoveAt` is the last recorded move, not necessarily resignation time;
  it cannot establish exact duration of a resigned game.
- A public handle is not proof of a unique person. Game exports do not reveal
  who controlled an account, how a challenge was created, or whether moves
  came through the GUI or an official API.
- Both saved profile responses contain `disabled: true` but **no public
  enforcement reason**. The flag alone does not establish a ban, cheating,
  automation, or a Terms-of-Service finding.
- Observed Maia games are not all games these accounts may have played. The
  ranking is within the collected casual Maia corpus, not all of Lichess.

Rules context: [Lichess Fair Play](https://lichess.org/page/fair-play) describes
permitted and forbidden move-input methods, while the
[Terms of Service](https://lichess.org/terms-of-service) explain that accounts
can be restricted or closed for multiple reasons. The records here cannot
identify the applicable reason, if any.
