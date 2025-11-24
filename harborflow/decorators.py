from __future__ import annotations

import asyncio
from functools import wraps
from typing import Any, Callable, Optional, Type, TypeVar, overload, ParamSpec, Awaitable, Union

from .types import Route, END, ConfigError
from .compile import compile_graph


T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")
_DEF_COUNTER = 0


@overload
def node(func: Callable[P, R]) -> Callable[P, R]: ...

@overload
def node(*, name: Optional[str] = None) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def node(func: Optional[Callable[P, R]] = None, *, name: Optional[str] = None) -> Union[Callable[P, R], Callable[[Callable[P, R]], Callable[P, R]]]:
    """标记一个函数/方法为 HarborFlow 节点。

    功能:
      - 为方法挂载元数据以参与图编译。
      - 支持同步和异步函数。

    使用场景:
      - 在类中声明可执行节点，支持默认名或自定义名。
      - 节点可以是普通函数或async函数。

    Args:
      func: 直接作为装饰器使用时的函数对象。
      name: 自定义节点名，默认使用函数名。

    Returns:
      Callable: 包装后的可调用对象，保持原始类型签名。
    """

    def decorator(f: Callable[P, R]) -> Callable[P, R]:
        node_name = name or f.__name__

        @wraps(f)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            return f(*args, **kwargs)

        global _DEF_COUNTER
        _DEF_COUNTER += 1
        setattr(wrapped, "__hf_is_node__", True)
        setattr(wrapped, "__hf_node_name__", node_name)
        setattr(wrapped, "__hf_def_index__", _DEF_COUNTER)
        setattr(wrapped, "__hf_is_async__", asyncio.iscoroutinefunction(f))
        setattr(wrapped, "__hf_is_parallel__", False)  # 默认不是并行节点
        return wrapped

    if func is not None and callable(func):
        return decorator(func)
    return decorator


def parallel_node(func: Optional[Callable[P, R]] = None, *, name: Optional[str] = None) -> Union[Callable[P, R], Callable[[Callable[P, R]], Callable[P, R]]]:
    """标记一个函数/方法为 HarborFlow 并行节点。

    功能:
      - 为方法挂载元数据以参与图编译。
      - 标记节点可以与其他节点并行执行。

    使用场景:
      - 在类中声明可并行执行的节点。
      - 适用于独立的、无依赖的计算任务。

    Args:
      func: 直接作为装饰器使用时的函数对象。
      name: 自定义节点名，默认使用函数名。

    Returns:
      Callable: 包装后的可调用对象，保持原始类型签名。
    """

    def decorator(f: Callable[P, R]) -> Callable[P, R]:
        node_name = name or f.__name__

        @wraps(f)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            return f(*args, **kwargs)

        global _DEF_COUNTER
        _DEF_COUNTER += 1
        setattr(wrapped, "__hf_is_node__", True)
        setattr(wrapped, "__hf_node_name__", node_name)
        setattr(wrapped, "__hf_def_index__", _DEF_COUNTER)
        setattr(wrapped, "__hf_is_async__", asyncio.iscoroutinefunction(f))
        setattr(wrapped, "__hf_is_parallel__", True)  # 标记为并行节点
        return wrapped

    if func is not None and callable(func):
        return decorator(func)
    return decorator


class GraphConfig:
    """存放 HarborFlow 图的基础配置。

    功能:
      - 记录状态类型、起点节点、结束哨兵与图名。

    使用场景:
      - 由 @graph 装饰器创建并挂载到类上。

    Args:
      state: 状态类型或模式。
      start: 起始节点名。
      finish: 结束哨兵，默认 END。
      name: 图名称，默认类名。
    """

    def __init__(
        self,
        state: Type[Any],
        start: str,
        finish: Any = END,
        name: Optional[str] = None,
    ) -> None:
        self.state = state
        self.start = start
        self.finish = finish
        self.name = name


def graph(
    *,
    state: Type[Any],
    start: str,
    finish: Any = END,
    name: Optional[str] = None,
):
    """类装饰器：声明“类即图”。

    功能:
      - 标记类为可编译图并注入 compile 方法。

    使用场景:
      - 用户以类组织节点并期望生成 LangGraph 应用。

    Args:
      state: 状态类型或模式。
      start: 起始节点名。
      finish: 结束哨兵，默认 END。
      name: 图名称，默认类名。

    Returns:
      Type[T]: 被装饰的类。

    说明:
      - 注入的 `compile(self, **options)` 会透传参数到 `compile_graph(self, **options)`，
        包括 `check`（是否启用编译校验）。
    """

    def decorator(cls: Type[T]) -> Type[T]:
        if not isinstance(start, str):
            raise ConfigError("graph(start=...) 必须是节点名字符串")

        cfg = GraphConfig(state=state, start=start, finish=finish, name=name or cls.__name__)
        setattr(cls, "__hf_graph_config__", cfg)

        def compile_method(self, **options: Any):
            return compile_graph(self, **options)

        setattr(cls, "compile", compile_method)
        return cls

    return decorator