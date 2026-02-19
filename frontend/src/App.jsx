import { useEffect, useMemo, useState } from "react";
import {
  fetchExchangeConfig,
  fetchMetrics,
  fetchOpenOrders,
  fetchRecentTrades,
  fetchRuntimeProfile,
  fetchSecretsStatus,
  fetchStatus,
  login,
  startEngine,
  stopEngine,
  updateExchangeConfig,
  updateRuntimeProfile,
} from "./api";

const initialLogin = { username: "admin", password: "" };

const profileFieldMeta = [
  {
    key: "aggressiveness",
    label: "做市激进度",
    hint: "越高越积极，价差更紧、刷新更快。",
  },
  {
    key: "inventory_tolerance",
    label: "库存容忍度",
    hint: "越高越允许持仓波动，挂单名义上限更大。",
  },
  {
    key: "risk_threshold",
    label: "风险阈值",
    hint: "越高越宽松，熔断阈值更高、只读恢复更快。",
  },
];

function fmt(value, digits = 4) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toFixed(digits);
}

function sliderValue(value) {
  if (value === null || value === undefined) return 0;
  const num = Number(value);
  if (Number.isNaN(num)) return 0;
  return Math.max(0, Math.min(100, num));
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
      <div className="chart-meta">最新: {values.length ? fmt(values[values.length - 1], 6) : "-"}</div>
    </div>
  );
}

