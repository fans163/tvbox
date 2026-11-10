"""对每个开板回封事件(首板或2板)计算特征:
市场环境 / K线位置形态 / 量能换手 / 板块热度 / 后续表现
输出 /workspace/data/events.csv
"""
import os, json, glob
import pandas as pd
import numpy as np

DATA_DIR = "/workspace/data/klines"
names = json.load(open("/workspace/data/stock_list.json"))

# ---- 读全市场K线 ----
frames = []
for fp in sorted(glob.glob(os.path.join(DATA_DIR, "*.csv"))):
    code = os.path.basename(fp)[:-4]
    try:
        df = pd.read_csv(fp)
    except Exception:
        continue
    if len(df) < 30:
        continue
    df["code"] = code
    frames.append(df)
all_df = pd.concat(frames, ignore_index=True)
all_df["date"] = pd.to_datetime(all_df["date"])
all_df = all_df.sort_values(["code", "date"]).reset_index(drop=True)

def round2(x):
    return np.floor(x * 100 + 0.5) / 100.0

def limit_pct_of(code, name):
    if "ST" in name.upper():
        return 0.05
    if code.startswith(("300", "301", "688")):
        return 0.20
    return 0.10

all_df["name"] = all_df["code"].map(names)
all_df["lpct"] = [limit_pct_of(c, n) for c, n in zip(all_df["code"], all_df["name"])]
g = all_df.groupby("code", sort=False)
all_df["prev_close"] = g["close"].shift(1)
all_df["limit_price"] = round2(all_df["prev_close"] * (1 + all_df["lpct"]))
all_df["is_zt"] = (all_df["close"] >= all_df["limit_price"] - 1e-6) & all_df["prev_close"].notna()

# 连板计数
lb = []
for code, sub in all_df.groupby("code", sort=False):
    s = sub["is_zt"].values
    c = 0
    arr = np.zeros(len(s), dtype=int)
    for i, v in enumerate(s):
        c = c + 1 if v else 0
        arr[i] = c
    lb.append(pd.Series(arr, index=sub.index))
all_df["lianban"] = pd.concat(lb).sort_index()

# 5日均量(不含当日)
all_df["vol_ma5_prev"] = g["volume"].apply(lambda s: s.shift(1).rolling(5).mean()).reset_index(level=0, drop=True)
all_df["vol_ratio"] = all_df["volume"] / all_df["vol_ma5_prev"]

# 250日低点/60日高点(截至前一日)
all_df["low250_prev"] = g["low"].apply(lambda s: s.shift(1).rolling(250, min_periods=60).min()).reset_index(level=0, drop=True)
all_df["high60_prev"] = g["high"].apply(lambda s: s.shift(1).rolling(60, min_periods=20).max()).reset_index(level=0, drop=True)
all_df["close_ma20"] = g["close"].apply(lambda s: s.rolling(20).mean()).reset_index(level=0, drop=True)
# 开板深度: 盘中最低价相对涨停价的距离(%)——衡量回封前被砸开的幅度
all_df["open_depth"] = (all_df["low"] / all_df["limit_price"] - 1) * 100

by_code = {c: sub.reset_index(drop=True) for c, sub in all_df.groupby("code")}

