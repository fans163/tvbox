"""对比分析: 成功(连板>=3) vs 失败(止于2板) 开板回封事件的特征差异"""
import pandas as pd
import numpy as np

ev = pd.read_csv("/workspace/data/events.csv", parse_dates=["date"])
pd.set_option("display.width", 250)

def med(x): return np.nanmedian(x)
def mean(x): return np.nanmean(x)

print("=" * 90)
print("样本规模:", ev.groupby("label").size().to_dict())
print("按板位:", ev.groupby(["label", "board_n"]).size().to_dict())

# ---------- 1. 市场环境 ----------
print("\n" + "=" * 90)
print("【1】开板日大盘环境分布 (占比%)")
t = pd.crosstab(ev["env"], ev["label"], normalize="columns") * 100
print(t.round(1).to_string())
print("\n成功率 = 成功/(成功+失败) 按环境:")
t2 = pd.crosstab(ev["env"], ev["label"])
t2["成功率%"] = (t2["success"] / t2.sum(axis=1) * 100).round(1)
print(t2.to_string())
print("\n指数20日涨幅中位数 / 60日涨幅中位数:")
print(ev.groupby("label")[["idx_ret20", "idx_ret60"]].median().round(2).to_string())

# ---------- 2. K线位置与形态 ----------
print("\n" + "=" * 90)
print("【2】K线位置与形态")
feats = ["open_pct", "amplitude", "open_depth", "pos_vs_low250", "price"]
agg = ev.groupby("label")[feats].median().round(2)
print(agg.to_string())
print("\n创60日新高比例 %:")
print((ev.groupby("label")["break_high60"].mean() * 100).round(1).to_string())
print("\n价格分位带成功率:")
ev["price_band"] = pd.cut(ev["price"], [0, 5, 10, 15, 20, 30, 50, 500])
t3 = pd.crosstab(ev["price_band"], ev["label"])
t3["成功率%"] = (t3["success"] / t3.sum(axis=1) * 100).round(1)
print(t3.to_string())

# ---------- 3. 量能换手 ----------
print("\n" + "=" * 90)
print("【3】量能与换手")
print(ev.groupby("label")[["turnover", "vol_ratio", "amount_yi"]].median().round(2).to_string())
print("\n换手率分位带成功率:")
ev["to_band"] = pd.cut(ev["turnover"], [0, 3, 5, 8, 12, 18, 25, 40, 100])
t4 = pd.crosstab(ev["to_band"], ev["label"])
t4["成功率%"] = (t4["success"] / t4.sum(axis=1) * 100).round(1)
print(t4.to_string())
print("\n量比(对5日均量)分位带成功率:")
ev["vr_band"] = pd.cut(ev["vol_ratio"], [0, 1, 2, 3, 5, 8, 15, 100])
t5 = pd.crosstab(ev["vr_band"], ev["label"])
t5["成功率%"] = (t5["success"] / t5.sum(axis=1) * 100).round(1)
print(t5.to_string())

# ---------- 4. 板块/市场热度 ----------
print("\n" + "=" * 90)
print("【4】板块与市场热度")
print(ev.groupby("label")[["mkt_zt_count", "mkt_max_lb", "ind_zt_count", "ind_rank"]].median().round(1).to_string())
print("\n所属行业当日涨停家数分带成功率:")
ev["ind_band"] = pd.cut(ev["ind_zt_count"], [-1, 0, 1, 2, 3, 5, 8, 50])
t6 = pd.crosstab(ev["ind_band"], ev["label"])
t6["成功率%"] = (t6["success"] / t6.sum(axis=1) * 100).round(1)
print(t6.to_string())
print("\n市场涨停家数(情绪)分带成功率:")
ev["mkt_band"] = pd.cut(ev["mkt_zt_count"], [0, 20, 35, 50, 70, 100, 300])
t7 = pd.crosstab(ev["mkt_band"], ev["label"])
t7["成功率%"] = (t7["success"] / t7.sum(axis=1) * 100).round(1)
print(t7.to_string())

# ---------- 5. 行业成功率 TOP ----------
print("\n" + "=" * 90)
print("【5】行业维度(成功样本数>=10的行业)")
ind = ev.groupby("industry").agg(
    total=("label", "count"),
    succ=("label", lambda s: (s == "success").sum()))
ind["成功率%"] = (ind["succ"] / ind["total"] * 100).round(1)
ind = ind[ind["succ"] >= 10].sort_values("成功率%", ascending=False)
print(ind.head(20).to_string())

# ---------- 6. 开板形态组合 ----------
print("\n" + "=" * 90)
print("【6】开板形态组合成功率 (高开幅度 × 振幅)")
ev["open_band"] = pd.cut(ev["open_pct"], [-100, 0, 2, 4, 6, 8, 21])
ev["amp_band"] = pd.cut(ev["amplitude"], [0, 5, 8, 11, 14, 21])
piv = pd.crosstab([ev["open_band"], ev["amp_band"]], ev["label"])
piv["成功率%"] = (piv["success"] / piv.sum(axis=1) * 100).round(1)
piv["样本"] = piv["success"] + piv["fail"]
print(piv[piv["样本"] >= 30].sort_values("成功率%", ascending=False).head(20).to_string())

# ---------- 7. 后续表现 ----------
print("\n" + "=" * 90)
print("【7】开板日回封买入的后续表现")
print(ev.groupby("label")[["next_open_pct", "next_close_pct", "fut5_close_pct", "fut5_max_pct"]].median().round(2).to_string())
print("\n次日续板率 %:")
print((ev.groupby("label")["next_continue_zt"].mean() * 100).round(1).to_string())

ev.to_csv("/workspace/data/events_enriched.csv", index=False)
print("\nsaved events_enriched.csv")
