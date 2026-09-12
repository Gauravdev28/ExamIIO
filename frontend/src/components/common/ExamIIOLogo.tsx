import React from 'react';
import { clsx } from 'clsx';

export interface ExamIIOLogoProps {
  variant?: 'full' | 'icon';
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  showSubtitle?: boolean;
}

export const ExamIIOLogo: React.FC<ExamIIOLogoProps> = ({
  variant = 'full',
  size = 'md',
  className,
  showSubtitle = false, // Subtitle explicitly disabled for ExamIIO
}) => {
  const config = {
    sm: { w: 26, h: 26, rx: 6, text: 'text-base' },
    md: { w: 32, h: 32, rx: 7, text: 'text-lg' },
    lg: { w: 40, h: 40, rx: 9, text: 'text-2xl' },
    xl: { w: 52, h: 52, rx: 12, text: 'text-3xl' },
  }[size];

  const iconSvg = (
    <svg
      width={config.w}
      height={config.h}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="shrink-0 transition-transform duration-150 group-hover:scale-105"
      aria-label="ExamIIO logo mark"
    >
      {/* Precision container in institutional professional blue */}
      <rect width="32" height="32" rx={config.rx} fill="#2878D8" />

      {/* Enclosing verification ring 'O' */}
      <circle cx="16" cy="16" r="8" stroke="#FAF9F6" strokeWidth="2.2" strokeLinecap="round" />

      {/* Twin assessment pillars 'II' */}
      <rect x="12.2" y="11" width="2.2" height="10" rx="1.1" fill="#FAF9F6" />
      <rect x="17.6" y="11" width="2.2" height="10" rx="1.1" fill="#FAF9F6" />

      {/* Central precision verification datum node in restrained teal */}
      <circle cx="16" cy="16" r="1.3" fill="#2FA878" />

      {/* Precision alignment ticks at perimeter */}
      <line x1="4.5" y1="16" x2="6.5" y2="16" stroke="#FAF9F6" strokeWidth="1.2" strokeLinecap="round" strokeOpacity="0.8" />
      <line x1="25.5" y1="16" x2="27.5" y2="16" stroke="#FAF9F6" strokeWidth="1.2" strokeLinecap="round" strokeOpacity="0.8" />
    </svg>
  );

  if (variant === 'icon') {
    return <div className={clsx('inline-flex items-center', className)}>{iconSvg}</div>;
  }

  return (
    <div className={clsx('inline-flex items-center gap-2.5 select-none group', className)}>
      {iconSvg}
      <div className="flex flex-col text-left">
        <span className={clsx('font-black tracking-tight text-[#243247] leading-none font-sans', config.text)}>
          Exam<span className="text-[#2878D8]">IIO</span>
        </span>
        {showSubtitle && (
          <span className="text-[10px] uppercase tracking-widest text-[#5E6B7D] font-semibold mt-0.5 leading-tight">
            Assessment Platform
          </span>
        )}
      </div>
    </div>
  );
};

export default ExamIIOLogo;
