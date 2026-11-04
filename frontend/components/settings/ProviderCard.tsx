"use client";

import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { Empty } from "@/components/Empty";
import { Field } from "@/components/Field";
import { PasswordInput } from "@/components/PasswordInput";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errorMessage, json } from "@/lib/api";
import type { ProviderSettings, ProviderTestResult } from "@/lib/types";

const NAMES: Record<string, string> = { claude: "Anthropic Claude", openai: "OpenAI", gemini: "Google Gemini", ollama: "Ollama (local)" };

export function ProviderCard({ p, isAdmin, onSaved }: { p: ProviderSettings; isAdmin: boolean; onSaved: (p: ProviderSettings) => void }) {
  // The real key never reaches the browser: the input starts empty and blank means "keep".
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState(p.model ?? "");
  const [embeddingModel, setEmbeddingModel] = useState(p.embedding_model ?? "");
  const [baseUrl, setBaseUrl] = useState(p.base_url ?? "");
  const [busy, setBusy] = useState<"save" | "remove" | "test" | null>(null);
  const [test, setTest] = useState<ProviderTestResult | null>(null);
  const id = (f: string) => `${p.provider}-${f}`;

  async function put(body: Record<string, string>, kind: "save" | "remove") {
    setBusy(kind);
    try {
      const saved = await api<ProviderSettings>(`/api/settings/providers/${p.provider}`, { method: "PUT", body: json(body) });
      setApiKey("");
      onSaved(saved);
      toast.success(kind === "remove" ? `${NAMES[p.provider]} key removed` : `${NAMES[p.provider]} settings saved`);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  function save(e: FormEvent) {
    e.preventDefault();
    const body: Record<string, string> = { model };
    if (apiKey.trim()) body.api_key = apiKey.trim();
    if (p.supports_embeddings) body.embedding_model = embeddingModel;
    if (p.provider === "ollama") body.base_url = baseUrl;
    void put(body, "save");
  }

  async function runTest() {
    setBusy("test");
    setTest(null);
    try {
      setTest(await api<ProviderTestResult>(`/api/settings/providers/${p.provider}/test`, { method: "POST" }));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card
      title={NAMES[p.provider] ?? p.provider}
      actions={
        <span className="flex flex-wrap gap-1">
          {p.active_llm && <Badge tone="indigo">Active LLM</Badge>}
          {p.active_embedding && <Badge tone="sky">Active embeddings</Badge>}
          {!p.supports_embeddings && <Badge tone="neutral">No embeddings</Badge>}
        </span>
      }
    >
      <form onSubmit={save} className="space-y-4">
        {p.needs_key && (
          <div>
            <p className="mb-3 text-sm text-muted-foreground">
              Stored key: {p.api_key_masked ? <code className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">{p.api_key_masked}</code> : <Empty text="none" />}
            </p>
            <Field label="New API key" htmlFor={id("key")} hint="Leave blank to keep the stored key.">
              <PasswordInput id={id("key")} autoComplete="new-password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} disabled={!isAdmin} placeholder={p.has_key ? "Enter a key to replace it" : "Paste an API key"} />
            </Field>
          </div>
        )}
        <Field label="Model" htmlFor={id("model")}>
          <Input className="font-mono" id={id("model")} value={model} onChange={(e) => setModel(e.target.value)} disabled={!isAdmin} />
        </Field>
        {p.supports_embeddings && (
          <Field label="Embedding model" htmlFor={id("emb")} hint={p.active_embedding ? "Changing it re-embeds every invoice." : undefined}>
            <Input className="font-mono" id={id("emb")} value={embeddingModel} onChange={(e) => setEmbeddingModel(e.target.value)} disabled={!isAdmin} />
          </Field>
        )}
        {p.provider === "ollama" && (
          <Field label="Base URL" htmlFor={id("url")}>
            <Input className="font-mono" id={id("url")} type="url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} disabled={!isAdmin} placeholder="http://localhost:11434" />
          </Field>
        )}

        {test && (
          <div aria-live="polite" className="space-y-1 rounded-md border border-border bg-muted/30 p-3 text-sm">
            {test.llm && <TestLine label="Extraction" ok={test.llm.ok} text={test.llm.ok ? `ok, ${test.llm.invoices} invoice(s) found` : test.llm.error} />}
            {test.embedding && <TestLine label="Embeddings" ok={test.embedding.ok} text={test.embedding.ok ? `ok, ${test.embedding.dims} dimensions` : test.embedding.error} />}
          </div>
        )}

        {isAdmin && (
          <div className="flex flex-wrap gap-2 pt-1">
            <Button type="submit" loading={busy === "save"} disabled={!!busy}>Save</Button>
            <Button variant="outline" onClick={runTest} loading={busy === "test"} disabled={!!busy}>Test connection</Button>
            {p.needs_key && p.has_key && (
              <Button variant="ghost" className="text-rose-700 hover:text-rose-800 dark:text-rose-400" onClick={() => put({ api_key: "" }, "remove")} loading={busy === "remove"} disabled={!!busy}>Remove key</Button>
            )}
          </div>
        )}
      </form>
    </Card>
  );
}

function TestLine({ label, ok, text }: { label: string; ok: boolean; text: string }) {
  return (
    <p className="flex flex-wrap items-start gap-2">
      <span className="font-medium">{label}:</span>
      <span className={`break-words ${ok ? "text-emerald-700 dark:text-emerald-400" : "text-rose-700 dark:text-rose-400"}`}>{text}</span>
    </p>
  );
}
