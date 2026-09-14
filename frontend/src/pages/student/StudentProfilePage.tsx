import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { fetchStudentSelfProfile, changeUserPassword } from '../../api/students';
import { getStudentAssessments } from '../../api/assessments';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import {
  UserCheck,
  KeyRound,
  AlertCircle,
  CheckCircle2,
  FileText,
  Clock,
  Calendar,
  Play,
} from 'lucide-react';
import { StudentProfile } from '../../types/student';
import { StudentAssessmentItem } from '../../types/assessment';

export const StudentProfilePage: React.FC = () => {
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [assignedAssessments, setAssignedAssessments] = useState<StudentAssessmentItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isChangingPass, setIsChangingPass] = useState(false);
  const [passError, setPassError] = useState<string | null>(null);
  const [passSuccess, setPassSuccess] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [profileRes, assessmentsRes] = await Promise.all([
          fetchStudentSelfProfile(),
          getStudentAssessments().catch(() => ({ data: [] })),
        ]);
        if (profileRes.data) {
          setProfile(profileRes.data);
        }
        if (assessmentsRes.data) {
          setAssignedAssessments(assessmentsRes.data);
        }
      } catch (err: any) {
        console.error("Failed to load student profile:", err);
      } finally {
        setIsLoading(false);
      }
    };
    loadData();
  }, []);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPassError(null);
    setPassSuccess(null);

    if (newPassword !== confirmPassword) {
      setPassError('New password and confirmation do not match.');
      return;
    }

    if (newPassword.length < 8) {
      setPassError('Password must be at least 8 characters.');
      return;
    }

    setIsChangingPass(true);
    try {
      await changeUserPassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      setPassSuccess('Your password has been successfully updated.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      const msg =
        err.error?.details?.new_password?.[0] ||
        err.error?.details?.current_password?.[0] ||
        err.error?.message ||
        'Failed to update password.';
      setPassError(msg);
    } finally {
      setIsChangingPass(false);
    }
  };

  if (isLoading) {
    return (
      <div className="py-20 flex justify-center text-slate-400">
        <svg className="animate-spin h-8 w-8 text-brand-400" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      </div>
    );
  }

  return (
    <div className="w-full px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div className="border-b border-slate-200 pb-4">
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Student Profile</h1>
        <p className="text-xs text-slate-500 mt-1 font-mono">
          Exam Unique Identifier & Academic Credentials
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Student Identity Card */}
        <Card className="p-6 space-y-5 bg-white border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between pb-4 border-b border-slate-200">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200">
                <UserCheck className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900">Student Identification</h3>
                <p className="text-xs text-slate-500 font-mono">ExamIIO Candidate</p>
              </div>
            </div>
            <Badge variant="success">ACTIVE</Badge>
          </div>

          <div className="space-y-3 text-xs font-mono">
            <div className="flex justify-between py-2 border-b border-slate-100">
              <span className="text-slate-500">Exam Unique ID (EUID)</span>
              <span className="text-emerald-700 font-bold">{profile?.euid || 'N/A'}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-100">
              <span className="text-slate-500">Roll Number</span>
              <span className="text-slate-900 font-semibold">{profile?.roll_number || 'N/A'}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-100">
              <span className="text-slate-500">Email Address</span>
              <span className="text-slate-700">{profile?.email || 'N/A'}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-100 items-center">
              <span className="text-slate-500">Craft Coins Earned</span>
              <span className="text-amber-700 font-bold font-mono bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                🪙 {profile?.coins ?? 0}
              </span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-slate-500">Account Enrolled</span>
              <span className="text-slate-600">
                {profile?.created_at ? new Date(profile.created_at).toLocaleDateString() : 'N/A'}
              </span>
            </div>
          </div>
        </Card>

        {/* Password Management Card */}
        <Card className="p-6 space-y-5 bg-white border border-slate-200 shadow-sm">
          <div className="flex items-center gap-3 pb-4 border-b border-slate-200">
            <div className="p-2.5 rounded-xl bg-amber-50 text-amber-700 border border-amber-200">
              <KeyRound className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Security & Password</h3>
              <p className="text-xs text-slate-500">Update account credentials</p>
            </div>
          </div>

          {passError && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 flex items-start gap-2 text-rose-800 text-xs">
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
              <span>{passError}</span>
            </div>
          )}

          {passSuccess && (
            <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 flex items-start gap-2 text-emerald-800 text-xs">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
              <span>{passSuccess}</span>
            </div>
          )}

          <form onSubmit={handleChangePassword} className="space-y-3 text-xs">
            <div className="space-y-1">
              <label className="text-slate-700 font-medium">Current Password</label>
              <input
                type="password"
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>
            <div className="space-y-1">
              <label className="text-slate-700 font-medium">New Password</label>
              <input
                type="password"
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="At least 8 characters"
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>
            <div className="space-y-1">
              <label className="text-slate-700 font-medium">Confirm New Password</label>
              <input
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>
            <div className="pt-2">
              <Button type="submit" variant="primary" size="sm" isLoading={isChangingPass} className="w-full">
                Update Password
              </Button>
            </div>
          </form>
        </Card>
      </div>

      {/* Authoritative Assigned Assessments Section */}
      <Card className="p-6 space-y-4 bg-white border border-slate-200 shadow-sm">
        <div className="flex items-center justify-between pb-3 border-b border-slate-200">
          <div className="flex items-center gap-2.5">
            <FileText className="w-5 h-5 text-emerald-600" />
            <h3 className="text-base font-bold text-slate-900">Assigned Technical Assessments</h3>
          </div>
          <Badge variant="neutral" size="sm">
            {assignedAssessments.length} Active {assignedAssessments.length === 1 ? 'Evaluation' : 'Evaluations'}
          </Badge>
        </div>

        {assignedAssessments.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-500 font-mono">
            No published assessments currently assigned to your account.
          </div>
        ) : (
          <div className="divide-y divide-slate-100 font-mono text-xs">
            {assignedAssessments.map((a) => (
              <div key={a.id} className="py-3.5 flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="font-sans font-bold text-slate-900 text-sm">{a.title}</div>
                  <div className="flex items-center gap-3 text-slate-500">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-amber-500" /> {a.duration_minutes}m
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5 text-emerald-500" /> {new Date(a.start_datetime).toLocaleDateString()} - {new Date(a.end_datetime).toLocaleDateString()}
                    </span>
                    <span className="text-slate-500">Attempts: {a.attempts_used} / {a.attempt_limit}</span>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <Badge variant={a.is_eligible ? 'success' : 'neutral'} size="sm">
                    {a.is_eligible ? 'ELIGIBLE' : 'LIMIT REACHED'}
                  </Badge>
                  <Link to="/student/assessments">
                    <Button variant="secondary" size="sm">
                      <Play className="w-3.5 h-3.5 mr-1 text-emerald-600" />
                      Take Assessment
                    </Button>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};

export default StudentProfilePage;
