import asyncio, argparse, time, statistics, json, os, sys
from datetime import datetime
from typing import List

try:
    import httpx
except ImportError:
    print("Missing: pip install httpx"); sys.exit(1)

parser = argparse.ArgumentParser(description="Article Contest Tool Benchmark")
parser.add_argument("--url",         default="http://localhost:8000")
parser.add_argument("--token",       default="")
parser.add_argument("--contest",     default="")
parser.add_argument("--concurrency", type=int, default=50)
parser.add_argument("--articles",    type=int, default=100)
parser.add_argument("--batch-size",  type=int, default=50)
parser.add_argument("--skip-db",     action="store_true")
parser.add_argument("--output",      default="benchmark_results.json")
args = parser.parse_args()

BASE_URL    = args.url.rstrip("/")
AUTH_TOKEN  = args.token
CONTEST     = args.contest
CONCURRENCY = args.concurrency
ARTICLES    = args.articles
BATCH_SIZE  = getattr(args, "batch_size")

SAMPLE_TITLES = [
    "Saturn","interview","double","shrieking","wad","polisi","kanun","Muslim","su","ob",
    "nom","dil","narm","deha","deh","aziz","ben","shahar","kitob","op",
    "cennet","rusto","hasa","ko","mot","su","moe","pid","nom","nama",
    "jal","aal","din","eid","roz","khas","nabi","iman","azab","rahm",
    "yetim","jahan","ajab","nazm","qaum","zulm","ilm","amal","qalb","ruh",
    "Jupiter","Mars","Venus","Mercury","Neptune","Uranus","Pluto","Earth","Moon","Sun",
    "water","fire","air","earth","stone","tree","bird","river","ocean","mountain",
    "book","pen","door","window","road","bridge","song","dance","poem","art",
    "hand","eye","head","heart","mind","soul","life","death","love","hate",
    "rice","wheat","salt","sugar","tea","coffee","milk","oil","gold","silver",
]

def make_titles(user_idx: int, count: int):
    seen = set()
    result = []
    i = 0
    while len(result) < count:
        t = SAMPLE_TITLES[(user_idx * 7 + i) % len(SAMPLE_TITLES)]
        if t not in seen:
            seen.add(t)
            result.append(t)
        i += 1
    return result

async def check_health(client):
    t0 = time.perf_counter()
    try:
        r = await client.get(f"{BASE_URL}/api/contests")
        ms = (time.perf_counter()-t0)*1000
        return {"ok": r.status_code==200, "latency_ms": round(ms,2), "contests": len(r.json()) if r.status_code==200 else 0}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def bench_mediawiki(titles, rounds=3):
    print(f"\n[2] MediaWiki API Batch Query - {len(titles[:50])} titles x {rounds} rounds")
    url = "https://bn.wiktionary.org/w/api.php"
    hdrs = {"User-Agent":"ArticleContestBenchmark/1.0 (safe test)","Accept-Encoding":"gzip"}
    lats = []; errs = 0
    async with httpx.AsyncClient(timeout=30.0, headers=hdrs) as c:
        for i in range(rounds):
            params = {"action":"query","format":"json","titles":"|".join(titles[:50]),"prop":"revisions","rvprop":"timestamp|user","rvlimit":1,"rvdir":"newer"}
            t0 = time.perf_counter()
            try:
                r = await c.post(url, data=params)
                ms = (time.perf_counter()-t0)*1000
                if r.status_code==200:
                    pages = r.json().get("query",{}).get("pages",{})
                    lats.append(ms)
                    print(f"   Round {i+1}: {ms:.0f}ms, {len(pages)} pages")
                else:
                    errs += 1; print(f"   Round {i+1}: HTTP {r.status_code}")
            except Exception as e:
                errs += 1; print(f"   Round {i+1}: ERROR {e}")
            if i < rounds-1: await asyncio.sleep(1.0)
    if not lats: return {"skipped":True,"reason":"all rounds failed"}
    return {"avg_ms":round(statistics.mean(lats),1),"min_ms":round(min(lats),1),"max_ms":round(max(lats),1),"titles_per_sec":round(50*len(lats)/(sum(lats)/1000),1),"errors":errs}

