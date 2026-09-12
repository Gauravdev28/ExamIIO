import React from 'react';
import { CheckCircle, AlertCircle, RefreshCw, Server, Database, ShieldAlert } from 'lucide-react';

export interface HealthCheckItem {
  key: string;
  display_name: string;
  category: 'DATA' | 'ENVIRONMENT';
  passed: boolean;
  status: 'PASS' | 'ERROR' | 'ENVIRONMENT' | 'WARN';
  message: string;
  suggested_action?: string;
}

export interface QuestionHealthData {
  is_ready: boolean;
  is_data_ready: boolean;
  environment_ready: boolean;
  status: string;
  passed_checks: number;
  total_checks: number;
  passed_data_checks: number;
  total_data_checks: number;
  checks: HealthCheckItem[];
  errors: string[];
}

interface QuestionReadinessProps {
  healthData: QuestionHealthData | null;
  isLoading?: boolean;
  onRefreshHealth?: () => void;
  questionType: 'MCQ' | 'CODING';
}

export const QuestionReadiness: React.FC<QuestionReadinessProps> = ({
  healthData,
  isLoading = false,
  onRefreshHealth,
  questionType,
}) => {
  if (questionType === 'MCQ') {
    return (
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-indigo-600" />
            <h2 className="text-lg font-bold text-slate-900">Question Readiness</h2>
          </div>
          <span className="text-xs px-2.5 py-1 font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
            MCQ Canonical Evaluation
          </span>
        </div>
        <p className="text-sm text-slate-600">
          MCQ questions require a non-empty question statement, at least 2 options, and exactly 1 correct answer.
        </p>
      </div>
    );
  }

  const dataChecks = healthData?.checks?.filter((c) => c.category === 'DATA') || [];
  const envChecks = healthData?.checks?.filter((c) => c.category === 'ENVIRONMENT') || [];
  const dataPassed = healthData?.passed_data_checks ?? dataChecks.filter((c) => c.passed).length;
  const dataTotal = healthData?.total_data_checks ?? 11;
  const allDataPassed = dataPassed === dataTotal;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-6">
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-indigo-600" />
            <h2 className="text-lg font-bold text-slate-900">Question Readiness & Health</h2>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Publishing requires all 11 DATA checks to PASS. Judge0 Sandbox execution environment is reported separately.
          </p>
        </div>

        {onRefreshHealth && (
          <button
            type="button"
            onClick={onRefreshHealth}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Re-evaluate Health
          </button>
        )}
      </div>

      {/* 11 DATA CHECKS SECTION */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
            1. Question Data Readiness ({dataPassed}/{dataTotal} Checks Passed)
          </span>
          <span
            className={`text-xs px-2.5 py-0.5 font-bold rounded-full border ${
              allDataPassed
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : 'bg-amber-50 text-amber-700 border-amber-200'
            }`}
          >
            {allDataPassed ? 'DATA READY FOR PUBLISH' : `${dataTotal - dataPassed} BLOCKING ISSUES`}
          </span>
        </div>

        {dataChecks.length === 0 ? (
          <div className="text-xs text-slate-500 p-4 bg-slate-50 rounded-lg border border-slate-200">
            Save draft to run all 11 automated data integrity checks.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            {dataChecks.map((chk, idx) => (
              <div
                key={chk.key}
                className={`p-3 rounded-lg border text-xs flex items-start gap-2.5 ${
                  chk.passed
                    ? 'bg-emerald-50/40 border-emerald-200 text-slate-800'
                    : 'bg-red-50/50 border-red-200 text-red-950'
                }`}
              >
                {chk.passed ? (
                  <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-900">
                      {idx + 1}. {chk.display_name}
                    </span>
                    <span
                      className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                        chk.passed ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'
                      }`}
                    >
                      {chk.status}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-600 mt-0.5 leading-snug">{chk.message}</p>
                  {!chk.passed && chk.suggested_action && (
                    <p className="text-[10px] text-red-700 mt-1 font-medium italic">
                      Action: {chk.suggested_action}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* SEPARATE ENVIRONMENT CHECK SECTION */}
      <div className="pt-4 border-t border-slate-200">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-1.5">
            <Server className="w-4 h-4 text-slate-500" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
              2. Isolated Sandbox Environment (Execution Infrastructure)
            </span>
          </div>
          <span className="text-[11px] text-slate-500 italic">Independent of Question Data</span>
        </div>

        {envChecks.length === 0 ? (
          <div className="text-xs text-slate-500 p-3 bg-slate-50 rounded-lg border border-slate-200">
            Sandbox health check pending.
          </div>
        ) : (
          envChecks.map((chk) => (
            <div
              key={chk.key}
              className={`p-3 rounded-lg border text-xs flex items-start gap-2.5 ${
                chk.passed
                  ? 'bg-blue-50/50 border-blue-200 text-slate-800'
                  : 'bg-amber-50/50 border-amber-200 text-amber-950'
              }`}
            >
              {chk.passed ? (
                <CheckCircle className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
              ) : (
                <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-900">{chk.display_name}</span>
                  <span
                    className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                      chk.passed
                        ? 'bg-blue-100 text-blue-800'
                        : 'bg-amber-100 text-amber-800'
                    }`}
                  >
                    {chk.status}
                  </span>
                </div>
                <p className="text-[11px] text-slate-600 mt-0.5 leading-snug">{chk.message}</p>
                {!chk.passed && (
                  <p className="text-[10px] text-amber-800 mt-1 italic">
                    Note: Live sandbox execution is isolated. This environment warning does NOT block publishing when all 11 DATA checks pass.
                  </p>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
