import { useState, useEffect } from 'react';
import { supabase } from '@/integrations/supabase/client';

export interface ProjectionPoint {
  week: number;
  median: number;
  p25: number;
  p75: number;
  milestone: string | null;
  observedAt: string | null;
}

export interface UseProjectionsResult {
  projections: ProjectionPoint[];
  loading: boolean;
  reason: string | null;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function parseProjectionRow(
  value: unknown,
  weekFallback: number,
  observedAt: string | null,
): ProjectionPoint | null {
  const row =
    value !== null && typeof value === 'object' && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : null;
  if (!row) return null;

  const week = isFiniteNumber(row.week) ? row.week : weekFallback;
  const median = isFiniteNumber(row.median) ? row.median : null;
  const p25 = isFiniteNumber(row.p25) ? row.p25 : null;
  const p75 = isFiniteNumber(row.p75) ? row.p75 : null;

  if (median === null || p25 === null || p75 === null) return null;

  const milestone =
    typeof row.milestone === 'string' && row.milestone.trim()
      ? row.milestone.trim()
      : null;

  return { week, median, p25, p75, milestone, observedAt };
}

export function useProjections(): UseProjectionsResult {
  const [projections, setProjections] = useState<ProjectionPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [reason, setReason] = useState<string | null>(null);

  useEffect(() => {
    const fetchProjections = async () => {
      setLoading(true);
      setReason(null);

      try {
        const { data: simData, error } = await supabase
          .from('monte_carlo_simulations')
          .select('results, created_at')
          .order('created_at', { ascending: false })
          .limit(1)
          .single();

        if (error || !simData) {
          setProjections([]);
          setReason(error?.message ?? 'No Monte Carlo simulation results are available.');
          return;
        }

        const observedAt = simData.created_at;
        const results = simData.results;

        if (!Array.isArray(results) || results.length === 0) {
          setProjections([]);
          setReason('The latest Monte Carlo simulation does not contain a weekly projection series.');
          return;
        }

        const parsed = results
          .map((row, idx) => parseProjectionRow(row, idx + 1, observedAt))
          .filter((point): point is ProjectionPoint => point !== null);

        if (parsed.length === 0) {
          setProjections([]);
          setReason('Monte Carlo results exist but do not contain usable weekly projection points.');
          return;
        }

        setProjections(parsed);
      } catch (error) {
        console.error('Failed to fetch projections:', error);
        setProjections([]);
        setReason('Failed to load projection data.');
      } finally {
        setLoading(false);
      }
    };

    fetchProjections();
  }, []);

  return { projections, loading, reason };
}
