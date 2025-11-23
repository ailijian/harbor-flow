## 一、整体架构与分层（洋葱视角）

### 1.1 模块分层

按依赖方向（外层只能依赖内层）：

```text
[最外层] harborflow.decorators
          ↓  只依赖 types / compile 的接口，不碰 langgraph
[中  间] harborflow.compile
          ↓  只依赖 types；是对 langgraph 的适配层
[最内层] harborflow.types
          ↓  只依赖 typing / langgraph.types.Command / langgraph.graph.END
       LangGraph v1.0 (StateGraph / Command / END)
```

* **Domain / Core（内圈） → `types.py`**

  * HarborFlow 的领域概念：`Route`、`END`、错误类型。
  * 不关心“类怎么变成 graph”，也不直接操作 LangGraph 的 builder。

* **Application（中圈） → `compile.py`**

  * 只负责一件事：把“带 `@graph` / `@node` 元数据的类”翻译成 `StateGraph` 并 `.compile()`。
  * 对 LangGraph v1.0 的唯一适配点：`StateGraph` + `Command` + `START/END`。([LangChain 文档][1])

* **Interface / UX（外圈） → `decorators.py`**

  * 对开发者暴露的唯一入口：`@graph`、`@node`。
  * 不直接依赖 LangGraph，只依赖 `compile.compile_graph()` 这一窄接口 + `Route` / `END` 类型。

> 设计目标：
>
> * **用户只需要 import：**`graph, node, Route, END`
> * 看不到 LangGraph 的复杂 API，只感知“类即图，返回即路由”。

---

## 二、`types.py` 实现设计（核心领域层）

### 2.1 职责与对外 API

**职责：**

* 定义 HarborFlow 的最小核心类型：

  * `END`：LangGraph 的 END 哨兵的二次导出。
  * `Route`：对 LangGraph `Command` 的薄包装，体现 “goto + update” 语义。
  * 若需要，定义少量错误类型（例如配置错误）。

**对外 API（V1.0.0）**：

```python
from harborflow.types import (
    Route,      # 节点推荐返回值
    END,        # 终止哨兵（来自 langgraph.graph）
    HarborFlowError,
    ConfigError,
)
```

### 2.2 关键设计点

1. **Route 与 LangGraph.Command 的关系**

   * LangGraph v1.0 中 `Command` 用于“同时更新 state + 指定下一节点”([LangChain Blog][2])
   * HarborFlow 的 `Route` 不直接暴露 `Command`，而是：

     * 在 `compile.py` 里把 `Route` 映射为 `Command`；
     * 对用户暴露更直观的字段名：`goto`、`update`。

2. **最小语义：只负责 “去哪 + 更新什么”**

   * V1.0.0 不引入复杂字段（如 subgraph、resume 等），只保留：

     * `goto`: `str | Sequence[str] | END`
     * `update`: `Mapping[str, Any] | None`

3. **辅助构造函数**

   * 提供用户手感好的方法：

     * `Route.to(goto, **update)`：最常见快速写法。
     * `Route.finish(**update)`：`goto=END` 的糖。

4. **不含状态合并/列表 extend 规则**

   * **合并策略交给 LangGraph 的 reducer / State 定义**([LangChain 文档][3])
   * HarborFlow 不在 `Route` 内做“智能 append/extend”，避免再次提高心智负担。

### 2.3 代码骨架（示意）

