## 确认循环

### 1. 任务理解

* 为 harbor-flow 项目建立可“一键发布并同步 PyPI”的自动化工作流（参考现有 harborai 工作流）。

* 统一项目版本至 0.1.0 并完成一次正式发布（GitHub Release + PyPI 发布）。

* 发布流程可支持手动触发与基于标签触发，理想情况下使用 PyPI Trusted Publishing。

### 2. 已加载 / 需要加载的上下文

* 已有：

  * L1：项目规则声明三层分层与 Public API（project\_rules）。

  * 代码结构：`harborflow/__init__.py` 已导出 Public API（e:\project\harbor-flow\harborflow\__init_\_.py:1-13）。

  * 包配置：`pyproject.toml` 当前版本为 `0.0.1`，缺少 build-system（e:\project\harbor-flow\pyproject.toml:1-8）。

  * 现有工作流（针对 harborai 的模板）：

    * 完整发布：`release.yml`（e:\project\harbor-flow\.github\workflows\release.yml）

    * 简化发布：`simple-release.yml`（e:\project\harbor-flow\.github\workflows\simple-release.yml）

    * 最小化发布：`release-minimal.yml`、`release-minimal-safe.yml`

    * 测试：`test.yml`、`test-basic.yml`

  * 以上工作流多处使用 `harborai` 名称与目录，例如 `ls -la harborai/`、`pip install harborai==...` 等。

* 仍需：

  * PyPI 项目 `harborflow` 是否已启用 Trusted Publishing（OIDC）。如未启用，需要 `PYPI_API_TOKEN` 作为备用。

  * GitHub 环境是否已允许 `id-token: write`（用于 OIDC）。

  * 是否倾向使用 `setuptools` 还是 `hatchling` 作为构建后端（两者均可满足需求）。

### 3. 执行计划

* 步骤 1：对齐 packaging（构建后端与包发现）

  * 在 `pyproject.toml` 增加 `[build-system]`，默认使用 `setuptools`：

    * `requires = ["setuptools>=61.0", "wheel"]`

    * `build-backend = "setuptools.build_meta"`

  * 增加包发现配置：`[tool.setuptools.packages.find]`，`include = ["harborflow*"]`。

  * 将 `version` 调整为 `0.1.0`，与发布目标对齐。

* 步骤 2：调整发布工作流（以 `release.yml` 为主）

  * 将所有 `harborai` 文本替换为 `harborflow`，包括：

    * 目录检查：`ls -la harborflow/`

    * 包导入与语法检查：`python -m py_compile harborflow/__init__.py`、`python -c "import harborflow; ..."`

    * PyPI 页面链接：`https://pypi.org/p/harborflow`

    * 安装命令模板：`pip install harborflow==${VERSION#v}`

  * 发布到 PyPI：保留 `pypa/gh-action-pypi-publish@release/v1` 并启用 `id-token: write` 权限；如未启用 OIDC，则使用 `repository-url` + `PYPI_API_TOKEN` 作为回退方案。

  * 文档部署：使用条件判断防故障（`if: ${{ hashFiles('mkdocs.yml') != '' }}`）以避免没有文档配置时失败。

  * Docker 构建：保留但 `continue-on-error: true`，不会阻断发布流程。

* 步骤 3：简化与校验工作流

  * 对 `simple-release.yml` / `release-minimal*.yml` 进行同样的 `harborflow` 替换与最小校验调整，使其可手动/标签触发的预发布或实验发布也能工作。

* 步骤 4：版本与触发方式

  * 修改 `pyproject.toml` 版本为 `0.1.0` 并提交。

  * 触发发布选项：

    * 选项 A：推送标签 `v0.1.0`（触发 Release 工作流的 `push.tags`）。

    * 选项 B：通过 `workflow_dispatch` 手动输入 `version = v0.1.0` 触发。

* 步骤 5：发布与验证

  * 构建分发包（`python -m build`）并生成 `dist/*`。

  * 创建 GitHub Release（含自动生成的变更日志）。

  * 发布至 PyPI（或 TestPyPI 用于预发布测试）。

  * 验证：在独立环境运行 `pip install harborflow==0.1.0` 并执行基础导入测试：`python -c "import harborflow; print(harborflow.__all__)"`。

* 重点说明：

  * 本次改动不影响 Public API 的 L3 契约（未改动 API 行为）。

  * 需要同步变更的是 packaging 与工作流配置；代码实现与 Docstring 无需修改。

### 4. 影响范围与风险

* 影响模块：`pyproject.toml`、`.github/workflows/*`。不改动 `harborflow/*` 业务逻辑。

* 风险：

  * 缺少 `[build-system]` 会导致 `python -m build` 失败（通过新增配置解决）。

  * 未启用 PyPI Trusted Publishing 会导致发布失败（提供 `PYPI_API_TOKEN` 回退）。

  * 文档工作流若无 `mkdocs.yml` 会失败（通过条件判断规避）。

  * 现有 workflow 中仍引用 `harborai` 会导致目录检查或导入失败（全面替换为 `harborflow`）。

### 5. 用户决策

* 构建后端选择：`setuptools`（默认，成熟稳定）。

* PyPI 发布方式：优先 OIDC（Trusted Publishing）。

* 触发发布：推送标签 `v0.1.0` 或使用手动触发并输入 `v0.1.0`。

确认按以上方案执行，请：

* 更新 `pyproject.toml`（加入 build-system 与包发现；版本改为 0.1.0）。

* 修订 `release.yml` 等工作流以适配 `harborflow`。

* 提交并触发 `v0.1.0` 的发布流程，完成 GitHub Release 与 PyPI 同步，并在完成后给出验证结果与（可选）Diary 草稿。

