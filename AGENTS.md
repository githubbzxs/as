# AGENTS.md

## Facts

- **[2026-02-19] 项目目标**：交付 GRVT 做市实盘首版，范围仅下单、监控、API Key 配置，不含回测模块。
  - Impact：`backend/`、`frontend/`

- **[2026-02-19] 首版交易范围**：USDT 永续，当前默认交易对为 `BNB_USDT-PERP`。
  - Impact：`backend/app/schemas.py`

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

## Commands

- **[2026-02-19] 后端启动**：`cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload`
- **[2026-02-19] 前端开发**：`cd frontend && npm install && npm run dev`
- **[2026-02-19] 前端构建**：`cd frontend && npm run build`
- **[2026-02-19] 测试**：`cd backend && pytest -q`

## Status / Next

- **[2026-02-19] 当前状态**：核心后端、WebUI、测试与部署模板已落地，待接入真实 GRVT 账户做联调。
  - Next：在香港机配置真实 `GRVT_API_KEY/GRVT_API_SECRET/GRVT_TRADING_ACCOUNT_ID` 后执行灰度上线。

## Known Issues

- **[2026-02-19] Mock 与真实环境差异**：默认 `GRVT_USE_MOCK=true` 便于本地联调，但真实成交回报节奏与滑点行为需在 testnet 再校准。
  - Verify：关闭 mock 后运行 `GET /api/status` 与实际下单验证。

- **[2026-02-19] 香港机部署状态**：已完成部署，服务 `grvt-mm` 运行在 `103.52.152.92:18081`。
  - Why：原 `8080` 被既有 docker-proxy 占用，改为 `18081` 避免冲突。
  - Verify：`systemctl is-active grvt-mm`、`curl http://127.0.0.1:18081/healthz`
