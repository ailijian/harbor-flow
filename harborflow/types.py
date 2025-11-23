from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Generic, TypeVar, Sequence, Union, Optional

from langgraph.graph import END as _LG_END
from langgraph.types import Command


StateT = TypeVar("StateT", bound=Mapping[str, Any])
NodeNameT = TypeVar("NodeNameT", bound=str)

END = _LG_END


class HarborFlowError(Exception):
    """HarborFlow 基础异常。

    功能:
      - 作为 HarborFlow 的通用异常基类。

    使用场景:
      - 标准化抛错类型，供上层捕获与处理。
    """


class ConfigError(HarborFlowError):
    """配置或装饰器使用错误。

    功能:
      - 当 @graph/@node 的使用方式不符合约定时抛出。

    使用场景:
      - 编译前检查失败或节点返回类型不合法。
    """


@dataclass
class Route(Generic[StateT, NodeNameT]):
    """封装下一步路由与状态更新。

    功能:
      - 表达“去哪(goto)与更新(update)”的最小语义。
      - 为 LangGraph Command 提供友好包装与构造方法。

    使用场景:
      - 节点方法返回本类型以控制后续执行与状态变更。

    Args:
      goto: 下一节点名、节点名序列或 END。
      update: 要合入的局部状态字典，None 表示无更新。

    Returns:
      Route: 路由与更新信息的容器。
    """

    goto: Union[NodeNameT, Sequence[NodeNameT], object]
    update: Optional[Mapping[str, Any]] = None

    @classmethod
    def to(
        cls,
        goto: Union[NodeNameT, Sequence[NodeNameT], object],
        **update: Any,
    ) -> "Route":
        """构造指向指定节点的 Route。

        Args:
          goto: 下一节点或节点序列，或 END。
          **update: 要合入的局部状态键值。

        Returns:
          Route: 新的路由对象。
        """
        return cls(goto=goto, update=update or None)

    @classmethod
    def finish(cls, **update: Any) -> "Route":
        """构造指向 END 的 Route。

        Args:
          **update: 要合入的局部状态键值。

        Returns:
          Route: 指向 END 的路由对象。
        """
        return cls(goto=END, update=update or None)

    def with_update(self, **more: Any) -> "Route":
        """以浅覆盖方式追加 update。

        Args:
          **more: 追加的局部状态键值。

        Returns:
          Route: 自身，用于链式调用。
        """
        merged = dict(self.update or {})
        merged.update(more)
        self.update = merged
        return self

    def to_command(self) -> Command:
        """转换为 LangGraph Command。

        Returns:
          Command: 具备 goto 与 update 字段的对象。
        """
        return Command(goto=self.goto, update=self.update)