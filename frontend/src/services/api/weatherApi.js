/**
 * Weather API client — connects frontend to SUPADSP Weather Agent backend.
 */
const WEATHER_API_BASE = '/api/v1/weather';

async function fetchWeather(endpoint, options = {}) {
  const url = `${WEATHER_API_BASE}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    return await res.json();
  } catch (err) {
    console.warn(`[WeatherAPI] ${endpoint} failed:`, err);
    return null;
  }
}

export const weatherApi = {
  getCurrent: (location = 'Hyderabad') =>
    fetchWeather(`/current?location=${encodeURIComponent(location)}`),

  getForecast: (location = 'Hyderabad') =>
    fetchWeather(`/forecast?location=${encodeURIComponent(location)}`),

  getAlerts: (location = 'Hyderabad') =>
    fetchWeather(`/alerts?location=${encodeURIComponent(location)}`),

  analyze: (location = 'Hyderabad', objective = '') =>
    fetchWeather('/analyze', {
      method: 'POST',
      body: JSON.stringify({ location, objective }),
    }),

  chat: (question, location = 'Hyderabad') =>
    fetchWeather('/chat', {
      method: 'POST',
      body: JSON.stringify({ question, location }),
    }),
};

export default weatherApi;
