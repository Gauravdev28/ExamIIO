import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export type BadgeVariant =
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'
  | 'neutral'
  | 'purple'
  | 'blue'
  | 'cyan'
  | 'violet'
  | 'emerald'
  | 'amber'
  | 'orange'
  | 'coral';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  dot?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'md',
  className,
  dot = false,
}) => {
  const baseStyles = 'inline-flex items-center font-medium rounded-full select-none';

  const variants: Record<BadgeVariant, string> = {
    success: 'bg-emerald-50 text-emerald-700 border border-emerald-200/80',
    emerald: 'bg-emerald-50 text-emerald-700 border border-emerald-200/80',
    warning: 'bg-amber-50 text-amber-800 border border-amber-200/80',
    amber: 'bg-amber-50 text-amber-800 border border-amber-200/80',
    orange: 'bg-orange-50 text-orange-800 border border-orange-200/80',
    danger: 'bg-rose-50 text-rose-700 border border-rose-200/80',
    coral: 'bg-rose-50 text-rose-700 border border-rose-200/80',
    info: 'bg-brand-50 text-brand-700 border border-brand-200/80',
    blue: 'bg-brand-50 text-brand-700 border border-brand-200/80',
    cyan: 'bg-cyan-50 text-cyan-700 border border-cyan-200/80',
    violet: 'bg-purple-50 text-purple-700 border border-purple-200/80',
    purple: 'bg-purple-50 text-purple-700 border border-purple-200/80',
    neutral: 'bg-canvas-subtle text-navy-700 border border-borderWarm',
  };

  const dotColors: Record<BadgeVariant, string> = {
    success: 'bg-emerald-500',
    emerald: 'bg-emerald-500',
    warning: 'bg-amber-500',
    amber: 'bg-amber-500',
    orange: 'bg-orange-500',
    danger: 'bg-rose-500',
    coral: 'bg-rose-500',
    info: 'bg-brand-500',
    blue: 'bg-brand-500',
    cyan: 'bg-cyan-500',
    violet: 'bg-purple-500',
    purple: 'bg-purple-500',
    neutral: 'bg-navy-400',
  };

  const sizes = {
    sm: 'text-[11px] px-2 py-0.5 gap-1.5 leading-tight',
    md: 'text-xs px-2.5 py-1 gap-1.5 font-semibold leading-tight',
    lg: 'text-sm px-3.5 py-1.5 gap-2 font-semibold',
  };

  return (
    <span className={twMerge(clsx(baseStyles, variants[variant], sizes[size], className))}>
      {dot && (
        <span className={clsx('w-1.5 h-1.5 rounded-full shrink-0', dotColors[variant])} />
      )}
      {children}
    </span>
  );
};

