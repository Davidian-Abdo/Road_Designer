import { type InputHTMLAttributes, type ReactNode, forwardRef } from "react";
import { cn } from "@/lib/cn";

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  required?: boolean;
  error?: string;
  suffix?: ReactNode;
}

/** Labelled input — the form's atomic building block (mirrors one Streamlit
 * st.number_input / st.text_input row). */
export const Field = forwardRef<HTMLInputElement, FieldProps>(
  ({ label, hint, required, error, suffix, className, id, ...props }, ref) => {
    const inputId = id ?? `field-${label.replace(/\s+/g, "-").toLowerCase()}`;
    return (
      <div className="flex flex-col gap-1">
        <label htmlFor={inputId} className="text-sm font-medium text-ink">
          {label} {required && <span className="text-accent">★</span>}
        </label>
        <div className="flex items-center gap-2">
          <input
            ref={ref}
            id={inputId}
            className={cn(
              "w-full rounded-md border border-navy/15 bg-white px-3 py-1.5 text-sm text-ink",
              "focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent",
              error && "border-accent",
              className
            )}
            {...props}
          />
          {suffix && <span className="text-xs text-muted">{suffix}</span>}
        </div>
        {hint && !error && <p className="text-xs text-muted">{hint}</p>}
        {error && <p className="text-xs font-medium text-accent">{error}</p>}
      </div>
    );
  }
);
Field.displayName = "Field";
