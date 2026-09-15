import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { IconContainer, IconColor, IconPropType } from './IconContainer';

export interface StatCardProps {
  icon: IconPropType;
  iconColor?: IconColor;
  color?: IconColor;
  title: string;
  value: string | number;
  subtitle?: string;
  badge?: React.ReactNode;
  trend?: {
    value: string;
    isPositive?: boolean;
  };
  onClick?: () => void;
  className?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  icon,
  iconColor,
  color = 'blue',
  title,
  value,
  subtitle,
  badge,
  trend,
  onClick,
  className,
}) => {
  const activeColor = iconColor || color;
  const isInteractive = Boolean(onClick);

  return (
    <div
      onClick={onClick}
      className={twMerge(
        clsx(
          'p-5 rounded-2xl bg-canvas-card border border-borderWarm shadow-warm-xs transition-all duration-200',
          isInteractive && 'hover:shadow-warm-md hover:border-borderWarm-strong hover:-translate-y-0.5 cursor-pointer',
          className
        )
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <IconContainer icon={icon} color={activeColor} size="md" />
        {badge}
      </div>

      <div className="mt-4 space-y-1">
        <div className="text-2xl sm:text-3xl font-bold font-display text-navy-950 tracking-tight leading-none">
          {value}
        </div>
        <div className="text-xs font-semibold uppercase tracking-wider text-navy-500">
          {title}
        </div>
        {subtitle && (
          <p className="text-xs text-navy-400 mt-1">
            {subtitle}
          </p>
        )}
      </div>

      {trend && (
        <div className="mt-3 pt-3 border-t border-borderWarm-subtle flex items-center gap-1.5 text-xs font-medium">
          <span className={trend.isPositive ? 'text-accent-emerald' : 'text-accent-coral'}>
            {trend.value}
          </span>
          <span className="text-navy-400">vs last cycle</span>
        </div>
      )}
    </div>
  );
};
