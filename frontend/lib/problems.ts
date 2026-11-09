/**
 * What went wrong, kept as a cause rather than a sentence (2026-11-09).
 *
 * Screens used to store an error as finished text -- the API's English
 * "That session was not found.", or a sentence from the copy in whatever
 * language was on when it happened -- so a Tamil reader saw English, and an
 * error already on screen stayed in its old language after a switch. A
 * Problem is the cause: a key into the copy, or the API error with its code.
 * It becomes words only when drawn, in the language being read then.
 */

import { ApiError } from "./api";
import { copyFor, type Copy } from "./i18n";
import type { Language } from "./types";

/** The copy's plain sentences -- the keys whose value is a string. */
export type CopyKey = {
  [K in keyof Copy]: Copy[K] extends string ? K : never;
}[keyof Copy];

export type Problem = { key: CopyKey } | { api: ApiError };

/** A sentence the app itself says. */
export function problem(key: CopyKey): Problem {
  return { key };
}

/** Whatever a failed call threw. */
export function fromError(cause: unknown): Problem {
  return cause instanceof ApiError ? { api: cause } : { key: "somethingWentWrong" };
}

export function problemText(found: Problem | null, language: Language): string | null {
  if (!found) return null;
  const copy = copyFor(language);
  if ("key" in found) return copy[found.key];

  const error = found.api;
  // Could not reach the API at all.
  if (error.status === 0) return copy.serverUnreachable;
  const translated = error.code ? copy.errorCodes[error.code] : undefined;
  if (translated) return translated;
  // Untranslated: the API's own words are English, so they are right for an
  // English reader; anyone else gets the plain "something went wrong".
  return language === "en" ? error.message : copy.somethingWentWrong;
}
