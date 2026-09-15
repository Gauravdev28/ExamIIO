import React, { forwardRef } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { ChevronDown } from 'lucide-react';

export interface SelectOption {
  value: string | number;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  helperText?: string;
  error?: string;
  options?: SelectOption[];
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(({
  label,
  helperText,
  error,
  options,
  children,
  className,
  id,
  disabled,
  ...props
}, ref) => {
  const selectId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div className="w-full space-y-1">
      {label && (
        <label htmlFor={selectId} className="text-xs font-semibold uppercase tracking-wider text-navy-700 select-none">
          {label}
        </label>
      )}

      <div className="relative flex items-center">
        <select
          ref={ref}
          id={selectId}
          disabled={disabled}
          className={twMerge(
            clsx(
              'w-full appearance-none px-3.5 py-2.5 pr-10 text-sm rounded-xl bg-white border text-navy-900 transition-all outline-none',
              'border-borderWarm focus:border-brand-500 focus:ring-2 focus:ring-brand-100 cursor-pointer',
              error && 'border-accent-coral focus:border-accent-coral focus:ring-rose-100',
              disabled && 'bg-canvas-subtle text-navy-500 cursor-not-allowed opacity-80',
              className
            )
          )}
          {...props}
        >
          {options
            ? options.map((opt) => (
                <option key={opt.value} value={opt.value} disabled={opt.disabled}>
                  {opt.label}
                </option>
              ))
            : children}
        </select>

        <div className="absolute right-3.5 flex items-center pointer-events-none text-navy-400">
          <ChevronDown className="w-4 h-4" />
        </div>
      </div>

      {error ? (
        <p className="text-xs text-accent-coral font-medium mt-1">
          {error}
        </p>
      ) : helperText ? (
        <p className="text-xs text-navy-500 mt-1">
          {helperText}
        </p>
      ) : null}
    </div>
  );
});

Select.displayName = 'Select';
