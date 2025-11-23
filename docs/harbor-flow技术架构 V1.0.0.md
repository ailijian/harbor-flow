# HarborFlow v1.0.0 技术架构文档

> 基于 LangGraph 1.0+ 的轻量语法糖层

---

## 0. 文档目的与适用范围

* **文档角色**：

  * 这是 HarborFlow v1.0.0 的**唯一事实来源**（Single Source of Truth，架构层级）。
  * 后续的「实现细节 / 模块设计 / 代码级文档」都必须以本稿为准进行展开或细化。

* **目标读者**：

  * 已理解 LangGraph 1.0 基本概念（`StateGraph`、`START`/`END`、`Command` 等）；([LangChain 文档][1])
  * 准备或正在实现 HarborFlow v1.0 的核心代码；
  * 使用 HarborFlow 的高级用户（需要知道“它到底帮我做了什么，没做什么”）。

* **版本约束**：

  * **LangGraph：`>= 1.0.0`**（v1.0 之后官方承诺不再有破坏性 API 变更）。([GitHub][2])
  * HarborFlow 不考虑兼容旧版 `langgraph<1.0`。

---

## 1. 设计目标与非目标

### 1.1 设计目标（DX 视角）

1. **代码即图（Code-as-Graph）**

   * 用户只需要写一个普通 Python 类 + 若干方法；
   * 类结构（方法名 / 顺序）就是图结构的默认骨架。

2. **返回即路由（Return-as-Route）**

   * 若节点返回 `Route(...)`（本质是 LangGraph 的 `Command`），则**返回值直接决定下一个节点**以及状态更新；([LangChain 文档][3])
   * 若返回的是 `dict`，则**只表示“状态更新”**，路由按编译时生成的顺序边执行。

3. **显式编译，透明运行**

   * 保留官方推荐模式：

     ```python
     app = ChatFlow().compile()
     result = app.invoke({"messages": []})
     ```
   * `compile()` 明确表达“从类 → LangGraph 图”的一步；
   * 返回对象就是原生 `CompiledStateGraph` 的轻量包装，所有 LangGraph 能力（`invoke/stream/checkpoint`）都可直接使用。([LangChain 文档][4])

4. **最少新概念，仅四个名字**

   * `graph`（图声明装饰器）
   * `node`（节点声明装饰器）
   * `Route`（路由+状态更新，封装 `Command`）
   * `END`（直接转出 LangGraph 的 END 哨兵常量）([LangChain 文档][1])

5. **紧贴 LangGraph 1.0 的原生能力**

   * 不重新实现状态聚合、持久化、检查点、Streaming 等；
   * 只做**语法糖 + 约定**，让 Graph API 用起来更像写普通函数。

### 1.2 非目标（v1.0 明确不做的事）

1. **不提供复杂控制流 DSL**

   * 不内建 Guard 系统、循环检测器、错误恢复 DSL 等（这些会在 v1.x 后续版本中评估）；
   * 若需要复杂控制流，可直接回落使用原生 LangGraph Graph API / Command / 条件边。([LangChain 文档][5])

2. **不重新包装 LangGraph Runtime**

   * 不重新定义 checkpointer/interrupt/store 等概念；
   * 只做一层非常薄的 `HarborCompiledGraph` 包装（或直接返回原生对象），确保用户可以无缝使用官方文档中的所有能力。

3. **不隐藏 LangGraph 细节到“看不见”**

   * HarborFlow 目标是“减轻样板和心智负担”，不是把 LangGraph 完全藏起来；
   * 用户若愿意，依然可以看到图（`get_graph().draw_mermaid()`）、使用 Studio 等工具。([Phase 2][6])

---

## 2. 与 LangGraph 1.0 的关系与依赖

本节只聚焦 HarborFlow 直接依赖的官方概念。

### 2.1 Graph API：StateGraph & START/END

* HarborFlow 基于 **Graph API**（非 Functional API）。([LangChain 文档][4])
* 使用的核心类型：

  * `StateGraph(state_schema=State, *, name=None, **kwargs)`
  * 特殊节点：`START`, `END`
* HarborFlow 不改变这些概念，只是**在编译期自动调用这些 API** 来构建图。

### 2.2 Command：HarborFlow `Route` 的基础

