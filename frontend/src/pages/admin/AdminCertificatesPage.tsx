import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Award,
  Search,
  Download,
  RefreshCw,
  CheckCircle2,
  Clock,
  AlertCircle,
  XCircle,
  Copy,
  Check,
  ArrowLeft,
  ChevronRight,
  Loader2,
  Layers,
} from 'lucide-react';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { ResultsAPI } from '../../api/results';
import {
  Certificate,
  CertificateStatus,
  AssessmentCertificateSummary,
} from '../../types/results';

export const AdminCertificatesPage: React.FC = () => {
  const { assessmentId } = useParams<{ assessmentId?: string }>();
  const navigate = useNavigate();

  // ---------------------------------------------------------------------------
  // Directory View State (All Assessments with Certificates)
  // ---------------------------------------------------------------------------
  const [summaries, setSummaries] = useState<AssessmentCertificateSummary[]>([]);
  const [loadingSummaries, setLoadingSummaries] = useState(true);
  const [summarySearch, setSummarySearch] = useState('');
  const [summaryError, setSummaryError] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Scoped View State (Certificates belonging to specific Assessment)
  // ---------------------------------------------------------------------------
  const [certificates, setCertificates] = useState<Certificate[]>([]);
  const [assessmentInfo, setAssessmentInfo] = useState<{
    id: string;
    title: string;
    status: string;
    total_certificates?: number;
  } | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [certSearch, setCertSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [loadingScoped, setLoadingScoped] = useState(true);
  const [scopedError, setScopedError] = useState<string | null>(null);
  const [is404, setIs404] = useState(false);

  // ---------------------------------------------------------------------------
  // Action State (Download, Retry, Copy)
  // ---------------------------------------------------------------------------
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // ===========================================================================
  // Load Directory Summaries
  // ===========================================================================
  const loadSummaries = useCallback(async () => {
    setLoadingSummaries(true);
    setSummaryError(null);
    try {
      const params: any = {};
      if (summarySearch.trim()) params.search = summarySearch.trim();
      const data = await ResultsAPI.getAdminCertificateAssessmentSummary(params);
      setSummaries(data || []);
    } catch (err: any) {
      const safeMsg =
        err?.response?.data?.error?.message ||
        err?.response?.data?.message ||
        err?.error?.message ||
        err.message ||
        'Failed to load assessment certificate directory.';
      setSummaryError(safeMsg);
    } finally {
      setLoadingSummaries(false);
    }
  }, [summarySearch]);

  // ===========================================================================
  // Load Scoped Certificates
  // ===========================================================================
  const loadScopedCertificates = useCallback(async () => {
    if (!assessmentId) return;
    setLoadingScoped(true);
    setScopedError(null);
    setIs404(false);
    try {
      const params: any = { page };
      if (certSearch.trim()) params.search = certSearch.trim();
      if (statusFilter !== 'all') params.status = statusFilter;

      const res = await ResultsAPI.getAdminAssessmentCertificates(assessmentId, params);
      setCertificates(res.results || []);
      setTotalCount(res.count || 0);
      if (res.assessment) {
        setAssessmentInfo(res.assessment);
      }
    } catch (err: any) {
      if (err?.response?.status === 404 || err?.status_code === 404) {
        setIs404(true);
        setScopedError('Assessment not found. The assessment may have been removed or the ID is invalid.');
      } else {
        const safeMsg =
          err?.response?.data?.error?.message ||
          err?.response?.data?.message ||
          err?.error?.message ||
          err.message ||
          'Failed to load certificates for this assessment.';
        setScopedError(safeMsg);
      }
    } finally {
      setLoadingScoped(false);
    }
  }, [assessmentId, page, statusFilter]);

  // Mount / Route Change Effects
  useEffect(() => {
    if (!assessmentId) {
      loadSummaries();
    } else {
      loadScopedCertificates();
    }
  }, [assessmentId, loadSummaries, loadScopedCertificates]);

  // Handlers
  const handleSummarySearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadSummaries();
  };

  const handleScopedSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadScopedCertificates();
  };

  const handleRetry = async (certId: string) => {
    setRetryingId(certId);
    try {
      const updated = await ResultsAPI.retryAdminCertificate(certId);
      setCertificates((prev) =>
        prev.map((c) => (c.id === certId ? updated : c))
      );
    } catch (err: any) {
      alert(err?.response?.data?.message || err?.message || 'Failed to retry certificate generation.');
    } finally {
      setRetryingId(null);
    }
  };

  const handleDownload = async (cert: Certificate) => {
    setDownloadingId(cert.id);
    try {
      await ResultsAPI.downloadAdminCertificate(cert.id, cert.certificate_id);
    } catch (err: any) {
      alert(err?.response?.data?.message || err?.message || 'Download failed or PDF not ready.');
    } finally {
      setDownloadingId(null);
    }
  };

  const copyVerificationLink = (certificateId: string) => {
    const url = `${window.location.origin}/verify/${certificateId}`;
    navigator.clipboard.writeText(url);
    setCopiedId(certificateId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const renderStatusBadge = (status: CertificateStatus) => {
    switch (status) {
      case 'ISSUED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            Issued
          </span>
        );
      case 'PENDING':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock className="w-3.5 h-3.5 text-amber-600 animate-spin" />
            Pending
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
            Failed
          </span>
        );
      case 'REVOKED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200">
            <XCircle className="w-3.5 h-3.5 text-slate-500" />
            Revoked
          </span>
        );
      default:
        return <Badge variant="neutral">{status}</Badge>;
    }
  };

  // ===========================================================================
  // VIEW 1: Assessment-Scoped Certificate Roster (/admin/assessments/:id/certificates)
  // ===========================================================================
  if (assessmentId) {
    return (
      <div className="w-full px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Breadcrumb & Navigation */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-slate-200">
          <div>
            <button
              onClick={() => navigate('/admin/certificates')}
              className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-slate-800 mb-2 transition"
            >
              <ArrowLeft className="w-4 h-4" /> Back to All Assessments
            </button>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-600/10 flex items-center justify-center text-indigo-600 shrink-0">
                <Award className="w-6 h-6" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2 flex-wrap">
                  <span>{assessmentInfo?.title || 'Assessment'}</span>
                  <span className="text-slate-400 font-normal text-lg sm:text-xl">Certificates</span>
                </h1>
                <p className="text-xs sm:text-sm text-slate-500">
                  Authoritative participation certificate roster issued for this examination.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => loadScopedCertificates()}
              disabled={loadingScoped}
              className="inline-flex items-center gap-2 px-3.5 py-2 text-xs sm:text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 disabled:opacity-50 transition shadow-sm"
            >
              <RefreshCw className={`w-4 h-4 ${loadingScoped ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Error Banner */}
        {scopedError && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-sm">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 shrink-0 text-rose-600" />
              <span>{scopedError}</span>
            </div>
            {is404 ? (
              <button
                onClick={() => navigate('/admin/certificates')}
                className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold rounded-lg transition shrink-0 self-start sm:self-auto"
              >
                Back to Certificates
              </button>
            ) : (
              <button
                onClick={() => loadScopedCertificates()}
                className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold rounded-lg transition shrink-0 self-start sm:self-auto"
              >
                Retry
              </button>
            )}
          </div>
        )}

        {/* Filter & Search Bar */}
        <Card className="p-4 bg-white border-slate-200 shadow-sm">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <form onSubmit={handleScopedSearchSubmit} className="flex items-center gap-2 w-full sm:w-80">
              <div className="relative flex-1">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search candidate, roll #, cert ID..."
                  value={certSearch}
                  onChange={(e) => setCertSearch(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 bg-white border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <button
                type="submit"
                className="px-3 py-2 bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition"
              >
                Search
              </button>
            </form>

            <div className="flex items-center gap-3 w-full sm:w-auto">
              <span className="text-xs text-slate-600 font-semibold">Status:</span>
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                className="bg-white border border-slate-300 text-slate-800 text-xs rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
              >
                <option value="all">All Statuses</option>
                <option value="ISSUED">Issued</option>
                <option value="PENDING">Pending</option>
                <option value="FAILED">Failed</option>
                <option value="REVOKED">Revoked</option>
              </select>
            </div>
          </div>
        </Card>

        {/* Content Table / Loading / Empty */}
        {loadingScoped ? (
          <div className="flex flex-col items-center justify-center p-16 space-y-3 bg-white rounded-xl border border-slate-200">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
            <span className="text-sm font-medium text-slate-600">Loading certificates...</span>
          </div>
        ) : certificates.length === 0 ? (
          <div className="text-center p-16 bg-white rounded-xl border border-slate-200 text-slate-500">
            <Award className="w-10 h-10 text-slate-400 mx-auto mb-3" />
            <h3 className="text-base font-bold text-slate-800 mb-1">No certificates found.</h3>
            <p className="text-xs text-slate-500">
              {certSearch.trim() || statusFilter !== 'all'
                ? 'No certificates match the selected filter criteria for this assessment.'
                : 'No certificates have been issued for this assessment yet.'}
            </p>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    <th className="py-3.5 px-4">Candidate</th>
                    <th className="py-3.5 px-4">EUID / Roll</th>
                    <th className="py-3.5 px-4">Certificate ID</th>
                    <th className="py-3.5 px-4">Issued At</th>
                    <th className="py-3.5 px-4">Status</th>
                    <th className="py-3.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-sm">
                  {certificates.map((c) => (
                    <tr key={c.id} className="hover:bg-slate-50/80 transition">
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-slate-900">{c.printed_name || c.student_name}</div>
                        <div className="text-xs text-slate-500">{c.student_email}</div>
                      </td>
                      <td className="py-3.5 px-4 text-slate-600 font-mono text-xs">
                        {c.student_roll_number || 'N/A'}
                      </td>
                      <td className="py-3.5 px-4">
                        <span className="font-mono text-xs text-slate-800 bg-slate-100 px-2 py-1 rounded border border-slate-200">
                          {c.certificate_id}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-xs text-slate-600">
                        {c.issued_at ? new Date(c.issued_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="py-3.5 px-4">{renderStatusBadge(c.status)}</td>
                      <td className="py-3.5 px-4 text-right space-x-2">
                        {c.status === 'ISSUED' && c.has_pdf && (
                          <button
                            onClick={() => handleDownload(c)}
                            disabled={downloadingId === c.id}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-lg text-xs font-semibold transition"
                            title="Download Certificate PDF"
                          >
                            <Download className="w-3.5 h-3.5" />
                            {downloadingId === c.id ? 'Downloading...' : 'Download'}
                          </button>
                        )}
                        <button
                          onClick={() => copyVerificationLink(c.certificate_id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition"
                          title="Copy Public Verification Link"
                        >
                          {copiedId === c.certificate_id ? (
                            <>
                              <Check className="w-3.5 h-3.5 text-emerald-600" />
                              <span className="text-emerald-700">Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3.5 h-3.5" />
                              <span>Verify Link</span>
                            </>
                          )}
                        </button>
                        {(c.status === 'FAILED' || c.status === 'PENDING') && (
                          <button
                            onClick={() => handleRetry(c.id)}
                            disabled={retryingId === c.id}
                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 rounded-lg text-xs font-semibold transition"
                          >
                            <RefreshCw className={`w-3.5 h-3.5 ${retryingId === c.id ? 'animate-spin' : ''}`} />
                            Retry
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between p-4 border-t border-slate-200 bg-white text-xs text-slate-600">
              <div>Total Certificates: {totalCount}</div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 bg-slate-100 border border-slate-200 hover:bg-slate-200 disabled:opacity-50 text-slate-700 font-medium rounded-lg transition"
                >
                  Previous
                </button>
                <span className="font-semibold text-slate-800">Page {page}</span>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={certificates.length < 20}
                  className="px-3 py-1.5 bg-slate-100 border border-slate-200 hover:bg-slate-200 disabled:opacity-50 text-slate-700 font-medium rounded-lg transition"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ===========================================================================
  // VIEW 2: Assessment-Wise Directory Landing View (/admin/certificates)
  // ===========================================================================
  const totalCertsAcrossAll = summaries.reduce((acc, s) => acc + (s.certificate_count || 0), 0);

  return (
    <div className="w-full px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-slate-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600/10 flex items-center justify-center text-indigo-600 shrink-0">
            <Award className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Participation Certificates
            </h1>
            <p className="text-sm text-slate-500">
              Authoritative participation certificate roster organized by examination.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => loadSummaries()}
            disabled={loadingSummaries}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 disabled:opacity-50 transition shadow-sm"
          >
            <RefreshCw className={`w-4 h-4 ${loadingSummaries ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card className="p-5 bg-white border-slate-200 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shrink-0">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Examinations with Certificates
            </div>
            <div className="text-2xl font-extrabold text-slate-900 mt-0.5">
              {summaries.length}
            </div>
          </div>
        </Card>

        <Card className="p-5 bg-white border-slate-200 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 shrink-0">
            <Award className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Total Certificates Issued
            </div>
            <div className="text-2xl font-extrabold text-emerald-700 mt-0.5">
              {totalCertsAcrossAll}
            </div>
          </div>
        </Card>
      </div>

      {/* Error Banner */}
      {summaryError && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-sm">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 shrink-0 text-rose-600" />
            <span>{summaryError}</span>
          </div>
          <button
            onClick={() => loadSummaries()}
            className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold rounded-lg transition shrink-0 self-start sm:self-auto"
          >
            Retry
          </button>
        </div>
      )}

      {/* Search Bar */}
      <Card className="p-4 bg-white border-slate-200 shadow-sm">
        <form onSubmit={handleSummarySearchSubmit} className="flex items-center gap-2 max-w-md">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search assessment title..."
              value={summarySearch}
              onChange={(e) => setSummarySearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-white border border-slate-300 text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <button
            type="submit"
            className="px-4 py-2 bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-700 text-xs sm:text-sm font-semibold rounded-lg transition"
          >
            Search
          </button>
        </form>
      </Card>

      {/* Assessments List / Cards */}
      {loadingSummaries ? (
        <div className="flex flex-col items-center justify-center p-16 space-y-3 bg-white rounded-xl border border-slate-200">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
          <span className="text-sm font-medium text-slate-600">Loading assessments...</span>
        </div>
      ) : summaries.length === 0 ? (
        <div className="text-center p-16 bg-white rounded-xl border border-slate-200 text-slate-500">
          <Award className="w-12 h-12 text-slate-400 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-slate-800 mb-1">No certificates found.</h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto mb-4">
            {summarySearch.trim()
              ? 'No assessments match your search query.'
              : 'There are currently no examinations with issued participation certificates.'}
          </p>
          <button
            onClick={() => navigate('/admin/assessments')}
            className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs rounded-lg transition"
          >
            Go to Assessments
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {summaries.map((s) => (
            <Card
              key={s.id}
              className="p-6 bg-white border-slate-200 hover:border-indigo-300 hover:shadow-md transition flex flex-col justify-between"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-base font-bold text-slate-900 truncate" title={s.title}>
                      {s.title}
                    </h3>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant="neutral" size="sm">
                        {s.status}
                      </Badge>
                      <span className="text-xs text-slate-500 font-medium">
                        {s.duration_minutes} mins &bull; {s.total_points} pts
                      </span>
                    </div>
                  </div>
                </div>

                <div className="pt-2">
                  <div className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-50 border border-indigo-100 rounded-lg text-indigo-700 font-bold text-xs">
                    <Award className="w-4 h-4" />
                    <span>
                      {s.certificate_count} {s.certificate_count === 1 ? 'certificate' : 'certificates'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-100">
                <button
                  onClick={() => navigate(`/admin/assessments/${s.id}/certificates`)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs sm:text-sm rounded-lg shadow-sm transition"
                >
                  <span>View Certificates</span>
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
