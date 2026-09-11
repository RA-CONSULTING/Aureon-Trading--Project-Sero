import { Card, CardContent } from '@/components/ui/card';
import { AlertTriangle } from 'lucide-react';
import { useTerminalState } from '@/hooks/useTerminalState';
import { readWarRoomEvidence } from '@/lib/warRoomEvidence';
import type { WarState, WarConfig } from '@/hooks/useWarRoom';

interface CommandCenterProps {
  warState: WarState;
  onLaunch: () => void;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
  onEmergencyHalt: () => void;
  onConfigUpdate: (config: Partial<WarConfig>) => void;
}

export function CommandCenter(props: CommandCenterProps) {
  const { state, isFresh } = useTerminalState();
  const evidence = readWarRoomEvidence(state, isFresh);
  void props;

  return (
    <Card className="p-6 bg-card/50 backdrop-blur border-primary/20">
      <CardContent className="p-0">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-warning mt-0.5" />
          <div className="space-y-1">
            <p className="font-medium">Command Center — Legacy / Unavailable</p>
            <p className="text-sm text-muted-foreground">
              {evidence.available
                ? 'War-room command surface has no runtime-backed source. Synthetic status controls are disabled.'
                : evidence.reason}
            </p>
            <p className="text-xs text-muted-foreground">
              Control props are accepted for compatibility but are not applied.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
