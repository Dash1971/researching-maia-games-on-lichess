"""Synthetic published shards exercise comparison scope and integrity rules."""
import collections
import csv
import datetime as dt
import gzip
import hashlib
import json
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build_casual_comparison as comparison
from export_casual_games import COLUMNS
from comparison_behaviour import quick_transition, matched_pair, build_comparison_behaviour


def row(identifier, bot='maia1', opponent='alice', month='2024-01', variant='standard', winner='white', status='mate'):
    timestamp = int(dt.datetime.fromisoformat(month + '-15T12:00:00+00:00').timestamp() * 1000)
    return dict(zip(COLUMNS, [bot, identifier, opponent, str(timestamp - 60000), str(timestamp), 'black', winner, status, 'rapid', 'rapid', variant, 'friend', 'B00', 'Test Opening', '1500', '1400', '600', '0']))


class ComparisonTests(unittest.TestCase):
    def fixture(self, rows, kind='rated'):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        folder = root / 'data' / (kind + '-games')
        folder.mkdir(parents=True)
        groups = collections.defaultdict(list)
        for item in rows:
            year = dt.datetime.fromtimestamp(int(item['last_move_at_ms']) / 1000, dt.timezone.utc).year
            groups[f'{item["bot"]}_{year}.csv.gz'].append(item)
        shards = []
        for name, items in groups.items():
            path = folder / name
            with gzip.open(path, 'wt', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=COLUMNS)
                writer.writeheader()
                writer.writerows(items)
            shards.append({'file': name, 'rows': len(items), 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        manifest = {'fields': list(COLUMNS), 'records': len(rows), 'shards': shards, 'start_utc_inclusive': '2023-10-04T00:00:00Z', 'end_utc_exclusive': '2026-10-04T09:00:00Z'}
        path = folder / 'manifest.json'
        path.write_text(json.dumps(manifest))
        return root, path, manifest

    def scan(self, rows):
        root, _, _ = self.fixture(rows)
        with patch.object(comparison, 'ROOT', root), patch.dict(comparison.EXPECTED, rated=len(rows)):
            return comparison.scan('rated', set())

    def test_partial_months_excluded_from_comparable_periods(self):
        rows = [row('a', month='2023-10'), row('b', month='2023-11'), row('c', month='2024-10'), row('d', month='2025-10'), row('e', month='2026-09'), row('f', month='2026-10')]
        # October tail must remain within the fixed boundary.
        rows[-1]['last_move_at_ms'] = str(comparison.END - 1)
        rows[-1]['created_at_ms'] = str(comparison.END - 60000)
        raw = self.scan(rows)
        # Each bot needs a decisive game for the original summary calculation.
        raw['bot_decisive'].update({'maia5': 1, 'maia9': 1})
        summary = comparison.summarize(raw)
        self.assertEqual(summary['first_12_complete_months'], 2)
        self.assertEqual(summary['last_12_complete_months'], 2)
        self.assertEqual(sum(summary['partial_october'].values()), 2)

    def test_duplicate_game_ids_rejected_across_shards(self):
        with self.assertRaises(AssertionError):
            self.scan([row('a'), row('a', bot='maia5')])

    def test_end_boundary_is_exclusive(self):
        item = row('a'); item['last_move_at_ms'] = str(comparison.END)
        with self.assertRaises(AssertionError):
            self.scan([item])

    def test_hash_failure_rejected(self):
        root, path, manifest = self.fixture([row('a')])
        manifest['shards'][0]['sha256'] = '0' * 64
        path.write_text(json.dumps(manifest))
        with patch.object(comparison, 'ROOT', root), patch.dict(comparison.EXPECTED, rated=1), self.assertRaises(AssertionError):
            comparison.scan('rated', set())

    def test_account_dedup_and_no_winner_denominators(self):
        raw = self.scan([row('a'), row('b', opponent='alice', winner='', status='draw'), row('c', opponent='', winner='', status='timeout')])
        self.assertEqual(raw['monthly_accounts']['2024-01'], {'alice'})
        self.assertEqual(raw['missing_opponent'], 1)
        self.assertEqual(raw['bot_decisive']['maia1'], 1)
        self.assertEqual(raw['no_winner']['maia1'], 2)

    def test_full_matching_excludes_position_games_and_uses_same_color(self):
        rated = [row(f'r-{i}', month='2026-09', winner='black') for i in range(10)]
        casual = [row(f'c-{i}', month='2026-09', winner='white') for i in range(10)]
        casual += [row(f'p-{i}', month='2026-09', winner='black', variant='fromPosition') for i in range(20)]
        rated_root, _, _ = self.fixture(rated)
        casual_root, _, _ = self.fixture(casual, 'casual')
        shutil.copytree(casual_root / 'data' / 'casual-games', rated_root / 'data' / 'casual-games')
        result = build_comparison_behaviour(rated_root / 'data')
        matched = result['matched_standard_outcomes']
        self.assertEqual(matched['accounts'], 1)
        self.assertEqual(matched['rated_games'], 10)
        self.assertEqual(matched['casual_games'], 10)
        self.assertEqual(matched['mean_casual_minus_rated_pp'], 100)
        # Changing casual color leaves no qualifying matched stratum.
        for item in casual:
            if item['variant'] == 'standard':
                item['bot_color'] = 'white'
        changed_root, _, _ = self.fixture(casual, 'casual')
        shutil.rmtree(rated_root / 'data' / 'casual-games')
        shutil.copytree(changed_root / 'data' / 'casual-games', rated_root / 'data' / 'casual-games')
        self.assertEqual(build_comparison_behaviour(rated_root / 'data')['matched_standard_outcomes']['accounts'], 0)

    def test_standard_outcomes_do_not_include_position_games(self):
        raw = self.scan([row('a', winner='black'), row('b', variant='fromPosition', winner='white'), row('c', winner='', status='draw'), row('d', winner='', status='timeout')])
        self.assertEqual(raw['per_bot']['maia1'], 4)
        self.assertEqual(raw['standard_bot_games']['maia1'], 3)
        self.assertEqual(raw['outcomes']['maia1', 'loss'], 1)
        self.assertEqual(raw['standard_outcomes']['maia1', 'loss'], 0)
        self.assertEqual(raw['standard_outcomes']['maia1', 'win'], 1)
        self.assertEqual(raw['standard_outcomes']['maia1', 'draw'], 1)
        self.assertEqual(raw['standard_outcomes']['maia1', 'unknown'], 1)

    def test_next_event_can_switch_format_and_position_is_not_skipped(self):
        prior = {'created': 0, 'finished': 1000, 'mode': 'rated', 'bot': 'maia1', 'standard': True}
        following = {'created': 2000, 'finished': 3000, 'mode': 'casual', 'bot': 'maia1', 'standard': False}
        result = quick_transition(prior, following, 900000)
        self.assertTrue(result['quick'])
        self.assertTrue(result['other_mode'])
        self.assertTrue(result['same_bot'])
        self.assertFalse(result['same_mode'])
        self.assertFalse(result['next_standard'])
        self.assertFalse(quick_transition(prior, None, 900000)['quick'])

    def test_return_eligibility_overlap_and_exact_ten_minute_edge(self):
        prior = {'created': 0, 'finished': 1000, 'mode': 'rated', 'bot': 'maia1', 'standard': True}
        event = {'created': 601000, 'finished': 602000, 'mode': 'rated', 'bot': 'maia5', 'standard': True}
        self.assertTrue(quick_transition(prior, event, 601000)['quick'])
        self.assertFalse(quick_transition(prior, event, 600999)['eligible'])
        event['created'] = 999
        self.assertFalse(quick_transition(prior, event, 900000)['quick'])

    def test_matched_scores_require_both_formats_and_preserve_draw_points(self):
        self.assertIsNone(matched_pair((9,9), (100,50)))
        self.assertIsNone(matched_pair((100,50), (9,9)))
        result = matched_pair((10,5), (20,15))
        self.assertEqual(result['rated_score_pct'], 50)
        self.assertEqual(result['casual_score_pct'], 75)
        self.assertEqual(result['casual_minus_rated_pp'], 25)


if __name__ == '__main__':
    unittest.main()
