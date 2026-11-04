"use client";

import { useSyncExternalStore } from "react";
import { APPEARANCE_KEY } from "@/lib/appearance";

export type Appearance = "light" | "dark" | "system";

const KEY = APPEARANCE_KEY;
const listeners = new Set<() => void>();

function read(): Appearance {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

export function applyAppearance(mode: Appearance) {
  const dark = mode === "dark" || (mode === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
  document.documentElement.style.colorScheme = dark ? "dark" : "light";
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const onSystem = () => {
    if (read() === "system") applyAppearance("system");
    cb();
  };
  media.addEventListener("change", onSystem);
  return () => {
    listeners.delete(cb);
    media.removeEventListener("change", onSystem);
  };
}

/** Light, dark or system theme, remembered per browser. Storage failures fall back to system. */
export function useAppearance() {
  const appearance = useSyncExternalStore(subscribe, read, () => "system" as Appearance);
  function updateAppearance(mode: Appearance) {
    try {
      localStorage.setItem(KEY, mode);
    } catch {
      // Private mode or blocked storage: the choice still applies for this page view.
    }
    applyAppearance(mode);
    listeners.forEach((l) => l());
  }
  return { appearance, updateAppearance };
}
