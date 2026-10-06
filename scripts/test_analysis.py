"""Small synthetic datasets exercise denominator, chronology and integrity rules."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from fan_insights import build_insights, outcome, pack, rating_band
from learning_insights import summarize_pair, aggregate, build_learning_insights, DAY_MS

FIELDS = ['bot', 'game_id', 'opponent_id', 'created_at_ms', 'last_move_at_ms', 'bot_color', 'winner', 'status', 'speed', 'perf', 'variant', 'source', 'opening_eco', 'opening_name', 'bot_rating', 'opponent_rating', 'clock_initial_seconds', 'clock_increment_seconds']


def game(identifier, account='alice', bot='maia1', created=0, finished=1000, winner='black', status='mate', color='black'):
    return dict(zip(FIELDS, [bot, identifier, account, str(created), str(finished), color, winner, status, 'rapid', 'rapid', 'standard', 'friend', 'B00', 'Test Opening: Variation', '1500', '1400', '600', '0']))


class AnalysisTests(unittest.TestCase):
    def build(self, rows, corrupt_checksum=False, wrong_rows=False, builder=build_insights):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name)
        shard = path / 'test.csv.gz'
        with gzip.open(shard, 'wt', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        manifest = {'fields': FIELDS, 'records': len(rows), 'start_utc_inclusive': '1970-01-01T00:00:00Z', 'end_utc_exclusive': '1970-01-02T00:00:00Z', 'shards': [{'file': shard.name, 'rows': len(rows), 'sha256': hashlib.sha256(shard.read_bytes()).hexdigest()}]}
        if corrupt_checksum:
            manifest['shards'][0]['sha256'] = '0' * 64
        if wrong_rows:
            manifest['shards'][0]['rows'] += 1
        (path / 'manifest.json').write_text(json.dumps(manifest))
        return builder(path)

    def test_integrity_failures_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
            self.build([game('a')], corrupt_checksum=True)
        with self.assertRaisesRegex(ValueError, 'Row count mismatch'):
            self.build([game('a')], wrong_rows=True)

    def test_results_are_opponent_perspective(self):
        self.assertEqual(outcome(game('a', winner='white')), 'win')
        self.assertEqual(outcome(game('a', winner='black')), 'loss')
        self.assertEqual(outcome(game('a', winner='', status='draw')), 'draw')
        self.assertEqual(outcome(game('a', winner='', status='stalemate')), 'draw')
        self.assertEqual(outcome(game('a', winner='', status='timeout')), 'unknown')

    def test_draw_and_unknown_denominators(self):
        import collections
        result = pack(collections.Counter(win=1, draw=2, loss=1, unknown=1))
        self.assertEqual(result['win_pct_of_all_games'], 20)
        self.assertEqual(result['score_pct_of_known_outcomes'], 50)
        self.assertIsNone(pack(collections.Counter(unknown=1))['score_pct_of_known_outcomes'])

    def test_rating_boundaries(self):
        for rating, expected in [(999, '<1000'), (1000, '1000–1199'), (1199, '1000–1199'), (1200, '1200–1399'), (1999, '1800–1999'), (2000, '2000+')]:
            self.assertEqual(rating_band(rating), expected)

    def test_returns_sort_chronologically_and_match_account(self):
        # Unsorted input; switching bots counts any-Maia but not same-Maia.
        result = self.build([game('c', created=3000, finished=4000), game('b', bot='maia5', created=2000, finished=2500), game('a'), game('d', account='bob', created=1500, finished=2000)])
        rows = {(r['bot'], r['previous_opponent_outcome']): r for r in result['quick_returns_by_bot_and_prior_outcome']}
        self.assertEqual(rows['maia1', 'loss']['eligible_games'], 3)
        self.assertEqual(rows['maia1', 'loss']['quick_return_any_maia'], 1)
        self.assertEqual(rows['maia1', 'loss']['quick_return_same_maia'], 0)
        self.assertEqual(rows['maia5', 'loss']['quick_return_any_maia'], 1)
        self.assertEqual(result['opponent_accounts']['accounts'], 2)

    def test_right_edge_and_overlap_do_not_count_as_returns(self):
        result = self.build([game('a', created=0, finished=5000), game('b', created=2000, finished=6000), game('c', created=86000000, finished=86001000), game('d', created=86002000, finished=86003000)])
        row = next(r for r in result['quick_returns_by_bot_and_prior_outcome'] if r['bot'] == 'maia1' and r['previous_opponent_outcome'] == 'loss')
        self.assertEqual(row['eligible_games'], 2)
        self.assertEqual(row['quick_return_same_maia'], 0)
        self.assertEqual(result['consecutive_observed_game_gaps']['overlapping_next_game'], 1)

    def test_unknown_accounts_retained_in_outcomes_not_account_counts(self):
        result = self.build([game('a', account=''), game('b')])
        self.assertEqual(result['outcomes_by_bot'][0]['games'], 2)
        self.assertEqual(result['opponent_accounts']['games_with_known_account'], 1)
        self.assertEqual(result['missing_fields']['opponent_id'], 1)


class LearningTests(unittest.TestCase):
    build = AnalysisTests.build
    def pair_rows(self, early_score=0, late_score=1):
        return [{'created_ms': i * DAY_MS if i < 20 else (i + 30) * DAY_MS,
                 'score': early_score if i < 20 else late_score,
                 'opponent_rating': 1400 if i < 20 else 1450,
                 'bot_rating': 1500 if i < 20 else 1525,
                 'white': int(i >= 20)} for i in range(40)]

    def test_pair_requires_disjoint_windows_and_gap(self):
        rows = self.pair_rows()
        self.assertIsNone(summarize_pair(rows[:-1]))
        self.assertIsNone(summarize_pair(rows, min_gap_days=32))
        result = summarize_pair(rows, min_gap_days=31)
        self.assertEqual(result['score_change_pp'], 100)
        self.assertEqual(result['opponent_rating_change'], 50)
        self.assertEqual(result['bot_rating_change'], 25)
        self.assertEqual(result['early_white_pct'], 0)
        self.assertEqual(result['late_white_pct'], 100)

    def test_equal_account_weight_and_half_draw_score(self):
        a = summarize_pair(self.pair_rows(0, 1))
        b = summarize_pair(self.pair_rows(1, .5))
        a['games'] = 10000  # More activity must not add weight.
        result = aggregate([a, b])
        self.assertEqual(result['mean_score_change_pp'], 25)
        self.assertEqual(result['improved_accounts'], 1)
        self.assertEqual(result['declined_accounts'], 1)
        self.assertEqual(result['compared_games'], 80)

    def test_matching_selects_one_eligible_stratum_per_account(self):
        rows = []
        for bot, size in [('maia1', 40), ('maia5', 50)]:
            for i in range(size):
                when = (i if i < 20 else i + 100) * DAY_MS
                rows.append(game(f'{bot}-{i}', bot=bot, created=when, finished=when+1000,
                                 winner='black' if i < 20 else 'white'))
        # Cheat games cannot turn an otherwise too-small stratum eligible.
        for i in range(40):
            when = (i if i < 20 else i + 100) * DAY_MS
            rows.append(game(f'cheat-{i}', account='bob', created=when, finished=when+1000,
                             status='cheat' if i == 0 else 'mate'))
        result = self.build(list(reversed(rows)), builder=build_learning_insights)
        main = result['cohorts'][0]
        self.assertEqual(main['overall']['accounts'], 1)
        self.assertEqual(main['by_bot'][0]['accounts'], 0)
        self.assertEqual(main['by_bot'][1]['accounts'], 1)
        self.assertEqual(main['overall']['mean_score_change_pp'], 100)
        self.assertEqual(result['excluded_games']['cheat_status'], 1)


if __name__ == '__main__':
    unittest.main()
