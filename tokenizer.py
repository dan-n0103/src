"""词法分析器：将源代码文本转换为 Token 列表。

支持（对应 spec.md §3）：
  - 注释    ; 到行尾
  - 整数    42, -7, 0
  - 布尔    #t, #f
  - 符号    foo, x1, +, <=, null? …
  - 字符串  "hello"（支持 \\n \\t \\" \\\\ 转义）
  - 引用简写 '
  - 括号    ( )
"""

from __future__ import annotations

from enum import Enum, auto
from typing import List, NamedTuple


# ──────────────────────────── Token 类型与结构 ────────────────────────────

class TokenType(Enum):
    INT    = auto()   # 整数字面量
    BOOL   = auto()   # #t / #f
    SYMBOL = auto()   # 符号（变量名 / 操作符）
    STRING = auto()   # 字符串字面量
    QUOTE  = auto()   # ' 引用简写
    LPAREN = auto()   # (
    RPAREN = auto()   # )


class Token(NamedTuple):
    """一个词法单元。value 的类型取决于 type：
      INT    → int
      BOOL   → bool
      SYMBOL → Symbol
      STRING → SchemeString
      其余   → str（字面文本）
    """
    type: TokenType
    value: object
    pos: int          # 在源代码中的起始位置（用于报错）


# ──────────────────────────── Scheme 专用包装类型 ────────────────────────────

class Symbol:
    """Scheme 符号，与 Python str 区分，保证 eq? / equal? 语义正确。"""
    __slots__ = ('name',)

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Symbol) and self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)


class SchemeString:
    """Scheme 字符串，与 Python str 和 Symbol 区分。"""
    __slots__ = ('value',)

    def __init__(self, value: str) -> None:
        self.value = value

    def __repr__(self) -> str:
        return f'"{self.value}"'

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SchemeString) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)


# ──────────────────────────── 核心词法分析 ────────────────────────────

# 原子的终止字符集：遇到这些字符就停止读取当前原子
_DELIMITERS = frozenset(' \t\n\r()";\'')


def tokenize(source: str) -> List[Token]:
    """将源代码字符串扫描为 Token 列表。

    算法：逐字符扫描，根据首字符分派到对应子程序。
    - 空白   → 跳过
    - ;     → 跳过直到行尾
    - ( )   → 生成对应括号 Token
    - '     → 生成 QUOTE Token
    - "     → 读取字符串字面量（处理转义）
    - #     → 读取布尔 #t / #f
    - 其它  → 读取原子（连续非定界符字符），再分类为整数或符号
    """
    tokens: List[Token] = []
    i = 0
    n = len(source)

    while i < n:
        c = source[i]

        # ── 空白 ──
        if c.isspace():
            i += 1
            continue

        # ── 注释：; 到行尾 ──
        if c == ';':
            i += 1
            while i < n and source[i] != '\n':
                i += 1
            continue

        # ── 左括号 ──
        if c == '(':
            tokens.append(Token(TokenType.LPAREN, '(', i))
            i += 1
            continue

        # ── 右括号 ──
        if c == ')':
            tokens.append(Token(TokenType.RPAREN, ')', i))
            i += 1
            continue

        # ── 引用简写 ' ──
        if c == "'":
            tokens.append(Token(TokenType.QUOTE, "'", i))
            i += 1
            continue

        # ── 字符串字面量 ──
        if c == '"':
            value, i = _read_string(source, i, n)
            tokens.append(Token(TokenType.STRING, SchemeString(value), i))
            continue

        # ── 布尔 #t / #f ──
        if c == '#':
            if i + 1 < n and source[i + 1] in ('t', 'f'):
                value = (source[i + 1] == 't')
                tokens.append(Token(TokenType.BOOL, value, i))
                i += 2
                continue
            raise SyntaxError(f"位置 {i}: 未知的 # 语法")

        # ── 原子：整数或符号 ──
        start = i
        while i < n and source[i] not in _DELIMITERS:
            i += 1
        word = source[start:i]
        if not word:
            # 不应该到达这里，但做防御性处理
            raise SyntaxError(f"位置 {start}: 无法识别的字符 {source[start]!r}")

        if _is_integer(word):
            tokens.append(Token(TokenType.INT, int(word), start))
        else:
            tokens.append(Token(TokenType.SYMBOL, Symbol(word), start))

    return tokens


# ──────────────────────────── 辅助函数 ────────────────────────────

def _is_integer(word: str) -> bool:
    """判断一个词是否为整数字面量。

    规则：
      - 全部为数字        → 整数（如 42, 0, 007）
      - '-' 后跟数字      → 负整数（如 -7, -42）
      - 其它              → 不是整数（如 -, +, foo, 1+2）
    """
    if not word:
        return False
    if word[0] == '-' and len(word) > 1:
        return word[1:].isdigit()
    return word.isdigit()


def _read_string(source: str, start: int, n: int) -> tuple[str, int]:
    """从位置 start（指向开头 "）读取字符串字面量。

    处理的转义序列：\\n → 换行, \\t → 制表符, \\" → 双引号, \\\\\\\\ → 反斜杠。
    返回 (字符串内容, 闭引号后一位置)。
    """
    i = start + 1   # 跳过开头的 "
    chars: list[str] = []

    while i < n:
        c = source[i]
        if c == '"':
            return ''.join(chars), i + 1
        if c == '\\':
            i += 1
            if i >= n:
                raise SyntaxError(f"位置 {start}: 字符串未终止，转义序列不完整")
            esc = source[i]
            if   esc == 'n':  chars.append('\n')
            elif esc == 't':  chars.append('\t')
            elif esc == '"':  chars.append('"')
            elif esc == '\\': chars.append('\\')
            else:             chars.append(esc)   # 其它转义原样保留
        else:
            chars.append(c)
        i += 1

    raise SyntaxError(f"位置 {start}: 字符串未终止，缺少闭引号")
