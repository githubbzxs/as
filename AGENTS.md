# AGENTS.md

## 部署

- 合适时调用 `skill:deploy`。
- 默认部署目标：DO 最小杯伦敦（`144.126.234.61`，`root@22`）。

### 部署信息（供 `skill:deploy` 使用）

- 香港：
  - ip：`103.52.152.92`
  - 密码：`DGA7PMU5WmBQ`
  - ssh 信息：`root@22`
- DO 最小杯伦敦：
  - ip：`144.126.234.61`
  - 密码：`cb7989f02d835a430437675e87!`
  - ssh 信息：`root@22`
- 大陆：
  - ip：`106.15.59.92`
  - 密码：`486QWQqwq`
  - ssh 信息：`Administrator@22`

## Facts

- **[2026-02-20] 监控指标精简（按产品口径）**：`MetricsSummary` 与前端卡片已移除 `free_usdt`、`inventory_usage_ratio`，仅保留权益与库存名义等核心展示。
  - Impact：`backend/app/schemas.py`、`backend/app/services/monitoring.py`、`frontend/src/App.jsx`、`backend/tests/test_monitoring_metrics.py`

- **[2026-02-20] 成交执行参数回归“激进成交优先”**：`strategy -> runtime` 映射固定注入成交优先参数（更窄价差、更快重挂、更短 TTL）。
  - Impact：`backend/app/services/strategy_mapper.py`、`backend/app/schemas.py`、`backend/tests/test_strategy_mapper.py`

- **[2026-02-20] taker 平仓链路补齐量化与残量处理**：平仓下单改为按交易对步长量化（reduce-only 向下量化），并在低于最小平仓量时抛出残量异常供引擎终止重试。
  - Impact：`backend/app/exchange/base.py`、`backend/app/exchange/grvt_live.py`、`backend/app/engine/strategy_engine.py`、`backend/tests/test_grvt_order_size_quantize.py`、`backend/tests/test_strategy_engine_close.py`

- **[2026-02-20] HYPE 交易对接入**：策略配置与前端交易对选项新增 `HYPE_USDT_Perp`，与现有 `BNB/XRP/SUI` 同口径管理。
  - Impact：`backend/app/schemas.py`、`frontend/src/App.jsx`、`backend/tests/test_goal_api.py`、`backend/tests/test_strategy_mapper.py`、`backend/tests/test_runtime_config.py`

- **[2026-02-20] 下单量约束解析增强**：交易对约束解析新增 CCXT 风格字段兼容（`limits.amount.min`、`precision.amount`、`info.*`），并补齐多交易对量化回归测试。
  - Why：修复 `XRP/SUI` 场景下元数据命中不足导致的粒度拒单。
  - Impact：`backend/app/exchange/grvt_live.py`、`backend/tests/test_grvt_order_size_quantize.py`

- **[2026-02-20] 库存占比口径切换为可用资金杠杆口径**：单边触发与库存上限运行时口径已改为 `free_usdt * effective_leverage`，不再直接使用 `equity` 作为分母。
  - Why：修复小本金高杠杆场景（如 8u*50x）下“权益占比”与实际可开仓能力脱节的问题。
  - Impact：`backend/app/engine/strategy_engine.py`、`backend/app/exchange/grvt_live.py`、`backend/app/models.py`、`backend/app/schemas.py`

- **[2026-02-20] 账户资金快照接口新增**：交易所适配层新增 `fetch_account_funds`，统一返回 `equity/free/used/source`，并保留 `fetch_equity` 兼容路径。
  - Impact：`backend/app/exchange/base.py`、`backend/app/exchange/grvt_live.py`、`backend/tests/test_grvt_funds_snapshot.py`

- **[2026-02-20] 监控新增可用资金口径指标**：摘要与诊断新增 `free_usdt`、`effective_capacity_notional`、`inventory_usage_ratio`、`effective_liquidity_k`。
  - Impact：`backend/app/services/monitoring.py`、`backend/app/schemas.py`、`frontend/src/App.jsx`

- **[2026-02-20] 参数入口切换**：前后端新增 `StrategyConfig`（`/api/config/strategy`），WebUI 已从“目标交易量模式”切换为“交易对 + AS 三参数(gamma/sigma/k) + 两项风控（最大回撤/最大库存占比）”。
  - Impact：`backend/app/schemas.py`、`backend/app/api/config.py`、`backend/app/services/runtime_config.py`、`backend/app/services/strategy_mapper.py`、`frontend/src/App.jsx`

- **[2026-02-20] 重挂防抖落地**：新增 `min_order_age_before_requote_sec`（默认 `1.0s`）与 side 级别局部换单，替代“全撤全挂”。
  - Why：修复“0.x 秒频繁撤挂导致难成交”的问题，同时尽量保持双边在簿连续性。
  - Impact：`backend/app/engine/strategy_engine.py`、`backend/app/schemas.py`

