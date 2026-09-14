import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { AdminAPI } from '../api/admin';
import { getQuestions } from '../api/questions';
import { AdminDashboardOverview } from '../types/admin';
import {
  FileCode,
  Plus,
  Users,
  ArrowRight,
  Code2,
  ShieldCheck,
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [overview, setOverview] = useState<AdminDashboardOverview | null>(null);
  const [questionsCount, setQuestionsCount] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setIsLoading(true);
    try {
      // 1. Fetch overview metrics, recent assessments, and activity
      const overviewPromise = AdminAPI.getOverview().catch(() => ({
        metrics: {
          active_assessments: 0,
          upcoming_assessments: 0,
          completed_assessments: 0,
          total_students: 0,
        },
        recent_assessments: [],
        upcoming_assessments: [],
        recent_activity: [],
      }));

      // 2. Fetch authoritative questions count
      const questionsPromise = getQuestions({ page_size: 1 })
        .then((res) => {
          if (res?.data && typeof res.data.count === 'number') {
            return res.data.count;
          }
          if (typeof (res as any)?.count === 'number') {
            return (res as any).count;
          }
          return null;
        })
        .catch(() => null);

      const [overviewData, qCount] = await Promise.all([overviewPromise, questionsPromise]);
      setOverview(overviewData);
      setQuestionsCount(qCount);
    } catch {
      setOverview({
        metrics: {
          active_assessments: 0,
          upcoming_assessments: 0,
          completed_assessments: 0,
          total_students: 0,
        },
        recent_assessments: [],
        upcoming_assessments: [],
        recent_activity: [],
      });
      setQuestionsCount(null);
    } finally {
      setIsLoading(false);
    }
  };

  // Time-aware greeting logic:
  // Before 12:00 -> Good morning
  // 12:00–16:59 -> Good afternoon
  // 17:00 onward -> Good evening
  const getGreeting = (): string => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  };

  const displayName =
    user?.display_name ||
    user?.first_name ||
    (user?.email ? user.email.split('@')[0] : 'Administrator');

  // Format institutional numbers (pad single digits < 10 with leading zero: 04, 08)
  const formatKpiNumber = (val: number): string => {
    if (val >= 0 && val < 10) {
      return String(val).padStart(2, '0');
    }
    return String(val);
  };

  // Derive operational status: LIVE | SCHEDULED | COMPLETED
  const getAssessmentStatus = (a: {
    status: string;
    start_datetime?: string | null;
    end_datetime?: string | null;
  }): 'LIVE' | 'SCHEDULED' | 'COMPLETED' | string => {
    if (a.status === 'ARCHIVED') return 'COMPLETED';
    const now = new Date();
    if (a.start_datetime) {
      const start = new Date(a.start_datetime);
      const end = a.end_datetime ? new Date(a.end_datetime) : null;
      if (start <= now && (!end || end >= now)) {
        return 'LIVE';
      }
      if (start > now) {
        return 'SCHEDULED';
      }
      if (end && end < now) {
        return 'COMPLETED';
      }
    }
    if (a.status === 'PUBLISHED') return 'LIVE';
    if (a.status === 'DRAFT') return 'SCHEDULED';
    return a.status;
  };

  // Render Status Badge according to the Institutional Precision theme
  const renderStatusBadge = (status: string) => {
    switch (status) {
      case 'LIVE':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-[#EBF7F2] text-[#1F855C] border border-[#BDE5D4]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#2FA878] animate-pulse" />
            Live
          </span>
        );
      case 'SCHEDULED':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-[#EEF5FC] text-[#2878D8] border border-[#CFE2F7]">
            Scheduled
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-[#EDE9E1] text-[#5E6B7D] border border-[#DDD8CE]">
            Completed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-[#FAF9F6] text-[#5E6B7D] border border-[#DDD8CE]">
            {status}
          </span>
        );
    }
  };

  // Human-readable action label formatter
  const formatActivityAction = (action: string): string => {
    const actionMap: Record<string, string> = {
      ASSESSMENT_PUBLISHED: 'Assessment published',
      ASSESSMENT_PUBLISH: 'Assessment published',
      ASSESSMENT_CREATED: 'Assessment created',
      ASSESSMENT_CREATE: 'Assessment created',
      QUESTION_BANK_UPDATED: 'Question bank updated',
      QUESTION_CREATED: 'Question bank updated',
      QUESTION_CREATE: 'Question created',
      PROCTOR_ASSIGNED: 'Proctor assigned',
      PROCTOR_ASSIGN: 'Proctor assigned',
      CERTIFICATE_ISSUED: 'Certificate issued',
      CERTIFICATE_ISSUE: 'Certificate issued',
      STUDENT_REGISTERED: 'Candidate registered',
      STUDENT_INVITED: 'Candidate invited',
    };
    if (actionMap[action]) return actionMap[action];
    return action.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
  };

  // Human-readable relative timestamp formatter
  const formatRelativeTime = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMin = Math.floor(diffMs / 60000);
      const diffHour = Math.floor(diffMin / 60);
      const diffDay = Math.floor(diffHour / 24);

      if (diffMin < 1) return 'Just now';
      if (diffMin < 60) return `${diffMin}m ago`;
      if (diffHour < 24) return `${diffHour}h ago`;
      if (diffDay === 1) return 'Yesterday';
      if (diffDay < 7) return `${diffDay}d ago`;
      return date.toLocaleDateString();
    } catch {
      return isoString;
    }
  };

  const assessmentsList = overview?.recent_assessments || [];
  const activityList = overview?.recent_activity || [];

  return (
    <div className="w-full min-h-[calc(100vh-4rem)] bg-[#F4F1EA] text-[#243247] selection:bg-[#2878D8]/20 selection:text-[#243247]">
      <div className="w-full px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* ============================================================
          1. HEADER & BRAND IDENTITY
          ============================================================ */}
      <div className="space-y-4">
        <div>
          <div className="text-xs font-mono font-bold tracking-widest text-[#2878D8] uppercase">
            ExamIIO
          </div>
        </div>

        <div className="flex items-center justify-between pt-1 border-b border-[#DDD8CE] pb-3">
          <h1 className="text-lg sm:text-xl font-bold text-[#243247] tracking-tight">
            Dashboard
          </h1>
          <span className="text-xs sm:text-sm font-semibold text-[#243247] whitespace-nowrap truncate max-w-[200px] sm:max-w-none">
            {displayName}
          </span>
        </div>
      </div>

      {/* ============================================================
          2. GREETING & HEADLINE
          ============================================================ */}
      <div>
        <h2 className="text-2xl sm:text-3xl font-bold text-[#243247] tracking-tight font-sans">
          {getGreeting()}, {displayName}.
        </h2>
        <p className="text-xs sm:text-sm text-[#5E6B7D] mt-1">
          Here's what's happening across ExamIIO.
        </p>
      </div>

      {/* ============================================================
          3. PRIMARY KPI RIBBON (4 Metric Cards)
          ============================================================ */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        {/* Active Assessments */}
        <div className="bg-white rounded-xl border border-[#DDD8CE] p-4 sm:p-5 shadow-xs transition-colors hover:border-[#2878D8]/40">
          <div className="text-[11px] sm:text-xs font-semibold text-[#5E6B7D] uppercase tracking-wider">
            Active Assessments
          </div>
          <div className="text-2xl sm:text-3xl font-bold font-mono text-[#243247] mt-2">
            {isLoading ? '—' : formatKpiNumber(overview?.metrics.active_assessments ?? 0)}
          </div>
          <div className="text-[11px] text-[#5E6B7D] mt-1 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#2FA878]" />
            <span>Live windows</span>
          </div>
        </div>

        {/* Candidates */}
        <div className="bg-white rounded-xl border border-[#DDD8CE] p-4 sm:p-5 shadow-xs transition-colors hover:border-[#2878D8]/40">
          <div className="text-[11px] sm:text-xs font-semibold text-[#5E6B7D] uppercase tracking-wider">
            Candidates
          </div>
          <div className="text-2xl sm:text-3xl font-bold font-mono text-[#243247] mt-2">
            {isLoading ? '—' : formatKpiNumber(overview?.metrics.total_students ?? 0)}
          </div>
          <div className="text-[11px] text-[#5E6B7D] mt-1">
            Registered students
          </div>
        </div>

        {/* Questions */}
        <div className="bg-white rounded-xl border border-[#DDD8CE] p-4 sm:p-5 shadow-xs transition-colors hover:border-[#2878D8]/40">
          <div className="text-[11px] sm:text-xs font-semibold text-[#5E6B7D] uppercase tracking-wider">
            Questions
          </div>
          <div className="text-2xl sm:text-3xl font-bold font-mono text-[#243247] mt-2">
            {isLoading ? '—' : questionsCount !== null ? formatKpiNumber(questionsCount) : '—'}
          </div>
          <div className="text-[11px] text-[#5E6B7D] mt-1">
            Question bank items
          </div>
        </div>

        {/* Proctors */}
        <div className="bg-white rounded-xl border border-[#DDD8CE] p-4 sm:p-5 shadow-xs transition-colors hover:border-[#2878D8]/40">
          <div className="text-[11px] sm:text-xs font-semibold text-[#5E6B7D] uppercase tracking-wider">
            Proctors
          </div>
          <div className="text-2xl sm:text-3xl font-bold font-mono text-[#5E6B7D] mt-2">
            —
          </div>
          <div className="text-[11px] text-[#8C98A9] mt-1 font-mono">
            Not configured
          </div>
        </div>
      </div>

      {/* ============================================================
          4. RESTRAINED QUICK ACTIONS TOOLBAR
          ============================================================ */}
      <div className="flex flex-wrap items-center gap-2.5 pt-1">
        <Link
          to="/admin/assessments/create"
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-[#2878D8] hover:bg-[#2065B8] active:bg-[#18539C] text-white text-xs font-semibold shadow-xs transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Create Assessment</span>
        </Link>
        <Link
          to="/admin/questions"
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-white hover:bg-[#EDE9E1] text-[#243247] border border-[#DDD8CE] text-xs font-semibold shadow-xs transition-colors"
        >
          <Code2 className="w-3.5 h-3.5 text-[#2878D8]" />
          <span>Question Bank</span>
        </Link>
        <Link
          to="/admin/students"
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-white hover:bg-[#EDE9E1] text-[#243247] border border-[#DDD8CE] text-xs font-semibold shadow-xs transition-colors"
        >
          <Users className="w-3.5 h-3.5 text-[#2878D8]" />
          <span>Manage Students</span>
        </Link>
        <Link
          to="/admin/assessments"
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-white hover:bg-[#EDE9E1] text-[#243247] border border-[#DDD8CE] text-xs font-semibold shadow-xs transition-colors"
        >
          <ShieldCheck className="w-3.5 h-3.5 text-[#2878D8]" />
          <span>Proctor Console</span>
        </Link>
      </div>

      {/* ============================================================
          5. MAIN CONTENT: ASSESSMENT ACTIVITY & RECENT ACTIVITY
          ============================================================ */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Left 2 Columns: Assessment Activity */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-[#DDD8CE]">
            <h3 className="text-xs sm:text-sm font-bold text-[#243247] uppercase tracking-wider">
              Assessment Activity
            </h3>
            <Link
              to="/admin/assessments"
              className="text-xs font-semibold text-[#2878D8] hover:text-[#2065B8] flex items-center gap-1 transition-colors"
            >
              <span>View All</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          <div className="bg-white rounded-xl border border-[#DDD8CE] overflow-hidden shadow-xs">
            {isLoading ? (
              <div className="py-12 text-center text-xs text-[#5E6B7D]">
                Loading assessment activity...
              </div>
            ) : assessmentsList.length === 0 ? (
              <div className="py-12 px-6 text-center space-y-3">
                <div className="w-10 h-10 rounded-full bg-[#EDE9E1] text-[#5E6B7D] mx-auto flex items-center justify-center">
                  <FileCode className="w-5 h-5 text-[#2878D8]" />
                </div>
                <div className="space-y-1">
                  <div className="text-sm font-semibold text-[#243247]">No assessments yet</div>
                  <p className="text-xs text-[#5E6B7D] max-w-sm mx-auto">
                    Create your first technical assessment to begin.
                  </p>
                </div>
                <div className="pt-2">
                  <Link
                    to="/admin/assessments/create"
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#2878D8] hover:bg-[#2065B8] active:bg-[#18539C] text-white text-xs font-semibold shadow-xs transition-colors"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Create Assessment</span>
                  </Link>
                </div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#FAF9F6] border-b border-[#DDD8CE] text-[#5E6B7D] font-semibold">
                    <tr>
                      <th className="px-4 py-3 text-left">Assessment</th>
                      <th className="px-4 py-3 text-left">Status</th>
                      <th className="px-4 py-3 text-right">Candidates</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#EDE9E1]">
                    {assessmentsList.map((a) => {
                      const operationalStatus = getAssessmentStatus(a);
                      return (
                        <tr
                          key={a.id}
                          className="hover:bg-[#FAF9F6] transition-colors"
                        >
                          <td className="px-4 py-3.5 text-left">
                            <Link
                              to={`/admin/assessments/${a.id}`}
                              className="font-semibold text-xs text-[#243247] hover:text-[#2878D8] transition-colors line-clamp-1"
                              title={a.title}
                            >
                              {a.title}
                            </Link>
                            {a.start_datetime && (
                              <div className="text-[11px] text-[#8C98A9] font-mono mt-0.5">
                                {new Date(a.start_datetime).toLocaleDateString()}
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-3.5 text-left whitespace-nowrap">
                            {renderStatusBadge(operationalStatus)}
                          </td>
                          <td className="px-4 py-3.5 text-right font-mono text-xs font-semibold text-[#243247]">
                            {a.candidates_count}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Right 1 Column: Recent Activity */}
        <div className="space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-[#DDD8CE]">
            <h3 className="text-xs sm:text-sm font-bold text-[#243247] uppercase tracking-wider">
              Recent Activity
            </h3>
            <Link
              to="/admin/retention"
              className="text-xs font-semibold text-[#2878D8] hover:text-[#2065B8] flex items-center gap-1 transition-colors"
            >
              <span>Audit Log</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          <div className="bg-white rounded-xl border border-[#DDD8CE] p-4 shadow-xs">
            {isLoading ? (
              <div className="py-8 text-center text-xs text-[#5E6B7D]">
                Loading activity...
              </div>
            ) : activityList.length === 0 ? (
              <div className="py-8 px-2 text-center space-y-1">
                <div className="text-xs font-semibold text-[#243247]">
                  No recent activity
                </div>
                <p className="text-xs text-[#5E6B7D] leading-relaxed">
                  Activity will appear here as administrators work across ExamIIO.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {activityList.slice(0, 6).map((act) => (
                  <div
                    key={act.id}
                    className="flex items-start justify-between gap-3 text-xs pb-2.5 border-b border-[#EDE9E1] last:border-b-0 last:pb-0"
                  >
                    <div className="space-y-0.5 min-w-0">
                      <div className="font-semibold text-[#243247] truncate">
                        {formatActivityAction(act.action)}
                      </div>
                      <div className="text-[11px] text-[#5E6B7D] truncate">
                        by {act.actor_name || 'System'}
                      </div>
                    </div>
                    <div className="text-[11px] font-mono text-[#8C98A9] shrink-0 whitespace-nowrap">
                      {formatRelativeTime(act.timestamp)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  </div>
);
};

export default DashboardPage;
