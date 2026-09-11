import { Card } from '@/components/ui/card';
import { Shield } from 'lucide-react';

interface LiveTradingTestPanelProps {
  hasCredentials?: boolean;
  userId?: string;
}

export const LiveTradingTestPanel = (_props: LiveTradingTestPanelProps) => {
  return (
    <Card className="p-6 border-muted">
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-muted-foreground" />
          <h3 className="text-lg font-semibold">Live Trading Test</h3>
        </div>
        <p className="text-sm text-muted-foreground">
          Live trading and test-trade execution are disabled by the current safety posture. The runtime reports real orders, exchange mutations, and order-intent publishing as held.
        </p>
      </div>
    </Card>
  );
};