* LangGraph 1.0 提供 `Command` 类型，用于**同时：**

  * 更新状态：`update={...}`
  * 跳转节点：`goto="other_node"`([LangChain 文档][3])
* 官方建议：当你需要“更新状态 + 路由”时使用 `Command`，否则用条件边。
* **HarborFlow 的 Route = 针对 Python 用户的轻量封装：**

  * 语义上等价于 `Command`；
  * API 更贴近“路由”的直觉（`Route(goto=..., update=...)`）。

### 2.3 CompiledStateGraph 与运行时

* `StateGraph.compile()` 返回一个 **CompiledStateGraph**，提供：([LangChain 文档][4])

  * `invoke(initial_state, *, config=None, **kwargs)`
  * `ainvoke(...)`
  * `stream(...) / astream(...)`
* HarborFlow 的 `.compile()` 就是构造 `StateGraph` → `compile()` → 包装返回对象，**不会改变这些运行时行为**。

---

## 3. 模块与包结构（v1.0 级别）

从实现角度，HarborFlow 推荐的最小包结构如下（仅架构层级，非最终代码）：

```text
harborflow/
  __init__.py          # 对外暴露 graph, node, Route, END
  decorators.py        # 实现 @graph, @node
  types.py             # 定义 Route 类型（封装 Command）
  compile.py           # Graph 编译器（类 → StateGraph）
  runtime.py           # 轻量包装已编译图（可选）
  introspection.py     # 帮助函数（获取节点列表等，可选）
```

对用户而言，只需要记住一行：

```python
from harborflow import graph, node, Route, END
```

---

## 4. 核心抽象设计

### 4.1 Route：动态路由 + 状态更新

#### 4.1.1 用户视角 API

> 推荐使用方式

```python
from harborflow import Route, END
from typing import Literal

def agent(state: State) -> Route[Literal["tool", END]]:
    # some logic ...
    if need_tool:
        return Route(
            goto="tool",
            update={"messages": [...]}  # 追加/覆盖的细节交给 LangGraph 的 reducer/聚合逻辑
        )
    else:
        return Route(
            goto=END,
            update={"messages": [...]} 
        )
```

* **字段含义**：

  * `goto: str | END`

    * 下一个要执行的节点名，或 `END`；
  * `update: Mapping[str, Any] | Any`

    * 传给 LangGraph 的状态更新值（与原生 `Command(update=...)` 行为保持一致）。([LangChain 文档][3])

* **类型标注（推荐但非强制）**：

  * `Route[Literal["tool", END]]` 对应 LangGraph 中 `Command[Literal["tool"]]` 的写法，有助于 IDE 补全和图渲染。([LangChain 文档][3])

#### 4.1.2 实现视角（与 LangGraph 的映射）

* `Route` 在实现上可以是：

  * 一个 dataclass / 普通类，内部**持有一个 `langgraph.types.Command` 实例**；或
  * 直接继承/别名 `Command`，只增加一层薄包装（方便 import 和 IDE 文档）。([LangChain 文档][3])
* 编译期 & 运行期关键点：

  * 节点函数返回 `Route` → HarborFlow 包装器提取 `goto` 与 `update` → 返回原生 `Command` 给 LangGraph；
  * HarborFlow 不再引入自定义保留字段（如 `__harborflow__`），避免与 LangGraph 的内部状态机制冲突，减少心智负担。

### 4.2 `@node`：节点声明

#### 4.2.1 使用约定

```python
from harborflow import node, Route, END

class ChatFlow:
    @node
    def agent(self, state: State) -> Route:
        ...

    @node(name="tool")  # 可选：显式命名
    def call_tool(self, state: State) -> Route:
        ...
```

* **命名规则**：

  * 默认节点名为方法名：`agent`, `call_tool`；
  * 可用 `@node(name="...")` 覆盖；
  * 节点名必须唯一。

* **函数签名（v1.0 简化版）**：

  * 推荐：`def node(self, state: State) -> Route | dict:`
  * v1.0 **不引入** context/runtime 注入（如 `state, config`），避免一次性暴露太多 LangGraph 内部概念；
  * 将 context 的支持留给 v1.1+，通过 `context_schema` 与可选第二参数扩展。

