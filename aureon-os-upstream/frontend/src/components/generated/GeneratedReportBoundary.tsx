import React, { useEffect, useState, type ReactNode } from 'react';
import { reportBoundaryEvidence } from '@/lib/recordedReportEvidence';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function GeneratedReportBoundary({ report, source, children, scope = 'current' }: { report: unknown; source: string; children: ReactNode; scope?: 'current' | 'recorded' }) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(timer);
  }, []);
  const evidence = reportBoundaryEvidence(report, scope, now);
  if (!evidence.current) return <Card>
    <CardHeader><CardTitle className="text-base">Report unavailable</CardTitle></CardHeader>
    <CardContent className="space-y-2 text-sm text-muted-foreground">
      <p>{evidence.reason}</p>
      {evidence.timestamp && <p>Report timestamp: {evidence.timestamp}</p>}
      <a href={source} target="_blank" rel="noreferrer" className="underline">View original report</a>
    </CardContent>
  </Card>;
  return <div className="space-y-2"><p className="text-xs text-muted-foreground">{evidence.reason} Source: {source} · {evidence.timestamp}</p>{children}</div>;
}
