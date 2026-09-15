import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'text' | 'circular' | 'rectangular';
  width?: string | number;
  height?: string | number;
}

export const Skeleton: React.FC<SkeletonProps> = ({
  variant = 'rectangular',
  width,
  height,
  className,
  style,
  ...props
}) => {
  const variantStyles = {
    text: 'h-4 w-full rounded-md',
    circular: 'rounded-full shrink-0',
    rectangular: 'rounded-xl w-full',
  };

  return (
    <div
      className={twMerge(
        clsx(
          'animate-pulse bg-borderWarm-subtle/80',
          variantStyles[variant],
          className
        )
      )}
      style={{
        width,
        height,
        ...style,
      }}
      {...props}
    />
  );
};
