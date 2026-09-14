import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { getStudentAssessments, startAssessmentAttempt } from '../../api/assessments';
import { ResultsAPI } from '../../api/results';
import { StudentAssessmentItem } from '../../types/assessment';
import { AssessmentResult } from '../../types/results';
import { Button } from '../../components/common/Button';
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
  RefreshCw
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

  const candidateDisplayName = user?.display_name || user?.first_name || (user?.email ? user.email.split('@')[0] : 'Candidate');

  return (
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

        <div className="flex flex-wrap items-center justify-between gap-4 pt-1 border-b border-[#DDD8CE] pb-3">
          <div className="flex items-center gap-3">
            <h1 className="text-lg sm:text-xl font-bold text-[#243247] tracking-tight">
              Student Workspace
            </h1>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-semibold bg-[#EDE9E1] text-[#243247] border border-[#DDD8CE]">
              Candidate
            </span>
            <button
              type="button"
              onClick={loadDashboardData}
              disabled={isLoading}
              title="Refresh Workspace Data"
              className="p-1.5 rounded-md text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1] transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {/* Quick Nav Tabs */}
          <div className="flex items-center gap-1 bg-[#FAF9F6] p-1 rounded-xl border border-[#DDD8CE] text-xs font-medium">
            <Link to="/student" className="px-3 py-1.5 rounded-lg bg-[#2878D8] text-white font-semibold shadow-xs">
              Dashboard
            </Link>
            <Link to="/student/assessments" className="px-3 py-1.5 rounded-lg text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1] transition-colors">
              My Assessments
            </Link>
            <Link to="/student/certificates" className="px-3 py-1.5 rounded-lg text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1] transition-colors">
              Certificates
            </Link>
            <Link to="/student/privacy" className="px-3 py-1.5 rounded-lg text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1] transition-colors">
              Privacy &amp; Rights
            </Link>
            <Link to="/student/profile" className="px-3 py-1.5 rounded-lg text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1] transition-colors">
              Profile
            </Link>
          </div>
        </div>
      </div>

      {/* ============================================================
          2. GREETING & CANDIDATE IDENTITY BANNER
          ============================================================ */}
      <div className="p-6 sm:p-8 bg-[#FAF9F6] rounded-2xl border border-[#DDD8CE] shadow-xs space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-md text-xs font-semibold bg-[#EEF5FC] text-[#2878D8] border border-[#D9DDE3]">
                Candidate Verified
              </span>
              {user?.student_profile?.roll_number && (
                <span className="px-2.5 py-0.5 rounded-md text-xs font-mono text-[#5E6B7D] bg-[#EDE9E1] border border-[#DDD8CE]">
                  Roll: {user.student_profile.roll_number}
                </span>
              )}
              <span className="px-2.5 py-0.5 rounded-md text-xs font-mono text-[#5E6B7D] bg-[#EDE9E1] border border-[#DDD8CE]">
                EUID: {user?.student_profile?.euid || user?.id || 'EU-CANDIDATE'}
              </span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-[#243247] tracking-tight font-sans">
              Welcome back, {candidateDisplayName}.
            </h2>
            <p className="text-xs sm:text-sm text-[#5E6B7D] leading-relaxed max-w-2xl">
              Access your scheduled examinations, resume in-progress sessions, and review authoritative evaluation results across ExamIIO.
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <Link to="/student/assessments">
              <Button variant="primary" size="md" className="flex items-center gap-2">
                <span>View All Exams</span>
                <ArrowRight className="w-4 h-4" />
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* ============================================================
          3. METRICS RIBBON (4 Metric Cards)
          ============================================================ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-[#FAF9F6] border border-[#DDD8CE] shadow-xs flex items-center gap-4">
          <div className="w-11 h-11 rounded-lg bg-[#EDE9E1] border border-[#DDD8CE] text-[#2878D8] flex items-center justify-center shrink-0">
            <FileCode className="w-5 h-5" />
          </div>
          <div>
            <div className="text-2xl font-bold text-[#243247] font-sans">
              {availableAssessments.length}
            </div>
            <div className="text-xs text-[#5E6B7D]">Available Exams</div>
          </div>
        </div>

        <div className="p-5 rounded-xl bg-[#FAF9F6] border border-[#DDD8CE] shadow-xs flex items-center gap-4">
          <div className="w-11 h-11 rounded-lg bg-[#EDE9E1] border border-[#DDD8CE] text-[#D97706] flex items-center justify-center shrink-0">
            <Clock className="w-5 h-5" />
          </div>
          <div>
            <div className="text-2xl font-bold text-[#243247] font-sans">
              {inProgressAssessments.length}
            </div>
            <div className="text-xs text-[#5E6B7D]">Active / In-Progress</div>
          </div>
        </div>

        <div className="p-5 rounded-xl bg-[#FAF9F6] border border-[#DDD8CE] shadow-xs flex items-center gap-4">
          <div className="w-11 h-11 rounded-lg bg-[#EDE9E1] border border-[#DDD8CE] text-[#2FA878] flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <div className="text-2xl font-bold text-[#243247] font-sans">
              {results.length}
            </div>
            <div className="text-xs text-[#5E6B7D]">Completed Assessments</div>
          </div>
        </div>

        <div className="p-5 rounded-xl bg-[#FAF9F6] border border-[#DDD8CE] shadow-xs flex items-center gap-4">
          <div className="w-11 h-11 rounded-lg bg-[#EDE9E1] border border-[#DDD8CE] text-amber-700 flex items-center justify-center shrink-0">
            <Award className="w-5 h-5" />
          </div>
          <div>
            <div className="text-2xl font-bold text-[#243247] font-sans">
              {coinsSummary?.total_coins ?? 0}
            </div>
            <div className="text-xs text-[#5E6B7D]">Craft Coins Earned</div>
          </div>
        </div>
      </div>

      {/* ============================================================
          4. COINS & MILESTONE PROGRESSION CARD
          ============================================================ */}
      <div className="p-6 bg-[#FAF9F6] rounded-2xl border border-[#DDD8CE] shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-base font-bold text-[#243247]">🪙 Craft Coins &amp; Milestone Progression</span>
              <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-[#EDE9E1] text-[#2878D8] border border-[#DDD8CE]">
                +3 Coins / Correct Question
              </span>
            </div>
            <p className="text-xs text-[#5E6B7D]">
              Solve examination questions accurately to accumulate verified achievement tokens and advance your milestone level.
            </p>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={handleOpenLeaderboard}
            className="flex items-center gap-1.5 text-xs font-semibold"
          >
            <Trophy className="w-3.5 h-3.5 text-[#2878D8]" />
            <span>View Society Leaderboard</span>
          </Button>
        </div>

        {/* Milestone Steps Bar */}
        <div className="space-y-2 pt-2">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-[#5E6B7D]">
              Current: <strong className="text-[#243247]">{coinsSummary?.total_coins ?? 0} Coins</strong> ({coinsSummary?.correct_questions_count ?? 0} verified solutions)
            </span>
            <span className="text-[#5E6B7D]">
              Next Milestone: <strong className="text-[#243247]">{coinsSummary?.milestone_progress?.next_milestone ?? 50} Coins</strong>
              {coinsSummary?.milestone_progress?.remaining_coins !== undefined && (
                <span className="text-[#2878D8] font-medium ml-1.5">
                  ({coinsSummary.milestone_progress.remaining_coins} more to reach next tier)
                </span>
              )}
            </span>
          </div>

          {/* Progress Bar Container */}
          <div className="w-full h-2.5 bg-[#EDE9E1] rounded-full overflow-hidden border border-[#DDD8CE]">
            <div
              className="h-full bg-[#2878D8] rounded-full transition-all duration-500"
              style={{ width: `${Math.min(100, Math.max(0, coinsSummary?.milestone_progress?.progress_percent ?? 0))}%` }}
            />
          </div>

          {/* Milestone markers */}
          <div className="flex justify-between items-center text-[11px] font-mono text-[#5E6B7D] pt-0.5">
            <span className={((coinsSummary?.total_coins ?? 0) >= 0) ? 'font-bold text-[#243247]' : ''}>0</span>
            <span className={((coinsSummary?.total_coins ?? 0) >= 50) ? 'font-bold text-[#243247]' : ''}>50</span>
            <span className={((coinsSummary?.total_coins ?? 0) >= 100) ? 'font-bold text-[#243247]' : ''}>100</span>
            <span className={((coinsSummary?.total_coins ?? 0) >= 250) ? 'font-bold text-[#243247]' : ''}>250</span>
            <span className={((coinsSummary?.total_coins ?? 0) >= 500) ? 'font-bold text-[#243247]' : ''}>500</span>
          </div>
        </div>
      </div>

      {/* Error Alert Banner if start attempt failed */}
      {startErrorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-start justify-between gap-4 text-rose-800 text-xs shadow-xs animate-fadeIn">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-bold text-rose-900 text-sm">Unable to Start Assessment</h4>
              <p className="mt-1 text-rose-700 font-sans">{startErrorMessage}</p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={() => setStartErrorMessage(null)}>
            Dismiss
          </Button>
        </div>
      )}

      {/* ============================================================
          5. ACTIVE / IN-PROGRESS ASSESSMENT BANNER
          ============================================================ */}
      {inProgressAssessments.length > 0 && (
        <div className="p-5 rounded-2xl bg-[#FEF3C7]/40 border border-[#FDE68A] space-y-3">
          <div className="flex items-center gap-2 text-amber-900 font-bold text-sm">
            <Clock className="w-4 h-4 text-amber-700" />
            <span>Active Assessment Session In Progress</span>
          </div>
          <p className="text-xs text-amber-800">
            You have an open test attempt currently in progress. Your timer continues counting down on the server.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
            {inProgressAssessments.map((item) => (
              <div
                key={item.id}
                className="p-4 rounded-xl bg-white border border-[#DDD8CE] shadow-xs flex items-center justify-between gap-4"
              >
                <div>
                  <div className="text-sm font-bold text-[#243247]">{item.title}</div>
                  <div className="text-xs text-[#5E6B7D] font-mono mt-0.5">
                    Duration: {item.duration_minutes} Mins
                  </div>
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  className="bg-[#2878D8] hover:bg-[#2065B8] flex items-center gap-1.5 shrink-0"
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
          6. SCHEDULED EXAMINATIONS
          ============================================================ */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-[#243247]">Your Scheduled Examinations</h3>
            <span className="text-xs px-2 py-0.5 rounded-full bg-[#EDE9E1] text-[#243247] font-mono border border-[#DDD8CE]">
              {assessments.length}
            </span>
          </div>
          <Link to="/student/assessments" className="text-xs font-semibold text-[#2878D8] hover:text-[#2065B8] flex items-center gap-1">
            <span>View All</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {isLoading ? (
          <div className="p-12 rounded-xl bg-[#FAF9F6] border border-[#DDD8CE] text-center text-xs text-[#5E6B7D] shadow-xs">
            Loading scheduled examinations...
          </div>
        ) : assessments.length === 0 ? (
          <div className="p-8 rounded-2xl bg-[#FAF9F6] border border-[#DDD8CE] text-center space-y-3 shadow-xs">
            <div className="w-10 h-10 rounded-full bg-[#EDE9E1] text-[#5E6B7D] mx-auto flex items-center justify-center">
              <FileCode className="w-5 h-5" />
            </div>
            <h4 className="text-sm font-semibold text-[#243247]">No Assigned Assessments</h4>
            <p className="text-xs text-[#5E6B7D] max-w-sm mx-auto">
              You currently have no pending assessments assigned to your candidate profile. 
              Assessments will appear here once scheduled by your instructor or institution.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {assessments.map((item) => {
              const status = getStatus(item);
              return (
                <div
                  key={item.id}
                  className="p-6 rounded-2xl bg-white border border-[#DDD8CE] shadow-xs space-y-4 hover:border-[#2878D8]/50 transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1">
                      <h4 className="text-base font-bold text-[#243247]">{item.title}</h4>
                      <p className="text-xs text-[#5E6B7D] line-clamp-2">{item.description}</p>
                    </div>
                    <span
                      className={`px-2.5 py-0.5 rounded-md text-xs font-semibold shrink-0 border ${
                        status === 'IN_PROGRESS'
                          ? 'bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]'
                          : status === 'COMPLETED'
                          ? 'bg-[#E8F5F3] text-[#1F855C] border-[#A7F3D0]'
                          : 'bg-[#EEF5FC] text-[#2878D8] border-[#D9DDE3]'
                      }`}
                    >
                      {status.replace('_', ' ')}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-4 text-xs text-[#5E6B7D] font-mono pt-2 border-t border-[#EDE9E1]">
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-[#5E6B7D]" />
                      <span>{item.duration_minutes} Mins</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-[#5E6B7D]" />
                      <span>{new Date(item.start_datetime).toLocaleDateString()}</span>
                    </div>
                  </div>

                  <div className="pt-2">
                    {status === 'IN_PROGRESS' ? (
                      <Button
                        variant="primary"
                        size="sm"
                        className="w-full flex items-center justify-center gap-2 bg-[#2878D8] hover:bg-[#2065B8] text-white"
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
                        <CheckCircle2 className="w-3.5 h-3.5 text-[#2FA878]" />
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
                </div>
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
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-[#243247]">Recent Assessment Results</h3>
            <span className="text-xs px-2 py-0.5 rounded-full bg-[#EDE9E1] text-[#243247] font-mono border border-[#DDD8CE]">
              {results.length}
            </span>
          </div>
          {results.length > 0 && (
            <Link to="/student/certificates" className="text-xs font-semibold text-[#2878D8] hover:text-[#2065B8] flex items-center gap-1">
              <span>View Certificates</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          )}
        </div>

        {isLoading ? (
          <div className="p-8 rounded-xl bg-[#FAF9F6] border border-[#DDD8CE] text-center text-xs text-[#5E6B7D] shadow-xs">
            Loading examination results...
          </div>
        ) : results.length === 0 ? (
          <div className="p-6 rounded-2xl bg-[#FAF9F6] border border-[#DDD8CE] text-center space-y-2 shadow-xs">
            <p className="text-xs text-[#5E6B7D]">
              No finalized results published yet. Results become accessible after institutional evaluation release.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {results.slice(0, 3).map((res) => (
              <div
                key={res.id}
                className="p-4 rounded-xl bg-white border border-[#DDD8CE] shadow-xs flex items-center justify-between gap-4"
              >
                <div className="space-y-0.5">
                  <div className="text-sm font-semibold text-[#243247]">{res.assessment_title}</div>
                  <div className="text-xs text-[#5E6B7D] font-mono">
                    Score: <strong className="text-[#243247]">{res.total_score_earned}</strong> / {res.total_possible_score} ({res.percentage}%)
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`px-2.5 py-0.5 rounded-md text-xs font-semibold border ${
                      res.is_passed
                        ? 'bg-[#E8F5F3] text-[#1F855C] border-[#A7F3D0]'
                        : 'bg-[#FEF2F2] text-[#DC2626] border-[#FECACA]'
                    }`}
                  >
                    {res.is_passed ? 'PASSED' : 'NOT PASSED'}
                  </span>
                  <Link to={`/student/results/${res.id}`}>
                    <Button variant="outline" size="sm">
                      View Scorecard
                    </Button>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ============================================================
          8. LEADERBOARD MODAL
          ============================================================ */}
      {isLeaderboardOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs overflow-y-auto animate-fadeIn">
          <div className="max-w-2xl w-full p-6 space-y-5 border border-[#DDD8CE] shadow-2xl relative my-8 bg-[#FAF9F6] rounded-2xl">
            <button
              onClick={() => setIsLeaderboardOpen(false)}
              className="absolute top-4 right-4 text-[#5E6B7D] hover:text-[#243247] font-bold p-1 rounded-lg hover:bg-[#EDE9E1] transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-3 border-b border-[#DDD8CE] pb-4">
              <div className="w-10 h-10 rounded-xl bg-[#EDE9E1] border border-[#DDD8CE] text-[#2878D8] flex items-center justify-center">
                <Trophy className="w-5 h-5 text-[#2878D8]" />
              </div>
              <div>
                <h3 className="text-base font-bold text-[#243247]">Craft Society Student Leaderboard</h3>
                <p className="text-xs text-[#5E6B7D]">Ranked deterministically by verified coins earned</p>
              </div>
            </div>

            {isLoadingLeaderboard ? (
              <div className="py-12 text-center text-xs text-[#5E6B7D] font-mono animate-pulse">
                Loading society leaderboard...
              </div>
            ) : leaderboardData.length === 0 ? (
              <div className="py-12 text-center text-xs text-[#5E6B7D] font-sans">
                No students on the leaderboard yet. Complete assessments to earn coins!
              </div>
            ) : (
              <div className="max-h-80 overflow-y-auto divide-y divide-[#EDE9E1] border border-[#DDD8CE] rounded-xl bg-white">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-[#FAF9F6] text-[#5E6B7D] border-b border-[#DDD8CE] text-[11px] uppercase font-semibold">
                    <tr>
                      <th className="p-3 w-14 text-center">Rank</th>
                      <th className="p-3">Candidate</th>
                      <th className="p-3">Roll Number</th>
                      <th className="p-3 text-right">Coins</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#EDE9E1] text-[#243247]">
                    {leaderboardData.map((item, index) => {
                      const isTop3 = item.rank <= 3;
                      return (
                        <tr key={`${item.rank}-${item.roll_number || index}`} className={`hover:bg-[#FAF9F6] ${isTop3 ? 'bg-[#EEF5FC]/40' : ''}`}>
                          <td className="p-3 text-center font-bold">
                            {item.rank === 1 ? '🥇' : item.rank === 2 ? '🥈' : item.rank === 3 ? '🥉' : `#${item.rank}`}
                          </td>
                          <td className="p-3 font-sans font-semibold text-[#243247]">
                            {item.name || 'Candidate'}
                          </td>
                          <td className="p-3 text-[#5E6B7D]">{item.roll_number}</td>
                          <td className="p-3 text-right font-bold text-[#2878D8]">
                            🪙 {item.coins}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            <div className="flex justify-end pt-2 border-t border-[#DDD8CE]">
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-fadeIn">
          <div className="max-w-md w-full p-6 space-y-5 border border-[#DDD8CE] bg-white shadow-2xl rounded-2xl">
            <div className="flex items-start justify-between gap-3 border-b border-[#EDE9E1] pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-[#EEF5FC] text-[#2878D8] border border-[#D9DDE3]">
                  <BookOpen className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-[#243247]">Start Examination</h3>
                  <p className="text-xs text-[#5E6B7D]">Confirm test session initialization</p>
                </div>
              </div>
              <button
                onClick={() => setPendingStartAssessment(null)}
                className="p-1 rounded-lg text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1] transition-colors"
                disabled={Boolean(isStartingId)}
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs text-[#5E6B7D]">
              <div className="p-3.5 rounded-xl bg-[#FAF9F6] border border-[#DDD8CE] space-y-2">
                <div className="font-bold text-sm text-[#243247]">{pendingStartAssessment.title}</div>
                {pendingStartAssessment.description && (
                  <p className="text-[#5E6B7D] line-clamp-2">{pendingStartAssessment.description}</p>
                )}
                <div className="flex flex-wrap items-center gap-4 pt-2 border-t border-[#DDD8CE] font-mono text-[11px] text-[#243247]">
                  <div className="flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-[#2878D8]" />
                    <span>Duration: <strong>{pendingStartAssessment.duration_minutes} Mins</strong></span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Award className="w-3.5 h-3.5 text-[#2FA878]" />
                    <span>Points: <strong>{pendingStartAssessment.total_points}</strong></span>
                  </div>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-[#EDE9E1] border border-[#DDD8CE] text-[#243247] space-y-1.5">
                <div className="font-semibold flex items-center gap-1.5 text-[#243247]">
                  <Shield className="w-4 h-4 text-[#2878D8]" />
                  <span>Exam Integrity Notice</span>
                </div>
                <p className="text-[11px] leading-relaxed text-[#5E6B7D]">
                  Your examination timer will begin immediately upon starting. Fullscreen mode and continuous AI proctoring telemetry will be active throughout your attempt.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2 border-t border-[#EDE9E1]">
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
