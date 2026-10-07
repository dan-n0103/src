"""求值器：实现 evaluate(expr, env) 和 apply(proc, args) 互相调用。

严格按 spec.md §4 处理特殊形式：
  quote, if, cond, define, lambda, let, begin, and, or

关键语义：
  - and/or 短路求值
  - let 并行绑定（绑定之间互不可见）
  - lambda 闭包（捕获定义时环境）
"""

from __future__ import annotations

from typing import Any, List

from tokenizer import Symbol, SchemeString
from environment import Environment


# ──────────────────────────── 过程类型 ────────────────────────────

class LambdaProcedure:
    """用户自定义过程（闭包）。

    捕获定义时的环境，调用时在其基础上扩展参数绑定。
    """
    __slots__ = ('params', 'body', 'env')

    def __init__(self, params: list, body: list, env: Environment) -> None:
        # params: Symbol 列表（形参名）
        # body:   表达式列表（函数体，可能有多个表达式，按 begin 语义执行）
        # env:    闭包捕获的定义时环境
        self.params = params
        self.body = body
        self.env = env


class BuiltinProcedure:
    """内置过程：包装一个 Python 函数。"""
    __slots__ = ('name', 'func')

    def __init__(self, name: str, func) -> None:
        self.name = name
        self.func = func


# ──────────────────────────── 点对表示 ────────────────────────────

class Pair:
    """点对（cons cell），列表的基础构件。

    (1 2 3) 实际存储为 Pair(1, Pair(2, Pair(3, NIL)))。
    用 Python None 代表空表 '() 。
    """
    __slots__ = ('first', 'second')

    def __init__(self, first: Any, second: Any) -> None:
        self.first = first
        self.second = second


# NIL 常量：空表。用 Python None 表示，Pair 的 second 为 None 表示列表结尾。
# 这样 (null? '()) 就是判断值是否为 None。

# ──────────────────────────── 辅助判断 ────────────────────────────

def is_true(val: Any) -> bool:
    """Scheme 真值判断：只有 #f (即 Python False) 为假，其余均为真。

    注意：0、None（空表）、SchemeString("") 都是真。
    """
    return val is not False


def scheme_symbol(name: str) -> Symbol:
    """快速构造同名 Symbol。"""
    return Symbol(name)


# ──────────────────────────── quote 数据转换 ────────────────────────────

def quote_convert(expr: Any) -> Any:
    """将 AST 中的 quote 数据转换为运行时值。

    AST 中的列表 (quote (1 2 3)) 里的 (1 2 3) 是 Python list，
    需要转换为 Pair 链才能与 cons/car/cdr 一致。
    整数、布尔、Symbol、SchemeString 直接返回。
    """
    if isinstance(expr, list):
        # 列表 → 从右向左折叠为 Pair 链，末尾接 None（空表）
        result = None
        for elem in reversed(expr):
            result = Pair(quote_convert(elem), result)
        return result
    # 原子类型直接返回
    return expr


# ──────────────────────────── 核心：evaluate ────────────────────────────

def evaluate(expr: Any, env: Environment) -> Any:
    """求值表达式 expr 在环境 env 下的值。

    分派规则：
      1. 自求值类型（int, float, bool, SchemeString）→ 直接返回
      2. Symbol → 环境查找变量
      3. list（S-表达式）→ 根据第一个元素分派：
         - 特殊形式（quote, if, cond, define, lambda, let, begin, and, or）
         - 普通函数调用：先求值操作符和全部实参，再 apply
    """
    # ── 自求值类型 ──
    if isinstance(expr, (int, float, bool, SchemeString)):
        return expr

    # ── 空表（quote 出来的空列表 [] ） ──
    if isinstance(expr, list) and len(expr) == 0:
        return None  # 空表用 None 表示

    # ── Symbol：变量引用 ──
    if isinstance(expr, Symbol):
        return env.lookup(expr.name)

    # ── S-表达式（列表） ──
    if isinstance(expr, list):
        first = expr[0]

        # ── 特殊形式分派 ──
        if isinstance(first, Symbol):
            name = first.name

            # quote —— 原样返回，不求值
            if name == 'quote':
                return quote_convert(expr[1])

            # if —— 只走一个分支
            if name == 'if':
                test_val = evaluate(expr[1], env)
                if is_true(test_val):
                    return evaluate(expr[2], env)
                else:
                    # 有假分支就求值假分支，否则返回 None
                    if len(expr) > 3:
                        return evaluate(expr[3], env)
                    return None

            # cond —— 多分支选择
            if name == 'cond':
                return _eval_cond(expr[1:], env)

            # define —— 定义名字
            if name == 'define':
                return _eval_define(expr, env)

            # lambda —— 制造闭包
            if name == 'lambda':
                params = expr[1]  # 参数列表（Symbol 列表）
                body = expr[2:]   # 函数体（可能有多个表达式）
                return LambdaProcedure(params, body, env)

            # let —— 局部变量（并行绑定）
            if name == 'let':
                return _eval_let(expr, env)

            # begin —— 顺序执行
            if name == 'begin':
                return _eval_begin(expr[1:], env)

            # and —— 短路求值
            if name == 'and':
                return _eval_and(expr[1:], env)

            # or —— 短路求值
            if name == 'or':
                return _eval_or(expr[1:], env)

        # ── 普通函数调用：先求值操作符，再求值全部实参，最后 apply ──
        operator = evaluate(first, env)
        operands = [evaluate(arg, env) for arg in expr[1:]]
        return apply(operator, operands)

    # 不应到达此处
    raise TypeError(f"无法求值的表达式: {expr!r}")


