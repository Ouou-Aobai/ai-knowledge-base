"""
workflows/nodes.py — 向后兼容的 re-export 入口

V3 的 6 个节点函数已经拆成独立文件（一个 Agent 一个文件）：

    workflows/collector.py     → collect_node    (数据采集)
    workflows/analyzer.py      → analyze_node    (内容分析)
    workflows/reviewer.py      → review_node     (质量审核，5 维加权)
    workflows/reviser.py       → revise_node     (定向修改)
    workflows/organizer.py     → organize_node   (整理入库，正常终点)
    workflows/human_flag.py    → human_flag_node (人工介入，异常终点)

本文件保留只是为了向后兼容——老代码可能用 `from workflows.nodes import review_node`，
新代码建议直接 import 对应文件（例如 `from workflows.reviewer import review_node`），
文件名和 Agent 名一对一，一眼能定位。
"""

from workflows.analyzer import analyze_node
from workflows.collector import collect_node
from workflows.human_flag import human_flag_node
from workflows.organizer import organize_node
from workflows.reviewer import REVIEWER_PASS_THRESHOLD, REVIEWER_WEIGHTS, review_node
from workflows.reviser import revise_node

__all__ = [
    "collect_node",
    "analyze_node",
    "review_node",
    "revise_node",
    "organize_node",
    "human_flag_node",
    "REVIEWER_WEIGHTS",
    "REVIEWER_PASS_THRESHOLD",
]
