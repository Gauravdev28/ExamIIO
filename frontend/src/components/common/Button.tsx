import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'danger' | 'ghost' | 'success' | 'subtle';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  className,
  disabled,
  ...props
}) => {
  const baseStyles = 'inline-flex items-center justify-center font-medium rounded-xl transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-canvas disabled:opacity-50 disabled:cursor-not-allowed select-none active:scale-[0.98]';

  const variants = {
    primary: 'bg-brand-600 hover:bg-brand-700 text-white font-semibold shadow-warm-xs hover:shadow-warm-sm focus:ring-brand-500 active:bg-brand-800',
    secondary: 'bg-canvas-card hover:bg-canvas-subtle text-navy-800 border border-borderWarm shadow-warm-xs hover:border-borderWarm-strong focus:ring-brand-400 active:bg-canvas-subtle',
    outline: 'border border-borderWarm-strong hover:border-brand-600 hover:bg-brand-50 text-navy-800 hover:text-brand-700 focus:ring-brand-500',
    danger: 'bg-accent-coral hover:bg-rose-700 text-white shadow-warm-xs focus:ring-rose-500 active:bg-rose-800 font-semibold',
    ghost: 'hover:bg-canvas-subtle text-navy-700 hover:text-navy-950 focus:ring-navy-300',
    success: 'bg-accent-emerald hover:bg-emerald-700 text-white shadow-warm-xs focus:ring-emerald-500 active:bg-emerald-800 font-semibold',
    subtle: 'bg-brand-50 hover:bg-brand-100 text-brand-700 font-semibold border border-brand-200/60 focus:ring-brand-400',
  };

  const sizes = {
    sm: 'text-xs px-3 py-1.5 gap-1.5',
    md: 'text-sm px-4 py-2 gap-2',
    lg: 'text-base px-5 py-2.5 gap-2.5',
  };

  return (
    <button
      className={twMerge(clsx(baseStyles, variants[variant], sizes[size], className))}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <>
          <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-current" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          Loading...
        </>
      ) : (
        <>
          {leftIcon && <span className="shrink-0">{leftIcon}</span>}
          {children}
          {rightIcon && <span className="shrink-0">{rightIcon}</span>}
        </>
      )}
    </button>
  );
};

