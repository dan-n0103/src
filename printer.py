"""值的打印：根据 spec.md §8 将 Scheme 值转为字符串。

规则：
  - 整数      → 42
  - 浮点      → 0.5
  - 布尔      → #t / #f
  - 符号      → foo
  - 字符串    → "hello"（带引号；换行/制表符打印为 \n \t 转义形式）
  - 真列表    → (1 2 3)
  - 点对      → (1 . 2)
  - 空表      → ()
  - 过程      → #<procedure>

提供两个函数：
  - scheme_repr(val)   → 正规打印（字符串带引号，转义可见）
  - display_repr(val)  → display 打印（字符串不带引号，转义已展开）
"""

from __future__ import annotations

from typing import Any

from tokenizer import Symbol, SchemeString
from evaluator import Pair, LambdaProcedure, BuiltinProcedure


# ──────────────────────────── 正规打印 ────────────────────────────

def scheme_repr(val: Any) -> str:
    """将 Scheme 值转为可读字符串（字符串带引号，转义可见）。"""

    # 空表
    if val is None:
        return "()"

    # 布尔（必须在 int 之前判断，因为 bool 是 int 的子类）
    if isinstance(val, bool):
        return "#t" if val else "#f"

    # 整数
    if isinstance(val, int):
        return str(val)

    # 浮点
    if isinstance(val, float):
        return str(val)

    # 符号
    if isinstance(val, Symbol):
        return val.name

    # 字符串（带引号，内部转义字符打印为 \n \t 等转义形式）
    if isinstance(val, SchemeString):
        return _string_repr(val.value)

    # 点对 / 列表
    if isinstance(val, Pair):
        return _pair_repr(val)

    # 过程
    if isinstance(val, (LambdaProcedure, BuiltinProcedure)):
        return "#<procedure>"

    # 兜底
    return str(val)


# ──────────────────────────── display 打印 ────────────────────────────

def display_repr(val: Any) -> str:
    """将 Scheme 值转为 display 字符串（字符串不带引号，转义已展开）。

    与 scheme_repr 的唯一区别：字符串不带引号，且转义序列已展开为实际字符。
    其余类型与 scheme_repr 相同。
    """

    # 空表
    if val is None:
        return "()"

    # 布尔
    if isinstance(val, bool):
        return "#t" if val else "#f"

    # 整数
    if isinstance(val, int):
        return str(val)

    # 浮点
    if isinstance(val, float):
        return str(val)

    # 符号
    if isinstance(val, Symbol):
        return val.name

    # 字符串（不带引号，转义已展开——直接输出原始内容）
    if isinstance(val, SchemeString):
        return val.value

    # 点对 / 列表
    if isinstance(val, Pair):
        return _pair_repr(val, display=True)

    # 过程
    if isinstance(val, (LambdaProcedure, BuiltinProcedure)):
        return "#<procedure>"

    # 兜底
    return str(val)


# ──────────────────────────── 辅助函数 ────────────────────────────

def _string_repr(s: str) -> str:
    """将字符串内容转为带引号的转义表示。

    例如："hello\nworld" → "\"hello\\nworld\""
    换行符 → \\n，制表符 → \\t，双引号 → \\"，反斜杠 → \\\\
    """
    escaped = []
    for ch in s:
        if   ch == '\n':  escaped.append('\\n')
        elif ch == '\t':  escaped.append('\\t')
        elif ch == '"':   escaped.append('\\"')
        elif ch == '\\':  escaped.append('\\\\')
        else:             escaped.append(ch)
    return '"' + ''.join(escaped) + '"'


def _pair_repr(pair: Pair, display: bool = False) -> str:
    """将点对转为字符串表示。

    真列表 (Pair 链末端为 None)：(1 2 3)
    非真列表（末端不是 None）：(1 2 . 3)
    """
    parts = []
    curr = pair

    # 沿 Pair 链向右遍历，收集 first
    while isinstance(curr, Pair):
        parts.append(scheme_repr(curr.first) if not display else display_repr(curr.first))
        curr = curr.second

    # curr 现在是链的末端
    if curr is None:
        # 真列表：末端是空表 → (a b c)
        return "(" + " ".join(parts) + ")"
    else:
        # 非真列表：末端不是空表 → (a b . tail)
        tail_str = scheme_repr(curr) if not display else display_repr(curr)
        return "(" + " ".join(parts) + " . " + tail_str + ")"
