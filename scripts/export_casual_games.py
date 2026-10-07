#!/usr/bin/env python3
"""Deterministically export the locally collected casual Maia metadata to CSV.gz.

Usage: python3 scripts/export_casual_games.py --db /path/to/games.sqlite3
The input database is not included in this repository. No credentials are used.
"""

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import sqlite3
from collections import Counter
from pathlib import Path

BOTS = ("maia1", "maia5", "maia9")
START = int(dt.datetime(2023, 10, 4, tzinfo=dt.timezone.utc).timestamp() * 1000)
END = int(dt.datetime(2026, 10, 4, 9, tzinfo=dt.timezone.utc).timestamp() * 1000)
COLUMNS = (
    "bot", "game_id", "opponent_id", "created_at_ms", "last_move_at_ms",
    "bot_color", "winner", "status", "speed", "perf", "variant", "source",
    "opening_eco", "opening_name", "bot_rating", "opponent_rating",
    "clock_initial_seconds", "clock_increment_seconds",
)
SELECT = """SELECT bot, game_id, opponent_id, created_at, last_move_at,
bot_color, winner, status, speed, perf, variant, source, opening_eco,
opening_name, bot_rating, opponent_rating, clock_initial, clock_increment
FROM bot_games ORDER BY bot, created_at, game_id"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/casual-games"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f"file:{args.db.resolve()}?mode=ro", uri=True)
    assert con.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    assert con.execute("SELECT count(*) FROM bot_games WHERE last_move_at IS NULL OR last_move_at < ? OR last_move_at >= ?", (START, END)).fetchone()[0] == 0
    assert con.execute("SELECT count(*) FROM bot_games").fetchone()[0] == 2040728

    writers = {}
    counts = Counter()
    seen_ids = set()
    try:
        for row in con.execute(SELECT):
            bot, game_id, _, _, last_move_at, *_ = row
            assert bot in BOTS and game_id not in seen_ids
            seen_ids.add(game_id)
            year = dt.datetime.fromtimestamp(last_move_at / 1000, dt.timezone.utc).year
            assert year in (2023, 2024, 2025, 2026)
            name = f"{bot}_{year}.csv.gz"
            if name not in writers:
                raw = (args.out / name).open("wb")
                zipped = gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9)
                text = io.TextIOWrapper(zipped, encoding="utf-8", newline="")
                writer = csv.writer(text, lineterminator="\n")
                writer.writerow(COLUMNS)
                writers[name] = (raw, zipped, text, writer)
            writers[name][3].writerow(row)
            counts[name] += 1
    finally:
        for raw, zipped, text, _ in writers.values():
            text.close()  # closes gzip too
            raw.close()
        con.close()

    assert sum(counts.values()) == 2040728 == len(seen_ids)
    shards = []
    for name in sorted(counts):
        path = args.out / name
        shards.append({
            "file": name,
            "rows": counts[name],
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    manifest = {
        "dataset": "Casual games involving official Lichess Maia 1, 5, and 9 bots",
        "source": "Lichess user-game export API, filtered to casual (rated=false) games",
        "source_url": "https://lichess.org/api#operation/apiGamesUser",
        "start_utc_inclusive": "2023-10-04T00:00:00Z",
        "end_utc_exclusive": "2026-10-04T09:00:00Z",
        "time_basis": "last_move_at_ms (last recorded move; may precede resignation or flag fall)",
        "records": sum(counts.values()),
        "distinct_game_ids": len(seen_ids),
        "fields": COLUMNS,
        "shards": shards,
        "notes": [
            "One CSV row per bot/game pair; no Maia-versus-Maia duplicates occurred in this window.",
            "The export contains metadata only. Moves, PGNs, chat and private account details were not collected.",
            "Opponent IDs are public Lichess account handles; 2 records have no opponent ID.",
        ],
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": manifest["records"], "shards": len(shards), "bytes": sum(x["bytes"] for x in shards)}, indent=2))


if __name__ == "__main__":
    main()
