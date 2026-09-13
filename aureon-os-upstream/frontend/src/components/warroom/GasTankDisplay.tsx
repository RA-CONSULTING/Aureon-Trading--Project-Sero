import { Card, CardContent } from '@/components/ui/card';
import { useGasTank } from '@/hooks/useGasTank';
import { gasTankMoney, gasTankReceiptIsCurrent } from '@/lib/gasTankDisplay';

interface GasTankDisplayProps {
  userId: string | null;
  onEmpty?: () => void;
}

export const GasTankDisplay = ({ userId }: GasTankDisplayProps) => {
  const gasTank = useGasTank(userId);
  const observed = gasTankReceiptIsCurrent(gasTank.receipt.observed, gasTank.receipt.receivedAt);

  // Calculate percentage for fuel gauge
  const percentage = gasTank.initialBalance > 0 
    ? Math.max(0, Math.min(100, (gasTank.balance / gasTank.initialBalance) * 100))
    : 0;

  // Determine gauge color
  const getGaugeColor = () => {
    if (gasTank.status === 'EMPTY') return 'from-gray-600 to-gray-800';
    if (gasTank.status === 'CRITICAL') return 'from-destructive to-destructive';
    if (gasTank.status === 'LOW') return 'from-warning to-warning';
    return 'from-success to-success';
  };

  // Determine status emoji
  const getStatusEmoji = () => {
    if (gasTank.status === 'EMPTY') return '';
    if (gasTank.status === 'CRITICAL') return '';
    if (gasTank.status === 'LOW') return '';
    return '';
  };

  if (gasTank.isLoading) {
    return (
      <Card className="bg-card/50 backdrop-blur border-primary/20">
        <CardContent className="p-4">
          <div className="flex items-center justify-center">
            <p className="text-sm text-muted-foreground">Loading gas tank...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
      <Card className={`bg-card/50 backdrop-blur border-primary/20 relative ${
        gasTank.status === 'LOW' || gasTank.status === 'CRITICAL' ? 'animate-pulse' : ''
      }`}>
        <CardContent className="p-4">
          <div className="space-y-3">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xl"></span>
                <h3 className="font-bold text-sm">GAS TANK</h3>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono bg-primary/10 px-2 py-1 rounded">
                  {observed ? gasTank.membershipType.toUpperCase() : 'Unavailable'} {observed ? `${(gasTank.feeRate * 100).toFixed(0)}%` : ''}
                </span>
              </div>
            </div>

            {/* Fuel Gauge */}
            <div className="space-y-1">
              <div className="h-8 bg-muted/30 rounded-lg overflow-hidden relative">
                <div
                  className={`h-full bg-gradient-to-r ${getGaugeColor()} transition-all duration-500`}
                  style={{ width: `${percentage}%` }}
                />
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-xs font-bold text-white drop-shadow-lg">
                    {observed ? `${percentage.toFixed(0)}%` : 'N/A'}
                  </span>
                </div>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">
                  {gasTankMoney(gasTank.balance, observed)} / {gasTankMoney(gasTank.initialBalance, observed)}
                </span>
              </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <p className="text-muted-foreground">High-Water Mark</p>
                <p className="font-bold">{gasTankMoney(gasTank.highWaterMark, observed)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Today's Fees</p>
                <p className="font-bold text-destructive">{gasTankMoney(gasTank.feesPaidToday, observed)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Total Fees Paid</p>
                <p className="font-bold text-destructive">{gasTankMoney(gasTank.totalFeesPaid, observed)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Status</p>
                <p className="font-bold">
                  {getStatusEmoji()} {observed ? gasTank.status : 'Unavailable'}
                </p>
              </div>
            </div>
            {!observed && (
              <p className="text-xs text-muted-foreground">{gasTank.receipt.reason}</p>
            )}

            <p className="rounded border border-warning/30 bg-warning/5 p-2 text-xs text-muted-foreground">
              Provider-verified top-ups are not commissioned in this build. This panel is a read-only account-ledger observation.
            </p>

            {/* Empty Overlay */}
            {observed && gasTank.status === 'EMPTY' && (
              <div className="absolute inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center rounded-lg">
                <div className="text-center p-4">
                  <p className="text-2xl mb-2"></p>
                  <p className="font-bold text-destructive mb-2">GAS TANK EMPTY</p>
                  <p className="text-xs text-muted-foreground mb-3">Trading paused. Provider-verified funding is unavailable.</p>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
  );
};
