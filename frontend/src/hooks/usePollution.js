/**
 * usePollution — React hooks for Pollution dashboard data.
 * Each hook exposes: data, loading, error states.
 * Forecast failure never breaks the rest of the dashboard.
 *
 * Cache TTLs (Pollution-scoped):
 *   current: 5 min | historical: 15 min | forecast: 30 min | metadata: 1 hour
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { pollutionApi } from '../services/api/pollutionApi';

// Simple in-memory cache (Pollution-scoped only)
const cache = {};

function useCachedFetch(key, fetcher, ttlMs = 300000) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const refetch = useCallback(async () => {
    // Check cache
    const cached = cache[key];
    if (cached && Date.now() - cached.time < ttlMs) {
      setData(cached.data);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const result = await fetcher();
      if (!mountedRef.current) return;
      if (result.status === 'error') {
        setError(result.message);
        setData(null);
      } else {
        setData(result);
        cache[key] = { data: result, time: Date.now() };
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err.message);
        setData(null);
      }
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [key, fetcher, ttlMs]);

  useEffect(() => {
    mountedRef.current = true;
    refetch();
    return () => { mountedRef.current = false; };
  }, [refetch]);

  const status = loading ? 'loading' : error ? 'error' : data?.status === 'no_data' ? 'empty' : 'success';
  return { data, loading, error, status, refetch };
}

/** Current AQI summary */
export function usePollutionCurrent() {
  return useCachedFetch('current', pollutionApi.getCurrent, 300000);
}

/** Pollutant concentrations */
export function usePollutants() {
  return useCachedFetch('pollutants', pollutionApi.getPollutants, 300000);
}

/** AQI trend for a given time range */
export function usePollutionTrend(range = '24h') {
  const fetcher = useCallback(() => pollutionApi.getTrend(range), [range]);
  return useCachedFetch(`trend-${range}`, fetcher, 900000);
}

/** AQI hotspots */
export function useHotspots() {
  return useCachedFetch('hotspots', pollutionApi.getHotspots, 300000);
}

/** Daily forecast */
export function useForecast() {
  return useCachedFetch('forecast', pollutionApi.getForecastDaily, 1800000);
}

/** AQI distribution */
export function useDistribution() {
  return useCachedFetch('distribution', pollutionApi.getDistribution, 300000);
}

/** Area trends vs previous period */
export function useAreaTrends() {
  return useCachedFetch('areaTrends', pollutionApi.getAreaTrends, 900000);
}

/** Alerts */
export function useAlerts() {
  return useCachedFetch('alerts', pollutionApi.getAlerts, 300000);
}

/** Full summary (all-in-one for initial load) */
export function usePollutionSummary() {
  return useCachedFetch('summary', pollutionApi.getSummary, 300000);
}

/** Invalidate cache for a specific key or all */
export function invalidatePollutionCache(key = null) {
  if (key) {
    delete cache[key];
  } else {
    Object.keys(cache).forEach(k => delete cache[k]);
  }
}
