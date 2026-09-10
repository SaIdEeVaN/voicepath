"use client";

/**
 * The admin bearer token, held for this tab only.
 *
 * Not a security boundary: every /api/admin/* route re-checks the role
 * server-side (PRD section 6.6). This only avoids showing an empty table to
 * someone who has not authenticated yet.
 *
 * sessionStorage rather than localStorage, so closing the tab ends the
 * session rather than leaving a token on a shared machine.
 */

import { useEffect, useState } from "react";

const TOKEN_KEY = "voicepath.admin.token";

export function useAdminToken(): [string, (value: string) => void] {
  const [token, setToken] = useState("");

  useEffect(() => {
    try {
      setToken(window.sessionStorage.getItem(TOKEN_KEY) ?? "");
    } catch {
      /* Storage unavailable; the field still works for this page view. */
    }
  }, []);

  const update = (value: string) => {
    setToken(value);
    try {
      window.sessionStorage.setItem(TOKEN_KEY, value);
    } catch {
      /* Ignored. */
    }
  };

  return [token, update];
}
