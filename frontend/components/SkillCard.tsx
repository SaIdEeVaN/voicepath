"use client";

/**
 * One extracted skill, with the words that produced it.
 *
 * The evidence panel is not a detail -- it is the trust layer (PRD section 7).
 * A person seeing "Two-Wheeler Repair" attributed to them can read the exact
 * sentence of their own that produced it, and delete it if the machine got it
 * wrong. That is why the quote sits inside the card rather than behind a
 * disclosure.
 */

import { useState } from "react";

import { categoryLabel, copyFor, skillLabel } from "@/lib/i18n";

// Mirrors NORMALIZATION_ACCEPT_THRESHOLD on the server. Shown, not enforced
// here -- the decision was already made; this only says what the bar was.
const ACCEPT_THRESHOLD = 0.82;
import type { ExtractedSkill, Language } from "@/lib/types";

interface SkillCardProps {
  skill: ExtractedSkill;
  language: Language;
  onRename(name: string): void;
  onRemove(): void;
  onDisambiguate(): void;
}

export function SkillCard({
  skill,
  language,
  onRename,
  onRemove,
  onDisambiguate,
}: SkillCardProps) {
  const copy = copyFor(language);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(skill.raw_name);

  const uncertain = skill.needs_disambiguation;
  const confidence =
    typeof skill.match_confidence === "number" ? skill.match_confidence : null;
  const title = skillLabel(skill, language);

  const commit = () => {
    const next = draft.trim();
    if (next && next !== skill.raw_name) onRename(next);
    else setDraft(skill.raw_name);
    setEditing(false);
  };

  return (
    <div
      className="flex flex-col gap-3.5 rounded-[14px] p-5.5"
      style={{
        background: "var(--color-surface)",
        border: `1px solid ${
          uncertain
            ? "color-mix(in srgb, var(--color-caution) 45%, transparent)"
            : "var(--ink-09)"
        }`,
        padding: "1.375rem",
      }}
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          {editing ? (
            <input
              value={draft}
              autoFocus
              onChange={(event) => setDraft(event.target.value)}
              onBlur={commit}
              onKeyDown={(event) => {
                if (event.key === "Enter") commit();
                if (event.key === "Escape") {
                  setDraft(skill.raw_name);
                  setEditing(false);
                }
              }}
              aria-label={copy.edit}
              className="font-display w-full rounded-[7px] px-2 py-1 text-[21px] tracking-[-0.02em] outline-none"
              style={{
                border: "1px solid var(--color-accent)",
                background: "#fff",
              }}
            />
          ) : (
            <h3
              className="font-display text-[21px] leading-tight tracking-[-0.02em]"
              lang={language}
            >
              {title}
            </h3>
          )}
          <p
            className="font-mono mt-1.5 text-[11px] tracking-[0.05em]"
            style={{ color: "var(--ink-38)" }}
          >
            {skill.normalized_code
              ? `${categoryLabel(skill.category, language)} · ${skill.normalized_code}`.trim()
              : skill.raw_name}
          </p>

          {/* The number behind the match, and the bar it had to clear. A score
              shown against its threshold is a claim someone can check; "the
              system understood you" is not. Hidden when nothing matched --
              there is no score to defend. */}
          {skill.normalized_code && confidence !== null && (
            <p
              className="font-mono mt-1 text-[11px] tracking-[0.04em]"
              style={{ color: uncertain ? "var(--color-caution-ink)" : "var(--ink-45)" }}
            >
              {confidence.toFixed(3)}
              {" · "}
              {uncertain ? copy.confidenceAsking : copy.confidenceAccepted}
              {" · "}
              {copy.confidenceThreshold} {ACCEPT_THRESHOLD.toFixed(2)}
            </p>
          )}
        </div>

        <div className="flex flex-none gap-1">
          <IconButton
            label={copy.edit}
            onClick={() => setEditing((value) => !value)}
          >
            <path d="M4 20h4L19 9l-4-4L4 16z" />
          </IconButton>
          <IconButton label={copy.remove} onClick={onRemove} danger>
            <path d="M6 6l12 12M18 6L6 18" />
          </IconButton>
        </div>
      </div>

      <figure
        className="flex flex-col gap-1.5 rounded-[10px] px-4 py-3"
        style={{ background: "var(--ink-03)" }}
      >
        <figcaption
          className="font-mono flex items-center gap-1.5 text-[10.5px] tracking-[0.06em]"
          style={{ color: "var(--ink-45)" }}
        >
          <svg
            viewBox="0 0 24 24"
            width={12}
            height={12}
            fill="none"
            stroke="currentColor"
            strokeWidth={1.8}
            strokeLinecap="round"
            aria-hidden="true"
          >
            <path d="M4 12h2.5l2-5 3 10 3-8 2 3H20" />
          </svg>
          {copy.youSaid}
        </figcaption>
        <blockquote
          className="text-[15px] leading-snug"
          style={{ color: "var(--ink-80)" }}
          lang={language}
        >
          {skill.evidence_phrase}
        </blockquote>
      </figure>

      {uncertain && (
        <button
          type="button"
          onClick={onDisambiguate}
          className="flex items-center gap-2.5 rounded-[10px] px-3.5 py-2.5 text-left text-[13px] leading-snug transition-colors"
          style={{
            background:
              "color-mix(in srgb, var(--color-caution) 14%, transparent)",
            color: "var(--color-caution-ink)",
          }}
          lang={language}
        >
          <span
            className="h-[7px] w-[7px] flex-none rotate-45"
            style={{ background: "var(--color-caution-mark)" }}
          />
          {copy.notSure}
        </button>
      )}
    </div>
  );
}

function IconButton({
  label,
  onClick,
  danger = false,
  children,
}: {
  label: string;
  onClick(): void;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      className={`vp-icon-button grid h-[30px] w-[30px] place-items-center rounded-lg${
        danger ? " vp-icon-button-danger" : ""
      }`}
    >
      <svg
        viewBox="0 0 24 24"
        width={15}
        height={15}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.7}
        strokeLinecap="round"
        aria-hidden="true"
      >
        {children}
      </svg>
    </button>
  );
}
