# 0. 仓库说明与 Harbor-spec 模式

- 本仓库是 **HarborFlow** 项目的源码，目标：
  - 在 LangGraph v1.0 之上提供一个更易用的、声明式的图编排层；
  - 对最终用户暴露极简 API：`graph`, `node`, `Route`, `END`, `HarborFlowError`, `ConfigError`。
- 本项目在 AI IDE 中启用了 **Harbor-spec 模式**：
  - 通用行为规范见全局 `role_rules`；
  - 本文件是本仓库的 **L1 宪法 / Project Rules**，声明：
    - 代码分层与依赖边界；
    - 本仓库的 L3 Docstring 模板（Python）；
    - Diary 文件位置与格式；
    - 在开发 HarborFlow 时，如何按 Harbor-spec 的方式进行 vibe coding。

---

# 1. 代码结构与分层（洋葱架构）

## 1.1 预期目录结构

```text
harborflow/
  __init__.py
  types.py        # 领域核心：Route / END / 错误类型
  decorators.py   # 开发者 UX：@graph / @node
  compile.py      # LangGraph 适配：类 → StateGraph.compile()
specs/
  DEVELOPMENT_DIARY.md   # HarborFlow 的行为变更记录（Diary）
tests/
  ...                    # 单元测试 / 集成测试
```

如果 IDE 尚未打开某个文件，而你需要阅读其中内容，请明确要求用户粘贴对应代码片段。

## 1.2 三层洋葱分层与依赖规则（硬约束）

分层结构：

```text
[最外层] harborflow.decorators
          ↓  只依赖 types / compile 的接口，不直接 import langgraph
[中  间] harborflow.compile
          ↓  只依赖 types；对 langgraph 进行适配
[最内层] harborflow.types
          ↓  只依赖 typing / dataclasses /
             langgraph.types.Command / langgraph.graph.END
       LangGraph v1.0 (StateGraph / Command / START / END)
```

依赖约束：

* 在 `harborflow.types` 中：

  * ✅ 可以用：`dataclasses` / `typing` / `langgraph.graph.END` / `langgraph.types.Command`；
  * ❌ 不允许 import `harborflow.compile` 或 `harborflow.decorators`；
  * ❌ 不允许直接使用 `StateGraph` / `START` 等 builder API。

* 在 `harborflow.compile` 中：

  * ✅ 可以用：`harborflow.types` 中的 `Route` / `ConfigError` / `END` 等；
  * ✅ 可以用：`langgraph.graph.StateGraph`, `START`, `END`, `langgraph.types.Command`；
  * ❌ 不允许 import `harborflow.decorators`。

* 在 `harborflow.decorators` 中：

  * ✅ 可以用：`from .types import Route, END, ConfigError`；
  * ✅ 可以用：`from .compile import compile_graph`；
  * ❌ 不允许直接 import `langgraph.*` 或操作 `StateGraph` / `Command`。

> 任何新增模块，都必须先决定它属于哪一层，并遵守“只能依赖内层，不依赖外层”的原则。

---

# 2. 本仓库的 L3 定义与范围

在 HarborFlow 项目中，**下列 Docstring 一律视为 L3 原子事实**（SSOT）：

1. `harborflow.types` 中：

   * `Route` 类及其关键方法（如 `to` / `finish` / `with_update` / `to_command`）的 Docstring；
   * `HarborFlowError` / `ConfigError` 的 Docstring；
2. `harborflow.decorators` 中：

   * `graph` 装饰器；
   * `node` 装饰器；
   * 可能存在的配置类（如 `GraphConfig`）；
3. `harborflow.compile` 中：

   * `compile_graph` 函数；
   * 节点收集 / 包装等对外可见辅助函数（如未来导出的 `_iter_nodes` / `_wrap_node` 若对用户有意义）。

当你修改上述任一函数 / 类的实现、语义或对外使用方式时：

* 必须视为 **L3 变更**；
* 必须在方案中同步更新对应 Docstring（完整可替换版本）；
* 必须考虑是否需要更新测试与 Diary（见后文）。

---

# 3. 本项目的 L3 Docstring 模板（Python）

> 这个模板是 HarborFlow 作为 Harbor-spec 参考实现时的“吃狗粮版本”，
> 适用于：`harborflow.types` / `harborflow.decorators` / `harborflow.compile` 中的 **Public API**。

## 3.1 适用范围

* **必须使用完整 L3 模板的对象**：

  * `Route` 及其关键方法；
  * `HarborFlowError` / `ConfigError`；
  * `graph` 装饰器；
  * `node` 装饰器；
  * `compile_graph`；
  * `__init__.py` 中通过 `__all__` 导出的其它 Public API（若有）。

* 内部辅助函数 / 私有工具（如以下划线开头）：

  * 可以使用简化 Docstring，但如果它们承载关键行为约束，也建议逐步补齐为完整模板。

## 3.2 标准 L3 模板（示例）

在 HarborFlow 中，你应优先使用下列模板结构（可按语义调整措辞，但字段名与结构尽量保持）：