- **[2026-02-20] 单边触发口径变更**：单边挂单由“库存名义倍数阈值”改为“`abs(inventory_notional)/equity` 阈值”，并加入滞回回切（恢复阈值）。
  - Impact：`backend/app/engine/strategy_engine.py`、`backend/app/schemas.py`

- **[2026-02-19] 项目目标**：交付 GRVT 做市实盘首版，范围仅下单、监控、API Key 配置，不含回测模块。
  - Impact：`backend/`、`frontend/`

- **[2026-02-19] 首版交易范围**：USDT 永续，当前默认交易对为 `BNB_USDT-PERP`。
  - Impact：`backend/app/schemas.py`

- **[2026-02-19] 参数交互形态**：WebUI 改为“三旋钮自动模式”（做市激进度/库存容忍度/风险阈值），后端自动映射到运行参数。
  - Impact：`backend/app/services/profile_mapper.py`、`frontend/src/App.jsx`

- **[2026-02-19] 实盘默认策略**：交易环境固定为 `prod`，前后端已移除 `mock` 开关与 Mock 适配器。
  - Impact：`backend/app/services/exchange_config.py`、`backend/app/exchange/factory.py`、`frontend/src/App.jsx`

- **[2026-02-19] 告警配置入口**：新增 Telegram 配置持久化与 API（Bot Token/Chat ID），支持 WebUI 配置且密钥不回显。
  - Impact：`backend/app/services/telegram_config.py`、`backend/app/api/config.py`、`frontend/src/App.jsx`

- **[2026-02-19] 部署目标切换**：新增伦敦机作为当前默认部署目标，香港机保留为历史环境。
  - Impact：部署流程、运维排障路径

- **[2026-02-19] GRVT 交易对格式兼容**：适配器已兼容 `-PERP/_PERP/_Perp`，统一归一到 `_Perp` 后再调用交易所接口。
  - Why：避免因旧配置（如 `BNB_USDT-PERP`）导致行情接口 400、引擎看似“启动无反应”。
  - Impact：`backend/app/exchange/grvt_live.py`、`backend/app/schemas.py`、`backend/tests/test_grvt_symbol_normalize.py`

- **[2026-02-19] 成交诊断指标落地**：监控摘要新增盘口距离、1分钟成交/撤单、在簿时长分位数、重报价原因，并新增对应时序曲线。
  - Impact：`backend/app/schemas.py`、`backend/app/services/monitoring.py`、`backend/app/engine/strategy_engine.py`、`frontend/src/App.jsx`

- **[2026-02-19] 启动挂单行为更新**：引擎启动后不再经过 readonly 预热，直接进入 running 并执行挂单同步。
  - Why：避免启动后长时间“看起来无挂单”，缩短到首轮有效挂单的时间。
  - Impact：`backend/app/engine/strategy_engine.py`、`backend/tests/test_strategy_engine_startup.py`

- **[2026-02-19] 成交诊断展示调整**：前端已移除“成交诊断”面板，仅保留核心运行卡片、曲线与订单/成交表。
  - Why：按产品要求简化界面，降低非必要诊断噪声。
  - Impact：`frontend/src/App.jsx`、`frontend/src/styles.css`

- **[2026-02-19] 挂单失败根因修复**：`client_order_id` 由超长数字改为 18 位短数字，避免交易所侧重复判定导致持续拒单。
  - Why：线上出现持续 `400 code=2013 (Client Order ID repeats with the last order)`，引擎运行但始终无在簿挂单。
  - Impact：`backend/app/engine/strategy_engine.py`、`backend/tests/test_strategy_engine_requote.py`

- **[2026-02-19] 最小下单量保护**：运行时新增 `min_order_size_base` 下限保护，避免小资金账户下单量低于交易所最小限制。
  - Why：线上出现持续 `400 code=2062 (Order size smaller than min size)`，导致引擎运行但无有效挂单。
  - Impact：`backend/app/schemas.py`、`backend/app/engine/strategy_engine.py`、`backend/tests/test_strategy_engine_startup.py`

- **[2026-02-19] 价格刻度对齐保护**：报价下发前按盘口推断 tick 对价格量化，避免无效价格刻度导致拒单。
  - Why：线上出现持续 `400 code=2064 (Invalid limit price tick)`，即使下单量已达标也无法在簿。
  - Impact：`backend/app/engine/strategy_engine.py`、`backend/tests/test_strategy_engine_startup.py`

- **[2026-02-19] 停止/熔断平仓策略升级**：引擎 `stop/halt` 均改为“先撤单，再 taker 立即平仓”，平仓失败按指数退避无限重试直到仓位归零。
  - Why：避免“状态已停但持仓未清”导致尾部风险残留。
  - Impact：`backend/app/engine/strategy_engine.py`、`backend/app/exchange/base.py`、`backend/app/exchange/grvt_live.py`、`backend/tests/test_strategy_engine_close.py`

- **[2026-02-19] 指标口径增强**：监控摘要新增运行时长、累计成交笔数、累计交易量、总/日 PnL、手续费返佣/成本拆分，成交表新增 `fee_side`。
  - Why：解决“PnL/余额/手续费读数可解释性不足”和手续费正负号混淆。
  - Impact：`backend/app/services/monitoring.py`、`backend/app/schemas.py`、`backend/app/api/monitor.py`、`backend/tests/test_monitoring_metrics.py`

