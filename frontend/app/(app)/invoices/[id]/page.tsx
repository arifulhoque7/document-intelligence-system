"use client";

import { Check, FileText, RotateCcw, Save } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Alert } from "@/components/Alert";
import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { Empty } from "@/components/Empty";
import { ErrorState } from "@/components/ErrorState";
import { DiffList } from "@/components/invoices/DiffList";
import { HistoryPanel } from "@/components/invoices/HistoryPanel";
import { InvoiceFields } from "@/components/invoices/InvoiceFields";
import { IssuesPanel } from "@/components/invoices/IssuesPanel";
import { LineItemsEditor } from "@/components/invoices/LineItemsEditor";
import { PageHeader } from "@/components/PageHeader";
import { PageSkeleton } from "@/components/Spinner";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/useApi";
import { usePageCrumb } from "@/hooks/useSession";
import { api, ApiError, errorMessage, fieldErrors, json } from "@/lib/api";
import { buildPatch, toForm, toRows, type FormValues, type LineRow } from "@/lib/invoiceForm";
import type { CorrectionResult, FieldDiff, InvoiceDetail, Revision } from "@/lib/types";

type Notice = { tone: "success" | "error" | "info"; title: string; text?: string; diff?: FieldDiff };

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const inv = useApi<InvoiceDetail>(`/api/invoices/${id}`);
  const history = useApi<Revision[]>(`/api/invoices/${id}/history`);
  const [values, setValues] = useState<FormValues | null>(null);
  const [rows, setRows] = useState<LineRow[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState<Notice | null>(null);
  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState(false);

  const invoice = inv.data;
  usePageCrumb(invoice ? invoice.invoice_number ?? "Invoice without a number" : null);
  // Reset the form whenever a fresh copy of the invoice arrives (first load, save, approve).
  useEffect(() => {
    if (!invoice) return;
    setValues(toForm(invoice));
    setRows(toRows(invoice.line_items));
  }, [invoice]);

  if (inv.error) return <ErrorState error={inv.error} onRetry={inv.reload} />;
  if (!invoice || !values) return <PageSkeleton label="Loading invoice" />;

  const patch = buildPatch(invoice, values, rows);
  const dirty = Object.keys(patch).length > 0;
  const lineIssues = invoice.issues.some((i) => i.field === "line_items");

  function reset() {
    if (!invoice) return;
    setValues(toForm(invoice));
    setRows(toRows(invoice.line_items));
    setErrors({});
  }

  async function save() {
    setSaving(true);
    setErrors({});
    setNotice(null);
    try {
      const res = await api<CorrectionResult>(`/api/invoices/${id}`, { method: "PATCH", body: json(patch) });
      const changed = Object.keys(res.changed).length;
      setNotice(changed ? { tone: "success", title: "Changes saved", diff: res.changed } : { tone: "info", title: "Nothing changed", text: "The saved values were already the same." });
      if (changed) toast.success(`Saved ${changed} change(s)`);
      inv.setData(res.invoice);
      void history.reload();
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) setErrors(fieldErrors(e));
      setNotice({ tone: "error", title: "Could not save", text: errorMessage(e) });
    } finally {
      setSaving(false);
    }
  }

  async function approveInvoice() {
    setApproving(true);
    setNotice(null);
    try {
      await api(`/api/invoices/${id}/approve`, { method: "POST" });
      await Promise.all([inv.reload(), history.reload()]);
      toast.success("Invoice approved");
    } catch (e) {
      toast.error(`Could not approve: ${errorMessage(e)}`);
    } finally {
      setApproving(false);
    }
  }

  return (
    <>
      <PageHeader
        title={invoice.invoice_number ? <span className="font-mono">{invoice.invoice_number}</span> : "Invoice without a number"}
        description={
          <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
            <StatusBadge status={invoice.status} />
            {invoice.needs_review && invoice.status !== "needs_review" && <Badge tone="indigo">Needs review</Badge>}
            <Link href={`/documents/${invoice.document_id}`} className="hover:text-primary hover:underline">{invoice.filename ?? "Source document"}</Link>
            {invoice.source_ref && <span className="font-mono text-xs">{invoice.source_ref}</span>}
            {invoice.extracted_by && <span className="font-mono text-xs">{invoice.extracted_by}</span>}
          </span>
        }
        actions={
          <>
            <Button variant="ghost" onClick={reset} disabled={!dirty || saving}>
              <RotateCcw aria-hidden /> Discard
            </Button>
            <Button variant="outline" onClick={save} loading={saving} disabled={!dirty}>
              {!saving && <Save aria-hidden />} Save changes
            </Button>
            <Button onClick={approveInvoice} loading={approving} disabled={dirty || invoice.status === "approved"} title={dirty ? "Save or discard your changes first" : undefined}>
              {!approving && <Check aria-hidden />} {invoice.status === "approved" ? "Approved" : "Approve"}
            </Button>
          </>
        }
      />

      {notice && (
        <div className="mb-4">
          <Alert tone={notice.tone} title={notice.title}>
            {notice.text}
            {notice.diff && <div className="mt-2"><DiffList diff={notice.diff} /></div>}
          </Alert>
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <Card title="Extracted fields" caption="Confidence per field, edits are marked certain" actions={dirty && <Badge tone="sky"><span className="font-mono">{Object.keys(patch).length}</span> unsaved</Badge>}>
            <InvoiceFields
              invoice={invoice}
              values={values}
              issues={invoice.issues}
              errors={errors}
              disabled={saving}
              onChange={(k, v) => setValues({ ...values, [k]: v })}
            />
          </Card>
          <Card flush title="Line items" caption={`${rows.length} row(s)`}>
            {errors.line_items && <p className="px-4 pt-3 text-xs text-destructive-foreground">{errors.line_items}</p>}
            <LineItemsEditor rows={rows} onChange={setRows} disabled={saving} highlight={lineIssues} />
          </Card>
          <Card title="Source text" caption={invoice.source_ref ?? undefined} actions={<FileText className="size-4 text-muted-foreground" aria-hidden />}>
            {invoice.source_text ? (
              <pre className="max-h-96 overflow-auto rounded-md bg-muted/50 p-3 font-mono text-xs leading-relaxed break-words whitespace-pre-wrap">{invoice.source_text}</pre>
            ) : (
              <Empty text="No source text stored for this invoice" />
            )}
          </Card>
        </div>
        <div className="space-y-4">
          <Card title="Validation" caption={`${invoice.issues.length} issue(s)`}>
            <IssuesPanel issues={invoice.issues} />
          </Card>
          <Card title="Revision history">
            <HistoryPanel revisions={history.data} error={history.error} onRetry={history.reload} />
          </Card>
        </div>
      </div>
    </>
  );
}
