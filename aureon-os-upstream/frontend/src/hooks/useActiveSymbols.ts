import { useCallback, useMemo } from 'react';
import { useFreshBinanceTickers } from './useFreshBinanceTickers';
import { tickerOpportunityScore } from '@/lib/freshTickerEvidence';

export interface ActiveSymbol {
  symbol: string;
  baseAsset: string;
  quoteAsset: string;
  price: number;
  volume: number;
  volatility: number;
  change: number;
  opportunityScore: number;
  lastUpdate: number;
  isLive: boolean;
}

export interface UseActiveSymbolsResult {
  symbols: ActiveSymbol[];
  topSymbols: ActiveSymbol[];
  isLoading: boolean;
  lastUpdate: number | null;
  totalAvailable: number;
  error: string | null;
  refreshSymbols: () => Promise<void>;
  getSymbol: (symbol: string) => ActiveSymbol | undefined;
  getTopByVolume: (limit?: number) => ActiveSymbol[];
  getTopByVolatility: (limit?: number) => ActiveSymbol[];
}

const TOP_SYMBOLS_COUNT = 50;

export function useActiveSymbols(): UseActiveSymbolsResult {
  const { tickers, isLoading, lastUpdate, refresh, error } = useFreshBinanceTickers(TOP_SYMBOLS_COUNT);
  const symbols = useMemo<ActiveSymbol[]>(() => tickers.map(ticker => ({
    symbol: ticker.symbol, baseAsset: ticker.base, quoteAsset: ticker.quote,
    price: ticker.price, volume: ticker.volume, volatility: ticker.volatility,
    change: ticker.change, opportunityScore: tickerOpportunityScore(ticker),
    lastUpdate: ticker.sourceAt, isLive: true,
  })).sort((a, b) => b.opportunityScore - a.opportunityScore), [tickers]);
  const getSymbol = useCallback((symbol: string) => symbols.find(item => item.symbol === symbol), [symbols]);
  const getTopByVolume = useCallback((limit = 10) => [...symbols].sort((a, b) => b.volume - a.volume).slice(0, limit), [symbols]);
  const getTopByVolatility = useCallback((limit = 10) => [...symbols].sort((a, b) => b.volatility - a.volatility).slice(0, limit), [symbols]);
  return {
    symbols, topSymbols: symbols.slice(0, TOP_SYMBOLS_COUNT), isLoading, lastUpdate,
    totalAvailable: symbols.length, error, refreshSymbols: refresh,
    getSymbol, getTopByVolume, getTopByVolatility,
  };
}
