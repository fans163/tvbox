"""严格联合条件回测: 开板回封打板策略的期望收益
入场: 开板日回封收盘(涨停价)买入
出场规则(近似):
  - 若成功(run>=3): 持有到连板结束后的第一根非涨停K线收盘卖出(即开板run的end_date之后首日)
  - 若失败(run=2): 次日收盘卖出
用概率加权计算期望收益、胜率、盈亏比
"""
import os, glob, json
import pandas as pd
import numpy as np

ev = pd.read_csv("/workspace/data/events.csv", parse_dates=["date"])
names = json.load(open("/workspace/data/stock_list.json"))

# 读取K线索引以便查后续行情
kl = {}
for fp in glob.glob("/workspace/data/klines/*.csv"):
    code = os.path.basename(fp)[:-4]
    kl[code] = pd.read_csv(fp, parse_dates=["date"])

runs = pd.read_csv("/workspace/data/runs_all.csv", parse_dates=["start_date", "end_date", "b1_date", "b2_date"])
runs["code"] = runs["code"].astype(str).str.zfill(6)

# 定位每个事件对应的run与退出价
results = []
for _, e in ev.iterrows():
    code = str(e["code"]).zfill(6)
    df = kl.get(code)
    if df is None:
        continue
    df = df.sort_values("date").reset_index(drop=True)
    hit = df.index[df["date"] == e["date"]]
    if len(hit) == 0:
        continue
    i = hit[0]
    buy = df.loc[i, "close"]
    label = e["label"]
    # 退出: 成功->run结束后首日收盘; 失败->次日收盘
    # run的end_date
    run = runs[(runs.code == code) & ((runs.b1_date == e["date"]) | (runs.b2_date == e["date"]))]
    if run.empty:
        continue
    end_date = run.iloc[0]["end_date"]
    end_idx = df.index[df["date"] == end_date]
    if label == "success":
        # 连板结束日之后第一根K线收盘卖出
        if len(end_idx) and end_idx[0] + 1 < len(df):
            sell = df.loc[end_idx[0] + 1, "close"]
            sell_date = df.loc[end_idx[0] + 1, "date"]
        else:
            continue
    else:
        # 失败: 开板日次日收盘
        if i + 1 < len(df):
            sell = df.loc[i + 1, "close"]
            sell_date = df.loc[i + 1, "date"]
        else:
            continue
    ret = (sell / buy - 1) * 100
    # 次日开盘(衡量隔夜溢价可执行性)
    nxt_open_ret = (df.loc[i + 1, "open"] / buy - 1) * 100 if i + 1 < len(df) else np.nan
    results.append({**e.to_dict(), "ret": ret, "nxt_open_ret": nxt_open_ret})

res = pd.DataFrame(results)
print("总样本:", len(res))

def report(df, desc):
    if len(df) < 10:
        print(f"{desc:<50} 样本不足")
        return
    win = (df.ret > 0).mean() * 100
    avg = df.ret.mean()
    med = df.ret.median()
    gp = df[df.ret > 0].ret.mean() if (df.ret > 0).any() else 0
    gl = abs(df[df.ret <= 0].ret.mean()) if (df.ret <= 0).any() else 1
    pl = gp / gl if gl else np.inf
    print(f"{desc:<50} n={len(df):>4} 胜率{win:5.1f}% 均收益{avg:6.2f}% 中位{med:6.2f}% 盈亏比{pl:.2f}")

print("\n===== 全样本基准 =====")
for bn in (1, 2):
    report(res[res.board_n == bn], f"{bn}板开板 全部")
report(res, "全部")

print("\n===== 联合条件筛选 =====")
conds = [
    ("低振幅<=5% + 价格<20", lambda d: (d.amplitude <= 5) & (d.price < 20)),
    ("低振幅<=5% + 价格<20 + 距低点<40%", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.pos_vs_low250 < 40)),
    ("低振幅<=5% + 价格<20 + 换手<12%", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.turnover < 12)),
    ("低振幅<=5% + 价格<20 + 距低点<40% + 换手<12%", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.pos_vs_low250 < 40) & (d.turnover < 12)),
    ("低振幅<=5% + 价格<20 + 距低点<40% + 换手<12% + 非熊市", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.pos_vs_low250 < 40) & (d.turnover < 12) & (d.env != "熊市")),
    ("低振幅<=6% + 价格<15 + 距低点<35% + 换手3-12% + 量比>=1", lambda d: (d.amplitude <= 6) & (d.price < 15) & (d.pos_vs_low250 < 35) & (d.turnover >= 3) & (d.turnover < 12) & (d.vol_ratio >= 1)),
]
for bn in (1, 2):
    print(f"\n--- {bn}板开板 ---")
    sub = res[res.board_n == bn]
    report(sub, "基准(全部)")
    for desc, f in conds:
        report(sub[f(sub)], desc)

print("\n===== 成功/失败的收益分解 (理解盈亏结构) =====")
for bn in (1, 2):
    sub = res[res.board_n == bn]
    print(f"\n--- {bn}板开板 ---")
    print(sub.groupby("label")["ret"].describe()[["count", "mean", "50%", "min", "max"]].round(2).to_string())

res.to_csv("/workspace/data/backtest.csv", index=False)
