# 来源与证据边界

核对日期为 2026-11-22。岗位要求与公司公开介绍来自机构发布。技术选型、职责映射和案例均为课程分析，样本也不代表全行业招聘频率。

## 岗位

- 九坤。附件《九坤智能化工程师》用于端到端、AI 协作、交易支持与 React/TypeScript 加分项的映射。附件没有进入 Git。公开技术职责以九坤在华中科技大学的宣讲材料为准。[公司介绍](https://www.ubiquant.com/website/about) · [招聘官网](https://www.ubiquant.com/website/career) · [宣讲发布页](https://job.hust.edu.cn/extxjh/581791873703758.do)
- 中欧基金。公开量化系统工程师职位，用于对照低延迟、列式存储、流式消息和云原生。[职位原文](https://zofund.zhiye.com/socialxq?jobId=621074149)
- 明汯投资。招聘主页所列研究基础设施、训练推理、K8s 和缓存要求。[机构招聘页](https://join.mhfunds.com/index)
- Jane Street。研究工作介绍涉及市场数据、冲击与 OCaml。[Quantitative Research](https://www.janestreet.com/quantitative-research/)
- Citadel Securities。交易和研究数据平台的 kdb+/q 工程侧重点。[Kdb+/Q Engineer](https://www.citadelsecurities.com/careers/details/kdb-q-engineer/)

## 市场与交易

- [上证所 Level-2 产品说明](https://www.sseinfo.com/services/assortment/level2/) · [行情历史数据](https://www.sseinfo.com/services/assortment/historical/)
- [上交所程序化交易管理细则](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20250612_10781696.shtml)
- [上交所 ETF 申赎与折溢价教学](https://etf.sse.com.cn/fund/learning/strategy/c/5704303.shtml) · [ETF IOPV 风险实例](https://www.sse.com.cn/disclosure/fund/announcement/c/new/2026-03-18/515750_20260318_V7NE.pdf)
- [中金所沪深300股指期货业务入口](https://www.cffex.com.cn/hs300/) · [合约细则存档](https://www.yhqh.com.cn/upload/cn/uploadfile/2015/0731/20150731085738148.pdf)
- [上交所沪深300ETF期权条款](https://www.sse.com.cn/assortment/options/contract/c/c_20230303_5717360.shtml) · [除权后合约调整公告例](https://www.sse.com.cn/assortment/options/disclo/update/c/c_20250617_10782153.shtml)
- [南方基金 510500 份额折算停牌公告](https://epaper.stcn.com/paper/zqsb/html/2015-04/07/content_671814.htm)
- [FIX Trading Community 的交易消息语义](https://archive.fixtrading.org/online-specification/business-area-trade/)

## 技术

- 存储和查询。[Apache Kafka 顺序与投递语义](https://kafka.apache.org/41/design/design/) · [ClickHouse 列存](https://clickhouse.com/resources/engineering/what-is-columnar-storage) · [Redis 持久化](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/) · [MySQL InnoDB 事务](https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-model.html) · [时序 ASOF 查询](https://questdb.com/docs/query/sql/asof-join/)
- 性能和可观测性。[Go 诊断与 pprof](https://go.dev/doc/diagnostics) · [OpenTelemetry 信号](https://opentelemetry.io/docs/concepts/signals/) · [Kubernetes 探针](https://kubernetes.io/docs/concepts/workloads/pods/probes/)
- ML 工具。[scikit-learn 时间切分](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) · [PyTorch DDP](https://docs.pytorch.org/docs/stable/generated/torch.nn.parallel.DistributedDataParallel.html) · [PyTorch Profiler](https://docs.pytorch.org/docs/stable/profiler.html)

## 研究论文

- Moskowitz、Ooi、Pedersen（2012），时间序列动量，研究数据为不同资产类别的流动性期货。[原论文](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf)
- Cont、Kukanov、Stoikov，订单簿事件与价格冲击，研究数据来自纽约证券交易所行情记录。[作者论文](https://arxiv.org/abs/1011.6402)
- Almgren、Chriss，最优执行与冲击风险的权衡。[原论文存档](https://www.smallake.kr/wp-content/uploads/2016/03/optliq.pdf)

## 实验数据

腾讯提供冻结的 ETF 前复权日线与上证综指日期代理。东方财富只独立抽查沪深 300 ETF 的 6 个交易日，开高低收一致。原始研究中的三只标的是事后选定，日线来源和复权口径决定可做的检验范围。[请求与哈希](../evidence/input-provenance.json)

L2 盘口、PIT 修订和 OMS 的输入是自制夹具。按序号恢复、按可知时点查询和事件幂等属于工程验证。它们没有估计任何真实队列成交率或策略收益。
