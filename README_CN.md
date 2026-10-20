# AnticipatoryGold AI v1：研究开发版，交易锁定

已导入原始附件，并按策略、MQL5、AI API、宏观数据、回测、独立风险审计六项职责完成首轮安全修复。

**当前不能交易，也不是已完成的可交易版本。** 普通终端初始化被禁止；即使在 Strategy Tester 内，新开仓也被硬锁。在线 EA→API 接口为明确拒绝的占位函数。没有启用实盘或模拟盘。

保留全部原始 EA 输入参数和数值默认值；按用户“直接实施下一阶段”的授权，实现2倍已收盘M5 ATR止损、止损距离定仓及持久化停机的研究源码；原有风险上限不变。

Stage2测试套件包括10项EA源码检查、22项独立Python风险政策案例、10项宏观和62项模拟API测试，共104项；实际执行状态见docs/VALIDATION_RESULTS.md。另有 1 项上游依赖弃用警告。未调用付费模型。MetaEditor 编译、MT5 回测和收益指标均为 NOT RUN。

止损与持久化规则已获实施授权，详见docs/DECISIONS_REQUIRED.md及MQL5/STAGE2.md；尚缺真实券商成本、成交核对和Windows证据，交易锁继续保留。待解决项与发布阻断条件见 docs/DEFECT_REGISTER.md 和 docs/RISK_REVIEW.md。请勿绕过新开仓锁获取收益数据。

执行安装和离线检查请参阅 README.md；此 PR 仅供审查，不自动合并。
