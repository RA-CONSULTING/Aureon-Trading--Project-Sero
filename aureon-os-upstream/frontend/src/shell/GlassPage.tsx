import React, { type ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

/** Presentation only: headings never imply that a source or operation is live. */
export function GlassPageHeader({ title, description, eyebrow, icon: Icon, actions }: {
  title: string;
  description?: ReactNode;
  eyebrow?: string;
  icon?: LucideIcon;
  actions?: ReactNode;
}) {
  return <header className="aureon-glass-page-header">
    <div className="min-w-0">
      {eyebrow && <p className="aureon-glass-eyebrow">{eyebrow}</p>}
      <h1>{Icon && <Icon className="h-6 w-6 shrink-0" aria-hidden="true" />}{title}</h1>
      {description && <div className="aureon-glass-description">{description}</div>}
    </div>
    {actions && <div className="aureon-glass-page-actions">{actions}</div>}
  </header>;
}

export function GlassSection({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cn('aureon-glass-panel', className)}>{children}</section>;
}
