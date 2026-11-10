"""从全市场日K线重构涨停历史，识别连板>=3的run，提取首板/2板开板回封案例。
输出:
  /workspace/data/limit_days.csv   全市场每日涨停明细
  /workspace/data/cases.csv        连板run案例（含正负样本）
"""
import os, json, glob
import pandas as pd
import numpy as np

DATA_DIR = "/workspace/data/klines"
names = json.load(open("/workspace/data/stock_list.json"))

def limit_pct_of(code, name):
    if "ST" in name.upper():
        return 0.05
    if code.startswith(("300", "301", "688")):
        return 0.20
    return 0.10

def round2(x):
    # A股涨停价: 四舍五入到分(half-up)
    return np.floor(x * 100 + 0.5) / 100.0

frames = []
files = sorted(glob.glob(os.path.join(DATA_DIR, "*.csv")))
print("files:", len(files))
for fp in files:
    code = os.path.basename(fp)[:-4]
    name = names.get(code, "")
    try:
        df = pd.read_csv(fp)
    except Exception:
        continue
    if len(df) < 30:
        continue
    df["code"] = code
    df["name"] = name
    df["lpct"] = limit_pct_of(code, name)
    frames.append(df)

all_df = pd.concat(frames, ignore_index=True)
all_df["date"] = pd.to_datetime(all_df["date"])
all_df = all_df.sort_values(["code", "date"]).reset_index(drop=True)
print("rows:", len(all_df), "stocks:", all_df.code.nunique())

# 涨停价 & 事件判定
g = all_df.groupby("code", sort=False)
all_df["prev_close"] = g["close"].shift(1)
all_df["limit_price"] = round2(all_df["prev_close"] * (1 + all_df["lpct"]))
all_df["is_zt"] = (all_df["close"] >= all_df["limit_price"] - 1e-6) & all_df["prev_close"].notna()
all_df["opened"] = all_df["is_zt"] & (all_df["low"] < all_df["limit_price"] - 1e-6)
all_df["yizi"] = all_df["is_zt"] & ~all_df["opened"]

# 连板计数（连续is_zt的天数）
def consec(s):
    grp = (s != s.shift()).cumsum()
    return s.groupby(grp).cumsum().where(s, 0)
all_df["lianban"] = g["is_zt"].apply(consec).reset_index(level=0, drop=True) if False else None
# 用更稳的写法
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

zt = all_df[all_df["is_zt"]].copy()
zt.to_csv("/workspace/data/limit_days.csv", index=False)
print("limit-up day records:", len(zt))

# ===== 构建连板run =====
# run定义: 连板序列 lianban 1,2,3... 到断板为止
runs = []
for code, sub in all_df.groupby("code", sort=False):
    sub = sub.reset_index(drop=True)
    lbs = sub["lianban"].values
    n = len(sub)
    i = 0
    while i < n:
        if lbs[i] == 1:
            j = i
            while j + 1 < n and lbs[j + 1] == lbs[j] + 1:
                j += 1
            height = lbs[j]
            if height >= 2:  # 至少2板才有"2板开板"语境；首板开板也要求最终>=2? 负样本需要<3,含首板后断的
                pass
            # 记录所有 run(高度>=1)
            b1 = sub.iloc[i]
            b2 = sub.iloc[i + 1] if i + 1 <= j else None
            runs.append({
                "code": code, "name": b1["name"],
                "start_date": b1["date"], "end_date": sub.iloc[j]["date"],
                "height": height,
                "b1_date": b1["date"], "b1_opened": bool(b1["opened"]), "b1_yizi": bool(b1["yizi"]),
                "b1_open": b1["open"], "b1_close": b1["close"], "b1_high": b1["high"], "b1_low": b1["low"],
                "b1_volume": b1["volume"], "b1_turnover": b1["turnover"], "b1_amp": b1["amplitude"],
                "b2_date": b2["date"] if b2 is not None else None,
                "b2_opened": bool(b2["opened"]) if b2 is not None else None,
                "b2_yizi": bool(b2["yizi"]) if b2 is not None else None,
                "b2_open": b2["open"] if b2 is not None else None,
                "b2_close": b2["close"] if b2 is not None else None,
                "b2_high": b2["high"] if b2 is not None else None,
                "b2_low": b2["low"] if b2 is not None else None,
                "b2_volume": b2["volume"] if b2 is not None else None,
                "b2_turnover": b2["turnover"] if b2 is not None else None,
                "b2_amp": b2["amplitude"] if b2 is not None else None,
            })
            i = j + 1
        else:
            i += 1

runs_df = pd.DataFrame(runs)
runs_df.to_csv("/workspace/data/runs_all.csv", index=False)
print("runs total:", len(runs_df), " runs>=3:", (runs_df.height >= 3).sum())

# ===== 案例: 首板或2板开板回封 =====
# 正样本: run高度>=3 且 (b1_opened 或 b2_opened)
pos = runs_df[(runs_df.height >= 3) & (runs_df.b1_opened | (runs_df.b2_opened == True))].copy()
pos["label"] = "success"
# 负样本: 开板回封且达到2板 但未能到3板(首板或2板开过板, 高度恰为2)——真正的"回封后失败"对照组
neg = runs_df[(runs_df.height == 2) & (runs_df.b1_opened | (runs_df.b2_opened == True))].copy()
neg["label"] = "fail"
cases = pd.concat([pos, neg], ignore_index=True)
# 开板发生的板位
def open_board(r):
    bs = []
    if r["b1_opened"]: bs.append(1)
    if r["b2_opened"] is True or r["b2_opened"] == True: bs.append(2)
    return ",".join(map(str, bs))
cases["open_boards"] = cases.apply(open_board, axis=1)
cases.to_csv("/workspace/data/cases.csv", index=False)
print("positive:", len(pos), " negative:", len(neg))
print("\n=== 正样本(高度>=3且首/2板开过板)高度分布 ===")
print(pos.height.value_counts().sort_index().to_string())
