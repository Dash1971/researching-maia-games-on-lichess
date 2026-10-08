#!/usr/bin/env python3
"""Rebuild two high-volume Maia account case studies from published game data.

Run from the repository root: python3 scripts/build_account_case_studies.py
No network access or private database is required.
"""

import collections
import csv
import datetime as dt
import gzip
import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASUAL = ROOT / "data" / "casual-games"
CASES = ROOT / "data" / "account-cases"
ACCOUNTS = ("scissorsharpness", "top1mostplayedgames")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values, fraction):
    assert values
    ordered = sorted(values)
    return ordered[int((len(ordered) - 1) * fraction)]


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).isoformat()


def read_published_casual_metadata():
    manifest = json.loads((CASUAL / "manifest.json").read_text(encoding="utf-8"))
    counts = collections.Counter()
    selected = {account: {} for account in ACCOUNTS}
    rows_seen = 0
    from_position = 0
    for shard in manifest["shards"]:
        path = CASUAL / shard["file"]
        assert path.stat().st_size == shard["bytes"]
        assert sha256(path) == shard["sha256"]
        shard_rows = 0
        with gzip.open(path, "rt", encoding="utf-8", newline="") as source:
            for row in csv.DictReader(source):
                shard_rows += 1
                from_position += row["variant"] == "fromPosition"
                account = row["opponent_id"].lower()
                if account:
                    counts[account] += 1
                if account in selected:
                    gid = row["game_id"]
                    assert gid not in selected[account]
                    selected[account][gid] = row
        assert shard_rows == shard["rows"]
        rows_seen += shard_rows
    assert rows_seen == manifest["records"] == 2040728
    assert from_position == 118056
    leaders = counts.most_common(2)
    assert leaders == [("scissorsharpness", 63504), ("top1mostplayedgames", 27506)]
    return selected, leaders, from_position


