import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  getQuestions,
  duplicateQuestion,
  publishVersion,
} from '../../api/questions';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { PageHeader } from '../../components/common/PageHeader';
import { Tabs, TabItem } from '../../components/common/Tabs';
import { ErrorBoundary } from '../../components/common/ErrorBoundary';
import { QuestionPreviewModal } from '../../components/admin/QuestionPreviewModal';
import { ImportQuestionsModal } from '../../components/admin/ImportQuestionsModal';
import { DeleteQuestionModal } from '../../components/admin/DeleteQuestionModal';
import {
  HelpCircle,
  Plus,
  Search,
  Eye,
  Edit,
  FileText,
  AlertCircle,
  Filter,
  ChevronLeft,
  ChevronRight,
  FileSpreadsheet,
  Copy,
  Trash2,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react';
import { QuestionItem } from '../../types/question';

export const AdminQuestionsPage: React.FC = () => {
  const navigate = useNavigate();
  const [questions, setQuestions] = useState<QuestionItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 15;

  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'ALL' | 'PUBLISHED' | 'DRAFT'>('ALL');
  const [selectedType, setSelectedType] = useState('');
  const [selectedDifficulty, setSelectedDifficulty] = useState('');

  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Modals state
  const [previewQuestionId, setPreviewQuestionId] = useState<string | null>(null);
  const [previewVersionNumber, setPreviewVersionNumber] = useState<number | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [deleteTargetQuestion, setDeleteTargetQuestion] = useState<QuestionItem | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  const fetchQuestions = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const filters: any = {
        page: currentPage,
        page_size: pageSize,
      };

      if (searchQuery.trim()) filters.search = searchQuery.trim();
      if (selectedType) filters.type = selectedType;
      if (selectedDifficulty) filters.difficulty = selectedDifficulty;

      if (activeTab === 'PUBLISHED') filters.version_status = 'PUBLISHED';
      else if (activeTab === 'DRAFT') filters.version_status = 'DRAFT';

      const res = await getQuestions(filters);
      if (res && res.data) {
        setQuestions(Array.isArray(res.data.results) ? res.data.results : []);
        setTotalCount(typeof res.data.count === 'number' ? res.data.count : 0);
      } else if (res && Array.isArray((res as any).results)) {
        setQuestions((res as any).results);
        setTotalCount(typeof (res as any).count === 'number' ? (res as any).count : (res as any).results.length);
      } else if (Array.isArray(res)) {
        setQuestions(res);
        setTotalCount(res.length);
      } else {
        setQuestions([]);
        setTotalCount(0);
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to load question bank.');
      setQuestions([]);
      setTotalCount(0);
    } finally {
      setIsLoading(false);
    }
  }, [currentPage, activeTab, selectedType, selectedDifficulty, searchQuery]);

  useEffect(() => {
    fetchQuestions();
  }, [fetchQuestions]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
    fetchQuestions();
  };

  const handleOpenPreview = (qId: string, vNum: number) => {
    setPreviewQuestionId(qId);
    setPreviewVersionNumber(vNum);
    setIsPreviewOpen(true);
  };

  const handlePublish = async (qId: string, vNum: number) => {
    try {
      const res = await publishVersion(qId, vNum);
      if (res.data) {
        fetchQuestions();
      }
    } catch (err: any) {
      alert(err.error?.message || err.message || 'Failed to publish question version.');
    }
  };

  const handleDuplicate = async (q: QuestionItem) => {
    try {
      const res = await duplicateQuestion(q.id);
      if (res.data) {
        fetchQuestions();
        const targetQId = res.data.question_id || res.data.id;
        navigate(`/admin/questions/${targetQId}/versions/${res.data.version_number}`);
      }
    } catch (err: any) {
      alert(err.error?.message || 'Failed to duplicate question.');
    }
  };

  const handleOpenDeleteModal = (question: QuestionItem) => {
    setDeleteTargetQuestion(question);
    setIsDeleteModalOpen(true);
  };

  const totalPages = Math.ceil(totalCount / pageSize);

  const statusTabs: TabItem<'ALL' | 'PUBLISHED' | 'DRAFT'>[] = [
    { id: 'ALL', label: 'ALL' },
    { id: 'PUBLISHED', label: 'PUBLISHED' },
    { id: 'DRAFT', label: 'DRAFTS' },
  ];

  const renderQuestionTypeBadge = (type: string) => {
    switch (type) {
      case 'MCQ':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            Multiple Choice
          </span>
        );
      case 'CODING':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            Coding
          </span>
        );
      default:
        return <Badge variant="neutral">{type}</Badge>;
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 space-y-6 max-w-7xl">
      <PageHeader
        icon={<HelpCircle className="w-6 h-6" />}
        title="Question Bank"
        description="Immutable versioned question bank with automated testing, coding sandboxes, and canonical Excel import."
        actions={
          <div className="flex items-center gap-3">
            <Button
              variant="secondary"
              size="md"
              onClick={() => setIsImportModalOpen(true)}
              className="text-slate-800 bg-white hover:bg-slate-50 border-slate-300 font-semibold"
              aria-label="Import Questions"
            >
              <FileSpreadsheet className="w-4 h-4 mr-1.5 text-emerald-600" />
              Import Questions
            </Button>
            <Button
              variant="primary"
              size="md"
              onClick={() => navigate('/admin/questions/create')}
              aria-label="Create Question"
            >
              <Plus className="w-4 h-4 mr-1.5" />
              Create Question
            </Button>
          </div>
        }
      />

      <Card className="p-4 space-y-4 bg-white border border-slate-200 shadow-sm">
        <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
          <Tabs<'ALL' | 'PUBLISHED' | 'DRAFT'>
            tabs={statusTabs}
            activeTab={activeTab}
            onChange={(tab) => {
              setActiveTab(tab);
              setCurrentPage(1);
            }}
          />

          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 w-full md:w-auto">
            <div className="relative flex-1 md:w-64">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search questions or tags..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>
            <Button type="submit" variant="secondary" size="sm">
              Search
            </Button>
          </form>
        </div>

        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-slate-100 text-xs">
          <div className="flex items-center gap-1.5 text-slate-500 font-medium">
            <Filter className="w-3.5 h-3.5" />
            <span>Filters:</span>
          </div>

          <select
            value={selectedType}
            onChange={(e) => {
              setSelectedType(e.target.value);
              setCurrentPage(1);
            }}
            className="px-2.5 py-1 rounded-md border border-slate-200 text-slate-700 bg-white text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
          >
            <option value="">All Question Types</option>
            <option value="MCQ">Multiple Choice</option>
            <option value="CODING">Coding</option>
          </select>

          <select
            value={selectedDifficulty}
            onChange={(e) => {
              setSelectedDifficulty(e.target.value);
              setCurrentPage(1);
            }}
            className="px-2.5 py-1 rounded-md border border-slate-200 text-slate-700 bg-white text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
          >
            <option value="">All Difficulties</option>
            <option value="EASY">Easy</option>
            <option value="MEDIUM">Medium</option>
            <option value="HARD">Hard</option>
          </select>

          {(selectedType || selectedDifficulty || searchQuery) && (
            <button
              onClick={() => {
                setSelectedType('');
                setSelectedDifficulty('');
                setSearchQuery('');
                setCurrentPage(1);
              }}
              className="text-xs text-rose-600 hover:underline ml-auto font-medium"
            >
              Reset Filters
            </button>
          )}
        </div>
      </Card>

      <Card className="overflow-hidden border border-slate-200 shadow-sm bg-white">
        {isLoading ? (
          <div className="p-12 text-center text-slate-500 text-xs font-mono">
            <div className="w-6 h-6 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            Loading question bank records...
          </div>
        ) : errorMessage ? (
          <div className="p-8 text-center text-rose-700 text-xs space-y-3">
            <AlertCircle className="w-6 h-6 mx-auto text-rose-600" />
            <p className="font-semibold">{errorMessage}</p>
            <Button
              variant="secondary"
              size="sm"
              onClick={fetchQuestions}
              className="mt-2 inline-flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Retry Loading Questions
            </Button>
          </div>
        ) : !Array.isArray(questions) || questions.length === 0 ? (
          <div className="p-16 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-400">
              <HelpCircle className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-bold text-slate-900">No questions found</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              There are no questions matching your current tab and filters. Create a new question or import via canonical Excel template.
            </p>
            <Button
              variant="primary"
              size="sm"
              onClick={() => navigate('/admin/questions/create')}
              className="mt-2"
            >
              <Plus className="w-4 h-4 mr-1.5" />
              Create First Question
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="px-4 py-3">ID</th>
                  <th className="px-4 py-3">Title</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Difficulty</th>
                  <th className="px-4 py-3">Points</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Version</th>
                  <th className="px-4 py-3">Health</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {questions.map((q) => {
                  if (!q) return null;
                  const targetVer = q.latest_version;
                  const isPublished = targetVer?.status === 'PUBLISHED';
                  const isDraft = targetVer?.status === 'DRAFT';
                  const qIdStr = String(q.id || '');
                  const qIdShort = qIdStr ? (qIdStr.length > 8 ? `${qIdStr.slice(0, 8)}…` : qIdStr) : '—';
                  const versionNum = targetVer?.version_number ?? 1;

                  return (
                    <tr key={q.id || Math.random()} className="hover:bg-slate-50/80 transition-colors">
                      {/* ID */}
                      <td className="px-4 py-3.5 font-mono text-[11px] text-slate-500 font-semibold" title={qIdStr}>
                        {qIdShort}
                      </td>

                      {/* Title */}
                      <td className="px-4 py-3.5 max-w-xs md:max-w-sm">
                        <div className="font-bold text-slate-900 text-sm">
                          <Link
                            to={
                              targetVer
                                ? `/admin/questions/${q.id}/versions/${versionNum}`
                                : `/admin/questions/${q.id}`
                            }
                            className="hover:text-emerald-600 line-clamp-1"
                          >
                            {targetVer?.title || '(Untitled Question)'}
                          </Link>
                        </div>
                        {targetVer?.tags && Array.isArray(targetVer.tags) && targetVer.tags.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {targetVer.tags.map((t: any, idx: number) => {
                              const tagText = typeof t === 'string' ? t : t?.name || `tag-${idx}`;
                              const tagKey = typeof t === 'string' ? `${t}-${idx}` : t?.id || t?.slug || `${tagText}-${idx}`;
                              return (
                                <span
                                  key={tagKey}
                                  className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-medium"
                                >
                                  #{tagText}
                                </span>
                              );
                            })}
                          </div>
                        )}
                      </td>

                      {/* Type */}
                      <td className="px-4 py-3.5">
                        {renderQuestionTypeBadge(q.question_type)}
                      </td>

                      {/* Difficulty */}
                      <td className="px-4 py-3.5">
                        {targetVer ? (
                          <Badge
                            variant={
                              targetVer.difficulty === 'EASY'
                                ? 'success'
                                : targetVer.difficulty === 'MEDIUM'
                                ? 'warning'
                                : 'danger'
                            }
                          >
                            {targetVer.difficulty}
                          </Badge>
                        ) : (
                          '—'
                        )}
                      </td>

                      {/* Points */}
                      <td className="px-4 py-3.5 font-bold text-emerald-700">
                        {targetVer?.points ?? '—'} pts
                      </td>

                      {/* Status */}
                      <td className="px-4 py-3.5">
                        <Badge
                          variant={
                            isPublished
                              ? 'success'
                              : isDraft
                              ? 'warning'
                              : 'neutral'
                          }
                        >
                          {targetVer?.status || q.status}
                        </Badge>
                      </td>

                      {/* Version */}
                      <td className="px-4 py-3.5">
                        <span className="text-[10px] px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-mono font-bold">
                          v{versionNum}
                        </span>
                      </td>

                      {/* Health */}
                      <td className="px-4 py-3.5">
                        {q.question_type === 'MCQ' ? (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            100% Ready
                          </span>
                        ) : targetVer?.health_status && typeof targetVer.health_status === 'object' ? (
                          targetVer.health_status.is_data_ready ? (
                            <span
                              className="inline-flex items-center px-2.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200"
                              title="11/11 Data Checks Passed. Sandbox is independent environment status."
                            >
                              11/11 Ready
                            </span>
                          ) : (
                            <span
                              className="inline-flex items-center px-2.5 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200"
                              title={`${targetVer.health_status.passed_data_checks ?? targetVer.health_status.passed_checks ?? 0} of 11 data checks passed`}
                            >
                              {targetVer.health_status.passed_data_checks ?? targetVer.health_status.passed_checks ?? 0}/11 Ready
                            </span>
                          )
                        ) : (
                          <span className="text-slate-400 text-[11px]">Ready</span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3.5 text-right space-x-1 whitespace-nowrap">
                        {targetVer && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleOpenPreview(q.id, versionNum)}
                            title="Candidate preview"
                            aria-label="Candidate preview"
                          >
                            <Eye className="w-3.5 h-3.5 text-slate-600" />
                          </Button>
                        )}
                        {targetVer && isDraft && (
                          <Link
                            to={`/admin/questions/${q.id}/versions/${versionNum}`}
                            className="inline-flex items-center justify-center p-1.5 text-slate-600 hover:text-emerald-700 hover:bg-slate-100 rounded-lg"
                            title="Edit question"
                            aria-label="Edit question"
                          >
                            <Edit className="w-3.5 h-3.5" />
                          </Link>
                        )}
                        {targetVer && isPublished && (
                          <Link
                            to={`/admin/questions/${q.id}/versions/${versionNum}`}
                            className="inline-flex items-center justify-center p-1.5 text-slate-600 hover:text-indigo-700 hover:bg-slate-100 rounded-lg"
                            title="View question"
                            aria-label="View question"
                          >
                            <FileText className="w-3.5 h-3.5" />
                          </Link>
                        )}
                        {isDraft && targetVer && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handlePublish(q.id, versionNum)}
                            title="Publish question"
                            aria-label="Publish question"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDuplicate(q)}
                          title="Duplicate question"
                          aria-label="Duplicate question"
                        >
                          <Copy className="w-3.5 h-3.5 text-slate-600" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleOpenDeleteModal(q)}
                          title="Delete question"
                          aria-label="Delete question"
                        >
                          <Trash2 className="w-3.5 h-3.5 text-rose-600" />
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="px-4 py-3 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500 bg-slate-50">
            <div>
              Showing page <span className="font-semibold text-slate-700">{currentPage}</span> of{' '}
              <span className="font-semibold text-slate-700">{totalPages}</span> ({totalCount} questions)
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>
        )}
      </Card>

      <ErrorBoundary fallbackTitle="Question Preview Modal Error">
        <QuestionPreviewModal
          questionId={previewQuestionId}
          versionNumber={previewVersionNumber}
          isOpen={isPreviewOpen}
          onClose={() => setIsPreviewOpen(false)}
        />
      </ErrorBoundary>

      <ErrorBoundary fallbackTitle="Delete Question Modal Error">
        <DeleteQuestionModal
          question={deleteTargetQuestion}
          isOpen={isDeleteModalOpen}
          onClose={() => {
            setIsDeleteModalOpen(false);
            setDeleteTargetQuestion(null);
          }}
          onSuccess={() => {
            fetchQuestions();
          }}
        />
      </ErrorBoundary>

      <ErrorBoundary fallbackTitle="Import Questions Modal Error">
        <ImportQuestionsModal
          isOpen={isImportModalOpen}
          onClose={() => setIsImportModalOpen(false)}
          onSuccess={() => {
            fetchQuestions();
          }}
        />
      </ErrorBoundary>
    </div>
  );
};

export default AdminQuestionsPage;