- **[2026-02-19] 库存上限权益联动**：运行时库存阈值支持 `max_inventory_notional_pct`，按 `equity * pct` 动态计算，固定名义值作为兼容兜底。
  - Why：修复固定名义阈值与账户权益脱节的问题。
  - Impact：`backend/app/schemas.py`、`backend/app/services/profile_mapper.py`、`backend/app/engine/strategy_engine.py`

- **[2026-02-19] 告警规范化与心跳**：Telegram 告警改为标准模板（等级/事件/详情），支持关键事件必发与可配置心跳摘要。
  - Impact：`backend/app/services/alerting.py`、`backend/app/engine/strategy_engine.py`、`backend/data/runtime_config.json`

- **[2026-02-19] 前端参数面板升级**：保留三旋钮自动模式，新增“高级参数（全量可调）”折叠面板，并为每个参数展示含义与调参影响。
  - Impact：`frontend/src/App.jsx`、`frontend/src/styles.css`

- **[2026-02-19] 参数交互彻底简化**：前端已切换为“目标参数极简模式”（本金/目标小时交易量/风险档位），移除高级参数入口。
  - Why：用户反馈参数过多难以调整，需要 user-friendly 的单入口配置。
  - Impact：`frontend/src/App.jsx`、`frontend/src/api.js`

- **[2026-02-19] 目标配置模型落地**：后端新增 `GoalConfig` 与 `/api/config/goal`，并把 `runtime_config.json` 升级为 `runtime_config + goal_config` 双配置结构。
  - Impact：`backend/app/schemas.py`、`backend/app/services/runtime_config.py`、`backend/app/services/goal_mapper.py`、`backend/app/api/config.py`、`backend/data/runtime_config.json`

- **[2026-02-19] 成交目标闭环新增**：引擎加入 60 秒节拍的成交量目标调节器（按最近 1 小时成交量偏差微调价差/循环间隔，单次 10% 限幅）。
  - Impact：`backend/app/engine/strategy_engine.py`、`backend/app/services/monitoring.py`、`backend/app/schemas.py`

- **[2026-02-19] 简化回测子系统新增**：新增 CSV 数据回放引擎、异步任务服务、CLI 与 API 查询接口。
  - Impact：`backend/app/backtest/engine.py`、`backend/app/backtest/service.py`、`backend/app/backtest/run.py`、`backend/app/api/backtest.py`、`backend/app/main.py`、`backend/app/core/container.py`

- **[2026-02-19] 达成率主口径切换**：监控与前端主展示改为“启动累计达成率”（按启动后累计成交额/运行时长折算目标），保留“近1小时达成率”用于内部调节。
  - Why：修复滚动窗口导致的“达成率倒退”体验。
  - Impact：`backend/app/services/monitoring.py`、`backend/app/schemas.py`、`frontend/src/App.jsx`

- **[2026-02-19] 策略磨损指标新增**：新增统一指标 `wear_per_10k`，口径为 `-pnl_total / total_trade_volume_notional * 10000`。
  - Impact：`backend/app/services/monitoring.py`、`backend/app/schemas.py`、`frontend/src/App.jsx`

- **[2026-02-19] 下单量重挂触发补齐**：重挂判定新增数量偏差条件，支持在目标参数变化后自动按新单量撤挂重下。
  - Why：修复“改目标后每单数量不变化”的行为缺口。
  - Impact：`backend/app/engine/strategy_engine.py`、`backend/tests/test_strategy_engine_startup.py`

- **[2026-02-19] 交易对配置扩展**：GoalConfig 新增 `symbol` 并支持 `BNB_USDT_Perp/XRP_USDT_Perp/SUI_USDT_Perp`；运行中仅允许改目标参数，不允许切换交易对。
  - Impact：`backend/app/schemas.py`、`backend/app/services/goal_mapper.py`、`backend/app/api/config.py`、`frontend/src/App.jsx`

- **[2026-02-19] 配置界面简化**：前端移除动态价差/实时波动卡片、移除清空密钥复选框，挂单/成交表改为仅显示最近 5 条。
  - Impact：`frontend/src/App.jsx`

- **[2026-02-19] 指标展示再次精简**：前端已移除当日 PnL、近 1 小时成交量与达成率，仅保留“本次策略成交量（累计）”作为成交量主展示。
  - Why：按用户要求降低噪音，避免多口径造成误解。
  - Impact：`frontend/src/App.jsx`

- **[2026-02-19] 50x 口径映射落地**：GoalConfig 映射运行参数时固定按 `principal_usdt * 50` 作为有效资金，参与单笔名义与库存上限计算。
  - Why：解决“小本金下参数变化对实际下单量不敏感”的问题。
  - Impact：`backend/app/services/goal_mapper.py`、`backend/tests/test_goal_mapper.py`

