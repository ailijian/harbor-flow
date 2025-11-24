from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Mapping, Generic, TypeVar, Sequence, Union, Optional, Callable

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


class NodeExecutionError(HarborFlowError):
    """节点执行错误。

    功能:
      - 当节点执行失败时抛出，包含节点名和原始异常。

    使用场景:
      - 节点函数抛出异常或超时。
    """
    
    def __init__(self, node_name: str, original_error: Exception, message: Optional[str] = None):
        self.node_name = node_name
        self.original_error = original_error
        if message is None:
            message = f"节点 '{node_name}' 执行失败: {str(original_error)}"
        super().__init__(message)


@dataclass
class NodeConfig:
    """节点执行配置。

    功能:
      - 配置节点的超时、重试等行为。
      - 提供标准化的错误处理机制。

    使用场景:
      - 为节点设置执行超时时间。
      - 配置失败重试策略。
      - 自定义错误处理行为。

    Args:
      timeout: 节点执行超时时间（秒），None表示无超时。
      max_retries: 最大重试次数，0表示不重试。
      retry_delay: 重试延迟时间（秒）。
      on_error: 错误处理回调函数。
    """

    timeout: Optional[float] = None
    max_retries: int = 0
    retry_delay: float = 1.0
    on_error: Optional[Callable[[str, Exception], Any]] = None

    async def execute_with_retry(self, node_name: str, func: Callable[[], Any]) -> Any:
        """使用重试机制执行节点函数。

        Args:
          node_name: 节点名称，用于错误信息。
          func: 要执行的函数。

        Returns:
          Any: 函数执行结果。

        Raises:
          NodeExecutionError: 当所有重试都失败时抛出。
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if self.timeout is not None:
                    # 使用asyncio.wait_for处理超时
                    if asyncio.iscoroutinefunction(func):
                        return await asyncio.wait_for(func(), timeout=self.timeout)
                    else:
                        # 对于同步函数，在线程池中执行并设置超时
                        loop = asyncio.get_event_loop()
                        return await asyncio.wait_for(
                            loop.run_in_executor(None, func), 
                            timeout=self.timeout
                        )
                else:
                    if asyncio.iscoroutinefunction(func):
                        return await func()
                    else:
                        return func()
                        
            except Exception as e:
                last_error = e
                
                # 调用错误处理回调
                if self.on_error is not None:
                    try:
                        if asyncio.iscoroutinefunction(self.on_error):
                            await self.on_error(node_name, e)
                        else:
                            self.on_error(node_name, e)
                    except Exception as callback_error:
                        # 如果错误处理回调也失败，记录但不中断重试流程
                        print(f"错误处理回调失败: {callback_error}")
                
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay)
        
        # 所有重试都失败
        raise NodeExecutionError(node_name, last_error)


def validate_state_transition(
    prev_state: Mapping[str, Any], 
    next_state: Mapping[str, Any],
    state_schema: Optional[type] = None,
    required_fields: Optional[list[str]] = None,
    immutable_fields: Optional[list[str]] = None
) -> bool:
    """验证状态转换的合法性。

    功能:
      - 检查状态字段的完整性和类型。
      - 验证不可变字段是否被修改。
      - 确保必需字段存在。

    使用场景:
      - 节点执行前后的状态验证。
      - 确保状态转换符合业务规则。

    Args:
      prev_state: 前一个状态。
      next_state: 新状态。
      state_schema: 状态类型模式（如TypedDict类）。
      required_fields: 必需字段列表。
      immutable_fields: 不可变字段列表。

    Returns:
      bool: 验证是否通过。

    Raises:
      ConfigError: 当验证失败时抛出，包含详细的错误信息。
    """
    errors = []
    
    # 检查必需字段
    if required_fields:
        missing_fields = [field for field in required_fields if field not in next_state]
        if missing_fields:
            errors.append(f"缺少必需字段: {missing_fields}")
    
    # 检查不可变字段
    if immutable_fields and prev_state:
        for field in immutable_fields:
            if field in prev_state and field in next_state:
                if prev_state[field] != next_state[field]:
                    errors.append(f"不可变字段 '{field}' 被修改: {prev_state[field]} -> {next_state[field]}")
    
    # 检查类型模式（如果提供）
    if state_schema and hasattr(state_schema, '__annotations__'):
        annotations = state_schema.__annotations__
        for field, expected_type in annotations.items():
            if field in next_state:
                actual_value = next_state[field]
                # 基础类型检查
                if expected_type == str and not isinstance(actual_value, str):
                    errors.append(f"字段 '{field}' 类型错误: 期望 str, 得到 {type(actual_value).__name__}")
                elif expected_type == int and not isinstance(actual_value, int):
                    errors.append(f"字段 '{field}' 类型错误: 期望 int, 得到 {type(actual_value).__name__}")
                elif expected_type == float and not isinstance(actual_value, (int, float)):
                    errors.append(f"字段 '{field}' 类型错误: 期望 float, 得到 {type(actual_value).__name__}")
                elif expected_type == bool and not isinstance(actual_value, bool):
                    errors.append(f"字段 '{field}' 类型错误: 期望 bool, 得到 {type(actual_value).__name__}")
                elif hasattr(expected_type, '__origin__'):  # 处理泛型类型
                    if expected_type.__origin__ == list and not isinstance(actual_value, list):
                        errors.append(f"字段 '{field}' 类型错误: 期望 list, 得到 {type(actual_value).__name__}")
                    elif expected_type.__origin__ == dict and not isinstance(actual_value, dict):
                        errors.append(f"字段 '{field}' 类型错误: 期望 dict, 得到 {type(actual_value).__name__}")
    
    if errors:
        raise ConfigError(f"状态验证失败: {'; '.join(errors)}")
    
    return True


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