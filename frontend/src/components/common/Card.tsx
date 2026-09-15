import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'warm' | 'elevated' | 'outlined' | 'tinted' | 'interactive';
  glass?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  variant = 'warm',
  glass = false,
  className,
  ...props
}) => {
  const variantStyles = {
    warm: 'bg-canvas-card border border-borderWarm shadow-warm-xs text-navy-900',
    elevated: 'bg-white border border-borderWarm shadow-warm-md text-navy-900',
    outlined: 'bg-transparent border border-borderWarm text-navy-900',
    tinted: 'bg-canvas-tinted border border-brand-200/70 shadow-warm-xs text-navy-900',
    interactive: 'bg-canvas-card border border-borderWarm shadow-warm-xs hover:shadow-warm-md hover:border-borderWarm-strong hover:-translate-y-0.5 transition-all duration-200 cursor-pointer text-navy-900',
  };

  const glassStyle = glass ? 'warm-glass' : '';

  return (
    <div
      className={twMerge(
        clsx(
          'rounded-2xl p-6 transition-all duration-200',
          variantStyles[variant],
          glassStyle,
          className
        )
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export const CardHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, children, ...props }) => (
  <div className={twMerge('flex flex-col space-y-1.5 pb-4 border-b border-borderWarm-subtle', className)} {...props}>
    {children}
  </div>
);

export const CardTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({ className, children, ...props }) => (
  <h3 className={twMerge('font-display text-lg font-bold text-navy-950 tracking-tight leading-tight', className)} {...props}>
    {children}
  </h3>
);

export const CardDescription: React.FC<React.HTMLAttributes<HTMLParagraphElement>> = ({ className, children, ...props }) => (
  <p className={twMerge('text-xs text-navy-500 leading-relaxed', className)} {...props}>
    {children}
  </p>
);

export const CardContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, children, ...props }) => (
  <div className={twMerge('pt-4', className)} {...props}>
    {children}
  </div>
);

export const CardFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, children, ...props }) => (
  <div className={twMerge('flex items-center pt-4 border-t border-borderWarm-subtle mt-4', className)} {...props}>
    {children}
  </div>
);

