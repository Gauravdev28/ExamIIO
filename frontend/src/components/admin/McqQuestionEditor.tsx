import React from 'react';
import { Plus, Trash2, CheckCircle2 } from 'lucide-react';

export interface McqOptionItem {
  id: string;
  text: string;
  is_correct: boolean;
}

interface McqQuestionEditorProps {
  options: McqOptionItem[];
  onChange: (options: McqOptionItem[]) => void;
  disabled?: boolean;
}

export const McqQuestionEditor: React.FC<McqQuestionEditorProps> = ({
  options,
  onChange,
  disabled = false,
}) => {
  const handleOptionTextChange = (index: number, text: string) => {
    const updated = options.map((opt, i) => (i === index ? { ...opt, text } : opt));
    onChange(updated);
  };

  const handleSelectCorrect = (index: number) => {
    const updated = options.map((opt, i) => ({
      ...opt,
      is_correct: i === index,
    }));
    onChange(updated);
  };

  const handleAddOption = () => {
    const nextKey = String.fromCharCode(65 + options.length);
    onChange([...options, { id: nextKey, text: '', is_correct: false }]);
  };

  const handleRemoveOption = (index: number) => {
    if (options.length <= 2) {
      alert('A minimum of 2 options is required.');
      return;
    }
    const wasCorrect = options[index].is_correct;
    const remaining = options.filter((_, i) => i !== index);
    // Re-key sequentially A, B, C...
    const rekeyed = remaining.map((opt, i) => ({
      ...opt,
      id: String.fromCharCode(65 + i),
      is_correct: wasCorrect && i === 0 ? true : opt.is_correct,
    }));
    // If the correct option was removed, set first option as correct
    if (wasCorrect && !rekeyed.some((o) => o.is_correct) && rekeyed.length > 0) {
      rekeyed[0].is_correct = true;
    }
    onChange(rekeyed);
  };

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4 text-slate-900">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <div>
          <h3 className="text-sm font-bold text-slate-900">MCQ Options</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Configure choices and designate exactly one correct answer. Minimum 2 options required.
          </p>
        </div>
        {!disabled && (
          <button
            type="button"
            onClick={handleAddOption}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200 transition-colors cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Option</span>
          </button>
        )}
      </div>

      <div className="space-y-3">
        {options.map((opt, idx) => (
          <div
            key={opt.id}
            className={`flex items-center gap-3 p-3 rounded-xl border transition-all ${
              opt.is_correct
                ? 'bg-purple-50/50 border-purple-300 ring-1 ring-purple-400/30'
                : 'bg-white border-slate-200 hover:border-slate-300'
            }`}
          >
            {/* Option Key Badge */}
            <span className="w-7 h-7 flex items-center justify-center rounded-lg bg-slate-100 text-slate-700 font-mono text-xs font-bold shrink-0">
              {opt.id}
            </span>

            {/* Option Text Input */}
            <input
              type="text"
              disabled={disabled}
              value={opt.text}
              onChange={(e) => handleOptionTextChange(idx, e.target.value)}
              placeholder={`Option ${opt.id} text...`}
              className="flex-1 px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white text-slate-900 focus:ring-2 focus:ring-purple-500 focus:outline-none disabled:bg-slate-50"
            />

            {/* Radio / Correct Answer Selector */}
            <button
              type="button"
              disabled={disabled}
              onClick={() => handleSelectCorrect(idx)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                opt.is_correct
                  ? 'bg-purple-600 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{opt.is_correct ? 'Correct' : 'Mark Correct'}</span>
            </button>

            {/* Delete Option Button */}
            {!disabled && options.length > 2 && (
              <button
                type="button"
                onClick={() => handleRemoveOption(idx)}
                className="p-1.5 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-rose-50 transition-colors cursor-pointer"
                title="Remove option"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