```python
# harborflow/types.py
from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Mapping,
    MutableMapping,
    Generic,
    TypeVar,
    Sequence,
    Union,
    Optional,
)
from langgraph.graph import END as _LG_END  # v1.0+ END 哨兵:contentReference[oaicite:4]{index=4}
from langgraph.types import Command  # v1.0+ Command 类型:contentReference[oaicite:5]{index=5}


StateT = TypeVar("StateT", bound=Mapping[str, Any])
NodeNameT = TypeVar("NodeNameT", bound=str)

END = _LG_END  # 向用户二次导出


class HarborFlowError(Exception):
    """HarborFlow 基础异常"""


class ConfigError(HarborFlowError):
    """配置或装饰器使用错误"""


@dataclass
class Route(Generic[StateT, NodeNameT]):
    """HarborFlow 节点推荐返回值：封装下一步路由 + 状态更新"""

    goto: Union[NodeNameT, Sequence[NodeNameT], object]  # 包括 END
    update: Optional[Mapping[str, Any]] = None

    # --- 辅助构造 ---

    @classmethod
    def to(
        cls,
        goto: Union[NodeNameT, Sequence[NodeNameT], object],
        **update: Any,
    ) -> "Route":
        return cls(goto=goto, update=update or None)

    @classmethod
    def finish(cls, **update: Any) -> "Route":
        """语义：本节点结束整个图"""
        return cls(goto=END, update=update or None)

    def with_update(self, **more: Any) -> "Route":
        """链式追加 update（不做深合并，只是浅层覆盖）"""
        merged = dict(self.update or {})
        merged.update(more)
        self.update = merged
        return self

    # --- 给编译层使用的转换 ---

    def to_command(self) -> Command:
        """转换为 LangGraph Command 对象（供 compile.py 使用）"""
        return Command(
            goto=self.goto,
            update=self.update,
        )
```

> 注意：这里没引入任何 HarborFlow 自己的 “保留字段” / `__harborflow__` 命名空间，完全交给 LangGraph 的 state / reducer 机制。

### 2.4 `types.py` 开发计划

**Step 1：定义错误类型**

* [ ] `HarborFlowError`
* [ ] `ConfigError`

**Step 2：LangGraph 依赖接入**

* [ ] 从 `langgraph.graph` 导入并 re-export `END`
* [ ] 从 `langgraph.types` 导入 `Command`（确认 v1.0+ API）

**Step 3：实现 `Route`**

* [ ] 数据字段：`goto`, `update`
* [ ] `Route.to()` / `Route.finish()` / `with_update()`
* [ ] `to_command()` 实现

**Step 4：简单单元测试**

* [ ] `Route.to("node", x=1).to_command()` → `Command(goto="node", update={"x":1})`
* [ ] `Route.finish(msg="hi")` → `goto is END`
* [ ] `with_update()` 覆盖行为符合预期

---

## 三、`decorators.py` 实现设计（接口层）

### 3.1 职责与 API

**职责：**

* 把“普通 Python 类 + 方法”**标记**成 HarborFlow graph：

  * `@graph`：标记类为一个可编译的图，记录状态类型、起点节点等元信息，并注入 `compile()` 方法。
  * `@node`：标记类方法为节点，记录节点名等元信息。

**对外 API：**

```python
from harborflow import graph, node, Route, END
# 或 from harborflow.decorators import graph, node
```

用户写法（回顾）：

```python
from harborflow import graph, node, Route, END
from typing import TypedDict, List

class State(TypedDict):
    messages: List[tuple[str, str]]

@graph(state=State, start="agent", finish=END)
class SimpleChat:
    @node
    def agent(self, state: State):
        last = state["messages"][-1][1] if state["messages"] else "none"
        reply = f"echo: {last}"
        # 推荐写法：返回 Route
        return Route.to("agent", messages=[("assistant", reply)])
```

### 3.2 关键设计点

1. **`@graph` 只负责“标记 + 挂载 compile”，不做编译**

   * 真正的编译逻辑放在 `compile.py` 的 `compile_graph(instance)` 中。
   * `@graph` 的工作：

     * 把配置（`state`, `start`, `finish` 等）存到类属性（例如：`__hf_config__`）。
     * 在类上注入一个实例方法 `compile(self, **options)`，内部调用 `compile_graph(self, **options)`。

2. **`@node` 只做“打标签”，不包复杂逻辑**

   * 不做只读代理、Guard 之类的高级功能（V1.0.0 不引入）。
   * 只是给函数/方法挂上：

     * `__hf_is_node__ = True`
     * `__hf_node_name__ = ...`（如果用户未指定，默认用函数名）。

3. **依赖方向**

   * `decorators.py` 可以引用 `compile.compile_graph` 作为黑盒；
   * 不直接 import LangGraph，保证 UI 层对底层实现透明。

### 3.3 代码骨架（示意）

