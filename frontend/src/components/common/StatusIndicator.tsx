import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export type StatusType = 'online' | 'active' | 'warning' | 'error' | 'offline' | 'neutral';

interface StatusIndicatorProps {
  status: StatusType;
  label?: string;
  pulse?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  status,
  label,
  pulse = true,
  size = 'md',
  className,
}) => {
  const dotColors: Record<StatusType, { dot: string; ping: string; text: string }> = {
    online: { dot: 'bg-accent-emerald', ping: 'bg-emerald-400', text: 'text-emerald-700' },
    active: { dot: 'bg-brand-600', ping: 'bg-brand-400', text: 'text-brand-700' },
    warning: { dot: 'bg-accent-amber', ping: 'bg-amber-400', text: 'text-amber-800' },
    error: { dot: 'bg-accent-coral', ping: 'bg-rose-400', text: 'text-rose-700' },
    offline: { dot: 'bg-navy-400', ping: 'bg-navy-300', text: 'text-navy-500' },
    neutral: { dot: 'bg-navy-400', ping: 'bg-navy-300', text: 'text-navy-600' },
  };

  const sizeStyles = {
    sm: 'w-2 h-2',
    md: 'w-2.5 h-2.5',
    lg: 'w-3 h-3',
  };

  const current = dotColors[status];

  return (
    <span className={twMerge(clsx('inline-flex items-center gap-2 select-none', className))}>
      <span className="relative flex items-center justify-center">
        {pulse && status !== 'offline' && status !== 'neutral' && (
          <span
            className={clsx(
              'animate-ping absolute inline-flex h-full w-full rounded-full opacity-75',
              sizeStyles[size],
              current.ping
            )}
          />
        )}
        <span
          className={clsx(
            'relative inline-flex rounded-full',
            sizeStyles[size],
            current.dot
          )}
        />
      </span>
      {label && (
        <span className={clsx('text-xs font-semibold uppercase tracking-wider', current.text)}>
          {label}
        </span>
      )}
    </span>
  );
};