- **[2026-02-19] 库存与单笔联动约束**：新增硬约束 `max_inventory_notional >= max_single_order_notional * 1.8`，并将单边挂单触发阈值提升为 `1.5x max_inventory_notional`。
  - Why：减少“一成交就单边挂单”的误触发。
  - Impact：`backend/app/services/goal_mapper.py`、`backend/app/engine/strategy_engine.py`、`backend/tests/test_strategy_engine_startup.py`

- **[2026-02-20] 下单量步长量化修复**：GRVT 适配器新增交易对元数据约束缓存（`min_size/base_decimals/size_step`），下单前统一对 `size` 按步长量化并执行最小下单量抬升。
  - Why：修复线上持续 `400 code=2065 (Order size too granular)` 导致运行中无在簿挂单。
  - Impact：`backend/app/exchange/grvt_live.py`、`backend/tests/test_grvt_order_size_quantize.py`

- **[2026-02-20] 本次成交量口径修复**：监控累计指标仅统计 `created_at >= session_started_at` 的成交，避免把启动前历史成交混入“本次策略成交量”。
  - Why：修复“本次策略成交量”展示偏大/偏错的问题。
  - Impact：`backend/app/services/monitoring.py`、`backend/tests/test_monitoring_metrics.py`、`backend/app/models.py`

## Decisions

- **[2026-02-20] 平仓残量终止决策**：`stop/halt` 平仓阶段若命中 `PositionDustError`（仓位小于交易所最小可平量），引擎不再无限重试，改为发布 `close_done(dust=true)` 并告警标记。
  - Why：避免“仓位已是残量却永久重试”的假死状态，确保停止流程可完成。
  - Impact：`backend/app/engine/strategy_engine.py`、`backend/app/exchange/base.py`、`backend/app/exchange/grvt_live.py`

- **[2026-02-20] 成交提速参数收敛决策**：策略配置写入运行参数时统一覆盖为成交优先执行窗口（`min_spread/max_spread/requote/ttl/interval`）。
  - Why：修复“长期不改单、成交慢”的执行层保守漂移。
  - Impact：`backend/app/services/strategy_mapper.py`、`backend/app/schemas.py`

- **[2026-02-20] 交易对约束缺失策略**：当 `min_size/size_step` 无法可靠解析时，适配器改为阻断下单并抛出明确错误，不再回退默认步长下单。
  - Why：优先避免重复触发 `2065` 粒度拒单风暴，提升故障可诊断性。
  - Impact：`backend/app/exchange/grvt_live.py`、`backend/tests/test_grvt_order_size_quantize.py`

- **[2026-02-20] 库存风险分母决策**：库存占比分母采用 `free_usdt * effective_leverage`（默认 50x），并在 `free` 缺失时回退到 `equity-used` 估算。
  - Why：最贴近“实际可用可开名义”口径，解决小本金高杠杆误判。
  - Impact：`backend/app/engine/strategy_engine.py`、`backend/app/exchange/grvt_live.py`

- **[2026-02-20] k 自适应决策**：`k` 采用盘口深度单因子自适应（`base_k * depth_factor`，区间限幅 `[0.5x, 2.0x]`），`gamma` 继续沿用随 `sigma` 自适应。
  - Why：在不引入过多参数复杂度下，增强深度差场景的价差与成交质量平衡。
  - Impact：`backend/app/engine/strategy_engine.py`

- **[2026-02-20] 配置策略决策**：主配置入口从 Goal 模型迁移到 Strategy 模型；`/api/config/goal` 保留为兼容接口但不再作为前端主路径。
  - Why：满足“回归 AS 核心参数、移除目标交易量驱动”的产品要求，降低参数语义偏差。
  - Impact：`backend/app/api/config.py`、`frontend/src/api.js`

- **[2026-02-20] 成交优先执行决策**：重挂改为“先挂新单再撤旧单”的 side 级更新策略。
  - Why：减少重挂过程的空档时间，优先保证持续在簿。
  - Impact：`backend/app/engine/strategy_engine.py`

- **[2026-02-19] 策略框架**：采用 Avellaneda-Stoikov + 基础自适应（波动率/深度/成交强度）。
  - Why：满足“参数自动适应实时波动”且实现可控。
  - Impact：`backend/app/engine/as_model.py`、`backend/app/engine/adaptive.py`

- **[2026-02-19] 执行与风控**：默认 post-only，三重熔断，重启后只读 180 秒。
  - Why：先保证做市成本和实盘安全。
  - Impact：`backend/app/engine/strategy_engine.py`、`backend/app/engine/risk_guard.py`

- **[2026-02-19] 架构选择**：Python FastAPI + React，单机一体化部署。
  - Why：量化迭代效率高，部署简单。
  - Impact：`backend/app/main.py`、`frontend/`

- **[2026-02-19] API 凭证管理**：新增 `exchange_config.json` 持久化，密钥只写不回显，运行中禁止修改。
  - Why：满足 WebUI 配置需求并降低运行时误操作风险。
  - Impact：`backend/app/services/exchange_config.py`、`backend/app/api/config.py`