* **返回值约定**：

  * **规范推荐**：统一返回 `Route`（官方文档与示例也如此书写）；
  * **受支持但不推荐**：返回 `dict`（视为“只更新状态，不改变路由”，用于简单顺序流）。

#### 4.2.2 编译时标记

`@node` 的职责非常单一：

1. 给函数打上几个内部标记，例如：

   * `_hf_is_node = True`
   * `_hf_node_name = "agent"`
   * `_hf_decl_order = <类定义顺序中的索引>`
   * `_hf_return_type = <typing.get_type_hints() 的结果>`
2. 不直接操作 LangGraph，所有图构建都由 `@graph` 装饰器所在模块统一完成。

### 4.3 `@graph`：类级图声明

#### 4.3.1 使用示例

```python
from harborflow import graph, node, Route, END
from typing_extensions import TypedDict

class State(TypedDict):
    messages: list[tuple[str, str]]

@graph(
    state=State,
    start="agent",          # 必填：起始节点
    finish=END,             # 可选：默认表示“最终必须停在 END”
    name="SimpleChat",      # 可选：图名
)
class SimpleChat:
    @node
    def agent(self, state: State) -> Route:
        last = state["messages"][-1][1] if state["messages"] else "none"
        reply = f"echo: {last}"
        # 简单写法：不手动路由，交给顺序边和 finish 处理
        return {"messages": [("assistant", reply)]}

    @node
    def done(self, state: State) -> Route:
        return Route(goto=END, update={})
```

* **参数含义**：

  * `state`: 必填，LangGraph `state_schema`，通常是 `TypedDict` / Pydantic Model / `MessagesState`；([LangChain 文档][1])
  * `start`: 必填，起始节点名（字符串）；
  * `finish`: 可选，默认为 `END`；
  * `name`: 可选，传给 `StateGraph(..., name=...)`；
  * `graph_options`: 可选，未来扩展用（例如持久化、检查点等配置的透传）。

#### 4.3.2 装饰器职责

`@graph` 装饰器在**类定义阶段**只做两件事：

1. 将配置写入类属性，例如：

   * `__hf_graph_config__ = GraphConfig(...)`
2. 包装类，注入 `compile()` 方法（实例级）：

   * `def compile(self, *, graph_options_override=None) -> HarborCompiledGraph | CompiledStateGraph: ...`

---

## 5. 编译流程：`ChatFlow().compile()`

> **核心设计原则**：
> 编译时尽量多做事（推导节点、生成顺序边、区分动态/顺序节点），让运行时行为简单、符合直觉。

### 5.1 总体流程

以 `ChatFlow().compile()` 为例：

1. **实例化类**

   * `instance = ChatFlow()`
   * 这一步允许构造函数中注册依赖（如模型、工具），但推荐保持轻量。

2. **收集节点元数据**

   * 遍历 `dir(instance)`，查找带 `_hf_is_node=True` 标记的方法；
   * 按 `_hf_decl_order` 排序，得到一个有序列表 `nodes = [("agent", fn1), ("tool", fn2), ...]`。

3. **识别节点类型（顺序 vs 动态）**

   * 对每个节点，检查返回类型标注：

     * 若 `return_annotation` 是 `Route` 或 `Route[...]` → 判定为**动态节点**；
     * 否则视为**顺序节点**（只更新状态，不决定路由）。
   * 这是 v1.0 的一个**关键 UX 决策**：

     * 用户只需在需要动态路由的节点上写 `-> Route[...]`，HarborFlow 就不会为该节点生成顺序出边，避免 `Command.goto` 与静态边叠加导致的困惑。([GitHub][7])

4. **构造 StateGraph**

   * `builder = StateGraph(state_schema=State, name="SimpleChat")`
   * （预留：未来可选传入 `context_schema`、checkpointer 等）。

5. **添加节点**

   * 对每个节点 `(name, fn)`：

     * 包装成 LangGraph 期望的节点函数（见 5.2）；
     * `builder.add_node(name, wrapped_fn)`。([LangChain 文档][5])

