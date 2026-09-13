import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, AlertCircle, Activity } from 'lucide-react';
import { useQueenHive } from '@/hooks/useQueenHive';
import { GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE } from '@/lib/tradingActionAvailability';

export function QGITAOMSIntegrationStatus() {
  const { session } = useQueenHive();

  return (
    <Card className="border-border/50 bg-card/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Activity className="h-4 w-4 text-muted-foreground" />
          QGITA → OMS Integration
        </CardTitle>
        <CardDescription className="text-xs">
          High-coherence signal observation; order routing unavailable
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-2">
          {/* Auto-Trading Status */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">Auto-Trading</span>
            <Badge variant="outline" className="gap-1">
              <AlertCircle className="h-3 w-3" />
              Unavailable
            </Badge>
          </div>

          {/* Hive Session Status */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">Queen-Hive Session</span>
            <Badge variant={session?.status === 'running' ? 'default' : 'outline'} className="gap-1">
              {session?.status === 'running' ? (
                <>
                  <CheckCircle2 className="h-3 w-3" />
                  Active
                </>
              ) : (
                <>
                  <AlertCircle className="h-3 w-3" />
                  Inactive
                </>
              )}
            </Badge>
          </div>

          {/* Integration Status */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">OMS Routing</span>
            <Badge variant="secondary" className="gap-1">
              <AlertCircle className="h-3 w-3" />
              Unavailable
            </Badge>
          </div>
        </div>

        {/* Info Box */}
        <div className="mt-3 p-2 rounded bg-warning/10 border border-warning/20">
          <p className="text-xs text-warning">{GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE}</p>
        </div>

        {/* Priority Mapping */}
        <div className="mt-3 pt-3 border-t border-border/50">
          <p className="text-xs font-semibold text-foreground mb-2">Priority Mapping</p>
          <div className="space-y-1 text-xs text-muted-foreground">
            <div className="flex justify-between">
              <span>Tier 1 (80-100%)</span>
              <span className="font-mono text-success">P80-100</span>
            </div>
            <div className="flex justify-between">
              <span>Tier 2 (60-79%)</span>
              <span className="font-mono text-warning">P60-79</span>
            </div>
            <div className="flex justify-between">
              <span>Tier 3 (&lt;60%)</span>
              <span className="font-mono text-muted-foreground">P40-59</span>
            </div>
            <div className="flex justify-between">
              <span>FTCP Bonus</span>
              <span className="font-mono text-primary">+10</span>
            </div>
            <div className="flex justify-between">
              <span>High Coherence</span>
              <span className="font-mono text-primary">+5</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
