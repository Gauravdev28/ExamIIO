import React from 'react';
import { Difficulty } from '../../types/question';

interface CommonQuestionFieldsProps {
  questionId: string;
  onQuestionIdChange: (val: string) => void;
  title: string;
  onTitleChange: (val: string) => void;
  difficulty: Difficulty;
  onDifficultyChange: (val: Difficulty) => void;
  points: number;
  onPointsChange: (val: number) => void;
  negativeMarkingEnabled: boolean;
  onNegativeMarkingChange: (enabled: boolean) => void;
  negativePoints: number;
  onNegativePointsChange: (val: number) => void;
  statement: string;
  onStatementChange: (val: string) => void;
  instructions: string;
  onInstructionsChange: (val: string) => void;
  disabled?: boolean;
  isEditing?: boolean;
}

export const CommonQuestionFields: React.FC<CommonQuestionFieldsProps> = ({
  questionId,
  onQuestionIdChange,
  title,
  onTitleChange,
  difficulty,
  onDifficultyChange,
  points,
  onPointsChange,
  negativeMarkingEnabled,
  onNegativeMarkingChange,
  negativePoints,
  onNegativePointsChange,
  statement,
  onStatementChange,
  instructions,
  onInstructionsChange,
  disabled = false,
  isEditing = false,
}) => {
  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-5 text-slate-900">
      <div className="border-b border-slate-100 pb-3">
        <h3 className="text-sm font-bold text-slate-900">Question Information</h3>
        <p className="text-xs text-slate-500 mt-0.5">
          General metadata and problem statement for this question.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Question ID */}
        <div className="space-y-1.5">
          <label className="block text-xs font-semibold text-slate-700">
            Question ID
          </label>
          <input
            type="text"
            disabled={disabled || isEditing}
            value={questionId}
            onChange={(e) => onQuestionIdChange(e.target.value)}
            placeholder="e.g. Q-101"
            className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 bg-white text-slate-900 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:bg-slate-50 disabled:text-slate-500 font-mono"
          />
        </div>

        {/* Title */}
        <div className="space-y-1.5 md:col-span-2">
          <label className="block text-xs font-semibold text-slate-700">
            Question Title <span className="text-rose-500">*</span>
          </label>
          <input
            type="text"
            disabled={disabled}
            value={title}
            onChange={(e) => onTitleChange(e.target.value)}
            placeholder="Descriptive title"
            className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 bg-white text-slate-900 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:bg-slate-50"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Difficulty */}
        <div className="space-y-1.5">
          <label className="block text-xs font-semibold text-slate-700">Difficulty</label>
          <select
            disabled={disabled}
            value={difficulty}
            onChange={(e) => onDifficultyChange(e.target.value as Difficulty)}
            className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 bg-white text-slate-900 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:bg-slate-50 font-medium"
          >
            <option value="EASY">Easy</option>
            <option value="MEDIUM">Medium</option>
            <option value="HARD">Hard</option>
          </select>
        </div>

        {/* Total Points */}
        <div className="space-y-1.5">
          <label className="block text-xs font-semibold text-slate-700">
            Total Points <span className="text-rose-500">*</span>
          </label>
          <input
            type="number"
            min={1}
            disabled={disabled}
            value={points}
            onChange={(e) => onPointsChange(Math.max(1, parseInt(e.target.value, 10) || 1))}
            className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 bg-white text-slate-900 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:bg-slate-50 font-mono"
          />
        </div>

        {/* Negative Marking */}
        <div className="space-y-1.5">
          <label className="block text-xs font-semibold text-slate-700">Negative Marking</label>
          <div className="flex items-center gap-3 pt-1">
            <label className="inline-flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
              <input
                type="checkbox"
                disabled={disabled}
                checked={negativeMarkingEnabled}
                onChange={(e) => onNegativeMarkingChange(e.target.checked)}
                className="w-4 h-4 rounded text-emerald-600 focus:ring-emerald-500 border-slate-300"
              />
              <span>Enable Penalty</span>
            </label>
            {negativeMarkingEnabled && (
              <input
                type="number"
                min={0}
                max={points}
                disabled={disabled}
                value={negativePoints}
                onChange={(e) => onNegativePointsChange(Math.max(0, parseInt(e.target.value, 10) || 0))}
                placeholder="Penalty"
                className="w-20 px-2 py-1 text-xs rounded-lg border border-slate-300 bg-white text-slate-900 focus:ring-2 focus:ring-emerald-500 font-mono"
              />
            )}
          </div>
        </div>
      </div>

      {/* Problem Statement */}
      <div className="space-y-1.5">
        <label className="block text-xs font-semibold text-slate-700">
          Problem Statement <span className="text-rose-500">*</span>
        </label>
        <textarea
          rows={5}
          disabled={disabled}
          value={statement}
          onChange={(e) => onStatementChange(e.target.value)}
          placeholder="Detailed problem statement..."
          className="w-full px-3 py-2.5 text-xs rounded-xl border border-slate-300 bg-white text-slate-900 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:bg-slate-50 font-sans leading-relaxed"
        />
      </div>

      {/* Instructions (Optional) */}
      <div className="space-y-1.5">
        <label className="block text-xs font-semibold text-slate-700">
          Candidate Instructions <span className="text-slate-400 font-normal">(optional)</span>
        </label>
        <textarea
          rows={2}
          disabled={disabled}
          value={instructions}
          onChange={(e) => onInstructionsChange(e.target.value)}
          placeholder="Special notes or instructions shown to candidates..."
          className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 bg-white text-slate-900 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:bg-slate-50 font-sans"
        />
      </div>
    </div>
  );
};
