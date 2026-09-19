/**
 * Pollution API client — connects frontend to Pollution Agent backend.
 * No external API is selected or hardcoded here.
 */
const POLLUTION_API_BASE = '/api/pollution';

async function fetchPollution(endpoint, options = {}) {
  const url = `${POLLUTION_API_BASE}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    return await res.json();
  } catch (err) {
    console.error(`[PollutionAPI] ${endpoint} failed:`, err);
    return { status: 'error', message: err.message };
  }
}

export const pollutionApi = {
  getCurrent: () => fetchPollution('/current'),
  getPollutants: () => fetchPollution('/pollutants'),
  getTrend: (range = '24h') => fetchPollution(`/trend?range=${range}`),
  getHotspots: () => fetchPollution('/hotspots'),
  getDistribution: () => fetchPollution('/distribution'),
  getAreaTrends: () => fetchPollution('/areas/trend'),
  getForecastDaily: () => fetchPollution('/forecast/daily'),
  getForecast7Day: () => fetchPollution('/forecast/7day'),
  getForecastHourly: () => fetchPollution('/forecast/hourly'),
  getAlerts: () => fetchPollution('/alerts'),
  getSummary: () => fetchPollution('/summary'),
  getInfo: () => fetchPollution('/info'),
  predict: (days) => fetchPollution('/predict', {
    method: 'POST',
    body: JSON.stringify({ days }),
  }),
};

export default pollutionApi;
