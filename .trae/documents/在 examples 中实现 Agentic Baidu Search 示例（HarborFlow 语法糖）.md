# 确认循环

## 1. 任务理解
- 在 `e:\project\harbor-flow\examples` 新增一个使用 HarborFlow 语法糖的“agentic search”示例。
- 示例通过百度千帆 AppBuilder Web Search（`https://qianfan.baidubce.com/v2/ai_search/web_search`）进行检索。
- 使用用户提供的 API Key，但不在代码中明文硬编码，改为读取环境变量以符合安全最佳实践。

## 2. 已加载 / 需要加载的上下文
- 已有：
  - L1（Project Rules）：三层洋葱分层与依赖规则；示例不修改库代码，仅新增示例文件。
  - L2：`examples/simple_chat.py` 的示例结构与风格；`harborflow.decorators` 的 `graph`/`node`；`harborflow.types` 的 `Route`/`END`。
  - L3：不改动库的 L3；示例将遵循库既有契约（节点返回 `Route.to/finish`、编译为 LangGraph）。
- 仍需：
  - 用户确认以环境变量 `APPBUILDER_API_KEY` 提供密钥（值为您提供的 key）。
  - 是否需要固定 `resource_type_filter.top_k`、`search_recency_filter`、`search_filter.site` 等默认策略。

## 3. 执行计划
- 步骤 1：新增 `examples/agentic_baidu_search.py`，定义 `State`（如 `query: str`, `references: list`, `summary: str`）。
- 步骤 2：用 `@graph(state=State, start="decide", finish=END)` 声明图类 `AgenticSearch`，并在类上注入 `.compile()`。
- 步骤 3：实现节点：
  - `decide(state)`: 根据 `query` 选择是否发起搜索，路由到 `search_baidu`。
  - `search_baidu(state)`: 使用标准库 `urllib.request` 以 POST 调用百度千帆搜索 API，读取环境变量 `APPBUILDER_API_KEY` 构造 `X-Appbuilder-Authorization: Bearer ...`，返回 `Route.to("summarize", references=...)`。
  - `summarize(state)`: 汇总 `references`（提取 `title`/`url`/`content`），生成 `summary` 文本，`Route.finish(summary=...)`。
- 步骤 4：在 `__main__` 中编译并演示 `invoke`，示例查询可用“北京有哪些旅游景区”。
- 步骤 5：不引入第三方依赖；如密钥缺失，节点抛出清晰错误；对超时/网络错误做最小健壮处理。

### 契约对齐（L3）
- 不修改库的 L3；示例的节点 Docstring 简要标注输入输出与异常，保持与 `Route` 契约一致（返回 `Route` / 局部状态更新）。

### 测试与验证
- 运行示例脚本进行集成验证；如需，后续可在 `tests/` 添加最小模拟测试（但本次不改动测试目录）。

## 4. 影响范围与风险
- 影响：仅新增示例文件，不影响库模块与现有测试。
- 风险：
  - 外部网络依赖与速率/额度限制（每日免费额度与最大调用次数）；
  - 密钥管理与泄露风险（采用环境变量降低风险）。
  - 响应结构变化导致解析失败（做最小结构健壮性）。

## 5. 需要用户决策
- 是否接受通过环境变量 `APPBUILDER_API_KEY` 注入密钥（推荐，值为您提供的 key）。
- 默认搜索参数：`top_k=10`、`search_recency_filter="year"`、是否固定 `search_filter.site=["www.weather.com.cn"]`（默认不固定站点）。
- 示例输出详细度：`summary` 仅标题与链接，还是包含简短摘要（默认包含简短摘要）。

请确认以上方案后，我将直接落盘实现示例文件，并给出运行与验证说明。