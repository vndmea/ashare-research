# 进度日志

## 会话：2026-07-07

### 阶段 1：开发计划细化与落盘
- **状态：** complete
- **开始时间：** 2026-07-07
- 执行的操作：
  - 盘点当前仓库未提交改动与新增模块
  - 阅读 README.md 了解项目当前定位与后续里程碑
  - 读取 planning-with-files-zh 技能说明与模板
  - 根据当前代码现状整理细化开发计划
  - 创建 task_plan.md、findings.md、progress.md
- 创建/修改的文件：
  - task_plan.md
  - findings.md
  - progress.md

### 阶段 1.1：规划文件审查与补强
- **状态：** complete
- 执行的操作：
  - 完整审查 task_plan.md、findings.md、progress.md
  - 识别当前阶段、依赖、风险、下一步建议和审查日志缺口
  - 更新 task_plan.md，使当前阶段推进到阶段 2，并补充依赖、风险与本周建议
  - 更新 findings.md，补充当前阻塞、文件审查结论和下一步建议
  - 更新 progress.md，记录本次审查与补强动作
- 创建/修改的文件：
  - task_plan.md
  - findings.md
  - progress.md

### 阶段 1.2：架构守则补充
- **状态：** complete
- 执行的操作：
  - 梳理当前项目如何在执行过程中防跑偏、防重复实现、防状态分裂
  - 将统一主流程、统一配置真源、统一状态对象等规则补入 task_plan.md
  - 在 findings.md 中记录本次架构防偏结论和新增约束理由
  - 在 progress.md 中追加本次补充动作
- 创建/修改的文件：
  - task_plan.md
  - findings.md
  - progress.md

### 阶段 1.3：长期扩展性与数据结构复审
- **状态：** complete
- 执行的操作：
  - 重新审视当前主流程、配置、回测、分析、实验模块
  - 判断当前架构是否具备长期扩展基础
  - 识别“流程架构强于数据架构”的现状
  - 将“数据契约与领域模型治理”补入 task_plan.md
  - 在 findings.md 中记录当前短板与长期扩展结论
- 创建/修改的文件：
  - task_plan.md
  - findings.md
  - progress.md

### 阶段 1.4：差距缩小专项计划补充
- **状态：** complete
- 执行的操作：
  - 评估当前项目与优秀工具、领先平台之间的主要差距
  - 将数据平台最小内核、交易账本、通用策略规格、实验复现体系并入长期规划
  - 在 task_plan.md 中加入差距缩小专项计划
  - 在 findings.md 中记录追赶主线和优先方向
- 创建/修改的文件：
  - task_plan.md
  - findings.md
  - progress.md

### 阶段 2：真实数据与回测补强执行
- **状态：** in_progress
- 执行的操作：
  - 已完成进入该阶段前的规划文件准备
  - 已补充执行期架构守则与红线
  - 已补充数据契约与领域模型治理要求
  - 新增 `src/ashare_research/contracts/schemas.py`，将官方 source/runtime DataFrame 结构落为统一 contracts 真源
  - 新增 `src/ashare_research/contracts/__init__.py`，暴露 contracts 模块入口
  - 将 `daily_bars.py`、`benchmarks.py`、`calendar.py`、`universe.py` 的输入字段约束与 contracts 对齐
  - 新增 `tests/test_contracts.py`，校验官方结构清单与 loader 字段约束一致
  - 已完成阶段 2 第一项“建立统一数据契约清单，明确官方 DataFrame 结构与字段语义”
  - 新增 `src/ashare_research/contracts/validation.py`，沉淀统一 source dataset 校验器
  - 强化 source loader，对空值、空字符串、非正价格、非负成交量等基础数据质量问题统一报错
  - 新增 `tests/test_source_validation.py`，补充字段错误与坏数据输入测试
  - 在 `src/ashare_research/pipeline/run.py` 中抽出统一研究输入加载入口与输入摘要能力
  - 在 `src/ashare_research/cli.py` 中新增 `ashare-validate-data` 预检命令
  - 在 README 中补充最小真实数据接入与验证链路：`download_guidebee_data.py -> ashare-validate-data -> ashare-run-backtest`
  - 在 `load_research_inputs()` 中补充跨表输入对齐校验，覆盖 `bars / trading_calendar / benchmark_returns / universe`
  - 新增跨表日期错位与 universe 越界测试，确保输入错位会在回测前失败
  - 扩展 `BacktestConfig`，补入 `slippage_rate` 与 `max_volume_participation`
  - 为回测结果补入 `execution_diagnostics` 与 `trade_ledger`
  - 将执行诊断与交易账本纳入统一报表输出和中文看板展示
  - 将 `StrategyConfig` 升级为通用 `parameters` 模型，策略注册表增加元信息
  - 新增 `relative_strength` 策略及其配置模板 `configs/relative_strength.yaml`
  - 将 `experiments/sweep.py` 升级为通用参数网格扫描，并写出 sweep manifest
  - 实际验证 `configs/relative_strength.yaml` 单次回测和通用 sweep CLI 路径均可运行
  - 新增 `src/ashare_research/data/manifest.py`，并让样例数据生成和 Guidebee 下载写出 `dataset_manifest.json`
  - 新增 `governance.md`，固化字段契约变更流程、模块边界、数据版本追溯和指标分层
  - 扩展报表层，补入持仓贡献、换手拆解和成本拆解
  - 扩展看板，增加实验结果对比视图和新报表入口
