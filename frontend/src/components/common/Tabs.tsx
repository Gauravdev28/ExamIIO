import React from 'react';

export interface TabItem<T extends string = string> {
  id: T;
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
  count?: number;
}

interface TabsProps<T extends string = string> {
  tabs: TabItem<T>[];
  activeTab: T;
  onChange: (tabId: T) => void;
  variant?: 'underline' | 'pills';
  className?: string;
}

export function Tabs<T extends string>({
  tabs,
  activeTab,
  onChange,
  variant = 'underline',
  className = '',
}: TabsProps<T>) {
  if (variant === 'pills') {
    return (
      <div className={`flex items-center gap-1.5 p-1 rounded-xl bg-canvas-subtle/90 border border-warm-200 ${className}`}>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onChange(tab.id)}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                isActive
                  ? 'bg-surface text-brand-700 shadow-warm-xs border border-warm-200 font-bold'
                  : 'text-navy-600 hover:text-navy-900 hover:bg-warm-100/70'
              }`}
            >
              {Icon && <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-brand-600' : 'text-navy-400'}`} />}
              <span>{tab.label}</span>
              {typeof tab.count === 'number' && (
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-mono ${
                  isActive ? 'bg-brand-50 text-brand-700' : 'bg-warm-200 text-navy-600'
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-2 border-b border-warm-200 pb-px overflow-x-auto ${className}`}>
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs sm:text-sm font-semibold border-b-2 transition-colors whitespace-nowrap ${
              isActive
                ? 'border-brand-600 text-brand-700 bg-brand-50/40'
                : 'border-transparent text-navy-600 hover:text-navy-900 hover:bg-warm-100/50'
            }`}
          >
            {Icon && <Icon className={`w-4 h-4 ${isActive ? 'text-brand-600' : 'text-navy-400'}`} />}
            <span>{tab.label}</span>
            {typeof tab.count === 'number' && (
              <span className={`text-xs px-2 py-0.5 rounded-full font-mono ${
                isActive ? 'bg-brand-100 text-brand-800' : 'bg-warm-100 text-navy-600'
              }`}>
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export default Tabs;
