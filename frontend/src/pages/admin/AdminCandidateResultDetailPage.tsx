import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Award,
  CheckCircle2,
  XCircle,
  AlertCircle,
  HelpCircle,
  ShieldAlert,
  Loader2,
  Code2,
  Database,
  FileText,
  User as UserIcon,
  Shield,
  Copy,
  Check,
} from 'lucide-react';
import { ResultsAPI } from '../../api/results';
import { AdminCandidateResultDetail, AdminQuestionReviewItem } from '../../types/results';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';

export const AdminCandidateResultDetailPage: React.FC = () => {
  const { assessmentId, resultId } = useParams<{ assessmentId: string; resultId: string }>();
  const navigate = useNavigate();

  const [result, setResult] = useState<AdminCandidateResultDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedCodeIndex, setCopiedCodeIndex] = useState<number | null>(null);

  useEffect(() => {
    if (assessmentId && resultId) {
      loadDetail();
    }
  }, [assessmentId, resultId]);

  const loadDetail = async () => {
    if (!assessmentId || !resultId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await ResultsAPI.getAdminAssessmentResultDetail(assessmentId, resultId);
      setResult(data);
    } catch (err: any) {
      setError(err?.response?.data?.message || err.message || 'Failed to load candidate result details.');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedCodeIndex(index);
    setTimeout(() => setCopiedCodeIndex(null), 2000);
  };

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case 'EVALUATED':
      case 'RELEASED':
        return <Badge variant="success" size="sm">{status}</Badge>;
      case 'DISQUALIFIED':
        return <Badge variant="danger" size="sm">Disqualified</Badge>;
      case 'EVALUATING':
        return <Badge variant="purple" size="sm">Evaluating</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{status}</Badge>;
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <Loader2 className="w-10 h-10 animate-spin text-emerald-600" />
        <p className="text-slate-500 font-medium text-sm">Loading authoritative candidate result & answer review...</p>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="max-w-3xl mx-auto mt-12 p-8 bg-white border border-slate-200 rounded-2xl shadow-sm text-center">
        <AlertCircle className="w-12 h-12 text-rose-500 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-slate-900 mb-2">Candidate Result Unavailable</h2>
        <p className="text-slate-600 text-sm mb-6">{error || 'The requested result could not be found.'}</p>
        <button
          onClick={() => navigate(`/admin/assessments/${assessmentId}/results`)}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs rounded-xl shadow-sm transition"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Candidate Roster
        </button>
      </div>
    );
  }

  const isPassed = result.is_passed;
  const proct = result.proctoring_summary;

  return (
    <div className="w-full px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Navigation Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <button
            onClick={() => navigate(`/admin/assessments/${assessmentId}/results`)}
            className="flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-slate-900 mb-2 transition"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Results Roster
          </button>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight flex items-center gap-3">
            <Award className="w-8 h-8 text-emerald-600" /> Candidate Result Review
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Assessment: <span className="font-semibold text-slate-800">{result.assessment_title}</span>
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(`/admin/assessments/${assessmentId}/proctoring`)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs sm:text-sm font-semibold rounded-lg shadow-sm transition"
          >
            <Shield className="w-4 h-4 text-emerald-400" /> View Proctoring
          </button>
        </div>
      </div>

      {/* Top Cards: Student Identity & Result Scorecard */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Student Card */}
        <Card className="p-6">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">
            <UserIcon className="w-4 h-4 text-emerald-600" /> Student Information
          </div>
          <div className="space-y-3">
            <div>
              <div className="text-xs text-slate-500 font-medium">Official Student Name</div>
              <div className="text-base font-bold text-slate-900">
                {result.student.official_name || 'N/A'}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500 font-medium">Email Address</div>
              <div className="text-sm font-mono text-slate-700">{result.student.email}</div>
            </div>
            <div className="grid grid-cols-2 gap-4 pt-1">
              <div>
                <div className="text-xs text-slate-500 font-medium">Roll Number</div>
                <div className="text-sm font-semibold font-mono text-slate-800">
                  {result.student.roll_number || 'N/A'}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500 font-medium">EUID</div>
                <div className="text-sm font-semibold font-mono text-slate-800">
                  {result.student.euid || 'N/A'}
                </div>
              </div>
            </div>
          </div>
        </Card>

        {/* Result Card */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-500 uppercase tracking-wider">
              <Award className="w-4 h-4 text-emerald-600" /> Assessment Result
            </div>
            <div>{renderStatusBadge(result.status)}</div>
          </div>

          <div className="flex items-baseline justify-between mb-4">
            <div>
              <div className="text-3xl font-black text-slate-900 tracking-tight">
                {result.total_score_earned}{' '}
                <span className="text-base text-slate-400 font-normal">/ {result.total_possible_score} pts</span>
              </div>
              <div className="text-sm font-bold text-emerald-700 mt-0.5">{result.percentage}% Score</div>
            </div>
            {isPassed !== null && (
              <span
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border ${
                  isPassed
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : 'bg-rose-50 text-rose-700 border-rose-200'
                }`}
              >
                {isPassed ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                {isPassed ? 'PASS' : 'FAIL'}
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3 pt-3 border-t border-slate-100 text-xs">
            <div>
              <span className="text-slate-500">Duration: </span>
              <span className="font-semibold text-slate-800 font-mono">
                {Math.round(result.time_spent_seconds / 60)} mins ({result.time_spent_seconds}s)
              </span>
            </div>
            <div>
              <span className="text-slate-500">Proctoring Risk: </span>
              {proct ? (
                <span
                  className={`inline-flex items-center gap-1 font-semibold ${
                    proct.risk_band === 'CRITICAL' || proct.risk_band === 'HIGH'
                      ? 'text-rose-600'
                      : proct.risk_band === 'MEDIUM'
                      ? 'text-amber-600'
                      : 'text-slate-700'
                  }`}
                >
                  <ShieldAlert className="w-3 h-3" /> {proct.risk_band} ({proct.risk_score})
                </span>
              ) : (
                <span className="text-slate-400">N/A</span>
              )}
            </div>
          </div>
        </Card>
      </div>

      {/* Metrics Summary Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-xs">
          <div className="text-xs text-slate-500 font-medium">Total Questions</div>
          <div className="text-xl font-bold text-slate-900 mt-1">
            {result.answered_questions} / {result.total_questions} answered
          </div>
        </div>
        <div className="bg-emerald-50/60 rounded-xl p-4 border border-emerald-200 shadow-xs">
          <div className="text-xs text-emerald-800 font-medium flex items-center gap-1.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Correct
          </div>
          <div className="text-xl font-bold text-emerald-900 mt-1">{result.correct_questions}</div>
        </div>
        <div className="bg-amber-50/60 rounded-xl p-4 border border-amber-200 shadow-xs">
          <div className="text-xs text-amber-800 font-medium flex items-center gap-1.5">
            <HelpCircle className="w-4 h-4 text-amber-600" /> Partially Correct
          </div>
          <div className="text-xl font-bold text-amber-900 mt-1">{result.partially_correct_questions}</div>
        </div>
        <div className="bg-rose-50/60 rounded-xl p-4 border border-rose-200 shadow-xs">
          <div className="text-xs text-rose-800 font-medium flex items-center gap-1.5">
            <XCircle className="w-4 h-4 text-rose-600" /> Incorrect
          </div>
          <div className="text-xl font-bold text-rose-900 mt-1">{result.incorrect_questions}</div>
        </div>
        <div className="bg-slate-100 rounded-xl p-4 border border-slate-200 shadow-xs">
          <div className="text-xs text-slate-600 font-medium">Skipped</div>
          <div className="text-xl font-bold text-slate-800 mt-1">{result.skipped_questions}</div>
        </div>
      </div>

      {/* Question-by-Question Detailed Review */}
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <FileText className="w-5 h-5 text-emerald-600" /> Question-by-Question Review
          </h2>
          <span className="text-xs font-semibold text-slate-500">
            {result.questions.length} Questions in Frozen Snapshot
          </span>
        </div>

        {result.questions.map((q: AdminQuestionReviewItem, idx: number) => {
          const isCorrect = q.is_correct;
          const isPartial = q.is_partially_correct;
          const isSkipped = q.is_skipped;

          return (
            <Card key={q.snapshot_question_id || idx} className="p-6 space-y-5 border-slate-200">
              {/* Question Header */}
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 pb-4 border-b border-slate-100">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="px-2.5 py-0.5 rounded-md bg-slate-900 text-white font-mono text-xs font-bold">
                      Q#{q.order}
                    </span>
                    <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-xs font-semibold">
                      {q.question_type}
                    </span>
                    <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 text-xs font-medium">
                      {q.difficulty}
                    </span>

                    {/* Verdict Pill */}
                    {isCorrect && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Correct
                      </span>
                    )}
                    {isPartial && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">
                        <HelpCircle className="w-3.5 h-3.5" /> Partial Credit
                      </span>
                    )}
                    {isSkipped && (
                      <span className="px-2.5 py-0.5 rounded-md text-xs font-bold bg-slate-100 text-slate-600">
                        Skipped
                      </span>
                    )}
                    {!isCorrect && !isPartial && !isSkipped && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200">
                        <XCircle className="w-3.5 h-3.5" /> Incorrect
                      </span>
                    )}
                  </div>
                  <h3 className="text-base font-bold text-slate-900 pt-1">{q.title}</h3>
                </div>

                <div className="text-right sm:shrink-0 font-mono">
                  <div className="text-lg font-bold text-slate-900">
                    {q.earned_points}{' '}
                    <span className="text-xs text-slate-400 font-normal">/ {q.max_points} pts</span>
                  </div>
                  {q.negative_marking_enabled && q.negative_points > 0 && (
                    <div className="text-2xs text-rose-500 font-medium">
                      Penalty: -{q.negative_points} pts
                    </div>
                  )}
                </div>
              </div>

              {/* Problem Prompt / Description */}
              {q.description && (
                <div className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap bg-slate-50/60 p-4 rounded-xl border border-slate-100">
                  {q.description}
                </div>
              )}

              {/* Type-Specific Answer & Evaluation Review */}
              {/* 1. MCQ / MULTI_SELECT / TRUE_FALSE */}
              {['MCQ', 'MULTI_SELECT', 'TRUE_FALSE'].includes(q.question_type) && q.correct_answer.options && (
                <div className="space-y-3 pt-2">
                  <div className="text-xs font-bold text-slate-600 uppercase tracking-wider">
                    Options & Answer Key
                  </div>
                  <div className="space-y-2">
                    {q.correct_answer.options.map((opt) => {
                      const isUserSelected = opt.is_selected;
                      const isOptCorrect = opt.is_correct;

                      let containerStyle = 'bg-white border-slate-200 text-slate-700';
                      if (isUserSelected && isOptCorrect) {
                        containerStyle = 'bg-emerald-50 border-emerald-300 text-emerald-950 font-medium';
                      } else if (isUserSelected && !isOptCorrect) {
                        containerStyle = 'bg-rose-50 border-rose-300 text-rose-950 font-medium';
                      } else if (!isUserSelected && isOptCorrect) {
                        containerStyle = 'bg-emerald-50/40 border-emerald-300 border-dashed text-emerald-950';
                      }

                      return (
                        <div
                          key={opt.id}
                          className={`p-3.5 rounded-xl border flex items-center justify-between gap-4 transition ${containerStyle}`}
                        >
                          <div className="flex items-center gap-3">
                            <span
                              className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold border ${
                                isOptCorrect
                                  ? 'bg-emerald-600 border-emerald-600 text-white'
                                  : isUserSelected
                                  ? 'bg-rose-600 border-rose-600 text-white'
                                  : 'bg-white border-slate-300 text-slate-600'
                              }`}
                            >
                              {isOptCorrect ? '✓' : isUserSelected ? '✗' : ''}
                            </span>
                            <span className="text-sm">{opt.text}</span>
                          </div>

                          <div className="flex items-center gap-2 shrink-0">
                            {isUserSelected && (
                              <span
                                className={`px-2 py-0.5 rounded text-xs font-bold border ${
                                  isOptCorrect
                                    ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
                                    : 'bg-rose-100 text-rose-800 border-rose-200'
                                }`}
                              >
                                Student's Answer
                              </span>
                            )}
                            {isOptCorrect && (
                              <span className="px-2 py-0.5 rounded text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                                Correct Answer
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* 2. SHORT_ANSWER */}
              {q.question_type === 'SHORT_ANSWER' && (
                <div className="space-y-4 pt-2">
                  <div>
                    <div className="text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5">
                      Student's Submitted Answer
                    </div>
                    <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 font-mono text-sm text-slate-900">
                      {q.student_answer.text_response || (
                        <span className="text-slate-400 italic font-sans">No answer submitted</span>
                      )}
                    </div>
                  </div>

                  <div>
                    <div className="text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5">
                      Accepted Exact Match Answers
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {(q.correct_answer.exact_matches || []).map((match, mIdx) => (
                        <span
                          key={mIdx}
                          className="px-3 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-lg font-mono text-xs font-bold"
                        >
                          {match}
                        </span>
                      ))}
                      <span className="text-xs text-slate-500 ml-2">
                        Case sensitive: <span className="font-semibold text-slate-700">{q.correct_answer.case_sensitive ? 'Yes' : 'No'}</span>
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* 3. CODING */}
              {q.question_type === 'CODING' && (
                <div className="space-y-5 pt-2">
                  {/* Candidate Code View */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <div className="text-xs font-bold text-slate-600 uppercase tracking-wider flex items-center gap-1.5">
                        <Code2 className="w-4 h-4 text-emerald-600" /> Student's Code Submission
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="px-2.5 py-0.5 rounded bg-slate-100 text-slate-700 font-mono text-xs font-semibold">
                          {q.code_submission?.language || q.student_answer.code_language || 'PYTHON'}
                        </span>
                        {q.code_submission?.source_code && (
                          <button
                            onClick={() => copyToClipboard(q.code_submission?.source_code || '', idx)}
                            className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-900 font-semibold transition"
                          >
                            {copiedCodeIndex === idx ? (
                              <>
                                <Check className="w-3.5 h-3.5 text-emerald-600" /> Copied
                              </>
                            ) : (
                              <>
                                <Copy className="w-3.5 h-3.5" /> Copy Code
                              </>
                            )}
                          </button>
                        )}
                      </div>
                    </div>

                    <pre className="p-4 bg-slate-900 text-slate-100 rounded-xl text-xs font-mono overflow-x-auto border border-slate-800 max-h-96 leading-relaxed">
                      <code>{q.code_submission?.source_code || q.student_answer.code_response || '// No code submitted'}</code>
                    </pre>
                  </div>

                  {/* Execution Diagnostics */}
                  {q.code_submission && (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                      <div>
                        <span className="text-slate-500 block">Verdict</span>
                        <span className="font-bold text-slate-900 font-mono">
                          {q.code_submission.verdict || 'N/A'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">Passed Test Cases</span>
                        <span className="font-bold text-slate-900 font-mono">
                          {q.code_submission.passed_test_cases} / {q.code_submission.total_test_cases}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">Execution Time</span>
                        <span className="font-bold text-slate-900 font-mono">
                          {q.code_submission.execution_time_ms} ms
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">Memory Used</span>
                        <span className="font-bold text-slate-900 font-mono">
                          {q.code_submission.memory_used_kb} KB
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Compilation Error if present */}
                  {q.code_submission?.compilation_error && (
                    <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl">
                      <div className="text-xs font-bold text-rose-800 uppercase tracking-wider mb-1">
                        Compilation Error Log
                      </div>
                      <pre className="text-xs font-mono text-rose-700 whitespace-pre-wrap">
                        {q.code_submission.compilation_error}
                      </pre>
                    </div>
                  )}

                  {/* Test Cases Table */}
                  {q.code_submission?.test_cases && q.code_submission.test_cases.length > 0 && (
                    <div>
                      <div className="text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">
                        Test Case Execution Summary
                      </div>
                      <div className="overflow-x-auto rounded-xl border border-slate-200">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 font-semibold">
                            <tr>
                              <th className="py-2.5 px-3">#</th>
                              <th className="py-2.5 px-3">Type</th>
                              <th className="py-2.5 px-3">Verdict</th>
                              <th className="py-2.5 px-3">Points</th>
                              <th className="py-2.5 px-3">Time</th>
                              <th className="py-2.5 px-3">Memory</th>
                              <th className="py-2.5 px-3">Input / Output</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {q.code_submission.test_cases.map((tc) => (
                              <tr key={tc.index} className="hover:bg-slate-50/60">
                                <td className="py-2.5 px-3 font-mono font-bold text-slate-800">
                                  #{tc.index}
                                </td>
                                <td className="py-2.5 px-3">
                                  {tc.is_hidden ? (
                                    <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-semibold text-2xs">
                                      Hidden
                                    </span>
                                  ) : (
                                    <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold text-2xs">
                                      Public
                                    </span>
                                  )}
                                </td>
                                <td className="py-2.5 px-3">
                                  <span
                                    className={`px-2 py-0.5 rounded text-2xs font-bold ${
                                      tc.verdict === 'PASSED'
                                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                        : 'bg-rose-50 text-rose-700 border border-rose-200'
                                    }`}
                                  >
                                    {tc.verdict}
                                  </span>
                                </td>
                                <td className="py-2.5 px-3 font-mono">
                                  {tc.points_awarded} / {tc.max_points}
                                </td>
                                <td className="py-2.5 px-3 font-mono text-slate-600">
                                  {tc.execution_time_ms} ms
                                </td>
                                <td className="py-2.5 px-3 font-mono text-slate-600">
                                  {tc.memory_used_kb} KB
                                </td>
                                <td className="py-2.5 px-3 text-slate-500 font-mono text-2xs">
                                  {tc.is_hidden ? (
                                    <span className="text-slate-400 italic">Protected Hidden Test Case</span>
                                  ) : (
                                    <div className="space-y-0.5">
                                      <div>In: {tc.public_input || 'None'}</div>
                                      <div>Expected: {tc.expected_output || 'None'}</div>
                                      <div>Actual: {tc.actual_output || 'None'}</div>
                                    </div>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* 4. SQL */}
              {q.question_type === 'SQL' && (
                <div className="space-y-4 pt-2">
                  <div>
                    <div className="text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                      <Database className="w-4 h-4 text-emerald-600" /> Student's SQL Query
                    </div>
                    <pre className="p-4 bg-slate-900 text-slate-100 rounded-xl text-xs font-mono overflow-x-auto border border-slate-800 leading-relaxed">
                      <code>{q.student_answer.sql_response || q.code_submission?.source_code || '-- No SQL query submitted'}</code>
                    </pre>
                  </div>

                  {q.correct_answer.expected_result_definition && (
                    <div>
                      <div className="text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5">
                        Expected Result Definition / Reference Target
                      </div>
                      <pre className="p-3.5 bg-emerald-50/50 text-emerald-950 border border-emerald-200 rounded-xl text-xs font-mono overflow-x-auto">
                        <code>{q.correct_answer.expected_result_definition}</code>
                      </pre>
                    </div>
                  )}

                  {q.correct_answer.schema_setup_sql && (
                    <details className="text-xs">
                      <summary className="font-semibold text-slate-600 cursor-pointer hover:text-slate-900 py-1">
                        View Sandbox Schema Setup SQL (DDL/DML)
                      </summary>
                      <pre className="mt-2 p-3 bg-slate-50 text-slate-700 border border-slate-200 rounded-xl font-mono text-2xs overflow-x-auto max-h-48">
                        <code>{q.correct_answer.schema_setup_sql}</code>
                      </pre>
                    </details>
                  )}
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
};
