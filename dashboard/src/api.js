const API_BASE = "/api";

export async function fetcher(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    err.info = await res.text().catch(() => null);
    throw err;
  }
  return res.json();
}

export const urls = {
  status: () => "/status",
  alerts: ({ days = 7, component } = {}) =>
    `/alerts?days=${days}${component ? `&component=${component}` : ""}`,
  wallets: () => "/wallets",
  walletDetail: (addr) => `/wallets/${addr}`,
  walletTrades: (addr, limit = 100) => `/wallets/${addr}/trades?limit=${limit}`,
  performance: (days = 30) => `/performance?days=${days}`,
  hotMarkets: () => "/markets/hot",
  audit: (limit = 50) => `/audit?limit=${limit}`,
  costs: () => "/costs",
  clusters: () => "/clusters",
};