```python
# harborflow/decorators.py
from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Optional, Type, TypeVar, overload

from .types import Route, END, ConfigError
from .compile import compile_graph  # 仅依赖这个窄接口

T = TypeVar("T")


# -------- @node --------

@overload
def node(func: Callable[..., Any]) -> Callable[..., Any]: ...
@overload
def node(*, name: Optional[str] = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


def node(func: Optional[Callable[..., Any]] = None, *, name: Optional[str] = None):
    """标记一个方法/函数为 HarborFlow 节点"""

    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        node_name = name or f.__name__

        @wraps(f)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            # V1.0.0 不增加魔法逻辑，直接调用原函数
            return f(*args, **kwargs)

        # 挂元数据（编译层会用）
        setattr(wrapped, "__hf_is_node__", True)
        setattr(wrapped, "__hf_node_name__", node_name)

        return wrapped

    # 支持 @node 和 @node(...)
    if func is not None and callable(func):
        return decorator(func)
    return decorator


# -------- @graph --------

class GraphConfig:
    """存放单个 HarborFlow 图的基础配置"""

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
    """类装饰器：声明“类即图”"""

    def decorator(cls: Type[T]) -> Type[T]:
        # 基本校验（轻量，重校验交给 compile.py）
        if not isinstance(start, str):
            raise ConfigError("graph(start=...) 必须是节点名字符串")

        # 记录配置到类级别
        cfg = GraphConfig(state=state, start=start, finish=finish, name=name or cls.__name__)
        setattr(cls, "__hf_graph_config__", cfg)

        # 注入 compile() 实例方法（薄封装）
        def compile_method(self, **options: Any):
            """编译成 LangGraph 应用（StateGraph.compile 的结果）"""
            return compile_graph(self, **options)

        setattr(cls, "compile", compile_method)

        return cls

    return decorator
```

### 3.4 `decorators.py` 开发计划

**Step 1：`@node`**

* [ ] 支持 `@node` / `@node(name="...")` 两种调用方式。
* [ ] 给 wrapped 函数挂 `__hf_is_node__` / `__hf_node_name__`。
* [ ] 简单单测：从类实例上拿到方法，检查属性存在。

**Step 2：`GraphConfig` 基础结构**

* [ ] `state`, `start`, `finish`, `name` 字段。
* [ ] 提供简单 `__repr__` / debug 友好描述（可选）。

**Step 3：`@graph`**

* [ ] 存储配置到 `cls.__hf_graph_config__`。
* [ ] 注入实例方法 `compile(self, **options) -> Any`，内部调用 `compile_graph(self, **options)`。

**Step 4：端到端最小验证**

* [ ] 写一个最小示例 `SimpleChat`（1–2 个节点）。
* [ ] 通过 `SimpleChat().compile()` 能得到一个可以 `.invoke()` 的 app（后续由 `compile.py` 实现配合）。

---

## 四、`compile.py` 实现设计（应用 / 基础设施层）

### 4.1 职责与输入输出

**职责：**

* 解析被 `@graph` / `@node` 标记的类实例；
* 构造 LangGraph v1.0 的 `StateGraph`；
* 按“顺序执行 + 可选 Route 跳转”的 UX 约定**自动加边**；
* 调用 `StateGraph.compile()` 得到可执行 app。

**核心入口 API**：

```python
from harborflow.compile import compile_graph

def compile_graph(flow_instance, *, check: bool = True, **compile_opts) -> "CompiledStateGraph":
    ...
```

* **输入**：一个被 `@graph` 装饰过的类实例；
* **输出**：LangGraph 的 `CompiledStateGraph`（拥有 `.invoke/.stream/ainvoke` 等方法）([LangChain参考][4])

### 4.2 如何利用 LangGraph v1.0 特性

1. **`StateGraph` + `START/END` 基本用法**

   * 创建 builder：`builder = StateGraph(state_schema)`；([LangChain 文档][1])
   * 添加节点：`builder.add_node(name, fn)`；
   * 添加边：`builder.add_edge(START, first_node)`、`builder.add_edge("a", "b")`、`builder.add_edge("last", END)`；
   * 编译：`app = builder.compile(**options)`。

2. **结合 `Command` 支持“返回即路由”**

   * LangGraph 官方设计：节点可以返回 `Command(goto=..., update=...)`，控制后续执行节点([LangChain Blog][2])
   * HarborFlow 的 `Route.to_command()` 就是对这一特性的包装。
   * 这样我们**不需要自己实现条件边 / 自定义 router**，最大限度使用 LangGraph 原生能力。

