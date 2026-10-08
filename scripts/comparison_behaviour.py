#!/usr/bin/env python3
"""Verified, descriptive casual/rated behaviour supplement; Python stdlib only."""
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

ROOT = Path(__file__).resolve().parents[1]
MODES = ('rated', 'casual')


def outcome(row):
    if row['winner'] in ('white', 'black'):
        return 'loss' if row['winner'] == row['bot_color'] else 'win'
    return 'draw' if row['status'] in ('draw', 'stalemate') else 'unknown'


def pct(n, d):
    return round(n / d * 100, 4) if d else None


def quick_transition(prior, following, end_ms):
    """Event dicts: created, finished, mode, bot, standard; or following=None.

Eligibility uses prior last recorded move, not precise ending time. Return is
first NEXT observed event in either mode; cannot skip intervening events.
"""
    eligible = prior['created'] <= prior['finished'] <= end_ms - 600000
    quick = bool(eligible and following is not None and 0 <= following['created'] - prior['finished'] <= 600000)
    return {'eligible': eligible, 'quick': quick,
            'same_mode': quick and prior['mode'] == following['mode'],
            'other_mode': quick and prior['mode'] != following['mode'],
            'same_bot': quick and prior['bot'] == following['bot'],
            'next_standard': quick and following['standard']}


def matched_pair(rated, casual, minimum=10):
    """(known games, opponent score sum) pairs; matched standard stratum."""
    if rated[0] < minimum or casual[0] < minimum:
        return None
    r, c = rated[1] / rated[0] * 100, casual[1] / casual[0] * 100
    return {'rated_games': rated[0], 'casual_games': casual[0], 'rated_score_pct': r,
            'casual_score_pct': c, 'casual_minus_rated_pp': c - r}


def shares(counter, denominator, top=None):
    ordered = sorted(counter.items(), key=lambda x: (-x[1], str(x[0])))
    return [{'label': label, 'games': count, 'pct': pct(count, denominator)} for label, count in (ordered[:top] if top else ordered)]


