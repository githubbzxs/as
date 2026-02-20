import { useMemo, useState, useEffect } from "react";
import {
  fetchExchangeConfig,
  fetchStrategyConfig,
  fetchMetrics,
  fetchOpenOrders,
  fetchRecentTrades,
  fetchSecretsStatus,
  fetchStatus,
  fetchTelegramConfig,
  login,
  startEngine,
  stopEngine,
  updateExchangeConfig,
  updateStrategyConfig,
  updateTelegramConfig,
} from "./api";

const initialLogin = { username: "admin", password: "" };

const symbolOptions = [
  { value: "BNB_USDT_Perp", label: "BNB_USDT_Perp" },
  { value: "XRP_USDT_Perp", label: "XRP_USDT_Perp" },
  { value: "SUI_USDT_Perp", label: "SUI_USDT_Perp" },
  { value: "HYPE_USDT_Perp", label: "HYPE_USDT_Perp" },
];

const wsStateMeta = {
  connecting: { label: "连接中", className: "ws-connecting" },
  connected: { label: "已连接", className: "ws-connected" },
  reconnecting: { label: "重连中", className: "ws-reconnecting" },
  disconnected: { label: "未连接", className: "ws-disconnected" },
};

function fmt(value, digits = 4) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toFixed(digits);
}

function formatDuration(seconds) {
  const sec = Number(seconds);
  if (!Number.isFinite(sec) || sec < 0) return "-";
  const total = Math.floor(sec);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return `${h}h ${m}m ${s}s`;
}

function buildSmoothPath(points) {
  if (!points.length) return "";
  if (points.length === 1) return `M${points[0].x},${points[0].y}`;
  let path = `M${points[0].x},${points[0].y}`;
  for (let i = 0; i < points.length - 1; i += 1) {
    const p0 = points[i - 1] || points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] || p2;
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;
    path += ` C${cp1x},${cp1y} ${cp2x},${cp2y} ${p2.x},${p2.y}`;
  }
  return path;
}

function LineChart({ title, points, color = "#0ea5e9" }) {
  const values = (points || []).map((p) => Number(p.value)).filter((v) => Number.isFinite(v));
  const width = 420;
  const height = 140;
  const gradientId = `gradient-${title.replace(/\s+/g, "-").toLowerCase()}`;

  const { linePath, areaPath } = useMemo(() => {
    if (!values.length) return { linePath: "", areaPath: "" };
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const coords = values.map((v, i) => ({
      x: (i / Math.max(1, values.length - 1)) * width,
      y: height - ((v - min) / span) * (height - 8) - 4,
    }));
    const line = buildSmoothPath(coords);
    const last = coords[coords.length - 1];
    const area = `${line} L${last.x},${height} L${coords[0].x},${height} Z`;
    return { linePath: line, areaPath: area };
  }, [values]);

  return (
    <div className="chart-card">
      <div className="chart-title">{title}</div>
      <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg" preserveAspectRatio="none">
        <defs>
          <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.35" />
            <stop offset="100%" stopColor={color} stopOpacity="0.0" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill={`url(#${gradientId})`} className="chart-area" />
        <path d={linePath} fill="none" stroke={color} strokeWidth="2.5" className="chart-line" />
      </svg>
      <div className="chart-meta">最新: {values.length ? fmt(values[values.length - 1], 6) : "-"}</div>
    </div>
  );
}

function LoginPanel({ onLogin, loading }) {
  const [form, setForm] = useState(initialLogin);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      await onLogin(form.username, form.password);
    } catch (err) {
      setError(err.message || "登录失败");
    }
  }

  return (
    <div className="login-wrapper">
      <form onSubmit={submit} className="login-card">
        <h1>GRVT 做市控制台</h1>
        <p>请输入应用账号密码后进入监控与控制页面。</p>
        <label>用户名</label>
        <input
          value={form.username}
          onChange={(e) => setForm((s) => ({ ...s, username: e.target.value }))}
          autoComplete="username"
        />
        <label>密码</label>
        <input
          type="password"
          value={form.password}
          onChange={(e) => setForm((s) => ({ ...s, password: e.target.value }))}
          autoComplete="current-password"
        />
        {error && <div className="error-text">{error}</div>}
        <button disabled={loading}>{loading ? "登录中..." : "登录"}</button>
      </form>
    </div>
  );
}