- **[2026-02-19] WS 稳定性策略**：前端 WS 改为状态化重连（connecting/connected/reconnecting/disconnected），不再把 `onerror` 直接视为全局错误。
  - Why：避免页面持续弹“连接异常”，降低误报。
  - Impact：`frontend/src/App.jsx`

- **[2026-02-19] 成交优先调参与映射**：默认运行参数和三旋钮映射改为成交优先区间（更窄价差、更快重报价、更大单笔名义）。
  - Why：解决“运行多分钟持续 0 成交”时策略长期过保守的问题。
  - Impact：`backend/app/schemas.py`、`backend/data/runtime_config.json`、`backend/app/services/profile_mapper.py`

- **[2026-02-19] 交易适配容错加固**：order book 读取失败时自动降级为 ticker-only；下单 client_order_id 改为纯数字，错误日志增加分类标签。
  - Why：规避 `event_time` 缺失与 `invalid literal for int()` 导致的主循环异常。
  - Impact：`backend/app/exchange/grvt_live.py`、`backend/app/engine/strategy_engine.py`

- **[2026-02-19] 做市启动节奏调整**：从“启动只读预热后再挂单”调整为“启动即进入 running 并挂单”。
  - Why：优先保证持续挂单可用性，符合“AS 模型应持续在簿报价”的产品预期。
  - Impact：`backend/app/engine/strategy_engine.py`

- **[2026-02-19] 关闭路径风险优先**：停止/熔断阶段优先执行 taker 平仓闭环，不以“仅停引擎”作为完成条件。
  - Why：在高波动场景下，仓位清理优先级高于进程快速返回。
  - Impact：`backend/app/engine/strategy_engine.py`

- **[2026-02-19] 参数设计改为目标驱动**：放弃前端三旋钮+高级参数暴露，改为 GoalConfig 单入口映射运行参数。
  - Why：降低配置理解门槛，确保 10u 小本金下可快速调到目标成交量模式。
  - Impact：`frontend/src/App.jsx`、`backend/app/services/goal_mapper.py`

- **[2026-02-19] 运行中配置边界收敛**：`/api/config/goal` 在运行态仅允许更新同币对参数，禁止运行中切换交易对。
  - Why：避免中途换标的导致残单/仓位语义不一致。
  - Impact：`backend/app/api/config.py`

- **[2026-02-19] 杠杆参数交互决策**：杠杆不开放前端调节，当前固定按 50x 生效于参数映射。
  - Why：优先满足快速试参与稳定口径，减少误配复杂度。
  - Impact：`backend/app/services/goal_mapper.py`、`backend/app/engine/strategy_engine.py`

- **[2026-02-19] 线上与回测环境分离**：在线服务保持 `prod`，回测任务默认 `testnet` 语义（不触发真实交易）。
  - Why：保持现有线上链路稳定，同时满足测试流量与参数验证需求。
  - Impact：`backend/app/schemas.py`、`backend/app/api/config.py`、`backend/app/backtest/*`

## Commands

- **[2026-02-19] 后端启动**：`cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload`
- **[2026-02-19] 前端开发**：`cd frontend && npm install && npm run dev`
- **[2026-02-19] 前端构建**：`cd frontend && npm run build`
- **[2026-02-19] 测试**：`cd backend && pytest -q`
- **[2026-02-19] 前端构建验证**：`cd frontend && npm run build`
- **[2026-02-19] 域名探活**：`curl -I http://as.0xpsyche.me`、`curl -I https://as.0xpsyche.me`
- **[2026-02-19] 简化回测 CLI**：`cd backend && python -m app.backtest.run --data <csv路径> --principal 10 --target-hourly 10000 --risk-profile throughput`
- **[2026-02-19] 回测 API**：`POST /api/backtest/jobs` -> `GET /api/backtest/jobs/{job_id}` -> `GET /api/backtest/jobs/{job_id}/report`

## Status / Next

- **[2026-02-20] 当前状态（成交提速 + 平仓闭环修复）**：已完成监控字段精简、成交优先参数收敛、taker 平仓量化与残量终止分支，后端测试 `74 passed`，前端构建通过。
  - Next：部署伦敦机后观察 10-20 分钟：`requote_reason` 不再长期 `none`、成交笔数提升、`stop/halt` 不再出现无限平仓重试。

- **[2026-02-20] 当前状态（XRP/SUI 下单量修复 + HYPE 接入）**：已完成 `HYPE_USDT_Perp` 前后端接入、交易对约束解析增强、缺约束阻断下单策略、以及多交易对回归用例；后端测试 `71 passed`，前端构建通过。
  - Next：部署后观察 `XRP/SUI/HYPE` 各 10-20 分钟，确认日志不再出现持续 `code=2065` 且 `open_orders` 可稳定在簿。

