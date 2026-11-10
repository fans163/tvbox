"""抓取全市场A股日K线（不复权），2025-11-01 ~ 2026-11-10，落盘CSV。
直连东财 push2his kline 接口，限速+重试，避免触发限流。
"""
import os, time, random, sys, json
import requests
from concurrent.futures import ThreadPoolExecutor

DATA_DIR = "/workspace/data/klines"
BEG, END = "20251101", "20261110"
THREADS = 12
REQ_INTERVAL = 0.12  # 每线程每次请求间隔

def _get_json(url, params, max_retry=8):
    delay = 1.0
    for _ in range(max_retry):
        try:
            r = requests.get(url, params=params, timeout=20)
            return r.json()
        except Exception:
            time.sleep(delay + random.uniform(0, 1))
            delay = min(delay * 2, 30)
    raise RuntimeError(f"failed after retries: {url}")

def get_stock_list():
    """优先用东财 clist 快照接口拿全市场代码+名称，失败则降级 akshare"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    codes = {}
    try:
        for mkt, fs in [("sh", "m:1+t:2,m:1+t:23"), ("sz", "m:0+t:6,m:0+t:80")]:
            pn = 1
            while True:
                params = {
                    "pn": pn, "pz": 500, "po": 1, "np": 1,
                    "fltt": 2, "invt": 2, "fid": "f3",
                    "fs": fs, "fields": "f12,f14",
                }
                j = _get_json(url, params)
                data = j.get("data")
                if not data or not data.get("diff"):
                    break
                for item in data["diff"]:
                    codes[item["f12"]] = item["f14"]
                total = data.get("total", 0)
                if pn * 500 >= total:
                    break
                pn += 1
                time.sleep(0.3)
        if len(codes) > 4000:
            return codes
    except Exception as e:
        print("clist failed:", e, flush=True)
    import akshare as ak
    df = ak.stock_info_a_code_name()
    return dict(zip(df["code"], df["name"]))

def secid_of(code):
    if code.startswith(("60", "68")):
        return f"1.{code}"
    return f"0.{code}"

def fetch_one(code, max_retry=6):
    path = os.path.join(DATA_DIR, f"{code}.csv")
    if os.path.exists(path) and os.path.getsize(path) > 200:
        return code, "cached"
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid_of(code),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101", "fqt": "0", "beg": BEG, "end": END,
    }
    delay = 1.0
    for attempt in range(max_retry):
        try:
            r = requests.get(url, params=params, timeout=15)
            j = r.json()
            data = j.get("data")
            if not data or not data.get("klines"):
                return code, "empty"
            with open(path, "w") as f:
                f.write("date,open,close,high,low,volume,amount,amplitude,pct,chg,turnover\n")
                for line in data["klines"]:
                    f.write(line + "\n")
            return code, "ok"
        except Exception as e:
            msg = str(e)
            time.sleep(delay + random.uniform(0, 1))
            delay = min(delay * 2, 30)
    return code, "fail"

def main():
    list_path = "/workspace/data/stock_list.json"
    if os.path.exists(list_path):
        codes = json.load(open(list_path))
    else:
        codes = get_stock_list()
        json.dump(codes, open(list_path, "w"), ensure_ascii=False)
    # 过滤：主板/创业板/科创板，排除北交所(8/4/920开头)
    keep = {c: n for c, n in codes.items()
            if c[:3] in ("600","601","603","605","000","001","002","003","300","301","688")}
    print(f"total {len(codes)}, keep {len(keep)}", flush=True)
    todo = list(keep.keys())
    done = ok = fail = empty = 0
    t0 = time.time()
    def wrapped(c):
        time.sleep(REQ_INTERVAL + random.uniform(0, 0.2))
        return fetch_one(c)
    with ThreadPoolExecutor(max_workers=THREADS) as ex:
        for code, status in ex.map(wrapped, todo):
            done += 1
            if status in ("ok", "cached"): ok += 1
            elif status == "empty": empty += 1
            else: fail += 1
            if done % 200 == 0:
                el = time.time() - t0
                print(f"[{done}/{len(todo)}] ok={ok} empty={empty} fail={fail} elapsed={el:.0f}s", flush=True)
    print(f"DONE ok={ok} empty={empty} fail={fail}", flush=True)

if __name__ == "__main__":
    main()
