"""Collect public, aggregate-only Lichess Maia data (Python standard library)."""

import datetime as dt
import json
import itertools
import re
import urllib.request
from pathlib import Path


BOTS = ("maia1", "maia5", "maia9")
ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"User-Agent": "maia-public-research/0.1 (read-only aggregate research)"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as response:
        return response.read().decode("utf-8")


def insight(bot, dimension, filters=None):
    url = f"https://lichess.org/insights/data/{bot}"
    body = json.dumps({"metric": "result", "dimension": dimension, "filters": filters or {}}).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={**HEADERS, "Content-Type": "application/json", "Origin": "https://lichess.org", "Referer": f"https://lichess.org/insights/{bot}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    categories = result["xAxis"]["categories"]
    sizes = result["sizeSerie"]["data"]
    series = {row["name"]: row["data"] for row in result["series"]}
    assert len(categories) == len(sizes)
    return {
        "categories": categories,
        "counts": sizes,
        "bot_result_percent": series,
        "total_in_displayed_categories": sum(sizes),
    }


def main():
    collected = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    output = {"collected_utc": collected, "accounts": {}, "cross_bot_games": {}}
    for bot in BOTS:
        profile = json.loads(get(f"https://lichess.org/api/user/{bot}"))
        assert profile["id"].lower() == bot and profile["title"] == "BOT"
        page = get(f"https://lichess.org/insights/{bot}")
        match = re.search(r'"nbGames":(\d+),"stale":(true|false)', page)
        if not match:
            raise RuntimeError(f"Missing indexed-game/staleness marker for {bot}")
        dimensions = {
            "color": insight(bot, "color"),
            "time_control": insight(bot, "variant"),
            "opening_all": insight(bot, "openingFamily"),
            "opening_human_white": insight(bot, "openingFamily", {"color": ["black"]}),
            "opening_human_black": insight(bot, "openingFamily", {"color": ["white"]}),
            "date_bins": insight(bot, "date"),
        }
        dates = dimensions.pop("date_bins")
        output["accounts"][bot] = {
            "profile_count": {key: profile["count"][key] for key in ("all", "rated", "win", "draw", "loss", "playing")},
            "insights_indexed_rated_games": int(match.group(1)),
            "insights_stale": match.group(2) == "true",
            "sample_oldest_bin_date_utc": dt.datetime.fromtimestamp(dates["categories"][0], dt.timezone.utc).date().isoformat(),
            "sample_newest_bin_date_utc": dt.datetime.fromtimestamp(dates["categories"][-1], dt.timezone.utc).date().isoformat(),
            "insights": dimensions,
        }
        assert sum(dimensions["color"]["counts"]) == 15000
        assert sum(dimensions["time_control"]["counts"]) == 15000
        assert output["accounts"][bot]["profile_count"]["all"] >= output["accounts"][bot]["profile_count"]["rated"]
    for first, second in itertools.combinations(BOTS, 2):
        pair = json.loads(get(f"https://lichess.org/api/crosstable/{first}/{second}"))
        output["cross_bot_games"][f"{first}_vs_{second}"] = pair["nbGames"]
    path = ROOT / "data" / "summary.json"
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
