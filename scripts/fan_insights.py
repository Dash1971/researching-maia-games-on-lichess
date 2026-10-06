#!/usr/bin/env python3
"""Rebuild extra fan-report facts from the published CSVs (stdlib only).

Streams CSV shards into counters and a temporary on-disk SQLite sort. No public
account handles or game IDs are included in the output. Run from any directory.
"""
import collections
import csv
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BOTS = ('maia1', 'maia5', 'maia9')
OUTCOMES = ('win', 'draw', 'loss', 'unknown')  # human/opponent perspective
BANDS = ('<1000', '1000–1199', '1200–1399', '1400–1599', '1600–1799', '1800–1999', '2000+')


def outcome(row):
    """A blank winner is a draw only for a known drawn end status."""
    winner = row['winner']
    if winner in ('white', 'black'):
        return 'loss' if winner == row['bot_color'] else 'win'
    if not winner and row['status'] in ('draw', 'stalemate'):
        return 'draw'
    return 'unknown'


def pack(counter):
    n = sum(counter.values())
    known = n - counter['unknown']
    return {'games': n, **{k: counter[k] for k in OUTCOMES},
            'win_pct_of_all_games': round(100 * counter['win'] / n, 3) if n else None,
            'score_pct_of_known_outcomes': round(100 * (counter['win'] + counter['draw'] / 2) / known, 3) if known else None}


