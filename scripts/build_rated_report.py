#!/usr/bin/env python3
"""Verify the published CSV shards and rebuild the aggregate research report.

Python standard library only. Run from the repository root after obtaining the
CSV.gz shards. The HTML is self-contained and contains no external scripts.
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
DATA = ROOT / "data" / "rated-games"
BOTS = ("maia1", "maia5", "maia9")
START = dt.datetime(2023, 10, 4, tzinfo=dt.timezone.utc)
END = dt.datetime(2026, 10, 4, 9, tzinfo=dt.timezone.utc)
FULL_MONTHS = [f"{y}-{m:02d}" for y in range(2023, 2027) for m in range(1, 13)
               if "2023-11" <= f"{y}-{m:02d}" <= "2026-09"]


def main():
    manifest=json.loads((DATA/"manifest.json").read_text())
    old=json.loads((ROOT/"data"/"summary.json").read_text())
    assert manifest["records"]==1425567
    account={}
    monthly=collections.Counter()
    bot_totals=collections.Counter()
    bot_colors=collections.Counter()
    bot_accounts={b:set() for b in BOTS}
    speed=collections.Counter()
    control=collections.Counter()
    opening=collections.Counter()
    rating_by_bot={b:[] for b in BOTS}
    rating_all=[]
    missing_rating=0
    unknown_opponent=0
    month_control=collections.Counter()
    seen=set()
    for shard in manifest["shards"]:
        path=DATA/shard["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest()==shard["sha256"]
        count=0
        with gzip.open(path,"rt",encoding="utf-8",newline="") as handle:
            reader=csv.DictReader(handle)
            assert reader.fieldnames==manifest["fields"]
            for row in reader:
                count+=1
                game_id=row["game_id"]
                assert game_id not in seen
                seen.add(game_id)
                bot=row["bot"]
                assert bot in BOTS
                finished=int(row["last_move_at_ms"])
                finished_dt=dt.datetime.fromtimestamp(finished/1000,dt.timezone.utc)
                assert START<=finished_dt<END
                assert shard["file"]==f"{bot}_{finished_dt.year}.csv.gz"
                month=finished_dt.strftime("%Y-%m")
                bot_totals[bot]+=1
                monthly[(month,bot)]+=1
                bot_colors[(bot,row["bot_color"])]+=1
                speed[row["speed"]]+=1
                initial=int(row["clock_initial_seconds"])
                increment=int(row["clock_increment_seconds"])
                ctrl=(initial,increment)
                control[ctrl]+=1
                month_control[(month,ctrl)]+=1
                family=row["opening_name"].split(":",1)[0]
                opening[family]+=1
                opp=row["opponent_id"]
                if not opp:
                    unknown_opponent+=1
                    continue
                bot_accounts[bot].add(opp)
                rating=int(row["opponent_rating"]) if row["opponent_rating"] else None
                if rating is None:
                    missing_rating+=1
                else:
                    rating_by_bot[bot].append(rating)
                    rating_all.append(rating)
                x=account.get(opp)
                if x is None:
                    x={"n":0,"bots":collections.Counter(),"sum":0,"rated_n":0,"first":(finished,bot),"last":(finished,bot)}
                    account[opp]=x
                x["n"]+=1
                x["bots"][bot]+=1
                if rating is not None:
                    x["sum"]+=rating
                    x["rated_n"]+=1
                if finished<x["first"][0]:x["first"]=(finished,bot)
                if finished>x["last"][0]:x["last"]=(finished,bot)
        assert count==shard["rows"],(shard["file"],count,shard["rows"])
    total=sum(bot_totals.values())
    assert total==manifest["records"]==len(seen)
    assert unknown_opponent==147
    first12,last12=FULL_MONTHS[:12],FULL_MONTHS[-12:]
    period=lambda months,b=None:sum(monthly[(m,x)] for m in months for x in ((b,) if b else BOTS))
    growth_first,growth_last=period(first12),period(last12)
    full_totals={m:sum(monthly[(m,b)] for b in BOTS) for m in FULL_MONTHS}
    peak=max(full_totals,key=full_totals.get)
    rank=sorted(account.items(),key=lambda x:(-x[1]["n"],x[0]))
    counts=sorted(x["n"] for x in account.values())
    n_accounts=len(account)
    top1=sum(counts[-round(n_accounts*.01):])
    multi=sum(len(x["bots"])>1 for x in account.values())
    all3=sum(len(x["bots"])==3 for x in account.values())
    active=[x for x in account.values() if x["n"]>=20 and x["last"][0]-x["first"][0]>=180*86400000]
    higher=sum(int(x["last"][1][-1])>int(x["first"][1][-1]) for x in active)
    lower=sum(int(x["last"][1][-1])<int(x["first"][1][-1]) for x in active)
    same=len(active)-higher-lower
    all_profiles={b:old["accounts"][b]["profile_count"] for b in BOTS}
    all_entries=sum(x["all"] for x in all_profiles.values())
    all_rated=sum(x["rated"] for x in all_profiles.values())
    all_casual=all_entries-all_rated
    all_overlap=sum(old["cross_bot_games"].values())
    all_distinct=all_entries-all_overlap
    rating_summary={}
    for b in BOTS:
        vals=rating_by_bot[b]
        vals.sort()
        rating_summary[b]={"game_mean":round(statistics.mean(vals)),"median":round(statistics.median(vals)),"p10":vals[int(.1*(len(vals)-1))],"p90":vals[int(.9*(len(vals)-1))]}
    rating_all.sort()
    overall_game_mean=round(statistics.mean(rating_all))
    overall_account_mean=round(statistics.mean(x["sum"]/x["rated_n"] for x in account.values() if x["rated_n"]))
    for b in BOTS:
        rating_summary[b]["account_mean"]=None
    # A second bounded streaming pass computes per-bot means without keeping game rows.
    bot_rating_account=collections.defaultdict(lambda:[0,0])
    for shard in manifest["shards"]:
        with gzip.open(DATA/shard["file"],"rt",encoding="utf-8",newline="") as handle:
            for row in csv.DictReader(handle):
                if row["opponent_id"] and row["opponent_rating"]:
                    a=bot_rating_account[(row["bot"],row["opponent_id"])]
                    a[0]+=int(row["opponent_rating"]);a[1]+=1
    for b in BOTS:
        rating_summary[b]["account_mean"]=round(statistics.mean(s/n for (bot,_),(s,n) in bot_rating_account.items() if bot==b))
    controls=[{"initial_seconds":a,"increment_seconds":i,"label":f"{a//60}+{i}" if a%60==0 else f"{a}s+{i}s","games":n} for (a,i),n in control.most_common()]
    summary={
        "scope":{"all_time_profile_snapshot_utc":old["collected_utc"],"rated_export_start_utc":START.isoformat(),"rated_export_end_exclusive_utc":END.isoformat(),"rated_export_timestamp_field":"last_move_at_ms (last recorded move, not necessarily game termination)"},
        "all_time":{"bot_game_entries":all_entries,"rated_bot_entries":all_rated,"casual_bot_entries":all_casual,"cross_bot_duplicate_entries":all_overlap,"unique_games":all_distinct,"per_bot":all_profiles},
        "rated_three_years":{"bot_game_entries":total,"unique_games":len(seen),"cross_bot_duplicate_entries":total-len(seen),"per_bot":dict(bot_totals),"opposing_accounts":n_accounts,"unknown_opponent_games":unknown_opponent,"missing_opponent_ratings":missing_rating,"first_12_complete_months":{"months":[first12[0],first12[-1]],"games":growth_first},"last_12_complete_months":{"months":[last12[0],last12[-1]],"games":growth_last},"peak_complete_month":{"month":peak,"games":full_totals[peak]},"monthly_complete":[{"month":m,"per_bot":{b:monthly[(m,b)] for b in BOTS},"bot_game_entries":full_totals[m],"unique_games":full_totals[m]} for m in FULL_MONTHS],"partial_months":{m:sum(monthly[(m,b)] for b in BOTS) for m in ("2023-10","2026-10")},"top_controls":controls[:20],"speed":dict(speed),"rating":{"game_weighted_mean":overall_game_mean,"account_weighted_mean":overall_account_mean,"per_bot":rating_summary},"accounts":{"one_game":sum(x==1 for x in counts),"median_games":statistics.median(counts),"mean_games":round(statistics.mean(counts),1),"top_one_percent_share":round(top1/total,4),"more_than_one_bot":multi,"all_three_bots":all3,"active_first_last_bot":{"eligible":len(active),"higher":higher,"lower":lower,"same":same}},"top_accounts":[{"handle":name,"games":x["n"],"per_bot":dict(x["bots"])} for name,x in rank[:20]],"opening_families":[{"name":name,"games":n} for name,n in opening.most_common(20)],"bot_color":{b:dict((color,bot_colors[(b,color)]) for color in ("white","black")) for b in BOTS}},
        "limitations":["All-time profile counters and three-year rated export use different scopes and collection times.","Month-by-month casual games were not downloaded.","October 2023 and October 2026 are partial months, excluded from monthly trend table and growth comparison.","Opposing accounts are public Lichess handles, not verified unique people.","No move lists or PGNs were downloaded; opening labels are Lichess metadata.","First-to-last bot level is descriptive, not proof of improvement or a causal effect of playing Maia."],
    }
    (ROOT/"data"/"rated_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    from fan_insights import build_insights
    from learning_insights import build_learning_insights
    from render_fan_report import render
    insights = build_insights()
    learning = build_learning_insights()
    for name, result in (("fan_insights", insights), ("learning_insights", learning)):
        (ROOT / "data" / f"{name}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    insights["learning"] = learning
    (ROOT / "index.html").write_text(render(summary, insights), encoding="utf-8")
    print(json.dumps({"games":total,"accounts":n_accounts,"all_time":all_entries,"growth_pct":round((growth_last/growth_first-1)*100,1),"learning_accounts":learning["cohorts"][0]["overall"]["accounts"]},indent=2))


if __name__=="__main__":
    main()
