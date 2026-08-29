import { type SelectHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/cn";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  hint?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, hint, className, id, children, ...props }, ref) => {
    const selectId = id ?? `select-${label.replace(/\s+/g, "-").toLowerCase()}`;
    return (
      <div className="flex flex-col gap-1">
        <label htmlFor={selectId} className="text-sm font-medium text-ink">
          {label}
        </label>
        <select
          ref={ref}
          id={selectId}
          className={cn(
            "w-full rounded-md border border-navy/15 bg-white px-3 py-1.5 text-sm text-ink",
            "focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent",
            className
          )}
          {...props}
        >
          {children}
        </select>
        {hint && <p className="text-xs text-muted">{hint}</p>}
      </div>
    );
  }
);
Select.displayName = "Select";
