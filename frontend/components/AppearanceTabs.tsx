"use client";

import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";
import { useAppearance, type Appearance } from "@/hooks/use-appearance";
import { cn } from "@/lib/utils";

const TABS: { value: Appearance; icon: LucideIcon; label: string }[] = [
  { value: "light", icon: Sun, label: "Light" },
  { value: "dark", icon: Moon, label: "Dark" },
  { value: "system", icon: Monitor, label: "System" },
];

export function AppearanceTabs({ className }: { className?: string }) {
  const { appearance, updateAppearance } = useAppearance();
  return (
    <div role="radiogroup" aria-label="Appearance" className={cn("inline-flex gap-1 rounded-lg bg-neutral-100 p-1 dark:bg-neutral-800", className)}>
      {TABS.map(({ value, icon: Icon, label }) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={appearance === value}
          onClick={() => updateAppearance(value)}
          className={cn(
            "flex items-center rounded-md px-3.5 py-1.5 text-sm transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
            appearance === value
              ? "bg-white shadow-xs dark:bg-neutral-700 dark:text-neutral-100"
              : "text-neutral-500 hover:bg-neutral-200/60 hover:text-black dark:text-neutral-400 dark:hover:bg-neutral-700/60 dark:hover:text-white",
          )}
        >
          <Icon className="-ml-1 size-4" aria-hidden />
          <span className="ml-1.5">{label}</span>
        </button>
      ))}
    </div>
  );
}
