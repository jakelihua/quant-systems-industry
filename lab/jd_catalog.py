"""Validate and render the versioned public-job evidence register."""
import argparse
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = {
    "QR": "量化研究", "ML": "金融机器学习", "QD": "量化开发", "DATA": "数据科学与行情数据",
    "PORT": "组合管理与投资实施", "INDEX": "指数与ETF", "TRADE": "量化交易与执行",
    "MICRO": "高频微观结构与做市", "FICC": "期货、利率、信用与外汇", "DERIV": "衍生品定价与波动率",
    "RISK": "投资、市场与模型风险", "SYS": "低延迟系统与交易基础设施",
    "HW": "FPGA与硬件", "OPS": "生产工程与SRE", "POST": "交易运营、基金核算与清算后台",
    "CLEAR": "交易所清算与流动性风险", "AI": "智能化与AI应用", "MLOPS": "研究平台与ML基础设施",
    "COMP": "合规、监控与控制", "UI": "全栈界面与量化数据产品", "PROD": "ETF及量化产品运营",
}


def load_register(path):
    sources, records, seen = {}, [], set()
    source = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            source, firm, group, provenance, status, url = line[1:].split("|")
            if source in sources or not url.startswith("https://"):
                raise ValueError(f"Invalid source: {source}")
            sources[source] = (firm, group, provenance, status, url)
        else:
            kind, title, family, summary = line.split("|")
            key = (source, title)
            if kind not in ("JD", "方向", "线索") or source is None or key in seen or family not in FAMILIES:
                raise ValueError(f"Invalid or duplicate record: {line}")
            seen.add(key)
            records.append((source, kind, title, family, summary))
    return sources, records


def render(sources, records):
    organs = {s[0] for s in sources.values()}
    counts = Counter(kind for _, kind, *_ in records)
    by_family = Counter(family for _, kind, _, family, _ in records if kind != "线索")
    text = ["# 跨机构量化岗位证据目录", "",
            f"2026-11-22，检索并登记 **{len(organs)} 家机构**与 **{len(sources)} 个来源入口**。",
            f"可核对 **{counts['JD']} 条具名岗位**、**{counts['方向']} 条岗位方向**，另列 {counts['线索']} 条证据待补线索。"
            "具名岗位可以来自校招综合公示、可读的机构摘要或历史岗位样本。具体招聘状态以机构原页为准。",
            "",
            "范围按机构类型和岗位族扩展。重复级别、相同公司多地同岗及纯通用 HR/行政等岗位不作为量化课程的独立技术岗位。"
            "未公开、登录可见和已下架 JD 无法做全量盘点。跨机构数字不可解释为招聘占比。",
            "",
            "原文证据见每个模块链接，下面的要点是摘要。课程对技术的解释和实践入口见 [岗位族课程地图](../docs/08-role-curriculum.md)。",
            "", "| 岗位族 | 证据条数 |", "|---|---:|"]
    text += [f"| {family} {label} | {by_family[family]} |" for family, label in FAMILIES.items()]
    for firm in dict.fromkeys(s[0] for s in sources.values()):
        text += ["", f"## {firm}", "",
                 "| 证据类型 | 岗位/方向 | 岗位族 | 公开证据摘要 | 来源 |", "|---|---|---|---|---|"]
        for source, kind, title, family, summary in records:
            org, group, provenance, status, url = sources[source]
            if org == firm:
                text.append(f"| {kind} | {title} | {family} | {summary} | [{provenance}，{status}]({url}) |")
    text += ["", "生成方式为 `python3 -m lab.jd_catalog`。源表中可按机构、岗位族、证据类型进行查询。", ""]
    return "\n".join(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "catalog/jd-catalog.md")
    args = parser.parse_args()
    sources, records = load_register(ROOT / "catalog/jd-register.txt")
    args.output.write_text(render(sources, records), encoding="utf-8")
    print(len({s[0] for s in sources.values()}), "organizations", len(sources), "sources",
          dict(Counter(kind for _, kind, *_ in records)))


if __name__ == "__main__":
    main()
