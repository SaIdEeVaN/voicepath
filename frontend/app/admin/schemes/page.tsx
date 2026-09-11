"use client";

/**
 * Scheme administration -- list, create, edit, delete.
 *
 * The other two admin views are read-only and share ``AdminTable``. This one
 * writes, so it owns its own fetching rather than bending that component into
 * a shape the other two would have to carry.
 *
 * Every write re-reads the list from the server instead of patching local
 * state. A row here decides what beneficiaries are shown, so the screen should
 * display what the database actually holds, not what this tab believes it sent.
 */

import { useCallback, useEffect, useState } from "react";

import { useAdminToken } from "@/lib/admin-token";
import { API_BASE } from "@/lib/api";
import type { SchemeDetail } from "@/lib/types";

const TYPES = [
  "Full-time",
  "Part-time",
  "Training",
  "Apprenticeship",
  "Self-employment support",
] as const;

interface FormState {
  title: string;
  organization: string;
  location: string;
  district: string;
  type: string;
  minimum_experience: string;
  salary_min: string;
  salary_max: string;
  nsqf_level: string;
  source_reference: string;
  official_url: string;
  description: string;
  is_active: boolean;
}

const EMPTY: FormState = {
  title: "",
  organization: "",
  location: "",
  district: "",
  type: "Full-time",
  minimum_experience: "0",
  salary_min: "",
  salary_max: "",
  nsqf_level: "",
  source_reference: "",
  official_url: "",
  description: "",
  is_active: true,
};

function toForm(scheme: SchemeDetail): FormState {
  return {
    title: scheme.title,
    organization: scheme.organization,
    location: scheme.location,
    district: scheme.district ?? "",
    type: scheme.type,
    minimum_experience: String(scheme.minimum_experience ?? 0),
    salary_min: scheme.salary_min?.toString() ?? "",
    salary_max: scheme.salary_max?.toString() ?? "",
    nsqf_level: scheme.nsqf_level ?? "",
    source_reference: scheme.source_reference ?? "",
    official_url: scheme.official_url ?? "",
    description: scheme.description ?? "",
    // Carried through, not assumed: editing a deactivated scheme must not
    // quietly put it back in front of people.
    is_active: scheme.is_active ?? true,
  };
}

/** Empty strings become null, so a cleared field clears the column. */
function toPayload(form: FormState) {
  const text = (value: string) => (value.trim() === "" ? null : value.trim());
  const number = (value: string) =>
    value.trim() === "" ? null : Number(value);
  return {
    title: form.title.trim(),
    organization: form.organization.trim(),
    location: form.location.trim(),
    district: text(form.district),
    type: form.type,
    minimum_experience: Number(form.minimum_experience || 0),
    certifications_required: [],
    salary_min: number(form.salary_min),
    salary_max: number(form.salary_max),
    nsqf_level: text(form.nsqf_level),
    source_reference: text(form.source_reference),
    official_url: text(form.official_url),
    description: text(form.description),
    is_active: form.is_active,
    skill_ids: [],
  };
}

