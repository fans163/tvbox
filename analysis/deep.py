"""深度分析: 板位拆分 / 环境交互 / 时间段稳健性 / 连板高度预测"""
import pandas as pd
import numpy as np

ev = pd.read_csv("/workspace/data/events.csv", parse_dates=["date"])
pd.set_option("display.width", 250)

def sr(df):
    """成功率"""
    s = (df["label"] == "success").sum()
    f = (df["label"] == "fail").sum()
    return f"{s/(s+f)*100:.1f}%" if s + f else "-", s + f

# ========== A. 首板开板 vs 2板开板 分开看 ==========
print("=" * 90)
print("【A】按板位拆分: 成功vs失败特征中位数")
feats = ["open_pct", "amplitude", "open_depth", "pos_vs_low250", "price",
         "turnover", "vol_ratio", "amount_yi", "mkt_zt_count", "ind_zt_count"]
for bn in (1, 2):
    sub = ev[ev.board_n == bn]
    print(f"\n--- {bn}板开板 (n={len(sub)}, 成功率 {(sub.label=='success').mean()*100:.1f}%) ---")
    print(sub.groupby("label")[feats].median().round(2).T.to_string())

# ========== B. 环境×板位成功率 ==========
print("\n" + "=" * 90)
print("【B】环境 × 板位 成功率")
for bn in (1, 2):
    sub = ev[ev.board_n == bn]
    print(f"\n--- {bn}板开板 ---")
    for env in ["牛市", "震荡市", "熊市"]:
        s, n = sr(sub[sub.env == env])
        print(f"  {env}: 成功率 {s} (n={n})")

# ========== C. 时间段稳健性(分上下半年) ==========
print("\n" + "=" * 90)
print("【C】分时段成功率(稳健性检验)")
ev["half"] = np.where(ev.date < "2026-05-01", "2025H2-2026H1前段", "2026H1后段-2026H2")
for bn in (1, 2):
    sub = ev[ev.board_n == bn]
    t = pd.crosstab(sub["half"], sub["label"])
    t["成功率%"] = (t["success"] / t.sum(axis=1) * 100).round(1)
    print(f"\n--- {bn}板开板 ---")
    print(t.to_string())

# ========== D. 连板高度预测: 成功案例中哪些走得更远 ==========
print("\n" + "=" * 90)
print("【D】成功案例的连板高度 vs 开板日特征 (只保留首板或2板单次开板)")
suc = ev[ev.label == "success"].copy()
suc["tall"] = suc["run_height"] >= 5  # 5板以上为妖股
print("成功案例高度分布:")
print(suc.run_height.value_counts().sort_index().to_string())
print("\n高板(>=5) vs 普通(3-4) 开板日特征中位数:")
print(suc.groupby("tall")[feats + ["idx_ret20"]].median().round(2).T.to_string())
print("\n高度>=5 的开板深度分布 %:")
tall = suc[suc.tall]
print(pd.cut(tall["open_depth"], [-100, -9, -7, -5, -3, -1, 0]).value_counts().sort_index().to_string())
print("\n高度3-4 的开板深度分布 %:")
mid = suc[~suc.tall]
print(pd.cut(mid["open_depth"], [-100, -9, -7, -5, -3, -1, 0]).value_counts().sort_index().to_string())

# ========== E. 综合打分: 用判别力较强的特征组合 ==========
print("\n" + "=" * 90)
print("【E】多特征组合的成功率")
def combo_sr(df, cond, desc):
    sub = df[cond(df)]
    s, n = sr(sub)
    base, nb = sr(df)
    print(f"  {desc:<55} 成功率 {s} (n={n})  [基准 {base}]")

for bn in (1, 2):
    sub = ev[ev.board_n == bn]
    print(f"\n--- {bn}板开板 组合条件 ---")
    combo_sr(sub, lambda d: d.amplitude <= 5, "低振幅<=5%")
    combo_sr(sub, lambda d: d.amplitude <= 5, "低振幅<=5%")
    combo_sr(sub, lambda d: (d.amplitude <= 5) & (d.price < 20), "低振幅<=5% + 价格<20")
    combo_sr(sub, lambda d: (d.amplitude <= 5) & (d.price < 20) & (d.turnover < 12), "低振幅 + 价格<20 + 换手<12%")
    combo_sr(sub, lambda d: (d.open_depth > -5), "浅开板(深度>-5%)")
    combo_sr(sub, lambda d: (d.open_depth > -5) & (d.price < 20), "浅开板 + 价格<20")
    combo_sr(sub, lambda d: (d.amplitude <= 5) & (d.mkt_zt_count >= 50), "低振幅 + 市场情绪尚可(涨停>=50家)")
    combo_sr(sub, lambda d: (d.env == "牛市") & (d.amplitude <= 5), "牛市 + 低振幅")
    combo_sr(sub, lambda d: (d.vol_ratio >= 1) & (d.vol_ratio <= 5) & (d.amplitude <= 8), "量比1-5 + 振幅<=8%")
    combo_sr(sub, lambda d: (d.amount_yi < 3), "成交额<3亿(小盘)")
    combo_sr(sub, lambda d: (d.amount_yi < 3) & (d.amplitude <= 6), "成交额<3亿 + 低振幅")
    combo_sr(sub, lambda d: (d.pos_vs_low250 < 40) & (d.amplitude <= 6), "距低点<40% + 低振幅")