# ──────────────────────────── 核心：apply ────────────────────────────

def apply(proc: Any, args: list) -> Any:
    """将过程 proc 应用于已求值的实参列表 args。

    分派：
      - LambdaProcedure → 在闭包环境上扩展参数绑定，按 begin 语义求值函数体
      - BuiltinProcedure → 直接调用 Python 函数
    """
    if isinstance(proc, LambdaProcedure):
        # 闭包调用：在捕获的环境上扩展参数绑定
        call_env = proc.env.extend(proc.params, args)
        # 函数体按 begin 语义依次求值，返回最后一个
        return _eval_begin(proc.body, call_env)

    if isinstance(proc, BuiltinProcedure):
        return proc.func(args)

    raise TypeError(f"无法调用非过程对象: {proc!r}")


# ──────────────────────────── 特殊形式辅助实现 ────────────────────────────

def _eval_define(expr: list, env: Environment) -> Any:
    """处理 (define 名 表达式) 和 (define (函数名 参数...) 体...)。

    第二种写法等价于 (define 函数名 (lambda (参数...) 体...))。
    返回被定义的符号名（Symbol），顶层打印时用。
    """
    target = expr[1]

    if isinstance(target, Symbol):
        # (define 名 表达式)
        value = evaluate(expr[2], env)
        env.define(target.name, value)
        return target  # 返回符号名

    if isinstance(target, list):
        # (define (函数名 参数...) 体...)
        func_name = target[0]       # Symbol
        params = target[1:]         # 参数列表
        body = expr[2:]             # 函数体
        # 等价于 (define 函数名 (lambda (参数...) 体...))
        proc = LambdaProcedure(params, body, env)
        name_str = func_name.name if isinstance(func_name, Symbol) else str(func_name)
        env.define(name_str, proc)
        return func_name  # 返回符号名

    raise SyntaxError(f"define 的目标格式错误: {target!r}")


def _eval_cond(clauses: list, env: Environment) -> Any:
    """处理 (cond (测试1 表达式...) (测试2 表达式...) ... (else 表达式...))。

    从上到下依次求值测试，遇到第一个不为 #f 的子句：
      - 子句有表达式 → 按 begin 语义依次求值，返回最后一个
      - 子句无表达式 → 返回测试值本身
    else 子句恒真。全部不匹配返回 None。
    """
    for clause in clauses:
        if not isinstance(clause, list) or len(clause) == 0:
            raise SyntaxError(f"cond 子句格式错误: {clause!r}")

        test = clause[0]

        # else 子句作为兜底
        if isinstance(test, Symbol) and test.name == 'else':
            if len(clause) == 1:
                return True  # (else) 无表达式，返回 #t
            return _eval_begin(clause[1:], env)

        # 求值测试
        test_val = evaluate(test, env)

        if is_true(test_val):
            if len(clause) == 1:
                # 无表达式，返回测试值本身
                return test_val
            # 有表达式，按 begin 语义依次求值
            return _eval_begin(clause[1:], env)

    # 全部不匹配
    return None


def _eval_let(expr: list, env: Environment) -> Any:
    """处理 (let ((名 表达式)...) 体...)。

    并行绑定：先在外层环境求值所有绑定表达式，再在新环境中绑定。
    绑定之间互不可见（与 let* 的串行绑定不同）。
    """
    bindings = expr[1]   # 绑定列表: [[名, 表达式], ...]
    body = expr[2:]      # 函数体

    # 并行求值：先在外层环境求值所有表达式
    names = []
    values = []
    for binding in bindings:
        if not isinstance(binding, list) or len(binding) != 2:
            raise SyntaxError(f"let 绑定格式错误: {binding!r}")
        name_sym = binding[0]
        val = evaluate(binding[1], env)
        name_str = name_sym.name if isinstance(name_sym, Symbol) else str(name_sym)
        names.append(name_str)
        values.append(val)

    # 创建新环境，绑定所有变量
    new_env = Environment(parent=env)
    for name, val in zip(names, values):
        new_env.define(name, val)

    # 按 begin 语义求值函数体
    return _eval_begin(body, new_env)


def _eval_begin(exprs: list, env: Environment) -> Any:
    """处理 (begin e1 e2 ...)：从左到右依次求值，返回最后一个。

    空序列返回 None（不应出现在合法代码中）。
    """
    result = None
    for e in exprs:
        result = evaluate(e, env)
    return result


def _eval_and(exprs: list, env: Environment) -> Any:
    """处理 (and e1 e2 ...)：短路求值。

    遇到第一个 #f 立刻返回 #f；全部为真则返回最后一个的值。
    (and) → #t。
    """
    if not exprs:
        return True  # (and) → #t

    for e in exprs:
        val = evaluate(e, env)
        if not is_true(val):
            return False  # 短路：立刻返回 #f，后面的不执行

    return val  # 全为真，返回最后一个的值


def _eval_or(exprs: list, env: Environment) -> Any:
    """处理 (or e1 e2 ...)：短路求值。

    遇到第一个不为 #f 的值立刻返回它；全为 #f 则返回 #f。
    (or) → #f。
    """
    if not exprs:
        return False  # (or) → #f

    for e in exprs:
        val = evaluate(e, env)
        if is_true(val):
            return val  # 短路：立刻返回该值，后面的不执行

    return False  # 全为 #f，返回 #f
