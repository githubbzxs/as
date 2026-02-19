# GRVT AS 做市系统

基于 Avellaneda-Stoikov（AS）模型的量化做市程序，支持：

- GRVT（真实接口 + Mock 联调模式）
- 7x24 自动做市（只读预热 + 自动恢复）
- Post-only 限价下单
- 三重熔断（连续失败/回撤/异常波动）
- WebUI（登录、启停、监控、参数时序、参数热更新）
- API Key 环境变量管理（UI 仅展示配置状态）

> 首版不包含回测模块。

## 目录结构

```text
backend/
  app/
    api/               # FastAPI 路由
    core/              # 配置、鉴权、依赖
    engine/            # AS 模型、自适应、风控、主引擎
    exchange/          # GRVT 适配层（live/mock）
    services/          # 监控、事件总线、告警、运行配置
  tests/               # 单元测试
frontend/
  src/                 # React 控制台
deploy/                # systemd 配置模板
scripts/               # 启动与部署脚本
```

## 快速启动（本地）

### 1) 后端

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
# source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### 2) 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器访问：`http://127.0.0.1:5173`

默认账号：`admin`
默认密码：`admin123`

## 生产构建（单机一体化）

```bash
cd frontend
npm install
npm run build

cd ../backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

前端静态资源在 `frontend/dist`，后端会自动托管 `/` 页面。

## 环境变量

见 `backend/.env.example`。

关键变量：

- `GRVT_USE_MOCK`：`true` 表示模拟交易所，`false` 表示真实 GRVT
- `GRVT_ENV`：`testnet/prod/staging/dev`
- `GRVT_API_KEY`
- `GRVT_API_SECRET`
- `GRVT_TRADING_ACCOUNT_ID`
- `APP_JWT_SECRET`
- `APP_ADMIN_USER`
- `APP_ADMIN_PASSWORD_HASH`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## API 概览

- `POST /api/auth/login`
- `GET /api/status`
- `GET /api/metrics`
- `GET /api/orders/open`
- `GET /api/trades/recent`
- `POST /api/engine/start`
- `POST /api/engine/stop`
- `GET /api/config/runtime`
- `PUT /api/config/runtime`
- `GET /api/config/secrets/status`
- `WS /ws/stream?token=...`

## 测试

```bash
cd backend
pytest -q
```

## 部署到香港机（IP+端口+应用内登录）

1. 在服务器安装 Python 3.11+ / Node.js 20+
2. 拉取代码
3. 前端构建：`cd frontend && npm ci && npm run build`
4. 后端安装依赖：`cd backend && pip install -r requirements.txt`
5. 复制 `.env.example` 为 `.env` 并填入真实密钥
6. 启动服务：`uvicorn app.main:app --host 0.0.0.0 --port 18081`（若端口冲突可调整）
7. 推荐使用 `deploy/grvt-mm.service` 交给 `systemd` 托管

## 风控说明

- 连续失败阈值：`max_consecutive_failures`
- 回撤熔断：`drawdown_kill_pct`
- 异常波动熔断：`volatility_kill_zscore`
- 重启只读期：`recovery_readonly_sec`

触发熔断后会自动撤单并发出告警。

