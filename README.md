# HarborFlow

基于 LangGraph v1.0 的轻量语法糖层，让“写图编排”退化为“写普通 Python 类与函数”。

## 为什么选择 HarborFlow

- 代码即图：使用 `@graph` 声明类、`@node` 声明方法，即可自动编译成可运行的状态图。
- 返回即路由：节点统一返回 `Route(goto=..., update=...)`，直接决定下一步与状态更新。
- **异步支持**：完整支持 `async/await`，同步和异步节点可混合使用。
- **高级功能**：条件路由、状态验证、错误处理、并行执行等现代工作流特性。
- 与 LangGraph 100% 兼容：编译后返回原生 `CompiledStateGraph`（或轻量包装），可直接 `invoke/stream/checkpoint`。
- 最小侵入与清晰心智模型：不重造底层运行时，只在 API 表面做减法，减少样板与心智负担。

## 安装

```bash
pip install harborflow
```

## 快速开始

以下示例展示如何用 HarborFlow 声明一张图并运行：

```python
from typing_extensions import TypedDict
from harborflow import graph, node, Route, END

class State(TypedDict):
    messages: list[tuple[str, str]]

@graph(state=State, start="agent", finish=END, name="SimpleChat")
class SimpleChat:
    @node
    def agent(self, state: State) -> Route:
        last = state["messages"][-1][1] if state["messages"] else "none"
        reply = f"echo: {last}"
        return {"messages": [("assistant", reply)]}

    @node
    def done(self, state: State) -> Route:
        return Route(goto=END, update={})

if __name__ == "__main__":
    app = SimpleChat().compile()
    result = app.invoke({"messages": [("user", "hello")]} )
    print(result)
```

## 高级功能示例

### 异步节点支持

```python
import asyncio
from harborflow import graph, node, Route, END, compile_graph_async

@graph(state=dict, start="async_processor", finish=END)
class AsyncWorkflow:
    @node
    async def async_processor(self, state):
        await asyncio.sleep(0.1)  # 异步操作
        return Route(goto=END, update={"result": "completed"})

# 异步编译和调用
async def main():
    flow = AsyncWorkflow()
    app = await compile_graph_async(flow)
    result = await app.ainvoke({"data": "test"})
    print(result)

asyncio.run(main())
```

### 条件路由

```python
from harborflow import ConditionalRoute

def smart_router(state: dict) -> ConditionalRoute:
    if state.get("urgent", False):
        return ConditionalRoute.when(
            lambda s: s.get("urgent", False),
            "fast_processor",
            priority=10
        )
    return Route(goto="normal_processor", update={})
```

### 错误处理和状态验证

```python
from harborflow import NodeConfig, validate_state_transition

# 配置节点超时和重试
node_config = NodeConfig(
    timeout=5.0,
    max_retries=3,
    retry_delay=1.0
)

# 验证状态转换
validate_state_transition(
    old_state, new_state,
    required_fields=["results"],
    immutable_fields=["id", "timestamp"]
)
```

## 动态路由示例（返回即路由）

```python
from harborflow import Route, END
from typing import Literal

def agent(state: dict) -> Route[Literal["tool", END]]:
    need_tool = state.get("need_tool", False)
    if need_tool:
        return Route(goto="tool", update={"messages": [("assistant", "using tool...")]})
    return Route(goto=END, update={"messages": [("assistant", "bye")]})
```

## 核心抽象

- `graph`：类级图声明装饰器，提供 `state`、`start`、`finish`、`name` 等配置，编译后返回 LangGraph `CompiledStateGraph`。
- `node`：方法级节点声明装饰器，节点函数应接收 `state` 并返回 `Route` 或 `dict`（顺序更新）。支持同步和异步函数。
- `parallel_node`：并行节点装饰器，标记可并行执行的节点。
- `Route`：动态路由+状态更新的统一返回对象，语义等价于 LangGraph `Command(goto, update)`。
- `ConditionalRoute`：条件路由，支持基于状态的动态分支和优先级控制。
- `NodeConfig`：节点配置，支持超时、重试和错误处理策略。
- `END`：LangGraph 的结束哨兵常量，表示流程结束。
- `compile_graph_async`：异步编译函数，支持包含异步节点的图编译。

## 设计原则（摘自架构与蓝图）

- 统一“返回即路由”心智模型：读节点函数的 `return` 即可读懂流程如何前进。
- 编译期尽可能多做事：自动推断节点类型（顺序/动态），为顺序节点生成静态边；动态节点不生成静态边，避免与 `goto` 混用。
- 保持 LangGraph 能力透明：`invoke/stream/ainvoke/checkpoint` 与 Studio/观测生态无缝对接。
- v1.0 边界：不内建 Guard/错误处理 DSL/复杂调度，只做极薄封装，保持可演进空间。

## API 速览

- `@graph(state, start, finish=END, name=...)`
- `@node(name=None)`
- `Route(goto: str|END, update: Mapping|Any)`
- `compile() -> CompiledStateGraph`
- 运行：`app.invoke(initial_state)` / `app.stream(...)` / `app.ainvoke(...)`

## 版本与发布

- 目标对齐 LangGraph `>= 1.0.0`。
- 使用 GitHub Actions + PyPI Trusted Publishing 自动发布。
- 版本语义：在功能稳定前以 `0.x` 迭代，小版本发布修复与小增强。

## 贡献指南

- 欢迎通过 Issue / PR 参与，建议基于 Docstring（L3）与测试协作，保持实现与契约一致。
- 重要行为变更请记录到 `specs/DEVELOPMENT_DIARY.md`（若启用）。

## 许可证

Apache-2.0