# GRVT AS 做市系统

基于 Avellaneda-Stoikov（AS）模型的量化做市程序，支持：

- GRVT（真实接口）
- 7x24 自动做市（只读预热 + 自动恢复）
- Post-only 限价下单
- 三重熔断（连续失败/回撤/异常波动）
- WebUI（登录、启停、监控、极简目标参数配置）
- API 配置管理（UI 可写入，密钥不回显）
- 简化回测子系统（CSV 数据回放 + 目标成交量评估）

## 目录结构

```text
backend/
  app/
    api/               # FastAPI 路由
    core/              # 配置、鉴权、依赖
    engine/            # AS 模型、自适应、风控、主引擎
    exchange/          # GRVT 适配层（live）
    backtest/          # 简化回测引擎与任务服务
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

- `GRVT_ENV`：默认固定 `prod`（实盘）
- `GRVT_API_KEY`
- `GRVT_API_SECRET`
- `GRVT_TRADING_ACCOUNT_ID`
- `APP_JWT_SECRET`
- `APP_ADMIN_USER`
- `APP_ADMIN_PASSWORD_HASH`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `EXCHANGE_CONFIG_PATH`：交易所连接配置持久化文件
- `TELEGRAM_CONFIG_PATH`：Telegram 配置持久化文件

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
- `GET /api/config/runtime/profile`
- `PUT /api/config/runtime/profile`
- `GET /api/config/goal`
- `PUT /api/config/goal`
- `GET /api/config/exchange`
- `PUT /api/config/exchange`
- `GET /api/config/telegram`
- `PUT /api/config/telegram`
- `GET /api/config/secrets/status`
- `POST /api/backtest/jobs`
- `GET /api/backtest/jobs/{job_id}`
- `GET /api/backtest/jobs/{job_id}/report`
- `WS /ws/stream?token=...`

## 目标参数与 API 配置规则

- 参数面板默认采用“目标参数模式”：`本金`、`目标小时交易量`、`风险档位`
- 后端会将目标参数映射到内部运行参数，并结合最近 1 小时成交量做小步调节
- 实盘环境固定为 `prod`，UI 不提供环境切换入口
- API/TG 配置保存后密钥不会回显，仅展示“已配置/未配置”
- 当引擎状态不是 `idle/halted` 时，`PUT /api/config/exchange` 会返回 `409`，避免运行中误改凭证
- 兼容接口 `PUT /api/config/runtime` 与 `PUT /api/config/runtime/profile` 仍可用，但前端默认不再暴露

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

