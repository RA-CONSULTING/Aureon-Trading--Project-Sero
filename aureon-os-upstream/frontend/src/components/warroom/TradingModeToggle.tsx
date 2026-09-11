import { Badge } from '@/components/ui/badge';
import { AlertTriangle } from 'lucide-react';
import { useTerminalState } from '@/hooks/useTerminalState';
import { readWarRoomEvidence } from '@/lib/warRoomEvidence';

interface TradingModeToggleProps {
  userId?: string | null;
}

export function TradingModeToggle({ userId }: TradingModeToggleProps) {
  const { state, isFresh } = useTerminalState();
  const evidence = readWarRoomEvidence(state, isFresh);

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-card/50 border border-border/50">
      <span className="text-sm font-medium">Trading Mode</span>
      <Badge variant="outline" className="flex items-center gap-1 text-muted-foreground">
        <AlertTriangle className="h-3 w-3" />
        Legacy / Disabled
      </Badge>
      {userId && (
        <span className="text-xs text-muted-foreground">
          {evidence.available
            ? 'No runtime-backed trading-mode control.'
            : evidence.reason}
        </span>
      )}
    </div>
  );
}
