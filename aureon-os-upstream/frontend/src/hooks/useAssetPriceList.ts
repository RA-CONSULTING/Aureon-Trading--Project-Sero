import { useCallback, useMemo } from 'react';
import { useFreshBinanceTickers } from './useFreshBinanceTickers';

export interface AssetPrice {
  symbol: string;
  base: string;
  quote: string;
  price: number;
  volume: number;
  change: number;
  volatility: number;
  exchange: 'binance' | 'kraken' | 'alpaca' | 'capital';
  dataSource: 'LIVE' | 'CACHED' | 'STALE' | 'NO_DATA';
  lastUpdate: number;
  priceVariance?: number;
}

export interface AssetPriceListStats {
  totalAssets: number;
  liveAssets: number;
  cachedAssets: number;
  staleAssets: number;
  noDataAssets: number;
  avgVolatility: number | null;
  topGainer: AssetPrice | null;
  topLoser: AssetPrice | null;
  topVolume: AssetPrice | null;
  dataFreshness: number | null;
}

export interface UseAssetPriceListResult {
  assets: AssetPrice[];
  stats: AssetPriceListStats;
  isLoading: boolean;
  lastRefresh: Date | null;
  error: string | null;
  refresh: () => Promise<void>;
  getAsset: (symbol: string) => AssetPrice | undefined;
  searchAssets: (query: string) => AssetPrice[];
  sortAssets: (by: 'symbol' | 'price' | 'change' | 'volume' | 'volatility') => AssetPrice[];
}

export const useAssetPriceList = (): UseAssetPriceListResult => {
  const { tickers, isLoading, lastUpdate, refresh, error } = useFreshBinanceTickers(200);
  const assets = useMemo<AssetPrice[]>(() => tickers.map(ticker => ({
    symbol: ticker.symbol, base: ticker.base, quote: ticker.quote,
    price: ticker.price, volume: ticker.volume, change: ticker.change,
    // The provider's range/price value is a ratio; this panel displays percent.
    volatility: ticker.volatility * 100,
    exchange: 'binance', dataSource: 'LIVE', lastUpdate: ticker.sourceAt,
  })), [tickers]);
  const stats = useMemo<AssetPriceListStats>(() => {
    const sortedByChange = [...assets].sort((a, b) => b.change - a.change);
    return {
      totalAssets: assets.length, liveAssets: assets.length,
      cachedAssets: 0, staleAssets: 0, noDataAssets: 0,
      avgVolatility: assets.length ? assets.reduce((sum, asset) => sum + asset.volatility, 0) / assets.length : null,
      topGainer: sortedByChange.find(asset => asset.change > 0) ?? null,
      topLoser: [...sortedByChange].reverse().find(asset => asset.change < 0) ?? null,
      topVolume: assets[0] ?? null,
      dataFreshness: assets.length ? 100 : null,
    };
  }, [assets]);
  const getAsset = useCallback((symbol: string) => assets.find(asset => asset.symbol.toLowerCase() === symbol.toLowerCase()), [assets]);
  const searchAssets = useCallback((query: string) => {
    const text = query.toLowerCase();
    return assets.filter(asset => [asset.symbol, asset.base, asset.quote].some(value => value.toLowerCase().includes(text)));
  }, [assets]);
  const sortAssets = useCallback((by: 'symbol' | 'price' | 'change' | 'volume' | 'volatility') =>
    [...assets].sort((a, b) => by === 'symbol' ? a.symbol.localeCompare(b.symbol) : b[by] - a[by]), [assets]);
  return {
    assets, stats, isLoading, lastRefresh: lastUpdate === null ? null : new Date(lastUpdate),
    error, refresh, getAsset, searchAssets, sortAssets,
  };
};
