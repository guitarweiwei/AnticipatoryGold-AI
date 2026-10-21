> **2026-10-21 latest:** Genuine signed MetaEditor 5.0.0.6274 compilation PASSED: **0 errors, 0 warnings**, fresh EX5 hash recorded. Authorized offline initialization generated the official standard library; firewall and process exit verified. Backtest/EA execution remain NOT RUN; all trading locks and risk limits remain unchanged. Earlier compilation failures below are historical. See [Windows evidence](tests/windows/CLOUD_COMPILE.md).

# AnticipatoryGold AI v1：研究开发版，交易锁定

用户已授权实施第1–3项：数据有效性、订单持久化与成交核验、篮子盈亏及费用预算。六个Agent分别负责策略、MQL5、API、宏观、验证和独立审计。

**当前仍不能交易。** 普通终端初始化禁止；Strategy Tester中新单也保持硬锁；在线EA/API仍明确否决。没有合并或启用实盘／模拟盘。

本轮研究源码包括：CSV2贯穿原始来源时间和日历有效期，API1.1统一前后校验并拒绝旧协议；完整已收盘OHLC与指标有效性检查；发送前持久化订单意图及已消费K线；订单／成交／仓位／止损核验；部分成交及重启不明状态停机；保留已平仓交易的篮子现金账本、保守费用分项和归档。

未来手续费及隔夜费没有可信券商上界，因此成本结构保持unknown，独立成本否决不解除。未虚构费用或调整现有35项输入／风险政策。旧AG2作用域缺少新执行日志会拒绝初始化，不静默迁移或清除停机记录。

当前测试套件175项：18项源码检查、45项Python参考案例、15项宏观和97项模拟API测试。实际结果见docs/VALIDATION_RESULTS.md。源码检查与独立参考模型不是MQL5执行证明。Windows PowerShell安装／编译脚本已实际执行，签名有效的MetaEditor 5.0.0.6274真实编译失败：1错误、0警告，缺官方Include/Trade/Trade.mqh，尚无成功EX5。见tests/windows/CLOUD_COMPILE.md。MT5回测、真实模型／券商／存储故障验证仍NOT RUN。

完整实现与剩余放行条件见docs/STAGE3_IMPLEMENTATION.md。请勿绕过交易锁获取收益数据；本PR保持Draft供审核。
