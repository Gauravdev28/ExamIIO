import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import {
  FileSpreadsheet,
  Download,
  UploadCloud,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  X,
  FileText,
  RefreshCw,
  Code2,
  ListFilter,
} from 'lucide-react';
import {
  downloadImportTemplate,
  previewSpreadsheetImport,
  confirmSpreadsheetImport,
} from '../../api/questions';
import {
  QuestionImportPreview,
  PreviewQuestion,
  ImportValidationError,
  ImportWarning,
} from '../../types/question';

interface ImportQuestionsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const ImportQuestionsModal: React.FC<ImportQuestionsModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  // 1. State declarations
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [previewData, setPreviewData] = useState<QuestionImportPreview | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successInfo, setSuccessInfo] = useState<{ count: number; message: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 2. Stable callbacks & handlers
  const handleReset = useCallback(() => {
    setSelectedFile(null);
    setPreviewData(null);
    setErrorMessage(null);
    setSuccessInfo(null);
    setIsLoading(false);
    setIsImporting(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  const handleClose = useCallback(() => {
    handleReset();
    onClose();
  }, [handleReset, onClose]);

  // 3. Effects that depend on those callbacks
  useEffect(() => {
    if (!isOpen) {
      handleReset();
    }
  }, [isOpen, handleReset]);

  // 4. Action Handlers
  const handleDownloadTemplate = async () => {
    try {
      const blob = await downloadImportTemplate('xlsx');
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'CODEGUARD_Question_Import_Template_v1.xlsx';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      setErrorMessage('Failed to download official template. Please try again.');
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext !== 'xlsx') {
      setErrorMessage('Please upload the official .xlsx template workbook (CODEGUARD_Question_Import_Template_v1.xlsx).');
      setSelectedFile(null);
      setPreviewData(null);
      return;
    }

    setSelectedFile(file);
    setErrorMessage(null);
    setSuccessInfo(null);
    setPreviewData(null);
    setIsLoading(true);

    try {
      const res = await previewSpreadsheetImport(file);
      if (res && res.data) {
        if (!Array.isArray(res.data.questions)) {
          setErrorMessage('Invalid import preview response from server. Expected questions array.');
          setPreviewData(null);
        } else {
          // Verify that questions do not have missing required canonical fields
          const hasInvalidQuestion = res.data.questions.some(
            (q: any) =>
              !q ||
              !q.question_id ||
              !q.title ||
              !q.type ||
              q.points === undefined ||
              q.points === null ||
              !q.difficulty
          );
          if (hasInvalidQuestion) {
            setErrorMessage(
              'Invalid import preview response: workbook contains questions with missing canonical fields (ID, title, type, difficulty, or points).'
            );
            setPreviewData(null);
          } else {
            setPreviewData(res.data);
          }
        }
      } else {
        setErrorMessage('Unable to analyze this workbook. Server returned an empty response.');
        setPreviewData(null);
      }
    } catch (err: any) {
      const msg = err.error?.message || err.message || 'Unable to analyze this workbook. Please verify the spreadsheet format and try again.';
      setErrorMessage(msg);
      setPreviewData(null);
    } finally {
      setIsLoading(false);
    }
  };

  // 5. Derived values and memoized computations
  const canonicalQuestions: PreviewQuestion[] = useMemo(() => {
    if (!previewData || !Array.isArray(previewData.questions)) return [];
    return previewData.questions;
  }, [previewData]);

  const detectedCount = canonicalQuestions.length;
  const mcqCount = canonicalQuestions.filter((q) => q.type === 'MCQ').length;
  const codingCount = canonicalQuestions.filter((q) => q.type === 'CODING').length;
  const errorsList: ImportValidationError[] = previewData?.errors ?? [];
  const warningsList: ImportWarning[] = previewData?.warnings ?? [];
  const isValidImport = Boolean(
    previewData?.is_valid &&
    detectedCount > 0 &&
    errorsList.length === 0 &&
    canonicalQuestions.length === detectedCount
  );

  const handleConfirmImport = async () => {
    if (!isValidImport || canonicalQuestions.length === 0) return;

    setIsImporting(true);
    setErrorMessage(null);

    try {
      const res = await confirmSpreadsheetImport(canonicalQuestions);
      if (res && res.data) {
        setSuccessInfo({
          count: res.data.created_count,
          message: res.data.message || `Successfully imported ${res.data.created_count} question(s) as Draft.`,
        });
        onSuccess();
      }
    } catch (err: any) {
      const details = err.error?.details || err.error?.message || err.message;
      setErrorMessage(typeof details === 'object' ? JSON.stringify(details) : String(details));
    } finally {
      setIsImporting(false);
    }
  };

  // 6. Conditional exit (placed after all hooks to adhere to React Rules of Hooks)
  if (!isOpen) return null;

  // 7. Render UI
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="import-questions-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4"
    >
      <div className="bg-white rounded-3xl shadow-2xl border border-slate-200 max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden text-slate-900">
        {/* Header */}
        <div className="px-6 py-5 bg-white border-b border-slate-200 text-slate-900 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-purple-50 text-purple-700 flex items-center justify-center border border-purple-200">
              <FileSpreadsheet className="w-4 h-4" />
            </div>
            <div>
              <h2 id="import-questions-modal-title" className="text-base font-bold text-slate-900">
                Import Questions
              </h2>
              <p className="text-xs text-slate-500">
                Canonical Excel Template v1 (MCQ & Coding) &bull; All-or-Nothing Import
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            aria-label="Close import dialog"
            className="text-slate-400 hover:text-slate-600 p-2 rounded-xl hover:bg-slate-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5 text-slate-900">
          {/* Step 1: Download Template */}
          <div className="p-4 rounded-2xl bg-purple-50/70 border border-purple-200/80 flex items-center justify-between gap-4">
            <div className="space-y-1">
              <h3 className="text-xs font-bold text-purple-950 uppercase tracking-wider">
                Official Canonical Template
              </h3>
              <p className="text-xs text-purple-800">
                Use <code className="px-1.5 py-0.5 rounded bg-purple-100 text-purple-900 font-semibold font-mono text-[11px]">CODEGUARD_Question_Import_Template_v1.xlsx</code> with 6 sheets (README, Questions, Options, Coding, TestCases, COLUMN_GUIDE).
              </p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleDownloadTemplate}
              className="border-purple-300 text-purple-700 hover:bg-purple-100/80 font-semibold whitespace-nowrap shrink-0"
              aria-label="Download Official Excel Template v1"
            >
              <Download className="w-4 h-4 mr-1.5" />
              Download Template
            </Button>
          </div>

          {/* Success Result Card */}
          {successInfo && (
            <div className="p-5 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-900 space-y-3">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="w-6 h-6 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-sm font-bold text-emerald-950">{successInfo.message}</h3>
                  <p className="text-xs text-emerald-800 mt-1">
                    <strong>{successInfo.count} question(s)</strong> have been created as <strong>DRAFT</strong>.
                    You can now inspect their health, review test cases, and publish them to make them eligible for examinations.
                  </p>
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2 border-t border-emerald-200/60">
                <Button variant="secondary" size="sm" onClick={handleReset}>
                  Import Another Workbook
                </Button>
                <Button variant="primary" size="sm" onClick={handleClose}>
                  View Question Bank
                </Button>
              </div>
            </div>
          )}

          {/* Error Message */}
          {errorMessage && (
            <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 flex items-start gap-3 text-xs">
              <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold text-rose-900">Import Validation Issue</p>
                <p className="mt-0.5 text-rose-700">{errorMessage}</p>
              </div>
            </div>
          )}

          {/* Step 2: Upload Zone or Analyzing Loader */}
          {!successInfo && (
            <>
              {isLoading ? (
                <div className="p-10 rounded-2xl bg-slate-50 border border-slate-200 flex flex-col items-center justify-center gap-3 text-center">
                  <RefreshCw className="w-8 h-8 text-purple-600 animate-spin" />
                  <div>
                    <h4 className="text-sm font-bold text-slate-900">Analyzing workbook...</h4>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Validating 6-sheet structure, MCQ options, and coding test cases...
                    </p>
                  </div>
                </div>
              ) : !previewData ? (
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-slate-300 hover:border-purple-500 hover:bg-purple-50/30 rounded-2xl p-8 text-center cursor-pointer transition-all flex flex-col items-center justify-center gap-3"
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".xlsx"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  <div className="w-12 h-12 rounded-2xl bg-purple-50 text-purple-600 flex items-center justify-center border border-purple-200 shadow-xs">
                    <UploadCloud className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-slate-900">
                      Upload your Excel workbook
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Click to browse or drag & drop <span className="font-mono font-semibold">.xlsx</span> files
                    </p>
                  </div>
                  <span className="px-3 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-700 font-semibold text-xs shadow-xs hover:bg-slate-50 transition">
                    Choose Excel File
                  </span>
                  <p className="text-[11px] text-slate-400">
                    Supported format: <span className="font-mono font-medium">.xlsx</span> (Canonical 6-sheet schema)
                  </p>
                </div>
              ) : (
                /* Step 3: Preview and Diagnostics */
                <div className="space-y-4">
                  {/* Workbook file info */}
                  <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-purple-600 shrink-0" />
                      <span className="font-semibold text-slate-900 font-mono">
                        {selectedFile?.name}
                      </span>
                      <span className="text-slate-500">
                        ({((selectedFile?.size || 0) / 1024).toFixed(1)} KB)
                      </span>
                    </div>
                    <Button variant="ghost" size="sm" onClick={handleReset}>
                      Choose Different File
                    </Button>
                  </div>

                  {/* Summary Metric Badges */}
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-center">
                      <div className="text-lg font-bold text-slate-900">
                        {detectedCount}
                      </div>
                      <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Detected</div>
                    </div>
                    <div className="p-3 rounded-xl bg-purple-50 border border-purple-200 text-center">
                      <div className="text-lg font-bold text-purple-700">
                        {mcqCount}
                      </div>
                      <div className="text-[10px] font-semibold text-purple-700 uppercase tracking-wider">MCQ</div>
                    </div>
                    <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-center">
                      <div className="text-lg font-bold text-emerald-700">
                        {codingCount}
                      </div>
                      <div className="text-[10px] font-semibold text-emerald-700 uppercase tracking-wider">Coding</div>
                    </div>
                    <div className={`p-3 rounded-xl text-center border ${
                      errorsList.length > 0
                        ? 'bg-rose-50 border-rose-200 text-rose-700'
                        : 'bg-emerald-50 border-emerald-200 text-emerald-700'
                    }`}>
                      <div className="text-lg font-bold">
                        {errorsList.length}
                      </div>
                      <div className="text-[10px] font-semibold uppercase tracking-wider">Errors</div>
                    </div>
                    <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-center text-amber-700">
                      <div className="text-lg font-bold">
                        {warningsList.length}
                      </div>
                      <div className="text-[10px] font-semibold uppercase tracking-wider">Warnings</div>
                    </div>
                  </div>

                  {/* Error Breakdown Card */}
                  {errorsList.length > 0 && (
                    <div className="p-4 rounded-xl bg-rose-50/80 border border-rose-200 space-y-2">
                      <div className="flex items-center gap-2 text-rose-800 font-bold text-xs">
                        <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                        <span>Validation Errors (Import Blocked — All-or-Nothing Enforced):</span>
                      </div>
                      <ul className="space-y-1.5 text-xs text-rose-700 max-h-44 overflow-y-auto pl-6 list-disc">
                        {errorsList.map((err, idx) => (
                          <li key={idx}>
                            <span className="font-mono font-bold">[{err.question_id || 'GLOBAL'}]:</span> {err.message}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Warnings Breakdown */}
                  {warningsList.length > 0 && (
                    <div className="p-3 rounded-xl bg-amber-50/80 border border-amber-200 space-y-1.5">
                      <div className="flex items-center gap-2 text-amber-800 font-bold text-xs">
                        <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                        <span>Warnings:</span>
                      </div>
                      <ul className="space-y-1 text-xs text-amber-700 max-h-32 overflow-y-auto pl-6 list-disc">
                        {warningsList.map((w, idx) => (
                          <li key={idx}>
                            <span className="font-mono font-bold">[{w.question_id || 'INFO'}]:</span> {w.message}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Question Roster Preview */}
                  {canonicalQuestions.length > 0 && (
                    <div className="border border-slate-200 rounded-2xl overflow-hidden">
                      <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-700">
                        Questions Detected ({detectedCount})
                      </div>
                      <div className="divide-y divide-slate-100 max-h-56 overflow-y-auto text-xs">
                        {canonicalQuestions.map((q, i) => (
                          <div key={q.question_id || i} className="p-3.5 flex items-center justify-between hover:bg-slate-50/80 transition-colors">
                            <div className="space-y-0.5 min-w-0 pr-4">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-[11px] font-bold px-1.5 py-0.5 bg-slate-100 rounded text-slate-700 shrink-0 border border-slate-200">
                                  {q.question_id}
                                </span>
                                <span className="font-semibold text-slate-900 truncate">
                                  {q.title}
                                </span>
                              </div>
                              {q.statement && (
                                <p className="text-[11px] text-slate-500 line-clamp-1">{q.statement}</p>
                              )}
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-600 border border-slate-200">
                                {q.difficulty}
                              </span>
                              <Badge variant={q.type === 'CODING' ? 'success' : 'purple'} size="sm">
                                {q.type === 'CODING' ? (
                                  <span className="flex items-center gap-1">
                                    <Code2 className="w-3 h-3" /> Coding
                                  </span>
                                ) : (
                                  <span className="flex items-center gap-1">
                                    <ListFilter className="w-3 h-3" /> MCQ
                                  </span>
                                )}
                              </Badge>
                              <span className="font-bold text-emerald-700 text-xs whitespace-nowrap">{q.points} pts</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
          <Button variant="ghost" size="sm" onClick={handleClose}>
            {successInfo ? 'Close' : 'Cancel'}
          </Button>

          {!successInfo && previewData && (
            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                size="md"
                disabled={!isValidImport || isImporting}
                onClick={handleConfirmImport}
                aria-label="Confirm Import Questions as Draft"
              >
                {isImporting ? (
                  <span className="flex items-center gap-2">
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Importing...
                  </span>
                ) : (
                  <span>Import {detectedCount} Questions as Draft</span>
                )}
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