3. **顺序执行 + Route 手动跳转并存**

   * **默认行为：顺序执行**

     * 根据类中节点出现的顺序，自动添加链式边：`START -> n1 -> n2 -> ... -> n_last -> END`；
     * 用户只返回 `dict`（Partial[State]）时，等价于“顺序执行到链上的下一个节点”。
   * **高级行为：Route 手动跳转**

     * 节点返回 `Route` → 转成 `Command(goto=..., update=...)`；
     * LangGraph 按 `goto` 执行指定节点（可以覆盖链式边）。

### 4.3 关键设计点

1. **节点收集规则**

   * 通过 `dir(instance)` 遍历属性；
   * 取出带 `__hf_is_node__` 的可调用对象；
   * 按 **定义顺序** 排序：

     * 简单做法：在 `@node` 上再挂一个自增序号 `__hf_def_index__`，在 decorator 中维护全局计数。
   * 得到有序列表：`[(node_name, bound_method), ...]`。

2. **节点包装逻辑（统一适配返回类型）**

   * 支持节点返回三种情况：

     1. `Route`（推荐）→ 转成 `Command`；
     2. `Command`（少数高级用户）→ 原样返回；
     3. `Mapping` / `dict`（Partial State）→ 顺序执行，保持 edge 链路。
   * 统一 wrap 成 LangGraph 理解的 node：

   ```python
   def make_wrapped_node(bound_method):
       def _node(state):
           result = bound_method(state)
           if isinstance(result, Route):
               return result.to_command()
           from langgraph.types import Command
           if isinstance(result, Command):
               return result
           if result is None:
               return {}
           if isinstance(result, Mapping):
               return result
           raise ConfigError("节点返回类型必须是 Route / Command / dict / None")
       return _node
   ```

3. **自动加边策略**

   * 有序节点列表：`n0, n1, ..., nk`
   * 配置 `start` 指定起点（必须在节点列表中）。
   * 线性边：

     * `builder.add_edge(START, start_node)`；
     * 对于列表中每个相邻对 `(ni, nj)`，按“定义顺序”添加 `builder.add_edge(ni, nj)`；
     * 最后一个节点默认加 `builder.add_edge(last, END)`。
   * 将来如需更复杂拓扑，可以增加额外参数，但 **V1.0.0 只做“顺序 + Route 手动跳转”**。

4. **基础校验（轻量）**

   * `start` 必须存在于节点名集合；
   * 至少有一个节点；
   * Warn：`finish` 长期可能不用单独存在（因为 END + Route 即可），V1.0.0 先保留但只做极简处理。

### 4.4 代码骨架（示意）

