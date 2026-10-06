#!/usr/bin/env python3
"""Descriptive early/later comparisons, not a causal training study (stdlib)."""
import collections
import csv
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics
import tempfile
from fan_insights import BOTS, outcome

ROOT = Path(__file__).resolve().parents[1]
DAY_MS = 86400000


def summarize_pair(games, n=20, min_gap_days=30):
    """Compare ordered dict rows with created_ms, score, ratings, white fields.

At least 2*n games and required gap between last early and first late game.
Caller filters unknown/cheat outcomes and enforces stratum eligibility.
"""
    if len(games) < 2 * n:
        return None
    early, late = games[:n], games[-n:]
    gap = (late[0]['created_ms'] - early[-1]['created_ms']) / DAY_MS
    if gap < min_gap_days:
        return None
    mean = lambda rows, key: statistics.mean([r[key] for r in rows if r[key] is not None]) if any(r[key] is not None for r in rows) else None
    early_score, late_score = mean(early, 'score'), mean(late, 'score')
    early_rating, late_rating = mean(early, 'opponent_rating'), mean(late, 'opponent_rating')
    early_bot, late_bot = mean(early, 'bot_rating'), mean(late, 'bot_rating')
    return {'games': len(games), 'gap_days': gap, 'early_score_pct': early_score * 100,
            'late_score_pct': late_score * 100, 'score_change_pp': round((late_score - early_score) * 100, 10),
            'opponent_rating_change': late_rating - early_rating if early_rating is not None and late_rating is not None else None,
            'bot_rating_change': late_bot - early_bot if early_bot is not None and late_bot is not None else None,
            'early_white_pct': mean(early, 'white') * 100, 'late_white_pct': mean(late, 'white') * 100}


def aggregate(pairs):
    def mean(key):
        values = [p[key] for p in pairs if p[key] is not None]
        return round(statistics.mean(values), 3) if values else None
    def median(key):
        values = [p[key] for p in pairs if p[key] is not None]
        return round(statistics.median(values), 3) if values else None
    changes = [p['score_change_pp'] for p in pairs]
    return {'accounts': len(pairs), 'compared_games': len(pairs) * 40,
            'improved_accounts': sum(x > 1e-9 for x in changes), 'unchanged_accounts': sum(abs(x) <= 1e-9 for x in changes), 'declined_accounts': sum(x < -1e-9 for x in changes),
            'mean_early_score_pct': mean('early_score_pct'), 'mean_late_score_pct': mean('late_score_pct'),
            'mean_score_change_pp': mean('score_change_pp'), 'median_score_change_pp': median('score_change_pp'),
            'mean_opponent_rating_change': mean('opponent_rating_change'), 'median_opponent_rating_change': median('opponent_rating_change'),
            'accounts_with_rating_comparison': sum(p['opponent_rating_change'] is not None for p in pairs),
            'mean_bot_rating_change': mean('bot_rating_change'), 'mean_early_white_pct': mean('early_white_pct'), 'mean_late_white_pct': mean('late_white_pct'),
            'median_gap_days': median('gap_days'),
            'change_distribution': [{'label': label, 'accounts': sum(lo <= change < hi for change in changes)} for label,lo,hi in [('−100 to <−20 pp',-101,-20),('−20 to <0 pp',-20,-1e-9),('0 pp',-1e-9,1e-9),('>0 to <20 pp',1e-9,20),('20 to 100 pp',20,101)]]}


