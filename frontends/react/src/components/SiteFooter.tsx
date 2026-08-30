// SPDX-FileCopyrightText: 2026 Beamstack <https://beam-stack.com>
// SPDX-License-Identifier: LicenseRef-BCL-1.1

/**
 * Persistent attribution footer.
 *
 * Satisfies LICENSE Section 3.7(b): a legible "Powered by Beamstack" credit,
 * linked to https://beam-stack.com, sitting where a user looks for credits
 * (a persistent application footer). Rendered once, at the bottom of the app
 * layout (see App.tsx).
 *
 * Brand blue is `#2F6BF3` (placeholder per brand/README.md — confirm against the
 * official brand). It is not a Tailwind token here (the app accent is red), so it
 * appears as an arbitrary value: `text-[#2F6BF3]`, `ring-[#2F6BF3]`.
 *
 * Logo handling: the official brand mark (brand/beamstack-logo.svg, mirrored to
 * src/assets/beamstack-logo.svg) is white-on-dark and would be invisible dropped
 * straight onto this light footer. The <BeamstackMark /> below therefore draws
 * the stacked-bars glyph in `currentColor`, so it inherits the Beamstack-blue
 * link colour and stays legible in any theme. To switch to the full logo later:
 *   import logoUrl from "@/assets/beamstack-logo.svg";
 *   ...<img src={logoUrl} alt="Beamstack" className="h-4 w-auto" />
 * (that SVG carries its own dark ground, so it reads fine on a light footer).
 */

const BEAMSTACK_URL = "https://beam-stack.com";

function BeamstackMark({ className }: { className?: string }) {
  // Three stacked bars from the Beamstack mark, drawn in currentColor so the
  // parent's text colour (Beamstack blue) keeps it legible on the light footer.
  return (
    <svg
      viewBox="0 0 70 60"
      className={className}
      role="img"
      aria-hidden="true"
      focusable="false"
    >
      <rect x="0" y="0" width="70" height="14" rx="7" fill="currentColor" />
      <rect x="0" y="23" width="70" height="14" rx="7" fill="currentColor" opacity="0.55" />
      <rect x="0" y="46" width="70" height="14" rx="7" fill="currentColor" />
    </svg>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-navy/15 bg-panel/60">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-1.5 px-6 py-4 text-[13px] leading-none text-muted sm:flex-row">
        <a
          href={BEAMSTACK_URL}
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Powered by Beamstack — opens beam-stack.com in a new tab"
          className="group inline-flex items-center gap-1.5 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2F6BF3] focus-visible:ring-offset-2"
        >
          <span className="text-muted">Powered by</span>
          <span className="inline-flex items-center gap-1 font-semibold text-[#2F6BF3] group-hover:underline">
            <BeamstackMark className="h-4 w-auto" />
            Beamstack
          </span>
        </a>
        <span className="text-muted/80">Road Designer v{__APP_VERSION__}</span>
      </div>
    </footer>
  );
}
