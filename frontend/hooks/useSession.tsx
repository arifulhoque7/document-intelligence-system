"use client";

import { createContext, useContext, useEffect } from "react";
import type { User } from "@/lib/types";

export const SessionContext = createContext<User | null>(null);

/** The signed-in user. Only valid inside the app shell, which loads it before rendering pages. */
export function useSession(): User {
  const user = useContext(SessionContext);
  if (!user) throw new Error("useSession must be used inside the app shell");
  return user;
}

/** Lets a detail page name its last breadcrumb (for example a file name) once its data has loaded. */
export const CrumbContext = createContext<(label: string | null) => void>(() => {});

export function usePageCrumb(label: string | null | undefined) {
  const set = useContext(CrumbContext);
  useEffect(() => {
    set(label ?? null);
    return () => set(null);
  }, [label, set]);
}
