from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Mapping, Union, Optional, Callable, Sequence

from .types import Route, END, StateT, NodeNameT


@dataclass
class ConditionalRoute(Route[StateT, NodeNameT]):
    """条件路由，支持基于状态动态决定路由。

    功能:
      - 扩展Route，添加条件判断逻辑。
      - 支持复杂的分支逻辑和状态依赖的路由。

    使用场景:
      - 根据状态值决定下一个节点。
      - 实现复杂的业务规则分支。
      - 支持并行执行的条件判断。

    Args:
      goto: 目标节点，可以是节点名、节点列表或条件函数。
      condition: 条件函数，接收状态返回是否满足条件。
      update: 状态更新。
      priority: 优先级，用于多个条件路由冲突时。
    """

    condition: Optional[Callable[[StateT], Union[bool, Awaitable[bool]]]] = None
    priority: int = 0

    def evaluate_condition(self, state: StateT) -> Union[bool, Awaitable[bool]]:
        """评估条件。

        Args:
          state: 当前状态。

        Returns:
          Union[bool, Awaitable[bool]]: 条件评估结果。
        """
        if self.condition is None:
            return True
        return self.condition(state)

    async def evaluate_condition_async(self, state: StateT) -> bool:
        """异步评估条件。

        Args:
          state: 当前状态。

        Returns:
          bool: 条件评估结果。
        """
        result = self.evaluate_condition(state)
        if asyncio.iscoroutine(result):
            return await result
        return result

    @classmethod
    def when(
        cls,
        condition: Callable[[StateT], Union[bool, Awaitable[bool]]],
        goto: Union[NodeNameT, Sequence[NodeNameT], object],
        **update: Any,
    ) -> "ConditionalRoute":
        """创建条件路由。

        Args:
          condition: 条件函数。
          goto: 目标节点。
          **update: 状态更新。

        Returns:
          ConditionalRoute: 条件路由对象。
        """
        # 提取priority参数，如果不存在则默认为0
        priority = update.pop('priority', 0)
        return cls(goto=goto, condition=condition, priority=priority, update=update or None)

    @classmethod
    def branch(
        cls,
        conditions: list[tuple[Callable[[StateT], Union[bool, Awaitable[bool]]], Union[NodeNameT, Sequence[NodeNameT], object]]],
        default_goto: Union[NodeNameT, Sequence[NodeNameT], object] = END,
        **update: Any,
    ) -> list["ConditionalRoute"]:
        """创建分支条件路由列表。

        Args:
          conditions: 条件和目标节点对的列表。
          default_goto: 默认目标节点。
          **update: 状态更新。

        Returns:
          list[ConditionalRoute]: 条件路由列表。
        """
        routes = []
        for i, (condition, goto) in enumerate(conditions):
            routes.append(cls.when(condition, goto, **update, priority=len(conditions) - i))
        
        # 添加默认分支
        routes.append(cls(goto=default_goto, priority=0))
        return routes