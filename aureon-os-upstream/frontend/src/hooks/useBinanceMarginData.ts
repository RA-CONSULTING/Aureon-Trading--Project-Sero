import { useEffect, useState } from 'react';

export interface MarginSentiment {
  crossMargin: {
    marginLevel: number;
    totalAssetOfBtc: number;
    totalLiabilityOfBtc: number;
    totalNetAssetOfBtc: number;
    riskLevel: string;
  };
  isolatedMargin: any | null;
  collateralRatio: any[];
  interestRate: any | null;
  recentLiquidations: {
    count: number;
    totalVolume: number;
    avgPrice: number;
  };
  sentiment: {
    leverageRisk: number; // 0-1, higher = more risk
    liquidationPressure: number; // 0-1, higher = more pressure
    borrowingCost: number;
    marketHealth: number; // 0-1, higher = healthier
  };
}

export const useBinanceMarginData = (symbol: string = 'BTC', refreshInterval: number = 30000) => {
  const [marginData, setMarginData] = useState<MarginSentiment | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchMarginData = async () => {
    setIsLoading(true);
    setError(null);

    setMarginData(null);
    setError(`Margin telemetry for ${symbol} is unavailable until the tenant-scoped provider route is commissioned.`);
    setIsLoading(false);
  };

  useEffect(() => {
    fetchMarginData();

    if (refreshInterval > 0) {
      const interval = setInterval(fetchMarginData, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [symbol, refreshInterval]);

  return {
    marginData,
    isLoading,
    error,
    refetch: fetchMarginData,
  };
};