async def bench_wiki_replica_db(concurrency=10, rounds=5):
    print(f"\n[3] Wiki Replica DB Throughput - {concurrency} concurrent x {rounds} rounds")
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", ".env"))
        from database import query_wiki_replica_batch, wiki_engine
        if not wiki_engine:
            return {"skipped":True,"reason":"No wiki_engine (SSH tunnel active? pymysql installed?)"}
        lats = []; errs = 0
        for rnd in range(rounds):
            t0 = time.perf_counter()
            loop = asyncio.get_event_loop()
            futs = [loop.run_in_executor(None, query_wiki_replica_batch, SAMPLE_TITLES[:50]) for _ in range(concurrency)]
            res = await asyncio.gather(*futs, return_exceptions=True)
            elapsed = (time.perf_counter()-t0)*1000
            ok = sum(1 for r in res if not isinstance(r, Exception) and r is not None)
            errs += concurrency - ok
            if ok > 0: lats.append(elapsed/ok)
            print(f"   Round {rnd+1}: {elapsed:.0f}ms total, {ok}/{concurrency} ok, {elapsed/max(ok,1):.1f}ms avg")
        if not lats: return {"skipped":True,"reason":"All queries failed"}
        return {"avg_ms":round(statistics.mean(lats),2),"p50_ms":round(statistics.median(lats),2),"min_ms":round(min(lats),2),"max_ms":round(max(lats),2),"errors":errs,"qps":round((concurrency*rounds)/(sum(lats)/1000),1)}
    except Exception as e:
        return {"skipped":True,"reason":str(e)}

async def one_user(client, uid, contest, n_articles, batch_sz, out):
    titles = make_titles(uid, n_articles)
    t_start = time.perf_counter()
    lats = []; ok = 0; err = 0
    for i in range(0, len(titles), batch_sz):
        chunk = titles[i:i+batch_sz]
        payload = {"contest_code":contest,"titles":chunk}
        t0 = time.perf_counter()
        try:
            r = await client.post(f"{BASE_URL}/api/submit-bulk", json=payload, timeout=30.0)
            ms = (time.perf_counter()-t0)*1000; lats.append(ms)
            if r.status_code==200:
                data = r.json()
                ok += sum(1 for x in data if x.get("is_valid"))
                err += sum(1 for x in data if not x.get("is_valid"))
            else: err += len(chunk)
        except Exception:
            lats.append((time.perf_counter()-t0)*1000); err += len(chunk)
    out.append({"ms": (time.perf_counter()-t_start)*1000, "lats": lats, "ok": ok, "err": err})

