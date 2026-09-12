import React from 'react';
import { Eye, Save, Send, ArrowLeft, Loader2, Lock } from 'lucide-react';

interface QuestionActionsProps {
  status?: string;
  isPublished?: boolean;
  isSaving?: boolean;
  isPublishing?: boolean;
  canPublish?: boolean;
  onSaveDraft: () => void;
  onPublish: () => void;
  onPreview: () => void;
  onBack: () => void;
}

export const QuestionActions: React.FC<QuestionActionsProps> = ({
  status = 'DRAFT',
  isPublished = false,
  isSaving = false,
  isPublishing = false,
  canPublish = true,
  onSaveDraft,
  onPublish,
  onPreview,
  onBack,
}) => {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-8 flex flex-wrap items-center justify-between gap-4 sticky bottom-4 z-20">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
        >
          <ArrowLeft className="w-4 h-4" />
          Question Bank
        </button>

        <div className="flex items-center gap-2 pl-2 border-l border-slate-200">
          <span className="text-xs text-slate-500 font-medium">Status:</span>
          <span
            className={`text-xs px-2.5 py-0.5 font-bold rounded-full ${
              isPublished
                ? 'bg-emerald-100 text-emerald-800'
                : status === 'DRAFT_READY' || status === 'DRAFT_DATA_READY'
                ? 'bg-blue-100 text-blue-800'
                : 'bg-amber-100 text-amber-800'
            }`}
          >
            {status}
          </span>
          {isPublished && (
            <span className="flex items-center gap-1 text-[11px] text-slate-500 font-medium ml-1">
              <Lock className="w-3.5 h-3.5 text-slate-400" />
              Published (Immutable)
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2.5">
        <button
          type="button"
          onClick={onPreview}
          className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg shadow-sm transition"
        >
          <Eye className="w-4 h-4 text-slate-500" />
          Candidate Preview
        </button>

        {!isPublished && (
          <>
            <button
              type="button"
              onClick={onSaveDraft}
              disabled={isSaving || isPublishing}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition disabled:opacity-50"
            >
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin text-slate-600" />
              ) : (
                <Save className="w-4 h-4 text-slate-600" />
              )}
              Save Draft
            </button>

            <button
              type="button"
              onClick={onPublish}
              disabled={isSaving || isPublishing || !canPublish}
              title={
                !canPublish
                  ? 'All 11 DATA checks must pass before publishing'
                  : 'Publish this question version'
              }
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isPublishing ? (
                <Loader2 className="w-4 h-4 animate-spin text-white" />
              ) : (
                <Send className="w-4 h-4 text-white" />
              )}
              Publish Question
            </button>
          </>
        )}
      </div>
    </div>
  );
};