- 创建/修改的文件：
  - src/ashare_research/contracts/__init__.py
  - src/ashare_research/contracts/schemas.py
  - src/ashare_research/data/daily_bars.py
  - src/ashare_research/data/benchmarks.py
  - src/ashare_research/data/calendar.py
  - src/ashare_research/data/universe.py
  - src/ashare_research/contracts/validation.py
  - src/ashare_research/pipeline/run.py
  - src/ashare_research/cli.py
  - src/ashare_research/backtest/accounting.py
  - src/ashare_research/backtest/engine.py
  - src/ashare_research/risk/tradeability.py
  - src/ashare_research/experiments/sweep.py
  - src/ashare_research/strategies/registry.py
  - src/ashare_research/strategies/relative_strength.py
  - src/ashare_research/strategies/moving_average.py
  - src/ashare_research/analysis/reports.py
  - src/ashare_research/data/manifest.py
  - dashboard.py
  - pyproject.toml
  - configs/backtest.yaml
  - configs/relative_strength.yaml
  - governance.md
  - tests/test_contracts.py
  - tests/test_source_validation.py
  - tests/test_pipeline.py
  - tests/test_config.py
  - tests/test_experiments.py
  - tests/test_backtest_smoke.py
  - tests/test_tradeability.py
  - README.md
  - task_plan.md
  - findings.md
  - progress.md

## 测试结果
| 测试 | 输入 | 预期结果 | 实际结果 | 状态 |
|------|------|---------|---------|------|
| 规划文件创建 | 项目根目录 | 生成可持续维护的计划文件 | 已生成 task_plan.md、findings.md、progress.md | 通过 |
| 规划文件审查 | 三个规划文件 | 找出是否需要细化和补充 | 已识别并补齐主要缺口 | 通过 |
| 架构守则补充 | 规划文件 | 增加防跑偏、防重复、防状态分裂约束 | 已补入 task_plan.md 与 findings.md | 通过 |
| 长期扩展性复审 | 中轴模块与规划文件 | 判断架构和数据结构是否适合长期扩展 | 已补入数据契约与领域模型治理要求 | 通过 |
| 差距缩小专项计划 | 规划文件 | 增加面向优秀/领先工具的追赶路线 | 已补入 task_plan.md 与 findings.md | 通过 |
| contracts/schemas 落地 | 核心 DataFrame 官方结构清单 | 将字段契约从隐式约定升级为代码内统一真源 | 已新增 contracts 模块并补充测试 | 通过 |
| contracts 一致性验证 | pytest | contracts 与 loader 字段约束保持一致 | 32 passed | 通过 |
| contracts 编译检查 | compileall | 新增模块可正常编译 | 通过 | 通过 |
| source 数据坏输入校验 | pytest | source loader 对字段错误与坏值快速失败 | 38 passed | 通过 |
| 数据预检命令 | `ashare-validate-data --config configs/backtest.yaml` | 输出统一输入摘要并成功通过 | 已输出 validation_status、bar_rows、symbol_count 等摘要 | 通过 |
| 跨表输入对齐校验 | pytest | bars、calendar、benchmark、universe 日期/股票池错位时快速失败 | 41 passed | 通过 |
| 通用策略/执行诊断/实验升级 | pytest | 通用参数模型、相对强弱策略、执行诊断、trade ledger、sweep manifest 均可回归 | 46 passed | 通过 |
| 相对强弱策略 CLI 运行 | `ashare-run-backtest --config configs/relative_strength.yaml` | 输出报告并打印结果路径 | 已生成 tmp_relative_strength 报告目录 | 通过 |
| 通用参数 sweep CLI 运行 | `ashare-run-backtest --config configs/relative_strength.yaml --sweep-parameter ...` | 输出 summary 与 manifest | 已生成 tmp_sweep 目录和 manifest | 通过 |
| 数据 manifest 追溯 | 样例数据生成 / Guidebee 下载 | 生成 dataset_manifest.json | 已落地 | 通过 |
| 治理文档落盘 | README / governance.md | 记录变更流程、模块边界、追溯与分层 | 已落地 | 通过 |
| 持仓贡献 / 换手拆解 / 成本拆解 | pytest | 新报表生成兼容旧数据和新数据 | 46 passed | 通过 |
| 看板实验对比 | 浏览器页面 | 参数扫描结果可排序查看 | 已接入 | 通过 |

## 错误日志
| 时间戳 | 错误 | 尝试次数 | 解决方案 |
|--------|------|---------|---------|
| 2026-07-07 | Get-ChildItem -Filter 误传数组导致 PowerShell 报错 | 1 | 不再用数组传 -Filter，改为直接创建规划文件 |
| 2026-07-07 | 桌面版 apply_patch 临时执行链路访问被拒绝 | 1 | 改用本地文件写入兜底，并记录为环境限制 |

## 五问重启检查
| 问题 | 答案 |
|------|------|
| 我在哪里？ | 阶段 2 持续推进中，阶段 3、4、6 的高优先级编码底座也已落地 |
| 我要去哪里？ | 下一步主要只剩真实供应数据默认接入和最终版本摘要确认 |
| 目标是什么？ | 将项目推进为可扩展的真实 A 股日频研究平台 |
| 我学到了什么？ | 当前最有价值的增强是沿着统一主流程补共享产物、追溯元数据和治理文档，而不是继续堆平行页面或局部脚本 |
| 我做了什么？ | 已完成计划细化、文件落盘、contracts/schema 与校验器落地、数据预检与跨表对齐、滑点与容量约束、执行诊断与交易账本、通用策略参数模型、第二策略样本、通用 sweep manifest、数据 manifest、治理文档、持仓贡献/换手拆解和中文看板实验对比 |

---
*每个阶段完成后或遇到错误时更新此文件*
