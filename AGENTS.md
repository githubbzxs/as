# AGENTS.md

## Facts

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

## Decisions

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

## Commands

- **[2026-02-19] 后端启动**：`cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload`
- **[2026-02-19] 前端开发**：`cd frontend && npm install && npm run dev`
- **[2026-02-19] 前端构建**：`cd frontend && npm run build`
- **[2026-02-19] 测试**：`cd backend && pytest -q`
- **[2026-02-19] 前端构建验证**：`cd frontend && npm run build`
- **[2026-02-19] 域名探活**：`curl -I http://as.0xpsyche.me`、`curl -I https://as.0xpsyche.me`

## Status / Next

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

## Known Issues

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