6. **添加边（顺序节点）**

   * 从 `@graph` 配置读取 `start`和`finish`；
   * `builder.add_edge(START, start)`；([Medium][8])
   * 遍历有序节点列表：

     * 如果当前节点是**顺序节点**，且下一个节点存在且是顺序/动态节点：

       * `builder.add_edge(cur, next)`；
     * 若当前节点是**动态节点**：

       * **不为其生成顺序出边**，完全由 `Route.goto` 控制。
   * 若存在 `finish != END` 的情况，暂不在 v1.0 支持自定义 finish 节点（避免过多概念），统一使用 LangGraph 的 `END` 作为终点。

7. **编译图并包装返回对象**

   * `compiled = builder.compile()`；([LangChain 文档][4])
   * 返回：

     * 简单实现：直接返回 `compiled`；
     * 或轻量包装为 `HarborCompiledGraph`，但只做极小程度的 API 透传和辅助方法（例如 `.inspect_nodes()`）。

### 5.2 节点包装逻辑

每个被 `@node` 标记的方法在添加到 `StateGraph` 前会被一个通用包装器包一层，统一处理返回值形态：

伪代码（架构级）：

```python
def wrap_node(fn, *, is_route_node: bool):
    def wrapped(state: State):
        result = fn(state)

        # 1) 动态路由节点：必须返回 Route
        if is_route_node:
            if isinstance(result, Route):
                # 转成 LangGraph Command
                return result.to_command()
            else:
                raise TypeError("节点声明为 Route 节点，但未返回 Route")

        # 2) 顺序节点：允许两种返回值
        if isinstance(result, Route):
            # 宽松支持：即便没写返回类型，也能用 Route
            return result.to_command()
        elif isinstance(result, dict):
            # 只表示“更新状态”，不改变路由 → 返回部分 state
            return result
        else:
            raise TypeError("节点必须返回 Route 或 dict")

    return wrapped
```

**关键 UX 点**：

* 对“纯顺序节点”，用户可以只返回 `dict`，完全不关心路由；
* 对“需要路由决定权”的节点，只需在返回类型写上 `-> Route[...]`，编译器就会自动当成动态节点，**不给它生成静态出边**，避免 LangGraph 中 `Command.goto + 静态边` 同时触发的隐性复杂度。([GitHub][7])

---

## 6. 运行时行为

### 6.1 顺序模式（只返回 dict）

* **图结构**：由 HarborFlow 在编译期生成一条**线性顺序边**（或少量分支）；
* **节点行为**：

  * 每个节点返回 `dict` 作为部分状态更新；
  * LangGraph 使用 reducer 或覆盖规则合并状态；([LangChain 文档][1])
  * 下一个节点由静态边决定，直到 END。

> 对用户来说，这种模式就像写一个 Python 类，方法按顺序执行，每个方法返回“增量状态”。

### 6.2 动态模式（返回 Route / Command）

* 当节点返回 `Route` 时：

  * HarborFlow 将其转换为 `Command(goto=..., update=...)`；([LangChain 文档][3])
  * LangGraph 根据 `goto` 跳转到指定节点（或 END），并应用 `update`；
  * 因为我们**不给 Route 节点生成静态出边**，避免了“静态边 + goto 同时生效”的混合语义。([GitHub][7])

> 这使得“返回即路由”在 HarborFlow 中语义非常直接：
> **你写的 `Route(goto=...)` 就是下一个节点，没有别的隐含路径。**

---

## 7. 错误处理策略（v1.0 最小版）

### 7.1 基本原则

* **不引入新的错误处理 DSL**；
* 完全依赖：

  * Python 异常机制；
  * LangGraph 在编译/运行时的错误反馈（例如无效节点、图结构错误等）。([LangChain 文档][5])

### 7.2 行为约定

1. **节点内部抛出的异常**

   * 透传给 LangGraph Runtime；
   * 调试时可以通过 LangGraph Studio / 日志查看调用栈。([Phase 2][6])

2. **HarborFlow 编译阶段错误**

   * 如：

     * `start` 节点不存在；
     * 节点返回类型标注为 `Route`，却返回了 `dict`；
   * 由 HarborFlow 抛出自定义异常（如 `HarborFlowConfigError`），错误信息包含：

     * 节点名、类名；
     * 建议修复方式（例如“若想使用顺序模式，请去掉返回类型 Route 标注”）。

3. **Type Hint 靠谱但非强制**

   * 若未写返回类型，但返回了 `Route`，仍然被视为动态路由（宽松支持）；
   * 只有在“写了 `-> Route` 却没返回 Route”时，才会强制抛错（避免静默歧义）。

