import { CircleDashed, ServerCog, UserRound } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { useIdentity } from '@/hooks/useIdentity';
import { operatingContextView } from '@/lib/operatingContext';

export function OperatingContextBanner() {
  const identityReceipt = useIdentity();
  const context = operatingContextView(identityReceipt.identity, identityReceipt.known);
  const Icon = context.kind === 'owner' ? ServerCog : context.kind === 'tenant' ? UserRound : CircleDashed;
  const tone = context.kind === 'owner'
    ? 'border-amber-400/35 bg-amber-400/[0.07]'
    : context.kind === 'tenant'
      ? 'border-cyan-400/30 bg-cyan-400/[0.06]'
      : 'border-border/60 bg-muted/20';

  return (
    <section
      data-testid="operating-context"
      data-operating-context={context.kind}
      className={`border-b px-4 py-2.5 ${tone}`}
      aria-label="Current operating context"
    >
      <div className="mx-auto flex max-w-[1600px] flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-2.5">
          <Icon className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">{context.eyebrow}</p>
            <p className="text-sm font-medium text-foreground">{context.title}</p>
            <p className="text-xs leading-relaxed text-muted-foreground">{context.description}</p>
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-start gap-1 sm:items-end">
          <Badge variant="outline" className="text-[10px]">{context.badge}</Badge>
          <p className="max-w-xl text-[10px] leading-relaxed text-muted-foreground sm:text-right">{context.boundary}</p>
        </div>
      </div>
    </section>
  );
}
