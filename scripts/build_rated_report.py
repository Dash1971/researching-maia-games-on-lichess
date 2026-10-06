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
import html
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "rated-games"
BOTS = ("maia1", "maia5", "maia9")
BOT_COLORS = {"maia1": "#2797b8", "maia5": "#f5a623", "maia9": "#6d62b5"}
START = dt.datetime(2023, 10, 4, tzinfo=dt.timezone.utc)
END = dt.datetime(2026, 10, 4, 9, tzinfo=dt.timezone.utc)
FULL_MONTHS = [f"{y}-{m:02d}" for y in range(2023, 2027) for m in range(1, 13)
               if "2023-11" <= f"{y}-{m:02d}" <= "2026-09"]


def esc(value):
    return html.escape(str(value))


def num(value):
    return f"{value:,}"


def share(a, b):
    return f"{a / b * 100:.1f}%" if b else "—"


def tab(headers, rows, cls=""):
    head = "".join(f"<th>{esc(x)}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{esc(x)}</td>" for x in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def bar(label, value, maximum, color="#2797b8", right=""):
    width = max(1, round(value / maximum * 100)) if maximum else 0
    return f'<div class="bar-row"><span class="bar-label">{esc(label)}</span><div class="bar-track"><div class="bar-fill" style="width:{width}%;background:{color}"></div></div><strong>{esc(right or num(value))}</strong></div>'


def monthly_chart(monthly):
    width, height, left, right, top, bottom = 1040, 290, 55, 16, 20, 43
    plot_w, plot_h = width-left-right, height-top-bottom
    totals = [sum(monthly[(m,b)] for b in BOTS) for m in FULL_MONTHS]
    ceiling = ((max(totals)+9999)//10000)*10000
    step = plot_w/len(FULL_MONTHS)
    parts = [f'<svg class="month-chart" role="img" aria-label="Monthly rated games by Maia bot, November 2023 through September 2026" viewBox="0 0 {width} {height}">']
    for n in range(0,ceiling+1,20000):
        y=top+plot_h-n/ceiling*plot_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#dce6ed"/><text x="{left-8}" y="{y+4:.1f}" text-anchor="end" class="axis">{n//1000}k</text>')
    for i,m in enumerate(FULL_MONTHS):
        x=left+i*step+step*.1
        bottom_y=top+plot_h
        for b in BOTS:
            h=monthly[(m,b)]/ceiling*plot_h
            bottom_y-=h
            parts.append(f'<rect x="{x:.1f}" y="{bottom_y:.1f}" width="{step*.8:.1f}" height="{h:.1f}" fill="{BOT_COLORS[b]}"><title>{m} {b}: {monthly[(m,b)]:,}</title></rect>')
        if m.endswith("-01") or m in (FULL_MONTHS[0],FULL_MONTHS[-1]):
            parts.append(f'<text x="{x+step*.4:.1f}" y="{height-15}" text-anchor="middle" class="axis">{m}</text>')
    parts.append("</svg>")
    return "".join(parts)


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
        "scope":{"all_time_profile_snapshot_utc":old["collected_utc"],"rated_export_start_utc":START.isoformat(),"rated_export_end_exclusive_utc":END.isoformat()},
        "all_time":{"bot_game_entries":all_entries,"rated_bot_entries":all_rated,"casual_bot_entries":all_casual,"cross_bot_duplicate_entries":all_overlap,"unique_games":all_distinct,"per_bot":all_profiles},
        "rated_three_years":{"bot_game_entries":total,"unique_games":len(seen),"cross_bot_duplicate_entries":total-len(seen),"per_bot":dict(bot_totals),"opposing_accounts":n_accounts,"unknown_opponent_games":unknown_opponent,"missing_opponent_ratings":missing_rating,"first_12_complete_months":{"months":[first12[0],first12[-1]],"games":growth_first},"last_12_complete_months":{"months":[last12[0],last12[-1]],"games":growth_last},"peak_complete_month":{"month":peak,"games":full_totals[peak]},"monthly_complete":[{"month":m,"per_bot":{b:monthly[(m,b)] for b in BOTS},"bot_game_entries":full_totals[m],"unique_games":full_totals[m]} for m in FULL_MONTHS],"partial_months":{m:sum(monthly[(m,b)] for b in BOTS) for m in ("2023-10","2026-10")},"top_controls":controls[:20],"speed":dict(speed),"rating":{"game_weighted_mean":overall_game_mean,"account_weighted_mean":overall_account_mean,"per_bot":rating_summary},"accounts":{"one_game":sum(x==1 for x in counts),"median_games":statistics.median(counts),"mean_games":round(statistics.mean(counts),1),"top_one_percent_share":round(top1/total,4),"more_than_one_bot":multi,"all_three_bots":all3,"active_first_last_bot":{"eligible":len(active),"higher":higher,"lower":lower,"same":same}},"top_accounts":[{"handle":name,"games":x["n"],"per_bot":dict(x["bots"])} for name,x in rank[:20]],"opening_families":[{"name":name,"games":n} for name,n in opening.most_common(20)],"bot_color":{b:dict((color,bot_colors[(b,color)]) for color in ("white","black")) for b in BOTS}},
        "limitations":["All-time profile counters and three-year rated export use different scopes and collection times.","Month-by-month casual games were not downloaded.","October 2023 and October 2026 are partial months, excluded from monthly trend table and growth comparison.","Opposing accounts are public Lichess handles, not verified unique people.","No move lists or PGNs were downloaded; opening labels are Lichess metadata.","First-to-last bot level is descriptive, not proof of improvement or a causal effect of playing Maia."],
    }
    (ROOT/"data"/"rated_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    report=render(summary,monthly,controls,opening,rank,all_profiles,bot_colors,month_control)
    (ROOT/"index.html").write_text(report,encoding="utf-8")
    print(json.dumps({"games":total,"accounts":n_accounts,"all_time":all_entries,"growth_pct":round((growth_last/growth_first-1)*100,1),"top_account_games":rank[0][1]["n"]},indent=2))


def render(s,monthly,controls,opening,rank,profiles,bot_colors,month_control):
    r=s["rated_three_years"];a=s["all_time"]
    first=r["first_12_complete_months"]["games"]
    last=r["last_12_complete_months"]["games"]
    growth=(last/first-1)*100
    cards=lambda items:'<div class="stat-grid">'+''.join(f'<div class="stat"><strong>{esc(n)}</strong><span>{esc(label)}</span></div>' for n,label in items)+'</div>'
    legend=''.join(f'<span><i style="background:{BOT_COLORS[b]}"></i>{esc(b.title().replace("Maia","Maia "))}</span>' for b in BOTS)
    all_table=tab(["Bot","All game entries","Rated","Casual"],[(b,num(profiles[b]["all"]),num(profiles[b]["rated"]),num(profiles[b]["all"]-profiles[b]["rated"])) for b in BOTS]+[("Total bot entries",num(a["bot_game_entries"]),num(a["rated_bot_entries"]),num(a["casual_bot_entries"]))])
    all_bars=''.join('<div class="stack-row"><strong>'+esc(b)+'</strong><div class="stack"><span style="width:'+str(profiles[b]["rated"]/profiles[b]["all"]*100)+'%;background:#2797b8"></span><span style="width:'+str((1-profiles[b]["rated"]/profiles[b]["all"])*100)+'%;background:#d9e6ee"></span></div><b>'+num(profiles[b]["all"])+"</b></div>" for b in BOTS)
    three_table=tab(["Bot","Rated game entries","Opposing accounts","Bot White","Bot Black"],[(b,num(r["per_bot"][b]),num(sum(1 for name,x in rank if x["bots"][b])),num(bot_colors[(b,"white")]),num(bot_colors[(b,"black")])) for b in BOTS]+[("Total entries",num(r["bot_game_entries"]),num(r["opposing_accounts"]),num(sum(bot_colors[(b,"white")] for b in BOTS)),num(sum(bot_colors[(b,"black")] for b in BOTS)))])
    growth_table=tab(["Bot","First complete 12 months","Last complete 12 months","Change"],[(b,num(sum(monthly[(m,b)] for m in FULL_MONTHS[:12])),num(sum(monthly[(m,b)] for m in FULL_MONTHS[-12:])),f"{(sum(monthly[(m,b)] for m in FULL_MONTHS[-12:])/sum(monthly[(m,b)] for m in FULL_MONTHS[:12])-1)*100:+.1f}%") for b in BOTS]+[("All bot entries",num(first),num(last),f"{growth:+.1f}%")])
    month_table=tab(["UTC month","Maia 1 entries","Maia 5 entries","Maia 9 entries","All entries","Unique games"],[(m,num(monthly[(m,"maia1")]),num(monthly[(m,"maia5")]),num(monthly[(m,"maia9")]),num(sum(monthly[(m,b)] for b in BOTS)),num(sum(monthly[(m,b)] for b in BOTS))) for m in FULL_MONTHS],"month-table")
    cmax=controls[0]["games"]
    controls_html=''.join(bar(x["label"],x["games"],cmax,right=f'{num(x["games"])} · {share(x["games"],r["bot_game_entries"])}') for x in controls[:8])
    speed_html=''.join(bar(x,n,max(r["speed"].values()),color="#6d62b5",right=f"{num(n)} · {share(n,r['bot_game_entries'])}") for x,n in sorted(r["speed"].items(),key=lambda z:-z[1]))
    rating_table=tab(["Opponent","Game-weighted mean","Account-weighted mean","Median","Middle 80%"],[(b,num(r["rating"]["per_bot"][b]["game_mean"]),num(r["rating"]["per_bot"][b]["account_mean"]),num(r["rating"]["per_bot"][b]["median"]),f"{num(r['rating']['per_bot'][b]['p10'])}–{num(r['rating']['per_bot'][b]['p90'])}") for b in BOTS]+[("All Maia games",num(r["rating"]["game_weighted_mean"]),num(r["rating"]["account_weighted_mean"]),"—","—")])
    top_table=tab(["Public Lichess account","Games","Maia 1","Maia 5","Maia 9"],[(name,num(x["n"]),num(x["bots"]["maia1"]),num(x["bots"]["maia5"]),num(x["bots"]["maia9"])) for name,x in rank[:10]])
    opening_html=''.join(bar(name,n,opening.most_common(1)[0][1],"#f5a623",f"{num(n)} · {share(n,r['bot_game_entries'])}") for name,n in opening.most_common(10))
    partial=r["partial_months"]
    active=r["accounts"]["active_first_last_bot"]
    css='''@page{size:A4;margin:9mm}*{box-sizing:border-box}body{margin:0;background:#f3f7f9;color:#14283b;font:16px/1.5 system-ui,-apple-system,sans-serif}main{max-width:1050px;margin:auto;background:#fff;padding:42px}h1{font-size:2.65rem;line-height:1.05;margin:.25em 0}.eyebrow{font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:#2797b8;font-size:.8rem}.lead{font-size:1.22rem;color:#36516a;max-width:800px}.scope{background:#e9f5f9;border-left:5px solid #2797b8;padding:13px 17px;border-radius:8px}.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:22px 0}.stat{background:#eaf2f6;border-radius:12px;padding:13px}.stat strong{display:block;font-size:1.65rem;line-height:1.15}.stat span{font-size:.85rem;color:#456175}.section{margin-top:36px;border-top:2px solid #dce8ef;padding-top:18px}h2{font-size:1.65rem;line-height:1.15;margin:.25em 0}h3{font-size:1.13rem;margin:22px 0 8px}.kicker{font-weight:700;color:#26718e}.muted,.fine{color:#536c80}.fine{font-size:.86rem}.legend{display:flex;gap:15px;flex-wrap:wrap;font-size:.83rem}.legend span{display:flex;align-items:center;gap:5px}.legend i{display:inline-block;width:12px;height:12px;border-radius:3px}.stack-row{display:grid;grid-template-columns:80px 1fr 100px;align-items:center;gap:12px;margin:12px 0}.stack{height:22px;border-radius:5px;display:flex;overflow:hidden}.stack span{height:100%}.stack-row b{text-align:right}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.87rem;margin:12px 0}th,td{padding:7px 8px;border-bottom:1px solid #dbe5ec;text-align:right}th:first-child,td:first-child{text-align:left}th{background:#e9f1f6;color:#26445d}tr:last-child{font-weight:700}.month-chart{width:100%;height:auto;background:#fbfdfe;border-radius:9px;margin:8px 0}.axis{font:12px system-ui,sans-serif;fill:#647d90}.bar-row{display:grid;grid-template-columns:185px 1fr 160px;align-items:center;gap:10px;margin:8px 0;font-size:.9rem}.bar-track{height:17px;background:#e8eef2;border-radius:6px;overflow:hidden}.bar-fill{height:100%;border-radius:6px}.bar-row strong{text-align:right;font-size:.83rem}.callout{background:#fff5e2;border-left:4px solid #f5a623;padding:12px 16px;border-radius:7px;margin:14px 0}.bridge{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;text-align:center}.bridge div{background:#eaf2f6;border-radius:9px;padding:10px}.bridge b{display:block;font-size:1.35rem}.links{font-size:.86rem}a{color:#17618a}nav{display:flex;gap:14px;flex-wrap:wrap;font-size:.86rem}details{margin-top:15px}summary{font-weight:700;cursor:pointer}@media(max-width:700px){main{padding:20px}h1{font-size:2rem}.stat-grid,.bridge{grid-template-columns:repeat(2,1fr)}.bar-row{grid-template-columns:105px 1fr 100px}.bar-label{font-size:.75rem}.bar-row strong{font-size:.7rem}.stack-row{grid-template-columns:55px 1fr 82px}}@media print{body{background:#fff;font-size:10px;line-height:1.22}main{padding:0;max-width:none}h1{font-size:1.85rem}h2{font-size:1.2rem}h3{font-size:.95rem}.lead{font-size:1rem}.stat-grid{margin:10px 0}.stat{padding:8px}.stat strong{font-size:1.15rem}.section{margin-top:12px;padding-top:7px}table{font-size:.68rem;margin:5px 0}th,td{padding:2px 4px}.month-table th,.month-table td{padding:1px 4px}.bar-row{margin:3px 0}.month-chart{max-height:150px}.fine{font-size:.75rem}nav{display:none}tr{break-inside:avoid}h2,h3{break-after:avoid}.ratings-start{break-before:page}}'''
    body=f'''<main><div class="eyebrow">Independent research · 6 October 2026</div><h1>How people play the Maia bots on Lichess</h1><p class="lead">A complete three-year census of <b>rated</b> games, placed beside a separate all-time snapshot that includes casual play.</p><nav><a href="#all-time">All-time context</a><a href="#rated">Three-year rated games</a><a href="#players">Players</a><a href="#style">How they play</a><a href="#methods">Methods & data</a></nav>
    <div class="scope"><b>Read this distinction first.</b> “Bot-game entries” adds the three Maia account totals; one Maia-vs-Maia game can contribute two entries. “Unique games” counts each game ID once. These are different only when the bots play each other. The all-time snapshot has 21 such overlaps. The three-year rated export has none, so its entry and unique-game counts are equal. All-time includes casual play; detailed monthly, player, clock and rating analyses below do not.</div>
    {cards([(num(a['bot_game_entries']),'all-time bot-game entries · rated + casual'),(num(a['unique_games']),'all-time unique games'),(num(r['bot_game_entries']),'rated games in three-year export'),(num(r['opposing_accounts']),'opposing Lichess accounts')])}
    <section class="section" id="all-time"><div class="eyebrow">01 / Broad context</div><h2>All games, including casual</h2><p>These moving Lichess profile counters were captured <b>4 October 2026 at 07:12 UTC</b>. They cover each bot’s entire account history, not just the three-year study. They cannot establish monthly casual-play trends.</p><div class="legend"><span><i style="background:#2797b8"></i>Rated</span><span><i style="background:#d9e6ee"></i>Casual</span></div>{all_bars}{all_table}<div class="bridge"><div><b>{num(a['bot_game_entries'])}</b>summed bot entries</div><div><b>− {num(a['cross_bot_duplicate_entries'])}</b>Maia-vs-Maia duplicate entries</div><div><b>{num(a['unique_games'])}</b>unique games</div></div><p class="fine">Casual = all profile games − rated profile games. The overlap comes from pairwise Maia-bot crosstables. These are game counts, not a count of people.</p></section>
    <section class="section" id="rated"><div class="eyebrow">02 / Detailed census</div><h2>Rated games in the last three years</h2><p>The downloadable game-level export covers games <b>finished 4 October 2023 00:00 UTC through, but not including, 4 October 2026 09:00 UTC</b>. It contains no casual games. Every game ID appears once; no game between two Maia bots occurred in this window.</p>{three_table}<div class="bridge"><div><b>{num(r['bot_game_entries'])}</b>bot-game entries</div><div><b>− 0</b>cross-bot overlaps</div><div><b>{num(r['unique_games'])}</b>unique rated games</div></div><h3>Popularity grew, but not smoothly</h3><p class="kicker">Comparable 12-month blocks: {num(first)} → {num(last)} games ({growth:+.1f}%).</p><p class="fine">The comparison is November 2023–October 2024 versus October 2025–September 2026. The strongest complete month was {esc(r['peak_complete_month']['month'])} ({num(r['peak_complete_month']['games'])} games). This is rated-play growth, not a claim about all Maia games.</p><div class="legend">{legend}</div>{monthly_chart(monthly)}{growth_table}<details open><summary>Every complete UTC month — all bot entries and unique games</summary><p class="fine">October 2023 ({num(partial['2023-10'])}) and October 2026 ({num(partial['2026-10'])}) are <b>partial months</b> and are intentionally omitted below and from the trend comparison. “All entries” and “unique games” match in every row because this export has zero Maia-vs-Maia overlap.</p>{month_table}</details></section>
    <section class="section" id="players"><div class="eyebrow">03 / Who plays</div><h2>Many one-off visitors, a small very active core</h2>{cards([(num(r['opposing_accounts']),'opposing accounts'),(f"{share(r['accounts']['one_game'],r['opposing_accounts'])}",'played exactly one game'),(num(r['accounts']['more_than_one_bot']),'played multiple Maia levels'),(f"{r['accounts']['top_one_percent_share']*100:.1f}%",'of games came from busiest 1%')])}<p>The median account played {r['accounts']['median_games']:g} games. The busiest account played {num(rank[0][1]['n'])}. Accounts are public Lichess handles, not verified unique people; 147 games have no opponent handle and are excluded from account statistics.</p><h3>Most active public accounts in this rated window</h3>{top_table}<p class="fine">Counts are for this three-year rated export only. They are not all-time leaderboards.</p><div class="callout"><b>Does playing Maia make people improve?</b> This dataset cannot establish that. Of {num(active['eligible'])} accounts with at least 20 games spanning 180 days, the last observed Maia opponent was a higher-numbered bot for {num(active['higher'])}, lower for {num(active['lower'])}, and unchanged for {num(active['same'])}. First/last opponents are noisy snapshots, not a learning measure or causal test.</div></section>
    <section class="section" id="style"><div class="eyebrow">04 / How they play</div><h2>10+0 leads; stronger bots draw higher-rated opponents</h2><p>Exact controls show initial minutes plus increment seconds. Speed categories are broader Lichess labels.</p><div class="two"><div><h3>Exact clock settings</h3>{controls_html}</div><div><h3>Speed categories</h3>{speed_html}</div></div><h3 class="ratings-start">Opponents’ Lichess ratings at game time</h3><p class="fine">These are Lichess ratings, not FIDE Elo. A game-weighted mean gives frequent players more influence; an account-weighted mean first averages each account’s ratings. Players may choose different speeds and bots, so this is not a controlled ability comparison.</p>{rating_table}<p class="fine">Missing opponent ratings: {num(r['missing_opponent_ratings'])} among games with identified opponents. Games with no opponent handle are excluded from rating averages.</p><h3>Most common named opening families</h3><p class="fine">Opening labels are Lichess metadata, grouped before a colon. They describe the position reached by both sides, not the human’s first move. Moves were not downloaded.</p>{opening_html}</section>
    <section class="section" id="methods"><div class="eyebrow">05 / Methods & data</div><h2>Download, inspect, reproduce</h2><p>The companion dataset contains all {num(r['bot_game_entries'])} rated game metadata rows in compressed year/bot CSV shards, their SHA-256 manifest, a field guide, aggregate JSON, and the standard-library scripts used to export and rebuild this report. <b>No move lists or PGNs were collected.</b></p><p>Validation checked unique game IDs, the frozen finish-time bounds, complete gap-free date coverage, the filtered-export cap, field presence, and shard hashes. The original private working SQLite database and credentials are not included.</p><p class="fine">Sources: <a href="https://lichess.org/api#operation/apiUser">Lichess profiles</a>, <a href="https://lichess.org/api#operation/apiCrosstable">bot crosstables</a>, <a href="https://lichess.org/api#operation/apiGamesUser">user-game export</a>. Lichess data retain their own terms; the repository’s MIT license applies to original code and writing. Independent fan research, not a Lichess or Maia publication.</p><p class="links"><a href="data/rated-games/manifest.json">Game-file manifest</a> · <a href="data/rated_summary.json">All aggregate tables (JSON)</a> · <a href="data/rated-games/README.md">Field guide</a> · <a href="RESEARCH_PLAN.md">Research plan</a></p></section></main>'''
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Maia on Lichess — rated-game census</title><style>'+css+'</style>'+body+'</html>'


if __name__=="__main__":
    main()
