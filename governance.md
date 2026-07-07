# 治理清单

## 目标
让 A 股研究平台在继续扩展时，始终沿着同一条主流程和同一套字段契约演进，避免功能各自为战、状态分裂和重复实现。

## 字段契约变更流程
1. 先更新 `src/ashare_research/contracts/schemas.py`。
2. 再复用 `src/ashare_research/contracts/validation.py` 的校验器。
3. 然后让 loader、pipeline、backtest、analysis、dashboard 共享同一字段名。
4. 最后补测试，确保新字段不是只在某个模块里“碰巧可用”。

## 最小变更检查清单
- 是否接入统一主流程 `src/ashare_research/pipeline/run.py`。
- 是否进入 `ResearchConfig` 或其可扩展参数模型。
- 是否写入 contracts 并有校验。
- 是否复用统一报表链路。
- 是否引入平行状态、平行指标计算或平行结果格式。

## 模块边界
- `data/` 只负责加载、校验、标准化和数据元信息。
- `strategies/` 只负责信号生成和策略元信息。
- `backtest/` 只负责撮合、执行约束、执行诊断、交易账本和净值演化。
- `analysis/` 只负责指标、归因和报表导出。
- `dashboard.py` 只负责展示，不重算核心结果。
- `experiments/` 只负责批量运行、汇总和复现产物。

## 数据版本追溯
- 每次样例数据生成或 Guidebee 下载后都应写入 `data/raw/dataset_manifest.json`。
- manifest 至少记录：来源名称、创建时间、日期范围、symbol 数量、文件行数、字段列表和来源细节。
- 当真实供应链切换时，优先更新 manifest 和数据下载脚本，不要先在下游模块里补丁式兼容。

## 指标分层
- 研究指标：收益、波动、回撤、换手、暴露、归因。
- 上线前验证指标：执行诊断、交易账本、容量限制、滑点、不可交易阻塞原因。
- 看板可以同时展示两类，但不要混成一套口径。

## 版本边界
- 阶段完成后必须更新 `task_plan.md`、`findings.md`、`progress.md`。
- 任何一次较大改动前先查看这份清单。
- 如果改动会引入第二套状态或第二条数据流，先停下来重构，而不是继续叠代码。
