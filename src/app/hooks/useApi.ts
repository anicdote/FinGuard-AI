/**
 * Data hooks — lightweight fetch + state wrappers.
 */

import { useState, useEffect, useCallback } from "react";
import { caseApi, analyticsApi, transactionApi } from "../services/api";

function useAsync<T>(fn: () => Promise<T>, deps: any[] = []) {
  const [data,    setData]    = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  const execute = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fn());
    } catch (e: any) {
      setError(e.message ?? "Error");
      setData(null);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => { execute(); }, [execute]);

  return { data, loading, error, refetch: execute };
}

export function useCases(params?: { status?: string; priority?: string }) {
  return useAsync(
    () => caseApi.list(params ?? {}),
    [params?.status, params?.priority]
  );
}

export function useCase(id: string) {
  // Don't call API with empty id
  return useAsync(
    () => id ? caseApi.get(id) : Promise.reject(new Error("No case ID")),
    [id]
  );
}

export function useCaseSummary() {
  return useAsync(() => caseApi.summary(), []);
}

export function useDashboardStats() {
  return useAsync(() => analyticsApi.dashboard(), []);
}

export function useTransactions(limit = 50) {
  return useAsync(() => transactionApi.list(limit), [limit]);
}

export function useTransactionStats() {
  return useAsync(() => transactionApi.stats(), []);
}

export function useTrend(days = 30) {
  return useAsync(() => analyticsApi.trend(days), [days]);
}
