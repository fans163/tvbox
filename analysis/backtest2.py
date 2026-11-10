"""修正回测:
样本 = 所有"首板或2板开板回封"的事件(不限run高度, 这才是开板时刻真实可观察的宇宙)
事件成功 = 开板回封的次日该股继续涨停(连板延续)
策略: 开板日回封以涨停价买入
  - 次日继续涨停: 持有, 直到断板日收盘卖出(吃完整段连板)
  - 次日未涨停: 次日收盘卖出
"""
import os, glob, json
import pandas as pd
import numpy as np

names = json.load(open("/workspace/data/stock_list.json"))

def limit_pct_of(code, name):
    if "ST" in str(name).upper():
        return 0.05
    if code.startswith(("300", "301", "688")):
        return 0.20
    return 0.10

def round2(x):
    return np.floor(x * 100 + 0.5) / 100.0

kl = {}
for fp in glob.glob("/workspace/data/klines/*.csv"):
    code = os.path.basename(fp)[:-4]
    kl[code] = pd.read_csv(fp, parse_dates=["date"])

# 重建所有开板回封事件(首板/2板): 用runs_all(含所有run)
runs = pd.read_csv("/workspace/data/runs_all.csv",
                   parse_dates=["start_date", "end_date", "b1_date", "b2_date"])
runs["code"] = runs["code"].astype(str).str.zfill(6)

events = []
for _, r in runs.iterrows():
    for bn, bdate, opened in [(1, r["b1_date"], r["b1_opened"]), (2, r["b2_date"], r["b2_opened"])]:
        if not opened or pd.isna(bdate):
            continue
        events.append({"code": r["code"], "name": r["name"], "board_n": bn,
                       "date": bdate, "run_height": r["height"]})
ev = pd.DataFrame(events)
print("全部开板回封事件(首/2板):", len(ev))

# 预计算每只股票的涨停标记与指标
cache = {}
def get_df(code):
    if code in cache:
        return cache[code]
    df = kl.get(code)
    if df is None:
        cache[code] = None
        return None
    df = df.sort_values("date").reset_index(drop=True)
    name = names.get(code, "")
    lp = limit_pct_of(code, name)
    df["prev_close"] = df["close"].shift(1)
    df["limit_price"] = round2(df["prev_close"] * (1 + lp))
    df["is_zt"] = (df["close"] >= df["limit_price"] - 1e-6) & df["prev_close"].notna()
    # 指标
    df["vol_ma5"] = df["volume"].shift(1).rolling(5).mean()
    df["vol_ratio"] = df["volume"] / df["vol_ma5"]
    df["low250"] = df["low"].shift(1).rolling(250, min_periods=60).min()
    df["amplitude"] = df["amplitude"]
    cache[code] = df
    return df

# 指数环境
idx = pd.read_csv("/workspace/data/index_sh.csv", parse_dates=["date"]).sort_values("date")
idx["ma60"] = idx["close"].rolling(60, min_periods=20).mean()
idx["ma250"] = idx["close"].rolling(250, min_periods=84).mean()
idx["ma60_slope"] = idx["ma60"].pct_change(5) * 100
def env_of(r):
    if pd.isna(r.ma60) or pd.isna(r.ma250):
        return "震荡市"
    if r.close > r.ma60 and r.close > r.ma250 and r.ma60_slope > 0:
        return "牛市"
    if r.close < r.ma60 and r.ma60_slope < 0:
        return "熊市"
    return "震荡市"
idx["env"] = idx.apply(env_of, axis=1)
env_map = idx.set_index("date")["env"].to_dict()

rows = []
for _, e in ev.iterrows():
    df = get_df(e["code"])
    if df is None:
        continue
    hit = df.index[df["date"] == e["date"]]
    if len(hit) == 0:
        continue
    i = hit[0]
    r = df.loc[i]
    if i + 1 >= len(df):
        continue
    nxt = df.loc[i + 1]
    buy = r["close"]
    cont = bool(nxt["is_zt"])  # 次日续板
    # 出场
    if cont:
        # 持有到断板日收盘: 从次日开始找首个非涨停日
        j = i + 1
        while j < len(df) and df.loc[j, "is_zt"]:
            j += 1
        if j < len(df):
            sell = df.loc[j, "close"]
            hold_days = j - i
        else:
            continue
    else:
        sell = nxt["close"]
        hold_days = 1
    ret = (sell / buy - 1) * 100
    rows.append({
        "code": e["code"], "name": e["name"], "board_n": e["board_n"], "date": e["date"],
        "cont": cont, "ret": ret, "hold_days": hold_days,
        "run_height": e["run_height"],
        # 开板日特征
        "open_pct": (r["open"] / r["prev_close"] - 1) * 100,
        "amplitude": r["amplitude"],
        "open_depth": (r["low"] / r["limit_price"] - 1) * 100,
        "price": r["close"],
        "turnover": r["turnover"],
        "vol_ratio": r["vol_ratio"],
        "amount_yi": r["amount"] / 1e8,
        "pos_vs_low250": (r["close"] / r["low250"] - 1) * 100 if r["low250"] else np.nan,
        "env": env_map.get(e["date"], "震荡市"),
        "nxt_open_ret": (nxt["open"] / buy - 1) * 100,
    })
