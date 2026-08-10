"use client";

import { useEffect, useState } from "react";

type Status = "checking" | "authenticated" | "anonymous";

/** Tjekker login-status mod /api/me (rører ikke datalageret — hurtigt kald). */
export function useAuthStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let cancelled = false;
    fetch("/api/me", { credentials: "same-origin" })
      .then((r) => {
        if (!cancelled) setStatus(r.ok ? "authenticated" : "anonymous");
      })
      .catch(() => {
        if (!cancelled) setStatus("anonymous");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return status;
}
