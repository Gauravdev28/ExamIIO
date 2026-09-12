import React, { useState } from 'react';
import { Plus, Trash2, Play, Terminal, CheckCircle2, AlertTriangle, XCircle, Clock } from 'lucide-react';
import { runSandboxTest, RunSandboxResult } from '../../api/questions';
import { CodingLanguage } from '../../types/question';

export interface TestCaseItem {
  case_id?: string;
  input_data: string;
  expected_output: string;
  points: number;
  is_hidden: boolean;
  is_example: boolean;
  explanation?: string;
}

interface TestCaseEditorProps {
  testCases: TestCaseItem[];
  onChange: (cases: TestCaseItem[]) => void;
  allowedLanguages: CodingLanguage[];
  starterCodes: Record<string, string>;
  disabled?: boolean;
}

export const TestCaseEditor: React.FC<TestCaseEditorProps> = ({
  testCases,
  onChange,
  allowedLanguages,
  starterCodes,
  disabled = false,
}) => {
  // Test Runner state
  const [runnerLang, setRunnerLang] = useState<CodingLanguage>(
    allowedLanguages.length > 0 ? allowedLanguages[0] : 'PYTHON'
  );
  const [runnerCode, setRunnerCode] = useState<string>('');
  const [runnerInput, setRunnerInput] = useState<string>('');
  const [runnerExpectedOutput, setRunnerExpectedOutput] = useState<string>('');
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [runResult, setRunResult] = useState<RunSandboxResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const handleCaseChange = (index: number, field: keyof TestCaseItem, value: any) => {
    const updated = testCases.map((tc, i) => {
      if (i !== index) return tc;
      const modified = { ...tc, [field]: value };
      // Invariant: HIDDEN test cases cannot be examples
      if (field === 'is_hidden' && value === true) {
        modified.is_example = false;
      }
      return modified;
    });
    onChange(updated);
  };

  const handleAddTestCase = () => {
    const nextIdx = testCases.length + 1;
    const isHidden = nextIdx > 1; // Default first as sample, subsequent as hidden
    const newCase: TestCaseItem = {
      case_id: `TC-${String(nextIdx).padStart(2, '0')}`,
      input_data: '',
      expected_output: '',
      points: 5,
      is_hidden: isHidden,
      is_example: !isHidden,
    };
    onChange([...testCases, newCase]);
  };

  const handleRemoveTestCase = (index: number) => {
    if (testCases.length <= 1) {
      alert('At least one test case is required.');
      return;
    }
    const remaining = testCases.filter((_, i) => i !== index);
    onChange(remaining);
  };

  const handleLoadTestCaseIntoRunner = (tc: TestCaseItem) => {
    setRunnerInput(tc.input_data);
    setRunnerExpectedOutput(tc.expected_output);
    // If runner code is empty, initialize with current starter code
    if (!runnerCode && starterCodes[runnerLang]) {
      setRunnerCode(starterCodes[runnerLang]);
    }
  };

  const handleExecuteCode = async () => {
    const codeToRun = runnerCode.trim() || starterCodes[runnerLang] || '';
    if (!codeToRun) {
      setRunError('Please enter source code to run.');
      return;
    }

    setIsRunning(true);
    setRunError(null);
    setRunResult(null);

    try {
      const res = await runSandboxTest({
        source_code: codeToRun,
        language: runnerLang,
        stdin: runnerInput,
        expected_output: runnerExpectedOutput,
        time_limit_ms: 2000,
        memory_limit_mb: 256,
      });
      if (res.data) {
        setRunResult(res.data);
      }
    } catch (err: any) {
      setRunError(err.error?.message || err.message || 'Execution failed.');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-6 text-slate-900">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <div>
          <h3 className="text-sm font-bold text-slate-900">Test Cases Workspace</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Configure sample and hidden test cases. Samples marked as Example are shown to candidates.
          </p>
        </div>
        {!disabled && (
          <button
            type="button"
            onClick={handleAddTestCase}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 transition-colors cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Test Case</span>
          </button>
        )}
      </div>

      {/* Test Cases List */}
      <div className="space-y-4">
        {testCases.map((tc, idx) => (
          <div
            key={idx}
            className={`p-4 rounded-xl border transition-all ${
              tc.is_hidden
                ? 'bg-slate-50/70 border-slate-200'
                : 'bg-emerald-50/20 border-emerald-200'
            }`}
          >
            {/* Top Bar for Case */}
            <div className="flex items-center justify-between gap-4 mb-3">
              <div className="flex items-center gap-3">
                <span className="font-mono text-xs font-bold text-slate-700">
                  #{idx + 1}
                </span>

                {/* Hidden / Public toggle */}
                <label className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 cursor-pointer">
                  <input
                    type="checkbox"
                    disabled={disabled}
                    checked={tc.is_hidden}
                    onChange={(e) => handleCaseChange(idx, 'is_hidden', e.target.checked)}
                    className="w-3.5 h-3.5 rounded text-emerald-600 focus:ring-emerald-500 border-slate-300"
                  />
                  <span>Hidden Test Case</span>
                </label>

                {/* Example sample flag */}
                {!tc.is_hidden && (
                  <label className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 cursor-pointer">
                    <input
                      type="checkbox"
                      disabled={disabled}
                      checked={tc.is_example}
                      onChange={(e) => handleCaseChange(idx, 'is_example', e.target.checked)}
                      className="w-3.5 h-3.5 rounded text-emerald-600 focus:ring-emerald-500 border-slate-300"
                    />
                    <span>Show as Example to Candidate</span>
                  </label>
                )}
              </div>

              <div className="flex items-center gap-3">
                {/* Points */}
                <div className="flex items-center gap-1 text-xs">
                  <label className="text-slate-500 font-medium">Points:</label>
                  <input
                    type="number"
                    min={1}
                    disabled={disabled}
                    value={tc.points}
                    onChange={(e) => handleCaseChange(idx, 'points', Math.max(1, parseInt(e.target.value, 10) || 1))}
                    className="w-16 px-2 py-1 text-xs rounded-lg border border-slate-300 bg-white text-slate-900 font-mono focus:ring-2 focus:ring-emerald-500"
                  />
                </div>

                {/* Load into runner button */}
                <button
                  type="button"
                  onClick={() => handleLoadTestCaseIntoRunner(tc)}
                  className="text-[11px] font-semibold text-slate-600 hover:text-emerald-700 px-2 py-1 rounded-lg bg-white border border-slate-200 hover:border-emerald-300 transition-colors"
                  title="Load input into test runner below"
                >
                  Load to Runner
                </button>

                {/* Remove button */}
                {!disabled && testCases.length > 1 && (
                  <button
                    type="button"
                    onClick={() => handleRemoveTestCase(idx)}
                    className="p-1 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-rose-50 transition-colors"
                    title="Delete test case"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>

            {/* Input and Expected Output textareas */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="block text-[11px] font-semibold text-slate-600">
                  Input (stdin)
                </label>
                <textarea
                  rows={2}
                  disabled={disabled}
                  value={tc.input_data}
                  onChange={(e) => handleCaseChange(idx, 'input_data', e.target.value)}
                  placeholder="Standard input..."
                  className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 bg-white text-slate-900 font-mono focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-[11px] font-semibold text-slate-600">
                  Expected Output <span className="text-rose-500">*</span>
                </label>
                <textarea
                  rows={2}
                  disabled={disabled}
                  value={tc.expected_output}
                  onChange={(e) => handleCaseChange(idx, 'expected_output', e.target.value)}
                  placeholder="Expected stdout..."
                  className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 bg-white text-slate-900 font-mono focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Inline Test Runner Panel — Light Professional Theme */}
      <div className="p-4 rounded-xl bg-slate-50 text-slate-900 space-y-4 border border-slate-200">
        <div className="flex items-center justify-between border-b border-slate-200 pb-2.5">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-emerald-600" />
            <h4 className="text-xs font-bold tracking-wide uppercase text-slate-700">
              Inline Code Runner
            </h4>
          </div>

          <div className="flex items-center gap-3">
            <select
              value={runnerLang}
              onChange={(e) => setRunnerLang(e.target.value as CodingLanguage)}
              className="px-2.5 py-1 text-xs rounded-lg bg-white border border-slate-300 text-slate-800 font-medium focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            >
              {allowedLanguages.map((l) => (
                <option key={l} value={l}>
                  {l === 'C' ? 'C' : l === 'CPP' ? 'C++' : l === 'JAVA' ? 'Java' : 'Python'}
                </option>
              ))}
            </select>

            <button
              type="button"
              disabled={isRunning}
              onClick={handleExecuteCode}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white transition-all disabled:opacity-60 cursor-pointer shadow-xs"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>{isRunning ? 'Running...' : 'Run Code'}</span>
            </button>
          </div>
        </div>

        {/* Code & Input Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="block text-[11px] font-semibold text-slate-600">
              Source Code <span className="text-[10px] text-slate-400">(leave blank to use starter code)</span>
            </label>
            <textarea
              rows={4}
              value={runnerCode}
              onChange={(e) => setRunnerCode(e.target.value)}
              placeholder={starterCodes[runnerLang] || 'print("Hello CODEGUARD")'}
              className="w-full px-3 py-2 text-xs rounded-lg bg-white border border-slate-300 text-slate-900 font-mono focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>

          <div className="space-y-1">
            <label className="block text-[11px] font-semibold text-slate-600">
              Input (stdin)
            </label>
            <textarea
              rows={4}
              value={runnerInput}
              onChange={(e) => setRunnerInput(e.target.value)}
              placeholder="Custom input data..."
              className="w-full px-3 py-2 text-xs rounded-lg bg-white border border-slate-300 text-slate-900 font-mono focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>
        </div>

        {/* Run Error Message */}
        {runError && (
          <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
            <XCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{runError}</span>
          </div>
        )}

        {/* Execution Result Display */}
        {runResult && (
          <div className="p-3.5 rounded-lg bg-white border border-slate-200 space-y-2.5 text-xs shadow-xs">
            <div className="flex items-center justify-between">
              {/* Status Badge */}
              <div className="flex items-center gap-2">
                {runResult.status === 'SUCCESS' ? (
                  <span className="inline-flex items-center gap-1 text-xs font-bold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-md border border-emerald-200">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Execution Successful
                  </span>
                ) : runResult.status === 'COMPILATION_ERROR' ? (
                  <span className="inline-flex items-center gap-1 text-xs font-bold text-rose-700 bg-rose-50 px-2.5 py-0.5 rounded-md border border-rose-200">
                    <XCircle className="w-3.5 h-3.5" /> Compilation Error
                  </span>
                ) : runResult.status === 'RUNTIME_ERROR' ? (
                  <span className="inline-flex items-center gap-1 text-xs font-bold text-amber-800 bg-amber-50 px-2.5 py-0.5 rounded-md border border-amber-200">
                    <AlertTriangle className="w-3.5 h-3.5" /> Runtime Error
                  </span>
                ) : runResult.status === 'TIME_LIMIT_EXCEEDED' ? (
                  <span className="inline-flex items-center gap-1 text-xs font-bold text-orange-800 bg-orange-50 px-2.5 py-0.5 rounded-md border border-orange-200">
                    <Clock className="w-3.5 h-3.5" /> Time Limit Exceeded
                  </span>
                ) : runResult.status === 'SANDBOX_UNAVAILABLE' ? (
                  <span className="inline-flex items-center gap-1 text-xs font-bold text-slate-700 bg-slate-100 px-2.5 py-0.5 rounded-md border border-slate-300">
                    <AlertTriangle className="w-3.5 h-3.5" /> Coding Sandbox Unavailable
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-xs font-bold text-rose-700 bg-rose-50 px-2.5 py-0.5 rounded-md border border-rose-200">
                    <XCircle className="w-3.5 h-3.5" /> {runResult.status}
                  </span>
                )}

                {runResult.passed !== undefined && runResult.passed !== null && (
                  <span
                    className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-0.5 rounded-md border ${
                      runResult.passed
                        ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
                        : 'text-rose-700 bg-rose-50 border-rose-200'
                    }`}
                  >
                    {runResult.passed ? 'Output Matched' : 'Output Mismatch'}
                  </span>
                )}
              </div>

              {/* Execution Metrics */}
              <div className="flex items-center gap-3 text-[11px] text-slate-500 font-mono">
                <span>{runResult.execution_time_ms} ms</span>
                <span>&bull;</span>
                <span>{runResult.memory_kb} KB</span>
              </div>
            </div>

            {/* Stdout Output */}
            {runResult.stdout !== null && (
              <div className="space-y-1">
                <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wider">stdout:</span>
                <pre className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-slate-800 font-mono text-xs whitespace-pre-wrap">
                  {runResult.stdout || '(no output)'}
                </pre>
              </div>
            )}

            {/* Compile Output */}
            {runResult.compile_output && (
              <div className="space-y-1">
                <span className="text-[10px] font-bold text-rose-700 uppercase tracking-wider">compiler log:</span>
                <pre className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 font-mono text-xs whitespace-pre-wrap">
                  {runResult.compile_output}
                </pre>
              </div>
            )}

            {/* Stderr Output */}
            {runResult.stderr && (
              <div className="space-y-1">
                <span className="text-[10px] font-bold text-amber-700 uppercase tracking-wider">stderr:</span>
                <pre className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 font-mono text-xs whitespace-pre-wrap">
                  {runResult.stderr}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
