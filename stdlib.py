"""内置函数库：根据 spec.md §5 实现所有内置过程。

分类：
  - 算术：+ - * / modulo quotient expt abs
  - 比较：= < > <= >=
  - 布尔：not
  - 列表：cons car cdr list length append null? pair? list?
  - 谓词：number? boolean? symbol? string? procedure? zero? even? odd? eq? equal?
  - 输出：display newline

每个内置函数接收一个已求值的参数列表 args，返回 Scheme 值。
display / newline 的返回值为 None（不打印）。
"""

from __future__ import annotations

import math
import sys
from typing import Any, Dict

from tokenizer import Symbol, SchemeString
from evaluator import BuiltinProcedure, LambdaProcedure, Pair
from printer import scheme_repr, display_repr


# ──────────────────────────── 算术 ────────────────────────────

def _add(args: list) -> int:
    """(+) → 0；(+ a b ...) → 求和"""
    return sum(args)


def _sub(args: list) -> int:
    """(- a) → 取反；(- a b ...) → a - b - ..."""
    if len(args) == 1:
        return -args[0]
    result = args[0]
    for a in args[1:]:
        result -= a
    return result


def _mul(args: list) -> int:
    """(*) → 1；(* a b ...) → 求积"""
    result = 1
    for a in args:
        result *= a
    return result


def _div(args: list):
    """(/ a) → 倒数（浮点）；(/ a b ...) → 整数商，负数向零截断。

    整数相除用 int(a / b) 实现向零截断（Python // 向负无穷截断）。
    """
    if len(args) == 1:
        # 单参数求倒数，返回浮点
        return 1.0 / args[0]
    result = args[0]
    for a in args[1:]:
        # 向零截断：int() 截断小数部分
        result = int(result / a)
    return result


def _modulo(args: list) -> int:
    """(modulo a b) → a mod b"""
    return args[0] % args[1]


def _quotient(args: list) -> int:
    """(quotient a b) → 整除商，负数向零截断"""
    return int(args[0] / args[1])


def _expt(args: list) -> int:
    """(expt base exp) → base ** exp"""
    return args[0] ** args[1]


def _abs(args: list) -> int:
    """(abs x) → |x|"""
    return abs(args[0])


# ──────────────────────────── 比较（链式） ────────────────────────────

def _make_chain_cmp(op):
    """构造链式比较函数：相邻两两都成立才为真。

    例如 (< 2 3 4) 等价于 (< 2 3) and (< 3 4)。
    """
    def cmp(args: list) -> bool:
        for i in range(len(args) - 1):
            if not op(args[i], args[i + 1]):
                return False
        return True
    return cmp

_eq  = _make_chain_cmp(lambda a, b: a == b)
_lt  = _make_chain_cmp(lambda a, b: a < b)
_gt  = _make_chain_cmp(lambda a, b: a > b)
_le  = _make_chain_cmp(lambda a, b: a <= b)
_ge  = _make_chain_cmp(lambda a, b: a >= b)


# ──────────────────────────── 布尔 ────────────────────────────

def _not(args: list) -> bool:
    """(not x) → #t 当 x 为 #f，否则 #f。

    只有 #f 是假；0、() 等都不是假。
    """
    return args[0] is False


# ──────────────────────────── 列表操作 ────────────────────────────

def _cons(args: list) -> Pair:
    """(cons a b) → 构造点对"""
    return Pair(args[0], args[1])


def _car(args: list) -> Any:
    """(car pair) → 取点对第一项"""
    if not isinstance(args[0], Pair):
        raise TypeError(f"car: 参数不是点对: {args[0]!r}")
    return args[0].first


def _cdr(args: list) -> Any:
    """(cdr pair) → 取点对第二项"""
    if not isinstance(args[0], Pair):
        raise TypeError(f"cdr: 参数不是点对: {args[0]!r}")
    return args[0].second


def _list(args: list) -> Any:
    """(list a b ...) → 打包成真列表（Pair 链）"""
    result = None  # 空表
    for a in reversed(args):
        result = Pair(a, result)
    return result


def _length(args: list) -> int:
    """(length lst) → 列表长度"""
    count = 0
    curr = args[0]
    while isinstance(curr, Pair):
        count += 1
        curr = curr.second
    return count


def _append(args: list) -> Any:
    """(append lst1 lst2 ...) → 拼接列表。

    将多个列表首尾相接。最后一个参数可以不是真列表（成为结果的末尾）。
    """
    if not args:
        return None  # 空表

    # 只有一个参数，直接返回
    if len(args) == 1:
        return args[0]

    # 递归拼接：先把除最后一个以外的列表的元素收集起来，再接到最后一个参数上
    result = args[-1]  # 最后一个参数作为尾部
    for lst in reversed(args[:-1]):
        # 把 lst 的元素从右到左 cons 到 result 上
        elements = []
        curr = lst
        while isinstance(curr, Pair):
            elements.append(curr.first)
            curr = curr.second
        for elem in reversed(elements):
            result = Pair(elem, result)

    return result


def _null_p(args: list) -> bool:
    """(null? x) → 是否空表"""
    return args[0] is None


def _pair_p(args: list) -> bool:
    """(pair? x) → 是否点对（非空）"""
    return isinstance(args[0], Pair)


def _list_p(args: list) -> bool:
    """(list? x) → 是否真列表（Pair 链末端为 None）"""
    curr = args[0]
    while isinstance(curr, Pair):
        curr = curr.second
    return curr is None


