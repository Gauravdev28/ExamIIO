import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { Button } from './Button';
import { IconPropType } from './IconContainer';

interface EmptyStateProps {
  icon?: IconPropType;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void;
  className?: string;
  children?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  secondaryActionLabel,
  onSecondaryAction,
  className,
  children,
}) => {
  const renderIcon = () => {
    if (!icon) return null;
    if (React.isValidElement(icon)) return icon;
    if (typeof icon === 'function' || (typeof icon === 'object' && icon !== null)) {
      const IconComponent = icon as React.ComponentType<{ className?: string }>;
      return <IconComponent className="w-8 h-8" />;
    }
    return icon;
  };

  return (
    <div
      className={twMerge(
        clsx(
          'flex flex-col items-center justify-center p-8 sm:p-12 text-center rounded-2xl bg-canvas-card border border-borderWarm shadow-warm-xs',
          className
        )
      )}
    >
      {icon && (
        <div className="w-16 h-16 rounded-2xl bg-brand-50 border border-brand-200/80 text-brand-600 flex items-center justify-center mb-4 shadow-warm-xs">
          {renderIcon()}
        </div>
      )}

      <h3 className="font-display text-lg sm:text-xl font-bold text-navy-950 tracking-tight">
        {title}
      </h3>

      {description && (
        <p className="text-xs sm:text-sm text-navy-500 max-w-md mt-1.5 leading-relaxed">
          {description}
        </p>
      )}

      {children && <div className="mt-4 w-full">{children}</div>}

      {(actionLabel || secondaryActionLabel) && (
        <div className="flex flex-wrap items-center justify-center gap-3 mt-6">
          {actionLabel && onAction && (
            <Button variant="primary" size="md" onClick={onAction}>
              {actionLabel}
            </Button>
          )}
          {secondaryActionLabel && onSecondaryAction && (
            <Button variant="secondary" size="md" onClick={onSecondaryAction}>
              {secondaryActionLabel}
            </Button>
          )}
        </div>
      )}
    </div>
  );
};