```python
# harborflow/compile.py
from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Tuple
from typing import get_type_hints

from langgraph.graph import StateGraph, START, END as LG_END  # v1.0+:contentReference[oaicite:9]{index=9}
from langgraph.types import Command  # v1.0+:contentReference[oaicite:10]{index=10}

from .types import Route, ConfigError, END


def _iter_nodes(flow_instance: Any) -> List[Tuple[str, Callable[..., Any]]]:
    """从实例上收集所有 HarborFlow 节点（按定义顺序排好）"""
    nodes: List[Tuple[int, str, Callable[..., Any]]] = []

    for attr_name in dir(flow_instance):
        attr = getattr(flow_instance, attr_name)
        if callable(attr) and getattr(attr, "__hf_is_node__", False):
            node_name = getattr(attr, "__hf_node_name__", attr_name)
            order = getattr(attr, "__hf_def_index__", 0)
            nodes.append((order, node_name, attr))

    # 按定义顺序排序
    nodes.sort(key=lambda x: x[0])
    # 返回 (node_name, bound_method)
    return [(n, fn) for _, n, fn in nodes]


def _wrap_node(bound_method: Callable[..., Any]) -> Callable[[Mapping[str, Any]], Any]:
    """将用户节点包装成 LangGraph 期望的节点函数"""

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
            f"节点 `{getattr(bound_method, '__hf_node_name__', bound_method.__name__)}` "
            "返回类型必须是 Route / Command / Mapping / None"
        )

    return _node


def compile_graph(flow_instance: Any, **compile_options: Any):
    """把带 @graph/@node 的类实例编译成 LangGraph 应用"""

    cfg = getattr(flow_instance, "__hf_graph_config__", None)
    if cfg is None:
        raise ConfigError("对象缺少 __hf_graph_config__，请确认类已使用 @graph 装饰。")

    state_schema = cfg.state
    start_name = cfg.start

    # 1. 收集节点
    nodes = _iter_nodes(flow_instance)
    if not nodes:
        raise ConfigError("图中没有任何 @node 节点。")

    node_names = {name for name, _ in nodes}
    if start_name not in node_names:
        raise ConfigError(f"start='{start_name}' 不在节点列表中：{sorted(node_names)}")

    # 2. 构建 StateGraph
    builder = StateGraph(state_schema)

    # 添加节点
    for name, bound_method in nodes:
        builder.add_node(name, _wrap_node(bound_method))

    # 3. 添加边：START + 顺序链
    builder.add_edge(START, start_name)

    # 顺序链：按 nodes 的顺序
    for (name_i, _), (name_j, _) in zip(nodes, nodes[1:]):
        builder.add_edge(name_i, name_j)

    # 最后一个到 END
    last_name, _ = nodes[-1]
    builder.add_edge(last_name, LG_END)

    # 4. 设置入口点并编译
    builder.set_entry_point(start_name)
    app = builder.compile(**compile_options)
    return app
```

> 说明：
>
> * 这里我们还没实现 `__hf_def_index__`，可以在 `@node` 中用一个简单的全局递增计数器加上；
> * `finish` 目前没用到（因为 END + Route 就够用），V1.0.0 可以先记录但不强依赖。

### 4.5 `compile.py` 开发计划

**Step 1：节点收集**

* [ ] `_iter_nodes()`：基于 `__hf_is_node__` / `__hf_node_name__` 收集节点；
* [ ] 在 `@node` 装饰器里增加 `__hf_def_index__` 以保证顺序（简单全局计数即可）。

**Step 2：返回值适配**

* [ ] `_wrap_node()` 支持 `Route` / `Command` / `Mapping` / `None` 四种情况；
* [ ] 错误信息中包含节点名，便于调试。

**Step 3：图结构构建**

* [ ] 从 `__hf_graph_config__` 读取 `state`, `start`；
* [ ] 使用 `StateGraph(state_schema)` 初始化；
* [ ] `add_node` 所有节点；
* [ ] `add_edge(START, start)`；
* [ ] nodes 顺序链 + 最后到 `END`；
* [ ] `set_entry_point(start)`；
* [ ] `compile(**options)`。

**Step 4：最小集成测试**

* [ ] 一个两节点 demo：`input -> agent`，仅顺序返回 dict；
* [ ] 一个 Route demo：在中间节点 `Route.to("other")` 手动跳转；
* [ ] 确认 `.invoke()` / `.stream()` 等 LangGraph v1.0 方法可用。

---

## 五、整体开发顺序（V1.0.0 最小可用版）

你可以按下面顺序推进，每一步都能得到“可运行的最小版本”，方便迭代：

1. **实现 `types.py`**

   * Route + END re-export + 错误类型；
   * 写简单单元测试。

2. **实现最简 `@node` + `@graph`（不加 def_index 也行）**

   * 先只挂上元数据；
   * 手动在 `compile.py` 里用固定顺序（比如 `sorted(node_names)`）做原型。

3. **实现最简单版 `compile_graph`**

   * 只支持一个节点的图（无顺序链），先跑通 `SimpleChat().compile().invoke(...)`。

4. **引入“顺序链”与 `__hf_def_index__`**

   * 在 `@node` 装饰器中维护全局计数；
   * `compile.py` 使用该顺序添加链式边。

5. **支持 Route / Command 返回值**

   * `_wrap_node()` 中增加类型分支；
   * 写一个 Route 跳转的集成示例（如 agent → tool → agent）。

6. **补充错误信息 / 小文档示例**

   * 对 `ConfigError` 补充消息；
   * 写 1–2 个完整最小 demo 放到 docs 示例中。

---