---

## 8. 与 LangGraph 生态的集成

### 8.1 Streaming / Async / Interrupt / Checkpoint

* HarborFlow 的 `.compile()` 返回对象**应当遵循 LangGraph `CompiledStateGraph` 完整接口**：([LangChain 文档][4])

  * `invoke / ainvoke`
  * `stream / astream`
  * `get_graph`（用于绘图 / Studio）
* v1.0 不对这些方法做再包装，只保证：

  * 用户能在 HarborFlow 上**无缝调用 LangGraph 官方文档中的用法**；
  * 例如：

    ```python
    app = ChatFlow().compile()
    for step in app.stream({"messages": []}, stream_mode="values"):
        print(step)
    ```

### 8.2 LangGraph Studio / 可观测性

* 因为底层对象仍是 LangGraph 的图：

  * 用户可以使用 LangGraph Studio 打开 HarborFlow 编译出来的图；([Phase 2][6])
  * 也可以接入第三方 Tracer（如 Opik、LangSmith 等），HarborFlow 不做额外限制。([Comet][9])

---

## 9. 用户体验与心智模型

### 9.1 对开发者的“心智画面”

HarborFlow 期望开发者只记住**三个问题**：

1. **“我的状态长什么样？”** → 写好 `State`（TypedDict / Model）。
2. **“有哪些步骤（节点）？”** → 在类上用 `@node` 标出方法即可。
3. **“哪里需要分支/循环？”**

   * 不需要：节点返回 `dict`，按顺序执行；
   * 需要：返回 `Route(goto=..., update=...)`。

### 9.2 教程与文档建议（v1.0 基调）

* **官方示例与教程中：**

  * **统一写法**：节点示例全部使用 `Route` 返回值（哪怕只是简单 `Route(goto=next, update={...})`），以建立“返回即路由”的主心智模型；
  * 在“顺序模式”章节中再解释：“其实你也可以只返回 `dict`，这时 HarborFlow 帮你按类定义顺序接好边”。

* **API 设计上保留灵活性，但文档上给出“唯一推荐姿势”**，从而兼顾：

  * 初学者：照抄教程 → 全部是 Route 写法，心智简单清晰；
  * 进阶用户：读到“可以直接 `return {}`”时，会自然理解这是针对某些简单场景的捷径。

### 9.3 为什么保留 `compile()` / `invoke()` 二段式？

* **清晰的阶段界限**：

  * `compile()` 表示“图结构已固定，可以渲染、部署、共享”；
  * `invoke()` 表示“用某个初始状态运行一次图”；([LangChain 文档][4])
* **对接 LangGraph 工具链**：

  * Studio / 可视化 / 观测 都是围绕“已编译图”展开的；
  * 若直接提供 `run(initial_state)` 语法糖，反而会模糊这层概念，对调试不友好。
* **v1.0 强调“贴近 LangGraph 官方心智”**，而不是再做一套完全不同的运行入口。

---

## 10. V1.0 功能边界与后续演进方向

### 10.1 V1.0 明确包含

* 类级图声明：`@graph(state, start, finish=END, name=...)`
* 方法级节点声明：`@node`
* `Route` 类型：封装 LangGraph `Command`，支持 `goto + update` 模式；([LangChain 文档][3])
* 基于返回类型（是否 `Route`）推断节点是：

  * 顺序节点（有静态顺序边）；
  * 动态节点（仅靠 `Route.goto` 路由）。
* `.compile()` → 返回 LangGraph 编译后的图对象（或轻量包装）。

### 10.2 V1.0 明确不包含（但可能在 v1.x 引入）

* Guard / 条件守卫系统；
* 错误处理装饰器（统一错误路由节点）；
* 循环/步数限制检测；
* `context_schema` 及节点第二参数注入；
* 子图 / 嵌套图 的一等支持；
* 并行分支（`add_parallel_edges`）的语法糖。([LangChain 文档][5])

这些能力一旦加入，都会显著增加概念数量和文档长度。
在 v1.0 这个阶段，它们被有意识地**推迟**，以确保：

> **“如果你会写 Python 函数 + 会看一眼 LangGraph 文档，你就能在 5 分钟内上手 HarborFlow。”**

---
