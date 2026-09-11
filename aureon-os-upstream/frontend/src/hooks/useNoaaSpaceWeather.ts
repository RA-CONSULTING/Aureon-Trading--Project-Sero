import { useEffect, useState } from 'react';
import { NOAA_FEED_IDS, NOAA_REFRESH_MS, emptyNoaaReceipt, type NoaaFeed, type NoaaReceipt } from '@/lib/noaaObservationEvidence';
import { fetchNoaaFeed } from '@/lib/noaaPublicSource';

const initial = (): Record<NoaaFeed, NoaaReceipt> => Object.fromEntries(
  NOAA_FEED_IDS.map(feed => [feed, emptyNoaaReceipt(feed, true, 'Loading NOAA public source')]),
) as Record<NoaaFeed, NoaaReceipt>;

/** Four independent public observations. Transport never replaces a provider time_tag. */
export function useNoaaSpaceWeather(refreshMs = NOAA_REFRESH_MS) {
  const [feeds, setFeeds] = useState(initial);
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    let cancelled = false;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    const poll = async () => {
      await Promise.all(NOAA_FEED_IDS.map(async feed => {
        const receipt = await fetchNoaaFeed(feed, controller.signal);
        if (!cancelled) setFeeds(current => ({ ...current, [feed]: receipt }));
      }));
      if (!cancelled) pollTimer = setTimeout(() => void poll(), Math.max(NOAA_REFRESH_MS, refreshMs));
    };
    void poll();
    const ageTimer = setInterval(() => setNow(Date.now()), 5_000);
    return () => {
      cancelled = true;
      controller.abort();
      clearTimeout(pollTimer);
      clearInterval(ageTimer);
    };
  }, [refreshMs]);
  return { feeds, now, isLoading: NOAA_FEED_IDS.some(feed => feeds[feed].status === 'loading') };
}
