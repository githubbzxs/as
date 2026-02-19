import { useEffect, useMemo, useState } from "react";
import {
  fetchExchangeConfig,
  fetchMetrics,
  fetchOpenOrders,
  fetchRecentTrades,
  fetchRuntimeConfig,
  fetchRuntimeProfile,
  fetchSecretsStatus,
  fetchStatus,
  fetchTelegramConfig,
  login,
  startEngine,
  stopEngine,
  updateExchangeConfig,
  updateRuntimeConfig,
  updateRuntimeProfile,
  updateTelegramConfig,
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

const runtimeFieldMeta = [
  {
    key: "symbol",
    label: "交易对",
    type: "text",
    meaning: "策略运行标的。",
    up: "切换到更活跃标的可能提升成交。",
    down: "低流动标的会降低成交节奏。",
  },
  {
    key: "equity_risk_pct",
    label: "权益风险占比",
    type: "number",
    step: 0.001,
    meaning: "单轮下单规模参考权益比例。",
    up: "成交与风险都放大。",
    down: "风险降低但成交变慢。",
  },
  {
    key: "max_inventory_notional_pct",
    label: "库存名义占比上限",
    type: "number",
    step: 0.01,
    meaning: "库存上限=权益×该比例。",
    up: "允许更大净仓。",
    down: "更快触发库存限制。",
  },
  {
    key: "max_inventory_notional",
    label: "固定库存上限(兼容)",
    type: "number",
    step: 1,
    meaning: "占比模式关闭时使用的固定值。",
    up: "容忍更大净仓。",
    down: "仓位控制更紧。",
  },
  {
    key: "max_single_order_notional",
    label: "单笔最大名义",
    type: "number",
    step: 1,
    meaning: "每笔挂单名义上限。",
    up: "单笔成交能力提高。",
    down: "下单冲击更小。",
  },
  {
    key: "min_spread_bps",
    label: "最小价差(bps)",
    type: "number",
    step: 0.01,
    meaning: "报价下限。",
    up: "更保守。",
    down: "更贴盘口。",
  },
  {
    key: "max_spread_bps",
    label: "最大价差(bps)",
    type: "number",
    step: 0.01,
    meaning: "报价上限。",
    up: "波动时更保守。",
    down: "始终更激进。",
  },
  {
    key: "requote_threshold_bps",
    label: "重报价阈值(bps)",
    type: "number",
    step: 0.01,
    meaning: "盘口偏离触发重挂阈值。",
    up: "撤改单更少。",
    down: "跟价更快。",
  },
  {
    key: "order_ttl_sec",
    label: "挂单TTL(秒)",
    type: "number",
    step: 1,
    meaning: "订单在簿最长停留时间。",
    up: "驻留更久。",
    down: "刷新更快。",
  },
  {
    key: "quote_interval_sec",
    label: "主循环间隔(秒)",
    type: "number",
    step: 0.01,
    meaning: "策略每轮执行间隔。",
    up: "响应更慢。",
    down: "响应更快。",
  },
  {
    key: "min_order_size_base",
    label: "最小下单量保护",
    type: "number",
    step: 0.0001,
    meaning: "防止小于交易所最小量。",
    up: "最小量拒单更少。",
    down: "粒度更细。",
  },
  {
    key: "sigma_window_sec",
    label: "sigma窗口(秒)",
    type: "number",
    step: 1,
    meaning: "波动估计窗口。",
    up: "曲线更平滑。",
    down: "响应更灵敏。",
  },
  {
    key: "depth_window_sec",
    label: "深度窗口(秒)",
    type: "number",
    step: 1,
    meaning: "盘口深度统计窗口。",
    up: "估计更稳。",
    down: "反应更快。",
  },
  {
    key: "trade_intensity_window_sec",
    label: "成交强度窗口(秒)",
    type: "number",
    step: 1,
    meaning: "成交强度统计窗口。",
    up: "更平滑。",
    down: "更灵敏。",
  },
  {
    key: "drawdown_kill_pct",
    label: "回撤熔断阈值(%)",
    type: "number",
    step: 0.1,
    meaning: "权益回撤触发熔断阈值。",
    up: "更耐受回撤。",
    down: "更早止损。",
  },
  {
    key: "volatility_kill_zscore",
    label: "波动熔断Z阈值",
    type: "number",
    step: 0.1,
    meaning: "异常波动触发熔断阈值。",
    up: "更迟钝。",
    down: "更敏感。",
  },
  {
    key: "max_consecutive_failures",
    label: "连续失败阈值",
    type: "number",
    step: 1,
    meaning: "连续失败达到该值熔断。",
    up: "容错更高。",
    down: "保护更早。",
  },
  {
    key: "recovery_readonly_sec",
    label: "恢复只读时长(秒)",
    type: "number",
    step: 1,
    meaning: "风控恢复后的观察时长。",
    up: "更稳健。",
    down: "恢复更快。",
  },
  {
    key: "base_gamma",
    label: "基础γ",
    type: "number",
    step: 0.001,
    meaning: "AS 基础风险厌恶系数。",
    up: "报价更保守。",
    down: "报价更激进。",
  },
  {
    key: "gamma_min",
    label: "γ下限",
    type: "number",
    step: 0.001,
    meaning: "动态γ最小保护值。",
    up: "最低风险更高。",
    down: "可更激进。",
  },
  {
    key: "gamma_max",
    label: "γ上限",
    type: "number",
    step: 0.001,
    meaning: "动态γ最大保护值。",
    up: "极端时更保守。",
    down: "上限更低。",
  },
  {
    key: "liquidity_k",
    label: "流动性k",
    type: "number",
    step: 0.01,
    meaning: "AS 流动性参数。",
    up: "报价更保守。",
    down: "报价更贴盘。",
  },
  {
    key: "tg_heartbeat_enabled",
    label: "Telegram心跳开关",
    type: "boolean",
    meaning: "是否发送周期运行摘要。",
    up: "开启周期摘要。",
    down: "仅发送关键事件。",
  },
  {
    key: "tg_heartbeat_interval_sec",
    label: "Telegram心跳间隔(秒)",
    type: "number",
    step: 1,
    meaning: "周期摘要发送间隔。",
    up: "消息更少。",
    down: "消息更实时。",
  },
  {
    key: "close_retry_base_delay_sec",
    label: "平仓重试基础延迟(秒)",
    type: "number",
    step: 0.01,
    meaning: "taker 平仓失败首次重试间隔。",
    up: "重试更平缓。",
    down: "重试更快。",
  },
  {
    key: "close_retry_max_delay_sec",
    label: "平仓重试最大延迟(秒)",
    type: "number",
    step: 0.01,
    meaning: "指数退避最大间隔。",
    up: "更稳但更慢。",
    down: "更快重试。",
  },
  {
    key: "close_position_epsilon_base",
    label: "平仓完成阈值",
    type: "number",
    step: 0.000001,
    meaning: "净仓绝对值小于该值视为平仓完成。",
    up: "更快判定完成。",
    down: "更严格清仓。",
  },
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

function sliderValue(value) {
  if (value === null || value === undefined) return 0;
  const num = Number(value);
  if (Number.isNaN(num)) return 0;
  return Math.max(0, Math.min(100, num));
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

function RuntimeField({ meta, value, onChange }) {
  if (meta.type === "boolean") {
    return (
      <label className="runtime-field runtime-field-checkbox">
        <div className="runtime-label">{meta.label}</div>
        <input type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />
        <div className="runtime-help">
          <div>含义：{meta.meaning}</div>
          <div>调大：{meta.up}</div>
          <div>调小：{meta.down}</div>
        </div>
      </label>
    );
  }
  return (
    <label className="runtime-field">
      <div className="runtime-label">{meta.label}</div>
      <input
        type={meta.type === "number" ? "number" : "text"}
        step={meta.step || "any"}
        value={value ?? ""}
        onChange={(e) => {
          if (meta.type === "number") {
            const num = Number(e.target.value);
            if (!Number.isFinite(num)) return;
            onChange(num);
            return;
          }
          onChange(e.target.value);
        }}
      />
      <div className="runtime-help">
        <div>含义：{meta.meaning}</div>
        <div>调大：{meta.up}</div>
        <div>调小：{meta.down}</div>
      </div>
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
  const [runtimeConfig, setRuntimeConfig] = useState(null);
  const [runtimeDraft, setRuntimeDraft] = useState(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [exchangeConfig, setExchangeConfig] = useState(null);
  const [telegramConfig, setTelegramConfig] = useState(null);
  const [secrets, setSecrets] = useState(null);
  const [orders, setOrders] = useState([]);
  const [trades, setTrades] = useState([]);

  const [apiForm, setApiForm] = useState({
    grvt_api_key: "",
    grvt_api_secret: "",
    grvt_trading_account_id: "",
    clear_grvt_api_key: false,
    clear_grvt_api_secret: false,
    clear_grvt_trading_account_id: false,
  });
  const [telegramForm, setTelegramForm] = useState({
    telegram_bot_token: "",
    telegram_chat_id: "",
    clear_telegram_bot_token: false,
    clear_telegram_chat_id: false,
  });

  const [profileSaving, setProfileSaving] = useState(false);
  const [runtimeSaving, setRuntimeSaving] = useState(false);
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
    const [profileRes, runtimeRes, exchangeRes, telegramRes, secretRes] = await Promise.all([
      fetchRuntimeProfile(token),
      fetchRuntimeConfig(token),
      fetchExchangeConfig(token),
      fetchTelegramConfig(token),
      fetchSecretsStatus(token),
    ]);
    setRuntimeProfile(profileRes);
    setRuntimeConfig(runtimeRes);
    setRuntimeDraft(runtimeRes);
    setExchangeConfig(exchangeRes);
    setTelegramConfig(telegramRes);
    setSecrets(secretRes);
    setApiForm((prev) => ({
      ...prev,
      grvt_api_key: "",
      grvt_api_secret: "",
      grvt_trading_account_id: "",
      clear_grvt_api_key: false,
      clear_grvt_api_secret: false,
      clear_grvt_trading_account_id: false,
    }));
    setTelegramForm((prev) => ({
      ...prev,
      telegram_bot_token: "",
      telegram_chat_id: "",
      clear_telegram_bot_token: false,
      clear_telegram_chat_id: false,
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
      const raw = await fetchRuntimeConfig(token);
      setRuntimeConfig(raw);
      setRuntimeDraft(raw);
      setNotice("自动参数已保存");
    } catch (err) {
      setError(err.message || "保存自动参数失败");
    } finally {
      setProfileSaving(false);
    }
  }

  async function saveRuntimeAdvanced() {
    if (!runtimeDraft) return;
    setRuntimeSaving(true);
    setNotice("");
    try {
      const updated = await updateRuntimeConfig(token, runtimeDraft);
      setRuntimeConfig(updated);
      setRuntimeDraft(updated);
      const profile = await fetchRuntimeProfile(token);
      setRuntimeProfile(profile);
      setNotice("高级参数已保存");
    } catch (err) {
      setError(err.message || "保存高级参数失败");
    } finally {
      setRuntimeSaving(false);
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
        clear_grvt_api_key: apiForm.clear_grvt_api_key,
        clear_grvt_api_secret: apiForm.clear_grvt_api_secret,
        clear_grvt_trading_account_id: apiForm.clear_grvt_trading_account_id,
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
        clear_telegram_bot_token: telegramForm.clear_telegram_bot_token,
        clear_telegram_chat_id: telegramForm.clear_telegram_chat_id,
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
          <span>总PnL</span>
          <strong>{fmt(summary.pnl_total, 2)}</strong>
        </div>
        <div className="card">
          <span>当日PnL</span>
          <strong>{fmt(summary.pnl_daily, 2)}</strong>
        </div>
        <div className="card">
          <span>净仓名义</span>
          <strong>{fmt(summary.inventory_notional, 2)}</strong>
        </div>
        <div className="card">
          <span>动态价差(bps)</span>
          <strong>{fmt(summary.spread_bps, 2)}</strong>
        </div>
        <div className="card">
          <span>实时波动(sigma)</span>
          <strong>{fmt(summary.sigma, 6)}</strong>
        </div>
        <div className="card">
          <span>运行时长</span>
          <strong>{formatDuration(summary.run_duration_sec)}</strong>
        </div>
        <div className="card">
          <span>累计交易量</span>
          <strong>{fmt(summary.total_trade_volume_notional, 2)}</strong>
        </div>
        <div className="card">
          <span>累计成交笔数</span>
          <strong>{fmt(summary.total_trade_count, 0)}</strong>
        </div>
        <div className="card">
          <span>手续费(返佣/成本)</span>
          <strong>
            {fmt(summary.total_fee_rebate, 4)} / {fmt(summary.total_fee_cost, 4)}
          </strong>
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
          <h2>自动参数（默认）</h2>
          <p className="panel-tip">默认使用三旋钮自动映射。你也可以展开高级参数手动覆盖全部运行参数。</p>
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
                <div>库存占比上限: {fmt(runtimeProfile.runtime_preview?.max_inventory_notional_pct, 3)}</div>
                <div>
                  动态库存名义估算:{" "}
                  {fmt((summary.equity || 0) * (runtimeProfile.runtime_preview?.max_inventory_notional_pct || 0), 2)}
                </div>
                <div>回撤熔断(%): {fmt(runtimeProfile.runtime_preview?.drawdown_kill_pct, 2)}</div>
              </div>
            </div>
          )}

          <div className="advanced-toggle">
            <button onClick={() => setAdvancedOpen((s) => !s)}>
              {advancedOpen ? "收起高级参数" : "展开高级参数（全量可调）"}
            </button>
          </div>

          {advancedOpen && runtimeDraft && (
            <div className="runtime-grid">
              {runtimeFieldMeta.map((meta) => (
                <RuntimeField
                  key={meta.key}
                  meta={meta}
                  value={runtimeDraft[meta.key]}
                  onChange={(nextValue) => setRuntimeDraft((prev) => ({ ...prev, [meta.key]: nextValue }))}
                />
              ))}
              <button className="btn-primary" disabled={runtimeSaving} onClick={saveRuntimeAdvanced}>
                {runtimeSaving ? "保存中..." : "保存高级参数"}
              </button>
              {runtimeConfig && <div className="panel-tip">当前配置版本已载入，可随时覆盖保存。</div>}
            </div>
          )}
        </div>

        <div className="panel">
          <h2>实盘配置</h2>
          <p className="panel-tip">默认固定为 GRVT prod 实盘环境，仅在引擎 idle/halted 时允许修改。</p>

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
                disabled={telegramForm.clear_telegram_bot_token}
                placeholder="留空表示保持原值"
                onChange={(e) => setTelegramForm((s) => ({ ...s, telegram_bot_token: e.target.value }))}
              />
            </label>

            <label>
              <span>TELEGRAM_CHAT_ID</span>
              <input
                value={telegramForm.telegram_chat_id}
                disabled={telegramForm.clear_telegram_chat_id}
                placeholder="留空表示保持原值"
                onChange={(e) => setTelegramForm((s) => ({ ...s, telegram_chat_id: e.target.value }))}
              />
            </label>

            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={telegramForm.clear_telegram_bot_token}
                onChange={(e) => setTelegramForm((s) => ({ ...s, clear_telegram_bot_token: e.target.checked }))}
              />
              <span>清空已保存 Bot Token</span>
            </label>

            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={telegramForm.clear_telegram_chat_id}
                onChange={(e) => setTelegramForm((s) => ({ ...s, clear_telegram_chat_id: e.target.checked }))}
              />
              <span>清空已保存 Chat ID</span>
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
              GRVT_TRADING_ACCOUNT_ID:{" "}
              {exchangeConfig?.grvt_trading_account_id_configured ? "已配置" : "未配置"}
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
                <th>类型</th>
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