def build_learning_insights(data_dir=None):
    data_dir = Path(data_dir) if data_dir else ROOT / 'data' / 'rated-games'
    manifest = json.loads((data_dir / 'manifest.json').read_text())
    configs = [('main', 40, 30), ('sensitivity', 60, 90)]
    selected = {name: {} for name, _, _ in configs}
    exclusions = collections.Counter()
    with tempfile.TemporaryDirectory(prefix='maia-learning-') as temporary:
        db = sqlite3.connect(str(Path(temporary) / 'sort.sqlite3'))
        db.execute('CREATE TABLE games (account TEXT, bot TEXT, initial INTEGER, increment INTEGER, speed TEXT, created INTEGER, id TEXT, score REAL, opponent_rating INTEGER, bot_rating INTEGER, white INTEGER)')
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
            with gzip.open(data_dir / shard['file'], 'rt', encoding='utf-8', newline='') as handle:
                for row in csv.DictReader(handle):
                    shard_rows += 1
                    result = outcome(row)
                    reason = 'missing_account' if not row['opponent_id'] else 'cheat_status' if row['status'] == 'cheat' else 'unknown_outcome' if result == 'unknown' else None
                    if reason:
                        exclusions[reason] += 1
                        continue
                    if not row['clock_initial_seconds'] or not row['clock_increment_seconds']:
                        exclusions['missing_clock'] += 1
                        continue
                    score = {'win': 1.0, 'draw': 0.5, 'loss': 0.0}[result]
                    rating = lambda field: int(row[field]) if row[field] else None
                    batch.append((row['opponent_id'],row['bot'],int(row['clock_initial_seconds']),int(row['clock_increment_seconds']),row['speed'],int(row['created_at_ms']),row['game_id'],score,rating('opponent_rating'),rating('bot_rating'),int(row['bot_color']=='black')))
                    if len(batch) >= 10000:
                        db.executemany('INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?,?)',batch)
                        batch.clear()
            if shard_rows != shard['rows']:
                raise ValueError(f'Row count mismatch: {path.name}')
        db.executemany('INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?,?)',batch)
        db.commit()
        db.execute('CREATE INDEX strata ON games (account,bot,initial,increment,speed,created,id)')
        key = None
        rows = []
        def evaluate():
            if key is None:
                return
            account, bot, initial, increment, speed = key
            for name, minimum, days in configs:
                if len(rows) < minimum:
                    continue
                pair = summarize_pair(rows, min_gap_days=days)
                if pair is None:
                    continue
                pair['bot'] = bot
                pair['speed'] = speed
                pair['clock_initial_seconds'] = initial
                pair['clock_increment_seconds'] = increment
                rank = (-len(rows), bot, initial, increment, speed)
                existing = selected[name].get(account)
                if existing is None or rank < existing[0]:
                    selected[name][account] = (rank, pair)
        for row in db.execute('SELECT * FROM games ORDER BY account,bot,initial,increment,speed,created,id'):
            next_key = tuple(row[:5])
            if next_key != key:
                evaluate()
                key = next_key
                rows = []
            rows.append(dict(zip(('created_ms','game_id','score','opponent_rating','bot_rating','white'),row[5:])))
        evaluate()
        db.close()
    cohorts = []
    for name, minimum, days in configs:
        pairs = [p for _, p in selected[name].values()]
        clocks = collections.Counter((p['bot'],p['clock_initial_seconds'],p['clock_increment_seconds'],p['speed']) for p in pairs)
        cohorts.append({'name': name, 'minimum_games_in_matching_stratum': minimum, 'early_games': 20, 'late_games': 20, 'minimum_gap_between_windows_days': days,
                        'overall': aggregate(pairs), 'by_bot': [{'bot': b, **aggregate([p for p in pairs if p['bot']==b])} for b in BOTS],
                        'by_speed': [{'speed': speed, **aggregate([p for p in pairs if p['speed']==speed])} for speed in sorted({p['speed'] for p in pairs})],
                        'selected_clock_counts': [{'bot': b,'initial_seconds': initial,'increment_seconds': increment,'speed': speed,'accounts': count} for (b,initial,increment,speed),count in sorted(clocks.items())]})
    return {'scope': {'records': manifest['records'], 'start_utc_inclusive': manifest['start_utc_inclusive'], 'end_utc_exclusive': manifest['end_utc_exclusive']},
            'definitions': {'question': 'How did persistent accounts score in their early versus later observed games against the same Maia and exact clock?',
                'matching': 'Same opponent account, Maia bot, clock initial seconds, increment seconds, and Lichess speed category. Valid outcome games ordered by creation time then game ID.',
                'selection': 'For each cohort independently, each account contributes once: select its eligible matching stratum with the most games; ties by bot, initial seconds, increment seconds, speed, ascending.',
                'score': 'Opponent score: win=1, draw=0.5, loss=0. First 20 versus last 20 valid games; windows never overlap. Summaries weight each selected account equally.',
                'gap': 'At least 30 days between the last early and first late game in main cohort; 90 days in sensitivity. Sensitivity additionally requires at least 60 valid games in the stratum.',
                'rating': 'Mean recorded opponent Lichess ratings in the early/later windows, within matching bot/clock/speed. Accounts can play and train elsewhere. Bot rating and color mix shifts are reported as potential confounders.',
                'limits': 'Descriptive association among selected persistent accounts, not proof that playing Maia improves skill. Selection/survivorship bias, regression to the mean, external training, bot changes and color mix can affect the result. Game outcomes and Lichess ratings are different measures; Maia level is not a measured skill gain.',
                'input_verification': 'This script verifies published shard SHA-256 hashes and row counts before analysis.'},
            'excluded_games': dict(exclusions), 'cohorts': cohorts}


if __name__ == '__main__':
    result = build_learning_insights()
    path = ROOT / 'data' / 'learning_insights.json'
    path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    for cohort in result['cohorts']:
        print(cohort['name'],json.dumps(cohort['overall']))
