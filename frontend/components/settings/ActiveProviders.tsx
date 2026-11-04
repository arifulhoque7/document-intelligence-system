"use client";

import { useState } from "react";
import { Alert } from "@/components/Alert";
import { toast } from "sonner";
import { Card } from "@/components/Card";
import { Field, SimpleSelect } from "@/components/Field";
import { Button } from "@/components/ui/button";
import { api, errorMessage, json } from "@/lib/api";
import type { ProviderSettings } from "@/lib/types";

const NAMES: Record<string, string> = { claude: "Anthropic Claude", openai: "OpenAI", gemini: "Google Gemini", ollama: "Ollama" };

export function ActiveProviders({ providers, isAdmin, onSaved }: { providers: ProviderSettings[]; isAdmin: boolean; onSaved: (p: ProviderSettings[]) => void }) {
  const currentLlm = providers.find((p) => p.active_llm)?.provider ?? "";
  const currentEmb = providers.find((p) => p.active_embedding)?.provider ?? "";
  const [llm, setLlm] = useState(currentLlm);
  const [embedding, setEmbedding] = useState(currentEmb);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      const body: Record<string, string> = {};
      if (llm && llm !== currentLlm) body.llm = llm;
      if (embedding && embedding !== currentEmb) body.embedding = embedding;
      onSaved(await api<ProviderSettings[]>("/api/settings/active", { method: "PUT", body: json(body) }));
      toast.success(body.embedding ? "Saved. All invoices are being re-embedded in the background." : "Active provider saved");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const changed = (llm && llm !== currentLlm) || (embedding && embedding !== currentEmb);

  return (
    <Card title="Active providers" caption="Used for new extractions and searches">
      <div className="space-y-4">
        <Alert tone="info">
          The LLM provider extracts invoice fields from PDFs and images. Embeddings power semantic search. Claude has no embeddings API, so
          embeddings need OpenAI, Gemini or Ollama. Changing the embedding provider re-embeds every invoice, because vectors from different
          models cannot be compared.
        </Alert>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="LLM provider (extraction)" htmlFor="active-llm">
            <SimpleSelect id="active-llm" value={llm} onChange={setLlm} disabled={!isAdmin} placeholder="None selected" options={providers.map((p) => ({ value: p.provider, label: `${NAMES[p.provider]}${p.needs_key && !p.has_key ? " (no key)" : ""}` }))} />
          </Field>
          <Field label="Embedding provider (semantic search)" htmlFor="active-emb">
            <SimpleSelect id="active-emb" value={embedding} onChange={setEmbedding} disabled={!isAdmin} placeholder="None selected" options={providers.filter((p) => p.supports_embeddings).map((p) => ({ value: p.provider, label: `${NAMES[p.provider]}${p.needs_key && !p.has_key ? " (no key)" : ""}` }))} />
          </Field>
        </div>
        {isAdmin && (
          <Button onClick={save} loading={busy} disabled={!changed}>Save active providers</Button>
        )}
      </div>
    </Card>
  );
}
