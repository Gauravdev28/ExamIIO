import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import {
  createQuestion,
  getQuestionVersionDetail,
  updateDraftVersion,
  publishVersion,
  getQuestionVersionHealth,
} from '../../api/questions';
import { QuestionTypeSelector } from '../../components/admin/QuestionTypeSelector';
import { CommonQuestionFields } from '../../components/admin/CommonQuestionFields';
import { McqQuestionEditor, McqOptionItem } from '../../components/admin/McqQuestionEditor';
import { CodingConfigEditor } from '../../components/admin/CodingConfigEditor';
import { TestCaseEditor, TestCaseItem } from '../../components/admin/TestCaseEditor';
import { QuestionReadiness, QuestionHealthData } from '../../components/admin/QuestionReadiness';
import { QuestionActions } from '../../components/admin/QuestionActions';
import { QuestionPreviewModal } from '../../components/admin/QuestionPreviewModal';
import { AlertCircle, CheckCircle2 } from 'lucide-react';
import {
  QuestionType,
  Difficulty,
  CodingLanguage,
} from '../../types/question';

export const QuestionEditorPage: React.FC = () => {
  const { id: routeQuestionId, version: routeVersionStr } = useParams<{ id?: string; version?: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const typeParam = searchParams.get('type') as QuestionType | null;

  const isEditing = Boolean(routeQuestionId && routeVersionStr);
  const routeVersionNum = routeVersionStr ? parseInt(routeVersionStr, 10) : 1;

  // Canonical Form State
  const [questionId, setQuestionId] = useState('');
  const [questionType, setQuestionType] = useState<QuestionType>('CODING');
  const [versionStatus, setVersionStatus] = useState<string>('DRAFT');
  const [title, setTitle] = useState('');
  const [statement, setStatement] = useState('');
  const [instructions, setInstructions] = useState('');
  const [points, setPoints] = useState<number>(10);
  const [negativeMarkingEnabled, setNegativeMarkingEnabled] = useState(false);
  const [negativePoints, setNegativePoints] = useState<number>(0);
  const [difficulty, setDifficulty] = useState<Difficulty>('MEDIUM');

  // MCQ State
  const [options, setOptions] = useState<McqOptionItem[]>([
    { id: 'A', text: '', is_correct: true },
    { id: 'B', text: '', is_correct: false },
    { id: 'C', text: '', is_correct: false },
    { id: 'D', text: '', is_correct: false },
  ]);

  // Coding State
  const [constraints, setConstraints] = useState('');
  const [allowedLanguages, setAllowedLanguages] = useState<CodingLanguage[]>(['PYTHON', 'CPP', 'JAVA', 'C']);
  const [starterCodes, setStarterCodes] = useState<Record<string, string>>({
    PYTHON: 'def solve():\n    pass\n',
    CPP: '#include <bits/stdc++.h>\n',
    JAVA: 'import java.io.*;\n',
    C: '#include <stdio.h>\n',
  });
  const [timeLimitMs, setTimeLimitMs] = useState<number>(2000);
  const [memoryLimitMb, setMemoryLimitMb] = useState<number>(256);

  // Test Cases State
  const [testCases, setTestCases] = useState<TestCaseItem[]>([
    { case_id: 'TC01', input_data: '2 3', expected_output: '5', points: 5, is_hidden: false, is_example: true },
    { case_id: 'TC02', input_data: '10 20', expected_output: '30', points: 5, is_hidden: true, is_example: false },
  ]);

  // Health State
  const [healthData, setHealthData] = useState<QuestionHealthData | null>(null);
  const [isHealthLoading, setIsHealthLoading] = useState(false);

  // UI / Async State
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  // Initialize Question Type from query param in Create mode
  useEffect(() => {
    if (!isEditing && typeParam) {
      if (typeParam === 'MCQ' || typeParam === 'CODING') {
        setQuestionType(typeParam);
      }
    }
  }, [isEditing, typeParam]);

  const loadHealth = useCallback(async (qId: string, vNum: number) => {
    setIsHealthLoading(true);
    try {
      const res = await getQuestionVersionHealth(qId, vNum);
      if (res.data) {
        setHealthData(res.data);
      }
    } catch {
      // Health check endpoint might be unavailable or non-coding
    } finally {
      setIsHealthLoading(false);
    }
  }, []);

  const loadVersionData = useCallback(async (qId: string, vNum: number) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await getQuestionVersionDetail(qId, vNum);
      if (res.data) {
        const v = res.data;
        const qType = v.question_type === 'MCQ' ? 'MCQ' : 'CODING';
        setQuestionType(qType);
        setQuestionId(v.question_id || qId);
        setVersionStatus(v.status);
        setTitle(v.title || '');
        setStatement(v.description || '');
        setInstructions(v.instructions || '');
        setPoints(v.points || 10);
        setNegativeMarkingEnabled(Boolean(v.negative_marking_enabled));
        setNegativePoints(v.negative_points || 0);
        setDifficulty(v.difficulty || 'MEDIUM');

        if (qType === 'MCQ' && v.type_config?.options) {
          const rawOpts = v.type_config.options;
          const corrList = v.type_config.correct_options || [];
          const corrSingle = v.type_config.correct_option;
          setOptions(
            rawOpts.map((o: any) => ({
              id: o.id || o.key,
              text: o.text || '',
              is_correct: Boolean(o.is_correct || corrList.includes(o.id) || o.id === corrSingle),
            }))
          );
        } else if (qType === 'CODING' && v.coding_config) {
          setConstraints(v.coding_config.constraints || '');
          if (v.coding_config.allowed_languages && v.coding_config.allowed_languages.length > 0) {
            setAllowedLanguages(v.coding_config.allowed_languages);
          } else {
            setAllowedLanguages(['PYTHON', 'CPP', 'JAVA', 'C']);
          }
          if (v.coding_config.starter_codes) {
            setStarterCodes(v.coding_config.starter_codes);
          }
          setTimeLimitMs(v.coding_config.time_limit_ms || 2000);
          setMemoryLimitMb(v.coding_config.memory_limit_mb || 256);
          if (v.coding_config.test_cases && v.coding_config.test_cases.length > 0) {
            setTestCases(
              v.coding_config.test_cases.map((tc: any, idx: number) => ({
                case_id: tc.name || `TC${idx + 1}`,
                input_data: tc.input_data || '',
                expected_output: tc.expected_output || '',
                points: tc.points || 1,
                is_hidden: Boolean(tc.is_hidden),
                is_example: Boolean(tc.is_example),
              }))
            );
          }
        }

        if (qType === 'CODING') {
          await loadHealth(qId, vNum);
        }
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to load question details.');
    } finally {
      setIsLoading(false);
    }
  }, [loadHealth]);

  useEffect(() => {
    if (isEditing && routeQuestionId && routeVersionNum) {
      loadVersionData(routeQuestionId, routeVersionNum);
    }
  }, [isEditing, routeQuestionId, routeVersionNum, loadVersionData]);

  // Build Payload conforming to Canonical Architecture
  const buildPayload = () => {
    const basePayload: any = {
      question_type: questionType,
      title: title.trim(),
      description: statement.trim(),
      instructions: instructions.trim(),
      points,
      negative_marking_enabled: negativeMarkingEnabled,
      negative_points: negativeMarkingEnabled ? negativePoints : 0,
      difficulty,
    };

    if (questionType === 'MCQ') {
      const correctOpt = options.find((o) => o.is_correct)?.id || 'A';
      basePayload.type_config = {
        options: options.map((o) => ({ id: o.id.trim(), text: o.text.trim(), is_correct: o.is_correct })),
        correct_options: [correctOpt],
        correct_option: correctOpt,
      };
    } else {
      // Examples derived from sample tests marked as is_example
      const examples = testCases
        .filter((tc) => tc.is_example)
        .map((tc) => ({
          input: tc.input_data,
          output: tc.expected_output,
          explanation: '',
        }));

      basePayload.coding_config = {
        problem_statement: statement.trim(),
        constraints: constraints.trim(),
        allowed_languages: allowedLanguages,
        starter_codes: starterCodes,
        time_limit_ms: timeLimitMs,
        memory_limit_mb: memoryLimitMb,
        examples,
      };

      basePayload.test_cases = testCases.map((tc, idx) => ({
        name: tc.case_id || `TC${idx + 1}`,
        input_data: tc.input_data,
        expected_output: tc.expected_output,
        points: tc.points,
        is_hidden: tc.is_hidden,
        is_example: tc.is_example,
        execution_order: idx + 1,
        is_verified: true,
      }));
    }

    return basePayload;
  };

  const handleSaveDraft = async () => {
    if (questionType === 'CODING' && allowedLanguages.length === 0) {
      setErrorMessage('At least one programming language must be enabled.');
      return;
    }
    setIsSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    const payload = buildPayload();

    try {
      if (!isEditing) {
        const res = await createQuestion(payload);
        if (res.data) {
          setSuccessMessage('Question created successfully in DRAFT status.');
          navigate(`/admin/questions/${res.data.question_id}/versions/${res.data.version_number}`);
        }
      } else {
        await updateDraftVersion(routeQuestionId!, routeVersionNum, payload);
        setSuccessMessage('Draft saved successfully.');
        if (questionType === 'CODING') {
          await loadHealth(routeQuestionId!, routeVersionNum);
        }
      }
    } catch (err: any) {
      const msg =
        err.error?.message ||
        err.error?.detail ||
        (err.error?.errors ? err.error.errors.join(', ') : null) ||
        err.message ||
        'Failed to save draft.';
      setErrorMessage(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const handlePublish = async () => {
    if (questionType === 'CODING' && allowedLanguages.length === 0) {
      setErrorMessage('At least one programming language must be enabled.');
      return;
    }
    if (
      !window.confirm(
        'Are you sure you want to publish this question? Once published, this version will become permanently IMMUTABLE.'
      )
    ) {
      return;
    }

    setIsPublishing(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const payload = buildPayload();
      let targetQId = routeQuestionId;
      let targetVNum = routeVersionNum;

      if (!isEditing || !targetQId) {
        // Save as draft first
        const createRes = await createQuestion(payload);
        if (!createRes.data) {
          throw new Error('Failed to create question draft.');
        }
        targetQId = createRes.data.question_id;
        targetVNum = createRes.data.version_number;
      } else {
        await updateDraftVersion(targetQId, targetVNum, payload);
      }

      // 2. Publish
      const res = await publishVersion(targetQId!, targetVNum);
      if (res.data) {
        setVersionStatus('PUBLISHED');
        setSuccessMessage('Question published successfully! Version is now locked and immutable.');
        if (questionType === 'CODING') {
          await loadHealth(targetQId!, targetVNum);
        }
        if (!isEditing && targetQId) {
          navigate(`/admin/questions/${targetQId}/versions/${targetVNum}`, { replace: true });
        }
      }
    } catch (err: any) {
      const msg =
        err.error?.message ||
        err.error?.detail ||
        (err.error?.errors ? err.error.errors.join(', ') : null) ||
        err.message ||
        'Failed to publish question.';
      setErrorMessage(msg);
    } finally {
      setIsPublishing(false);
    }
  };

  const isLocked = versionStatus === 'PUBLISHED' || versionStatus === 'ARCHIVED';

  if (isLoading) {
    return (
      <div className="w-full px-4 sm:px-6 lg:px-8 py-16 flex flex-col items-center justify-center space-y-3">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs text-slate-500 font-mono">Loading question configuration...</p>
      </div>
    );
  }

  return (
    <div className="w-full px-4 sm:px-6 lg:px-8 py-8">
      <div className="w-full">
        {/* Page Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              {isLocked ? 'View Question' : isEditing ? 'Edit Question' : 'Create Question'}
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              {isLocked
                ? 'Published Question — Locked & Permanently Immutable.'
                : 'Canonical Question Authoring — Simple, Clean, Tab-Free Architecture.'}
            </p>
          </div>
          {isEditing && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono px-2 py-1 bg-slate-200 text-slate-700 rounded">
                v{routeVersionNum}
              </span>
            </div>
          )}
        </div>

        {/* Alerts */}
        {errorMessage && (
          <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 flex items-start gap-3 text-red-800 text-sm">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-semibold text-red-900">Validation / Execution Error</p>
              <p className="text-xs mt-0.5 leading-relaxed">{errorMessage}</p>
            </div>
          </div>
        )}

        {successMessage && (
          <div className="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex items-start gap-3 text-emerald-800 text-sm">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-semibold text-emerald-900">Success</p>
              <p className="text-xs mt-0.5 leading-relaxed">{successMessage}</p>
            </div>
          </div>
        )}

        {/* 1. Question Type Selector */}
        <QuestionTypeSelector
          questionType={questionType}
          onChange={(t) => {
            if (t === 'MCQ' || t === 'CODING') {
              setQuestionType(t);
            }
          }}
          disabled={isEditing || isLocked}
        />

        {/* 2. Common Fields */}
        <CommonQuestionFields
          questionId={questionId}
          onQuestionIdChange={setQuestionId}
          title={title}
          onTitleChange={setTitle}
          difficulty={difficulty}
          onDifficultyChange={setDifficulty}
          points={points}
          onPointsChange={setPoints}
          negativeMarkingEnabled={negativeMarkingEnabled}
          onNegativeMarkingChange={setNegativeMarkingEnabled}
          negativePoints={negativePoints}
          onNegativePointsChange={setNegativePoints}
          statement={statement}
          onStatementChange={setStatement}
          instructions={instructions}
          onInstructionsChange={setInstructions}
          disabled={isLocked}
          isEditing={isEditing}
        />

        {/* 3. Question-Type Specific Configuration */}
        {questionType === 'MCQ' ? (
          <McqQuestionEditor
            options={options}
            onChange={setOptions}
            disabled={isLocked}
          />
        ) : (
          <>
            {/* Coding Configuration */}
            <CodingConfigEditor
              constraints={constraints}
              onConstraintsChange={setConstraints}
              allowedLanguages={allowedLanguages}
              onAllowedLanguagesChange={setAllowedLanguages}
              starterCodes={starterCodes}
              onStarterCodesChange={setStarterCodes}
              timeLimitMs={timeLimitMs}
              onTimeLimitChange={setTimeLimitMs}
              memoryLimitMb={memoryLimitMb}
              onMemoryLimitChange={setMemoryLimitMb}
              disabled={isLocked}
            />

            {/* Test Cases */}
            <TestCaseEditor
              testCases={testCases}
              onChange={setTestCases}
              allowedLanguages={allowedLanguages}
              starterCodes={starterCodes}
              disabled={isLocked}
            />
          </>
        )}

        {/* 4. Question Readiness & Health */}
        <QuestionReadiness
          healthData={healthData}
          isLoading={isHealthLoading}
          onRefreshHealth={
            isEditing && routeQuestionId && routeVersionNum && questionType === 'CODING'
              ? () => loadHealth(routeQuestionId, routeVersionNum)
              : undefined
          }
          questionType={questionType === 'MCQ' ? 'MCQ' : 'CODING'}
        />

        {/* 5. Actions Bar */}
        <QuestionActions
          status={versionStatus}
          isPublished={isLocked}
          isSaving={isSaving}
          isPublishing={isPublishing}
          canPublish={!isLocked && (questionType === 'MCQ' || healthData?.is_data_ready !== false)}
          onSaveDraft={handleSaveDraft}
          onPublish={handlePublish}
          onPreview={() => {
            if (!isEditing) {
              alert('Please save a draft first to preview the candidate view.');
              return;
            }
            setIsPreviewOpen(true);
          }}
          onBack={() => navigate('/admin/questions')}
        />

        {/* Candidate Preview Modal */}
        <QuestionPreviewModal
          isOpen={isPreviewOpen}
          onClose={() => setIsPreviewOpen(false)}
          questionId={routeQuestionId || null}
          versionNumber={routeVersionNum || null}
        />
      </div>
    </div>
  );
};

export default QuestionEditorPage;
