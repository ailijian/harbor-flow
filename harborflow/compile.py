from __future__ import annotations

from typing import Any, Callable, List, Mapping, Tuple

from langgraph.graph import StateGraph, START, END as LG_END
from langgraph.types import Command

from .types import Route, ConfigError, END


def _iter_nodes(flow_instance: Any) -> List[Tuple[str, Callable[..., Any]]]:
    nodes: List[Tuple[int, str, Callable[..., Any]]] = []
    for attr_name in dir(flow_instance):
        attr = getattr(flow_instance, attr_name)
        if callable(attr) and getattr(attr, "__hf_is_node__", False):
            node_name = getattr(attr, "__hf_node_name__", attr_name)
            order = getattr(attr, "__hf_def_index__", 0)
            nodes.append((order, node_name, attr))
    nodes.sort(key=lambda x: x[0])
    return [(n, fn) for _, n, fn in nodes]


def _wrap_node(bound_method: Callable[..., Any]) -> Callable[[Mapping[str, Any]], Any]:
    def _node(state: Mapping[str, Any]) -> Any:
        result = bound_method(state)
        if isinstance(result, Route):
            return result.to_command()
        if isinstance(result, Command):
            return result
        if result is None:
            return {}
        if isinstance(result, Mapping):
            return result
        raise ConfigError(
            f"节点 `{getattr(bound_method, '__hf_node_name__', bound_method.__name__)}` 返回类型必须是 Route / Command / Mapping / None"
        )

    return _node


def compile_graph(flow_instance: Any, *, check: bool = True, **compile_options: Any):
    """将带 @graph/@node 元数据的实例编译为 LangGraph 应用。

    功能:
      - 收集被 @node 标记的方法并构建顺序链。
      - 连接 START/END 并适配节点返回值为 Command 或局部状态。

    使用场景:
      - 用户通过 @graph/@node 定义流程后，需要得到可 .invoke/.stream 的应用。

    Args:
      flow_instance: 使用 @graph 装饰的类实例。
      check (bool): 是否启用编译前的基础校验（V1.0.0 语义占位，默认 True）。
      **compile_options: 传递给 StateGraph.compile 的可选参数。

    Returns:
      Any: LangGraph 的编译结果应用对象。
    """
    cfg = getattr(flow_instance, "__hf_graph_config__", None)
    if cfg is None:
        raise ConfigError("对象缺少 __hf_graph_config__，请确认类已使用 @graph 装饰。")

    state_schema = cfg.state
    start_name = cfg.start

    nodes = _iter_nodes(flow_instance)
    if not nodes:
        raise ConfigError("图中没有任何 @node 节点。")

    node_names = {name for name, _ in nodes}
    if start_name not in node_names:
        raise ConfigError(f"start='{start_name}' 不在节点列表中：{sorted(node_names)}")

    builder = StateGraph(state_schema)

    for name, bound_method in nodes:
        builder.add_node(name, _wrap_node(bound_method))

    builder.add_edge(START, start_name)

    for (name_i, _), (name_j, _) in zip(nodes, nodes[1:]):
        builder.add_edge(name_i, name_j)

    last_name, _ = nodes[-1]
    builder.add_edge(last_name, LG_END)

    builder.set_entry_point(start_name)
    app = builder.compile(**compile_options)
    return app