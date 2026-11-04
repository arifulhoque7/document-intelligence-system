"use client";

import { useState, type ReactNode } from "react";
import { ErrorState } from "@/components/ErrorState";
import { Spinner } from "@/components/Spinner";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useApi } from "@/hooks/useApi";
import { usePoll } from "@/hooks/usePoll";
import { CrumbContext, SessionContext } from "@/hooks/useSession";
import type { Stats, User } from "@/lib/types";
import { AppHeader } from "./AppHeader";
import { AppSidebar } from "./AppSidebar";

export function AppShell({ children }: { children: ReactNode }) {
  const { data: user, error, reload } = useApi<User>("/api/auth/me");
  const stats = useApi<Stats>(user ? "/api/stats" : null);
  const [crumb, setCrumb] = useState<string | null>(null);
  // Keeps the review count in the sidebar fresh without a page reload.
  usePoll(stats.reload, !!user, 15000);

  if (error) {
    return (
      <div className="mx-auto max-w-lg p-8">
        <ErrorState error={error} onRetry={reload} />
      </div>
    );
  }
  if (!user) {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <Spinner label="Loading session" />
      </div>
    );
  }

  return (
    <SessionContext.Provider value={user}>
      <CrumbContext.Provider value={setCrumb}>
        <TooltipProvider delayDuration={0}>
          <SidebarProvider>
            <AppSidebar user={user} reviewCount={stats.data?.invoices_needing_review ?? 0} />
            <SidebarInset>
              <AppHeader detail={crumb} />
              <div className="p-4">{children}</div>
            </SidebarInset>
          </SidebarProvider>
        </TooltipProvider>
      </CrumbContext.Provider>
    </SessionContext.Provider>
  );
}
