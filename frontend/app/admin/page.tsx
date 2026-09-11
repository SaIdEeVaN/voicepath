import Link from "next/link";

/**
 * Admin landing.
 *
 * ``/admin`` used to 404 -- only the three sub-routes existed, so anything
 * linking to the dashboard by its obvious name hit a dead end. This is the
 * index those links deserve: what each view is for, and a word on what admin
 * deliberately cannot see.
 */

const SECTIONS = [
  {
    href: "/admin/schemes",
    title: "Schemes",
    body: "Create, edit and remove the schemes people are matched to. Each one "
      + "carries the government page it is published on.",
    action: "Manage schemes",
  },
  {
    href: "/admin/taxonomy",
    title: "Skill taxonomy",
    body: "The standard vocabulary spoken skills are mapped onto. Adding an "
      + "entry needs an embedding before matching can reach it.",
    action: "View taxonomy",
  },
  {
    href: "/admin/sessions",
    title: "Sessions",
    body: "Counts, scores and languages. Transcripts are deliberately absent: "
      + "usage can be audited without reading what people said.",
    action: "View sessions",
  },
];

export default function AdminHomePage() {
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="font-display text-[clamp(1.5rem,2.6vw,2rem)] tracking-[-0.02em]">
          Admin dashboard
        </h1>
        <p
          className="mt-2 max-w-[46em] text-[14.5px] leading-relaxed"
          style={{ color: "var(--ink-55)" }}
        >
          Everything here changes what beneficiaries are shown. A scheme removed
          stops being matched to anyone; a scheme added is matched from the next
          session onward.
        </p>
      </div>

      <ul className="grid gap-3.5 [grid-template-columns:repeat(auto-fill,minmax(280px,1fr))]">
        {SECTIONS.map((section) => (
          <li key={section.href}>
            <Link
              href={section.href}
              className="flex h-full flex-col gap-2.5 rounded-[14px] p-5 transition-transform hover:-translate-y-0.5"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--ink-09)",
              }}
            >
              <span className="font-display text-[18px] leading-tight">
                {section.title}
              </span>
              <span
                className="flex-1 text-[13.5px] leading-relaxed"
                style={{ color: "var(--ink-55)" }}
              >
                {section.body}
              </span>
              <span className="text-[13px]" style={{ color: "var(--color-accent)" }}>
                {section.action} →
              </span>
            </Link>
          </li>
        ))}
      </ul>

      <p className="max-w-[46em] text-[13px]" style={{ color: "var(--ink-45)" }}>
        Every request here is re-checked server-side against a hashed token. The
        field in the header is a convenience, not the access control.
      </p>
    </div>
  );
}
