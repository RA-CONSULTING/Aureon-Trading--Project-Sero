import React from 'react';
import { Card, CardContent } from './ui/card';
import { AlertTriangle } from 'lucide-react';
import { useTerminalState } from '@/hooks/useTerminalState';
import { readWarRoomEvidence } from '@/lib/warRoomEvidence';

export const AnalysisModePanel: React.FC<{ tool: string }> = ({ tool }) => {
  const { state, isFresh } = useTerminalState();
  const evidence = readWarRoomEvidence(state, isFresh);

  return (
    <Card className="border-border/50">
      <CardContent className="p-6">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-warning mt-0.5" />
          <div className="space-y-1">
            <p className="font-medium">Analysis Mode Panel — Legacy / Unavailable</p>
            <p className="text-sm text-muted-foreground">
              {evidence.available
                ? 'This panel has no runtime-backed source for phase dynamics, memory tracer, or stability outputs. Synthetic rendering is disabled.'
                : evidence.reason}
            </p>
            {tool && tool !== 'select' && (
              <p className="text-xs text-muted-foreground">Requested tool: {tool}</p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
