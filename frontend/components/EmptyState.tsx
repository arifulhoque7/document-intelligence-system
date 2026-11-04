import { Inbox, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function EmptyState({ title, description, icon: Icon = Inbox, action, compact = false }: { title: string; description?: ReactNode; icon?: LucideIcon; action?: ReactNode; compact?: boolean }) {
  if (compact) return <p className="px-4 py-8 text-center text-sm text-muted-foreground">{title}</p>;
  return (
    <div className="flex flex-col items-center px-6 py-16 text-center">
      <span className="inline-flex size-16 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Icon size={28} aria-hidden />
      </span>
      <h2 className="mt-8 text-2xl leading-8 font-bold text-foreground">{title}</h2>
      {description && <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
