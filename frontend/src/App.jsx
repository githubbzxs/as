import { useEffect, useMemo, useState } from "react";
import {
  fetchMetrics,
  fetchOpenOrders,
  fetchRecentTrades,
  fetchRuntimeConfig,
  fetchSecretsStatus,
  fetchStatus,
  login,
  startEngine,
  stopEngine,
  updateRuntimeConfig,
} from "./api";

const initialLogin = { username: "admin", password: "" };

function fmt(value, digits = 4) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toFixed(digits);
}

function LineChart({ title, points, color = "#0ea5e9" }) {
  const values = (points || []).map((p) => Number(p.value));
  const width = 360;
  const height = 110;

  const path = useMemo(() => {
    if (!values.length) return "";
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    return values
      .map((v, i) => {
        const x = (i / Math.max(1, values.length - 1)) * width;
        const y = height - ((v - min) / span) * height;
        return `${i === 0 ? "M" : "L"}${x},${y}`;
      })
      .join(" ");
  }, [values]);

  return (
    <div className="chart-card">
      <div className="chart-title">{title}</div>
      <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg" preserveAspectRatio="none">
        <path d={path} fill="none" stroke={color} strokeWidth="2" />
      </svg>
      <div className="chart-meta">
        最新: {values.length ? fmt(values[values.length - 1], 6) : "-"}
      </div>
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
  const [runtimeConfig, setRuntimeConfig] = useState(null);
  const [secrets, setSecrets] = useState(null);
  const [orders, setOrders] = useState([]);
  const [trades, setTrades] = useState([]);
  const [error, setError] = useState("");

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

  async function loadAll() {
    if (!token) return;
    const [statusRes, metricsRes, cfgRes, secretRes, orderRes, tradeRes] = await Promise.all([
      fetchStatus(token),
      fetchMetrics(token),
      fetchRuntimeConfig(token),
      fetchSecretsStatus(token),
      fetchOpenOrders(token),
      fetchRecentTrades(token),
    ]);
    setStatus(statusRes);
    setMetrics(metricsRes);
    setRuntimeConfig(cfgRes);
    setSecrets(secretRes);
    setOrders(orderRes);
    setTrades(tradeRes);
  }

  useEffect(() => {
    if (!token) return;
    let timer = null;
    let closed = false;

    const start = async () => {
      try {
        await loadAll();
      } catch (err) {
        if (!closed) setError(err.message || "加载失败");
      }
      timer = setInterval(async () => {
        try {
          await loadAll();
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
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/stream?token=${token}`);
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
        }
      } catch {
        // 忽略非关键消息
      }
    };
    ws.onerror = () => {
      setError("WebSocket 连接异常");
    };
    return () => ws.close();
  }, [token]);

  async function commandStart() {
    try {
      await startEngine(token);
      await loadAll();
    } catch (err) {
      setError(err.message || "启动失败");
    }
  }

  async function commandStop() {
    try {
      await stopEngine(token);
      await loadAll();
    } catch (err) {
      setError(err.message || "停止失败");
    }
  }

  async function saveConfig() {
    if (!runtimeConfig) return;
    try {
      const payload = {
        ...runtimeConfig,
        equity_risk_pct: Number(runtimeConfig.equity_risk_pct),
        max_inventory_notional: Number(runtimeConfig.max_inventory_notional),
        max_single_order_notional: Number(runtimeConfig.max_single_order_notional),
        min_spread_bps: Number(runtimeConfig.min_spread_bps),
        max_spread_bps: Number(runtimeConfig.max_spread_bps),
        requote_threshold_bps: Number(runtimeConfig.requote_threshold_bps),
        drawdown_kill_pct: Number(runtimeConfig.drawdown_kill_pct),
        volatility_kill_zscore: Number(runtimeConfig.volatility_kill_zscore),
      };
      const cfg = await updateRuntimeConfig(token, payload);
      setRuntimeConfig(cfg);
    } catch (err) {
      setError(err.message || "保存配置失败");
    }
  }

  function logout() {
    localStorage.removeItem("mm_token");
    setToken("");
  }

  if (!token) {
    return <LoginPanel onLogin={handleLogin} loading={authLoading} />;
  }

  const summary = metrics?.summary;
  const series = metrics?.series || {};

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <h1>GRVT AS 做市控制台</h1>
          <p>交易对: {status?.symbol || "-"}</p>
        </div>
        <div className="actions">
          <button className="btn-primary" onClick={commandStart}>启动</button>
          <button className="btn-danger" onClick={commandStop}>停止</button>
          <button onClick={logout}>退出</button>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <section className="cards">
        <div className="card"><span>引擎模式</span><strong>{status?.mode || "-"}</strong></div>
        <div className="card"><span>账户权益</span><strong>{fmt(summary?.equity, 2)}</strong></div>
        <div className="card"><span>PnL</span><strong>{fmt(summary?.pnl, 2)}</strong></div>
        <div className="card"><span>净仓名义</span><strong>{fmt(summary?.inventory_notional, 2)}</strong></div>
        <div className="card"><span>动态价差(bps)</span><strong>{fmt(summary?.spread_bps, 2)}</strong></div>
        <div className="card"><span>实时波动(sigma)</span><strong>{fmt(summary?.sigma, 6)}</strong></div>
      </section>

      <section className="charts-grid">
        <LineChart title="Sigma" points={series.sigma} color="#0ea5e9" />
        <LineChart title="Spread(bps)" points={series.spread_bps} color="#f97316" />
        <LineChart title="Inventory Notional" points={series.inventory_notional} color="#22c55e" />
      </section>

      <section className="panel-grid">
        <div className="panel">
          <h2>运行参数</h2>
          {runtimeConfig && (
            <div className="form-grid">
              {["equity_risk_pct", "max_inventory_notional", "max_single_order_notional", "min_spread_bps", "max_spread_bps", "requote_threshold_bps", "drawdown_kill_pct", "volatility_kill_zscore"].map((key) => (
                <label key={key}>
                  <span>{key}</span>
                  <input
                    value={runtimeConfig[key]}
                    onChange={(e) => setRuntimeConfig((s) => ({ ...s, [key]: e.target.value }))}
                  />
                </label>
              ))}
              <button className="btn-primary" onClick={saveConfig}>保存参数</button>
            </div>
          )}
        </div>

        <div className="panel">
          <h2>密钥状态</h2>
          <ul className="status-list">
            <li>GRVT_API_KEY: {secrets?.grvt_api_key_configured ? "已配置" : "未配置"}</li>
            <li>GRVT_API_SECRET: {secrets?.grvt_api_secret_configured ? "已配置" : "未配置"}</li>
            <li>GRVT_TRADING_ACCOUNT_ID: {secrets?.grvt_trading_account_id_configured ? "已配置" : "未配置"}</li>
            <li>JWT密钥: {secrets?.app_jwt_secret_configured ? "已配置" : "未配置"}</li>
            <li>Telegram: {secrets?.telegram_configured ? "已配置" : "未配置"}</li>
          </ul>
        </div>
      </section>

      <section className="tables">
        <div className="panel table-panel">
          <h2>当前挂单</h2>
          <table>
            <thead><tr><th>ID</th><th>方向</th><th>价格</th><th>数量</th><th>状态</th></tr></thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.order_id}><td>{o.order_id}</td><td>{o.side}</td><td>{fmt(o.price, 4)}</td><td>{fmt(o.size, 4)}</td><td>{o.status}</td></tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="panel table-panel">
          <h2>最近成交</h2>
          <table>
            <thead><tr><th>ID</th><th>方向</th><th>价格</th><th>数量</th><th>手续费</th></tr></thead>
            <tbody>
              {trades.map((t) => (
                <tr key={t.trade_id}><td>{t.trade_id}</td><td>{t.side}</td><td>{fmt(t.price, 4)}</td><td>{fmt(t.size, 4)}</td><td>{fmt(t.fee, 6)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
