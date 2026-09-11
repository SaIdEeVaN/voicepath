"use client";

/**
 * The session a person is in the middle of.
 *
 * Held in React state and mirrored to sessionStorage, so a refresh mid-flow
 * does not lose what someone just spent two minutes saying. sessionStorage
 * rather than localStorage on purpose: the record should not outlive the tab.
 * The transcript is the sensitive part, and it belongs to this visit.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api } from "./api";
import type {
  ExtractedProfile,
  ExtractedSkill,
  HealthResponse,
  Language,
  MatchResult,
} from "./types";

const STORAGE_KEY = "voicepath.session.v1";

interface StoredState {
  language: Language;
  sessionId: string | null;
  transcript: string;
  profile: ExtractedProfile | null;
  skills: ExtractedSkill[];
  matches: MatchResult[];
  /**
   * Which language `matches` were explained in.
   *
   * Explanations are prose the server writes, not copy the client renders,
   * so they do not follow a language change on their own. Recording the
   * language they arrived in is what lets a screen notice they are stale
   * rather than showing the previous language under a switched interface.
   */
  matchesLanguage: Language | null;
  degraded: boolean;
  audioRetained: boolean;
}

const EMPTY: StoredState = {
  language: "ta",
  sessionId: null,
  transcript: "",
  profile: null,
  skills: [],
  matches: [],
  matchesLanguage: null,
  degraded: false,
  audioRetained: false,
};

interface SessionContextValue extends StoredState {
  health: HealthResponse | null;
  /** True once every health attempt has failed: a real outage. */
  healthUnreachable: boolean;
  /** True while retrying: the backend is probably still waking up. */
  healthWaking: boolean;
  setLanguage(language: Language): void;
  setSession(sessionId: string, transcript: string, language: Language): void;
  setUnderstanding(
    profile: ExtractedProfile,
    skills: ExtractedSkill[],
    degraded: boolean,
  ): void;
  setSkills(skills: ExtractedSkill[]): void;
  setMatches(matches: MatchResult[], language: Language): void;
  setAudioRetained(retained: boolean): void;
  reset(): void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

function read(): StoredState {
  if (typeof window === "undefined") return EMPTY;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY;
    return { ...EMPTY, ...(JSON.parse(raw) as Partial<StoredState>) };
  } catch {
    return EMPTY;
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  // Starts at EMPTY on both server and client so the first paint matches;
  // the stored state is adopted in the effect below. Reading storage during
  // render would hydrate-mismatch.
  const [state, setState] = useState<StoredState>(EMPTY);
  const [hydrated, setHydrated] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthUnreachable, setHealthUnreachable] = useState(false);
  const [healthWaking, setHealthWaking] = useState(false);

  useEffect(() => {
    setState(read());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      /* Private mode, or storage full. The flow still works in memory. */
    }
  }, [state, hydrated]);

  // Health, with retries. A free-tier host suspends the backend when idle and
  // takes 30-60s to wake, so a single failed call says "unreachable" about a
  // server that is merely asleep. Retrying with backoff covers the wake-up, and
  // `healthWaking` lets screens say "starting up" rather than "broken" while it
  // happens -- a distinction the person waiting can act on.
  useEffect(() => {
    let cancelled = false;

    const attempt = async (remaining: number, delayMs: number): Promise<void> => {
      try {
        const result = await api.health();
        if (cancelled) return;
        setHealth(result);
        setHealthUnreachable(false);
        setHealthWaking(false);
      } catch {
        if (cancelled) return;
        if (remaining <= 0) {
          // Out of attempts: this is a real outage, not a slow start.
          setHealth(null);
          setHealthWaking(false);
          setHealthUnreachable(true);
          return;
        }
        setHealthWaking(true);
        await new Promise((resolve) => setTimeout(resolve, delayMs));
        if (cancelled) return;
        // Backoff, capped so a long outage does not stretch to minutes between
        // tries while someone is watching the screen.
        return attempt(remaining - 1, Math.min(delayMs * 1.6, 12000));
      }
    };

    void attempt(6, 2000);

    return () => {
      cancelled = true;
    };
  }, []);

  // Every setter is a functional update, so none of them needs a dependency --
  // and each must keep a stable identity. Screens list these in effect
  // dependency arrays; a setter rebuilt on every state change re-runs those
  // effects, which tears down in-flight work and starts it again.
  const setLanguage = useCallback(
    (language: Language) => setState((s) => ({ ...s, language })),
    [],
  );
  const setSession = useCallback(
    (sessionId: string, transcript: string, language: Language) =>
      setState((s) => ({
        ...s,
        sessionId,
        transcript,
        language,
        // A new recording invalidates everything downstream of it.
        profile: null,
        skills: [],
        matches: [],
        matchesLanguage: null,
      })),
    [],
  );
  const setUnderstanding = useCallback(
    (profile: ExtractedProfile, skills: ExtractedSkill[], degraded: boolean) =>
      setState((s) => ({
        ...s,
        profile,
        skills,
        degraded,
        matches: [],
        matchesLanguage: null,
      })),
    [],
  );
  const setSkills = useCallback(
    (skills: ExtractedSkill[]) =>
      setState((s) => ({ ...s, skills, matches: [] })),
    [],
  );
  const setMatches = useCallback(
    (matches: MatchResult[], language: Language) =>
      setState((s) => ({ ...s, matches, matchesLanguage: language })),
    [],
  );
  const setAudioRetained = useCallback(
    (audioRetained: boolean) => setState((s) => ({ ...s, audioRetained })),
    [],
  );
  const reset = useCallback(
    () => setState((s) => ({ ...EMPTY, language: s.language })),
    [],
  );

  const value = useMemo<SessionContextValue>(
    () => ({
      ...state,
      health,
      healthUnreachable,
      healthWaking,
      setLanguage,
      setSession,
      setUnderstanding,
      setSkills,
      setMatches,
      setAudioRetained,
      reset,
    }),
    [
      state,
      health,
      healthUnreachable,
      healthWaking,
      setLanguage,
      setSession,
      setUnderstanding,
      setSkills,
      setMatches,
      setAudioRetained,
      reset,
    ],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used inside SessionProvider");
  }
  return context;
}

/** True when speech or language services are running offline. */
export function useDegraded(): { speech: boolean; language: boolean } {
  const { health } = useSession();
  const degraded = health?.degraded ?? [];
  return {
    speech: degraded.includes("stt"),
    language: degraded.includes("llm"),
  };
}

/** Retry helper for screens that need a session but were opened cold. */
export function useRequireSession(): { sessionId: string | null; ready: boolean } {
  const { sessionId } = useSession();
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);
  return { sessionId, ready };
}

export const useSessionCallbacks = () => {
  const session = useSession();
  return useCallback(() => session, [session]);
};
