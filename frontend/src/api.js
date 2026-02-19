const jsonHeaders = {
  "Content-Type": "application/json",
};

export async function apiRequest(path, { method = "GET", token, body } = {}) {
  const headers = { ...jsonHeaders };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function login(username, password) {
  return apiRequest("/api/auth/login", {
    method: "POST",
    body: { username, password },
  });
}

export async function fetchStatus(token) {
  return apiRequest("/api/status", { token });
}

export async function fetchMetrics(token) {
  return apiRequest("/api/metrics", { token });
}

export async function fetchRuntimeConfig(token) {
  return apiRequest("/api/config/runtime", { token });
}

export async function updateRuntimeConfig(token, payload) {
  return apiRequest("/api/config/runtime", {
    method: "PUT",
    token,
    body: payload,
  });
}

export async function fetchRuntimeProfile(token) {
  return apiRequest("/api/config/runtime/profile", { token });
}

export async function updateRuntimeProfile(token, payload) {
  return apiRequest("/api/config/runtime/profile", {
    method: "PUT",
    token,
    body: payload,
  });
}

export async function fetchExchangeConfig(token) {
  return apiRequest("/api/config/exchange", { token });
}

export async function updateExchangeConfig(token, payload) {
  return apiRequest("/api/config/exchange", {
    method: "PUT",
    token,
    body: payload,
  });
}

export async function fetchSecretsStatus(token) {
  return apiRequest("/api/config/secrets/status", { token });
}

export async function fetchOpenOrders(token) {
  return apiRequest("/api/orders/open", { token });
}

export async function fetchRecentTrades(token) {
  return apiRequest("/api/trades/recent", { token });
}

export async function startEngine(token) {
  return apiRequest("/api/engine/start", {
    method: "POST",
    token,
  });
}

export async function stopEngine(token) {
  return apiRequest("/api/engine/stop", {
    method: "POST",
    token,
  });
}
