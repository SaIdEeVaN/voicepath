"use client";

/**
 * Understanding (PRD section 5).
 *
 * Everything the machine believes about the person, shown before it is used
 * for anything, with the evidence attached and an edit control on each line.
 * The confirm button is the only way forward, so nothing is matched against a
 * profile the person has not seen.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { DegradedNote, ErrorNote } from "@/components/Notices";
import { MicIcon } from "@/components/MicIcon";
import { AddSkillByTyping } from "@/components/AddSkillByTyping";
import { SkillCard } from "@/components/SkillCard";
import { ApiError, api } from "@/lib/api";
import { copyFor } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import type { AssistantQueryResponse, Language, SkillEdit } from "@/lib/types";

export default function UnderstandingPage() {
  const router = useRouter();
  const {
    language,
    sessionId,
    transcript,
    skills,
    profile,
    setUnderstanding,
    setSkills,
  } = useSession();
  const copy = copyFor(language);

  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [answer, setAnswer] = useState<AssistantQueryResponse | null>(null);
  // A ref, not state. As state this was in the effect's own dependency
  // array, so setting it re-ran the effect, which fired the previous
  // cleanup, which set cancelled -- and the answer was thrown away when it
  // arrived. The guard against asking twice was what stopped it answering
  // once. A ref changes nothing React watches.
  //
  // It holds the language it last asked in, rather than a bare boolean.
  // The answer is prose the server wrote in one language; a boolean said
  // "already asked" and so pinned it there forever, leaving the previous
  // language's answer sitting under a switched interface.
  const askedIn = useRef<Language | null>(null);

  useEffect(() => setHydrated(true), []);

  // Extraction runs once per session. Re-entering the screen after an edit
  // reads what is already in state rather than re-extracting, which would
  // discard the person's corrections.
  useEffect(() => {
    if (!hydrated) return;
    if (!sessionId) {
      router.replace("/speak");
      return;
    }
    if (profile !== null || skills.length > 0) return;

    let cancelled = false;
    setLoading(true);
    api
      .extract(sessionId)
      .then((result) => {
        if (cancelled) return;
        setUnderstanding(result.profile, result.skills, result.degraded);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setError(
          cause instanceof ApiError ? cause.message : copy.somethingWentWrong,
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [hydrated, sessionId, profile, skills.length, router, setUnderstanding]);

  /**
   * Ask what they were doing, then do it.
   *
   * "I repair two-wheelers" is work to extract. "Tell me about Adarsh Gram" is
   * a question for the guidelines. "I do welding, is there a scheme for that?"
   * is both, and it is the case worth getting right -- reading it as one or
   * the other silently drops half of what they said.
   *
   * What goes to retrieval depends on which it was. A question on its own
   * searches as asked. A question attached to a description searches with the
   * whole sentence, because the slice loses its own subject -- "is there a
   * scheme for that?" cannot say what "that" was, and the answer drifts to
   * whatever the documents mention most. Measured: the slice returned a vague
   * yes, the whole sentence returned "the passages do not mention a specific
   * scheme for welding", which is the true answer.
   */
  useEffect(() => {
    if (!hydrated || !transcript.trim() || askedIn.current === language) return;
    askedIn.current = language;

    let cancelled = false;
    api
      .understand(transcript, language)
      .then((intent) => {
        if (cancelled || !intent.asks_question || !intent.question) return;
        const question = intent.describes_work ? transcript : intent.question;
        return api
          .ask({ sessionId, schemeId: null, question, language })
          .then((result) => {
            // Shown only when a document backs it. An uncited answer would be
            // the model talking about a scheme it has not read.
            if (!cancelled && (result.citations?.length ?? 0) > 0) setAnswer(result);
          });
      })
      .catch(() => {
        /* Classification is a router, not a guarantee. If it cannot run, the
           extraction path below still does what it always did. */
      });

    return () => {
      cancelled = true;
    };
  }, [hydrated, transcript, sessionId, language]);

  const push = useCallback(
    async (edits: SkillEdit[]) => {
      if (!sessionId) return;
      setBusy(true);
      setError(null);
      try {
        const result = await api.normalize(sessionId, edits);
        setSkills(result.skills);
      } catch (cause) {
        setError(
          cause instanceof ApiError ? cause.message : copy.somethingWentWrong,
        );
      } finally {
        setBusy(false);
      }
    },
    // copy is in here so a failure after a language switch is reported in
    // the language now on screen, not the one the callback was built in.
    [sessionId, setSkills, copy.somethingWentWrong],
  );

  const asEdits = (): SkillEdit[] =>
    skills.map((skill) => ({
      id: skill.id,
      raw_name: skill.raw_name,
      evidence_phrase: skill.evidence_phrase,
      chosen_skill_id: skill.user_confirmed ? skill.normalized_skill_id : null,
    }));

  /**
   * A skill the person typed rather than spoke.
   *
   * It joins the list as any other does, and goes through the same
   * normalization: exact alias, then embedding, then the disambiguation screen
   * if it is not clear enough. Nothing is accepted just because it was typed.
   *
   * The typed words are the evidence. Every card shows the words that produced
   * it, and for this one that is what they wrote -- the same rule the landing
   * page follows when someone types instead of speaking.
   */
  const addTyped = (text: string) => {
    void push([
      ...asEdits(),
      { raw_name: text, evidence_phrase: text, chosen_skill_id: null },
    ]);
  };

  const rename = (index: number, name: string) => {
    const edits = asEdits();
    const target = edits[index];
    if (!target) return;
    // The evidence stays exactly as it was. Renaming corrects the label the
    // machine chose, and must never rewrite what the person said.
    void push(
      edits.map((edit, i) =>
        i === index ? { ...target, raw_name: name, chosen_skill_id: null } : edit,
      ),
    );
  };

  const remove = (index: number) => {
    void push(
      asEdits().map((edit, i) => (i === index ? { ...edit, removed: true } : edit)),
    );
  };

  if (!hydrated) return null;

  const uncertainCount = skills.filter((s) => s.needs_disambiguation).length;

  return (
    <section className="mx-auto w-full max-w-[1180px] flex-1 px-[7vw] py-[clamp(2rem,5vw,3.5rem)] pb-20">
      <DegradedNote />

      <div className="mb-10 flex flex-wrap items-end justify-between gap-10">
        <div>
          <h1 className="vp-display max-w-[20em] text-[clamp(1.875rem,3.4vw,2.875rem)]" lang={language}>
            {loading ? copy.loading : copy.weHeard}
          </h1>
          <p
            className="mt-3 max-w-[34em] text-[14.5px] leading-relaxed"
            style={{ color: "var(--ink-55)" }}
            lang={language}
          >
            {copy.weHeardSub}
          </p>
        </div>

        {skills.length > 0 && (
          <button
            type="button"
            disabled={busy}
            onClick={() => router.push("/passport")}
            className="vp-pill vp-pill-primary flex-none disabled:opacity-50"
            lang={language}
          >
            {copy.confirm}
            <span className="text-[17px]">→</span>
          </button>
        )}
      </div>

      {error && (
        <div className="mb-8 max-w-[46em]">
          <ErrorNote message={error} />
        </div>
      )}

      {uncertainCount > 0 && (
        <button
          type="button"
          onClick={() => router.push("/understanding/disambiguate")}
          className="mb-6 flex items-center gap-2.5 rounded-xl px-4 py-3 text-sm"
          style={{
            background:
              "color-mix(in srgb, var(--color-caution) 14%, transparent)",
            color: "var(--color-caution-ink)",
          }}
          lang={language}
        >
          <span
            className="h-2 w-2 flex-none rotate-45"
            style={{ background: "var(--color-caution-mark)" }}
          />
          {copy.notSure} ({uncertainCount})
        </button>
      )}

      {/* Shown whenever a document answered them, skills or not. Someone who
          said "I do welding, is there a scheme for that?" gets both: the
          answer to what they asked, and the skills from what they told us. */}
      {answer && (
        <div className="mb-10 flex flex-col gap-5">
          <div>
            <h2 className="vp-display text-[clamp(1.375rem,2.4vw,1.75rem)]" lang={language}>
              {copy.answeredQuestion}
            </h2>
            <p
              className="mt-3 max-w-[44em] text-[15.5px] leading-relaxed"
              style={{ color: "var(--ink-70)" }}
              lang={language}
            >
              {answer.answer_text}
            </p>
          </div>

          <ul className="flex max-w-[44em] flex-col gap-1.5">
            {(answer.citations ?? []).map((citation, index) => (
              <li
                key={`${citation.source}-${index}`}
                className="rounded-lg px-3 py-2 text-[12px] leading-relaxed"
                style={{ background: "var(--ink-04)", color: "var(--ink-55)" }}
              >
                <span className="font-mono text-[11px]" style={{ color: "var(--ink-45)" }}>
                  {citation.document_title}
                  {citation.heading ? ` · ${citation.heading}` : ""}
                </span>
                <span className="mt-1 block">&ldquo;{citation.excerpt}&rdquo;</span>
              </li>
            ))}
          </ul>

          {/* Only when they asked without telling us anything. Someone who did
              both has skills below and does not need to be sent back. */}
          {!loading && skills.length === 0 && (
            <div className="flex flex-col items-start gap-3">
              <p className="text-[14px]" style={{ color: "var(--ink-55)" }} lang={language}>
                {copy.askedNotTold}
              </p>
              <button
                type="button"
                onClick={() => router.push("/speak")}
                className="vp-pill vp-pill-primary"
                lang={language}
              >
                {copy.resay}
              </button>
            </div>
          )}
        </div>
      )}

      {!loading && skills.length === 0 && !answer ? (
        <div className="flex flex-col items-center gap-7">
          <EmptyState
            title={copy.nothingHeard}
            body={copy.nothingHeardSub}
            action={copy.resay}
            onAction={() => router.push("/speak")}
          />
          {/* Speech already failed to find anything for this person once.
              Offering only the microphone again is the least useful thing the
              screen can do. */}
          <AddSkillByTyping
            language={language}
            busy={busy}
            onAdd={addTyped}
          />
        </div>
      ) : skills.length === 0 ? null : (

        <div className="grid gap-3.5 [grid-template-columns:repeat(auto-fill,minmax(310px,1fr))]">
          {skills.map((skill, index) => (
            <SkillCard
              key={skill.id ?? `${skill.raw_name}-${index}`}
              skill={skill}
              language={language}
              onRename={(name) => rename(index, name)}
              onRemove={() => remove(index)}
              onDisambiguate={() => router.push("/understanding/disambiguate")}
            />
          ))}

          <button
            type="button"
            onClick={() => router.push("/speak")}
            className="flex min-h-[170px] flex-col items-center justify-center gap-3 rounded-[14px] border border-dashed p-5.5 transition-colors"
            style={{ borderColor: "var(--ink-22)", color: "var(--ink-45)" }}
            lang={language}
          >
            <MicIcon size={28} />
            <span className="text-center text-sm leading-snug">
              {copy.addMore}
            </span>
          </button>
        </div>
      )}

      {/* Typing sits under the cards rather than among them: the mic keeps its
          place as the first thing offered, and this is the second way. */}
      {!loading && skills.length > 0 && (
        <div className="mt-7 flex justify-center">
          <AddSkillByTyping language={language} busy={busy} onAdd={addTyped} />
        </div>
      )}
    </section>
  );
}

function EmptyState({
  title,
  body,
  action,
  onAction,
}: {
  title: string;
  body: string;
  action: string;
  onAction(): void;
}) {
  return (
    <div className="flex flex-col items-start gap-4 py-10">
      <h2 className="vp-display max-w-[18em] text-[clamp(1.375rem,2.4vw,1.875rem)]">
        {title}
      </h2>
      <p className="max-w-[32em] text-[15px]" style={{ color: "var(--ink-62)" }}>
        {body}
      </p>
      <button type="button" onClick={onAction} className="vp-pill vp-pill-primary mt-2">
        <MicIcon size={17} strokeWidth={1.5} />
        {action}
      </button>
    </div>
  );
}
