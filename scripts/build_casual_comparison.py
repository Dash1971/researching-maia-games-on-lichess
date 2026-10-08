#!/usr/bin/env python3
"""Verify both published Maia corpora and build the casual/rated supplement.

Standard library only. All findings are derived from the CSV.gz files in this
repository; the private collection databases and Lichess token are not needed.
"""

import collections
import csv
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
from fan_insights import outcome

ROOT = Path(__file__).resolve().parents[1]
BOTS = ("maia1", "maia5", "maia9")
START = int(dt.datetime(2023, 10, 4, tzinfo=dt.timezone.utc).timestamp() * 1000)
END = int(dt.datetime(2026, 10, 4, 9, tzinfo=dt.timezone.utc).timestamp() * 1000)
MONTHS = [f"{year}-{month:02d}" for year in range(2023, 2027)
          for month in range(1, 13)
          if "2023-11" <= f"{year}-{month:02d}" <= "2026-09"]
EXPECTED = {"rated": 1425567, "casual": 2040728}
COLORS = {"rated": "#95684d", "casual": "#367451"}


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def control_label(initial, increment):
    if initial is None or increment is None:
        return "No recorded clock"
    return f"{initial // 60}+{increment}" if initial % 60 == 0 else f"{initial}s+{increment}s"


def scan(kind, seen):
    folder = ROOT / "data" / f"{kind}-games"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["records"] == EXPECTED[kind]
    result = {
        "entries": 0, "per_bot": collections.Counter(), "monthly": collections.Counter(),
        "monthly_accounts": collections.defaultdict(set),
        "sept_account_games": collections.Counter(),
        "sept_account_bot": collections.Counter(),
        "sept_account_clock": collections.Counter(),
        "speed": collections.Counter(), "controls": collections.Counter(),
        "accounts": collections.Counter(), "account_rating": collections.defaultdict(lambda: [0, 0]),
        "rating_sum": 0, "rating_n": 0, "bot_decisive": collections.Counter(),
        "bot_wins": collections.Counter(), "no_winner": collections.Counter(),
        "missing_opponent": 0, "missing_rating": 0, "missing_clock": 0,
        "source": collections.Counter(), "variant": collections.Counter(),
        "shards": [], "outcomes": collections.Counter(), "standard_bot_games": collections.Counter(),
        "standard_outcomes": collections.Counter(), "status": collections.Counter(),
    }
    for shard in manifest["shards"]:
        path = folder / shard["file"]
        assert path.stat().st_size == shard["bytes"], path
        assert file_sha256(path) == shard["sha256"], path
        rows = 0
        with gzip.open(path, "rt", encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            assert reader.fieldnames == manifest["fields"]
            for row in reader:
                rows += 1
                game_id = row["game_id"]
                assert game_id and game_id not in seen, (kind, game_id)
                seen.add(game_id)
                bot = row["bot"]
                assert bot in BOTS
                timestamp = int(row["last_move_at_ms"])
                assert START <= timestamp < END
                month = dt.datetime.fromtimestamp(timestamp / 1000, dt.timezone.utc).strftime("%Y-%m")
                assert shard["file"] == f"{bot}_{month[:4]}.csv.gz"
                assert row["bot_color"] in ("white", "black")
                result["entries"] += 1
                result["per_bot"][bot] += 1
                result["monthly"][(month, bot)] += 1
                result["speed"][row["speed"]] += 1
                result["source"][row["source"]] += 1
                result["variant"][row["variant"]] += 1
                result["status"][row["status"]] += 1
                opponent_result = outcome(row)
                bot_result = {"win": "loss", "loss": "win", "draw": "draw", "unknown": "unknown"}[opponent_result]
                result["outcomes"][(bot, bot_result)] += 1
                if row["variant"] == "standard":
                    result["standard_bot_games"][bot] += 1
                    result["standard_outcomes"][(bot, bot_result)] += 1
                if row["clock_initial_seconds"] and row["clock_increment_seconds"]:
                    label = control_label(int(row["clock_initial_seconds"]),
                                          int(row["clock_increment_seconds"]))
                else:
                    label = "No recorded clock"
                    result["missing_clock"] += 1
                result["controls"][label] += 1
                opponent = row["opponent_id"]
                if opponent:
                    result["accounts"][opponent] += 1
                    result["monthly_accounts"][month].add(opponent)
                    if kind == "casual" and month == "2026-09":
                        result["sept_account_games"][opponent] += 1
                        result["sept_account_bot"][(opponent, bot)] += 1
                        result["sept_account_clock"][(opponent, label)] += 1
                else:
                    result["missing_opponent"] += 1
                if row["opponent_rating"]:
                    rating = int(row["opponent_rating"])
                    result["rating_sum"] += rating
                    result["rating_n"] += 1
                    if opponent:
                        cell = result["account_rating"][opponent]
                        cell[0] += rating
                        cell[1] += 1
                else:
                    result["missing_rating"] += 1
                winner = row["winner"]
                if winner in ("white", "black"):
                    result["bot_decisive"][bot] += 1
                    if winner == row["bot_color"]:
                        result["bot_wins"][bot] += 1
                else:
                    result["no_winner"][bot] += 1
        assert rows == shard["rows"]
        result["shards"].append({"file": shard["file"], "rows": rows, "sha256": shard["sha256"]})
    assert result["entries"] == manifest["records"] == EXPECTED[kind]
    assert len(seen) == sum(EXPECTED[x] for x in ("rated", "casual")
                            if x == kind or kind == "casual")
    return result


def summarize(raw):
    entries = raw["entries"]
    accounts = raw["accounts"]
    n_accounts = len(accounts)
    top_one = sum(sorted(accounts.values(), reverse=True)[:round(n_accounts * .01)])
    account_means = [total / count for total, count in raw["account_rating"].values()]
    months = {month: sum(raw["monthly"][(month, bot)] for bot in BOTS) for month in MONTHS}
    return {
        "bot_game_entries": entries, "unique_games": entries, "per_bot": dict(raw["per_bot"]),
        "opposing_accounts": n_accounts, "missing_opponent_ids": raw["missing_opponent"],
        "missing_opponent_ratings": raw["missing_rating"], "missing_clocks": raw["missing_clock"],
        "speed": dict(raw["speed"]), "top_controls": [
            {"label": label, "games": count} for label, count in raw["controls"].most_common(10)
        ],
        "rating": {
            "game_weighted_mean": round(raw["rating_sum"] / raw["rating_n"]),
            "account_weighted_mean": round(sum(account_means) / len(account_means)),
        },
        "accounts": {
            "one_game": sum(n == 1 for n in accounts.values()),
            "top_one_percent_game_share": round(top_one / entries, 4),
        },
        "bot_win_share_of_decisive": {
            bot: round(raw["bot_wins"][bot] / raw["bot_decisive"][bot], 4) for bot in BOTS
        },
        "games_without_winner": sum(raw["no_winner"].values()),
        "first_12_complete_months": sum(months[m] for m in MONTHS[:12]),
        "last_12_complete_months": sum(months[m] for m in MONTHS[-12:]),
        "partial_october": {
            month: sum(raw["monthly"][(month, bot)] for bot in BOTS)
            for month in ("2023-10", "2026-10")
        },
        "source": dict(raw["source"]), "variant": dict(raw["variant"]),
        "status": dict(raw["status"]),
        "outcomes_all_games": [{"bot": bot, "games": raw["per_bot"][bot], **{result: raw["outcomes"][(bot,result)] for result in ("win","draw","loss","unknown")}} for bot in BOTS],
        "outcomes_standard": [{"bot": bot, "games": raw["standard_bot_games"][bot], **{result: raw["standard_outcomes"][(bot,result)] for result in ("win","draw","loss","unknown")}} for bot in BOTS],
    }


def main():
    seen = set()
    print("Verifying rated shards…", flush=True)
    rated_raw = scan("rated", seen)
    rated_accounts = set(rated_raw["accounts"])
    print("Verifying casual shards…", flush=True)
    casual_raw = scan("casual", seen)
    casual_accounts = set(casual_raw["accounts"])
    rated, casual = summarize(rated_raw), summarize(casual_raw)
    monthly = [{"month": month,
                "rated": sum(rated_raw["monthly"][(month, bot)] for bot in BOTS),
                "casual": sum(casual_raw["monthly"][(month, bot)] for bot in BOTS),
                "rated_accounts": len(rated_raw["monthly_accounts"][month]),
                "casual_accounts": len(casual_raw["monthly_accounts"][month])}
               for month in MONTHS]
    for point in monthly:
        point["casual_share_pct"] = round(100 * point["casual"] / (point["rated"] + point["casual"]), 1)
    top_handle, top_games = casual_raw["sept_account_games"].most_common(1)[0]
    sep = next(point for point in monthly if point["month"] == "2026-09")
    aug = next(point for point in monthly if point["month"] == "2026-08")
    concentration = {
        "handle": top_handle, "games": top_games,
        "sensitivity_definition": "Subtract only this account’s September 2026 casual games from the last 12-month total; retain its other months and the entire first period.",
        "share_of_september_pct": round(100 * top_games / sep["casual"], 1),
        "september_without_account": sep["casual"] - top_games,
        "august_games": aug["casual"],
        "september_accounts": sep["casual_accounts"],
        "august_accounts": aug["casual_accounts"],
        "one_plus_zero_games": casual_raw["sept_account_clock"][(top_handle, "1+0")],
        "by_bot": {bot: casual_raw["sept_account_bot"][(top_handle, bot)] for bot in BOTS},
        "growth_excluding_account_pct": round(100 * ((casual["last_12_complete_months"] - top_games) / casual["first_12_complete_months"] - 1), 1),
    }
    data = {
        "scope": {"start_utc_inclusive": "2023-10-04T00:00:00Z",
                  "end_utc_exclusive": "2026-10-04T09:00:00Z",
                  "time_basis": "last recorded move (last_move_at_ms)"},
        "rated": rated, "casual": casual,
        "combined_unique_games": rated["unique_games"] + casual["unique_games"],
        "account_overlap": {"both": len(rated_accounts & casual_accounts),
                            "rated_only": len(rated_accounts - casual_accounts),
                            "casual_only": len(casual_accounts - rated_accounts)},
        "monthly_complete": monthly,
        "september_2026_concentration": concentration,
        "limitations": [
            "Partial October 2023 and October 2026 are excluded from month comparisons.",
            "Account handles are not verified unique people; prolific accounts affect game-weighted metrics.",
            "A seven-day game-start lookback cannot guarantee capture of games lasting longer than seven days across the starting edge.",
            "Bulk metadata omits moves, starting boards and chat; a separate two-account follow-up includes public moves and FENs. Opening names are source metadata.",
            "Rated and casual accounts, clocks, bot choices and variant tags differ. Descriptive comparisons are not causal effects.",
            "Casual includes fromPosition games. Exact starting FENs are absent from the bulk metadata; the separate two-account follow-up collected them. Standard-tagged subsets are shown separately.",
            "Outcome percentages use all games as denominator unless explicitly labeled decisive-only or score.",
        ],
    }
    (ROOT / "data" / "casual_comparison.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    from comparison_behaviour import build_behaviour
    from render_casual_supplement import render
    print("Computing cross-format behaviour…", flush=True)
    behaviour = build_behaviour()
    (ROOT / "data" / "comparison_behaviour.json").write_text(json.dumps(behaviour, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    from build_account_case_studies import main as build_cases
    cases = build_cases(verbose=False)
    (ROOT / "casual-vs-rated.html").write_text(render(data, behaviour, cases), encoding="utf-8")
    with (ROOT / "data" / "casual_comparison_monthly.csv").open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=("month", "rated", "casual", "casual_share_pct", "rated_accounts", "casual_accounts"), lineterminator="\n")
        writer.writeheader()
        writer.writerows(monthly)
    print(json.dumps({"rated": rated["bot_game_entries"], "casual": casual["bot_game_entries"],
                      "account_overlap": data["account_overlap"],
                      "growth_rated_pct": round(100 * (rated["last_12_complete_months"] / rated["first_12_complete_months"] - 1), 1),
                      "growth_casual_pct": round(100 * (casual["last_12_complete_months"] / casual["first_12_complete_months"] - 1), 1)}, indent=2))


if __name__ == "__main__":
    main()
