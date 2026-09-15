import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface PageHeaderProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  breadcrumbs?: React.ReactNode;
  className?: string;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  icon,
  title,
  description,
  badge,
  actions,
  breadcrumbs,
  className = '',
}) => {
  return (
    <div
      className={twMerge(
        clsx(
          'flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-6 border-b border-borderWarm',
          className
        )
      )}
    >
      <div className="space-y-1.5">
        {breadcrumbs && <div className="mb-2">{breadcrumbs}</div>}
        <div className="flex items-center gap-3.5">
          {icon && (
            <div className="p-2.5 rounded-2xl bg-brand-50 text-brand-600 border border-brand-200/80 shadow-warm-xs shrink-0 flex items-center justify-center">
              {icon}
            </div>
          )}
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-2xl sm:text-3xl font-bold text-navy-950 tracking-tight font-display">
                {title}
              </h1>
              {badge}
            </div>
            {description && (
              <p className="text-xs sm:text-sm text-navy-500 max-w-2xl mt-0.5 leading-relaxed">
                {description}
              </p>
            )}
          </div>
        </div>
      </div>
      {actions && <div className="flex items-center gap-3 shrink-0 flex-wrap">{actions}</div>}
    </div>
  );
};

export default PageHeader;

