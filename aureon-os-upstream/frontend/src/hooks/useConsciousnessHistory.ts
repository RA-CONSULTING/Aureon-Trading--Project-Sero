import { useState, useEffect, useCallback } from 'react';
import { supabase } from '@/integrations/supabase/client';
import type { SchumannData } from '@/lib/earthObservationEvidence';

interface BiometricSnapshot {
  hrv?: number;
  heartRate?: number;
  alpha?: number;
  theta?: number;
  delta?: number;
  beta?: number;
  coherenceIndex?: number;
}

export interface ConsciousnessHistoryData {
  id: string;
  timestamp: string;
  schumann_frequency: number;
  schumann_amplitude: number;
  schumann_quality: number;
  schumann_coherence_boost: number;
  schumann_phase: string;
  hrv: number | null;
  heart_rate: number | null;
  alpha_waves: number | null;
  theta_waves: number | null;
  delta_waves: number | null;
  beta_waves: number | null;
  biometric_coherence_index: number | null;
  celestial_boost: number;
  total_coherence: number;
}

export function useConsciousnessHistory(hoursBack: number = 24) {
  const [historyData, setHistoryData] = useState<ConsciousnessHistoryData[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchHistory = useCallback(async () => {
    try {
      const cutoffTime = new Date();
      cutoffTime.setHours(cutoffTime.getHours() - hoursBack);

      const { data, error } = await supabase
        .from('consciousness_field_history')
        .select('*')
        .gte('timestamp', cutoffTime.toISOString())
        .order('timestamp', { ascending: true })
        .limit(1000);

      if (error) {
        console.error('Error fetching consciousness history:', error);
        return;
      }

      setHistoryData(data || []);
    } catch (error) {
      console.error('Error in fetchHistory:', error);
    } finally {
      setIsLoading(false);
    }
  }, [hoursBack]);

  useEffect(() => {
    fetchHistory();

    // Subscribe to realtime updates
    const channel = supabase
      .channel('consciousness-history-changes')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'consciousness_field_history'
        },
        (payload) => {
          setHistoryData(prev => [payload.new as ConsciousnessHistoryData, ...prev].slice(0, 1000));
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [fetchHistory]);

  const saveDataPoint = async (
    schumannData: SchumannData | null,
    biometricData: BiometricSnapshot | null,
    celestialBoost: number,
    totalCoherence: number
  ) => {
    try {
      if (!schumannData?.frequencyReported || !Number.isFinite(schumannData?.fundamentalHz) || !Number.isFinite(schumannData?.amplitude)) return;
      const { error } = await supabase
        .from('consciousness_field_history')
        .insert({
          schumann_frequency: schumannData.fundamentalHz,
          schumann_amplitude: schumannData.amplitude,
          schumann_quality: schumannData.quality,
          schumann_coherence_boost: schumannData.coherenceBoost,
          schumann_phase: schumannData.resonancePhase,
          hrv: biometricData?.hrv || null,
          heart_rate: biometricData?.heartRate || null,
          alpha_waves: biometricData?.alpha || null,
          theta_waves: biometricData?.theta || null,
          delta_waves: biometricData?.delta || null,
          beta_waves: biometricData?.beta || null,
          biometric_coherence_index: biometricData?.coherenceIndex || null,
          celestial_boost: celestialBoost,
          total_coherence: totalCoherence
        });

      if (error) {
        console.error('Error saving consciousness data:', error);
      }
    } catch (error) {
      console.error('Error in saveDataPoint:', error);
    }
  };

  return { historyData, isLoading, saveDataPoint };
}
