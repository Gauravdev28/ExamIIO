import React, { useEffect, useState } from 'react';
import { getQuestionUsage, deleteDraftQuestion, QuestionUsageInfo } from '../../api/questions';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { AlertTriangle, Trash2, X, ShieldAlert, CheckCircle2 } from 'lucide-react';
import { QuestionItem } from '../../types/question';

interface DeleteQuestionModalProps {
  question: QuestionItem | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (action: 'deleted') => void;
}

export const DeleteQuestionModal: React.FC<DeleteQuestionModalProps> = ({
  question,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [usage, setUsage] = useState<QuestionUsageInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !question) {
      setUsage(null);
      setErrorMessage(null);
      return;
    }

    const loadUsage = async () => {
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const res = await getQuestionUsage(question.id);
        if (res.data) {
          setUsage(res.data);
        }
      } catch (err: any) {
        setErrorMessage(err.error?.message || err.message || 'Failed to check question dependencies.');
      } finally {
        setIsLoading(false);
      }
    };

    loadUsage();
  }, [isOpen, question]);

  if (!isOpen || !question) return null;

  const targetVer = question.latest_version;
  const isDeletable = usage?.is_deletable ?? false;

  const handleDeletePermanent = async () => {
    setIsProcessing(true);
    setErrorMessage(null);
    try {
      await deleteDraftQuestion(question.id);
      onSuccess('deleted');
      onClose();
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to delete draft question.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 animate-in fade-in duration-200"
    >
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-lg w-full overflow-hidden text-slate-900">
        {/* Header */}
        <div className="px-6 py-4 flex items-center justify-between border-b border-slate-200 bg-white text-slate-900">
          <div className="flex items-center gap-2.5">
            {isDeletable ? (
              <div className="w-8 h-8 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center border border-rose-200">
                <Trash2 className="h-4 w-4" />
              </div>
            ) : (
              <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center border border-amber-200">
                <ShieldAlert className="h-4 w-4" />
              </div>
            )}
            <div>
              <h3 id="delete-modal-title" className="text-base font-bold text-slate-900">
                {isDeletable ? 'Delete Question' : 'Question Deletion Protected'}
              </h3>
              <p className="text-xs text-slate-500">
                {isDeletable ? 'Permanent administrative removal' : 'Historical referential integrity check'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5">
          {/* Question Summary */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Question Details
              </span>
              <div className="flex items-center gap-1.5">
                <Badge variant="info">{question.question_type}</Badge>
                <span className="text-xs px-2 py-0.5 rounded bg-white border border-slate-200 font-bold font-mono">
                  v{targetVer?.version_number || 1}
                </span>
                <Badge variant={targetVer?.status === 'PUBLISHED' ? 'success' : 'warning'}>
                  {targetVer?.status || 'DRAFT'}
                </Badge>
              </div>
            </div>
            <p className="text-sm font-bold text-slate-900 line-clamp-2">
              {targetVer?.title || '(Untitled Question)'}
            </p>
          </div>

          {errorMessage && (
            <div className="p-3.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {isLoading ? (
            <div className="py-6 flex flex-col items-center justify-center space-y-2 text-slate-500 text-xs font-mono">
              <div className="w-6 h-6 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin" />
              <span>Inspecting historical dependencies...</span>
            </div>
          ) : usage && (
            <div className="space-y-4">
              {/* Dependency Breakdown */}
              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                <div className="p-2.5 rounded-lg bg-slate-100/70 border border-slate-200 flex justify-between items-center">
                  <span className="text-slate-600">Assessments:</span>
                  <strong className={usage.assessments_count > 0 ? 'text-rose-600' : 'text-slate-700'}>
                    {usage.assessments_count}
                  </strong>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-100/70 border border-slate-200 flex justify-between items-center">
                  <span className="text-slate-600">Snapshots:</span>
                  <strong className={usage.snapshots_count > 0 ? 'text-rose-600' : 'text-slate-700'}>
                    {usage.snapshots_count}
                  </strong>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-100/70 border border-slate-200 flex justify-between items-center">
                  <span className="text-slate-600">Candidate Answers:</span>
                  <strong className={usage.answers_count > 0 ? 'text-rose-600' : 'text-slate-700'}>
                    {usage.answers_count}
                  </strong>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-100/70 border border-slate-200 flex justify-between items-center">
                  <span className="text-slate-600">Legal Holds:</span>
                  <strong className={usage.legal_holds_count > 0 ? 'text-rose-600' : 'text-slate-700'}>
                    {usage.legal_holds_count}
                  </strong>
                </div>
              </div>

              {/* Status Explanation */}
              {isDeletable ? (
                <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-start gap-2.5">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-bold">Safe to Delete</p>
                    <p className="text-slate-600">
                      This question has never been attached to an assessment. Deleting it will permanently remove it from the question bank.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs space-y-2">
                  <div className="flex items-center gap-2 font-bold text-amber-800">
                    <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
                    <span>Hard Deletion Blocked</span>
                  </div>
                  <p className="text-slate-700 leading-relaxed font-medium">
                    {usage.reason_blocked || (usage.assessments_count > 0 ? `Cannot delete this question because it is used in ${usage.assessments_count} assessment(s).` : 'This question is used in examination dependencies.')}
                  </p>
                  {usage.assessments && usage.assessments.length > 0 && (
                    <div className="mt-3 space-y-1.5 pt-2 border-t border-amber-200/60">
                      <p className="font-semibold text-slate-800 text-[11px] uppercase tracking-wider">
                        Assessments Using This Question ({usage.assessments.length}):
                      </p>
                      <div className="max-h-36 overflow-y-auto space-y-1 pr-1">
                        {usage.assessments.map((a) => (
                          <div
                            key={a.id}
                            className="p-2 rounded-lg bg-white border border-slate-200 flex items-center justify-between text-xs"
                          >
                            <span className="font-medium text-slate-800 truncate mr-2" title={a.title}>
                              {a.title}
                            </span>
                            <Badge variant={a.status === 'PUBLISHED' ? 'success' : 'neutral'}>
                              {a.status}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {usage.reasons && usage.reasons.length > 0 && (!usage.assessments || usage.assessments.length === 0) && (
                    <ul className="list-disc list-inside space-y-0.5 text-slate-600 pl-1">
                      {usage.reasons.map((r, idx) => (
                        <li key={idx}>{r}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
            {isDeletable ? (
              <>
                <Button
                  variant="secondary"
                  size="md"
                  onClick={onClose}
                  disabled={isProcessing}
                >
                  Cancel
                </Button>
                <Button
                  variant="danger"
                  size="md"
                  onClick={handleDeletePermanent}
                  disabled={isProcessing || isLoading}
                  className="bg-rose-600 hover:bg-rose-700 text-white font-semibold"
                >
                  <Trash2 className="w-4 h-4 mr-1.5" />
                  {isProcessing ? 'Deleting...' : 'Delete Permanently'}
                </Button>
              </>
            ) : (
              <Button
                variant="secondary"
                size="md"
                onClick={onClose}
                disabled={isProcessing}
              >
                Close
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