# ---- 市场环境 ----
idx = pd.read_csv("/workspace/data/index_sh.csv")
idx["date"] = pd.to_datetime(idx["date"])
idx = idx.sort_values("date").reset_index(drop=True)
for w in (20, 60, 120, 250):
    idx[f"ma{w}"] = idx["close"].rolling(w, min_periods=max(10, w // 3)).mean()
idx["ret20"] = idx["close"].pct_change(20) * 100
idx["ret60"] = idx["close"].pct_change(60) * 100
idx["ma60_slope"] = idx["ma60"].pct_change(5) * 100  # 5日斜率
def env_class(r):
    if pd.isna(r["ma60"]) or pd.isna(r["ma250"]):
        return "未知"
    above60 = r["close"] > r["ma60"]
    above250 = r["close"] > r["ma250"]
    slope_up = r["ma60_slope"] > 0
    if above60 and above250 and slope_up:
        return "牛市"
    if (not above60) and (not slope_up):
        return "熊市"
    return "震荡市"
idx["env"] = idx.apply(env_class, axis=1)
idx_map = idx.set_index("date")[["close", "ma20", "ma60", "ma250", "ret20", "ret60", "env"]].to_dict("index")

# ---- 板块/市场热度(用重构涨停数据自算) ----
ind_map = json.load(open("/workspace/data/industry_map.json"))  # code -> 行业
zt_days = all_df[all_df["is_zt"]][["date", "code", "lianban"]].copy()
mkt_heat = zt_days.groupby("date").agg(zt_count=("code", "count"), max_lb=("lianban", "max")).reset_index()
mkt_map = mkt_heat.set_index("date").to_dict("index")
zt_days["industry"] = zt_days["code"].map(ind_map)
ind_heat = zt_days.groupby(["date", "industry"]).size().reset_index(name="ind_zt_count")
ind_heat_map = {(r["date"], r["industry"]): r["ind_zt_count"] for _, r in ind_heat.iterrows()}
# 当日行业涨停数排名
ind_heat["rank"] = ind_heat.groupby("date")["ind_zt_count"].rank(ascending=False, method="min")
ind_rank_map = {(r["date"], r["industry"]): r["rank"] for _, r in ind_heat.iterrows()}

# ---- 事件构建 ----
cases = pd.read_csv("/workspace/data/cases.csv", parse_dates=["b1_date", "b2_date", "start_date", "end_date"])
cases["code"] = cases["code"].astype(str).str.zfill(6)
rows = []
for _, c in cases.iterrows():
    code = c["code"]
    sub = by_code.get(code)
    if sub is None:
        continue
    boards = [int(x) for x in str(c["open_boards"]).split(",") if x.strip().isdigit()]
    for bn in boards:
        bdate = c["b1_date"] if bn == 1 else c["b2_date"]
        rec = sub[sub["date"] == bdate]
        if rec.empty:
            continue
        r = rec.iloc[0]
        i = r.name  # reset_index后的位置
        # 事件前一日(启动前)数据: 首板事件取首板前, 2板事件取2板前(即首板)
        prev_i = i - 1
        prev = sub.iloc[prev_i] if prev_i >= 0 else None
        # 后续表现: 开板日收盘买入
        nxt = sub.iloc[i + 1: i + 6]
        next1 = sub.iloc[i + 1] if i + 1 < len(sub) else None
        buy = r["close"]
        fut_close5 = sub.iloc[i + 5]["close"] if i + 5 < len(sub) else np.nan
        fut_max5 = nxt["high"].max() if len(nxt) else np.nan
        mkt = mkt_map.get(bdate, {})
        ind = ind_map.get(code, "未知")
        d0 = idx_map.get(bdate, {})
        rows.append({
            "code": code, "name": c["name"], "board_n": bn, "date": bdate,
            "run_height": c["height"], "label": c["label"],
            "industry": ind,
            # K线形态
            "open_pct": (r["open"] / r["prev_close"] - 1) * 100,
            "amplitude": r["amplitude"],
            "open_depth": r["open_depth"],  # 开板最深回落幅度%(相对涨停价)
            "gap_to_open": (r["open"] / r["prev_close"] - 1) * 100,
            "pos_vs_low250": (r["close"] / r["low250_prev"] - 1) * 100 if r["low250_prev"] else np.nan,  # 距250日低点涨幅%
            "break_high60": bool(r["close"] >= (r["high60_prev"] or 1e18) - 1e-6),  # 创60日新高
            "price": r["close"],
            # 量能
            "turnover": r["turnover"], "vol_ratio": r["vol_ratio"],
            "amount_yi": r["amount"] / 1e8,
            # 市场环境
            "env": d0.get("env", "未知"),
            "idx_ret20": d0.get("ret20"), "idx_ret60": d0.get("ret60"),
            "idx_above_ma60": bool(d0.get("close", 0) > d0.get("ma60", 1e18)) if d0 else None,
            # 热度
            "mkt_zt_count": mkt.get("zt_count"), "mkt_max_lb": mkt.get("max_lb"),
            "ind_zt_count": ind_heat_map.get((bdate, ind), 0),
            "ind_rank": ind_rank_map.get((bdate, ind), np.nan),
            # 后续表现
            "next_open_pct": (next1["open"] / buy - 1) * 100 if next1 is not None else np.nan,
            "next_close_pct": (next1["close"] / buy - 1) * 100 if next1 is not None else np.nan,
            "fut5_close_pct": (fut_close5 / buy - 1) * 100 if not pd.isna(fut_close5) else np.nan,
            "fut5_max_pct": (fut_max5 / buy - 1) * 100 if not pd.isna(fut_max5) else np.nan,
            "next_continue_zt": bool(next1["is_zt"]) if next1 is not None else None,
        })

ev = pd.DataFrame(rows)
ev.to_csv("/workspace/data/events.csv", index=False)
print("events:", len(ev))
print(ev.groupby(["label", "board_n"]).size().to_string())