function SliderField({ label, value, hint, onChange }) {
  return (
    <label className="slider-field">
      <div className="slider-label-row">
        <span className="slider-label">{label}</span>
        <span className="slider-value">{fmt(value, 0)}</span>
      </div>
      <input
        type="range"
        min="0"
        max="100"
        step="1"
        value={sliderValue(value)}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <div className="slider-hint">{hint}</div>
    </label>
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
  const [runtimeProfile, setRuntimeProfile] = useState(null);
  const [exchangeConfig, setExchangeConfig] = useState(null);
  const [secrets, setSecrets] = useState(null);
  const [orders, setOrders] = useState([]);
  const [trades, setTrades] = useState([]);

  const [apiForm, setApiForm] = useState({
    grvt_env: "testnet",
    grvt_use_mock: true,
    grvt_api_key: "",
    grvt_api_secret: "",
    grvt_trading_account_id: "",
    clear_grvt_api_key: false,
    clear_grvt_api_secret: false,
    clear_grvt_trading_account_id: false,
  });

  const [profileSaving, setProfileSaving] = useState(false);
  const [exchangeSaving, setExchangeSaving] = useState(false);
  const [notice, setNotice] = useState("");
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
    const [profileRes, exchangeRes, secretRes] = await Promise.all([
      fetchRuntimeProfile(token),
      fetchExchangeConfig(token),
      fetchSecretsStatus(token),
    ]);
    setRuntimeProfile(profileRes);
    setExchangeConfig(exchangeRes);
    setSecrets(secretRes);
    setApiForm((prev) => ({
      ...prev,
      grvt_env: exchangeRes.grvt_env,
      grvt_use_mock: exchangeRes.grvt_use_mock,
      grvt_api_key: "",
      grvt_api_secret: "",
      grvt_trading_account_id: "",
      clear_grvt_api_key: false,
      clear_grvt_api_secret: false,
      clear_grvt_trading_account_id: false,
    }));
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
      await loadTradingData();
      setNotice("引擎已启动");
    } catch (err) {
      setError(err.message || "启动失败");
    }
  }

  async function commandStop() {
    try {
      await stopEngine(token);
      await loadTradingData();
      setNotice("引擎已停止");
    } catch (err) {
      setError(err.message || "停止失败");
    }
  }

  async function saveProfile() {
    if (!runtimeProfile) return;
    setProfileSaving(true);
    setNotice("");
    try {
      const payload = {
        aggressiveness: sliderValue(runtimeProfile.aggressiveness),
        inventory_tolerance: sliderValue(runtimeProfile.inventory_tolerance),
        risk_threshold: sliderValue(runtimeProfile.risk_threshold),
      };
      const updated = await updateRuntimeProfile(token, payload);
      setRuntimeProfile(updated);
      setNotice("自动参数已保存");
    } catch (err) {
      setError(err.message || "保存自动参数失败");
    } finally {
      setProfileSaving(false);
    }
  }

  const canEditApi = status?.mode === "idle" || status?.mode === "halted";

  async function saveExchange() {
    if (!canEditApi) {
      setError("引擎运行中禁止修改 API 配置，请先停止引擎");
      return;
    }
    setExchangeSaving(true);
    setNotice("");
    try {
      const payload = {
        grvt_env: apiForm.grvt_env,
        grvt_use_mock: apiForm.grvt_use_mock,
        grvt_api_key: apiForm.grvt_api_key,
        grvt_api_secret: apiForm.grvt_api_secret,
        grvt_trading_account_id: apiForm.grvt_trading_account_id,
        clear_grvt_api_key: apiForm.clear_grvt_api_key,
        clear_grvt_api_secret: apiForm.clear_grvt_api_secret,
        clear_grvt_trading_account_id: apiForm.clear_grvt_trading_account_id,
      };
      const updated = await updateExchangeConfig(token, payload);
      setExchangeConfig(updated);
      await loadConfigData();
      setNotice("API 配置已保存");
    } catch (err) {
      setError(err.message || "保存 API 配置失败");
    } finally {
      setExchangeSaving(false);
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
          <span>账户权益</span>
          <strong>{fmt(summary?.equity, 2)}</strong>
        </div>
        <div className="card">
          <span>PnL</span>
          <strong>{fmt(summary?.pnl, 2)}</strong>
        </div>
        <div className="card">
          <span>净仓名义</span>
          <strong>{fmt(summary?.inventory_notional, 2)}</strong>
        </div>
        <div className="card">
          <span>动态价差(bps)</span>
          <strong>{fmt(summary?.spread_bps, 2)}</strong>
        </div>
        <div className="card">
          <span>实时波动(sigma)</span>
          <strong>{fmt(summary?.sigma, 6)}</strong>
        </div>
      </section>

      <section className="charts-grid">
        <LineChart title="Sigma" points={series.sigma} color="#0ea5e9" />
        <LineChart title="Spread(bps)" points={series.spread_bps} color="#f97316" />
        <LineChart title="Inventory Notional" points={series.inventory_notional} color="#22c55e" />
      </section>

      <section className="panel-grid">
        <div className="panel">
          <h2>自动参数（仅三旋钮）</h2>
          <p className="panel-tip">系统会根据三项控制杆自动映射内部参数，并继续实时自适应。</p>
          {runtimeProfile && (
            <div className="slider-grid">
              {profileFieldMeta.map((field) => (
                <SliderField
                  key={field.key}
                  label={field.label}
                  value={runtimeProfile[field.key]}
                  hint={field.hint}
                  onChange={(value) => setRuntimeProfile((prev) => ({ ...prev, [field.key]: value }))}
                />
              ))}
              <button className="btn-primary" disabled={profileSaving} onClick={saveProfile}>
                {profileSaving ? "保存中..." : "保存自动参数"}
              </button>
              <div className="preview-list">
                <div>风险系数 γ: {fmt(runtimeProfile.runtime_preview?.base_gamma, 3)}</div>
                <div>最小价差(bps): {fmt(runtimeProfile.runtime_preview?.min_spread_bps, 2)}</div>
                <div>最大价差(bps): {fmt(runtimeProfile.runtime_preview?.max_spread_bps, 2)}</div>
                <div>最大库存名义: {fmt(runtimeProfile.runtime_preview?.max_inventory_notional, 2)}</div>
                <div>回撤熔断(%): {fmt(runtimeProfile.runtime_preview?.drawdown_kill_pct, 2)}</div>
              </div>
            </div>
          )}
        </div>

        <div className="panel">
          <h2>API 配置</h2>
          <p className="panel-tip">仅在引擎 idle/halted 时允许修改，保存后密钥不会回显。</p>
          <div className="form-grid">
            <label>
              <span>GRVT 环境</span>
              <select
                value={apiForm.grvt_env}
                onChange={(e) => setApiForm((s) => ({ ...s, grvt_env: e.target.value }))}
              >
                <option value="testnet">testnet</option>
                <option value="prod">prod</option>
                <option value="staging">staging</option>
                <option value="dev">dev</option>
              </select>
            </label>

            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={apiForm.grvt_use_mock}
                onChange={(e) => setApiForm((s) => ({ ...s, grvt_use_mock: e.target.checked }))}
              />
              <span>使用 Mock 交易所</span>
            </label>

            <label>
              <span>GRVT_API_KEY</span>
              <input
                type="password"
                value={apiForm.grvt_api_key}
                disabled={apiForm.clear_grvt_api_key}
                placeholder="留空表示保持原值"
                onChange={(e) => setApiForm((s) => ({ ...s, grvt_api_key: e.target.value }))}
              />
            </label>

            <label>
              <span>GRVT_API_SECRET</span>
              <input
                type="password"
                value={apiForm.grvt_api_secret}
                disabled={apiForm.clear_grvt_api_secret}
                placeholder="留空表示保持原值"
                onChange={(e) => setApiForm((s) => ({ ...s, grvt_api_secret: e.target.value }))}
              />
            </label>

            <label>
              <span>GRVT_TRADING_ACCOUNT_ID</span>
              <input
                value={apiForm.grvt_trading_account_id}
                disabled={apiForm.clear_grvt_trading_account_id}
                placeholder="留空表示保持原值"
                onChange={(e) => setApiForm((s) => ({ ...s, grvt_trading_account_id: e.target.value }))}
              />
            </label>

            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={apiForm.clear_grvt_api_key}
                onChange={(e) => setApiForm((s) => ({ ...s, clear_grvt_api_key: e.target.checked }))}
              />
              <span>清空已保存 API Key</span>
            </label>

            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={apiForm.clear_grvt_api_secret}
                onChange={(e) => setApiForm((s) => ({ ...s, clear_grvt_api_secret: e.target.checked }))}
              />
              <span>清空已保存 API Secret</span>
            </label>

            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={apiForm.clear_grvt_trading_account_id}
                onChange={(e) => setApiForm((s) => ({ ...s, clear_grvt_trading_account_id: e.target.checked }))}
              />
              <span>清空已保存 Trading Account ID</span>
            </label>

            <button className="btn-primary" disabled={!canEditApi || exchangeSaving} onClick={saveExchange}>
              {exchangeSaving ? "保存中..." : "保存 API 配置"}
            </button>
            {!canEditApi && <div className="block-hint">引擎运行中不可修改 API，请先停止。</div>}
          </div>

          <ul className="status-list">
            <li>GRVT_API_KEY: {exchangeConfig?.grvt_api_key_configured ? "已配置" : "未配置"}</li>
            <li>GRVT_API_SECRET: {exchangeConfig?.grvt_api_secret_configured ? "已配置" : "未配置"}</li>
            <li>
              GRVT_TRADING_ACCOUNT_ID:{" "}
              {exchangeConfig?.grvt_trading_account_id_configured ? "已配置" : "未配置"}
            </li>
            <li>JWT密钥: {secrets?.app_jwt_secret_configured ? "已配置" : "未配置"}</li>
            <li>Telegram: {secrets?.telegram_configured ? "已配置" : "未配置"}</li>
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
              {orders.map((o) => (
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
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <tr key={t.trade_id}>
                  <td>{t.trade_id}</td>
                  <td>{t.side}</td>
                  <td>{fmt(t.price, 4)}</td>
                  <td>{fmt(t.size, 4)}</td>
                  <td>{fmt(t.fee, 6)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
