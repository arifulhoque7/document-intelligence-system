"use client";

import { UserPlus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Alert } from "@/components/Alert";
import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { DataTable, TBody, Td, Th, THead, Tr } from "@/components/DataTable";
import { ErrorState } from "@/components/ErrorState";
import { Field, SimpleSelect } from "@/components/Field";
import { PasswordInput } from "@/components/PasswordInput";
import { ListSkeleton } from "@/components/Spinner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useApi } from "@/hooks/useApi";
import { api, errorMessage, json } from "@/lib/api";
import type { Role, User } from "@/lib/types";

function AddUserDialog({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("reviewer");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await api<User>("/api/auth/users", { method: "POST", body: json({ email, password, role }) });
      toast.success(`Created ${u.email} as ${u.role}`);
      setEmail("");
      setPassword("");
      setOpen(false);
      onCreated();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm"><UserPlus aria-hidden /> Add user</Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={create} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>Add a user</DialogTitle>
            <DialogDescription>Reviewers can correct and approve invoices. Admins can also change providers and users.</DialogDescription>
          </DialogHeader>
          {error && <Alert tone="error">{error}</Alert>}
          <Field label="Email" htmlFor="new-email">
            <Input id="new-email" type="email" autoComplete="off" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Password" htmlFor="new-password" hint="At least 8 characters.">
            <PasswordInput id="new-password" autoComplete="new-password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <Field label="Role" htmlFor="new-role">
            <SimpleSelect id="new-role" value={role} onChange={(v) => setRole(v as Role)} options={[{ value: "reviewer", label: "Reviewer" }, { value: "admin", label: "Admin" }]} />
          </Field>
          <DialogFooter>
            <Button type="submit" loading={busy} disabled={!email || password.length < 8}>Create user</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function UsersCard() {
  const { data, error, reload } = useApi<User[]>("/api/auth/users");
  return (
    <Card flush title="Users" caption={data ? `${data.length} account(s)` : undefined} actions={<AddUserDialog onCreated={reload} />}>
      {error ? (
        <div className="p-4"><ErrorState error={error} onRetry={reload} /></div>
      ) : !data ? (
        <ListSkeleton rows={2} label="Loading users" />
      ) : (
        <DataTable label="Users">
          <THead>
            <Th edge="start">Email</Th>
            <Th edge="end">Role</Th>
          </THead>
          <TBody>
            {data.map((u) => (
              <Tr key={u.id} dense>
                <Td edge="start">{u.email}</Td>
                <Td edge="end"><Badge tone={u.role === "admin" ? "indigo" : "neutral"} className="capitalize">{u.role}</Badge></Td>
              </Tr>
            ))}
          </TBody>
        </DataTable>
      )}
    </Card>
  );
}