- **[2026-02-20] 当前状态（可用资金口径 + k 自适应）**：已完成可用资金杠杆口径接入、`k` 深度自适应、监控字段与前端卡片展示、资金解析回归测试；后端测试 `64 passed`，前端构建通过。
  - Next：部署后观察 10-20 分钟 `inventory_usage_ratio` 与 `effective_liquidity_k` 曲线，确认单边触发与可用资金变化一致。

- **[2026-02-20] 当前状态（AS 参数回归）**：`strategy` 配置链路、重挂防抖、库存权益比单边阈值、前端策略面板已落地；后端测试 `58 passed`，前端构建通过。
  - Next：部署后观察 10-20 分钟 `open_orders` 连续性与 `requote_reason` 分布，重点确认不再出现高频抖动撤挂。

- **[2026-02-19] 当前状态**：默认实盘（prod）与去 mock、Telegram 配置、WS 重连状态已落地，后端测试 `20 passed`，前端构建通过，并已部署到香港机。
  - Next：在真实账户观察 Telegram 告警送达与实盘风控触发行为，按成交节奏微调参数。

- **[2026-02-19] 当前状态（更新）**：服务已首部署到伦敦机 `144.126.234.61`，`grvt-mm` 运行在 `:18081`，`as.0xpsyche.me` 已签发并启用 HTTPS，WSS 握手可收到 `hello`。
  - Next：观察 24h 稳定性（重启恢复、证书自动续期、WS 连通）并确认交易所连通质量。

- **[2026-02-19] 当前状态（补充）**：启动链路已修复“交易对格式错误”问题；当前若“启动无反应”，主要原因为实盘凭据未配置（`trading_account_id/api_key/api_secret`）。
  - Next：在 WebUI 完成 GRVT 三项凭据配置后再次启动并观察 `exchange_connected=true`。

- **[2026-02-19] 当前状态（成交优化）**：已完成成交优先改造（策略映射、运行参数、适配容错、诊断面板），后端测试 `28 passed`，前端构建通过。
  - Next：在实盘连续运行 10-15 分钟观察 `maker_fill_count_1m/cancel_count_1m/fill_to_cancel_ratio` 并按诊断值二次微调价差上限。

- **[2026-02-19] 当前状态（挂单优先）**：已完成“启动即挂单”改造与前端成交诊断面板下线，新增启动与下单双测例保障行为稳定。
  - Next：在实盘观察启动后首轮挂单时间与 5-10 分钟成交节奏，若仍偏慢再评估参数窗口而非重引擎流程。

- **[2026-02-19] 当前状态（风控与指标增强）**：已完成停止/熔断 taker 平仓闭环、Telegram 规范告警与心跳、库存权益联动、监控口径扩展、前端深色与高级参数面板。后端测试 `36 passed`，前端构建通过。
  - Next：实盘重点观察“平仓重试链路”和“心跳频率是否符合值守密度”，根据告警噪音再微调 `tg_heartbeat_interval_sec` 与重试退避参数。

- **[2026-02-19] 当前状态（部署完成）**：代码已推送 `origin/main`（HEAD `73233ae`），并通过应急 `scp` 路径重部署到香港机 `103.52.152.92`；`grvt-mm` active、`:18081` 监听、`/healthz` 正常。
  - Next：补齐香港机仓库的 Git 一致性（当前非 Git 工作树），恢复主干 `git pull --rebase` 部署路径。

- **[2026-02-19] 当前状态（参数极简+回测）**：`GoalConfig`、成交量目标闭环、简化回测子系统、前端极简参数面板已落地；后端测试 `44 passed`，前端构建通过。
  - Next：按“纽约+香港回放、伦敦回归”执行服务器侧测试与结果对比，校验目标达成率区间。

- **[2026-02-19] 当前状态（服务器验证）**：香港机 `103.52.152.92` 已同步新代码并通过后端测试 `44 passed`、前端构建与健康检查（`grvt-mm active`、`:18081` 监听、`/healthz` 正常）。
  - Next：补齐伦敦机回归验证并对比三机结果差异。

- **[2026-02-19] 当前状态（双机回放）**：香港机与纽约机均已执行同一份样例 CSV 回放，结果一致（`estimated_hourly_notional=7500`，目标达成率 `0.75`）。
  - Next：替换为更长时段真实样本数据，验证 24h 口径稳定性。

- **[2026-02-19] 当前状态（伦敦重部署）**：伦敦机 `144.126.234.61` 已通过应急 tar 包重部署最新本地工作区，服务器侧后端测试 `44 passed`，`grvt-mm` 运行在 `:18081` 且 `/healthz` 返回正常；域名 `as.0xpsyche.me` 探活为 HTTP 301、HTTPS 405（GET 限制）。
  - Next：将本地未提交变更整理并推送 `origin/main`，恢复 Git 主干部署路径。

- **[2026-02-19] 当前状态（口径与交互修复）**：已完成启动累计达成率、每万磨损指标、改单量重挂触发、币对可选（BNB/XRP/SUI）、运行中禁切币对、前端参数与表格精简；后端测试 `47 passed`，前端构建通过。
  - Next：实盘观察 30-60 分钟内 `wear_per_10k` 与 `target_completion_ratio_session` 的稳定性，并结合新增延迟诊断做下一轮参数微调。

