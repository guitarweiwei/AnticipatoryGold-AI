## 2026-10-23 核验：全年收益研究被行情下载阻断

本节取代上文运行中/排队状态。最终观察 run https://github.com/guitarweiwei/AnticipatoryGold-AI/actions/runs/39792120041 （source 78f1def8312080e9b0f3dc78c1b01063b47bf4ea）Cancelled，3h0m25s，GitHub 注释明确 exceeded maximum execution time 3h0m0s。发生在 Acquire frozen warmup and complete 2024 quotes privately；normalize/native indicator export/replay 均未执行。故收益、回撤、胜率均未知，不是零，不存在可交付的真实收益图。

最后打印的完整进度：completed_hours=4500 / expected_hours=10248；DOWNLOADED=1108、EMPTY_HTTP200=500、HTTP_ERROR=1768、DOWNLOAD_OR_DECODE_ERROR=1124；elapsed_seconds=10619.734。4500是已返回任务数，不是有效行情覆盖；1608含空文件也不是可宣称的交易小时数。2892请求或解码失败，5748尚未在最后日志中计数。不能把周末或未知失败补零、插值或跳过后计算全年收益。

真实前置步骤通过：数据/参考模型故障测试3s，官方签名运行时准备57s，原生指标导出脚本真实编译3s；这些不等于运行指标脚本或收益回测。artifact reference-replay-39792120041-1 仅4.22KB，页面digest 670f01b85c5eeb5528e2b40d46f8c6738041fd617ea20fd9ea16418de240e3f8；本轮未下载，不声称重算hash。全量manifest仅下载结束后写入，超时未留下完整逐小时manifest；不能事后补造错误原因或断言所有HTTP_ERROR是503/限流。

先前39789059620在网络错误后人工停止改进有限恢复；39790714321因独立审计发现同日亏损基线反复重置而人工停止，两次均没有可用收益结果。日损已修复（same-day return，跨日费用后再测风险），独立风险审计复跑通过12项；新增native输入SHA和行数绑定。最终39792120041以4个源文件规范LF SHA固定实际运行代码。2026-10-23本地再次12/12 reference tests通过。不要将测试里的3个合成ticks作为市场数据。

当前具体阻断为不完整的历史bid/ask行情。大规模错误无法靠原先“小集合一次恢复”解决，单纯延长运行或循环重试不构成可验证修复。下一次应先取得合法完整的XAUUSD原始bid/ask tick导出（覆盖2023-11-01至2025-01-01 exclusive，UTC或提供时区规则、价格精度和合约信息），或建立获授权的稳定官方数据渠道，先小样本验证再执行固定全年窗口；不改变5000 USD/1:30或风险参数，不重选收益好的区间。费用仍为预注册研究假设，独立价格/时间校准仍待完成。若用户只提供2024，需另补热身数据或明确说明缺失，不能静默缩短窗口。

所有生产锁保留；不实盘、不合并。只有数据、native来源绑定、账本对账通过后才生成标明REFERENCE/非MT5 Strategy Tester的收益和回撤图。
