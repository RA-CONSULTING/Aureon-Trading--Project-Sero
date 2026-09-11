import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp } from 'lucide-react';

interface Balance {
  asset: string;
  free: number;
  price: number;
  usdtValue: number;
}

interface QuickTradeProps {
  balances: Balance[];
  canTrade: boolean;
}

export const QuickTrade = (_props: QuickTradeProps) => {
  return (
    <Card className="bg-card/50 backdrop-blur border-border/50">
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-muted-foreground" />
          Quick Trade
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Manual order execution is disabled by the current safety posture. The runtime reports real orders, exchange mutations, and order-intent publishing as held.
        </p>
      </CardContent>
    </Card>
  );
};
