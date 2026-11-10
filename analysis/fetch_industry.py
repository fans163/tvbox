"""抓取全市场股票->行业映射(东财clist f100)，镜像轮换+长退避重试，断点续抓"""
import requests, time, random, json, os

HOSTS = ["https://20.push2.eastmoney.com", "https://90.push2.eastmoney.com",
         "https://28.push2.eastmoney.com", "https://push2.eastmoney.com"]
path = "/workspace/data/industry_map.json"
out = json.load(open(path)) if os.path.exists(path) else {}
target = set(json.load(open("/workspace/data/stock_list.json")).keys())

def fetch_page(fs, pn):
    params = {"pn": pn, "pz": 100, "po": 1, "np": 1, "fltt": 2, "invt": 2,
              "fid": "f3", "fs": fs, "fields": "f12,f100"}
    delay = 2.0
    for attempt in range(12):
        host = HOSTS[attempt % len(HOSTS)]
        try:
            r = requests.get(host + "/api/qt/clist/get", params=params, timeout=15)
            j = r.json()
            d = j.get("data")
            if d and d.get("diff"):
                return d
            # 空页: 重试几次确认(可能限流)
            if attempt >= 3:
                return d
        except Exception:
            pass
        time.sleep(delay + random.uniform(0, 1.5))
        delay = min(delay * 1.5, 30)
    return None

for fs in ["m:1+t:2,m:1+t:23", "m:0+t:6,m:0+t:80"]:
    pn = 1
    empty_streak = 0
    while True:
        d = fetch_page(fs, pn)
        if d is None:
            print(f"fs={fs} pn={pn} permanent fail", flush=True)
            break
        diff = d.get("diff") or []
        if not diff:
            empty_streak += 1
            if empty_streak >= 2 or pn > 1:
                break
        else:
            empty_streak = 0
            for item in diff:
                out[item["f12"]] = item.get("f100") or "未知"
        total = d.get("total", 0)
        if pn * 100 >= total:
            break
        pn += 1
        time.sleep(0.35)
    json.dump(out, open(path, "w"), ensure_ascii=False)
    print(f"fs={fs} done, total map={len(out)}", flush=True)

json.dump(out, open(path, "w"), ensure_ascii=False)
missing = len(target - set(out.keys()))
print("industry map:", len(out), "missing:", missing)