res = pd.DataFrame(rows)
res.to_csv("/workspace/data/backtest_full.csv", index=False)
print("有效回测样本:", len(res), " 续板率:", f"{res.cont.mean()*100:.1f}%")

def report(df, desc):
    if len(df) < 10:
        print(f"{desc:<52} 样本不足({len(df)})")
        return
    win = (df.ret > 0).mean() * 100
    avg = df.ret.mean()
    med = df.ret.median()
    gp = df[df.ret > 0].ret.sum()
    gl = abs(df[df.ret <= 0].ret.sum())
    pl = gp / gl if gl else np.inf
    cont_r = df.cont.mean() * 100
    print(f"{desc:<52} n={len(df):>4} 续板{cont_r:5.1f}% 胜率{win:5.1f}% 均{avg:6.2f}% 中位{med:6.2f}% 盈亏比{pl:4.2f}")

print("\n===== 基准 =====")
for bn in (1, 2):
    report(res[res.board_n == bn], f"{bn}板开板 全部")
report(res, "全部")

print("\n===== 单特征有效性(按2板开板, 更有交易意义) =====")
sub2 = res[res.board_n == 2]
for desc, f in [
    ("振幅<=5%", lambda d: d.amplitude <= 5),
    ("振幅<=6%", lambda d: d.amplitude <= 6),
    ("价格<10", lambda d: d.price < 10),
    ("价格<20", lambda d: d.price < 20),
    ("距低点<30%", lambda d: d.pos_vs_low250 < 30),
    ("距低点<40%", lambda d: d.pos_vs_low250 < 40),
    ("换手3-12%", lambda d: (d.turnover >= 3) & (d.turnover <= 12)),
    ("量比>=1", lambda d: d.vol_ratio >= 1),
    ("量比1-5", lambda d: (d.vol_ratio >= 1) & (d.vol_ratio <= 5)),
    ("成交额<5亿", lambda d: d.amount_yi < 5),
    ("开板深度>-5%(浅)", lambda d: d.open_depth > -5),
    ("牛市", lambda d: d.env == "牛市"),
    ("非熊市", lambda d: d.env != "熊市"),
]:
    report(sub2[f(sub2)], desc)

print("\n===== 联合条件(2板开板) =====")
for desc, f in [
    ("振幅<=5%+价格<20", lambda d: (d.amplitude <= 5) & (d.price < 20)),
    ("振幅<=5%+价格<20+距低点<40%", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.pos_vs_low250 < 40)),
    ("振幅<=5%+价格<20+距低点<40%+换手3-12%", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.pos_vs_low250 < 40) & (d.turnover >= 3) & (d.turnover <= 12)),
    ("振幅<=5%+价格<20+距低点<40%+换手3-12%+量比>=1", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.pos_vs_low250 < 40) & (d.turnover >= 3) & (d.turnover <= 12) & (d.vol_ratio >= 1)),
    ("上述+非熊市", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.pos_vs_low250 < 40) & (d.turnover >= 3) & (d.turnover <= 12) & (d.vol_ratio >= 1) & (d.env != "熊市")),
]:
    report(sub2[f(sub2)], desc)

print("\n===== 联合条件(1板开板) =====")
sub1 = res[res.board_n == 1]
report(sub1, "基准")
for desc, f in [
    ("振幅<=5%+价格<20", lambda d: (d.amplitude <= 5) & (d.price < 20)),
    ("振幅<=5%+价格<20+距低点<40%", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.pos_vs_low250 < 40)),
    ("振幅<=5%+价格<20+距低点<40%+换手3-12%+量比>=1", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.pos_vs_low250 < 40) & (d.turnover >= 3) & (d.turnover <= 12) & (d.vol_ratio >= 1)),
    ("上述+非熊市", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.pos_vs_low250 < 40) & (d.turnover >= 3) & (d.turnover <= 12) & (d.vol_ratio >= 1) & (d.env != "熊市")),
]:
    report(sub1[f(sub1)], desc)

print("\n===== 分时段稳健性(最优条件) =====")
res["half"] = np.where(res.date < "2026-05-01", "前段", "后段")
best = res[(res.board_n == 2) & (res.amplitude <= 5) & (res.price < 20) & (res.pos_vs_low250 < 40) & (res.turnover >= 3) & (res.turnover <= 12) & (res.vol_ratio >= 1)]
for h in ["前段", "后段"]:
    report(best[best.half == h], f"2板最优条件 {h}")
