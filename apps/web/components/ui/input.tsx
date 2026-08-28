import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, hint, id, ...props }, ref) => {
    const inputId = id || props.name;
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={inputId} className="text-xs font-medium text-graphite-700 dark:text-graphite-200">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={cn(
            "h-9 rounded border border-graphite-200 bg-white px-3 text-sm text-graphite-950 placeholder:text-graphite-400 outline-none transition-colors",
            "focus:border-signal-amber",
            "dark:border-graphite-700 dark:bg-graphite-900 dark:text-graphite-50",
            error && "border-signal-red focus:border-signal-red",
            className
          )}
          aria-invalid={!!error}
          aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
          {...props}
        />
        {error && (
          <span id={`${inputId}-error`} className="text-xs text-signal-red">
            {error}
          </span>
        )}
        {!error && hint && (
          <span id={`${inputId}-hint`} className="text-xs text-graphite-600 dark:text-graphite-400">
            {hint}
          </span>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, label, error, hint, id, ...props }, ref) => {
    const inputId = id || props.name;
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={inputId} className="text-xs font-medium text-graphite-700 dark:text-graphite-200">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={inputId}
          className={cn(
            "min-h-[90px] rounded border border-graphite-200 bg-white px-3 py-2 text-sm text-graphite-950 placeholder:text-graphite-400 outline-none transition-colors",
            "focus:border-signal-amber",
            "dark:border-graphite-700 dark:bg-graphite-900 dark:text-graphite-50",
            error && "border-signal-red focus:border-signal-red",
            className
          )}
          aria-invalid={!!error}
          aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
          {...props}
        />
        {error && (
          <span id={`${inputId}-error`} className="text-xs text-signal-red">
            {error}
          </span>
        )}
        {!error && hint && (
          <span id={`${inputId}-hint`} className="text-xs text-graphite-600 dark:text-graphite-400">
            {hint}
          </span>
        )}
      </div>
    );
  }
);
Textarea.displayName = "Textarea";
