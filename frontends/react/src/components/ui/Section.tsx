import type { ReactNode } from "react";

/** Collapsible form section — mirrors a Streamlit sidebar st.expander. */
export function Section({
  title,
  defaultOpen = false,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <details
      open={defaultOpen}
      className="group rounded-lg border border-navy/10 bg-white open:shadow-sm"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm font-bold text-navy">
        {title}
        <span className="text-muted transition-transform group-open:rotate-180">⌄</span>
      </summary>
      <div className="grid grid-cols-1 gap-4 border-t border-navy/10 px-4 py-4 sm:grid-cols-2">
        {children}
      </div>
    </details>
  );
}
