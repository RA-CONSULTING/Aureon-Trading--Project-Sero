import { Button } from '@/components/ui/button';
import { Flame } from 'lucide-react';
import type { ForceTradeResult } from '@/core/forceValidatedTrade';
import { GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE } from '@/lib/tradingActionAvailability';

interface IgnitionButtonProps {
  userId: string;
  tradingMode: 'paper' | 'live';
  onComplete?: (result: ForceTradeResult) => void;
  disabled?: boolean;
}

export function IgnitionButton(props: IgnitionButtonProps) {
  return (
    <div className="space-y-2" data-execution-available="false">
      <Button
        disabled
        aria-disabled="true"
        variant="destructive"
        size="lg"
        className="gap-2 font-bold"
        title={GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE}
      >
        <Flame className="h-5 w-5" />
        ORDER ACTION UNAVAILABLE
      </Button>
      <p className="max-w-md text-xs text-muted-foreground">
        {GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE} The {props.tradingMode} view remains available for analysis.
      </p>
    </div>
  );
}