- **[2026-02-19] 当前状态（伦敦再次重部署）**：伦敦机 `144.126.234.61` 已通过应急 `scp+tar` 同步本地最新改动并完成前端构建；`grvt-mm` active、`:18081` 监听、`/healthz` 正常，`DEPLOY_COMMIT=d7c0364-dirty-20260220_001612`。
  - Why：远端 `/opt/grvt-mm` 仍非 Git 工作树，无法走 `git pull --rebase` 主干路径。
  - Next：将本地变更推送 `origin/main` 后修复伦敦机仓库为可 Git 更新状态，恢复主干部署链路。

- **[2026-02-19] 当前状态（口径修复）**：已完成“去当日PnL/去达成率/单成交量展示”、50x 映射与单边阈值修复，新增回归测试；后端测试 `51 passed`，前端构建通过。
  - Next：实盘观察 15-30 分钟，重点确认“改单量后实际挂单量变化”与“成交后是否仍稳定双边挂单（未超 1.5x 库存阈值）”。

- **[2026-02-20] 当前状态（挂单恢复+成交量口径）**：已完成 `2065` 下单粒度修复与“本次策略成交量”会话口径修复，新增量化与口径回归用例；后端测试 `55 passed`。
  - Next：重部署伦敦机后观察 10-20 分钟，确认日志不再出现 `code=2065` 且 `open_orders` 可稳定在簿；同时核对策略重启后成交量从 0 开始累计。

## Known Issues

- **[2026-02-20] 残量终止为预期保护行为**：当净仓低于交易所 `min_close_size` 时会触发 `POSITION_FLAT_DUST` 并结束平仓重试，可能仍看到极小残仓显示。
  - Why：交易所最小成交量约束导致残量不可撮合，继续重试无意义。
  - Verify：停止时若出现 `close_done` 且 `dust=true`，同时告警 `POSITION_FLAT_DUST`，即表示命中该保护分支。

- **[2026-02-20] 约束缺失会阻断下单（预期行为）**：若交易对元数据未返回 `min_size/size_step`，系统将显式报错并停止该轮下单。
  - Why：避免无效默认步长导致的 `2065` 重复拒单。
  - Verify：日志应出现 `instrument_constraints_missing`，且不会继续发送被拒订单。

- **[2026-02-20] 可用资金字段来源差异**：不同账户/交易所响应下 `free_usdt` 可能来自 `USDT.free`、`free.USDT` 或 `equity-used` 回退。
  - Why：交易所返回字段存在不一致，已通过 `funds_source` 诊断字段标记来源。
  - Verify：观察 `tick.diagnostics.funds_source` 是否稳定且与账户面板一致。

- **[2026-02-20] 兼容接口残留**：`/api/config/goal` 仍可用，但已不再是主配置入口（前端已切换为 `/api/config/strategy`）。
  - Why：为历史脚本/调用方提供过渡兼容。
  - Verify：`GET/PUT /api/config/strategy` 返回成功且前端“策略配置（AS 核心）”面板可正常读写。

- **[2026-02-19] 域名接入状态**：`as.0xpsyche.me` 已接入 `103.52.152.92`，Nginx 已配置 HTTPS 与 WebSocket 反代。
  - Verify：`curl -I http://as.0xpsyche.me` 应 301 到 HTTPS，`curl -I https://as.0xpsyche.me` 返回 405/200 视请求方法而定，`wss://as.0xpsyche.me/ws/stream` 可收到 `hello`。

- **[2026-02-19] 香港机部署状态**：已完成部署，服务 `grvt-mm` 运行在 `103.52.152.92:18081`。
  - Why：原 `8080` 被既有 docker-proxy 占用，改为 `18081` 避免冲突。
  - Verify：`systemctl is-active grvt-mm`、`curl http://127.0.0.1:18081/healthz`

- **[2026-02-19] API 修改限制**：`PUT /api/config/exchange` 在 `running/readonly` 状态会返回 `409`。
  - Why：避免运行中误改密钥导致连接状态不一致。
  - Verify：启动引擎后调用接口应返回 409，停止后可成功更新。

- **[2026-02-19] 伦敦机首次接入注意事项**：新机 root 密码初始为过期状态，需先改密后才能自动化部署。
  - Why：SSH 登录阶段会强制改密，非交互命令直接失败。
  - Verify：`python scripts/ssh_exec.py "hostname"` 能直接返回结果即表示已解除阻塞。

- **[2026-02-19] 版本一致性注意事项**：伦敦机已通过本地快照应急部署到最新工作区，当前不等同于 `origin/main` 提交快照。
  - Why：本地 `main` 与 `origin/main` 存在提交与未提交差异，Git 主干部署会落到旧版本。
  - Verify：服务器 `git status --short` 显示大量工作区变更且新文件 `backend/app/services/telegram_config.py` 存在。

