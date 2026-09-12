import React, { useEffect, useState } from 'react';
import {
  Award,
  Search,
  Download,
  RefreshCw,
  ExternalLink,
  CheckCircle2,
  Clock,
  AlertCircle,
  XCircle,
  FileText,
  Copy,
  Check,
} from 'lucide-react';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { ResultsAPI } from '../../api/results';
import { Certificate, CertificateStatus } from '../../types/results';

export const AdminCertificatesPage: React.FC = () => {
  const [certificates, setCertificates] = useState<Certificate[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [loading, setLoading] = useState(true);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadCertificates();
  }, [page, statusFilter]);

  const loadCertificates = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = { page };
      if (search.trim()) params.search = search.trim();
      if (statusFilter !== 'all') params.status = statusFilter;

      const res = await ResultsAPI.getAdminCertificates(params);
      setCertificates(res.results);
      setTotalCount(res.count);
    } catch (err: any) {
      setError(err?.response?.data?.message || err.message || 'Failed to load certificates.');
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadCertificates();
  };

  const handleRetry = async (certId: string) => {
    setRetryingId(certId);
    try {
      const updated = await ResultsAPI.retryAdminCertificate(certId);
      setCertificates((prev) =>
        prev.map((c) => (c.id === certId ? updated : c))
      );
    } catch (err: any) {
      alert(err?.response?.data?.message || 'Failed to retry certificate generation.');
    } finally {
      setRetryingId(null);
    }
  };

  const handleDownload = async (cert: Certificate) => {
    setDownloadingId(cert.id);
    try {
      await ResultsAPI.downloadAdminCertificate(cert.id, cert.certificate_id);
    } catch (err: any) {
      alert(err?.response?.data?.message || 'Download failed or PDF not ready.');
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

  return (
    <div className="min-h-screen bg-slate-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-600/10 flex items-center justify-center text-indigo-600">
                <Award className="w-6 h-6" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                  Participation Certificates
                </h1>
                <p className="text-sm text-slate-500">
                  Authoritative participation certificate roster for Craft Society examinations.
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => loadCertificates()}
              className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition shadow-sm"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Filter & Search Bar */}
        <Card className="p-4 bg-white border-slate-200 shadow-sm">
          <form onSubmit={handleSearchSubmit} className="flex flex-col md:flex-row gap-4 items-center justify-between">
            <div className="relative flex-1 w-full">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search by Roll No, Candidate Name, Email, or Certificate ID..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 text-sm bg-slate-50 border border-slate-200 rounded-lg text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition"
              />
            </div>

            <div className="flex items-center gap-3 w-full md:w-auto">
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                className="px-3.5 py-2 text-sm bg-slate-50 border border-slate-200 rounded-lg text-slate-800 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="all">All Statuses</option>
                <option value="ISSUED">Issued</option>
                <option value="PENDING">Pending</option>
                <option value="FAILED">Failed</option>
                <option value="REVOKED">Revoked</option>
              </select>

              <button
                type="submit"
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition shadow-sm"
              >
                Search
              </button>
            </div>
          </form>
        </Card>

        {/* Error Alert */}
        {error && (
          <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-700 flex items-center gap-3">
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-600" />
            <span>{error}</span>
          </div>
        )}

        {/* Certificates Table */}
        <Card className="overflow-hidden bg-white border-slate-200 shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50/80 text-xs uppercase font-semibold text-slate-500 tracking-wider border-b border-slate-200">
                <tr>
                  <th className="px-6 py-4">Certificate ID</th>
                  <th className="px-6 py-4">Candidate</th>
                  <th className="px-6 py-4">Examination</th>
                  <th className="px-6 py-4">Attempt</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4">Issued At</th>
                  <th className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading && certificates.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-slate-400">
                      <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-500" />
                      Loading certificates...
                    </td>
                  </tr>
                ) : certificates.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-slate-400">
                      <FileText className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                      No certificates found matching criteria.
                    </td>
                  </tr>
                ) : (
                  certificates.map((cert) => (
                    <tr key={cert.id} className="hover:bg-slate-50/60 transition">
                      {/* Certificate ID */}
                      <td className="px-6 py-4 font-mono font-medium text-indigo-600 text-xs">
                        <div className="flex items-center gap-2">
                          <span>{cert.certificate_id}</span>
                          <button
                            onClick={() => copyVerificationLink(cert.certificate_id)}
                            title="Copy Verification Link"
                            className="text-slate-400 hover:text-slate-600 transition"
                          >
                            {copiedId === cert.certificate_id ? (
                              <Check className="w-3.5 h-3.5 text-emerald-600" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>
                      </td>

                      {/* Candidate */}
                      <td className="px-6 py-4">
                        <div className="font-semibold text-slate-900">{cert.printed_name}</div>
                        <div className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
                          {cert.student_roll_number && (
                            <span className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">
                              {cert.student_roll_number}
                            </span>
                          )}
                          <span>{cert.student_email}</span>
                        </div>
                      </td>

                      {/* Exam Title */}
                      <td className="px-6 py-4 font-medium text-slate-800">
                        {cert.exam_title}
                      </td>

                      {/* Attempt */}
                      <td className="px-6 py-4">
                        <span className="font-mono text-xs font-semibold px-2 py-0.5 bg-slate-100 text-slate-700 rounded-md">
                          Attempt #{cert.attempt_number || 1}
                        </span>
                      </td>

                      {/* Status */}
                      <td className="px-6 py-4">
                        {renderStatusBadge(cert.status)}
                      </td>

                      {/* Issued At */}
                      <td className="px-6 py-4 text-xs text-slate-500 whitespace-nowrap">
                        {cert.issued_at
                          ? new Date(cert.issued_at).toLocaleDateString('en-US', {
                              month: 'short',
                              day: 'numeric',
                              year: 'numeric',
                            })
                          : '—'}
                      </td>

                      {/* Actions */}
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {cert.status === 'ISSUED' && cert.has_pdf && (
                            <button
                              onClick={() => handleDownload(cert)}
                              disabled={downloadingId === cert.id}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition"
                            >
                              <Download className="w-3.5 h-3.5" />
                              PDF
                            </button>
                          )}

                          {(cert.status === 'FAILED' || cert.status === 'PENDING') && (
                            <button
                              onClick={() => handleRetry(cert.id)}
                              disabled={retryingId === cert.id}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-amber-700 bg-amber-50 hover:bg-amber-100 rounded-lg transition"
                            >
                              <RefreshCw className={`w-3.5 h-3.5 ${retryingId === cert.id ? 'animate-spin' : ''}`} />
                              Retry
                            </button>
                          )}

                          <a
                            href={`/verify/${cert.certificate_id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 text-slate-400 hover:text-indigo-600 rounded-lg hover:bg-slate-100 transition"
                            title="Open Public Verification Page"
                          >
                            <ExternalLink className="w-4 h-4" />
                          </a>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalCount > 20 && (
            <div className="px-6 py-4 bg-slate-50/50 border-t border-slate-200 flex items-center justify-between">
              <span className="text-xs text-slate-500">
                Showing {certificates.length} of {totalCount} records
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-50 transition"
                >
                  Previous
                </button>
                <span className="text-xs font-medium text-slate-700">Page {page}</span>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={certificates.length < 20}
                  className="px-3 py-1 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-50 transition"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};
export default AdminCertificatesPage;
