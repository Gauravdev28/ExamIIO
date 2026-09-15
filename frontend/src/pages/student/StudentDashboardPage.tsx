import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { getStudentAssessments, startAssessmentAttempt } from '../../api/assessments';
import { ResultsAPI } from '../../api/results';
import { StudentAssessmentItem } from '../../types/assessment';
import { AssessmentResult } from '../../types/results';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { StatCard } from '../../components/common/StatCard';
import { EmptyState } from '../../components/common/EmptyState';
import { Skeleton } from '../../components/common/Skeleton';
import {
  FileCode,
  Clock,
  Calendar,
  CheckCircle2,
  Award,
  Play,
  ArrowRight,
  BookOpen,
  Trophy,
  X,
  AlertCircle,
  Shield,
  RefreshCw,
  Zap,
} from 'lucide-react';

export const StudentDashboardPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [assessments, setAssessments] = useState<StudentAssessmentItem[]>([]);
  const [results, setResults] = useState<AssessmentResult[]>([]);
  const [coinsSummary, setCoinsSummary] = useState<{
    total_coins: number;
    correct_questions_count: number;
    milestone_progress: {
      current_coins: number;
      next_milestone: number;
      progress_percent: number;
      remaining_coins: number;
    };
  } | null>(null);

  const [isLeaderboardOpen, setIsLeaderboardOpen] = useState(false);
  const [leaderboardData, setLeaderboardData] = useState<Array<{
    rank: number;
    student_id?: string;
    name: string;
    roll_number: string;
    coins: number;
    is_current_user?: boolean;
  }>>([]);
  const [isLoadingLeaderboard, setIsLoadingLeaderboard] = useState(false);

  const [isLoading, setIsLoading] = useState(true);
  const [isStartingId, setIsStartingId] = useState<string | null>(null);
  const [pendingStartAssessment, setPendingStartAssessment] = useState<StudentAssessmentItem | null>(null);
  const [startErrorMessage, setStartErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setIsLoading(true);
    setStartErrorMessage(null);
    try {
      const [assessmentRes, resultsRes, coinsRes] = await Promise.allSettled([
        getStudentAssessments(),
        ResultsAPI.getStudentResults(1),
        ResultsAPI.getStudentCoinsSummary(),
      ]);

      if (assessmentRes.status === 'fulfilled' && assessmentRes.value.data) {
        setAssessments(assessmentRes.value.data);
      }

      if (resultsRes.status === 'fulfilled' && resultsRes.value?.results) {
        setResults(resultsRes.value.results);
      }

      if (coinsRes.status === 'fulfilled' && coinsRes.value) {
        setCoinsSummary(coinsRes.value);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenLeaderboard = async () => {
    setIsLeaderboardOpen(true);
    setIsLoadingLeaderboard(true);
    try {
      const res = await ResultsAPI.getStudentCoinsLeaderboard();
      if (res?.leaderboard) {
        setLeaderboardData(res.leaderboard);
      }
    } catch (err) {
      console.error('Failed to load leaderboard', err);
    } finally {
      setIsLoadingLeaderboard(false);
    }
  };

  const handleStartAttempt = (item: StudentAssessmentItem) => {
    setStartErrorMessage(null);
    if (item.active_attempt_id) {
      navigate(`/student/room/${item.active_attempt_id}`);
      return;
    }
    setPendingStartAssessment(item);
  };

  const handleConfirmStartAttempt = async () => {
    if (!pendingStartAssessment) return;
    const aId = pendingStartAssessment.id;
    setIsStartingId(aId);
    setStartErrorMessage(null);
    try {
      const res = await startAssessmentAttempt(aId);
      if (res.data?.attempt_id) {
        setPendingStartAssessment(null);
        navigate(`/student/room/${res.data.attempt_id}`);
      }
    } catch (err: any) {
      console.error('Failed to start assessment attempt:', err);
      const msg = err.error?.message || err.message || 'Unable to start this assessment. Please try again.';
      setStartErrorMessage(msg);
      setPendingStartAssessment(null);
    } finally {
      setIsStartingId(null);
    }
  };

  const getStatus = (item: StudentAssessmentItem): 'IN_PROGRESS' | 'COMPLETED' | 'AVAILABLE' => {
    if (item.active_attempt_id) return 'IN_PROGRESS';
    if (item.attempts_used >= item.attempt_limit && item.attempt_limit > 0) return 'COMPLETED';
    return 'AVAILABLE';
  };

  const inProgressAssessments = assessments.filter((a) => getStatus(a) === 'IN_PROGRESS');
  const availableAssessments = assessments.filter((a) => getStatus(a) === 'AVAILABLE');

  const candidateDisplayName =
    user?.display_name || user?.first_name || (user?.email ? user.email.split('@')[0] : 'Candidate');

  return (
    <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* ============================================================
          1. HEADER & REFRESH ACTION
          ============================================================ */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-warm-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold tracking-widest text-brand-600 uppercase">
              ExamIIO Candidate Portal
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-brand-400" />
            <span className="text-xs text-navy-400 font-medium">Authoritative Session</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold font-display text-navy-900 tracking-tight mt-1">
            Student Workspace
          </h1>
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
            <span>{isLoading ? 'Syncing...' : 'Sync Data'}</span>
          </Button>
          <Link to="/student/assessments">
            <Button variant="primary" size="sm" className="flex items-center gap-1.5">
              <span>View All Exams</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          </Link>
        </div>
      </div>

      {/* ============================================================
          2. CANDIDATE GREETING & VERIFIED IDENTITY HERO
          ============================================================ */}
      <div className="relative overflow-hidden rounded-2xl bg-surface border border-warm-200 p-6 sm:p-8 shadow-warm-sm">
        {/* Subtle decorative background shapes */}
        <div className="absolute -top-12 -right-12 w-64 h-64 rounded-full bg-brand-500/5 blur-2xl pointer-events-none" />
        <div className="absolute -bottom-10 right-24 w-48 h-48 rounded-full bg-cyan-500/5 blur-xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-3 max-w-2xl">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="blue" size="sm" dot>
                Verified Candidate
              </Badge>
              {user?.student_profile?.roll_number && (
                <Badge variant="neutral" size="sm" className="font-mono">
                  Roll: {user.student_profile.roll_number}
                </Badge>
              )}
              <Badge variant="neutral" size="sm" className="font-mono">
                EUID: {user?.student_profile?.euid || user?.id || 'EU-CANDIDATE'}
              </Badge>
            </div>

            <div>
              <h2 className="text-2xl sm:text-3xl font-display font-bold text-navy-900 tracking-tight">
                Welcome back, {candidateDisplayName}.
              </h2>
              <p className="text-sm text-navy-600 leading-relaxed mt-1">
                Access your scheduled examinations, resume in-progress sessions, and review authoritative evaluation results across ExamIIO.
              </p>
            </div>
          </div>

          <div className="shrink-0 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <Button
              variant="outline"
              size="md"
              onClick={handleOpenLeaderboard}
              className="flex items-center justify-center gap-2"
            >
              <Trophy className="w-4 h-4 text-amber-600" />
              <span>Leaderboard</span>
            </Button>
            <Link to="/student/assessments">
              <Button variant="primary" size="md" className="w-full flex items-center justify-center gap-2">
                <span>Start Testing</span>
                <Play className="w-4 h-4" />
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* ============================================================
          3. KEY METRICS STATCARDS
          ============================================================ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Available Exams"
          value={isLoading ? '-' : availableAssessments.length}
          subtitle="Ready for attempt"
          icon={FileCode}
          color="blue"
        />
        <StatCard
          title="In-Progress"
          value={isLoading ? '-' : inProgressAssessments.length}
          subtitle="Active timers running"
          icon={Clock}
          color="amber"
        />
        <StatCard
          title="Completed"
          value={isLoading ? '-' : results.length}
          subtitle="Evaluated submissions"
          icon={CheckCircle2}
          color="emerald"
        />
        <StatCard
          title="Craft Coins"
          value={isLoading ? '-' : (coinsSummary?.total_coins ?? 0)}
          subtitle="Reward points earned"
          icon={Award}
          color="orange"
        />
      </div>

      {/* Error Alert Banner */}
      {startErrorMessage && (
        <div className="p-4 rounded-2xl bg-coral-50 border border-coral-200 flex items-start justify-between gap-4 text-coral-800 text-xs shadow-warm-xs animate-scale-in">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-coral-600 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-bold text-coral-900 text-sm">Unable to Start Assessment</h4>
              <p className="mt-1 text-coral-700">{startErrorMessage}</p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={() => setStartErrorMessage(null)}>
            Dismiss
          </Button>
        </div>
      )}

      {/* ============================================================
          4. ACTIVE / IN-PROGRESS ASSESSMENT BANNER
          ============================================================ */}
      {inProgressAssessments.length > 0 && (
        <div className="p-6 rounded-2xl bg-amber-500/10 border border-amber-300 shadow-warm-xs space-y-4">
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse" />
            <h3 className="text-base font-bold font-display text-navy-900">
              Active Assessment Session In Progress
            </h3>
          </div>
          <p className="text-xs text-navy-600 max-w-2xl">
            You have an open examination attempt currently in progress. Your timer continues counting down on the secure server.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
            {inProgressAssessments.map((item) => (
              <div
                key={item.id}
                className="p-5 rounded-xl bg-surface border border-amber-200 shadow-warm-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
              >
                <div>
                  <h4 className="text-sm font-bold text-navy-900">{item.title}</h4>
                  <div className="flex items-center gap-2 text-xs text-navy-500 font-mono mt-1">
                    <Clock className="w-3.5 h-3.5 text-amber-600" />
                    <span>Duration: {item.duration_minutes} Mins</span>
                  </div>
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  className="w-full sm:w-auto flex items-center justify-center gap-1.5 shrink-0 bg-brand-600 hover:bg-brand-700"
                  onClick={() => navigate(`/student/room/${item.active_attempt_id}`)}
                >
                  <Play className="w-3.5 h-3.5" />
                  <span>Resume Exam</span>
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ============================================================
          5. CRAFT COINS & MILESTONE PROGRESSION
          ============================================================ */}
      <Card variant="warm" className="p-6 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-base font-bold font-display text-navy-900">
                Craft Society &amp; Milestone Progression
              </span>
              <Badge variant="blue" size="sm">
                +3 Coins / Verified Solution
              </Badge>
            </div>
            <p className="text-xs text-navy-600">
              Solve examination problems accurately to accumulate verified achievement tokens and advance your candidate rank.
            </p>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={handleOpenLeaderboard}
            className="flex items-center gap-1.5"
          >
            <Trophy className="w-3.5 h-3.5 text-amber-500" />
            <span>View Society Leaderboard</span>
          </Button>
        </div>

        <div className="space-y-2 pt-2">
          <div className="flex flex-wrap items-center justify-between text-xs font-mono">
            <span className="text-navy-600">
              Current Balance: <strong className="text-navy-900">{coinsSummary?.total_coins ?? 0} Coins</strong> ({coinsSummary?.correct_questions_count ?? 0} verified solutions)
            </span>
            <span className="text-navy-600">
              Next Tier: <strong className="text-navy-900">{coinsSummary?.milestone_progress?.next_milestone ?? 50} Coins</strong>
              {coinsSummary?.milestone_progress?.remaining_coins !== undefined && (
                <span className="text-brand-600 font-medium ml-1.5">
                  ({coinsSummary.milestone_progress.remaining_coins} more coins to level up)
                </span>
              )}
            </span>
          </div>

          {/* Styled Warm Progress Bar */}
          <div className="w-full h-3 bg-warm-200 rounded-full overflow-hidden border border-warm-300 p-0.5">
            <div
              className="h-full bg-linear-to-r from-brand-600 to-cyan-500 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(100, Math.max(0, coinsSummary?.milestone_progress?.progress_percent ?? 0))}%` }}
            />
          </div>

          {/* Milestone markers */}
          <div className="flex justify-between items-center text-[11px] font-mono text-navy-400 pt-0.5">
            <span className={(coinsSummary?.total_coins ?? 0) >= 0 ? 'font-bold text-navy-900' : ''}>0 Tier</span>
            <span className={(coinsSummary?.total_coins ?? 0) >= 50 ? 'font-bold text-navy-900' : ''}>50 Bronze</span>
            <span className={(coinsSummary?.total_coins ?? 0) >= 100 ? 'font-bold text-navy-900' : ''}>100 Silver</span>
            <span className={(coinsSummary?.total_coins ?? 0) >= 250 ? 'font-bold text-navy-900' : ''}>250 Gold</span>
            <span className={(coinsSummary?.total_coins ?? 0) >= 500 ? 'font-bold text-navy-900' : ''}>500 Diamond</span>
          </div>
        </div>
      </Card>

      {/* ============================================================
          6. SCHEDULED EXAMINATIONS
          ============================================================ */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <h3 className="text-lg font-bold font-display text-navy-900">Your Scheduled Examinations</h3>
            <Badge variant="blue" size="sm">
              {assessments.length} Available
            </Badge>
          </div>
          <Link to="/student/assessments" className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1">
            <span>View All</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Skeleton className="h-48 rounded-2xl" />
            <Skeleton className="h-48 rounded-2xl" />
          </div>
        ) : assessments.length === 0 ? (
          <EmptyState
            icon={FileCode}
            title="No Assigned Assessments"
            description="You currently have no pending assessments assigned to your candidate profile. Assessments will appear here once scheduled by your instructor or institution."
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {assessments.map((item) => {
              const status = getStatus(item);
              return (
                <Card
                  key={item.id}
                  variant="interactive"
                  className="p-6 flex flex-col justify-between space-y-4"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <h4 className="text-base font-bold text-navy-900 line-clamp-1">{item.title}</h4>
                        <p className="text-xs text-navy-600 line-clamp-2">{item.description || 'Comprehensive evaluation session.'}</p>
                      </div>
                      <Badge
                        variant={
                          status === 'IN_PROGRESS'
                            ? 'amber'
                            : status === 'COMPLETED'
                            ? 'emerald'
                            : 'blue'
                        }
                        size="sm"
                      >
                        {status.replace('_', ' ')}
                      </Badge>
                    </div>

                    <div className="flex flex-wrap items-center gap-4 text-xs text-navy-500 font-mono pt-3 border-t border-warm-200">
                      <div className="flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-brand-600" />
                        <span>{item.duration_minutes} Mins</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Calendar className="w-3.5 h-3.5 text-navy-400" />
                        <span>{new Date(item.start_datetime).toLocaleDateString()}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Zap className="w-3.5 h-3.5 text-amber-500" />
                        <span>{item.total_points} Points</span>
                      </div>
                    </div>
                  </div>

                  <div className="pt-2">
                    {status === 'IN_PROGRESS' ? (
                      <Button
                        variant="primary"
                        size="sm"
                        className="w-full flex items-center justify-center gap-2"
                        onClick={() => navigate(`/student/room/${item.active_attempt_id}`)}
                      >
                        <Play className="w-3.5 h-3.5" />
                        <span>Resume In-Progress Exam</span>
                      </Button>
                    ) : status === 'COMPLETED' ? (
                      <Button
                        variant="secondary"
                        size="sm"
                        className="w-full flex items-center justify-center gap-2"
                        onClick={() => navigate('/student/assessments')}
                      >
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                        <span>View Submission Status</span>
                      </Button>
                    ) : (
                      <Button
                        variant="primary"
                        size="sm"
                        className="w-full flex items-center justify-center gap-2"
                        disabled={isStartingId === item.id}
                        isLoading={isStartingId === item.id}
                        onClick={() => handleStartAttempt(item)}
                      >
                        <Play className="w-3.5 h-3.5" />
                        <span>Enter Assessment Room</span>
                      </Button>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* ============================================================
          7. RECENT ASSESSMENT RESULTS
          ============================================================ */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <h3 className="text-lg font-bold font-display text-navy-900">Recent Assessment Results</h3>
            <Badge variant="neutral" size="sm">
              {results.length} Recorded
            </Badge>
          </div>
          {results.length > 0 && (
            <Link to="/student/certificates" className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1">
              <span>View Certificates</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          )}
        </div>

        {isLoading ? (
          <Skeleton className="h-28 rounded-2xl" />
        ) : results.length === 0 ? (
          <Card variant="warm" className="p-6 text-center">
            <p className="text-xs text-navy-500">
              No finalized results published yet. Results become accessible after institutional evaluation release.
            </p>
          </Card>
        ) : (
          <div className="space-y-3">
            {results.slice(0, 3).map((res) => (
              <Card
                key={res.id}
                variant="warm"
                className="p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="text-sm font-bold text-navy-900">{res.assessment_title}</div>
                  <div className="text-xs text-navy-500 font-mono">
                    Score: <strong className="text-navy-900">{res.total_score_earned}</strong> / {res.total_possible_score} ({res.percentage}%)
                  </div>
                </div>

                <div className="flex items-center gap-3 w-full sm:w-auto justify-between sm:justify-end">
                  <Badge variant={res.is_passed ? 'emerald' : 'coral'} size="sm">
                    {res.is_passed ? 'PASSED' : 'NOT PASSED'}
                  </Badge>
                  <Link to={`/student/results/${res.id}`}>
                    <Button variant="outline" size="sm">
                      View Scorecard
                    </Button>
                  </Link>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* ============================================================
          8. LEADERBOARD MODAL
          ============================================================ */}
      {isLeaderboardOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/40 backdrop-blur-xs overflow-y-auto animate-scale-in">
          <div className="max-w-2xl w-full p-6 space-y-5 border border-warm-200 shadow-warm-xl relative my-8 bg-surface rounded-2xl">
            <button
              onClick={() => setIsLeaderboardOpen(false)}
              className="absolute top-4 right-4 text-navy-400 hover:text-navy-900 p-1.5 rounded-lg hover:bg-warm-100 transition-colors"
              aria-label="Close leaderboard modal"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-3 border-b border-warm-200 pb-4">
              <div className="w-10 h-10 rounded-xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center">
                <Trophy className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold font-display text-navy-900">Craft Society Student Leaderboard</h3>
                <p className="text-xs text-navy-500">Ranked deterministically by verified coins earned</p>
              </div>
            </div>

            {isLoadingLeaderboard ? (
              <div className="py-12 text-center text-xs text-navy-500 font-mono">
                Loading society leaderboard...
              </div>
            ) : leaderboardData.length === 0 ? (
              <div className="py-12 text-center text-xs text-navy-500 font-sans">
                No students on the leaderboard yet. Complete assessments to earn coins!
              </div>
            ) : (
              <div className="max-h-80 overflow-y-auto divide-y divide-warm-200 border border-warm-200 rounded-xl bg-surface">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-canvas-subtle text-navy-500 border-b border-warm-200 text-[11px] uppercase font-semibold">
                    <tr>
                      <th className="p-3 w-14 text-center">Rank</th>
                      <th className="p-3">Candidate</th>
                      <th className="p-3">Roll Number</th>
                      <th className="p-3 text-right">Coins</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-warm-100 text-navy-800">
                    {leaderboardData.map((item, index) => {
                      const isTop3 = item.rank <= 3;
                      return (
                        <tr
                          key={`${item.rank}-${item.roll_number || index}`}
                          className={`hover:bg-warm-100/60 transition-colors ${
                            isTop3 ? 'bg-brand-50/50' : ''
                          }`}
                        >
                          <td className="p-3 text-center font-bold">
                            {item.rank === 1 ? '🥇' : item.rank === 2 ? '🥈' : item.rank === 3 ? '🥉' : `#${item.rank}`}
                          </td>
                          <td className="p-3 font-sans font-semibold text-navy-900">
                            {item.name || 'Candidate'}
                          </td>
                          <td className="p-3 text-navy-500">{item.roll_number}</td>
                          <td className="p-3 text-right font-bold text-brand-600">
                            🪙 {item.coins}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            <div className="flex justify-end pt-2 border-t border-warm-200">
              <Button variant="secondary" size="sm" onClick={() => setIsLeaderboardOpen(false)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================
          9. START EXAMINATION CONFIRMATION MODAL
          ============================================================ */}
      {pendingStartAssessment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/40 backdrop-blur-xs animate-scale-in">
          <div className="max-w-md w-full p-6 space-y-5 border border-warm-200 bg-surface shadow-warm-xl rounded-2xl">
            <div className="flex items-start justify-between gap-3 border-b border-warm-200 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2.5 rounded-xl bg-brand-50 text-brand-600 border border-brand-200">
                  <BookOpen className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold font-display text-navy-900">Start Examination</h3>
                  <p className="text-xs text-navy-500">Confirm test session initialization</p>
                </div>
              </div>
              <button
                onClick={() => setPendingStartAssessment(null)}
                className="p-1 rounded-lg text-navy-400 hover:text-navy-700 hover:bg-warm-100 transition-colors"
                disabled={Boolean(isStartingId)}
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs text-navy-600">
              <div className="p-4 rounded-xl bg-canvas-subtle border border-warm-200 space-y-2">
                <div className="font-bold text-sm text-navy-900">{pendingStartAssessment.title}</div>
                {pendingStartAssessment.description && (
                  <p className="text-navy-600 line-clamp-2">{pendingStartAssessment.description}</p>
                )}
                <div className="flex flex-wrap items-center gap-4 pt-2 border-t border-warm-200 font-mono text-[11px] text-navy-700">
                  <div className="flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-brand-600" />
                    <span>Duration: <strong>{pendingStartAssessment.duration_minutes} Mins</strong></span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Award className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Points: <strong>{pendingStartAssessment.total_points}</strong></span>
                  </div>
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-warm-100 border border-warm-200 text-navy-800 space-y-1.5">
                <div className="font-semibold flex items-center gap-1.5 text-navy-900">
                  <Shield className="w-4 h-4 text-brand-600" />
                  <span>Exam Integrity Notice</span>
                </div>
                <p className="text-[11px] leading-relaxed text-navy-600">
                  Your examination timer will begin immediately upon starting. Fullscreen mode and continuous AI proctoring telemetry will be active throughout your attempt.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2 border-t border-warm-200">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPendingStartAssessment(null)}
                disabled={Boolean(isStartingId)}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                isLoading={isStartingId === pendingStartAssessment.id}
                onClick={handleConfirmStartAttempt}
              >
                <Play className="w-3.5 h-3.5 mr-1.5" />
                <span>Confirm &amp; Enter Room</span>
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default StudentDashboardPage;
