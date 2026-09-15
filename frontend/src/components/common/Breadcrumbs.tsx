import React from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface BreadcrumbItem {
  label: string;
  href?: string;
  icon?: React.ReactNode;
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
  showHome?: boolean;
  homeHref?: string;
  className?: string;
}

export const Breadcrumbs: React.FC<BreadcrumbsProps> = ({
  items,
  showHome = false,
  homeHref = '/',
  className,
}) => {
  return (
    <nav aria-label="Breadcrumb" className={twMerge('flex items-center text-xs font-medium', className)}>
      <ol className="flex items-center gap-1.5 flex-wrap text-navy-500">
        {showHome && (
          <li className="flex items-center gap-1.5">
            <Link
              to={homeHref}
              className="text-navy-400 hover:text-navy-900 transition-colors p-1 rounded-md hover:bg-canvas-subtle flex items-center"
              aria-label="Home"
            >
              <Home className="w-3.5 h-3.5" />
            </Link>
            <ChevronRight className="w-3.5 h-3.5 text-navy-400 shrink-0" />
          </li>
        )}

        {items.map((item, idx) => {
          const isLast = idx === items.length - 1;

          return (
            <li key={idx} className="flex items-center gap-1.5">
              {item.href && !isLast ? (
                <Link
                  to={item.href}
                  className="text-navy-600 hover:text-brand-600 transition-colors px-1.5 py-0.5 rounded-md hover:bg-canvas-subtle flex items-center gap-1"
                >
                  {item.icon}
                  <span>{item.label}</span>
                </Link>
              ) : (
                <span
                  className={clsx(
                    'px-1.5 py-0.5 flex items-center gap-1',
                    isLast ? 'text-navy-950 font-bold' : 'text-navy-600'
                  )}
                  aria-current={isLast ? 'page' : undefined}
                >
                  {item.icon}
                  <span>{item.label}</span>
                </span>
              )}

              {!isLast && <ChevronRight className="w-3.5 h-3.5 text-navy-400 shrink-0" />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
};
