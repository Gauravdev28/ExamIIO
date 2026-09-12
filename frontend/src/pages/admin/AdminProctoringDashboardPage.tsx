import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getAdminProctoringSessions,
  getAdminProctoringSessionDetail,
  updateAdminProctoringReview,
  getEvidenceUrl,
} from '../../api/proctoring';
import {
  AdminProctoringSessionSummary,
  AdminProctoringSessionDetail,
  RiskBand,
  ReviewStatus,
} from '../../types/proctoring';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { InvigilationAPI } from '../../api/invigilation';
import { ReattemptReason } from '../../types/invigilation';
import {
  ShieldAlert,
  ShieldCheck,
  Search,
  AlertTriangle,
  Eye,
  XCircle,
  Clock,
  ArrowLeft,
  Camera,
  Activity,
  CheckCircle,
  RotateCcw,
  X,
} from 'lucide-react';

export const AdminProctoringDashboardPage: React.FC = () => {
  const { assessmentId } = useParams<{ assessmentId: string }>();

  const [sessions, setSessions] = useState<AdminProctoringSessionSummary[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [riskFilter, setRiskFilter] = useState<string>('ALL');
  const [reviewFilter, setReviewFilter] = useState<string>('ALL');
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Selected session for detail/timeline modal
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [sessionDetail, setSessionDetail] = useState<AdminProctoringSessionDetail | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [reviewDecision, setReviewDecision] = useState<string>('REVIEWED_CLEAN');
  const [reviewNotes, setReviewNotes] = useState<string>('');
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);
  const [cancellingAttemptId, setCancellingAttemptId] = useState<string | null>(null);

  // Second-Chance / Reattempt state
  const [showReattemptModal, setShowReattemptModal] = useState(false);
  const [reattemptReason, setReattemptReason] = useState<ReattemptReason>('ACCIDENTAL_VIOLATION');
  const [reattemptNote, setReattemptNote] = useState('');
  const [isSubmittingReattempt, setIsSubmittingReattempt] = useState(false);
  const [reattemptSuccessMessage, setReattemptSuccessMessage] = useState<string | null>(null);
  const [reattemptErrorMessage, setReattemptErrorMessage] = useState<string | null>(null);
  const [reattemptRemainingSeconds, setReattemptRemainingSeconds] = useState<number>(0);

  // 60-Second Reattempt Preparation Window Countdown
  useEffect(() => {
    if (sessionDetail?.reattempt && sessionDetail.reattempt.status === 'AUTHORIZED') {
      const initialSeconds = sessionDetail.reattempt.available_at
        ? Math.max(0, Math.floor((new Date(sessionDetail.reattempt.available_at).getTime() - Date.now()) / 1000))
        : sessionDetail.reattempt.remaining_seconds || 0;
      setReattemptRemainingSeconds(initialSeconds);
      if (initialSeconds > 0) {
        const timer = setInterval(() => {
          setReattemptRemainingSeconds((prev) => {
            if (prev <= 1) {
              clearInterval(timer);
              return 0;
            }
            return prev - 1;
          });
        }, 1000);
        return () => clearInterval(timer);
      }
    } else {
      setReattemptRemainingSeconds(0);
    }
  }, [sessionDetail?.reattempt?.status, sessionDetail?.reattempt?.available_at]);

  const formatTimer = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  const fetchSessions = useCallback(async () => {
    if (!assessmentId) return;
    setErrorMessage(null);
    try {
      const params: any = {};
      if (searchQuery.trim()) params.search = searchQuery.trim();
      if (riskFilter !== 'ALL') params.risk_band = riskFilter;
      if (reviewFilter !== 'ALL') params.review_status = reviewFilter;

      const data = await getAdminProctoringSessions(assessmentId, params);
      setSessions(data.results || []);
      setTotalCount(data.count || 0);
    } catch (err: any) {
      setErrorMessage(err.error?.message || 'Failed to fetch proctoring sessions.');
    } finally {
      setIsLoading(false);
    }
  }, [assessmentId, searchQuery, riskFilter, reviewFilter]);

  // Initial fetch, 5s polling interval, and live WebSocket connection
  useEffect(() => {
    fetchSessions();
    const interval = setInterval(fetchSessions, 5000);

    let ws: WebSocket | null = null;
    if (assessmentId) {
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/proctor/assessments/${assessmentId}/`;
        ws = new WebSocket(wsUrl);
        ws.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data);
            if (
              payload.type === 'PROCTOR_EVENT' ||
              payload.type === 'REATTEMPT_AUTHORIZED' ||
              payload.event === 'REATTEMPT_AUTHORIZED'
            ) {
              fetchSessions();
              if (selectedSessionId) {
                getAdminProctoringSessionDetail(selectedSessionId)
                  .then((updated) => setSessionDetail(updated))
                  .catch(() => {});
              }
            }
          } catch (e) {
            // ignore parsing error
          }
        };
      } catch (e) {
        // graceful degradation to 5s polling
      }
    }

    return () => {
      clearInterval(interval);
      if (ws) ws.close();
    };
  }, [fetchSessions, assessmentId]);

  // 1-second countdown tick for termination_remaining_seconds
  useEffect(() => {
    const timer = setInterval(() => {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.termination_pending && s.termination_remaining_seconds !== undefined && s.termination_remaining_seconds !== null && s.termination_remaining_seconds > 0) {
            return {
              ...s,
              termination_remaining_seconds: s.termination_remaining_seconds - 1,
            };
          }
          return s;
        })
      );
      setSessionDetail((prev) => {
        if (prev && prev.termination_pending && prev.termination_remaining_seconds !== undefined && prev.termination_remaining_seconds !== null && prev.termination_remaining_seconds > 0) {
          return {
            ...prev,
            termination_remaining_seconds: prev.termination_remaining_seconds - 1,
          };
        }
        return prev;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const handleCancelTermination = async (attemptId: string) => {
    setCancellingAttemptId(attemptId);
    try {
      await InvigilationAPI.cancelTermination(attemptId, 'Proctor verified and dismissed focus loss');
      await fetchSessions();
      if (selectedSessionId) {
        const updated = await getAdminProctoringSessionDetail(selectedSessionId);
        setSessionDetail(updated);
      }
    } catch (err: any) {
      alert(err.error?.message || err.message || 'Failed to cancel exam termination.');
    } finally {
      setCancellingAttemptId(null);
    }
  };

  const handleOpenDetail = async (sessionId: string) => {
    setSelectedSessionId(sessionId);
    setIsDetailLoading(true);
    setReattemptSuccessMessage(null);
    setReattemptErrorMessage(null);
    setShowReattemptModal(false);
    try {
      const detail = await getAdminProctoringSessionDetail(sessionId);
      setSessionDetail(detail);
      if (detail.review) {
        setReviewDecision(detail.review.decision);
        setReviewNotes(detail.review.notes || '');
      } else {
        setReviewDecision('REVIEWED_CLEAN');
        setReviewNotes('');
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || 'Failed to load session details.');
    } finally {
      setIsDetailLoading(false);
    }
  };

  const handleCloseDetail = () => {
    setSelectedSessionId(null);
    setSessionDetail(null);
    setShowReattemptModal(false);
    setReattemptSuccessMessage(null);
    setReattemptErrorMessage(null);
  };

  const handleOpenReattemptModal = () => {
    setReattemptReason('ACCIDENTAL_VIOLATION');
    setReattemptNote('');
    setReattemptErrorMessage(null);
    setShowReattemptModal(true);
  };

  const handleConfirmReattempt = async () => {
    if (!sessionDetail) return;
    if (reattemptReason === 'OTHER' && !reattemptNote.trim()) {
      setReattemptErrorMessage('An explanatory note is required when reason is "Other".');
      return;
    }
    setIsSubmittingReattempt(true);
    setReattemptErrorMessage(null);
    try {
      await InvigilationAPI.authorizeReattempt(sessionDetail.attempt_id, {
        reason: reattemptReason,
        note: reattemptNote.trim(),
      });
      setShowReattemptModal(false);
      setReattemptNote('');
      setReattemptSuccessMessage(
        'Second chance authorized successfully. The student can begin Attempt #2 after the 60-second preparation period.'
      );
      // Refresh current detail and list
      if (selectedSessionId) {
        const updated = await getAdminProctoringSessionDetail(selectedSessionId);
        setSessionDetail(updated);
      }
      fetchSessions();
    } catch (err: any) {
      const msg =
        err.response?.data?.error ||
        err.response?.data?.detail ||
        (typeof err.response?.data === 'string' ? err.response?.data : null) ||
        err.error?.message ||
        err.message ||
        'Failed to authorize second chance.';
      setReattemptErrorMessage(msg);
    } finally {
      setIsSubmittingReattempt(false);
    }
  };

  const handleSaveReview = async () => {
    if (!selectedSessionId) return;
    setIsSubmittingReview(true);
    try {
      await updateAdminProctoringReview(selectedSessionId, reviewDecision, reviewNotes);
      // Refresh current detail and list
      const updated = await getAdminProctoringSessionDetail(selectedSessionId);
      setSessionDetail(updated);
      fetchSessions();
    } catch (err: any) {
      alert(err.error?.message || 'Failed to update review decision.');
    } finally {
      setIsSubmittingReview(false);
    }
  };

  const getRiskBandBadge = (band: RiskBand, score: string) => {
    switch (band) {
      case 'CRITICAL':
        return <Badge variant="danger" className="font-semibold">CRITICAL ({score})</Badge>;
      case 'HIGH':
        return <Badge variant="warning" className="bg-orange-100 text-orange-800 border-orange-200 dark:bg-orange-950 dark:text-orange-400 dark:border-orange-800 font-semibold">HIGH ({score})</Badge>;
      case 'MEDIUM':
        return <Badge variant="warning" className="font-semibold">MEDIUM ({score})</Badge>;
      case 'LOW':
        return <Badge variant="neutral" className="bg-amber-50 text-amber-800 border-amber-200 dark:bg-yellow-950 dark:text-yellow-400 dark:border-yellow-800">LOW ({score})</Badge>;
      default:
        return <Badge variant="success">NORMAL ({score})</Badge>;
    }
  };

  const getReviewStatusBadge = (status: ReviewStatus) => {
    switch (status) {
      case 'REVIEWED':
        return <Badge variant="success">Reviewed</Badge>;
      case 'DISMISSED':
        return <Badge variant="neutral">Dismissed</Badge>;
      case 'ESCALATED':
        return <Badge variant="danger">Escalated</Badge>;
      case 'UNDER_REVIEW':
        return <Badge variant="warning">Under Review</Badge>;
      default:
        return <Badge variant="neutral">Unreviewed</Badge>;
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 space-y-6 max-w-7xl">
      {/* Top Breadcrumb & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <Link
            to="/admin/assessments"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors mb-2"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Assessments
          </Link>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-600">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">
                AI Proctoring & Anomaly Review Dashboard
              </h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Real-time suspicious telemetry ledger, multi-modal risk scoring, and administrative audit review.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <Card className="p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search by name, email, or EUID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
            >
              <option value="ALL">All Risk Bands</option>
              <option value="CRITICAL">Critical Risk (81-100)</option>
              <option value="HIGH">High Risk (61-80)</option>
              <option value="MEDIUM">Medium Risk (41-60)</option>
              <option value="LOW">Low Risk (21-40)</option>
              <option value="NORMAL">Normal (0-20)</option>
            </select>
          </div>

          <div>
            <select
              value={reviewFilter}
              onChange={(e) => setReviewFilter(e.target.value)}
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
            >
              <option value="ALL">All Review Statuses</option>
              <option value="UNREVIEWED">Unreviewed</option>
              <option value="UNDER_REVIEW">Under Review</option>
              <option value="REVIEWED">Reviewed - Clean</option>
              <option value="DISMISSED">Dismissed False Positive</option>
              <option value="ESCALATED">Escalated for Inquiry</option>
            </select>
          </div>

          <div className="flex items-center justify-end">
            <span className="text-xs text-slate-500 font-mono">
              Total Sessions: <span className="text-slate-900 font-bold">{totalCount}</span>
            </span>
          </div>
        </div>
      </Card>

      {/* Sessions Table */}
      <Card className="overflow-hidden p-0">
        {isLoading ? (
          <div className="py-16 text-center text-slate-500 flex flex-col items-center gap-3">
            <Activity className="w-8 h-8 text-indigo-600 animate-spin" />
            <p className="text-xs font-mono">Loading proctoring sessions...</p>
          </div>
        ) : errorMessage ? (
          <div className="p-8 text-center text-rose-600 flex flex-col items-center gap-2">
            <AlertTriangle className="w-8 h-8" />
            <p className="text-sm font-semibold">{errorMessage}</p>
          </div>
        ) : sessions.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <ShieldCheck className="w-10 h-10 text-slate-400 mx-auto" />
            <p className="text-sm font-bold text-slate-800">No proctoring sessions found.</p>
            <p className="text-xs text-slate-500">No student attempts match the active filter criteria.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 uppercase tracking-wider font-semibold">
                <tr>
                  <th className="px-4 py-3.5">Candidate</th>
                  <th className="px-4 py-3.5">EUID / Roll No</th>
                  <th className="px-4 py-3.5">Attempt Status</th>
                  <th className="px-4 py-3.5 text-center">Violations</th>
                  <th className="px-4 py-3.5">Latest Violation</th>
                  <th className="px-4 py-3.5">Latest Time</th>
                  <th className="px-4 py-3.5">Risk Band</th>
                  <th className="px-4 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {sessions.map((s) => {
                  const attemptStatus = s.attempt_status || 'IN_PROGRESS';
                  return (
                    <tr key={s.session_id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-4 py-3.5">
                        <div className="flex flex-col">
                          <span className="font-sans font-bold text-slate-900 text-sm">{s.student.full_name}</span>
                          <span className="text-[11px] text-slate-500">{s.student.email}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="flex flex-col">
                          <span className="font-mono text-xs font-semibold text-slate-800">{s.student.euid || '—'}</span>
                          {s.student.roll_number && (
                            <span className="text-[10px] text-slate-400 font-mono">{s.student.roll_number}</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        {s.termination_pending ? (
                          <div className="flex flex-col gap-1.5 items-start">
                            <span className="px-2 py-0.5 bg-red-600 text-white rounded text-2xs font-bold uppercase tracking-wider animate-pulse flex items-center gap-1">
                              <AlertTriangle className="w-3 h-3" />
                              TERMINATION PENDING ({formatTimer(s.termination_remaining_seconds ?? 0)})
                            </span>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleCancelTermination(s.attempt_id);
                              }}
                              disabled={cancellingAttemptId === s.attempt_id}
                              className="text-[11px] font-bold text-emerald-700 hover:text-emerald-800 bg-emerald-50 hover:bg-emerald-100 border border-emerald-300 px-2 py-0.5 rounded transition inline-flex items-center gap-1 cursor-pointer"
                            >
                              <CheckCircle className="w-3 h-3" />
                              {cancellingAttemptId === s.attempt_id ? 'Cancelling...' : 'Cancel Exam Termination'}
                            </button>
                          </div>
                        ) : (s.is_disqualified || attemptStatus === 'DISQUALIFIED') ? (
                          (s.disqualification_reason || s.termination_reason || '').toUpperCase().includes('FOCUS') ? (
                            <div className="flex flex-col gap-1 items-start">
                              <Badge variant="danger" size="sm" className="font-bold text-[10px] leading-tight text-left">
                                EXAMINATION TERMINATED — WINDOW FOCUS LOST
                              </Badge>
                              <span className="text-[10px] text-red-600 font-mono font-semibold">Status: DISQUALIFIED</span>
                            </div>
                          ) : (
                            <Badge variant="danger" size="sm" className="font-bold">
                              DISQUALIFIED
                            </Badge>
                          )
                        ) : attemptStatus === 'SUBMITTED' ? (
                          <Badge variant="warning" size="sm">
                            SUBMITTED
                          </Badge>
                        ) : (
                          <Badge variant="info" size="sm">
                            {attemptStatus}
                          </Badge>
                        )}
                      </td>
                      <td className="px-4 py-3.5 text-center font-bold text-slate-900">
                        {s.violation_count ?? s.total_warnings_count}
                      </td>
                      <td className="px-4 py-3.5 font-medium text-slate-700">
                        {s.latest_violation || '—'}
                      </td>
                      <td className="px-4 py-3.5 text-slate-500 font-mono text-[11px]">
                        {s.latest_violation_at ? new Date(s.latest_violation_at).toLocaleTimeString() : '—'}
                      </td>
                      <td className="px-4 py-3.5">
                        {getRiskBandBadge(s.risk_band, s.risk_score)}
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => handleOpenDetail(s.session_id)}
                          className="inline-flex items-center gap-1.5"
                        >
                          <Eye className="w-3.5 h-3.5" /> Inspect Timeline
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Detail & Timeline Modal */}
      {selectedSessionId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm overflow-y-auto">
          <div className="bg-white border border-slate-200 rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden text-slate-900">
            {/* Modal Header */}
            <div className="p-6 border-b border-slate-200 flex items-center justify-between bg-slate-50/70">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-600">
                  <ShieldAlert className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    Proctoring Timeline & Evidence Review
                  </h3>
                  {sessionDetail && (
                    <p className="text-xs text-slate-500 mt-0.5 font-mono">
                      Student: <span className="font-bold text-slate-800">{sessionDetail.student.full_name}</span> ({sessionDetail.student.euid}) | Attempt: {sessionDetail.attempt_id}
                    </p>
                  )}
                </div>
              </div>
              <button
                onClick={handleCloseDetail}
                className="text-slate-400 hover:text-slate-700 transition-colors"
              >
                <XCircle className="w-6 h-6" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1">
              {isDetailLoading || !sessionDetail ? (
                <div className="py-12 text-center text-slate-500 flex flex-col items-center gap-3">
                  <Activity className="w-8 h-8 text-indigo-600 animate-spin" />
                  <p className="text-xs font-mono">Loading detailed event timeline and evidence...</p>
                </div>
              ) : (
                <>
                  {/* Authoritative Termination Alert Banners */}
                  {sessionDetail.termination_pending && (
                    <div className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3">
                        <div className="p-2.5 bg-red-100 border border-red-300 rounded-lg text-red-600 shrink-0">
                          <AlertTriangle className="w-6 h-6" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-red-700 tracking-wider uppercase">TERMINATION PENDING</span>
                            <span className="px-2 py-0.5 bg-red-100 border border-red-300 text-red-800 font-mono text-xs font-bold rounded">
                              {formatTimer(sessionDetail.termination_remaining_seconds ?? 0)}
                            </span>
                          </div>
                          <p className="text-xs text-red-600 mt-0.5 font-medium">
                            Focus Loss: {sessionDetail.termination_reason || 'EXAM WINDOW LOST FOCUS'}
                          </p>
                          <p className="text-[11px] text-slate-500 mt-0.5">
                            Attempt will automatically cancel upon countdown expiry unless proctor intervenes.
                          </p>
                        </div>
                      </div>
                      <Button
                        variant="primary"
                        size="sm"
                        className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold shrink-0 inline-flex items-center gap-1.5"
                        onClick={() => handleCancelTermination(sessionDetail.attempt_id)}
                        disabled={cancellingAttemptId === sessionDetail.attempt_id}
                      >
                        <CheckCircle className="w-4 h-4" />
                        {cancellingAttemptId === sessionDetail.attempt_id ? 'Cancelling...' : 'Cancel Exam Termination'}
                      </Button>
                    </div>
                  )}

                  {(sessionDetail.is_disqualified || sessionDetail.attempt_status === 'DISQUALIFIED') && (
                    <div className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-center gap-3">
                      <div className="p-2.5 bg-red-100 border border-red-300 rounded-lg text-red-600 shrink-0">
                        <AlertTriangle className="w-6 h-6" />
                      </div>
                      <div>
                        <span className="text-xs font-bold text-red-700 tracking-wider uppercase">
                          {(sessionDetail.disqualification_reason || sessionDetail.termination_reason || '').toUpperCase().includes('FOCUS')
                            ? 'EXAMINATION TERMINATED — WINDOW FOCUS LOST'
                            : 'EXAMINATION TERMINATED — DISQUALIFIED'}
                        </span>
                        <p className="text-xs text-red-600 mt-0.5">
                          {sessionDetail.disqualification_reason || 'Candidate disqualified due to examination integrity policy violation.'}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Summary Bar */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 bg-slate-50 border border-slate-200 rounded-xl">
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase font-semibold">Risk Score</span>
                      <div className="mt-1">{getRiskBandBadge(sessionDetail.risk_band, sessionDetail.risk_score)}</div>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase font-semibold">Review Status</span>
                      <div className="mt-1">{getReviewStatusBadge(sessionDetail.review_status)}</div>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase font-semibold">Total Events</span>
                      <div className="text-lg font-bold text-slate-900 mt-0.5 font-mono">{sessionDetail.total_events_count}</div>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase font-semibold">Warnings Issued</span>
                      <div className="text-lg font-bold text-slate-900 mt-0.5 font-mono">{sessionDetail.total_warnings_count}</div>
                    </div>
                  </div>

                  {/* Chronological Event Timeline */}
                  <div>
                    <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-3 flex items-center gap-2">
                      <Clock className="w-4 h-4 text-indigo-600" /> Chronological Telemetry Ledger
                    </h4>

                    {sessionDetail.events.length === 0 ? (
                      <p className="text-xs text-slate-500 italic p-4 bg-slate-50 rounded-xl border border-slate-200 font-mono">
                        No suspicious events recorded for this session.
                      </p>
                    ) : (
                      <div className="space-y-3">
                        {sessionDetail.events.map((ev) => (
                          <div
                            key={ev.id}
                            className="p-4 bg-slate-50 border border-slate-200 rounded-xl flex flex-col gap-2"
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <Badge
                                  variant={
                                    ev.severity === 'CRITICAL'
                                      ? 'danger'
                                      : ev.severity === 'HIGH'
                                      ? 'warning'
                                      : 'neutral'
                                  }
                                >
                                  {ev.event_type}
                                </Badge>
                                <span className="text-xs font-mono text-slate-500">
                                  [{ev.source}] Delta: +{ev.risk_delta}
                                </span>
                              </div>
                              <span className="text-xs text-slate-500 font-mono">
                                {new Date(ev.server_received_at).toLocaleTimeString()}
                              </span>
                            </div>

                            <div className="text-xs text-slate-600 grid grid-cols-2 sm:grid-cols-3 gap-2 mt-1 font-mono">
                              <div>
                                <span className="text-slate-400">Confidence:</span> {(ev.confidence * 100).toFixed(0)}%
                              </div>
                              <div>
                                <span className="text-slate-400">Model:</span> {ev.model_name || 'N/A'} ({ev.model_version || 'V1'})
                              </div>
                              <div>
                                <span className="text-slate-400">Policy:</span> {ev.inference_policy_version}
                              </div>
                            </div>

                            {/* Keyframe Evidence Media Preview */}
                            {ev.evidence_id && (
                              <div className="mt-3 p-3 bg-white border border-slate-200 rounded-xl">
                                <span className="text-xs font-semibold text-slate-700 flex items-center gap-1.5 mb-2">
                                  <Camera className="w-3.5 h-3.5 text-indigo-600" /> Captured Keyframe Evidence
                                </span>
                                <div className="max-w-xs rounded-lg overflow-hidden border border-slate-300 bg-black">
                                  <img
                                    src={getEvidenceUrl(ev.evidence_id)}
                                    alt="Proctoring Anomaly Keyframe"
                                    className="w-full h-auto object-cover"
                                    onError={(e) => {
                                      (e.target as HTMLElement).style.display = 'none';
                                    }}
                                  />
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Administrative Review Action Form */}
                  <div className="p-5 bg-indigo-50/40 border border-indigo-200 rounded-xl space-y-4">
                    <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-emerald-600" /> Authoritative Human Review Verdict
                    </h4>
                    <p className="text-xs text-slate-600">
                      Proctoring scores are probabilistic indicators. Assign authoritative institutional review determinations below.
                    </p>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                          Review Decision
                        </label>
                        <select
                          value={reviewDecision}
                          onChange={(e) => setReviewDecision(e.target.value)}
                          className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                        >
                          <option value="REVIEWED_CLEAN">Reviewed — Clean / Not Disqualified</option>
                          <option value="SUSPICIOUS_CONFIRMED">Reviewed — Confirmed Violation / Disqualified</option>
                          <option value="REQUIRES_FURTHER_INSPECTION">Reviewed — Requires Further Review</option>
                          <option value="DISMISSED_FALSE_POSITIVE">Dismissed as False Positive</option>
                        </select>
                        <p className="text-[11px] text-slate-500 mt-1.5 leading-snug">
                          Administrative human verdict for recordkeeping. A verdict of &quot;Not Disqualified&quot; does NOT alter attempt lifecycle status or resurrect terminal attempts.
                        </p>
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                        Administrative Audit Notes
                      </label>
                      <textarea
                        rows={3}
                        value={reviewNotes}
                        onChange={(e) => setReviewNotes(e.target.value)}
                        placeholder="Document observations, rationale, or interview outcomes..."
                        className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>

                    <div className="flex justify-end gap-3 pt-2">
                      <Button
                        variant="primary"
                        onClick={handleSaveReview}
                        disabled={isSubmittingReview}
                      >
                        {isSubmittingReview ? 'Saving...' : 'Save Review Decision'}
                      </Button>
                    </div>
                  </div>

                  {/* Reattempt Success Notification */}
                  {reattemptSuccessMessage && (
                    <div className="p-4 bg-emerald-50 border border-emerald-300 rounded-xl text-xs text-emerald-900 flex items-center justify-between gap-3 shadow-sm">
                      <div className="flex items-center gap-2.5">
                        <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0" />
                        <span className="font-medium">{reattemptSuccessMessage}</span>
                      </div>
                      <button
                        onClick={() => setReattemptSuccessMessage(null)}
                        className="text-emerald-700 hover:text-emerald-950 p-1"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  )}

                  {/* Second-Chance Action Section */}
                  <div className="p-5 bg-white border border-slate-200 rounded-xl space-y-4 shadow-sm">
                    <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                      <div className="flex items-center gap-2.5">
                        <div className="p-2 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-600">
                          <RotateCcw className="w-5 h-5" />
                        </div>
                        <div>
                          <h4 className="text-sm font-bold text-slate-900">Second-Chance Action</h4>
                          <p className="text-xs text-slate-500">
                            Authorize exactly ONE second attempt for a disqualified or cancelled student. Original attempt remains terminal.
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* STATE 4 — Attempt is already a reattempt (Attempt #2+) */}
                    {(sessionDetail.is_already_reattempt || (sessionDetail.attempt_number && sessionDetail.attempt_number > 1)) ? (
                      <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between text-xs">
                        <div>
                          <span className="font-bold text-slate-800">Attempt #{sessionDetail.attempt_number || 2}: </span>
                          <span className="text-slate-600">This attempt is already a reattempt. Chaining is prohibited (Attempt #3 is not allowed).</span>
                        </div>
                        <Badge variant="neutral">No Action Available</Badge>
                      </div>
                    ) : sessionDetail.reattempt?.status === 'CONSUMED' ? (
                      /* STATE 3 — Consumed */
                      <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl space-y-2 text-xs">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-emerald-900 uppercase tracking-wider text-[11px]">Reattempt:</span>
                            <span className="px-2.5 py-0.5 bg-emerald-200/80 text-emerald-900 font-bold rounded text-xs">
                              CONSUMED — Attempt #{sessionDetail.reattempt.new_attempt_number || 2}
                            </span>
                          </div>
                          <span className="text-slate-500 font-mono text-[11px]">
                            Authorized: {sessionDetail.reattempt.authorized_at ? new Date(sessionDetail.reattempt.authorized_at).toLocaleDateString() : '—'}
                          </span>
                        </div>
                        <p className="text-emerald-800 font-medium">
                          The candidate has consumed this second chance and begun Attempt #{sessionDetail.reattempt.new_attempt_number || 2}
                          {sessionDetail.reattempt.new_attempt_id && <span className="font-mono text-slate-700"> (Attempt ID: {sessionDetail.reattempt.new_attempt_id})</span>}.
                          Attempt #1 remains permanently CANCELLED for audit records.
                        </p>
                      </div>
                    ) : sessionDetail.reattempt?.status === 'AUTHORIZED' ? (
                      /* STATE 2 — Authorization Pending / Preparation Window */
                      <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl space-y-3 text-xs">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-amber-900 uppercase tracking-wider text-[11px]">Reattempt:</span>
                            <span className="px-2.5 py-0.5 bg-amber-200/80 text-amber-900 font-bold rounded text-xs">
                              AUTHORIZED — Waiting for student
                            </span>
                          </div>
                          {reattemptRemainingSeconds > 0 ? (
                            <span className="px-2.5 py-1 bg-amber-200 border border-amber-300 text-amber-900 font-mono text-xs font-bold rounded animate-pulse">
                              Preparation Delay: {reattemptRemainingSeconds}s remaining
                            </span>
                          ) : (
                            <span className="px-2.5 py-1 bg-emerald-100 border border-emerald-300 text-emerald-800 font-mono text-xs font-bold rounded">
                              Ready for Student to Start Attempt #2
                            </span>
                          )}
                        </div>
                        <p className="text-amber-900">
                          Second chance authorized. Reason:{' '}
                          <strong className="capitalize">{sessionDetail.reattempt.reason.toLowerCase().replace(/_/g, ' ')}</strong>
                          {sessionDetail.reattempt.note && <span className="italic"> — &quot;{sessionDetail.reattempt.note}&quot;</span>}.
                        </p>
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1 border-t border-amber-200/60">
                          <span className="text-slate-500 font-mono text-[11px]">
                            Server Available At: {sessionDetail.reattempt.available_at ? new Date(sessionDetail.reattempt.available_at).toLocaleTimeString() : 'Immediate'}
                          </span>
                          <Button variant="secondary" size="sm" disabled className="opacity-60 cursor-not-allowed">
                            Reattempt Already Authorized
                          </Button>
                        </div>
                      </div>
                    ) : (sessionDetail.is_disqualified || sessionDetail.attempt_status === 'CANCELLED' || sessionDetail.attempt_status === 'DISQUALIFIED') && (sessionDetail.can_grant_reattempt ?? true) ? (
                      /* STATE 1 — Eligible for Reattempt */
                      <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4 text-xs">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-slate-800">Attempt #{sessionDetail.attempt_number || 1}:</span>
                            <Badge variant="danger">
                              {sessionDetail.is_disqualified ? 'CANCELLED / DISQUALIFIED' : (sessionDetail.attempt_status || 'CANCELLED')}
                            </Badge>
                            <span className="text-slate-400">|</span>
                            <span className="text-slate-600 font-medium">Reattempt Status: <span className="text-slate-500">Not Authorized</span></span>
                          </div>
                          <p className="text-slate-500">
                            Candidate examination was terminated. You can authorize exactly one fresh attempt.
                          </p>
                        </div>
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={handleOpenReattemptModal}
                          className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold shrink-0 flex items-center gap-1.5 shadow-sm"
                        >
                          <RotateCcw className="w-4 h-4" />
                          Give Student Another Chance
                        </Button>
                      </div>
                    ) : (
                      /* STATE 5 — Not Eligible */
                      <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-500 flex items-center justify-between">
                        <span>
                          Reattempt actions are only available for cancelled or disqualified exam attempts.
                          (Current status: <strong className="font-semibold text-slate-700">{sessionDetail.attempt_status || 'ACTIVE'}</strong>)
                        </span>
                        <Badge variant="neutral">Not Eligible</Badge>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Give Student Another Chance Confirmation Modal */}
      {showReattemptModal && sessionDetail && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm overflow-y-auto">
          <div className="bg-white border border-emerald-500/40 rounded-xl shadow-2xl max-w-lg w-full p-6 space-y-4 text-slate-900">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <div className="p-1.5 bg-emerald-100 rounded-lg text-emerald-700">
                  <RotateCcw className="w-4 h-4" />
                </div>
                Give Student Another Chance
              </h3>
              <button
                onClick={() => setShowReattemptModal(false)}
                className="text-slate-400 hover:text-slate-700 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Candidate & Attempt Metadata */}
            <div className="p-3.5 bg-slate-50 rounded-xl space-y-1.5 text-xs text-slate-700 border border-slate-200">
              <div className="grid grid-cols-3 gap-1">
                <span className="text-slate-500 font-medium">Student:</span>
                <span className="col-span-2 font-bold text-slate-900">
                  {sessionDetail.student.full_name} ({sessionDetail.student.email})
                </span>
              </div>
              <div className="grid grid-cols-3 gap-1">
                <span className="text-slate-500 font-medium">Roll Number:</span>
                <span className="col-span-2 font-mono text-slate-800">
                  {sessionDetail.student.roll_number || sessionDetail.student.euid || 'N/A'}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-1">
                <span className="text-slate-500 font-medium">Assessment:</span>
                <span className="col-span-2 font-semibold text-slate-800">
                  {sessionDetail.assessment_title || 'Current Assessment'}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-1">
                <span className="text-slate-500 font-medium">Original Attempt:</span>
                <span className="col-span-2 font-bold text-slate-900">
                  #{sessionDetail.attempt_number || 1}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-1">
                <span className="text-slate-500 font-medium">Status:</span>
                <span className="col-span-2 font-bold text-rose-600 uppercase">
                  {sessionDetail.is_disqualified ? 'CANCELLED / DISQUALIFIED' : (sessionDetail.attempt_status || 'CANCELLED')}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-1">
                <span className="text-slate-500 font-medium">Violation:</span>
                <span className="col-span-2 text-rose-700 font-mono text-[11px]">
                  {sessionDetail.disqualification_reason || sessionDetail.termination_reason || 'Examination integrity policy violation'}
                </span>
              </div>
            </div>

            {/* Invariant Warning */}
            <div className="p-3.5 bg-amber-50 border border-amber-300 rounded-xl text-xs text-amber-900 flex items-start gap-2.5">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <p className="leading-relaxed">
                <strong>Warning:</strong> This action will permanently preserve Attempt #{sessionDetail.attempt_number || 1} as CANCELLED and authorize exactly ONE new attempt for this student. Attempt #{sessionDetail.attempt_number || 1} will not be reopened.
              </p>
            </div>

            {/* Reason Selection */}
            <div className="space-y-3 pt-1">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Reason <span className="text-rose-500">*</span>
                </label>
                <select
                  value={reattemptReason}
                  onChange={(e) => {
                    setReattemptReason(e.target.value as ReattemptReason);
                    setReattemptErrorMessage(null);
                  }}
                  className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500 font-medium"
                >
                  <option value="ACCIDENTAL_VIOLATION">Accidental violation</option>
                  <option value="TECHNICAL_PROBLEM">Technical problem</option>
                  <option value="PROCTOR_DECISION">Proctor decision</option>
                  <option value="OTHER">Other</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  {reattemptReason === 'OTHER' ? (
                    <>
                      Explanatory Note <span className="text-rose-500">* (Required for Other)</span>
                    </>
                  ) : (
                    'Explanatory Note (Optional)'
                  )}
                </label>
                <textarea
                  rows={3}
                  value={reattemptNote}
                  onChange={(e) => {
                    setReattemptNote(e.target.value);
                    if (reattemptErrorMessage) setReattemptErrorMessage(null);
                  }}
                  placeholder={
                    reattemptReason === 'OTHER'
                      ? 'Detailed justification is required when reason is Other...'
                      : 'Optional administrator notes for audit log...'
                  }
                  className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              {reattemptErrorMessage && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 font-medium flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
                  <span>{reattemptErrorMessage}</span>
                </div>
              )}
            </div>

            {/* Modal Actions */}
            <div className="flex justify-end gap-3 pt-3 border-t border-slate-200">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowReattemptModal(false)}
                disabled={isSubmittingReattempt}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleConfirmReattempt}
                disabled={isSubmittingReattempt || (reattemptReason === 'OTHER' && !reattemptNote.trim())}
                className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold flex items-center gap-1.5 disabled:opacity-50"
              >
                <RotateCcw className="w-4 h-4" />
                {isSubmittingReattempt ? 'Authorizing...' : 'Confirm & Authorize Second Chance'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminProctoringDashboardPage;