```python
def compile_graph(flow_instance: object, *, check: bool = True, **compile_opts: object) -> "CompiledStateGraph":
    """将带 @graph/@node 元数据的实例编译为 LangGraph 应用。

    功能:
      - 解析 @graph 装饰的类实例，收集其中标记为 @node 的方法。
      - 基于节点定义顺序构建顺序执行链，并接入 LangGraph 的 START/END。
      - 将节点返回的 Route/Command/dict 适配为 LangGraph 可消费的 Command 或局部状态更新。

    使用场景:
      - 用户已经使用 @graph/@node 定义好一组节点类，希望快速得到可 .invoke/.stream 的 LangGraph 应用。
      - 不适合在此处做复杂的业务逻辑判断或跨服务调用，只负责“编译图结构”。

    依赖:
      - langgraph.graph.StateGraph
      - langgraph.graph.START / langgraph.graph.END
      - langgraph.types.Command
      - harborflow.types.Route
      - harborflow.types.ConfigError

    @harbor.scope: public
    @harbor.idempotency: once

    Args:
      flow_instance (object): 已使用 @graph 装饰的类实例，内部包含若干 @node 标记的方法。
      check (bool): 是否在编译前执行基础配置校验，例如 start 节点是否存在、是否至少有一个节点等。
      **compile_opts: 透传给 LangGraph .compile(...) 的可选参数，例如配置检查选项等。

    Returns:
      CompiledStateGraph: 已编译完成的 LangGraph 应用，通常具备 .invoke/.stream/.ainvoke 等方法。

    Raises:
      ConfigError: 当缺少 __hf_graph_config__、start 节点不存在、图中没有任何 @node 等配置异常时抛出。
    """
```

> 当你创建 / 修改上述 Public API 时，**必须以此模板风格为参照**，保证：
>
> * 功能 / 使用场景 / 依赖 / Args / Returns / Raises 信息完整；
> * `@harbor.scope` 与 `@harbor.idempotency` 标签语义正确；
> * 描述面向“库使用者”，而不是只面向库内部实现者。

---

# 4. Diary 文件与记录规则

## 4.1 Diary 位置

* 本仓库的 Diary 文件固定为：

```text
specs/DEVELOPMENT_DIARY.md
```

* 若该文件不存在，你可以建议用户创建，并给出初始化内容模板。

## 4.2 推荐 Diary 条目结构

当你判断一次改动值得记录（见下节），请给出类似以下结构的 Markdown 条目，供用户直接粘贴：

```markdown
## YYYY-MM-DD harborflow Route 行为调整 001

- 类型: feature | bugfix | refactor | chore | incident
- 模块: harborflow.types
- 文件: harborflow/types.py
- 函数: harborflow.types.Route.to
- 摘要: 简要说明本次变更的核心内容，例如“Route.to 不再接受某类非法 goto”。
- 变更原因:
  - 说明为什么要进行这次修改，例如对齐 LangGraph v1.0 语义或简化用户心智模型。
- 具体改动:
  - bullet1
  - bullet2
- 关联 Issue/PR: #xxx 或 N/A
- 是否可能是 Breaking Change: 是/否（如是，请简要说明对旧调用方的影响）
```

## 4.3 哪些改动在 HarborFlow 中“建议写 Diary”

尤其应当提醒写 Diary 的场景包括：

* 更改 `Route` 的字段含义 / 辅助构造方法的语义；
* 更改 `compile_graph` 如何处理节点返回值（例如增加 / 减少支持的返回类型）；
* 更改 `@graph` / `@node` 对用户可见的用法或参数含义；
* 改变 onion 分层的依赖结构（例如新增一个跨层依赖）；
* 任何会影响 HarborFlow 使用者写法 / 行为预期的修改。

---

# 5. 在本仓库中进行 vibe coding 时的默认策略

当用户在 HarborFlow 仓库中发起需求（新增功能 / 重构 / 修改行为等）时，你应在通用 `role_rules` 的基础上，自动套用本项目的约定：

1. **先分层定位**

   * 判断改动主要落在：

     * `types.py`（领域核心：Route / END / 错误类型）；
     * `decorators.py`（用户 UX：@graph / @node）；
     * `compile.py`（编译逻辑：类 → StateGraph）；
   * 检查是否会破坏洋葱分层依赖。

2. **L3 优先**

   * 对上述 Public API 行为改动：

     * 优先更新/补齐对应 Docstring（使用本项目 L3 模板）；
     * 然后给出实现修改方案。

3. **考虑测试与 Diary**

   * 对行为变更：

     * 提醒用户对应测试是否需要更新或补充；
     * 如改动影响库外部使用方式，应建议写 Diary，并给出条目草稿。

4. **提交前自检（用户显式请求时）**

   * 当用户贴出 diff 或说明“准备发版 / 提 PR”时：

     * 从 HarborFlow + Harbor-spec 的视角检查：

       * 是否破坏分层；
       * Public API 的实现与 Docstring 是否仍一致；
       * 是否缺失必要的 Diary 记录；
     * 给出清晰的 TODO 清单。

---

# 6. 一句话总结（给 AI 自己的提示）

> 在 harborflow 仓库里，你的首要职责是：
> 1）守住 `types / compile / decorators` 的洋葱分层；
> 2）对 `Route / graph / node / compile_graph` 这些 Public API，用 **严格的 L3 模板** 描述清楚行为；
> 3）在每次行为变更中，同时想到 “Docstring 有没有对齐？测试要不要补？Diary 要不要记？”。

只要遵守本 `project_rules` 与通用 `role_rules`，你就能用 Harbor-spec 的方式为 HarborFlow 写出**稳定且不易漂移**的规范与实现。

---