def rating_band(rating):
    if rating < 1000:
        return BANDS[0]
    return BANDS[min(6, (rating - 1000) // 200 + 1)]


def build_insights(data_dir=None):
    data_dir = Path(data_dir) if data_dir else ROOT / 'data' / 'rated-games'
    manifest = json.loads((data_dir / 'manifest.json').read_text())
    end_ms = int(dt.datetime.fromisoformat(manifest['end_utc_exclusive'].replace('Z', '+00:00')).timestamp() * 1000)
    counts = collections.defaultdict(collections.Counter)
    colors = collections.defaultdict(collections.Counter)
    bands = collections.defaultdict(collections.Counter)
    band_speed = collections.defaultdict(collections.Counter)
    openings = collections.defaultdict(collections.Counter)
    statuses = collections.Counter()
    missing = collections.Counter()
    hours = collections.Counter()
    total = 0
    with tempfile.TemporaryDirectory(prefix='maia-fan-insights-') as temporary:
        connection = sqlite3.connect(str(Path(temporary) / 'sort.sqlite3'))
        connection.execute('CREATE TABLE games (account TEXT, bot TEXT, created INTEGER, finished INTEGER, outcome TEXT, id TEXT)')
        batch = []
        for shard in manifest['shards']:
            path = data_dir / shard['file']
            digest = hashlib.sha256()
            with path.open('rb') as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b''):
                    digest.update(block)
            if digest.hexdigest() != shard['sha256']:
                raise ValueError(f'Checksum mismatch: {path.name}')
            shard_rows = 0
            with gzip.open(path, 'rt', encoding='utf-8', newline='') as handle:
                reader = csv.DictReader(handle)
                if reader.fieldnames != manifest['fields']:
                    raise ValueError(f'Unexpected columns: {path.name}')
                for row in reader:
                    total += 1
                    shard_rows += 1
                    bot = row['bot']
                    result = outcome(row)
                    counts[bot][result] += 1
                    player_color = 'black' if row['bot_color'] == 'white' else 'white'
                    colors[bot, player_color][result] += 1
                    statuses[row['status'], row['winner']] += 1
                    if row['opponent_rating']:
                        band = rating_band(int(row['opponent_rating']))
                        bands[bot, band][result] += 1
                        band_speed[bot, band][row['speed']] += 1
                    else:
                        missing['opponent_rating'] += 1
                    if row['opening_name']:
                        family = row['opening_name'].split(':', 1)[0]
                        openings[bot, player_color, family][result] += 1
                    else:
                        missing['opening_name'] += 1
                    created, finished = int(row['created_at_ms']), int(row['last_move_at_ms'])
                    hours[dt.datetime.fromtimestamp(created / 1000, dt.timezone.utc).hour] += 1
                    if row['opponent_id']:
                        batch.append((row['opponent_id'], bot, created, finished, result, row['game_id']))
                    else:
                        missing['opponent_id'] += 1
                    if len(batch) >= 10000:
                        connection.executemany('INSERT INTO games VALUES (?,?,?,?,?,?)', batch)
                        batch.clear()
            if shard_rows != shard['rows']:
                raise ValueError(f'Row count mismatch: {path.name}')
        connection.executemany('INSERT INTO games VALUES (?,?,?,?,?,?)', batch)
        connection.commit()
        if total != manifest['records']:
            raise ValueError('Total record count mismatch')
        connection.execute('CREATE INDEX account_time ON games (account, created, id)')
        returns = collections.defaultdict(collections.Counter)
        gap_counts = collections.Counter()
        account_count = account_games = quick_accounts = 0
        game_buckets = collections.Counter()
        previous = None
        current_account = None
        current_count = 0
        current_quick = False
        def finish_account():
            nonlocal account_count, account_games, quick_accounts
            if current_count:
                account_count += 1
                account_games += current_count
                quick_accounts += int(current_quick)
                bucket = '1' if current_count == 1 else '2–9' if current_count < 10 else '10–49' if current_count < 50 else '50–199' if current_count < 200 else '200+'
                game_buckets[bucket] += 1
        for account, bot, created, finished, result, game_id in connection.execute('SELECT * FROM games ORDER BY account, created, id'):
            if account != current_account:
                finish_account()
                current_account = account
                current_count = 0
                current_quick = False
                previous = None
            current_count += 1
            eligible = finished <= end_ms - 600000 and finished >= created
            if eligible:
                returns[bot, result]['eligible_games'] += 1
            if previous is not None:
                old_bot, old_finished, old_result, old_eligible = previous
                gap = created - old_finished
                if gap < 0:
                    gap_counts['overlapping_next_game'] += 1
                else:
                    bucket = '0–1 minute' if gap <= 60000 else '1–10 minutes' if gap <= 600000 else '10–60 minutes' if gap <= 3600000 else '1–24 hours' if gap <= 86400000 else '1+ days'
                    gap_counts[bucket] += 1
                    if gap <= 600000 and old_eligible:
                        returns[old_bot, old_result]['quick_return_any_maia'] += 1
                        if bot == old_bot:
                            returns[old_bot, old_result]['quick_return_same_maia'] += 1
                        current_quick = True
            previous = bot, finished, result, eligible
        finish_account()
        connection.close()

    return_rows = []
    for bot in BOTS:
        for result in OUTCOMES:
            counter = returns[bot, result]
            eligible = counter['eligible_games']
            return_rows.append({'bot': bot, 'previous_opponent_outcome': result,
                                **{k: counter[k] for k in ('eligible_games', 'quick_return_any_maia', 'quick_return_same_maia')},
                                'same_maia_pct': round(100 * counter['quick_return_same_maia'] / eligible, 3) if eligible else None})
    return {
        'dataset': {'records': total, 'start_utc_inclusive': manifest['start_utc_inclusive'], 'end_utc_exclusive': manifest['end_utc_exclusive'], 'scope': 'Rated standard games against official Maia 1, 5 and 9; last-recorded-move-time bounded.'},
        'definitions': {
            'outcomes': 'Opponent perspective. Win/loss require a white/black winner. Blank winner is a draw only when status is draw or stalemate; otherwise unknown.',
            'win_pct': 'Wins divided by all games, with draws and unknowns retained in denominator.',
            'score_pct': '(Wins + half draws) divided by games with known outcomes.',
            'rating_bands': 'Recorded opponent Lichess rating at game time. Speed pools differ; distributions and outcomes mix speeds and do not estimate skill or causal effects.',
            'opening_families': 'Opening name before the first colon, reached by both players. Not a first-move reconstruction or a causal estimate of opening strength. Top 12 by volume per bot and opponent color.',
            'quick_return': 'The same public opponent account starts its next observed rated game against any of the three Maia bots 0–600 seconds after the prior game last_move_at_ms (last recorded move, which may precede resignation or flagging). Same-Maia subset also requires the next bot to match. No claim of a formal Lichess rematch or complete account history.',
            'quick_return_denominator': 'All games with a known opponent ID and nonnegative recorded duration, with last_move_at_ms at least 10 minutes before dataset end. Includes games with no observed next game. Last-move-time scope may omit games continuing past the end; casual games and games against other accounts are unobserved.',
            'return_comparison': 'Descriptive game-level rates, not independent-player experiments. Accounts with many games have more weight. Prior results may correlate with ratings, clocks, and individual habits.',
            'gaps': 'Between consecutive observed Maia rated games per opponent account, ordered by created_at_ms then game_id; negative gaps are counted separately as overlaps.',
            'accounts': 'Public account IDs, not necessarily distinct people. Account activity includes all three bots.'},
        'missing_fields': dict(sorted(missing.items())),
        'status_winner_counts': [{'status': s, 'winner': w or None, 'games': n} for (s, w), n in sorted(statuses.items())],
        'outcomes_by_bot': [{'bot': b, **pack(counts[b])} for b in BOTS],
        'outcomes_by_bot_and_opponent_color': [{'bot': b, 'opponent_color': c, **pack(colors[b, c])} for b in BOTS for c in ('white', 'black')],
        'rating_bands_by_bot': [{'bot': b, 'opponent_rating_band': band, **pack(bands[b, band]), 'speed_counts': dict(sorted(band_speed[b, band].items()))} for b in BOTS for band in BANDS],
        'opening_families_by_bot_and_opponent_color': [{'bot': b, 'opponent_color': c, 'opening_family': family, **pack(counter)} for b in BOTS for c in ('white', 'black') for family, counter in sorted(((family, counter) for (bb, cc, family), counter in openings.items() if bb == b and cc == c), key=lambda item: (-sum(item[1].values()), item[0]))[:12]],
        'quick_returns_by_bot_and_prior_outcome': return_rows,
        'consecutive_observed_game_gaps': dict(gap_counts),
        'opponent_accounts': {'accounts': account_count, 'games_with_known_account': account_games, 'accounts_with_at_least_one_quick_return': quick_accounts, 'game_count_buckets': dict(game_buckets)},
        'game_starts_by_utc_hour': [{'utc_hour': h, 'games': hours[h]} for h in range(24)]}


def main():
    result = build_insights()
    destination = ROOT / 'data' / 'fan_insights.json'
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(f"Wrote {destination}: {result['dataset']['records']:,} verified games")
    for row in result['outcomes_by_bot']:
        print(f"{row['bot']}: opponent wins {row['win_pct_of_all_games']:.1f}% ({row['win']:,}/{row['games']:,}); draws {row['draw']:,}")
    for row in result['quick_returns_by_bot_and_prior_outcome']:
        if row['previous_opponent_outcome'] in ('win', 'loss'):
            print(f"{row['bot']}: same-Maia quick return after opponent {row['previous_opponent_outcome']}: {row['same_maia_pct']:.1f}% ({row['quick_return_same_maia']:,}/{row['eligible_games']:,})")


if __name__ == '__main__':
    main()
