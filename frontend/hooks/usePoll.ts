"use client";

import { useEffect, useRef } from "react";

/** Calls `fn` every `ms` while `active` is true; pauses while the tab is hidden. */
export function usePoll(fn: () => unknown, active: boolean, ms = 2000) {
  const saved = useRef(fn);
  saved.current = fn;

  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => {
      if (document.visibilityState === "visible") void saved.current();
    }, ms);
    return () => clearInterval(id);
  }, [active, ms]);
}
