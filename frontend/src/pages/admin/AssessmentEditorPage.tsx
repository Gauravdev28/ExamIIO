import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  createAssessment,
  getAssessmentDetail,
  updateAssessment,
  publishAssessment,
  deleteAssessment,
  addQuestionToAssessment,
  removeQuestionFromAssessment,
} from '../../api/assessments';
import { getQuestions } from '../../api/questions';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import {
  ArrowLeft,
  Save,
  CheckCircle2,
  AlertCircle,
  Plus,
  Trash2,
  Lock,
  Calendar,
  Clock,
  Shuffle,
  FileText,
  Search,
  X,
  Shield,
  Camera,
  Smartphone,
  Users,
} from 'lucide-react';
import {
  AssessmentAdminDetail,
  ResultVisibility,
  AudienceResolution,
} from '../../types/assessment';
import { QuestionItem } from '../../types/question';
import { AssessmentAudiencePanel } from '../../components/admin/AssessmentAudiencePanel';

export const AssessmentEditorPage: React.FC = () => {
  const { id: routeAssessmentId } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const isEditing = Boolean(routeAssessmentId && routeAssessmentId !== 'create' && routeAssessmentId !== 'new');

  const [assessment, setAssessment] = useState<AssessmentAdminDetail | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [instructions, setInstructions] = useState('');
  const [startDatetime, setStartDatetime] = useState('');
  const [endDatetime, setEndDatetime] = useState('');
  const [durationMinutes, setDurationMinutes] = useState<number>(60);
  const [totalPoints, setTotalPoints] = useState<number>(0);
  const [passingPercentage, setPassingPercentage] = useState<number>(40);
  const [negativeMarkingEnabled, setNegativeMarkingEnabled] = useState(false);
  const [attemptLimit, setAttemptLimit] = useState<number>(1);
  const [randomizeQuestions, setRandomizeQuestions] = useState(false);
  const [randomizeOptions, setRandomizeOptions] = useState(false);
  const [resultVisibility, setResultVisibility] = useState<ResultVisibility>('AFTER_DEADLINE');
  const [proctoringEnabled, setProctoringEnabled] = useState(true);
  const [cameraRequired, setCameraRequired] = useState(true);
  const [phoneDetectionEnabled, setPhoneDetectionEnabled] = useState(true);
  const [faceDetectionEnabled, setFaceDetectionEnabled] = useState(true);
  const [multipleFaceDetectionEnabled, setMultipleFaceDetectionEnabled] = useState(true);
  const [gazeDetectionEnabled, setGazeDetectionEnabled] = useState(true);
  const [headMovementDetectionEnabled, setHeadMovementDetectionEnabled] = useState(true);
  const [maxConfirmedViolations, setMaxConfirmedViolations] = useState<number>(3);
  const [isPublishModalOpen, setIsPublishModalOpen] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [audienceTotalEligible, setAudienceTotalEligible] = useState<number>(0);
  const [targetAllStudents, setTargetAllStudents] = useState<boolean>(true);
  const [targetStudentIds, setTargetStudentIds] = useState<string[]>([]);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleAudienceValidationChange = useCallback((_isValid: boolean, count: number) => {
    setAudienceTotalEligible(count);
  }, []);

  const handleAudienceSelectionChange = useCallback((_secIds: string[], stuIds: string[], isAll?: boolean) => {
    setTargetStudentIds(stuIds);
    if (typeof isAll === 'boolean') {
      setTargetAllStudents(isAll);
    }
  }, []);

  const handleAudienceChanged = useCallback((resolution: AudienceResolution) => {
    const isAll = resolution.target_all_students ?? (resolution.audience_mode === 'ALL_STUDENTS' || resolution.audience_mode === 'ALL_ACTIVE');
    setTargetAllStudents(Boolean(isAll));
    setTargetStudentIds((resolution.additional_students || []).map((s) => s.id));
    setAudienceTotalEligible(resolution.total_eligible);
  }, []);

  // Question Picker state
  const [isQuestionPickerOpen, setIsQuestionPickerOpen] = useState(false);
  const [availableQuestions, setAvailableQuestions] = useState<QuestionItem[]>([]);
  const [questionSearch, setQuestionSearch] = useState('');
  const [selectedQvId, setSelectedQvId] = useState<string | null>(null);
  const [qPointsInput, setQPointsInput] = useState<number>(10);
  const [qNegEnabledInput, setQNegEnabledInput] = useState(false);
  const [qNegPointsInput, setQNegPointsInput] = useState<number>(0);
  const [isLoadingQuestions, setIsLoadingQuestions] = useState(false);
  const [pickerError, setPickerError] = useState<string | null>(null);

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const formatForDateTimeLocal = (d: Date): string => {
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  useEffect(() => {
    if (isEditing && routeAssessmentId) {
      loadAssessment(routeAssessmentId);
    } else {
      // Default future dates in local time
      const now = new Date();
      const nextWeek = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
      setStartDatetime(formatForDateTimeLocal(now));
      setEndDatetime(formatForDateTimeLocal(nextWeek));
    }
  }, [isEditing, routeAssessmentId]);

  const loadAssessment = async (aId: string) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await getAssessmentDetail(aId);
      if (res.data) {
        const d = res.data;
        setAssessment(d);
        setTitle(d.title);
        setDescription(d.description);
        setInstructions(d.instructions || '');
        setStartDatetime(formatForDateTimeLocal(new Date(d.start_datetime)));
        setEndDatetime(formatForDateTimeLocal(new Date(d.end_datetime)));
        setDurationMinutes(d.duration_minutes);
        setTotalPoints(d.total_points);
        if (d.passing_percentage !== undefined && d.passing_percentage !== null) {
          setPassingPercentage(Number(d.passing_percentage));
        }
        setNegativeMarkingEnabled(d.negative_marking_enabled);
        setAttemptLimit(d.attempt_limit);
        setRandomizeQuestions(d.randomize_questions);
        setRandomizeOptions(d.randomize_options);
        setResultVisibility(d.result_visibility);
        setProctoringEnabled(d.proctoring_enabled ?? true);
        setCameraRequired(d.camera_required ?? true);
        setPhoneDetectionEnabled(d.phone_detection_enabled ?? true);
        setFaceDetectionEnabled(d.face_detection_enabled ?? true);
        setMultipleFaceDetectionEnabled(d.multiple_face_detection_enabled ?? true);
        setGazeDetectionEnabled(d.gaze_detection_enabled ?? true);
        setHeadMovementDetectionEnabled(d.head_movement_detection_enabled ?? true);
        setMaxConfirmedViolations(d.max_confirmed_violations ?? 3);
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to load assessment.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async (isAutoSave: boolean = false): Promise<boolean> => {
    setErrorMessage(null);
    if (!isAutoSave) setSuccessMessage(null);

    const trimmedTitle = title.trim();
    const trimmedDesc = description.trim();

    if (!trimmedTitle) {
      setErrorMessage('Assessment title cannot be empty.');
      return false;
    }

    const startDate = new Date(startDatetime);
    const endDate = new Date(endDatetime);

    if (isNaN(startDate.getTime())) {
      setErrorMessage('Please provide a valid start datetime.');
      return false;
    }
    if (isNaN(endDate.getTime())) {
      setErrorMessage('Please provide a valid end / deadline datetime.');
      return false;
    }
    if (endDate <= startDate) {
      setErrorMessage('End / Deadline datetime must be strictly after start datetime.');
      return false;
    }
    if (durationMinutes < 1) {
      setErrorMessage('Duration must be at least 1 minute.');
      return false;
    }

    setIsSaving(true);

    const payload: any = {
      title: trimmedTitle,
      description: trimmedDesc,
      instructions: instructions.trim(),
      start_datetime: startDate.toISOString(),
      end_datetime: endDate.toISOString(),
      duration_minutes: durationMinutes,
      total_points: totalPoints,
      passing_percentage: passingPercentage,
      negative_marking_enabled: negativeMarkingEnabled,
      attempt_limit: attemptLimit,
      randomize_questions: randomizeQuestions,
      randomize_options: randomizeOptions,
      result_visibility: resultVisibility,
      proctoring_enabled: proctoringEnabled,
      camera_required: cameraRequired,
      phone_detection_enabled: phoneDetectionEnabled,
      face_detection_enabled: faceDetectionEnabled,
      multiple_face_detection_enabled: multipleFaceDetectionEnabled,
      gaze_detection_enabled: gazeDetectionEnabled,
      head_movement_detection_enabled: headMovementDetectionEnabled,
      max_confirmed_violations: Math.max(3, maxConfirmedViolations || 3),
    };

    if (isEditing && !isPublished) {
      payload.target_all_students = targetAllStudents;
      payload.target_student_ids = targetAllStudents ? [] : targetStudentIds;
    }

    try {
      if (!isEditing) {
        const res = await createAssessment(payload);
        if (res.data) {
          navigate(`/admin/assessments/${res.data.id}`);
          return true;
        }
      } else {
        const res = await updateAssessment(routeAssessmentId!, payload);
        if (res.data) {
          setAssessment(res.data);
          if (!isAutoSave) {
            setSuccessMessage('Assessment details updated successfully.');
          }
          return true;
        }
      }
      return false;
    } catch (err: any) {
      const details = err.error?.details;
      let detailedMsg = err.error?.message;
      if (details && typeof details === 'object') {
        const fieldMsgs = Object.entries(details).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`);
        if (fieldMsgs.length > 0) detailedMsg = fieldMsgs.join(' | ');
      }
      const finalMsg = detailedMsg || err.message || 'Failed to save assessment.';
      setErrorMessage(finalMsg);
      if (isPublishModalOpen) {
        setPublishError(finalMsg);
      }
      return false;
    } finally {
      setIsSaving(false);
    }
  };

  const handlePublish = async () => {
    if (!isEditing || !routeAssessmentId) return;

    setPublishError(null);
    setErrorMessage(null);
    setSuccessMessage(null);

    // First ensure current unsaved draft state is persisted
    const saved = await handleSave(true);
    if (!saved) {
      setPublishError('Please fix validation errors before publishing.');
      return;
    }

    setIsPublishing(true);
    try {
      const res = await publishAssessment(routeAssessmentId);
      if (res.data) {
        setAssessment(res.data);
        setSuccessMessage('Assessment published successfully! Candidates enrolled and snapshot frozen.');
        setIsPublishModalOpen(false);
      }
    } catch (err: any) {
      const details = err.error?.details;
      let detailedMsg = err.error?.message;
      if (details && typeof details === 'object') {
        const fieldMsgs = Object.entries(details).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`);
        if (fieldMsgs.length > 0) detailedMsg = fieldMsgs.join(' | ');
      }
      const finalMsg = detailedMsg || err.message || 'Failed to publish assessment.';
      setErrorMessage(finalMsg);
      setPublishError(finalMsg);
    } finally {
      setIsPublishing(false);
    }
  };

  const handleDeleteDraft = async () => {
    if (!isEditing || !routeAssessmentId || isLocked) return;
    if (!window.confirm('Are you sure you want to permanently delete this draft assessment? This action cannot be undone.')) {
      return;
    }

    setIsDeleting(true);
    setErrorMessage(null);
    try {
      await deleteAssessment(routeAssessmentId);
      navigate('/admin/assessments');
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to delete draft assessment.');
    } finally {
      setIsDeleting(false);
    }
  };

  const openQuestionPicker = async () => {
    setIsQuestionPickerOpen(true);
    setIsLoadingQuestions(true);
    setPickerError(null);
    try {
      const res = await getQuestions({ page_size: 100, version_status: 'PUBLISHED' });
      if (res.data) {
        setAvailableQuestions(res.data.results);
      }
    } catch (err: any) {
      console.error(err);
      setPickerError(err.error?.message || err.message || 'Failed to load questions.');
    } finally {
      setIsLoadingQuestions(false);
    }
  };

  const handleAddQuestionToAssessment = async () => {
    if (!routeAssessmentId || !selectedQvId) return;
    try {
      const res = await addQuestionToAssessment(routeAssessmentId, {
        question_version_id: selectedQvId,
        points: qPointsInput,
        negative_marking_enabled: qNegEnabledInput,
        negative_points: qNegPointsInput,
      });
      if (res.data) {
        setAssessment(res.data);
        setIsQuestionPickerOpen(false);
        setSelectedQvId(null);
        setSuccessMessage('Question successfully added.');
      }
    } catch (err: any) {
      alert(err.error?.message || 'Failed to add question to assessment.');
    }
  };

  const handleRemoveQuestion = async (qvId: string) => {
    if (!routeAssessmentId) return;
    try {
      const res = await removeQuestionFromAssessment(routeAssessmentId, qvId);
      if (res.data) {
        setAssessment(res.data);
      }
    } catch (err: any) {
      alert(err.error?.message || 'Failed to remove question.');
    }
  };

  const isArchived = assessment?.status === 'ARCHIVED';
  const isPublished = assessment?.status === 'PUBLISHED';
  const hasAttempts = Boolean(assessment?.attempt_count && assessment.attempt_count > 0);
  const isStructuralLocked = isPublished || isArchived;
  const isLocked = isStructuralLocked;
  const linkedQuestions = assessment?.assessment_questions || [];
  const questionPointsSum = linkedQuestions.reduce((sum, q) => sum + q.points, 0);

  const renderQuestionTypeBadge = (type: string) => {
    switch (type) {
      case 'MCQ':
        return <Badge variant="info" size="sm">Multiple Choice</Badge>;
      case 'MULTI_SELECT':
        return <Badge variant="neutral" size="sm">Multi-Select</Badge>;
      case 'CODING':
        return <Badge variant="success" size="sm">Coding</Badge>;
      case 'SQL':
        return <Badge variant="purple" size="sm">SQL Query</Badge>;
      case 'TRUE_FALSE':
        return <Badge variant="warning" size="sm">True / False</Badge>;
      case 'SHORT_ANSWER':
        return <Badge variant="neutral" size="sm">Short Answer</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{type}</Badge>;
    }
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-16 flex flex-col items-center justify-center space-y-3">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs text-slate-400 font-mono">Loading assessment configuration...</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 space-y-6 max-w-5xl">
      {/* Top Navigation */}
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <Link
          to="/admin/assessments"
          className="inline-flex items-center text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5" />
          Back to Assessments
        </Link>

        <div className="flex items-center gap-2">
          {assessment && (
            <Badge
              variant={
                assessment.status === 'PUBLISHED'
                  ? 'success'
                  : assessment.status === 'ARCHIVED'
                  ? 'neutral'
                  : 'warning'
              }
            >
              {assessment.status}
            </Badge>
          )}
          {isArchived && (
            <span className="flex items-center gap-1 text-xs text-slate-500 font-medium">
              <Lock className="w-3.5 h-3.5" /> Archived (Read Only)
            </span>
          )}
          {isPublished && (
            <span className="flex items-center gap-1 text-xs text-emerald-700 font-medium">
              <Lock className="w-3.5 h-3.5" /> Published (Questions Frozen • Metadata Editable)
            </span>
          )}
        </div>
      </div>

      {/* Notifications */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-3 text-rose-800 text-sm">
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}

      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex items-start gap-3 text-emerald-800 text-sm">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
          <span>{successMessage}</span>
        </div>
      )}

      {/* Section 1: Assessment Metadata & Scheduling */}
      <Card className="p-6 space-y-6">
        <div className="flex items-center justify-between border-b border-slate-200 pb-4">
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <FileText className="w-5 h-5 text-emerald-600" />
            Assessment Configuration & Scheduling
          </h2>
        </div>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-700">Assessment Title</label>
            <input
              type="text"
              disabled={isArchived}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. CS201 Final Examination / Data Engineering Assessment"
              className="w-full px-3.5 py-2.5 rounded-lg bg-white border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>

          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-700">Description</label>
            <textarea
              rows={3}
              disabled={isArchived}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Summary of assessment objectives..."
              className="w-full px-3.5 py-2.5 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>

          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-700">Student Instructions</label>
            <input
              type="text"
              disabled={isArchived}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="e.g. Ensure stable internet. Monaco editor supports Python, C++, and Java."
              className="w-full px-3.5 py-2.5 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>

          {/* Scheduling & Timing Controls */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs pt-2">
            <div className="space-y-1.5">
              <label className="block text-slate-700 font-semibold flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-emerald-600" />
                Start Datetime (UTC)
              </label>
              <input
                type="datetime-local"
                disabled={isArchived || (isPublished && hasAttempts)}
                value={startDatetime}
                onChange={(e) => setStartDatetime(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 focus:ring-2 focus:ring-emerald-500 font-mono"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-slate-700 font-semibold flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-rose-600" />
                End / Deadline (UTC)
              </label>
              <input
                type="datetime-local"
                disabled={isArchived}
                value={endDatetime}
                onChange={(e) => setEndDatetime(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 focus:ring-2 focus:ring-emerald-500 font-mono"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-slate-700 font-semibold flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-amber-600" />
                Duration (Minutes)
              </label>
              <input
                type="number"
                min={1}
                disabled={isArchived || (isPublished && hasAttempts)}
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(parseInt(e.target.value, 10) || 60)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 focus:ring-2 focus:ring-emerald-500 font-mono"
              />
            </div>
          </div>

          {/* Points & Attempts */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 text-xs pt-2">
            <div className="space-y-1.5">
              <label className="block text-slate-700 font-semibold">Total Points (Must equal Question sum)</label>
              <input
                type="number"
                min={0}
                disabled={isStructuralLocked}
                value={totalPoints}
                onChange={(e) => setTotalPoints(parseInt(e.target.value, 10) || 0)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-emerald-700 font-bold font-mono focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-slate-700 font-semibold">Passing Score (%)</label>
              <input
                type="number"
                min={0}
                max={100}
                disabled={isArchived || (isPublished && hasAttempts)}
                value={passingPercentage}
                onChange={(e) => setPassingPercentage(parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 font-mono focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-slate-700 font-semibold">Attempt Limit</label>
              <input
                type="number"
                min={1}
                disabled={isArchived || (isPublished && hasAttempts)}
                value={attemptLimit}
                onChange={(e) => setAttemptLimit(parseInt(e.target.value, 10) || 1)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 font-mono focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-slate-700 font-semibold">Result Visibility</label>
              <select
                disabled={isArchived}
                value={resultVisibility}
                onChange={(e) => setResultVisibility(e.target.value as ResultVisibility)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 font-medium focus:ring-2 focus:ring-emerald-500"
              >
                <option value="AFTER_DEADLINE">After Deadline</option>
                <option value="IMMEDIATE">Immediate</option>
                <option value="MANUAL">Manual Release</option>
              </select>
            </div>
          </div>

          {/* Randomization & Negative Marking Toggles */}
          <div className="flex flex-wrap items-center gap-6 p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs">
            <label className="flex items-center gap-2 cursor-pointer text-slate-700 font-medium">
              <input
                type="checkbox"
                disabled={isLocked}
                checked={negativeMarkingEnabled}
                onChange={(e) => setNegativeMarkingEnabled(e.target.checked)}
                className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4 bg-white border-slate-300"
              />
              <span>Enable Negative Marking Global Policy</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer text-slate-700 font-medium">
              <input
                type="checkbox"
                disabled={isLocked}
                checked={randomizeQuestions}
                onChange={(e) => setRandomizeQuestions(e.target.checked)}
                className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4 bg-white border-slate-300"
              />
              <span className="flex items-center gap-1">
                <Shuffle className="w-3.5 h-3.5 text-emerald-600" />
                Randomize Question Order
              </span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer text-slate-700 font-medium">
              <input
                type="checkbox"
                disabled={isLocked}
                checked={randomizeOptions}
                onChange={(e) => setRandomizeOptions(e.target.checked)}
                className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4 bg-white border-slate-300"
              />
              <span className="flex items-center gap-1">
                <Shuffle className="w-3.5 h-3.5 text-purple-600" />
                Randomize Options Order
              </span>
            </label>
          </div>
        </div>
      </Card>

      {/* Proctoring & Examination Security */}
      <Card className="p-6 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4">
          <div className="space-y-1">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Shield className="w-5 h-5 text-indigo-600" />
              AI-Assisted Proctoring & Security
            </h2>
            <p className="text-xs text-slate-500">
              Configure webcam requirements, AI telemetry, and disqualification thresholds.
            </p>
          </div>
          <Badge variant={proctoringEnabled ? 'success' : 'neutral'} size="sm">
            {proctoringEnabled ? 'Proctoring Active' : 'Unproctored'}
          </Badge>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between p-3.5 bg-slate-50 rounded-xl border border-slate-200">
            <div>
              <div className="text-xs font-bold text-slate-900">Enable AI-Assisted Proctoring</div>
              <div className="text-[11px] text-slate-500">Enable automated multi-modal monitoring during candidate exam sessions</div>
            </div>
            <input
              type="checkbox"
              disabled={isLocked}
              checked={proctoringEnabled}
              onChange={(e) => setProctoringEnabled(e.target.checked)}
              className="rounded text-indigo-600 focus:ring-indigo-500 h-4 w-4 bg-white border-slate-300 cursor-pointer"
            />
          </div>

          {proctoringEnabled && (
            <div className="space-y-4 pl-2 pt-2 border-l-2 border-indigo-100">
              <div className="flex items-center justify-between p-3 bg-white rounded-xl border border-slate-200">
                <div className="flex items-center gap-2.5">
                  <Camera className="w-4 h-4 text-slate-500" />
                  <div>
                    <div className="text-xs font-bold text-slate-800">Webcam Required for Entry</div>
                    <div className="text-[11px] text-slate-500">Candidates must verify webcam readiness before starting</div>
                  </div>
                </div>
                <input
                  type="checkbox"
                  disabled={isLocked}
                  checked={cameraRequired}
                  onChange={(e) => setCameraRequired(e.target.checked)}
                  className="rounded text-indigo-600 focus:ring-indigo-500 h-4 w-4 bg-white border-slate-300"
                />
              </div>

              <div className="space-y-2">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Strong Violation Detectors (Strike Counted)</span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <label className="flex items-center justify-between p-3 rounded-xl border border-slate-200 bg-white cursor-pointer hover:bg-slate-50">
                    <div className="flex items-center gap-2">
                      <Smartphone className="w-4 h-4 text-rose-500" />
                      <div>
                        <div className="text-xs font-semibold text-slate-900">Phone / Mobile Device</div>
                        <div className="text-[10px] text-slate-500">Strike counted upon AI confirmation</div>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      disabled={isLocked}
                      checked={phoneDetectionEnabled}
                      onChange={(e) => setPhoneDetectionEnabled(e.target.checked)}
                      className="rounded text-rose-600 focus:ring-rose-500 h-4 w-4"
                    />
                  </label>

                  <label className="flex items-center justify-between p-3 rounded-xl border border-slate-200 bg-white cursor-pointer hover:bg-slate-50">
                    <div className="flex items-center gap-2">
                      <Users className="w-4 h-4 text-rose-500" />
                      <div>
                        <div className="text-xs font-semibold text-slate-900">Multiple Faces Detected</div>
                        <div className="text-[10px] text-slate-500">Unauthorized second person in frame</div>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      disabled={isLocked}
                      checked={multipleFaceDetectionEnabled}
                      onChange={(e) => setMultipleFaceDetectionEnabled(e.target.checked)}
                      className="rounded text-rose-600 focus:ring-rose-500 h-4 w-4"
                    />
                  </label>
                </div>
              </div>

              <div className="space-y-2">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Supporting Telemetry (Non-Striking Telemetry)</span>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <label className="flex items-center justify-between p-3 rounded-xl border border-slate-200 bg-white cursor-pointer hover:bg-slate-50">
                    <div>
                      <div className="text-xs font-semibold text-slate-800">Face Not Detected</div>
                      <div className="text-[10px] text-slate-400">Absence telemetry reminder</div>
                    </div>
                    <input
                      type="checkbox"
                      disabled={isLocked}
                      checked={faceDetectionEnabled}
                      onChange={(e) => setFaceDetectionEnabled(e.target.checked)}
                      className="rounded text-indigo-600 focus:ring-indigo-500 h-4 w-4"
                    />
                  </label>

                  <label className="flex items-center justify-between p-3 rounded-xl border border-slate-200 bg-white cursor-pointer hover:bg-slate-50">
                    <div>
                      <div className="text-xs font-semibold text-slate-800">Gaze Deviation</div>
                      <div className="text-[10px] text-slate-400">Candidate looking away</div>
                    </div>
                    <input
                      type="checkbox"
                      disabled={isLocked}
                      checked={gazeDetectionEnabled}
                      onChange={(e) => setGazeDetectionEnabled(e.target.checked)}
                      className="rounded text-indigo-600 focus:ring-indigo-500 h-4 w-4"
                    />
                  </label>

                  <label className="flex items-center justify-between p-3 rounded-xl border border-slate-200 bg-white cursor-pointer hover:bg-slate-50">
                    <div>
                      <div className="text-xs font-semibold text-slate-800">Head Movement</div>
                      <div className="text-[10px] text-slate-400">Extreme yaw / pitch tilt</div>
                    </div>
                    <input
                      type="checkbox"
                      disabled={isLocked}
                      checked={headMovementDetectionEnabled}
                      onChange={(e) => setHeadMovementDetectionEnabled(e.target.checked)}
                      className="rounded text-indigo-600 focus:ring-indigo-500 h-4 w-4"
                    />
                  </label>
                </div>
              </div>

              <div className="p-3.5 bg-rose-50/50 rounded-xl border border-rose-200/80 flex flex-wrap items-center justify-between gap-4">
                <div className="space-y-0.5">
                  <div className="text-xs font-bold text-slate-900">Automatic Disqualification Threshold</div>
                  <div className="text-[11px] text-slate-600">
                    Number of confirmed strong violations before session is immediately terminated (Minimum: 3).
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={3}
                    max={10}
                    disabled={isLocked}
                    value={maxConfirmedViolations}
                    onChange={(e) => setMaxConfirmedViolations(Math.max(3, parseInt(e.target.value, 10) || 3))}
                    className="w-20 px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-mono font-bold text-center bg-white"
                  />
                  <span className="text-xs font-semibold text-slate-600">violations</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Candidate Selection */}
      {isEditing && (
        <AssessmentAudiencePanel
          assessmentId={routeAssessmentId || null}
          isLocked={isLocked}
          onAudienceChanged={handleAudienceChanged}
          onValidationChange={handleAudienceValidationChange}
          onSelectionChange={handleAudienceSelectionChange}
        />
      )}

      {/* Section 2: Assessment Questions List & Point Invariant Check */}
      {isEditing && (
        <Card className="p-6 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4">
            <div>
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                Assessment Questions ({linkedQuestions.length})
              </h2>
              <p className="text-xs text-slate-500">
                Bound to immutable published QuestionVersions
              </p>
            </div>

            {/* Invariant Meter */}
            <div className="flex items-center gap-3 font-mono text-xs">
              <span
                className={`px-3 py-1.5 rounded-lg border font-bold ${
                  questionPointsSum === totalPoints && totalPoints > 0
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                    : 'bg-amber-50 border-amber-200 text-amber-800'
                }`}
              >
                Questions Total: {questionPointsSum} / {totalPoints} pts{' '}
                {totalPoints !== questionPointsSum && `(${totalPoints - questionPointsSum} diff)`}
              </span>

              {!isLocked && (
                <Button type="button" variant="secondary" size="sm" onClick={openQuestionPicker}>
                  <Plus className="w-3.5 h-3.5 mr-1" /> Add Question
                </Button>
              )}
            </div>
          </div>

          {linkedQuestions.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500 font-mono">
              No questions linked to this assessment yet. Click "Add Question" to select from published questions.
            </div>
          ) : (
            <div className="space-y-3">
              {linkedQuestions.map((q, idx) => (
                <div
                  key={q.id}
                  className="flex items-center justify-between p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-bold text-slate-500 font-mono w-6">#{idx + 1}</span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-sans font-bold text-slate-900">{q.question_title}</span>
                        {renderQuestionTypeBadge(q.question_type)}
                        <Badge variant="neutral" size="sm">v{q.version_number}</Badge>
                      </div>
                      <div className="flex items-center gap-3 text-[11px] text-slate-500 mt-1 font-mono">
                        <span>Points: <strong className="text-emerald-700">{q.points}</strong></span>
                        {q.negative_marking_enabled && (
                          <span className="text-rose-600">Penalty: -{q.negative_points}</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {!isLocked && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRemoveQuestion(q.question_version_id)}
                      className="text-slate-400 hover:text-rose-600 hover:bg-rose-50"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Action Bar */}
      <div className="flex items-center justify-between pt-4 border-t border-slate-200">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="md" onClick={() => navigate('/admin/assessments')}>
            Cancel
          </Button>

          {!isLocked && isEditing && (
            <Button
              type="button"
              variant="ghost"
              size="md"
              onClick={handleDeleteDraft}
              isLoading={isDeleting}
              className="text-rose-600 hover:text-rose-700 hover:bg-rose-50"
            >
              <Trash2 className="w-4 h-4 mr-1.5" />
              Delete Draft
            </Button>
          )}
        </div>

        <div className="flex items-center gap-3">
          {!isArchived && (
            <Button
              type="button"
              variant="secondary"
              size="md"
              onClick={() => handleSave(false)}
              isLoading={isSaving}
            >
              <Save className="w-4 h-4 mr-2" />
              {isPublished ? 'Save Changes' : 'Save Draft'}
            </Button>
          )}

          {!isLocked && isEditing && (
            <div className="flex items-center gap-2">
              {audienceTotalEligible === 0 && (
                <span className="text-xs text-amber-700 font-semibold bg-amber-50 border border-amber-200 px-2.5 py-1 rounded-lg">
                  ⚠️ Candidates Required
                </span>
              )}
              <Button
                type="button"
                variant="primary"
                size="md"
                onClick={() => setIsPublishModalOpen(true)}
                isLoading={isPublishing}
                disabled={
                  linkedQuestions.length === 0 ||
                  questionPointsSum !== totalPoints ||
                  audienceTotalEligible === 0
                }
              >
                <CheckCircle2 className="w-4 h-4 mr-2" />
                Publish Assessment
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Question Picker Modal */}
      {isQuestionPickerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm overflow-y-auto">
          <Card className="max-w-3xl w-full p-6 space-y-6 border-slate-200 shadow-2xl relative my-8 bg-white">
            <button
              onClick={() => setIsQuestionPickerOpen(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-700 font-bold"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-3 border-b border-slate-200 pb-4">
              <div>
                <h3 className="text-base font-bold text-slate-900">Select Question for Assessment</h3>
                <p className="text-xs text-slate-500">Pick any published question from your question bank. Only published questions are eligible for exams.</p>
              </div>
            </div>

            {pickerError && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{pickerError}</span>
              </div>
            )}

            <div className="space-y-4">
              <div className="relative">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search questions by title..."
                  value={questionSearch}
                  onChange={(e) => setQuestionSearch(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-lg bg-white border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              {isLoadingQuestions ? (
                <div className="py-12 flex flex-col items-center justify-center text-slate-500 space-y-2 border border-slate-200 rounded-xl">
                  <div className="animate-spin rounded-full h-6 w-6 border-2 border-emerald-600 border-t-transparent" />
                  <span className="text-xs font-mono">Loading question bank...</span>
                </div>
              ) : (
                <div className="max-h-60 overflow-y-auto border border-slate-200 rounded-xl divide-y divide-slate-100 text-xs">
                  {availableQuestions
                    .filter((q) => {
                      const v = q.published_version || (q.latest_version?.status === 'PUBLISHED' ? q.latest_version : null);
                      if (!v) return false;
                      const title = v.title || '';
                      return title.toLowerCase().includes(questionSearch.toLowerCase());
                    })
                    .map((q) => {
                      const v = q.published_version || (q.latest_version?.status === 'PUBLISHED' ? q.latest_version : null);
                      if (!v) return null;
                      const isSelected = selectedQvId === v.id;

                      return (
                        <div
                          key={q.id}
                          onClick={() => {
                            setSelectedQvId(v.id);
                            setQPointsInput(v.points);
                          }}
                          className={`flex items-center justify-between p-3 cursor-pointer transition-colors ${
                            isSelected ? 'bg-emerald-50 border-l-4 border-emerald-600' : 'hover:bg-slate-50'
                          }`}
                        >
                          <div>
                            <div className="font-bold text-slate-900 text-sm">{v.title}</div>
                            <div className="flex flex-wrap items-center gap-2 mt-1">
                              {renderQuestionTypeBadge(q.question_type)}
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 font-mono font-bold">
                                v{v.version_number}
                              </span>
                              <Badge
                                variant={
                                  v.difficulty === 'EASY'
                                    ? 'success'
                                    : v.difficulty === 'MEDIUM'
                                    ? 'warning'
                                    : 'danger'
                                }
                                size="sm"
                              >
                                {v.difficulty}
                              </Badge>
                              <span className="font-semibold text-emerald-700">{v.points} pts</span>
                              {q.question_type === 'MCQ' ? (
                                <Badge variant="success" size="sm">100% Ready</Badge>
                              ) : v.health_status?.is_data_ready ? (
                                <Badge variant="success" size="sm">11/11 Ready</Badge>
                              ) : v.health_status ? (
                                <Badge variant="warning" size="sm">
                                  {v.health_status.passed_data_checks ?? v.health_status.passed_checks ?? 0}/11 Ready
                                </Badge>
                              ) : (
                                <Badge variant="neutral" size="sm">Ready</Badge>
                              )}
                              <Badge variant="success" size="sm">Published</Badge>
                            </div>
                          </div>
                        </div>
                      );
                    })}

                  {availableQuestions.filter((q) => {
                    const v = q.published_version || (q.latest_version?.status === 'PUBLISHED' ? q.latest_version : null);
                    if (!v) return false;
                    const title = v.title || '';
                    return title.toLowerCase().includes(questionSearch.toLowerCase());
                  }).length === 0 && (
                    <div className="p-8 text-center text-slate-400 font-sans text-xs">
                      No published questions found matching your search. Publish questions in the Question Bank before adding them to exams.
                    </div>
                  )}
                </div>
              )}

              {selectedQvId && (
                <div className="grid grid-cols-3 gap-3 p-3 rounded-xl bg-slate-50 border border-slate-200 font-mono text-xs">
                  <div className="space-y-1">
                    <label className="text-slate-700 font-semibold">Points</label>
                    <input
                      type="number"
                      min={1}
                      value={qPointsInput}
                      onChange={(e) => setQPointsInput(parseInt(e.target.value, 10) || 1)}
                      className="w-full p-1.5 rounded bg-white border border-slate-300 text-emerald-700 font-bold"
                    />
                  </div>
                  <div className="space-y-1 col-span-2 flex items-center justify-between">
                    <label className="flex items-center gap-2 cursor-pointer text-slate-700 pt-3 font-sans font-semibold">
                      <input
                        type="checkbox"
                        checked={qNegEnabledInput}
                        onChange={(e) => setQNegEnabledInput(e.target.checked)}
                        className="rounded text-emerald-600"
                      />
                      <span>Negative Marking</span>
                    </label>
                    {qNegEnabledInput && (
                      <div className="flex items-center gap-1 pt-2">
                        <span className="text-slate-500">Penalty:</span>
                        <input
                          type="number"
                          min={0}
                          value={qNegPointsInput}
                          onChange={(e) => setQNegPointsInput(parseInt(e.target.value, 10) || 0)}
                          className="w-16 p-1 rounded bg-white border border-slate-300 text-rose-600 font-bold"
                        />
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-200">
              <Button variant="ghost" size="sm" onClick={() => setIsQuestionPickerOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                disabled={!selectedQvId}
                onClick={handleAddQuestionToAssessment}
              >
                Add to Assessment
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Pre-Publish Confirmation Modal */}
      {isPublishModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <Card className="w-full max-w-md p-6 space-y-5 bg-white shadow-2xl animate-fade-in border-slate-200">
            <div className="flex items-start gap-3">
              <div className="p-2.5 rounded-full bg-purple-100 text-purple-700">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-bold text-slate-900">Publish Examination</h3>
                <p className="text-xs text-slate-500">
                  Confirm candidate enrollment and freeze parameters.
                </p>
              </div>
            </div>

            {publishError && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-start gap-2.5 text-xs text-rose-700">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
                <div className="space-y-0.5">
                  <p className="font-semibold text-rose-900">Publication failed</p>
                  <p className="text-rose-700 font-mono text-[11px] break-words">{publishError}</p>
                </div>
              </div>
            )}

            <div className="p-4 bg-purple-50/70 rounded-xl border border-purple-200 space-y-2.5 text-xs">
              <div className="flex justify-between text-slate-700">
                <span className="font-medium">Eligible Candidates:</span>
                <span className="font-mono font-bold text-purple-800">{audienceTotalEligible} candidates</span>
              </div>
              <div className="flex justify-between text-slate-700">
                <span className="font-medium">Total Questions:</span>
                <span className="font-mono font-bold text-slate-900">{linkedQuestions.length} questions</span>
              </div>
              <div className="flex justify-between text-slate-700">
                <span className="font-medium">Total Points:</span>
                <span className="font-mono font-bold text-slate-900">{totalPoints} pts</span>
              </div>
              <div className="flex justify-between text-slate-700">
                <span className="font-medium">Duration:</span>
                <span className="font-mono font-bold text-slate-900">{durationMinutes} mins</span>
              </div>
              <div className="flex justify-between text-slate-700">
                <span className="font-medium">Proctoring:</span>
                <span className="font-mono font-bold text-indigo-700">{proctoringEnabled ? 'Enabled' : 'Disabled'}</span>
              </div>
            </div>

            <div className="text-xs text-slate-600 space-y-1.5 leading-relaxed bg-amber-50 p-3 rounded-lg border border-amber-200">
              <p className="font-semibold text-amber-900">Authoritative Publication Notice:</p>
              <p className="text-amber-800">
                Publishing will enroll all <strong>{audienceTotalEligible} candidate(s)</strong>. The examination parameters, question versions, and proctoring configuration will become permanently locked.
              </p>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={isPublishing}
                onClick={() => setIsPublishModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="primary"
                size="sm"
                isLoading={isPublishing}
                onClick={handlePublish}
              >
                Confirm & Publish
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default AssessmentEditorPage;
