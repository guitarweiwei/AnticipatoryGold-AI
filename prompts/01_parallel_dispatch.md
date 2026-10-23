# 主 Agent：阶段 1 并行任务分派指令

在已完成初始审查、且用户批准计划后执行。为每项任务创建独立分支或 Git worktree，禁止共用工作目录并发编辑同一文件。

A. strategy-researcher（只读）：审查策略语义、参数单位、无未来数据规则；交付 `docs/STRATEGY_SPEC.md`，不写交易执行代码。
B. ai-api-engineer：只负责 `mac_ai/` 与 API 单元测试；不得改 `docs/API_CONTRACT.json`，若必须改先提出提案。
C. macro-data-engineer：只负责 `macro/` 或 `config/` 下数据适配器、样例和测试；不得声称 CSV 是实时行情。
D. mql5-engineer：只负责 MQL5 EA；严格依赖冻结接口；先修 P0，保留 live trading disabled。
E. backtest-engineer：只写测试、测试脚本和报告模板；不可调整策略参数以美化结果。
F. risk-auditor：只读独立审查，针对基线与各 PR 提交 Critical/High/Medium/Low findings，不负责自己修复后自我批准。

主 Agent：
1. 等独立任务完成后逐一检查 diff、测试命令、失败日志和文件冲突。
2. 风险审计必须由未实现该功能的 Agent 执行。
3. 不自动合并 PR。先汇总差异与测试结果，请用户批准，再合并。
4. 每次整合后重新跑全部可用测试；MetaEditor 编译和 MT5 回测需 HP Windows 上的真实日志。
5. 若 Agent 不能运行 Windows 专用测试，记录 NOT RUN，不得伪造通过。
