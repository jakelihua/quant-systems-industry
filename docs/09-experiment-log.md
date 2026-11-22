# 已执行实验与复算记录

日期为 2026-11-22。每份数字都能追溯到同目录代码与机器输出。真实行情只用于 ETF 样本，微观结构、期权、期货和其他金融账户示例使用合成路径。

## R1 真实行情前推

运行 `python3 -m lab.research`。2019–2025 年每年按此前日收益训练选 20/60/120 日窗口。七年均选 20 日。前推策略年化 13.25%、最大回撤 −35.16%，固定 60 日为 9.85% 与 −31.55%，同池等权为 14.61% 与 −20.71%。前推 97.5% 日 ES 3.64%。改动 2025 年未来收益后，先前的选择保持一致。[机器结果](../evidence/research.json) · [方法](03-research-and-risk.md)

## R2 模型漂移

运行 `python3 -m lab.model_drift`。固定随机种子下按 0–299、300–359、360–419 切分。线性模型仅在首段拟合。稳定验证段 RMSE 18.48 bp，优于零预测的 37.25 bp。人为让特征均值移动且系数反向后，RMSE 76.73 bp，劣于零预测的 34.82 bp，特征均值监控触发。均值告警只能揭示数据变化，模型失效由后续到达的标签独立确认。把生成器改为仅反转系数、不改特征均值，再验证监控漏报。[机器结果](../evidence/model-drift.json)

## D1 PIT 与盘口恢复

运行 `python3 -m lab.data_plane`。历史财务修订在三个决策时刻应依次为缺失、100、80，朴素历史查询错误地始终返回 80。连续盘序号从 11 跳到 13 时停止发布，序号 15 的完整快照恢复报价。注入同序号不同内容应使缓存失效。这个合成实验未实现真实多通道协议。[机器结果](../evidence/data-plane.json) · [SQL](../lab/pit.sql)

## E1 订单账本

运行两次 `python3 -m lab.execution`。首次独立事件 11 条，第二次新增 0。订单 A 申报 100 股，撤单确认前累计成 60 股，撤掉余下 40。已成价格成本 0.80 元、费 0.30 元、未成机会成本 2.40 元，合计 3.50 元，按 500 元到达名义计算为 70 bp。对照代码中的同事件 ID 重放与非法状态拒绝。工程练习的回报为合成，不代表交易所协议的完整实现。[首次](../evidence/execution.json) · [续跑](../evidence/execution-replay.json)

## P1 约束组合与对账

运行 `python3 -m lab.portfolio_controls`。四标的 5% 权重网格中共有 375 个预算和单票合规候选，58 个同时满足行业、beta、TE 和换手约束。仅预算/上限的解为 40/10/30/20%，双边换手 40%。加入换手不超过 30% 等约束后，选到 40/10/25/25%，年化 TE 2.61%，目标分值从 24.22 降到 21.92。换手成本在目标中只扣一次，所有预测值为合成输入。

同一脚本独立比较内外部成交文件。X2 本地有重复且价格差 1 分，X3 缺失在本地，X4 缺失在外部。运营需要保留两条独立异常性质和源端证据。系统不自动补记差异。[机器结果](../evidence/portfolio-controls.json)

## M1 期货换月

运行 `python3 -m lab.multi_asset`。两手、每点乘数 10。先做近月 100→103→101，再按远月 107 开新仓，远月盯市到 114。变动损益 60−40+140=160，手续费 12，净损益 148。把 100 与 114 直接相减会得到 280，混入了 6 个点的两合约价差共 120。单日保证金比例与抵押品占用同时受压，触发补入 71.20。现金增加含入金，将现金变化减去补入额后才得到交易净损益。实际结算、抵押品折扣及保证金规则按品种和账户核实。[机器结果](../evidence/multi-asset.json) · [CME 逐日盯市](https://www.cmegroup.com/education/courses/introduction-to-futures/mark-to-market) · [CME 清算风险](https://www.cmegroup.com/clearing/cme-clearing-knowledge-center.html)

## M2 期权压力重估

同一脚本内用欧式 Black–Scholes 加连续股息率模型反解 bid/ask IV。ETF 价格 5.00 下跌 0.30、IV 平移上升 8 个百分点，三腿组合 delta/vega 一阶近似 +4,750.22 元，加 gamma 后 +4,633.66 元，全量重估 +4,976.57 元。加入 gamma 在此次场景中反而使近似误差扩大，原因还可能涉及 vanna、volga 和高阶项。测试用 put-call parity 和反解回归固定口径。此处只有合成报价切片，没有真实波动率曲面或成交。[机器结果](../evidence/multi-asset.json) · [CME Greeks 教材](https://www.cmegroup.com/education/courses/option-greeks/options-the-greeks-options-premium-and-the-greeks)

## M3 做市损益

四笔模拟做市成交，价差捕获 +3.00 元，成交参考中价到收盘中价的方向性变化 −5.80 元，费 0.30，合计 −3.10 元。独立用现金 −498.10 加 100 股按 4.95 估值也得到 −3.10。成交后同一所选时点的带符号总 markout 为 −7.70 元。markout 用于看逆向选择，不能与收盘持仓损益重复加总。[机器结果](../evidence/multi-asset.json)

## V1 利率外汇与基金估值

运行 `python3 -m lab.valuation`。一只 5 年期年付息债券每百面额价格 95.5482，中央差分 DV01 为 0.04327。收益率上行 50 bp，线性损益 −2.1634，全量重估 −2.1331。半年期 EUR/USD 按 USD per EUR、指定两币利率推得理论远期 1.0880。持有 100,000 欧元远期到期时即期 1.10，未扣成本的交割收益为 1,200 美元。案例省略抵押币种、基差及交割风险。

份额实验中，投资损益造成单位净值由 1.00 变为 0.98。再按 0.98 发行 10 万份，净资产增长到 1,078,000，单位净值仍为 0.98。资金流与投资回报不能直接用资产规模差代替。[机器结果](../evidence/valuation.json) · [BIS 外汇市场口径](https://www.bis.org/publications/triennial-central-bank-survey-foreign-exchange-and-over-the-counter-otc-derivatives-markets-2025)

## S1 C++ 价格档基准

```bash
mkdir -p out
c++ -std=c++17 -O3 -Wall -Wextra -Werror benchmarks/price_levels.cpp -o out/price-levels
out/price-levels
```

同一 491,520 次合成更新，对比稠密整数数组和预填充 `std::map`，两个 checksum 都是 60,526,080。运行在 macOS arm64、Apple Clang 17。日志保留批平均每次更新耗时的 p50/p99 和样本数量。这类批统计无法推断单包端到端时延。数组适合紧凑、有上限的价格档域；宽稀疏域、插入/删除和档位遍历需要重新测。练习用相同测量方法反转运行顺序，再把冷启动、稀疏域和输入分布加入报告。[运行记录](../evidence/price-levels.json) · [源码](../benchmarks/price_levels.cpp)
