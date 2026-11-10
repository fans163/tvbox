"""对案例股票补充抓取: 主力资金流(东财) 与 筹码分布(cyq,近90天)
限流敏感: 串行+间隔, 失败跳过
输入: /workspace/data/cases.csv
输出: /workspace/data/fundflow/{code}.csv, /workspace/data/cyq/{code}.csv
"""
import os, time, random, json
import pandas as pd
import requests

os.makedirs("/workspace/data/fundflow", exist_ok=True)
os.makedirs("/workspace/data/cyq", exist_ok=True)

cases = pd.read_csv("/workspace/data/cases.csv")
codes = sorted(set(cases["code"].astype(str).str.zfill(6)))
print("case stocks:", len(codes))

def secid_of(code):
    return f"1.{code}" if code.startswith(("60", "68")) else f"0.{code}"

def mkt_of(code):
    return "sh" if code.startswith(("60", "68")) else "sz"

# ---- 主力资金: 东财 push2his 资金流接口 ----
def fetch_fundflow(code):
    path = f"/workspace/data/fundflow/{code}.csv"
    if os.path.exists(path) and os.path.getsize(path) > 100:
        return "cached"
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "secid": secid_of(code), "lmt": "0", "klt": "101",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63",
    }
    delay = 1.0
    for _ in range(5):
        try:
            r = requests.get(url, params=params, timeout=15)
            j = r.json()
            d = j.get("data")
            if not d or not d.get("klines"):
                return "empty"
            with open(path, "w") as f:
                f.write("date,main_net,small_net,mid_net,big_net,superbig_net,main_net_pct,close,pct\n")
                for line in d["klines"]:
                    p = line.split(",")
                    # f51日期 f52主力净流入 f53小单 f54中单 f55大单 f56超大单 f57主力净占比 f58收盘价 f59涨跌幅
                    f.write(",".join([p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8]]) + "\n")
            return "ok"
        except Exception:
            time.sleep(delay + random.uniform(0, 1))
            delay = min(delay * 2, 20)
    return "fail"

# ---- 筹码分布: akshare ----
import akshare as ak
def fetch_cyq(code):
    path = f"/workspace/data/cyq/{code}.csv"
    if os.path.exists(path) and os.path.getsize(path) > 100:
        return "cached"
    delay = 1.0
    for _ in range(4):
        try:
            df = ak.stock_cyq_em(symbol=code, adjust="")
            if df is None or df.empty:
                return "empty"
            df.to_csv(path, index=False)
            return "ok"
        except Exception:
            time.sleep(delay + random.uniform(0, 1))
            delay = min(delay * 2, 20)
    return "fail"

stats = {"ff_ok": 0, "cyq_ok": 0}
for i, code in enumerate(codes):
    s1 = fetch_fundflow(code)
    time.sleep(0.3 + random.uniform(0, 0.2))
    s2 = fetch_cyq(code)
    stats["ff_ok"] += s1 in ("ok", "cached")
    stats["cyq_ok"] += s2 in ("ok", "cached")
    if (i + 1) % 20 == 0:
        print(f"[{i+1}/{len(codes)}] {stats}", flush=True)
    time.sleep(0.4 + random.uniform(0, 0.3))
print("DONE", stats)
