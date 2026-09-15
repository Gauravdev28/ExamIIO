import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { AdminAPI } from '../api/admin';
import { getQuestions } from '../api/questions';
import { AdminDashboardOverview } from '../types/admin';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { StatCard } from '../components/common/StatCard';
import { EmptyState } from '../components/common/EmptyState';
import { Skeleton } from '../components/common/Skeleton';
import {
  FileCode,
  Plus,
  Users,
  ArrowRight,
  BookOpen,
  ShieldCheck,
  RefreshCw,
  Clock,
  ExternalLink,
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

  // Time-aware greeting logic
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

  // Render Status Badge
  const renderStatusBadge = (status: string) => {
    switch (status) {
      case 'LIVE':
        return (
          <Badge variant="emerald" size="sm" dot>
            Live
          </Badge>
        );
      case 'SCHEDULED':
        return (
          <Badge variant="blue" size="sm">
            Scheduled
          </Badge>
        );
      case 'COMPLETED':
        return (
          <Badge variant="neutral" size="sm">
            Completed
          </Badge>
        );
      default:
        return (
          <Badge variant="neutral" size="sm">
            {status}
          </Badge>
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
    <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* ============================================================
          1. HEADER & REFRESH ACTION
          ============================================================ */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-warm-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold tracking-widest text-brand-600 uppercase">
              ExamIIO Administration
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-brand-400" />
            <span className="text-xs text-navy-400 font-medium">Institutional Console</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold font-display text-navy-900 tracking-tight mt-1">
            {getGreeting()}, {displayName}.
          </h1>
          <p className="text-xs sm:text-sm text-navy-600 mt-1">
            Real-time overview of active assessments, candidates, and proctoring telemetry across ExamIIO.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="secondary"
            size="sm"
            onClick={loadDashboardData}
            disabled={isLoading}
            className="flex items-center gap-2"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-brand-600' : 'text-navy-500'}`} />
            <span>{isLoading ? 'Syncing...' : 'Sync Overview'}</span>
          </Button>
          <Link to="/admin/assessments/create">
            <Button variant="primary" size="sm" className="flex items-center gap-1.5">
              <Plus className="w-3.5 h-3.5" />
              <span>Create Assessment</span>
            </Button>
          </Link>
        </div>
      </div>

      {/* ============================================================
          2. PRIMARY KPI METRIC CARDS
          ============================================================ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Active Assessments"
          value={isLoading ? '—' : formatKpiNumber(overview?.metrics.active_assessments ?? 0)}
          subtitle="Currently live examination windows"
          icon={FileCode}
          color="blue"
        />
        <StatCard
          title="Candidates"
          value={isLoading ? '—' : formatKpiNumber(overview?.metrics.total_students ?? 0)}
          subtitle="Registered institutional examinees"
          icon={Users}
          color="emerald"
        />
        <StatCard
          title="Question Bank"
          value={isLoading ? '—' : questionsCount !== null ? formatKpiNumber(questionsCount) : '—'}
          subtitle="Authoritative evaluation items"
          icon={BookOpen}
          color="amber"
        />
        <StatCard
          title="Invigilators"
          value={isLoading ? '—' : 'Active'}
          subtitle="Proctor telemetry active"
          icon={ShieldCheck}
          color="violet"
        />
      </div>

      {/* ============================================================
          3. RESTRAINED QUICK ACTIONS TOOLBAR
          ============================================================ */}
      <div className="flex flex-wrap items-center gap-3 pt-1">
        <Link to="/admin/assessments/create">
          <Button variant="primary" size="sm" className="flex items-center gap-1.5">
            <Plus className="w-3.5 h-3.5" />
            <span>New Assessment</span>
          </Button>
        </Link>
        <Link to="/admin/questions">
          <Button variant="secondary" size="sm" className="flex items-center gap-1.5">
            <BookOpen className="w-3.5 h-3.5 text-brand-600" />
            <span>Question Bank</span>
          </Button>
        </Link>
        <Link to="/admin/students">
          <Button variant="secondary" size="sm" className="flex items-center gap-1.5">
            <Users className="w-3.5 h-3.5 text-emerald-600" />
            <span>Manage Students</span>
          </Button>
        </Link>
        <Link to="/admin/results">
          <Button variant="secondary" size="sm" className="flex items-center gap-1.5">
            <ExternalLink className="w-3.5 h-3.5 text-navy-500" />
            <span>Results &amp; Analytics</span>
          </Button>
        </Link>
      </div>

      {/* ============================================================
          4. MAIN WORKSPACE: ASSESSMENT ACTIVITY & AUDIT LOG
          ============================================================ */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Left 2 Columns: Assessment Activity */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-warm-200">
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold font-display text-navy-900">
                Assessment Activity
              </h3>
              <Badge variant="blue" size="sm">
                {assessmentsList.length}
              </Badge>
            </div>
            <Link
              to="/admin/assessments"
              className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1 transition-colors"
            >
              <span>View All</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <Card variant="warm" className="overflow-hidden p-0">
            {isLoading ? (
              <div className="p-8">
                <Skeleton className="h-40 rounded-xl" />
              </div>
            ) : assessmentsList.length === 0 ? (
              <EmptyState
                icon={FileCode}
                title="No assessments yet"
                description="Create your first technical assessment to begin evaluating candidates."
                actionLabel="Create Assessment"
                onAction={() => window.location.assign('/admin/assessments/create')}
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-canvas-subtle border-b border-warm-200 text-navy-500 font-semibold uppercase text-[11px]">
                    <tr>
                      <th className="px-5 py-3.5 text-left">Assessment</th>
                      <th className="px-5 py-3.5 text-left">Status</th>
                      <th className="px-5 py-3.5 text-right">Candidates</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-warm-100">
                    {assessmentsList.map((a) => {
                      const operationalStatus = getAssessmentStatus(a);
                      return (
                        <tr
                          key={a.id}
                          className="hover:bg-warm-100/60 transition-colors"
                        >
                          <td className="px-5 py-4 text-left">
                            <Link
                              to={`/admin/assessments/${a.id}`}
                              className="font-bold text-xs sm:text-sm text-navy-900 hover:text-brand-600 transition-colors line-clamp-1"
                              title={a.title}
                            >
                              {a.title}
                            </Link>
                            {a.start_datetime && (
                              <div className="flex items-center gap-1 text-[11px] text-navy-400 font-mono mt-0.5">
                                <Clock className="w-3 h-3 text-navy-400" />
                                <span>{new Date(a.start_datetime).toLocaleDateString()}</span>
                              </div>
                            )}
                          </td>
                          <td className="px-5 py-4 text-left whitespace-nowrap">
                            {renderStatusBadge(operationalStatus)}
                          </td>
                          <td className="px-5 py-4 text-right font-mono text-xs font-bold text-navy-800">
                            {a.candidates_count}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        {/* Right 1 Column: Recent Activity */}
        <div className="space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-warm-200">
            <h3 className="text-base font-bold font-display text-navy-900">
              Recent Activity
            </h3>
            <Link
              to="/admin/retention"
              className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1 transition-colors"
            >
              <span>Audit Log</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <Card variant="warm" className="p-5">
            {isLoading ? (
              <Skeleton className="h-40 rounded-xl" />
            ) : activityList.length === 0 ? (
              <div className="py-8 px-2 text-center space-y-1">
                <div className="text-xs font-semibold text-navy-900">
                  No recent activity
                </div>
                <p className="text-xs text-navy-500 leading-relaxed">
                  Activity will appear here as administrators work across ExamIIO.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {activityList.slice(0, 6).map((act) => (
                  <div
                    key={act.id}
                    className="flex items-start justify-between gap-3 text-xs pb-3 border-b border-warm-100 last:border-b-0 last:pb-0"
                  >
                    <div className="space-y-0.5 min-w-0">
                      <div className="font-semibold text-navy-900 truncate">
                        {formatActivityAction(act.action)}
                      </div>
                      <div className="text-[11px] text-navy-500 truncate">
                        by {act.actor_name || 'System'}
                      </div>
                    </div>
                    <div className="text-[11px] font-mono text-navy-400 shrink-0 whitespace-nowrap">
                      {formatRelativeTime(act.timestamp)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