def analyze_account(account, metadata, input_spec):
    path = CASES / input_spec["file"]
    assert path.stat().st_size == input_spec["bytes"]
    assert sha256(path) == input_spec["sha256"]
    seen = set()
    statuses = collections.Counter()
    variants = collections.Counter()
    speeds = collections.Counter()
    controls = collections.Counter()
    bots = collections.Counter()
    outcomes = collections.Counter()
    bot_outcomes = collections.defaultdict(collections.Counter)
    fen_and_moves = collections.Counter()
    fens = collections.Counter()
    move_lists = collections.Counter()
    plies = []
    own_moves = []
    starts = []
    last_move_lags = []
    daily = collections.Counter()
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            game = json.loads(line)
            gid = game["id"]
            assert gid in metadata and gid not in seen
            seen.add(gid)
            row = metadata[gid]
            assert game["rated"] is False
            assert game["createdAt"] == int(row["created_at_ms"])
            assert game["lastMoveAt"] == int(row["last_move_at_ms"])
            assert game["status"] == row["status"]
            assert game["variant"] == row["variant"]
            assert game.get("winner", "") == row["winner"], gid
            assert game["speed"] == row["speed"], gid
            assert game["clock"]["initial"] == int(row["clock_initial_seconds"]), gid
            assert game["clock"]["increment"] == int(row["clock_increment_seconds"]), gid
            assert {side.get("user", {}).get("id") for side in game["players"].values()} >= {account, row["bot"]}
            account_color = "white" if game["players"]["white"].get("user", {}).get("id") == account else "black"
            assert account_color != row["bot_color"]
            first_color = "black" if game.get("initialFen", "").split()[1:2] == ["b"] else "white"
            moves = game.get("moves", "")
            tokens = moves.split()
            own = sum((first_color if i % 2 == 0 else ("black" if first_color == "white" else "white")) == account_color for i in range(len(tokens)))
            own_moves.append(own)
            plies.append(len(tokens))
            statuses[game["status"]] += 1
            variants[game["variant"]] += 1
            speeds[row["speed"]] += 1
            controls[f'{row["clock_initial_seconds"]}+{row["clock_increment_seconds"]}'] += 1
            bots[row["bot"]] += 1
            winner = game.get("winner")
            bot_result = ("win" if winner == row["bot_color"] else "loss" if winner in ("white", "black")
                          else "draw" if not winner and game["status"] in ("draw", "stalemate") else "unknown")
            bot_outcomes[row["bot"]]["games"] += 1
            bot_outcomes[row["bot"]][bot_result] += 1
            outcomes["account_win" if winner == account_color else "maia_win" if winner in ("white", "black") else "no_winner"] += 1
            fen = game.get("initialFen") or "standard start"
            fens[fen] += 1
            move_lists[moves] += 1
            fen_and_moves[(fen, moves)] += 1
            starts.append(game["createdAt"])
            last_move_lags.append((game["lastMoveAt"] - game["createdAt"]) / 1000)
            daily[iso(game["createdAt"])[:10]] += 1
    assert seen == set(metadata) and len(seen) == input_spec["records"]
    assert all(counts["games"] == sum(counts[key] for key in ("win", "draw", "loss", "unknown"))
               for counts in bot_outcomes.values())
    starts.sort()
    gaps = [(b - a) / 1000 for a, b in zip(starts, starts[1:])]
    left = 0
    peak = {"games": 0}
    for right, stamp in enumerate(starts):
        while starts[left] < stamp - 3600000:
            left += 1
        count = right - left + 1
        if count > peak["games"]:
            peak = {"games": count, "from_utc": iso(starts[left]), "to_utc": iso(stamp)}
    burst = {"games": 0}
    begin = 0
    for i in range(1, len(starts) + 1):
        if i == len(starts) or starts[i] - starts[i - 1] > 30000:
            count = i - begin
            if count > burst["games"]:
                burst = {"games": count, "span_hours": round((starts[i-1]-starts[begin])/3600000, 2),
                         "first_start_utc": iso(starts[begin]), "last_start_utc": iso(starts[i-1])}
            begin = i
    return {
        "account": account, "games": len(seen), "first_start_utc": iso(starts[0]), "last_start_utc": iso(starts[-1]),
        "active_utc_days": len(daily), "by_utc_day": dict(sorted(daily.items())),
        "bot": dict(bots), "status": dict(statuses), "outcome": dict(outcomes),
        "per_bot_outcomes": {bot: {key: counts[key] for key in ("games", "win", "draw", "loss", "unknown")}
                         for bot, counts in sorted(bot_outcomes.items())},
        "variant": dict(variants), "speed": dict(speeds), "top_exact_controls_seconds": controls.most_common(8),
        "plies": {"median": percentile(plies, .5), "p90": percentile(plies, .9),
                  "one": sum(x == 1 for x in plies), "at_most_six": sum(x <= 6 for x in plies)},
        "account_moves": {"median": percentile(own_moves, .5), "zero": sum(x == 0 for x in own_moves)},
        "start_gap_seconds": {"median": round(statistics.median(gaps), 3), "p90": round(percentile(gaps, .9), 3)},
        "start_to_last_move_seconds": {"median": round(statistics.median(last_move_lags), 3),
                                       "p90": round(percentile(last_move_lags, .9), 3)},
        "peak_rolling_hour": peak, "longest_no_gap_over_30_seconds": burst,
        "unique_initial_positions": len(fens), "unique_move_lists": len(move_lists),
        "top_initial_positions": [{"fen": fen, "games": count} for fen, count in fens.most_common(8)],
        "top_move_lists": [{"moves": moves, "games": count} for moves, count in move_lists.most_common(8)],
        "top_position_and_move": [{"fen": fen, "moves": moves, "games": count} for (fen,moves), count in fen_and_moves.most_common(8)],
    }


def main(verbose=True):
    metadata, leaders, from_position = read_published_casual_metadata()
    manifest = json.loads((CASES / "manifest.json").read_text(encoding="utf-8"))
    results = {account: analyze_account(account, metadata[account], manifest["accounts"][account]) for account in ACCOUNTS}
    out = {"scope": "Collected casual games versus official Maia 1, 5 and 9 in the published three-year window; not account-wide histories",
           "casual_corpus_games": 2040728, "casual_from_position_games": from_position,
           "leaderboard_top_two": [{"account": a, "games": n} for a,n in leaders],
           "accounts": results,
           "profile_snapshot": json.loads((CASES / "profile_status_20261008.json").read_text(encoding="utf-8")),
           "limitations": ["lastMoveAt can precede resignation or time expiry and is not exact game duration",
                           "public game exports do not reveal who controlled an account or which interface created a challenge",
                           "a disabled profile flag gives no public reason for closure or restriction"]}
    (CASES / "summary.json").write_text(json.dumps(out,indent=2,ensure_ascii=False) + "\n",encoding="utf-8")
    if verbose:
        print(json.dumps({a:{"games":x["games"],"status":x["status"],"plies":x["plies"],"account_moves":x["account_moves"],"top_position_and_move":x["top_position_and_move"][:2]} for a,x in results.items()},indent=2))
    return out


if __name__ == "__main__":
    main()
