默认研究使用 `tencent_snapshot.json` 和 `eastmoney_510300_20251224_20251231.json`。这一目录在本地交付包内有固定快照，Git 历史保存代码、抽样请求说明、哈希和计算结果。行情快照单独管理。

重新下载腾讯快照时运行 `python3 baseline/fetch_snapshot.py baseline/data/tencent_snapshot.json`。前复权基准会变化，重新抓取的数据可能无法复现旧数字。东方财富的原请求和原快照哈希见 [研究证据](../../evidence/input-provenance.json)。拉取跨源数据时应确保两家复权口径可比较。
