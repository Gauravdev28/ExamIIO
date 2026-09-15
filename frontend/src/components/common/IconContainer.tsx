import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export type IconColor = 'blue' | 'cyan' | 'violet' | 'emerald' | 'amber' | 'orange' | 'coral' | 'navy';

export type IconPropType = React.ReactNode | React.ComponentType<{ className?: string }>;

interface IconContainerProps {
  icon: IconPropType;
  color?: IconColor;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  shape?: 'rounded' | 'circle';
}

export const IconContainer: React.FC<IconContainerProps> = ({
  icon,
  color = 'blue',
  size = 'md',
  className,
  shape = 'rounded',
}) => {
  const colorStyles: Record<IconColor, string> = {
    blue: 'bg-brand-50 text-brand-600 border-brand-200/80',
    cyan: 'bg-cyan-50 text-cyan-600 border-cyan-200/80',
    violet: 'bg-purple-50 text-purple-600 border-purple-200/80',
    emerald: 'bg-emerald-50 text-emerald-600 border-emerald-200/80',
    amber: 'bg-amber-50 text-amber-600 border-amber-200/80',
    orange: 'bg-orange-50 text-orange-600 border-orange-200/80',
    coral: 'bg-rose-50 text-rose-600 border-rose-200/80',
    navy: 'bg-canvas-subtle text-navy-700 border-borderWarm',
  };

  const sizeStyles = {
    sm: 'w-8 h-8 p-1.5 text-xs',
    md: 'w-10 h-10 p-2 text-sm',
    lg: 'w-12 h-12 p-2.5 text-base',
    xl: 'w-14 h-14 p-3 text-lg',
  };

  const shapeStyles = {
    rounded: 'rounded-xl',
    circle: 'rounded-full',
  };

  const renderIcon = () => {
    if (React.isValidElement(icon)) return icon;
    if (typeof icon === 'function' || (typeof icon === 'object' && icon !== null)) {
      const IconComponent = icon as React.ComponentType<{ className?: string }>;
      return <IconComponent className="w-full h-full" />;
    }
    return icon;
  };

  return (
    <div
      className={twMerge(
        clsx(
          'inline-flex items-center justify-center border shrink-0 transition-transform duration-200 group-hover:scale-105',
          colorStyles[color],
          sizeStyles[size],
          shapeStyles[shape],
          className
        )
      )}
    >
      {renderIcon()}
    </div>
  );
};