def build_comparison_behaviour(data_root=None):
    data_root = Path(data_root) if data_root else ROOT / 'data'
    totals = collections.Counter()
    accounts = {m: collections.Counter() for m in MODES}
    bots = {m: collections.Counter() for m in MODES}
    clocks = {m: collections.Counter() for m in MODES}
    speeds = {m: collections.Counter() for m in MODES}
    variants = {m: collections.Counter() for m in MODES}
    variant_outcomes = collections.defaultdict(collections.Counter)
    sept = collections.Counter()
    end = None
    window = None
    quick_counts = {scope: collections.defaultdict(collections.Counter) for scope in ('all_variants','standard')}
    regular = []
    matched = []
    outlier_clocks, outlier_speeds, outlier_variants = collections.Counter(), collections.Counter(), collections.Counter()
    outlier_total = outlier_sept = 0
    with tempfile.TemporaryDirectory(prefix='maia-comparison-') as tmp:
        db = sqlite3.connect(str(Path(tmp) / 'events.sqlite3'))
        # This is a disposable rebuild cache, never an authoritative database.
        db.execute('PRAGMA journal_mode=OFF')
        db.execute('PRAGMA synchronous=OFF')
        db.execute('PRAGMA cache_size=-65536')
        db.execute('CREATE TABLE events (account TEXT, mode TEXT, bot TEXT, created INTEGER, finished INTEGER, result TEXT, standard INTEGER, clock TEXT, speed TEXT, color TEXT, score REAL, id TEXT)')
        for mode in MODES:
            folder = data_root / f'{mode}-games'
            manifest = json.loads((folder / 'manifest.json').read_text())
            bound = int(dt.datetime.fromisoformat(manifest['end_utc_exclusive'].replace('Z','+00:00')).timestamp()*1000)
            start = int(dt.datetime.fromisoformat(manifest['start_utc_inclusive'].replace('Z','+00:00')).timestamp()*1000)
            if window is not None and window != (start,bound):
                raise ValueError('Mismatched observation windows')
            window = start,bound
            end = bound
            batch = []
            for shard in manifest['shards']:
                path = folder / shard['file']
                digest = hashlib.sha256()
                with path.open('rb') as handle:
                    for block in iter(lambda: handle.read(1024*1024),b''):
                        digest.update(block)
                if digest.hexdigest() != shard['sha256']:
                    raise ValueError(f'Checksum mismatch: {mode}/{path.name}')
                n = 0
                with gzip.open(path,'rt',encoding='utf-8',newline='') as handle:
                    reader = csv.DictReader(handle)
                    if reader.fieldnames != manifest['fields']:
                        raise ValueError('Unexpected fields')
                    for row in reader:
                        n += 1
                        created, finished = int(row['created_at_ms']), int(row['last_move_at_ms'])
                        if not start <= finished < end:
                            raise ValueError('Outside observation window')
                        bot, account, variant = row['bot'],row['opponent_id'],row['variant']
                        result = outcome(row)
                        clock = f"{row['clock_initial_seconds']}+{row['clock_increment_seconds']}" if row['clock_initial_seconds'] and row['clock_increment_seconds'] else 'missing'
                        color = 'white' if row['bot_color'] == 'black' else 'black'
                        totals[mode] += 1
                        bots[mode][bot] += 1
                        clocks[mode][clock] += 1
                        speeds[mode][row['speed']] += 1
                        variants[mode][variant] += 1
                        variant_outcomes[mode,variant][result] += 1
                        if account:
                            accounts[mode][account] += 1
                            if mode == 'casual' and '2026-09' == dt.datetime.fromtimestamp(finished/1000,dt.timezone.utc).strftime('%Y-%m'):
                                sept[account] += 1
                        score = {'win':1.0,'draw':0.5,'loss':0.0}.get(result) if row['status'] != 'cheat' else None
                        batch.append((account,mode,bot,created,finished,result,int(variant=='standard'),clock,row['speed'],color,score,row['game_id']))
                        if len(batch)>=10000:
                            db.executemany('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',batch)
                            batch.clear()
                if n != shard['rows']:
                    raise ValueError('Shard row-count mismatch')
            db.executemany('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',batch)
            if totals[mode] != manifest['records']:
                raise ValueError('Corpus row-count mismatch')
        db.commit()
        # Build uniqueness in one sorted pass rather than random writes per row.
        db.execute('CREATE UNIQUE INDEX unique_games ON events(id)')
        db.execute('CREATE INDEX chronology ON events(account,created,id)')
        casual_leaders = []
        for account, count in sorted(accounts['casual'].items(), key=lambda item: (-item[1], item[0]))[:10]:
            per_bot = dict(db.execute("SELECT bot,count(*) FROM events WHERE mode='casual' AND account=? GROUP BY bot", (account,)))
            casual_leaders.append({'account': account, 'games': count,
                                   'per_bot': {bot: per_bot.get(bot, 0) for bot in ('maia1', 'maia5', 'maia9')}})
        top_account = min(sept,key=lambda a:(-sept[a],a))
        outlier_sept = sept[top_account]
        for clock,speed,standard,n in db.execute('SELECT clock,speed,standard,count(*) FROM events WHERE mode="casual" AND account=? GROUP BY clock,speed,standard',(top_account,)):
            outlier_total += n
            outlier_clocks[clock] += n
            outlier_speeds[speed] += n
            outlier_variants['standard' if standard else 'nonstandard'] += n
        sept_start = int(dt.datetime(2026,9,1,tzinfo=dt.timezone.utc).timestamp()*1000)
        sept_end = int(dt.datetime(2026,10,1,tzinfo=dt.timezone.utc).timestamp()*1000)
        sept_variant = dict(db.execute("SELECT CASE standard WHEN 1 THEN 'standard' ELSE 'nonstandard' END,count(*) FROM events WHERE mode='casual' AND account=? AND finished>=? AND finished<? GROUP BY standard",(top_account,sept_start,sept_end)))
        current_account = None
        previous = None
        account_rates = {m:collections.Counter() for m in MODES}
        def process(previous, following):
            if previous is None:
                return
            flag = quick_transition(previous,following,end)
            if not flag['eligible']:
                return
            for scope in ('all_variants','standard'):
                if scope == 'standard' and not previous['standard']:
                    continue
                c = quick_counts[scope][previous['mode'],previous['result']]
                c['eligible_games'] += 1
                valid_next = flag['quick'] and (scope=='all_variants' or flag['next_standard'])
                if valid_next:
                    c['quick_any_mode'] += 1
                    c['quick_same_mode' if flag['same_mode'] else 'quick_other_mode'] += 1
                    c['quick_same_bot'] += int(flag['same_bot'])
                if scope=='standard':
                    a = account_rates[previous['mode']]
                    a['eligible_games'] += 1
                    a['quick_any_mode'] += int(valid_next)
                    a['quick_same_mode'] += int(valid_next and flag['same_mode'])
                    a[f"{previous['result']}_eligible"] += 1
                    a[f"{previous['result']}_quick"] += int(valid_next)
        def save_account():
            if current_account and all(account_rates[m]['eligible_games']>=10 for m in MODES):
                regular.append({m:dict(account_rates[m]) for m in MODES})
        fields = ('account','mode','bot','created','finished','result','standard')
        for raw in db.execute('SELECT account,mode,bot,created,finished,result,standard FROM events WHERE account!="" ORDER BY account,created,id'):
            row = dict(zip(fields,raw))
            if row['account'] != current_account:
                process(previous,None)
                save_account()
                current_account = row['account']
                previous = None
                account_rates = {m:collections.Counter() for m in MODES}
            process(previous,row)
            previous = row
        process(previous,None)
        save_account()
        db.execute('CREATE INDEX matching ON events(account,bot,clock,speed,color,mode)')
        # Stream ordered aggregates and retain only one account at a time.
        last_account = None
        cells = {}
        def choose():
            candidates=[]
            for key,modes in cells.items():
                if all(m in modes for m in MODES):
                    pair=matched_pair(modes['rated'],modes['casual'])
                    if pair:
                        pair['casual_minus_rated_mean_created_days']=(modes['casual'][2]-modes['rated'][2])/86400000
                        candidates.append((-min(pair['rated_games'],pair['casual_games']),-pair['rated_games']-pair['casual_games'],key,pair))
            if candidates:
                _,_,key,pair=min(candidates,key=lambda x:(x[0],x[1],x[2]))
                pair['bot']=key[0]
                matched.append(pair)
        for account,bot,clock,speed,color,mode,n,total_score,mean_created in db.execute('SELECT account,bot,clock,speed,color,mode,count(*),sum(score),avg(created) FROM events WHERE account!="" AND standard=1 AND score IS NOT NULL AND clock!="missing" GROUP BY account,bot,clock,speed,color,mode ORDER BY account,bot,clock,speed,color,mode'):
            if account!=last_account:
                choose()
                cells={}
                last_account=account
            cells.setdefault((bot,clock,speed,color),{})[mode]=(n,total_score,mean_created)
        choose()
        db.close()
    def quick_rows(scope):
        result=[]
        for mode in MODES:
            for prior in ('win','loss','draw','unknown'):
                c=quick_counts[scope][mode,prior]
                result.append({'mode':mode,'prior_outcome':prior,**{k:c[k] for k in ('eligible_games','quick_any_mode','quick_same_mode','quick_other_mode','quick_same_bot')},'quick_any_mode_pct':pct(c['quick_any_mode'],c['eligible_games'])})
        return result
    shared_rates=[]
    for mode in MODES:
        for prior in ('all','win','loss'):
            denominator='eligible_games' if prior=='all' else f'{prior}_eligible'
            numerator='quick_any_mode' if prior=='all' else f'{prior}_quick'
            cells=[r[mode] for r in regular if r[mode].get(denominator,0)>0]
            n=sum(c[denominator] for c in cells)
            q=sum(c.get(numerator,0) for c in cells)
            shared_rates.append({'mode':mode,'prior_outcome':prior,'accounts_with_denominator':len(cells),'eligible_games':n,'quick_returns':q,'game_weighted_pct':pct(q,n),'account_equal_pct':round(statistics.mean(c.get(numerator,0)/c[denominator]*100 for c in cells),4) if cells else None})
    matched_summary={'accounts':len(matched),'minimum_known_games_per_mode_per_stratum':10,'rated_games':sum(p['rated_games'] for p in matched),'casual_games':sum(p['casual_games'] for p in matched)}
    for k in ('rated_score_pct','casual_score_pct','casual_minus_rated_pp'):
        matched_summary['mean_'+k]=round(statistics.mean(p[k] for p in matched),4) if matched else None
    matched_summary['median_casual_minus_rated_pp']=round(statistics.median(p['casual_minus_rated_pp'] for p in matched),4) if matched else None
    matched_summary['casual_score_higher_accounts']=sum(p['casual_minus_rated_pp']>1e-9 for p in matched)
    matched_summary['same_score_accounts']=sum(abs(p['casual_minus_rated_pp'])<=1e-9 for p in matched)
    matched_summary['casual_score_lower_accounts']=sum(p['casual_minus_rated_pp']<-1e-9 for p in matched)
    matched_summary['mean_casual_minus_rated_mean_created_days']=round(statistics.mean(p['casual_minus_rated_mean_created_days'] for p in matched),3) if matched else None
    matched_summary['median_absolute_mean_created_gap_days']=round(statistics.median(abs(p['casual_minus_rated_mean_created_days']) for p in matched),3) if matched else None
    matched_summary['by_bot']=[{'bot':bot,'accounts':sum(p['bot']==bot for p in matched),'mean_casual_minus_rated_pp':round(statistics.mean(p['casual_minus_rated_pp'] for p in matched if p['bot']==bot),4)} for bot in sorted({p['bot'] for p in matched})]
    return {
        'scope':{'start_utc_inclusive':'2023-10-04T00:00:00Z','end_utc_exclusive':'2026-10-04T09:00:00Z','time_basis':'last recorded move','games':dict(totals)},
        'definitions':{
            'activity':'Game counts per public opposing account within each format; IDs are not necessarily distinct people. Median includes one-game accounts. Top1% selects max(1,round(accounts*.01)) most active accounts; share denominator all format games.',
            'casual_top_accounts':'Ten identified opposing accounts with most casual games across all variants in the observation window; descending games, ties ascending handle. Per-bot counts partition each total.',
            'outcomes':'Opponent perspective: winner white/black gives win/loss. Draw only for draw/stalemate status and no winner, other no-winner statuses unknown.',
            'quick_return':'First next observed game of the same opponent across both formats, ordered by created timestamp then game ID; 0–600 seconds from prior last recorded move. Last move may precede actual resignation or flagging. Same/opposite format counts partition all quick returns; no formal rematch claim.',
            'eligible':'Known account, created<=last recorded move, last recorded move at least10 minutes before scope end; no-next games included. Outside-scope, other-opponent, or private activity unobserved.',
            'standard_returns':'Prior must be standard; first next observed event must also be standard for quick return. An intervening custom-position event is never skipped.',
            'shared_regular':'Accounts with >=10 eligible standard games in each format. Every qualifying account equal weight for account-equal rates; outcome-specific rates include accounts with >=1 eligible game of that outcome. Game-weighted rates use same selected cohort.',
            'matched_outcomes':'Known outcome, non-cheat standard games; same account, bot, exact clock, speed, and opponent color, >=10 games per format. One stratum per account: maximize smaller mode game count, then combined game count, ties ascending(bot,clock-string,speed,color). Means weight accounts equally. Whole-period formats need not coincide in time; mean-created-time gaps are reported. Not a randomized or causal comparison.',
            'outlier':'Identify largest September2026 casual account, then remove ALL its casual games across full observation window for full-window clock/speed sensitivity; report September count separately. No assertion about identity or motive.'},
        'modes':{m:{'games':totals[m],'accounts':len(accounts[m]),'median_games_per_account':statistics.median(accounts[m].values()),'one_game_accounts':sum(n==1 for n in accounts[m].values()),'one_game_accounts_pct':pct(sum(n==1 for n in accounts[m].values()),len(accounts[m])),'top_1pct_games':sum(sorted(accounts[m].values(),reverse=True)[:max(1,round(len(accounts[m])*.01))]),'bot_shares':shares(bots[m],totals[m]),'top_clocks':shares(clocks[m],totals[m],8),'speed_shares':shares(speeds[m],totals[m]),'variant_counts':dict(variants[m])} for m in MODES},
        'casual_top_accounts':casual_leaders,
        'top_two_casual_accounts_rated_games':{row['account']:accounts['rated'][row['account']] for row in casual_leaders[:2]},
        'variant_outcomes':[{'mode':m,'variant':v,'games':sum(c.values()),**{k:c[k] for k in ('win','loss','draw','unknown')}} for (m,v),c in sorted(variant_outcomes.items())],
        'quick_returns_all_variants':quick_rows('all_variants'),'quick_returns_standard':quick_rows('standard'),
        'shared_regular_accounts_standard':{'accounts':len(regular),'minimum_eligible_games_per_mode':10,'rates':shared_rates},
        'matched_standard_outcomes':matched_summary,
        'outlier_sensitivity':{'september_2026_top_account_games':outlier_sept,'top_account_full_window_casual_games':outlier_total,'september_variant_counts':sept_variant,'full_window_variant_counts':dict(outlier_variants),'casual_games_excluding_account':totals['casual']-outlier_total,'casual_top_clocks_without_account':shares(clocks['casual']-outlier_clocks,totals['casual']-outlier_total,8),'casual_speed_shares_without_account':shares(speeds['casual']-outlier_speeds,totals['casual']-outlier_total)}}


build_behaviour = build_comparison_behaviour


if __name__=='__main__':
    result=build_comparison_behaviour()
    output=ROOT/'data'/'comparison_behaviour.json'
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'shared_regular':result['shared_regular_accounts_standard'],'matched':result['matched_standard_outcomes'],'outlier':result['outlier_sensitivity']},indent=2))
