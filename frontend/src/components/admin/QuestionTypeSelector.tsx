import React from 'react';
import { ListFilter, Code2, Lock } from 'lucide-react';
import { QuestionType } from '../../types/question';

interface QuestionTypeSelectorProps {
  questionType: QuestionType;
  onChange: (type: QuestionType) => void;
  disabled?: boolean;
}

export const QuestionTypeSelector: React.FC<QuestionTypeSelectorProps> = ({
  questionType,
  onChange,
  disabled = false,
}) => {
  return (
    <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <label className="block text-xs font-bold text-slate-900 uppercase tracking-wider">
            Question Type
          </label>
          <p className="text-xs text-slate-500 mt-0.5">
            Select the question type to display required fields.
          </p>
        </div>
        {disabled && (
          <span className="flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 px-2.5 py-1 rounded-lg border border-amber-200 font-medium">
            <Lock className="w-3.5 h-3.5" /> Type Locked
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 max-w-md">
        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange('MCQ')}
          className={`flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-xs font-bold transition-all cursor-pointer ${
            questionType === 'MCQ'
              ? 'bg-purple-50 text-purple-700 border-purple-300 ring-2 ring-purple-500/20 shadow-xs'
              : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100 hover:text-slate-900 disabled:opacity-60'
          }`}
        >
          <ListFilter className="w-4 h-4 text-purple-600" />
          <span>MCQ (Single Choice)</span>
        </button>

        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange('CODING')}
          className={`flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-xs font-bold transition-all cursor-pointer ${
            questionType === 'CODING'
              ? 'bg-emerald-50 text-emerald-700 border-emerald-300 ring-2 ring-emerald-500/20 shadow-xs'
              : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100 hover:text-slate-900 disabled:opacity-60'
          }`}
        >
          <Code2 className="w-4 h-4 text-emerald-600" />
          <span>CODING (Algorithm)</span>
        </button>
      </div>
    </div>
  );
};
