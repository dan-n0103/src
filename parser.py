"""语法分析器：将 Token 列表转换为 AST（嵌套 Python 列表）。

AST 节点约定：
  - int           → 整数字面量
  - bool          → 布尔字面量
  - Symbol        → 符号（变量 / 操作符 / 特殊形式名）
  - SchemeString  → 字符串字面量
  - list          → S-表达式（括号表达式），如 (+ 1 2) 表示为
                      [Symbol('+'), 1, 2]

引用简写 'x 在解析时展开为 (quote x)，即 [Symbol('quote'), x]。
"""

from __future__ import annotations

from typing import List

from tokenizer import Token, TokenType, Symbol, SchemeString


# ──────────────────────────── 公开接口 ────────────────────────────

def parse(tokens: List[Token]) -> list:
    """将 Token 列表解析为顶层表达式列表。

    返回值：一个 Python list，每个元素是一个 AST 节点。
    例如源码 "(+ 1 2) 42" 解析为 [[Symbol('+'), 1, 2], 42]。
    """
    expressions: list = []
    pos = 0
    n = len(tokens)

    while pos < n:
        expr, pos = _parse_expr(tokens, pos, n)
        expressions.append(expr)

    return expressions


# ──────────────────────────── 内部递归下降解析 ────────────────────────────

def _parse_expr(tokens: List[Token], pos: int, n: int) -> tuple[object, int]:
    """解析一个表达式，返回 (AST 节点, 新位置)。

    分派规则：
      QUOTE  → 读取下一个表达式 expr，返回 [Symbol('quote'), expr]
      LPAREN → 解析括号列表直到遇到 RPAREN
      RPAREN → 语法错误（意外的右括号）
      其它   → 原子（直接取 Token.value）
    """
    if pos >= n:
        raise SyntaxError("意外的输入结束，期望一个表达式")

    tok = tokens[pos]

    # ── 引用简写 'x → (quote x) ──
    if tok.type == TokenType.QUOTE:
        target, pos = _parse_expr(tokens, pos + 1, n)
        return [Symbol('quote'), target], pos

    # ── 括号表达式 (e1 e2 ...) ──
    if tok.type == TokenType.LPAREN:
        return _parse_list(tokens, pos + 1, n)

    # ── 意外的右括号 ──
    if tok.type == TokenType.RPAREN:
        raise SyntaxError(f"位置 {tok.pos}: 意外的 ')'")

    # ── 原子：整数 / 布尔 / 符号 / 字符串 ──
    return tok.value, pos + 1


def _parse_list(tokens: List[Token], pos: int, n: int) -> tuple[list, int]:
    """解析括号内的内容，直到遇到 RPAREN。

    调用时 pos 已经跳过了 LPAREN。
    返回 (元素列表, RPAREN 后一位置)。

    处理点对记法：若列表中出现 '.' 符号（如 (1 . 2)），
    读取 '.' 后的一个表达式作为 cdr，构造点对。
    """
    elements: list = []

    while pos < n and tokens[pos].type != TokenType.RPAREN:
        # 检查点对记法：当前 token 是符号 '.'
        if (tokens[pos].type == TokenType.SYMBOL
                and tokens[pos].value == Symbol('.')):
            # (a b . c) → elements 已有 [a, b]，现在读取 c
            pos += 1  # 跳过 '.'
            if not elements:
                raise SyntaxError(f"位置 {tokens[pos - 1].pos}: '.' 前没有元素")
            cdr, pos = _parse_expr(tokens, pos, n)
            if pos >= n or tokens[pos].type != TokenType.RPAREN:
                raise SyntaxError("点对记法 '.' 后只能有一个表达式，且必须紧跟 ')'")
            # 把点对表示为嵌套 cons：逐步从右向左折叠
            # (a b . c) → [Symbol('cons'), a, [Symbol('cons'), b, c]]
            # 但我们先用特殊标记让求值器处理；这里直接构造
            # 为求值器方便，我们返回一个 DottedList 标记
            return _build_dotted_list(elements, cdr), pos + 1

        expr, pos = _parse_expr(tokens, pos, n)
        elements.append(expr)

    if pos >= n:
        raise SyntaxError("括号未闭合，缺少 ')'")

    # pos 指向 RPAREN，跳过它
    return elements, pos + 1


def _build_dotted_list(elements: list, cdr: object) -> list:
    """将 (a b . c) 折叠为 [cons, a, [cons, b, c]] 形式的 AST。

    这样求值器只需正常求值即可得到点对链。
    """
    result = cdr
    for elem in reversed(elements):
        result = [Symbol('cons'), elem, result]
    return result
