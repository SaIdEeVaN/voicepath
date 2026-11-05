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

/** How often to keep asking once the server has missed its quick retries. */
const SLOW_RETRY_MS = 15000;

/**
 * How often to ask again once it has answered, while the tab is in view.
 * The model behind it can run out of allowance mid-session, and a notice that
 * only appears on the next page load appears too late to explain anything.
 */
const REFRESH_MS = 60000;

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
  /** A corrected profile. Drops the matches, which were scored on the old one. */
  setProfile(profile: ExtractedProfile): void;
  setMatches(matches: MatchResult[], language: Language): void;
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
  //
  // It never stops trying while the page is open. It used to give up after
  // about 45 seconds and stay given up: on 2026-11-03 the backend was down
  // for an hour, came back, and every page opened during the outage still
  // said it could not reach the server until someone thought to reload. A
  // wake from sleep on the free tier can also run past 45 seconds. Now, once
  // the quick retries are spent, it keeps asking every SLOW_RETRY_MS -- and
  // at once when the tab comes back into view or the network returns -- and
  // the page recovers by itself the moment the server answers.
  useEffect(() => {
    let cancelled = false;
    let answered = false;
    let slowTimer: ReturnType<typeof setTimeout> | null = null;
    let refreshTimer: ReturnType<typeof setTimeout> | null = null;

    const check = async (): Promise<boolean> => {
      try {
        const result = await api.health();
        if (cancelled) return true;
        answered = true;
        setHealth(result);
        setHealthUnreachable(false);
        setHealthWaking(false);
        return true;
      } catch {
        return false;
      }
    };

    const slow = () => {
      slowTimer = setTimeout(async () => {
        if (cancelled || answered) return;
        if (!(await check())) slow();
      }, SLOW_RETRY_MS);
    };

    const fast = async (remaining: number, delayMs: number): Promise<void> => {
      if (await check()) return;
      if (cancelled) return;
      if (remaining <= 0) {
        // Past a normal wake-up: say so, and keep trying more slowly.
        setHealth(null);
        setHealthWaking(false);
        setHealthUnreachable(true);
        slow();
        return;
      }
      setHealthWaking(true);
      await new Promise((resolve) => setTimeout(resolve, delayMs));
      if (cancelled) return;
      // Backoff, capped so a long outage does not stretch to minutes between
      // tries while someone is watching the screen.
      return fast(remaining - 1, Math.min(delayMs * 1.6, 12000));
    };

    // Once it has answered, keep the picture current: the model can be
    // rate-limited or run out of its daily allowance at any point, and the
    // backend says so in /health. Only while the tab is in view, so a page
    // left open in the background does not keep a free-tier server awake. A
    // failed refresh changes nothing -- the last answer stands until a
    // request on the page itself fails.
    const refresh = () => {
      refreshTimer = setTimeout(async () => {
        if (cancelled) return;
        if (answered && document.visibilityState === "visible") await check();
        refresh();
      }, REFRESH_MS);
    };

    // Coming back to the tab, or back online, is the moment someone looks --
    // ask now rather than at the next tick.
    const nudge = () => {
      if (cancelled || document.visibilityState !== "visible") return;
      void check();
    };

    void fast(6, 2000);
    refresh();
    document.addEventListener("visibilitychange", nudge);
    window.addEventListener("online", nudge);

    return () => {
      cancelled = true;
      if (slowTimer) clearTimeout(slowTimer);
      if (refreshTimer) clearTimeout(refreshTimer);
      document.removeEventListener("visibilitychange", nudge);
      window.removeEventListener("online", nudge);
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
  const setProfile = useCallback(
    (profile: ExtractedProfile) =>
      setState((s) => ({ ...s, profile, matches: [], matchesLanguage: null })),
    [],
  );
  const setMatches = useCallback(
    (matches: MatchResult[], language: Language) =>
      setState((s) => ({ ...s, matches, matchesLanguage: language })),
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
      setProfile,
      setMatches,
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
      setProfile,
      setMatches,
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

/**
 * What is running offline, as the interface needs to know it.
 *
 * `storage` is a database that was configured and did not answer -- the API
 * then runs on memory, and a record may not survive. A database that was
 * never configured (local development) is not flagged: nothing was promised.
 */
export function useDegraded(): {
  speech: boolean;
  /** No language model configured: rule-based paths only, by design. */
  language: boolean;
  /** A model is configured but not answering: rate-limited, out of allowance, down. */
  languageBusy: boolean;
  /** When the backend expects it back, if the provider said. ISO 8601. */
  languageBackAt: string | null;
  storage: boolean;
} {
  const { health } = useSession();
  const degraded = health?.degraded ?? [];
  const database = health?.database ?? {};
  const llmStatus = health?.llm?.status;
  const busy = llmStatus !== undefined && llmStatus !== "ok" && llmStatus !== "offline";
  return {
    speech: degraded.includes("stt"),
    // Embeddings down reads the same to a person: only skills they name
    // directly are recognised. Either way this is the notice that says so.
    language: (degraded.includes("llm") && !busy) || degraded.includes("embeddings"),
    languageBusy: busy,
    languageBackAt: busy ? (health?.llm?.until ?? null) : null,
    storage: database.configured === true && database.connected === false,
  };
}
