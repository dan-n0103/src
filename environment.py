"""环境类：实现词法作用域。

每个环境包含一个变量字典和指向外层环境的指针。
变量查找时先在当前层找，找不到再递归向上查找（词法作用域）。
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class Environment:
    """词法作用域环境。

    属性：
        bindings: 当前层的变量绑定（名字 → 值）
        parent:   指向外层环境的指针，None 表示顶层
    """

    __slots__ = ('bindings', 'parent')

    def __init__(self, parent: Optional[Environment] = None) -> None:
        self.bindings: Dict[str, Any] = {}
        self.parent: Optional[Environment] = parent

    def lookup(self, name: str) -> Any:
        """从当前环境向外层逐层查找变量 name 的值。

        找不到时抛出 NameError。
        """
        if name in self.bindings:
            return self.bindings[name]
        if self.parent is not None:
            return self.parent.lookup(name)
        raise NameError(f"未定义的变量: {name}")

    def define(self, name: str, value: Any) -> None:
        """在当前层绑定变量 name 的值为 value。"""
        self.bindings[name] = value

    def set(self, name: str, value: Any) -> None:
        """修改已有变量的值（在定义处修改，不是当前层新建）。

        用于 set! 等赋值操作（本解释器暂不实现，预留接口）。
        """
        if name in self.bindings:
            self.bindings[name] = value
            return
        if self.parent is not None:
            self.parent.set(name, value)
            return
        raise NameError(f"未定义的变量: {name}")

    def extend(self, params: list, args: list) -> Environment:
        """用参数和实参创建一个子环境（用于函数调用）。

        params: 参数名列表（Symbol 列表）
        args:   实参值列表
        返回：以 self 为父环境的新环境
        """
        child = Environment(parent=self)
        for param, arg in zip(params, args):
            # param 可能是 Symbol 对象，取其 name 属性
            param_name = param.name if hasattr(param, 'name') else str(param)
            child.bindings[param_name] = arg
        return child
