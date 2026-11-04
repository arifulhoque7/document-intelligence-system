"use client";

import { Alert } from "@/components/Alert";
import { AppearanceTabs } from "@/components/AppearanceTabs";
import { Card } from "@/components/Card";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { ActiveProviders } from "@/components/settings/ActiveProviders";
import { ProviderCard } from "@/components/settings/ProviderCard";
import { UsersCard } from "@/components/settings/UsersCard";
import { PageSkeleton } from "@/components/Spinner";
import { useApi } from "@/hooks/useApi";
import { useSession } from "@/hooks/useSession";
import type { ProviderSettings } from "@/lib/types";

export default function SettingsPage() {
  const user = useSession();
  const isAdmin = user.role === "admin";
  const { data, error, reload, setData } = useApi<ProviderSettings[]>("/api/settings/providers");

  return (
    <>
      <PageHeader title="Settings" description="AI providers for extraction and semantic search, users, and appearance." />
      <div className="space-y-4">
        {!isAdmin && <Alert tone="info">Only administrators can change provider settings. You can view the current configuration.</Alert>}
        <Card title="Appearance" caption="Saved in this browser">
          <AppearanceTabs />
        </Card>
        {error ? (
          <ErrorState error={error} onRetry={reload} />
        ) : !data ? (
          <PageSkeleton label="Loading providers" />
        ) : (
          <>
            {/* key resets the form when the active selection changes on the server */}
            <ActiveProviders key={data.map((p) => `${p.active_llm}${p.active_embedding}`).join()} providers={data} isAdmin={isAdmin} onSaved={setData} />
            <div className="grid gap-4 lg:grid-cols-2">
              {data.map((p) => (
                <ProviderCard key={p.provider} p={p} isAdmin={isAdmin} onSaved={(saved) => setData(data.map((x) => (x.provider === saved.provider ? saved : x)))} />
              ))}
            </div>
            {isAdmin && <UsersCard />}
          </>
        )}
      </div>
    </>
  );
}