async def bench_submit_bulk(contest, concurrency, n_art, batch_sz):
    print(f"\n[4] submit-bulk Load Test - {concurrency} users x {n_art} articles each")
    if not contest: return {"skipped":True,"reason":"No --contest code. Pass --contest <code>"}
    hdrs = {"Content-Type":"application/json"}
    if AUTH_TOKEN: hdrs["Cookie"] = f"auth_token={AUTH_TOKEN}"
    lim = httpx.Limits(max_connections=min(concurrency*2,200), max_keepalive_connections=concurrency)
    results = []
    t_wall = time.perf_counter()
    async with httpx.AsyncClient(headers=hdrs, limits=lim, timeout=60.0) as client:
        tasks = [one_user(client,u,contest,n_art,batch_sz,results) for u in range(concurrency)]
        print(f"   Firing {concurrency} virtual users...")
        await asyncio.gather(*tasks, return_exceptions=True)
    wall_ms = (time.perf_counter()-t_wall)*1000
    if not results: return {"skipped":True,"reason":"no results"}
    all_lats = [l for r in results for l in r["lats"]]
    tot_ok  = sum(r["ok"]  for r in results)
    tot_err = sum(r["err"] for r in results)
    tot_art = tot_ok + tot_err
    ut = sorted(r["ms"] for r in results)
    if not all_lats: return {"skipped":True,"reason":"no latency data"}
    sl = sorted(all_lats)
    return {
        "concurrency":concurrency,"articles_per_user":n_art,"batch_size":batch_sz,
        "total_articles":tot_art,"success":tot_ok,"errors":tot_err,
        "wall_time_s":round(wall_ms/1000,2),
        "articles_per_second":round(tot_art/(wall_ms/1000),1),
        "request_latency":{
            "avg_ms":round(statistics.mean(sl),1),"p50_ms":round(sl[len(sl)//2],1),
            "p95_ms":round(sl[min(int(len(sl)*0.95),len(sl)-1)],1),"p99_ms":round(sl[min(int(len(sl)*0.99),len(sl)-1)],1),
            "min_ms":round(sl[0],1),"max_ms":round(sl[-1],1),
        },
        "user_p95_ms":round(ut[min(int(len(ut)*0.95),len(ut)-1)],0),
    }

def extrapolate(sb):
    if "skipped" in sb: return {}
    aps = sb.get("articles_per_second",0)
    proj = {}
    for r in [1,2,4,8]:
        proj[f"{r}_replica"] = {"art_per_sec":round(aps*r,1),"art_per_hour":round(aps*r*3600),"concurrent_users":round(CONCURRENCY*r)}
    verdict = ("GOOD for Toolforge" if aps>10 else "MARGINAL - optimize queries" if aps>2 else "TOO SLOW - bottleneck detected")
    return {"observed_aps":aps,"verdict":verdict,"projected":proj}

def show(res):
    sep = "="*68
    print(f"\n{sep}\n  BENCHMARK RESULTS\n{sep}")
    h = res.get("api_health",{})
    print(f"\n[1] API Health: {'OK' if h.get('ok') else 'FAIL'}  lat={h.get('latency_ms')}ms  contests={h.get('contests')}")
    mw = res.get("mediawiki_api",{})
    if "skipped" not in mw:
        print(f"\n[2] MediaWiki API (50 titles/req): avg={mw['avg_ms']}ms  min={mw['min_ms']}ms  max={mw['max_ms']}ms  {mw['titles_per_sec']} titles/sec")
    db = res.get("wiki_replica_db",{})
    if "skipped" not in db:
        print(f"\n[3] Wiki Replica DB (10 concurrent): avg={db['avg_ms']}ms  qps={db['qps']}  errors={db['errors']}")
    else:
        print(f"\n[3] Wiki Replica DB: SKIPPED - {db.get('reason')}")
    sb = res.get("submit_bulk",{})
    if "skipped" not in sb:
        lat = sb["request_latency"]
        print(f"\n[4] submit-bulk Load Test:")
        print(f"    articles={sb['total_articles']}  success={sb['success']}  errors={sb['errors']}")
        print(f"    wall={sb['wall_time_s']}s  throughput={sb['articles_per_second']} art/sec")
        print(f"    latency: avg={lat['avg_ms']}ms  p50={lat['p50_ms']}ms  p95={lat['p95_ms']}ms  p99={lat['p99_ms']}ms")
    else:
        print(f"\n[4] submit-bulk: SKIPPED - {sb.get('reason')}")
    cap = res.get("capacity",{})
    if cap:
        print(f"\n[5] Toolforge Capacity: {cap['verdict']}")
        for k,v in cap.get("projected",{}).items():
            print(f"    {k:12s}: {v['art_per_sec']:6.1f} art/s  {v['art_per_hour']:>10,} art/hr  ~{v['concurrent_users']} users")
    print(f"\n{sep}")

async def main():
    print("="*68)
    print("  Article Contest Tool - Benchmark Suite")
    print(f"  {BASE_URL}  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*68)
    res = {"meta":{"url":BASE_URL,"ts":datetime.now().isoformat(),"concurrency":CONCURRENCY,"articles":ARTICLES}}
    print("\n[1] API Health Check")
    async with httpx.AsyncClient(timeout=10.0) as c:
        h = await check_health(c)
    res["api_health"] = h
    print(f"    {'OK' if h.get('ok') else 'FAIL'}  lat={h.get('latency_ms')}ms  contests={h.get('contests')}")
    if not h.get("ok"):
        print(f"\nERROR: Cannot reach {BASE_URL}. Start uvicorn first."); sys.exit(1)
    res["mediawiki_api"]    = await bench_mediawiki(SAMPLE_TITLES, rounds=3)
    res["wiki_replica_db"]  = (await bench_wiki_replica_db(10,5)) if not args.skip_db else {"skipped":True,"reason":"--skip-db"}
    res["submit_bulk"]      = await bench_submit_bulk(CONTEST, CONCURRENCY, ARTICLES, BATCH_SIZE)
    res["capacity"]         = extrapolate(res["submit_bulk"])
    show(res)
    with open(args.output,"w",encoding="utf-8") as f:
        json.dump(res,f,indent=2,ensure_ascii=False,default=str)
    print(f"\nResults saved: {args.output}")

if __name__ == "__main__":
    asyncio.run(main())