export default function AdminSchemesPage() {
  const [token] = useAdminToken();
  const [schemes, setSchemes] = useState<SchemeDetail[]>([]);
  const [form, setForm] = useState<FormState | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!token) {
      setSchemes([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/admin/schemes`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (!response.ok) throw new Error(await detailOf(response));
      setSchemes((await response.json()) as SchemeDetail[]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load.");
      setSchemes([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    if (!form) return;
    setBusy(true);
    setError(null);
    try {
      const editing = editingId !== null;
      const response = await fetch(
        `${API_BASE}/api/admin/schemes${editing ? `/${editingId}` : ""}`,
        {
          method: editing ? "PUT" : "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(toPayload(form)),
        },
      );
      if (!response.ok) throw new Error(await detailOf(response));
      setForm(null);
      setEditingId(null);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  };

  const reactivate = async (scheme: SchemeDetail) => {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/admin/schemes/${scheme.id}`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ...toPayload(toForm(scheme)), is_active: true }),
      });
      if (!response.ok) throw new Error(await detailOf(response));
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not reactivate.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (scheme: SchemeDetail) => {
    // The endpoint deactivates rather than deletes -- matches reference
    // schemes, and removing the row would take the audit trail with it. The
    // label says so: a button promising deletion that hides the row instead
    // is the kind of small lie this codebase is built to avoid.
    if (
      !window.confirm(
        `Deactivate "${scheme.title}"? It stops being matched to anyone. `
          + `The record is kept, so this can be undone.`,
      )
    ) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/admin/schemes/${scheme.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok && response.status !== 204) {
        throw new Error(await detailOf(response));
      }
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete.");
    } finally {
      setBusy(false);
    }
  };

  if (!token) {
    return (
      <p className="text-sm" style={{ color: "var(--ink-55)" }}>
        Enter an admin token above to manage schemes.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm" style={{ color: "var(--ink-55)" }}>
          {loading ? "Loading…" : `${schemes.length} schemes`}
        </p>
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setEditingId(null);
            setForm({ ...EMPTY });
          }}
          className="vp-pill vp-pill-primary disabled:opacity-50"
        >
          New scheme
        </button>
      </div>

      {error && (
        <p
          className="rounded-xl px-4 py-3 text-sm"
          style={{
            background: "color-mix(in srgb, var(--color-danger) 12%, transparent)",
            color: "var(--color-danger)",
          }}
        >
          {error}
        </p>
      )}

      {form && (
        <SchemeForm
          form={form}
          editing={editingId !== null}
          busy={busy}
          onChange={setForm}
          onCancel={() => {
            setForm(null);
            setEditingId(null);
          }}
          onSave={() => void save()}
        />
      )}

      <ul className="flex flex-col gap-2.5">
        {schemes.map((scheme) => (
          <li
            key={scheme.id}
            className="flex items-start gap-4 rounded-[14px] p-4"
            style={{
              background: "var(--color-surface)",
              border: "1px solid var(--ink-09)",
            }}
          >
            <div className="min-w-0 flex-1">
              <p className="font-display text-[17px] leading-tight">
                {scheme.title}
                {scheme.is_active === false && (
                  <span
                    className="ml-2.5 align-middle text-[11px] uppercase tracking-[0.08em]"
                    style={{ color: "var(--color-caution-ink)" }}
                  >
                    deactivated
                  </span>
                )}
              </p>
              <p className="mt-1 text-[13px]" style={{ color: "var(--ink-55)" }}>
                {[scheme.organization, scheme.location, scheme.type].join(" · ")}
              </p>
              {scheme.official_url ? (
                <a
                  href={scheme.official_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="font-mono mt-1.5 block truncate text-[11px] underline"
                  style={{ color: "var(--ink-45)" }}
                >
                  {scheme.official_url}
                </a>
              ) : (
                <p
                  className="font-mono mt-1.5 text-[11px]"
                  style={{ color: "var(--ink-38)" }}
                >
                  no official page
                </p>
              )}
            </div>

            <div className="flex flex-none gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  setEditingId(scheme.id);
                  setForm(toForm(scheme));
                }}
                className="vp-pill vp-pill-quiet text-[13px] disabled:opacity-50"
              >
                Edit
              </button>
              {scheme.is_active === false ? (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void reactivate(scheme)}
                  className="vp-pill vp-pill-quiet text-[13px] disabled:opacity-50"
                >
                  Reactivate
                </button>
              ) : (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void remove(scheme)}
                  className="vp-pill vp-pill-quiet text-[13px] disabled:opacity-50"
                  style={{ color: "var(--color-danger)" }}
                >
                  Deactivate
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SchemeForm({
  form,
  editing,
  busy,
  onChange,
  onCancel,
  onSave,
}: {
  form: FormState;
  editing: boolean;
  busy: boolean;
  onChange(next: FormState): void;
  onCancel(): void;
  onSave(): void;
}) {
  const set = (key: keyof FormState, value: string | boolean) =>
    onChange({ ...form, [key]: value });

  // Mirrors the server's pattern check, so a typo is caught while the person
  // is still looking at the field rather than after a round trip.
  const urlLooksWrong =
    form.official_url.trim() !== "" && !/^https?:\/\/\S+$/.test(form.official_url.trim());

  const incomplete =
    !form.title.trim() || !form.organization.trim() || !form.location.trim();

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (!incomplete && !urlLooksWrong) onSave();
      }}
      className="flex flex-col gap-4 rounded-[14px] p-5"
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--ink-22)",
      }}
    >
      <p className="font-display text-[17px]">
        {editing ? "Edit scheme" : "New scheme"}
      </p>

      <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]">
        <Field label="Title" value={form.title} onChange={(v) => set("title", v)} />
        <Field
          label="Organisation"
          value={form.organization}
          onChange={(v) => set("organization", v)}
        />
        <Field label="Place" value={form.location} onChange={(v) => set("location", v)} />
        <Field
          label="District"
          value={form.district}
          onChange={(v) => set("district", v)}
        />

        <label className="flex flex-col gap-1.5">
          <span className="text-[12px]" style={{ color: "var(--ink-55)" }}>
            Type
          </span>
          <select
            value={form.type}
            onChange={(event) => set("type", event.target.value)}
            className="rounded-lg px-3 py-2 text-sm"
            style={{ background: "var(--ink-04)", border: "1px solid var(--ink-09)" }}
          >
            {TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>

        <Field
          label="Minimum experience (years)"
          value={form.minimum_experience}
          onChange={(v) => set("minimum_experience", v)}
        />
        <Field
          label="Pay from"
          value={form.salary_min}
          onChange={(v) => set("salary_min", v)}
        />
        <Field
          label="Pay to"
          value={form.salary_max}
          onChange={(v) => set("salary_max", v)}
        />
        <Field
          label="NSQF level"
          value={form.nsqf_level}
          onChange={(v) => set("nsqf_level", v)}
        />
        <Field
          label="Scheme reference"
          value={form.source_reference}
          onChange={(v) => set("source_reference", v)}
        />
      </div>

      <label className="flex flex-col gap-1.5">
        <span className="text-[12px]" style={{ color: "var(--ink-55)" }}>
          Official government page
        </span>
        <input
          value={form.official_url}
          onChange={(event) => set("official_url", event.target.value)}
          placeholder="https://pmvishwakarma.gov.in/"
          className="rounded-lg px-3 py-2 text-sm"
          style={{
            background: "var(--ink-04)",
            border: `1px solid ${urlLooksWrong ? "var(--color-danger)" : "var(--ink-09)"}`,
          }}
        />
        <span className="text-[11px]" style={{ color: "var(--ink-45)" }}>
          {urlLooksWrong
            ? "Must start with http:// or https://"
            : "Quoted to people verbatim. Leave empty rather than guessing one."}
        </span>
      </label>

      <label className="flex flex-col gap-1.5">
        <span className="text-[12px]" style={{ color: "var(--ink-55)" }}>
          Description
        </span>
        <textarea
          value={form.description}
          onChange={(event) => set("description", event.target.value)}
          rows={3}
          className="rounded-lg px-3 py-2 text-sm"
          style={{ background: "var(--ink-04)", border: "1px solid var(--ink-09)" }}
        />
        <span className="text-[11px]" style={{ color: "var(--ink-45)" }}>
          The only text explanations may ground themselves in. Anything not here
          cannot be said about this scheme.
        </span>
      </label>

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={busy || incomplete || urlLooksWrong}
          className="vp-pill vp-pill-primary disabled:opacity-50"
        >
          {busy ? "Saving…" : editing ? "Save changes" : "Create scheme"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className="vp-pill vp-pill-quiet disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange(value: string): void;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[12px]" style={{ color: "var(--ink-55)" }}>
        {label}
      </span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-lg px-3 py-2 text-sm"
        style={{ background: "var(--ink-04)", border: "1px solid var(--ink-09)" }}
      />
    </label>
  );
}

async function detailOf(response: Response): Promise<string> {
  const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
  if (typeof body.detail === "string") return body.detail;
  return `Request failed (${response.status})`;
}