export default function App() {
  const [token, setToken] = useState(localStorage.getItem("mm_token") || "");
  const [authLoading, setAuthLoading] = useState(false);

  const [status, setStatus] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [strategyConfig, setStrategyConfig] = useState(null);
  const [strategyForm, setStrategyForm] = useState({
    symbol: "BNB_USDT_Perp",
    as_gamma: 0.1,
    as_sigma: 0.001,
    as_liquidity_k: 1.5,
    max_drawdown_pct: 9.0,
    max_inventory_equity_ratio: 0.6,
  });
  const [exchangeConfig, setExchangeConfig] = useState(null);
  const [telegramConfig, setTelegramConfig] = useState(null);
  const [secrets, setSecrets] = useState(null);
  const [orders, setOrders] = useState([]);
  const [trades, setTrades] = useState([]);

  const [apiForm, setApiForm] = useState({
    grvt_api_key: "",
    grvt_api_secret: "",
    grvt_trading_account_id: "",
  });
  const [telegramForm, setTelegramForm] = useState({
    telegram_bot_token: "",
    telegram_chat_id: "",
  });

  const [strategySaving, setStrategySaving] = useState(false);
  const [exchangeSaving, setExchangeSaving] = useState(false);
  const [telegramSaving, setTelegramSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [wsState, setWsState] = useState("disconnected");

  async function handleLogin(username, password) {
    setAuthLoading(true);
    try {
      const res = await login(username, password);
      setToken(res.access_token);
      localStorage.setItem("mm_token", res.access_token);
    } finally {
      setAuthLoading(false);
    }
  }

  async function loadTradingData() {
    if (!token) return;
    const [statusRes, metricsRes, orderRes, tradeRes] = await Promise.all([
      fetchStatus(token),
      fetchMetrics(token),
      fetchOpenOrders(token),
      fetchRecentTrades(token),
    ]);
    setStatus(statusRes);
    setMetrics(metricsRes);
    setOrders(orderRes);
    setTrades(tradeRes);
  }

  async function loadConfigData() {
    if (!token) return;
    const [strategyRes, exchangeRes, telegramRes, secretRes] = await Promise.all([
      fetchStrategyConfig(token),
      fetchExchangeConfig(token),
      fetchTelegramConfig(token),
      fetchSecretsStatus(token),
    ]);
    setStrategyConfig(strategyRes);
    setStrategyForm({
      symbol: strategyRes.symbol,
      as_gamma: strategyRes.as_gamma,
      as_sigma: strategyRes.as_sigma,
      as_liquidity_k: strategyRes.as_liquidity_k,
      max_drawdown_pct: strategyRes.max_drawdown_pct,
      max_inventory_equity_ratio: strategyRes.max_inventory_equity_ratio,
    });
    setExchangeConfig(exchangeRes);
    setTelegramConfig(telegramRes);
    setSecrets(secretRes);
    setApiForm({
      grvt_api_key: "",
      grvt_api_secret: "",
      grvt_trading_account_id: "",
    });
    setTelegramForm({
      telegram_bot_token: "",
      telegram_chat_id: "",
    });
  }

  useEffect(() => {
    if (!token) return;
    let timer = null;
    let closed = false;

    const start = async () => {
      try {
        await Promise.all([loadTradingData(), loadConfigData()]);
      } catch (err) {
        if (!closed) setError(err.message || "初始化加载失败");
      }

      timer = setInterval(async () => {
        try {
          await loadTradingData();
        } catch (err) {
          if (!closed) setError(err.message || "轮询失败");
        }
      }, 3000);
    };
    start();

    return () => {
      closed = true;
      if (timer) clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (!token) return;
    let ws = null;
    let retryTimer = null;
    let stopped = false;
    let retryCount = 0;

    const connect = () => {
      if (stopped) return;
      setWsState(retryCount === 0 ? "connecting" : "reconnecting");
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${window.location.host}/ws/stream?token=${token}`);

      ws.onopen = () => {
        retryCount = 0;
        setWsState("connected");
      };

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg.type === "tick" && msg.payload?.summary) {
            setMetrics((prev) => {
              if (!prev) return prev;
              return {
                ...prev,
                summary: msg.payload.summary,
              };
            });
            if (Array.isArray(msg.payload?.open_orders)) {
              setOrders(msg.payload.open_orders);
            }
          }
          if (msg.type === "close_retry") {
            setNotice("正在执行 taker 平仓重试...");
          }
          if (msg.type === "close_done") {
            setNotice("已完成 taker 平仓。");
          }
        } catch {
          // 忽略非关键消息
        }
      };

      ws.onerror = () => {
        // 交给 onclose 统一处理，避免重复错误横幅
      };

      ws.onclose = (evt) => {
        if (stopped) return;
        if (evt.code === 4401) {
          setWsState("disconnected");
          setError("登录状态已失效，请重新登录");
          localStorage.removeItem("mm_token");
          setToken("");
          return;
        }

        setWsState("reconnecting");
        const delay = Math.min(10000, 1000 * 2 ** Math.min(retryCount, 4));
        retryCount += 1;
        retryTimer = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      stopped = true;
      if (retryTimer) clearTimeout(retryTimer);
      if (ws) ws.close();
      setWsState("disconnected");
    };
  }, [token]);

  async function commandStart() {
    try {
      setError("");
      await startEngine(token);
      await loadTradingData();
      setNotice("引擎已启动");
    } catch (err) {
      setError(err.message || "启动失败");
    }
  }

  async function commandStop() {
    try {
      setError("");
      setNotice("停止中：正在执行撤单与 taker 平仓...");
      await stopEngine(token);
      await loadTradingData();
      setNotice("引擎已停止并完成平仓");
    } catch (err) {
      setError(err.message || "停止失败");
    }
  }

  async function saveStrategy() {
    setStrategySaving(true);
    setNotice("");
    try {
      const payload = {
        symbol: strategyForm.symbol,
        as_gamma: Number(strategyForm.as_gamma),
        as_sigma: Number(strategyForm.as_sigma),
        as_liquidity_k: Number(strategyForm.as_liquidity_k),
        max_drawdown_pct: Number(strategyForm.max_drawdown_pct),
        max_inventory_equity_ratio: Number(strategyForm.max_inventory_equity_ratio),
      };
      const updated = await updateStrategyConfig(token, payload);
      setStrategyConfig(updated);
      setStrategyForm({
        symbol: updated.symbol,
        as_gamma: updated.as_gamma,
        as_sigma: updated.as_sigma,
        as_liquidity_k: updated.as_liquidity_k,
        max_drawdown_pct: updated.max_drawdown_pct,
        max_inventory_equity_ratio: updated.max_inventory_equity_ratio,
      });
      setNotice("策略参数已保存");
    } catch (err) {
      setError(err.message || "保存策略参数失败");
    } finally {
      setStrategySaving(false);
    }
  }

  const canEditApi = status?.mode === "idle" || status?.mode === "halted";

  async function saveExchange() {
    if (!canEditApi) {
      setError("引擎运行中禁止修改配置，请先停止引擎");
      return;
    }
    setExchangeSaving(true);
    setNotice("");
    try {
      const payload = {
        grvt_api_key: apiForm.grvt_api_key,
        grvt_api_secret: apiForm.grvt_api_secret,
        grvt_trading_account_id: apiForm.grvt_trading_account_id,
      };
      const updated = await updateExchangeConfig(token, payload);
      setExchangeConfig(updated);
      await loadConfigData();
      setNotice("实盘 API 配置已保存");
    } catch (err) {
      setError(err.message || "保存实盘 API 配置失败");
    } finally {
      setExchangeSaving(false);
    }
  }

  async function saveTelegram() {
    if (!canEditApi) {
      setError("引擎运行中禁止修改配置，请先停止引擎");
      return;
    }
    setTelegramSaving(true);
    setNotice("");
    try {
      const payload = {
        telegram_bot_token: telegramForm.telegram_bot_token,
        telegram_chat_id: telegramForm.telegram_chat_id,
      };
      const updated = await updateTelegramConfig(token, payload);
      setTelegramConfig(updated);
      await loadConfigData();
      setNotice("Telegram 告警配置已保存");
    } catch (err) {
      setError(err.message || "保存 Telegram 配置失败");
    } finally {
      setTelegramSaving(false);
    }
  }

  function logout() {
    localStorage.removeItem("mm_token");
    setToken("");
  }

  if (!token) {
    return <LoginPanel onLogin={handleLogin} loading={authLoading} />;
  }

  const summary = metrics?.summary || {};
  const series = metrics?.series || {};
  const wsMeta = wsStateMeta[wsState] || wsStateMeta.disconnected;
  const topOrders = [...orders]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);
  const topTrades = [...trades]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <h1>GRVT AS 做市控制台</h1>
          <p>交易对: {status?.symbol || "-"}</p>
        </div>
        <div className="actions">
          <button className="btn-primary" onClick={commandStart}>
            启动
          </button>
          <button className="btn-danger" onClick={commandStop}>
            停止
          </button>
          <button onClick={logout}>退出</button>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}
      {notice && <div className="notice-banner">{notice}</div>}

      <section className="cards">
        <div className="card">
          <span>引擎模式</span>
          <strong>{status?.mode || "-"}</strong>
        </div>
        <div className="card">
          <span>WS 连接</span>
          <strong className={wsMeta.className}>{wsMeta.label}</strong>
        </div>
        <div className="card">
          <span>账户权益</span>
          <strong>{fmt(summary.equity, 2)}</strong>
        </div>
        <div className="card">
          <span>可用资金(USDT)</span>
          <strong>{fmt(summary.free_usdt, 2)}</strong>
        </div>
        <div className="card">
          <span>总PnL</span>
          <strong>{fmt(summary.pnl_total, 2)}</strong>
        </div>
        <div className="card">
          <span>净仓名义</span>
          <strong>{fmt(summary.inventory_notional, 2)}</strong>
        </div>
        <div className="card">
          <span>库存占用比(可用×杠杆)</span>
          <strong>{fmt((summary.inventory_usage_ratio || 0) * 100, 2)}%</strong>
        </div>
        <div className="card">
          <span>运行时长</span>
          <strong>{formatDuration(summary.run_duration_sec)}</strong>
        </div>
        <div className="card">
          <span>本次策略成交量</span>
          <strong>{fmt(summary.total_trade_volume_notional, 2)}</strong>
        </div>
        <div className="card">
          <span>每万交易额磨损</span>
          <strong>{fmt(summary.wear_per_10k, 2)}</strong>
        </div>
      </section>

      <section className="charts-grid">
        <LineChart title="Sigma" points={series.sigma} color="#22d3ee" />
        <LineChart title="Spread(bps)" points={series.spread_bps} color="#f59e0b" />
        <LineChart title="Inventory Notional" points={series.inventory_notional} color="#22c55e" />
        <LineChart title="Pnl Total" points={series.pnl_total || []} color="#38bdf8" />
        <LineChart title="Bid Distance(bps)" points={series.distance_bid_bps} color="#6366f1" />
        <LineChart title="Ask Distance(bps)" points={series.distance_ask_bps} color="#f43f5e" />
      </section>

      <section className="panel-grid">
        <div className="panel">
          <h2>策略配置（AS 核心）</h2>
          <p className="panel-tip">填写交易对、AS 三参数（gamma/sigma/k）和两项风控（最大回撤、最大库存占比）。</p>
          <div className="form-grid">
            <label>
              <span>交易对</span>
              <select
                value={strategyForm.symbol}
                onChange={(e) => setStrategyForm((s) => ({ ...s, symbol: e.target.value }))}
              >
                {symbolOptions.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Gamma (γ)</span>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={strategyForm.as_gamma}
                onChange={(e) => setStrategyForm((s) => ({ ...s, as_gamma: e.target.value }))}
              />
            </label>
            <label>
              <span>Sigma (σ, 兜底值)</span>
              <input
                type="number"
                step="0.0001"
                min="0.000001"
                value={strategyForm.as_sigma}
                onChange={(e) => setStrategyForm((s) => ({ ...s, as_sigma: e.target.value }))}
              />
            </label>
            <label>
              <span>Liquidity k</span>
              <input
                type="number"
                step="0.1"
                min="0.1"
                value={strategyForm.as_liquidity_k}
                onChange={(e) => setStrategyForm((s) => ({ ...s, as_liquidity_k: e.target.value }))}
              />
            </label>
            <label>
              <span>最大回撤(%)</span>
              <input
                type="number"
                step="0.1"
                min="0.1"
                value={strategyForm.max_drawdown_pct}
                onChange={(e) => setStrategyForm((s) => ({ ...s, max_drawdown_pct: e.target.value }))}
              />
            </label>
            <label>
              <span>最大库存占比(权益比)</span>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={strategyForm.max_inventory_equity_ratio}
                onChange={(e) => setStrategyForm((s) => ({ ...s, max_inventory_equity_ratio: e.target.value }))}
              />
            </label>
            <button className="btn-primary" disabled={strategySaving} onClick={saveStrategy}>
              {strategySaving ? "保存中..." : "应用策略参数"}
            </button>
          </div>
          <div className="preview-list">
            <div>实盘 sigma 以市场实时估计为主，手动 sigma 用于冷启动兜底。</div>
            <div>最小重挂在簿时长(秒): {fmt(strategyConfig?.runtime_preview?.min_order_age_before_requote_sec, 2)}</div>
            <div>挂单存活上限(秒): {fmt(strategyConfig?.runtime_preview?.order_ttl_sec, 2)}</div>
            <div>预估刷新间隔(秒): {fmt(strategyConfig?.runtime_preview?.quote_interval_sec, 2)}</div>
            <div>
              预估价差区间(bps): {fmt(strategyConfig?.runtime_preview?.min_spread_bps, 2)} ~{" "}
              {fmt(strategyConfig?.runtime_preview?.max_spread_bps, 2)}
            </div>
            <div>每万交易额磨损: {fmt(summary.wear_per_10k, 2)}</div>
          </div>
        </div>

        <div className="panel">
          <h2>实盘配置</h2>
          <p className="panel-tip">服务仍固定为 GRVT prod，仅在引擎 idle/halted 时允许修改凭据。</p>

          <div className="readonly-field">
            <span>GRVT 环境</span>
            <strong>prod（固定实盘）</strong>
          </div>

          <div className="form-grid">
            <label>
              <span>GRVT_API_KEY</span>
              <input
                type="password"
                value={apiForm.grvt_api_key}
                placeholder="留空表示保持原值"
                onChange={(e) => setApiForm((s) => ({ ...s, grvt_api_key: e.target.value }))}
              />
            </label>

            <label>
              <span>GRVT_API_SECRET</span>
              <input
                type="password"
                value={apiForm.grvt_api_secret}
                placeholder="留空表示保持原值"
                onChange={(e) => setApiForm((s) => ({ ...s, grvt_api_secret: e.target.value }))}
              />
            </label>

            <label>
              <span>GRVT_TRADING_ACCOUNT_ID</span>
              <input
                value={apiForm.grvt_trading_account_id}
                placeholder="留空表示保持原值"
                onChange={(e) => setApiForm((s) => ({ ...s, grvt_trading_account_id: e.target.value }))}
              />
            </label>

            <button className="btn-primary" disabled={!canEditApi || exchangeSaving} onClick={saveExchange}>
              {exchangeSaving ? "保存中..." : "保存实盘 API 配置"}
            </button>
          </div>

          <h3 className="sub-title">Telegram 告警配置</h3>
          <p className="panel-tip">支持 Bot Token 与 Chat ID，关键状态与心跳摘要由后端统一发送。</p>
          <div className="form-grid">
            <label>
              <span>TELEGRAM_BOT_TOKEN</span>
              <input
                type="password"
                value={telegramForm.telegram_bot_token}
                placeholder="留空表示保持原值"
                onChange={(e) => setTelegramForm((s) => ({ ...s, telegram_bot_token: e.target.value }))}
              />
            </label>

            <label>
              <span>TELEGRAM_CHAT_ID</span>
              <input
                value={telegramForm.telegram_chat_id}
                placeholder="留空表示保持原值"
                onChange={(e) => setTelegramForm((s) => ({ ...s, telegram_chat_id: e.target.value }))}
              />
            </label>

            <button className="btn-primary" disabled={!canEditApi || telegramSaving} onClick={saveTelegram}>
              {telegramSaving ? "保存中..." : "保存 Telegram 配置"}
            </button>

            {!canEditApi && <div className="block-hint">引擎运行中不可修改配置，请先停止。</div>}
          </div>

          <ul className="status-list">
            <li>GRVT_API_KEY: {exchangeConfig?.grvt_api_key_configured ? "已配置" : "未配置"}</li>
            <li>GRVT_API_SECRET: {exchangeConfig?.grvt_api_secret_configured ? "已配置" : "未配置"}</li>
            <li>
              GRVT_TRADING_ACCOUNT_ID: {exchangeConfig?.grvt_trading_account_id_configured ? "已配置" : "未配置"}
            </li>
            <li>TELEGRAM_BOT_TOKEN: {telegramConfig?.telegram_bot_token_configured ? "已配置" : "未配置"}</li>
            <li>TELEGRAM_CHAT_ID: {telegramConfig?.telegram_chat_id_configured ? "已配置" : "未配置"}</li>
            <li>JWT密钥: {secrets?.app_jwt_secret_configured ? "已配置" : "未配置"}</li>
            <li>Telegram总状态: {secrets?.telegram_configured ? "已配置" : "未配置"}</li>
          </ul>
        </div>
      </section>

      <section className="tables">
        <div className="panel table-panel">
          <h2>当前挂单</h2>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>方向</th>
                <th>价格</th>
                <th>数量</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {topOrders.map((o) => (
                <tr key={o.order_id}>
                  <td>{o.order_id}</td>
                  <td>{o.side}</td>
                  <td>{fmt(o.price, 4)}</td>
                  <td>{fmt(o.size, 4)}</td>
                  <td>{o.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="panel table-panel">
          <h2>最近成交</h2>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>方向</th>
                <th>价格</th>
                <th>数量</th>
                <th>手续费</th>
                <th>类型</th>
              </tr>
            </thead>
            <tbody>
              {topTrades.map((t) => (
                <tr key={t.trade_id}>
                  <td>{t.trade_id}</td>
                  <td>{t.side}</td>
                  <td>{fmt(t.price, 4)}</td>
                  <td>{fmt(t.size, 4)}</td>
                  <td>{fmt(t.fee, 6)}</td>
                  <td className={t.fee_side === "rebate" ? "fee-rebate" : t.fee_side === "cost" ? "fee-cost" : ""}>
                    {t.fee_side || "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