- **[2026-02-19] 启动无反应排查结论**：若 `GET /api/status` 中 `last_error` 为 `GrvtCcxt: this action requires a trading_account_id`，则为凭据缺失而非服务未启动。
  - Verify：`GET /api/config/secrets/status` 中 `grvt_api_key_configured/grvt_api_secret_configured/grvt_trading_account_id_configured` 均应为 `true`。

- **[2026-02-19] 近期异常模式补充**：若日志频繁出现 `KeyError: 'event_time'` 或 `invalid literal for int()`，优先检查是否为交易所响应字段缺失/非数字 client_order_id 触发。
  - Why：这两类异常会显著降低有效运行窗口并间接导致“无成交”误判。
  - Verify：`journalctl -u grvt-mm --no-pager | egrep \"event_time|invalid literal for int\"` 应不再持续刷屏。

- **[2026-02-19] 运行但不挂单排查结论**：若 `mode=running` 但 `open_orders=[]` 且日志反复出现 `code=2013 Client Order ID repeats with the last order`，则为下单被交易所拒绝而非策略未触发。
  - Why：此场景会表现为持续 `missing-side-buy,missing-side-sell` 和撤单计数增长。
  - Verify：`journalctl -u grvt-mm --no-pager | grep "code': 2013"`；修复后应出现 `create_order` 成功并能查到 open orders。

- **[2026-02-19] 运行但不挂单二级结论**：若 `mode=running` 且 `exchange_connected=true`，但日志持续 `code=2062 Order size smaller than min size`，则为下单量过小被交易所拒绝。
  - Why：低权益账户在默认 `quote_size_notional` 下可能推导出过小 `quote_size_base`。
  - Verify：`journalctl -u grvt-mm --no-pager | grep "code': 2062"`；应用最小下单量保护后应显著减少该错误并出现在簿订单。

- **[2026-02-19] 运行但不挂单三级结论**：若 `code=2062` 已消失但持续 `code=2064 Invalid limit price tick`，则需对 bid/ask 价格按交易所 tick 量化后再下单。
  - Why：模型浮点价格不一定落在交易所有效刻度网格上。
  - Verify：`journalctl -u grvt-mm --no-pager | grep "code': 2064"`；修复后应不再持续出现并能查到 open orders。

- **[2026-02-20] 运行但不挂单四级结论**：若 `code=2062/2064` 已处理但持续 `code=2065 Order size too granular`，则需按交易对步长量化下单数量，而非仅做最小下单量保护。
  - Why：交易所会对 `size` 精度做粒度校验，超出允许步长会整单拒绝。
  - Verify：`journalctl -u grvt-mm --no-pager | grep "code': 2065"`；修复后错误应消失且 `open_orders` 返回非空。

- **[2026-02-19] 平仓链路观察点**：停止/熔断接口会等待 taker 平仓完成后返回；若交易所持续拒单，接口可能长时间阻塞（符合“无限重试直到成功”策略）。
  - Verify：日志检索 `POSITION_FLATTEN_RETRY` 与 `close_done` 事件；最终需出现 `POSITION_FLAT` 告警。

- **[2026-02-19] 香港机部署路径异常**：`/opt/grvt-mm` 当前不是 Git 仓库，无法执行主干 `git pull --rebase`，本次采用最小文件 `scp` 应急同步。
  - Why：远端缺失 `.git` 元数据，`git rev-parse` 返回 “not a git repository”。
  - Verify：`cat /opt/grvt-mm/DEPLOY_COMMIT` 为 `73233ae`，`systemctl is-active grvt-mm` 为 `active`，`curl http://127.0.0.1:18081/healthz` 返回 `{"ok":true}`。

- **[2026-02-19] 回测输入数据格式约束**：简化回测 CSV 需包含 `timestamp` 与 `mid/mid_price/price/close` 字段之一；缺字段会直接失败。
  - Why：当前回放引擎采用最小输入模型，不做复杂字段推断。
  - Verify：调用 `POST /api/backtest/jobs` 时若缺字段应返回 400，字段完整应进入 `completed`。

- **[2026-02-19] 纽约机运行依赖缺失**：纽约机初始缺少 `python3-venv` 与 `pip3`，回放前需先安装运行时工具链。
  - Why：系统镜像较轻，未预装 Python 开发组件。
  - Verify：`python3 -m venv .venv` 与 `pip3 --version` 可执行后再跑 `python -m app.backtest.run`。

- **[2026-02-19] 伦敦机关停卡顿告警**：重启时可能因旧进程处于“平仓无限重试”而触发 `systemd stop-sigterm timeout`，随后被 SIGKILL 再拉起；新进程可正常恢复监听 `18081`。
  - Why：日志显示停止阶段持续出现 `KeyError: 'IOC'`（`flatten_position_taker` 路径），导致优雅退出超时。
  - Verify：`journalctl -u grvt-mm -n 200 --no-pager | egrep "KeyError: 'IOC'|stop-sigterm"`；重启后需满足 `systemctl is-active grvt-mm` 为 `active` 且 `curl -fsS http://127.0.0.1:18081/healthz` 返回 `{"ok":true}`。
