"""最终综合分析: 主特征 + 主力资金 + 筹码, 输出最优买入时机结论"""
import pandas as pd, numpy as np, glob, os, json

res = pd.read_csv("/workspace/data/backtest_full.csv", parse_dates=["date"])
res["code"] = res["code"].astype(str).str.zfill(6)

# ---- 合并主力资金(事件日 + 前一日) ----
ff_rows = {}
for fp in glob.glob("/workspace/data/fundflow/*.csv"):
    code = os.path.basename(fp)[:-4]
    try:
        ff = pd.read_csv(fp, parse_dates=["date"]).sort_values("date")
    except Exception:
        continue
    ff = ff.set_index("date")
    ff_rows[code] = ff

def ff_feat(code, date):
    ff = ff_rows.get(code)
    if ff is None or date not in ff.index:
        return pd.Series({"main_pct_0": np.nan, "main_pct_prev": np.nan})
    i = ff.index.get_loc(date)
    cur = ff.iloc[i]["main_net_pct"]
    prev = ff.iloc[i - 1]["main_net_pct"] if i > 0 else np.nan
    return pd.Series({"main_pct_0": cur, "main_pct_prev": prev})

ff_df = res.apply(lambda r: ff_feat(r["code"], r["date"]), axis=1)
res = pd.concat([res, ff_df], axis=1)

# ---- 合并筹码(事件日前一交易日) ----
cyq_rows = {}
for fp in glob.glob("/workspace/data/cyq/*.csv"):
    code = os.path.basename(fp)[:-4]
    try:
        cy = pd.read_csv(fp, parse_dates=["日期"]).sort_values("日期")
    except Exception:
        continue
    cyq_rows[code] = cy.set_index("日期")

def cyq_feat(code, date):
    cy = cyq_rows.get(code)
    if cy is None:
        return pd.Series({"profit_ratio": np.nan, "avg_cost": np.nan, "conc90": np.nan})
    prev = cy[cy.index < date]
    if prev.empty:
        return pd.Series({"profit_ratio": np.nan, "avg_cost": np.nan, "conc90": np.nan})
    r = prev.iloc[-1]
    return pd.Series({"profit_ratio": r["获利比例"] * 100, "avg_cost": r["平均成本"], "conc90": r["90集中度"] * 100})

cy_df = res.apply(lambda r: cyq_feat(r["code"], r["date"]), axis=1)
res = pd.concat([res, cy_df], axis=1)
res.to_csv("/workspace/data/final_dataset.csv", index=False)

def report(df, desc):
    if len(df) < 8:
        print(f"{desc:<58} n={len(df)} 样本不足")
        return
    win = (df.ret > 0).mean() * 100
    print(f"{desc:<58} n={len(df):>4} 续板{df.cont.mean()*100:5.1f}% 胜率{win:5.1f}% 均{df.ret.mean():6.2f}% 中位{df.ret.median():6.2f}%")

print("样本量(含资金流):", res.main_pct_0.notna().sum(), " (含筹码):", res.profit_ratio.notna().sum())

sub = res[res.board_n == 2]
print("\n===== 2板开板: 主力资金维度 =====")
print("续板 vs 未续板 主力净流入占比中位数:")
print(sub.groupby("cont")[["main_pct_0", "main_pct_prev"]].median().round(2).to_string())
for desc, f in [
    ("主力净流入>0(当日)", lambda d: d.main_pct_0 > 0),
    ("主力净流入>10%", lambda d: d.main_pct_0 > 10),
    ("振幅<=5% + 主力净流入>0", lambda d: (d.amplitude <= 5) & (d.main_pct_0 > 0)),
    ("振幅<=5% + 主力净流入>5", lambda d: (d.amplitude <= 5) & (d.main_pct_0 > 5)),
]:
    report(sub[f(sub)], desc)

print("\n===== 2板开板: 筹码维度 =====")
subc = sub[sub.profit_ratio.notna()]
print("续板 vs 未续板 筹码特征中位数:")
print(subc.groupby("cont")[["profit_ratio", "conc90"]].median().round(2).to_string())
for desc, f in [
    ("获利盘<20%", lambda d: d.profit_ratio < 20),
    ("获利盘<35%", lambda d: d.profit_ratio < 35),
    ("90集中度<15%(筹码集中)", lambda d: d.conc90 < 15),
    ("获利盘<35% + 集中度<15%", lambda d: (d.profit_ratio < 35) & (d.conc90 < 15)),
    ("获利盘<35% + 集中度<15% + 振幅<=5%", lambda d: (d.profit_ratio < 35) & (d.conc90 < 15) & (d.amplitude <= 5)),
]:
    report(subc[f(subc)], desc)

print("\n===== 终极组合(2板开板) =====")
for desc, f in [
    ("振幅<=5+价<20+距低<40", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.pos_vs_low250 < 40)),
    ("上述+主力净流入>0", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.pos_vs_low250 < 40) & (d.main_pct_0 > 0)),
    ("上述+获利盘<40", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.pos_vs_low250 < 40) & (d.profit_ratio < 40)),
    ("全条件+主力>0+获利盘<40", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.pos_vs_low250 < 40) & (d.main_pct_0 > 0) & (d.profit_ratio < 40)),
]:
    report(sub[f(sub)], desc)

print("\n===== 1板开板: 终极组合 =====")
sub1 = res[res.board_n == 1]
for desc, f in [
    ("基准", lambda d: d.price > 0),
    ("振幅<=5+价<20+距低<40", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.pos_vs_low250 < 40)),
    ("上述+主力净流入>0", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.pos_vs_low250 < 40) & (d.main_pct_0 > 0)),
    ("全条件+主力>0+获利盘<40", lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.pos_vs_low250 < 40) & (d.main_pct_0 > 0) & (d.profit_ratio < 40)),
]:
    report(sub1[f(sub1)], desc)

# ---- 成功案例的共同画像 ----
print("\n===== 成功案例(回封后续板)画像 =====")
sc = res[res.cont]
print(sc[["amplitude", "price", "pos_vs_low250", "turnover", "vol_ratio", "open_depth", "main_pct_0", "profit_ratio", "conc90"]].describe(percentiles=[0.25, 0.5, 0.75]).round(2).to_string())
