"use client";

/**
 * Narrowing the scheme list (PRD section 17), added 2026-11-05.
 *
 * Three questions people bring to the list: what kind of thing it is (a job,
 * training, help to run their own work), where (near them, or open anywhere in
 * India), and -- once they are matched -- which of their skills it is for. Each
 * is one choice at a time, with the count beside it, so nobody picks a filter
 * that empties the page without being told first. An option with nothing
 * behind it is not shown; a group with only one real option is not shown.
 *
 * Filtering only hides rows. The ranking, and the reasons, stay the server's.
 */

import type { Language } from "@/lib/types";
import { copyFor } from "@/lib/i18n";

export type KindFilter = "all" | "jobs" | "training" | "own";
export type WhereFilter = "all" | "local" | "india";

export interface SchemeFilterState {
  kind: KindFilter;
  where: WhereFilter;
  /** A taxonomy code from the person's skills, or "all". */
  skill: string;
}

export const NO_FILTERS: SchemeFilterState = { kind: "all", where: "all", skill: "all" };

interface Filterable {
  type: string;
  location: string;
  matchedSkillCodes?: string[];
}

/**
 * The scheme types the database allows (db/001_schema.sql), grouped the way a
 * person asks. An apprenticeship is paid learning on the job, so it sits with
 * training; self-employment support is the loans, subsidies and toolkits.
 */
export function kindOf(type: string): Exclude<KindFilter, "all"> | null {
  switch (type) {
    case "Full-time":
    case "Part-time":
      return "jobs";
    case "Training":
    case "Apprenticeship":
      return "training";
    case "Self-employment support":
      return "own";
    default:
      return null;
  }
}

export function whereOf(location: string): Exclude<WhereFilter, "all"> {
  return location === "All India" ? "india" : "local";
}

export function passes(item: Filterable, filters: SchemeFilterState): boolean {
  if (filters.kind !== "all" && kindOf(item.type) !== filters.kind) return false;
  if (filters.where !== "all" && whereOf(item.location) !== filters.where) return false;
  if (filters.skill !== "all" && !(item.matchedSkillCodes ?? []).includes(filters.skill)) {
    return false;
  }
  return true;
}

interface Option<T extends string> {
  value: T;
  label: string;
  count: number;
}

export function SchemeFilters({
  items,
  filters,
  onChange,
  skills,
  language,
}: {
  items: Filterable[];
  filters: SchemeFilterState;
  onChange(next: SchemeFilterState): void;
  /** The person's placed skills, as {code, label}. Empty when browsing. */
  skills: { code: string; label: string }[];
  language: Language;
}) {
  const copy = copyFor(language);

  // Each group counts against the other groups' current choices, so a number
  // always says how many rows that choice would leave on the page.
  const countWhere = (change: Partial<SchemeFilterState>) =>
    items.filter((item) => passes(item, { ...filters, ...change })).length;

  const kinds: Option<KindFilter>[] = [
    { value: "all", label: copy.filterAll, count: countWhere({ kind: "all" }) },
    { value: "jobs", label: copy.filterJobs, count: countWhere({ kind: "jobs" }) },
    { value: "training", label: copy.filterTraining, count: countWhere({ kind: "training" }) },
    { value: "own", label: copy.filterOwnWork, count: countWhere({ kind: "own" }) },
  ];
  const wheres: Option<WhereFilter>[] = [
    { value: "all", label: copy.filterAll, count: countWhere({ where: "all" }) },
    { value: "local", label: copy.filterLocal, count: countWhere({ where: "local" }) },
    { value: "india", label: copy.allIndia, count: countWhere({ where: "india" }) },
  ];
  const skillOptions: Option<string>[] = [
    { value: "all", label: copy.filterAll, count: countWhere({ skill: "all" }) },
    ...skills.map((s) => ({ value: s.code, label: s.label, count: countWhere({ skill: s.code }) })),
  ];

  return (
    <div className="flex flex-col gap-3" lang={language}>
      <Group
        label={copy.filterKind}
        options={kinds}
        value={filters.kind}
        onPick={(kind) => onChange({ ...filters, kind })}
      />
      <Group
        label={copy.filterWhere}
        options={wheres}
        value={filters.where}
        onPick={(where) => onChange({ ...filters, where })}
      />
      {skills.length > 1 && (
        <Group
          label={copy.filterSkill}
          options={skillOptions}
          value={filters.skill}
          onPick={(skill) => onChange({ ...filters, skill })}
        />
      )}
    </div>
  );
}

function Group<T extends string>({
  label,
  options,
  value,
  onPick,
}: {
  label: string;
  options: Option<T>[];
  value: T;
  onPick(value: T): void;
}) {
  // Keep the chosen option visible even at zero, so it can be switched off.
  const shown = options.filter((o) => o.value === "all" || o.count > 0 || o.value === value);
  // Fewer than two real choices is no choice: every row is already the same.
  const real = shown.filter((o) => o.value !== "all" && o.count > 0).length;
  if (real < 2 && value === "all") return null;

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <span
        className="font-mono w-[5.5rem] flex-none text-[11px] uppercase tracking-[0.08em] max-[560px]:w-full"
        style={{ color: "var(--ink-45)" }}
      >
        {label}
      </span>
      <div
        role="group"
        aria-label={label}
        className="flex flex-wrap gap-1 rounded-[18px] p-[3px]"
        style={{ background: "var(--ink-04)" }}
      >
        {shown.map((option) => {
          const on = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={on}
              onClick={() => onPick(option.value)}
              className="rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors"
              style={{
                background: on ? "var(--color-surface)" : "transparent",
                color: on ? "var(--color-ink)" : "var(--ink-55)",
                boxShadow: on ? "0 1px 3px rgb(var(--ink-rgb) / 0.12)" : "none",
              }}
            >
              {option.label}
              <span className="font-mono ml-1.5 text-[11px]" style={{ color: "var(--ink-38)" }}>
                {option.count}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
