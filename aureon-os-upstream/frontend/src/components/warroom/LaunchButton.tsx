import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { AlertTriangle } from 'lucide-react';
import { useTerminalState } from '@/hooks/useTerminalState';
import { readWarRoomEvidence } from '@/lib/warRoomEvidence';

interface LaunchButtonProps {
  onLaunch: () => void;
  onStop: () => void;
  status: 'idle' | 'active' | 'emergency_stopped';
}

export function LaunchButton({ status }: LaunchButtonProps) {
  const { state, isFresh } = useTerminalState();
  const evidence = readWarRoomEvidence(state, isFresh);
  void status;

  return (
    <Card className="bg-gradient-to-r from-primary/10 to-destructive/10 border-primary/30">
      <CardContent className="p-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-4 h-4 rounded-full bg-muted" />
            <div>
              <h3 className="text-xl font-bold">Launch Control — Legacy / Unavailable</h3>
              <p className="text-sm text-muted-foreground">
                {evidence.available
                  ? 'Launch control has no runtime-backed execution path. Synthetic trading activation is disabled.'
                  : evidence.reason}
              </p>
            </div>
          </div>
          <Badge variant="outline" className="flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" />
            Disabled
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
}