# ──────────────────────────── 谓词 ────────────────────────────

def _number_p(args: list) -> bool:
    """(number? x) → 是否数字"""
    return isinstance(args[0], (int, float)) and not isinstance(args[0], bool)


def _boolean_p(args: list) -> bool:
    """(boolean? x) → 是否布尔"""
    return isinstance(args[0], bool)


def _symbol_p(args: list) -> bool:
    """(symbol? x) → 是否符号"""
    return isinstance(args[0], Symbol)


def _string_p(args: list) -> bool:
    """(string? x) → 是否字符串"""
    return isinstance(args[0], SchemeString)


def _procedure_p(args: list) -> bool:
    """(procedure? x) → 是否过程"""
    return isinstance(args[0], (LambdaProcedure, BuiltinProcedure))


def _zero_p(args: list) -> bool:
    """(zero? x) → x == 0"""
    return args[0] == 0


def _even_p(args: list) -> bool:
    """(even? x) → x 是否偶数"""
    return args[0] % 2 == 0


def _odd_p(args: list) -> bool:
    """(odd? x) → x 是否奇数"""
    return args[0] % 2 != 0


def _eq_p(args: list) -> bool:
    """(eq? a b) → 按同一性比较。

    规则（spec.md §5）：
      - 符号、数字、布尔、空表 → 按值比较
      - 点对等复合数据 → 按同一性（is）比较
    """
    a, b = args[0], args[1]

    # 空表：None is None → True，即 (eq? '() '()) → #t
    if a is None and b is None:
        return True

    # 布尔：按值比较
    if isinstance(a, bool) and isinstance(b, bool):
        return a is b  # 只有 True is True / False is False

    # 数字：按值比较（排除 bool，因为 bool 是 int 子类）
    if isinstance(a, (int, float)) and not isinstance(a, bool):
        if isinstance(b, (int, float)) and not isinstance(b, bool):
            return a == b

    # 符号：按值比较
    if isinstance(a, Symbol) and isinstance(b, Symbol):
        return a.name == b.name

    # 字符串：按值比较
    if isinstance(a, SchemeString) and isinstance(b, SchemeString):
        return a.value == b.value

    # 复合数据（点对等）：按同一性比较
    return a is b


def _equal_p(args: list) -> bool:
    """(equal? a b) → 结构相等（逐层递归比较）。

    关键：先比较类型再比较值，避免 Python 的 True == 1 误判。
    """
    return _deep_equal(args[0], args[1])


def _deep_equal(a: Any, b: Any) -> bool:
    """递归结构相等判断。"""
    # 类型不同 → 不相等（避免 True == 1 的误判）
    if type(a) is not type(b):
        # 特例：int 和 float 之间可以比较
        if isinstance(a, (int, float)) and not isinstance(a, bool):
            if isinstance(b, (int, float)) and not isinstance(b, bool):
                return a == b
        return False

    # 空表
    if a is None and b is None:
        return True

    # 布尔
    if isinstance(a, bool):
        return a is b

    # 数字
    if isinstance(a, (int, float)):
        return a == b

    # 符号
    if isinstance(a, Symbol):
        return a.name == b.name

    # 字符串
    if isinstance(a, SchemeString):
        return a.value == b.value

    # 点对：递归比较 first 和 second
    if isinstance(a, Pair):
        return _deep_equal(a.first, b.first) and _deep_equal(a.second, b.second)

    # 内置过程 / Lambda：按同一性
    return a is b


# ──────────────────────────── 输出 ────────────────────────────

def _display(args: list) -> None:
    """(display x) → 打印 x（字符串不带引号），不换行。返回 None。"""
    sys.stdout.write(display_repr(args[0]))
    return None


def _newline(args: list) -> None:
    """(newline) → 输出换行。返回 None。"""
    sys.stdout.write('\n')
    return None


# ──────────────────────────── 注册所有内置函数 ────────────────────────────

def make_global_env() -> Dict[str, Any]:
    """创建全局环境，绑定所有内置函数。

    返回一个字典 {名字: BuiltinProcedure}，供 main.py 构建 Environment 使用。
    """
    stdlib_table = {
        # 算术
        '+':        _add,
        '-':        _sub,
        '*':        _mul,
        '/':        _div,
        'modulo':   _modulo,
        'quotient': _quotient,
        'expt':     _expt,
        'abs':      _abs,
        # 比较
        '=':        _eq,
        '<':        _lt,
        '>':        _gt,
        '<=':       _le,
        '>=':       _ge,
        # 布尔
        'not':      _not,
        # 列表
        'cons':     _cons,
        'car':      _car,
        'cdr':      _cdr,
        'list':     _list,
        'length':   _length,
        'append':   _append,
        'null?':    _null_p,
        'pair?':    _pair_p,
        'list?':    _list_p,
        # 谓词
        'number?':    _number_p,
        'boolean?':   _boolean_p,
        'symbol?':    _symbol_p,
        'string?':    _string_p,
        'procedure?': _procedure_p,
        'zero?':      _zero_p,
        'even?':      _even_p,
        'odd?':       _odd_p,
        'eq?':        _eq_p,
        'equal?':     _equal_p,
        # 输出
        'display':  _display,
        'newline':  _newline,
    }

    env_dict: Dict[str, Any] = {}
    for name, func in stdlib_table.items():
        env_dict[name] = BuiltinProcedure(name, func)

    return env_dict
