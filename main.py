"""mini-Scheme 解释器入口。

用法：
  python3 src/main.py file1.scm [file2.scm ...]   按顺序求值文件
  python3 src/main.py                              从标准输入读取

规则（spec.md §2）：
  - 按顺序求值每个顶层表达式
  - 每个求值结果独占一行打印
  - 结果为 None 时不打印（如 display / newline 的结果）
  - 多个文件共享同一个全局环境
"""

from __future__ import annotations

import sys

from tokenizer import tokenize
from parser import parse
from evaluator import evaluate, Pair
from environment import Environment
from stdlib import make_global_env
from printer import scheme_repr


# ──────────────────────────── 创建全局环境 ────────────────────────────

def create_global_environment() -> Environment:
    """创建包含所有内置函数的全局环境。"""
    env = Environment()
    for name, proc in make_global_env().items():
        env.define(name, proc)
    return env


# ──────────────────────────── 求值源代码 ────────────────────────────

def run_source(source: str, env: Environment) -> None:
    """对一段源代码求值所有顶层表达式，打印非 None 的结果。

    流程：源代码 → tokenize → parse → 逐个 evaluate → 打印
    """
    tokens = tokenize(source)
    expressions = parse(tokens)

    for expr in expressions:
        result = evaluate(expr, env)
        # 结果为 None 时不打印（display / newline / 空 if 假分支等）
        if result is not None:
            print(scheme_repr(result))


# ──────────────────────────── 主入口 ────────────────────────────

def main() -> None:
    """命令行入口。

    - 有参数：按顺序读取并求值每个文件
    - 无参数：从标准输入读取
    多个文件共享同一个全局环境。
    """
    env = create_global_environment()

    if len(sys.argv) > 1:
        # 从命令行参数指定的文件中读取
        for filename in sys.argv[1:]:
            with open(filename, 'r', encoding='utf-8') as f:
                source = f.read()
            run_source(source, env)
    else:
        # 无参数时从标准输入读取
        source = sys.stdin.read()
        run_source(source, env)


if __name__ == '__main__':
    main()
