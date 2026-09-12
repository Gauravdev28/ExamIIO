import React, { useState } from 'react';
import Editor from '@monaco-editor/react';
import { CodingLanguage } from '../../types/question';

interface CodingConfigEditorProps {
  constraints: string;
  onConstraintsChange: (val: string) => void;
  allowedLanguages: CodingLanguage[];
  onAllowedLanguagesChange: (langs: CodingLanguage[]) => void;
  starterCodes: Record<string, string>;
  onStarterCodesChange: (codes: Record<string, string>) => void;
  timeLimitMs: number;
  onTimeLimitChange: (val: number) => void;
  memoryLimitMb: number;
  onMemoryLimitChange: (val: number) => void;
  disabled?: boolean;
}

const DEFAULT_STARTER_CODES: Record<CodingLanguage, string> = {
  PYTHON: 'def solve():\n    pass\n',
  CPP: '#include <bits/stdc++.h>\n',
  JAVA: 'import java.io.*;\n',
  C: '#include <stdio.h>\n',
};

const MONACO_LANG_MAP: Record<CodingLanguage, string> = {
  PYTHON: 'python',
  CPP: 'cpp',
  JAVA: 'java',
  C: 'c',
};

export const CodingConfigEditor: React.FC<CodingConfigEditorProps> = ({
  constraints,
  onConstraintsChange,
  allowedLanguages,
  onAllowedLanguagesChange,
  starterCodes,
  onStarterCodesChange,
  timeLimitMs,
  onTimeLimitChange,
  memoryLimitMb,
  onMemoryLimitChange,
  disabled = false,
}) => {
  const [activeLang, setActiveLang] = useState<CodingLanguage>(
    allowedLanguages.length > 0 ? allowedLanguages[0] : 'PYTHON'
  );

  const handleToggleLanguage = (lang: CodingLanguage) => {
    if (allowedLanguages.includes(lang)) {
      const updated = allowedLanguages.filter((l) => l !== lang);
      onAllowedLanguagesChange(updated);
      if (activeLang === lang) {
        if (updated.length > 0) {
          setActiveLang(updated[0]);
        }
      }
    } else {
      const updated = [...allowedLanguages, lang];
      onAllowedLanguagesChange(updated);
      // Ensure default starter code is set if empty
      if (!starterCodes[lang]) {
        onStarterCodesChange({
          ...starterCodes,
          [lang]: DEFAULT_STARTER_CODES[lang],
        });
      }
      if (allowedLanguages.length === 0) {
        setActiveLang(lang);
      }
    }
  };

  const handleStarterCodeChange = (code: string | undefined) => {
    onStarterCodesChange({
      ...starterCodes,
      [activeLang]: code || '',
    });
  };

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-6 text-slate-900">
      <div className="border-b border-slate-100 pb-3">
        <h3 className="text-sm font-bold text-slate-900">Coding Configuration</h3>
        <p className="text-xs text-slate-500 mt-0.5">
          Configure constraints, enabled programming runtimes, starter code, and execution resource limits.
        </p>
      </div>

      {/* Constraints */}
      <div className="space-y-1.5">
        <label className="block text-xs font-semibold text-slate-700">
          Constraints <span className="text-slate-400 font-normal">(one per line, e.g. 1 &le; N &le; 10^5)</span>
        </label>
        <textarea
          rows={3}
          disabled={disabled}
          value={constraints}
          onChange={(e) => onConstraintsChange(e.target.value)}
          placeholder="1 <= N <= 10^5&#10;Time Complexity: O(N)"
          className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 bg-white text-slate-900 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:bg-slate-50 font-mono"
        />
      </div>

      {/* Enabled Languages Checkboxes */}
      <div className="space-y-2">
        <label className="block text-xs font-semibold text-slate-700">
          Enabled Languages <span className="text-rose-500">*</span>
        </label>
        <div className="flex flex-wrap gap-4">
          {(['PYTHON', 'CPP', 'JAVA', 'C'] as CodingLanguage[]).map((lang) => {
            const isChecked = allowedLanguages.includes(lang);
            return (
              <label
                key={lang}
                className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl border text-xs font-semibold transition-all cursor-pointer ${
                  isChecked
                    ? 'bg-emerald-50/60 text-emerald-800 border-emerald-300 ring-1 ring-emerald-500/20'
                    : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
                }`}
              >
                <input
                  type="checkbox"
                  disabled={disabled}
                  checked={isChecked}
                  onChange={() => handleToggleLanguage(lang)}
                  className="w-4 h-4 rounded text-emerald-600 focus:ring-emerald-500 border-slate-300"
                />
                <span>{lang === 'C' ? 'C' : lang === 'CPP' ? 'C++' : lang === 'JAVA' ? 'Java' : 'Python'}</span>
              </label>
            );
          })}
        </div>
        {allowedLanguages.length === 0 && (
          <p className="text-xs text-rose-600 font-semibold mt-1">
            At least one programming language must be enabled.
          </p>
        )}
      </div>

      {/* Execution Limits */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <label className="block text-xs font-semibold text-slate-700">
            Time Limit (ms) <span className="text-slate-400 font-normal">(100ms - 5000ms)</span>
          </label>
          <input
            type="number"
            min={100}
            max={5000}
            disabled={disabled}
            value={timeLimitMs}
            onChange={(e) => onTimeLimitChange(Math.min(5000, Math.max(100, parseInt(e.target.value, 10) || 2000)))}
            className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 bg-white text-slate-900 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:bg-slate-50 font-mono"
          />
        </div>

        <div className="space-y-1.5">
          <label className="block text-xs font-semibold text-slate-700">
            Memory Limit (MB) <span className="text-slate-400 font-normal">(16MB - 256MB)</span>
          </label>
          <input
            type="number"
            min={16}
            max={256}
            disabled={disabled}
            value={memoryLimitMb}
            onChange={(e) => onMemoryLimitChange(Math.min(256, Math.max(16, parseInt(e.target.value, 10) || 256)))}
            className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 bg-white text-slate-900 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:bg-slate-50 font-mono"
          />
        </div>
      </div>

      {/* Starter Code Workspace */}
      <div className="space-y-2 pt-2 border-t border-slate-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <label className="block text-xs font-semibold text-slate-700">
              Starter Code Language:
            </label>
            {/* Language Selector Dropdown (No Tab Bar) */}
            <select
              value={allowedLanguages.length === 0 ? '' : activeLang}
              disabled={disabled || allowedLanguages.length === 0}
              onChange={(e) => {
                if (e.target.value) {
                  setActiveLang(e.target.value as CodingLanguage);
                }
              }}
              className="px-3 py-1.5 text-xs rounded-lg border border-slate-300 bg-white text-slate-900 font-semibold focus:ring-2 focus:ring-emerald-500 focus:outline-none cursor-pointer disabled:bg-slate-100 disabled:text-slate-400"
            >
              {allowedLanguages.length === 0 ? (
                <option disabled value="">
                  No languages enabled
                </option>
              ) : (
                allowedLanguages.map((lang) => (
                  <option key={lang} value={lang}>
                    {lang === 'C' ? 'C' : lang === 'CPP' ? 'C++' : lang === 'JAVA' ? 'Java' : 'Python'}
                  </option>
                ))
              )}
            </select>
          </div>
          <span className="text-[11px] text-slate-400 font-mono">
            {allowedLanguages.length === 0 ? 'No language selected' : `Monaco Editor (${activeLang})`}
          </span>
        </div>

        {allowedLanguages.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-xs text-slate-500">
            Please enable at least one programming language above to edit starter code.
          </div>
        ) : (
          <div className="rounded-xl border border-slate-300 overflow-hidden shadow-2xs">
            <Editor
              height="260px"
              language={MONACO_LANG_MAP[activeLang] || 'python'}
              theme="vs-light"
              value={starterCodes[activeLang] ?? DEFAULT_STARTER_CODES[activeLang]}
              onChange={handleStarterCodeChange}
              options={{
                minimap: { enabled: false },
                fontSize: 12,
                scrollBeyondLastLine: false,
                readOnly: disabled,
                automaticLayout: true,
                tabSize: 4,
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
};
