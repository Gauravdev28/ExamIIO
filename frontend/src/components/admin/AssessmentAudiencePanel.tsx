import React, { useState, useEffect, useCallback, useRef } from 'react';
import { fetchStudents } from '../../api/students';
import {
  fetchAssessmentAudience,
  configureAssessmentAudience,
  previewAssessmentAudience,
} from '../../api/assessments';
import { StudentProfile } from '../../types/student';
import { AudienceResolution } from '../../types/assessment';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import {
  Users,
  UserPlus,
  Search,
  X,
  AlertCircle,
  CheckCircle2,
  Lock,
  Sparkles,
  UserCheck,
  Globe,
  UserCheck2,
} from 'lucide-react';

interface AssessmentAudiencePanelProps {
  assessmentId: string | null;
  isLocked: boolean;
  onAudienceChanged?: (resolution: AudienceResolution) => void;
  onValidationChange?: (isValid: boolean, totalEligible: number) => void;
  onSelectionChange?: (sectionIds: string[], studentIds: string[], targetAllStudents?: boolean) => void;
}

export const AssessmentAudiencePanel: React.FC<AssessmentAudiencePanelProps> = ({
  assessmentId,
  isLocked,
  onAudienceChanged,
  onValidationChange,
  onSelectionChange,
}) => {
  const onAudienceChangedRef = useRef(onAudienceChanged);
  onAudienceChangedRef.current = onAudienceChanged;

  const onValidationChangeRef = useRef(onValidationChange);
  onValidationChangeRef.current = onValidationChange;

  const onSelectionChangeRef = useRef(onSelectionChange);
  onSelectionChangeRef.current = onSelectionChange;

  const [mode, setMode] = useState<'ALL_STUDENTS' | 'SPECIFIC'>('ALL_STUDENTS');
  const [selectedStudentIds, setSelectedStudentIds] = useState<string[]>([]);
  const [resolution, setResolution] = useState<AudienceResolution | null>(null);

  // Student search & picker state
  const [availableStudents, setAvailableStudents] = useState<StudentProfile[]>([]);
  const [studentSearch, setStudentSearch] = useState('');
  const [isStudentPickerOpen, setIsStudentPickerOpen] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Initial load: existing audience for assessment
  useEffect(() => {
    if (!assessmentId) return;

    setIsLoading(true);
    fetchAssessmentAudience(assessmentId)
      .then((res) => {
        if (res.data) {
          const r = res.data;
          setResolution(r);
          const isAll = r.target_all_students ?? (r.audience_mode === 'ALL_STUDENTS' || r.audience_mode === 'ALL_ACTIVE');
          setMode(isAll ? 'ALL_STUDENTS' : 'SPECIFIC');
          const stuIds = (r.additional_students || []).map((s) => s.id);
          setSelectedStudentIds(stuIds);
          onValidationChangeRef.current?.(r.total_eligible > 0, r.total_eligible);
          onAudienceChangedRef.current?.(r);
        }
      })
      .catch((err: any) => {
        console.error('Failed to load audience configuration:', err);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [assessmentId]);

  // Load students for picker when opened
  useEffect(() => {
    if (isStudentPickerOpen && availableStudents.length === 0) {
      fetchStudents({ page_size: 100 })
        .then((res) => {
          if (res.data?.results) setAvailableStudents(res.data.results);
        })
        .catch(() => {});
    }
  }, [isStudentPickerOpen, availableStudents.length]);

  // Run preview on backend
  const runPreview = useCallback(
    async (isAll: boolean, stuIds: string[]) => {
      if (!assessmentId) return;
      try {
        const res = await previewAssessmentAudience(assessmentId, {
          target_all_students: isAll,
          target_section_ids: [],
          target_student_ids: isAll ? [] : stuIds,
        });
        if (res.data) {
          setResolution(res.data);
          onValidationChangeRef.current?.(res.data.total_eligible > 0, res.data.total_eligible);
        }
      } catch (err: any) {
        console.error('Failed to preview audience resolution:', err);
      }
    },
    [assessmentId]
  );

  useEffect(() => {
    const isAll = mode === 'ALL_STUDENTS';
    onSelectionChangeRef.current?.([], selectedStudentIds, isAll);
  }, [selectedStudentIds, mode]);

  const handleModeChange = (newMode: 'ALL_STUDENTS' | 'SPECIFIC') => {
    if (isLocked) return;
    setMode(newMode);
    setSaveSuccess(false);
    runPreview(newMode === 'ALL_STUDENTS', selectedStudentIds);
  };

  const handleAddStudent = (student: StudentProfile) => {
    if (isLocked) return;
    const studentUserId = student.user_id || student.id;
    if (!selectedStudentIds.includes(studentUserId)) {
      const updated = [...selectedStudentIds, studentUserId];
      setSelectedStudentIds(updated);
      setSaveSuccess(false);
      runPreview(false, updated);
    }
  };

  const handleRemoveStudent = (studentId: string) => {
    if (isLocked) return;
    const updated = selectedStudentIds.filter((id) => id !== studentId);
    setSelectedStudentIds(updated);
    setSaveSuccess(false);
    runPreview(false, updated);
  };

  const handleSaveAudience = async () => {
    if (!assessmentId || isLocked) return;

    setIsSaving(true);
    setErrorMessage(null);
    setSaveSuccess(false);
    try {
      const isAll = mode === 'ALL_STUDENTS';
      const res = await configureAssessmentAudience(assessmentId, {
        target_all_students: isAll,
        target_section_ids: [],
        target_student_ids: isAll ? [] : selectedStudentIds,
      });
      if (res.data) {
        setResolution(res.data);
        const resolvedIsAll = res.data.target_all_students ?? (res.data.audience_mode === 'ALL_STUDENTS' || res.data.audience_mode === 'ALL_ACTIVE');
        setMode(resolvedIsAll ? 'ALL_STUDENTS' : 'SPECIFIC');
        setSelectedStudentIds((res.data.additional_students || []).map((s) => s.id));
        setSaveSuccess(true);
        onAudienceChangedRef.current?.(res.data);
        onValidationChangeRef.current?.(res.data.total_eligible > 0, res.data.total_eligible);
        setTimeout(() => setSaveSuccess(false), 3000);
      }
    } catch (err: any) {
      const msg = err.error?.message || err.message || 'Failed to update target candidates.';
      setErrorMessage(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const totalEligible = resolution ? resolution.total_eligible : 0;
  const isZeroAudience = totalEligible === 0;

  return (
    <Card className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-purple-600" />
            <h2 className="text-base font-bold text-slate-900">Candidate Selection</h2>
            {isLocked ? (
              <Badge variant="neutral" size="sm" className="flex items-center gap-1">
                <Lock className="w-3 h-3" /> Locked & Authoritative
              </Badge>
            ) : (
              <Badge variant="purple" size="sm">
                Candidates Setup
              </Badge>
            )}
            {isLoading && (
              <span className="text-[11px] text-slate-400 font-mono animate-pulse">Loading candidates...</span>
            )}
          </div>
          <p className="text-xs text-slate-500">
            Target all students in Craft Society or choose specific candidates.
            Eligible candidates will receive authoritative exam assignments upon publication.
          </p>
        </div>

        {!isLocked && assessmentId && (
          <div className="flex items-center gap-2">
            {saveSuccess && (
              <span className="text-xs font-semibold text-emerald-600 flex items-center gap-1">
                <CheckCircle2 className="w-4 h-4" /> Candidates Saved
              </span>
            )}
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={handleSaveAudience}
              isLoading={isSaving}
            >
              Save Candidates
            </Button>
          </div>
        )}
      </div>

      {errorMessage && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-2.5 text-xs text-rose-700">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Mode Selection Radios */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <button
          type="button"
          disabled={isLocked}
          onClick={() => handleModeChange('ALL_STUDENTS')}
          className={`p-4 rounded-xl border text-left transition-all relative flex flex-col justify-between ${
            mode === 'ALL_STUDENTS'
              ? 'bg-purple-50/80 border-purple-400 ring-2 ring-purple-500/20 shadow-sm'
              : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60'
          } ${isLocked ? 'cursor-not-allowed opacity-90' : 'cursor-pointer'}`}
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Globe className="w-4 h-4 text-purple-600" />
              <span className="font-bold text-xs text-slate-900">All Students</span>
            </div>
            <input
              type="radio"
              checked={mode === 'ALL_STUDENTS'}
              disabled={isLocked}
              onChange={() => handleModeChange('ALL_STUDENTS')}
              className="text-purple-600 focus:ring-purple-500 h-4 w-4 pointer-events-none"
            />
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            Every student in Craft Society will automatically be assigned this exam upon publication.
          </p>
          <div className="mt-3 pt-2 border-t border-purple-100 flex items-center justify-between text-[11px] text-purple-700 font-medium">
            <span>Recommended for society-wide exams</span>
            <span className="font-mono font-bold">
              {(mode === 'ALL_STUDENTS'
                ? resolution?.total_eligible
                : (resolution?.all_students_count ?? resolution?.total_craft_society_students ?? resolution?.total_eligible)) ?? 0} students
            </span>
          </div>
        </button>

        <button
          type="button"
          disabled={isLocked}
          onClick={() => handleModeChange('SPECIFIC')}
          className={`p-4 rounded-xl border text-left transition-all relative flex flex-col justify-between ${
            mode === 'SPECIFIC'
              ? 'bg-purple-50/80 border-purple-400 ring-2 ring-purple-500/20 shadow-sm'
              : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60'
          } ${isLocked ? 'cursor-not-allowed opacity-90' : 'cursor-pointer'}`}
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <UserCheck2 className="w-4 h-4 text-purple-600" />
              <span className="font-bold text-xs text-slate-900">Selected Candidates Only</span>
            </div>
            <input
              type="radio"
              checked={mode === 'SPECIFIC'}
              disabled={isLocked}
              onChange={() => handleModeChange('SPECIFIC')}
              className="text-purple-600 focus:ring-purple-500 h-4 w-4 pointer-events-none"
            />
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            Handpick specific candidates by searching Roll Number, EUID, or name.
          </p>
          <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-600 font-medium">
            <span>For invitation-only or makeup sessions</span>
            <span className="font-mono font-bold">{selectedStudentIds.length} chosen</span>
          </div>
        </button>
      </div>

      {/* Selected Candidates Picker (when in SPECIFIC mode) */}
      {mode === 'SPECIFIC' && (
        <div className="space-y-3 pt-2 border-t border-slate-100">
          <div className="flex items-center justify-between">
            <label className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
              <UserPlus className="w-4 h-4 text-purple-600" />
              Specific Candidates
              {selectedStudentIds.length > 0 && (
                <span className="text-[11px] font-mono text-purple-700 bg-purple-100 px-2 py-0.5 rounded-full font-semibold">
                  {selectedStudentIds.length} added
                </span>
              )}
            </label>
            {!isLocked && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsStudentPickerOpen(!isStudentPickerOpen)}
                className="text-purple-700 border-purple-200 hover:bg-purple-50 text-xs"
              >
                {isStudentPickerOpen ? 'Close Picker' : '+ Add Candidates'}
              </Button>
            )}
          </div>

          {/* Searchable Picker Dropdown */}
          {isStudentPickerOpen && !isLocked && (
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3 animate-fade-in">
              <div className="relative">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5 pointer-events-none" />
                <input
                  type="text"
                  value={studentSearch}
                  onChange={(e) => setStudentSearch(e.target.value)}
                  placeholder="Search by roll number, EUID, email, or name..."
                  className="w-full pl-9 pr-3 py-1.5 rounded-lg border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-purple-500 bg-white"
                />
              </div>

              <div className="max-h-48 overflow-y-auto divide-y divide-slate-100 border border-slate-200 rounded-lg bg-white text-xs">
                {availableStudents
                  .filter((st) => {
                    const query = studentSearch.toLowerCase();
                    return (
                      st.email.toLowerCase().includes(query) ||
                      st.roll_number.toLowerCase().includes(query) ||
                      st.euid.toLowerCase().includes(query) ||
                      (st.certificate_name && st.certificate_name.toLowerCase().includes(query)) ||
                      (st.first_name && st.first_name.toLowerCase().includes(query))
                    );
                  })
                  .slice(0, 30)
                  .map((st) => {
                    const studentUserId = st.user_id || st.id;
                    const isAdded = selectedStudentIds.includes(studentUserId);
                    const displayName = st.certificate_name || st.first_name || st.email;
                    return (
                      <div
                        key={st.id}
                        className="p-2.5 flex items-center justify-between hover:bg-slate-50 transition-colors"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-slate-900">{st.roll_number}</span>
                          <span className="text-slate-600 text-[11px] truncate max-w-[200px]">
                            {displayName}
                          </span>
                          <span className="text-slate-400 font-mono text-[10px]">{st.euid}</span>
                        </div>
                        <Button
                          type="button"
                          variant={isAdded ? 'ghost' : 'secondary'}
                          size="sm"
                          disabled={isAdded}
                          onClick={() => handleAddStudent(st)}
                          className="text-xs h-7 px-2.5"
                        >
                          {isAdded ? (
                            <span className="text-emerald-600 font-semibold flex items-center gap-1">
                              <UserCheck className="w-3.5 h-3.5" /> Added
                            </span>
                          ) : (
                            '+ Add'
                          )}
                        </Button>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {/* Selected Candidates Pills */}
          {resolution && resolution.additional_students && resolution.additional_students.length > 0 ? (
            <div className="flex flex-wrap gap-2 pt-1">
              {resolution.additional_students.map((st) => (
                <div
                  key={st.id}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-100 border border-slate-200 text-xs font-mono text-slate-800"
                >
                  <span className="font-bold">{st.roll_number || st.email}</span>
                  {!isLocked && (
                    <button
                      type="button"
                      onClick={() => handleRemoveStudent(st.id)}
                      className="text-slate-400 hover:text-rose-600 p-0.5 rounded"
                      title="Remove candidate"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400 italic">No candidates specifically added yet.</p>
          )}
        </div>
      )}

      {/* Authoritative Candidate Summary Box */}
      <div
        className={`p-4 rounded-xl border transition-all ${
          isZeroAudience
            ? 'bg-amber-50/80 border-amber-300 text-amber-900'
            : 'bg-gradient-to-r from-purple-50/60 to-slate-50 border-purple-200 text-slate-800'
        }`}
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-600" />
              <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
                Authoritative Candidates Summary
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-slate-900">{totalEligible}</span>
              <span className="text-xs font-semibold text-slate-600">Total Eligible Candidates</span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs font-mono">
            <span className="px-2.5 py-1 rounded-md bg-white/80 border border-slate-200 font-semibold text-slate-700">
              {mode === 'ALL_STUDENTS' ? '🌐 All Students' : `🎯 ${selectedStudentIds.length} Selected Candidates`}
            </span>
          </div>
        </div>

        {/* Warning if 0 candidates eligible */}
        {isZeroAudience && (
          <div className="mt-3 pt-3 border-t border-amber-200/80 flex items-center gap-2 text-xs font-semibold text-amber-800">
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>
              Select at least one candidate before this assessment can be published.
            </span>
          </div>
        )}
      </div>
    </Card>
  );
};
export { AssessmentAudiencePanel as AssessmentCandidatesPanel };
