import React, { forwardRef } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  helperText?: string;
  error?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  badge?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(({
  label,
  helperText,
  error,
  leftIcon,
  rightIcon,
  badge,
  className,
  id,
  disabled,
  ...props
}, ref) => {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div className="w-full space-y-1">
      {(label || badge) && (
        <div className="flex items-center justify-between gap-2">
          {label && (
            <label htmlFor={inputId} className="text-xs font-semibold uppercase tracking-wider text-navy-700 select-none">
              {label}
            </label>
          )}
          {badge}
        </div>
      )}

      <div className="relative flex items-center">
        {leftIcon && (
          <div className="absolute left-3.5 flex items-center pointer-events-none text-navy-400">
            {leftIcon}
          </div>
        )}

        <input
          ref={ref}
          id={inputId}
          disabled={disabled}
          className={twMerge(
            clsx(
              'w-full px-3.5 py-2.5 text-sm rounded-xl bg-white border text-navy-900 placeholder:text-navy-400 transition-all outline-none',
              'border-borderWarm focus:border-brand-500 focus:ring-2 focus:ring-brand-100',
              leftIcon && 'pl-10',
              rightIcon && 'pr-10',
              error && 'border-accent-coral focus:border-accent-coral focus:ring-rose-100',
              disabled && 'bg-canvas-subtle text-navy-500 cursor-not-allowed opacity-80',
              className
            )
          )}
          {...props}
        />

        {rightIcon && (
          <div className="absolute right-3.5 flex items-center text-navy-400">
            {rightIcon}
          </div>
        )}
      </div>

      {error ? (
        <p className="text-xs text-accent-coral font-medium flex items-center gap-1 mt-1">
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

Input.displayName = 'Input';
