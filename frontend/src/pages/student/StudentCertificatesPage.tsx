import React, { useEffect, useState } from 'react';
import {
  Award,
  Download,
  ExternalLink,
  Copy,
  Check,
  Calendar,
  CheckCircle2,
  Clock,
  AlertCircle,
  FileCheck,
} from 'lucide-react';
import { Card } from '../../components/common/Card';
import { ResultsAPI } from '../../api/results';
import { Certificate } from '../../types/results';

export const StudentCertificatesPage: React.FC = () => {
  const [certificates, setCertificates] = useState<Certificate[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadCertificates();
  }, []);

  const loadCertificates = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await ResultsAPI.getStudentCertificates();
      setCertificates(data);
    } catch (err: any) {
      setError(err?.response?.data?.message || err.message || 'Failed to load your certificates.');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (cert: Certificate) => {
    setDownloadingId(cert.id);
    try {
      await ResultsAPI.downloadStudentCertificate(cert.id, cert.certificate_id);
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Download failed or certificate is still generating.');
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

  return (
    <div className="py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto space-y-8">
        {/* Page Header */}
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-amber-500/10 to-amber-600/20 flex items-center justify-center text-amber-600 border border-amber-200/60 shadow-sm">
              <Award className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
                My Certificates
              </h1>
              <p className="text-sm text-slate-500">
                Official Certificates of Participation earned through Craft Society at-home examinations.
              </p>
            </div>
          </div>
        </div>

        {/* Error Notification */}
        {error && (
          <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-700 flex items-center gap-3">
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-600" />
            <span>{error}</span>
          </div>
        )}

        {/* Content Body */}
        {loading ? (
          <div className="py-20 text-center text-slate-400">
            <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm font-medium">Loading your certificates...</p>
          </div>
        ) : certificates.length === 0 ? (
          <Card className="p-12 text-center bg-white border-slate-200 shadow-sm">
            <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center text-slate-400 mx-auto mb-4">
              <FileCheck className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-bold text-slate-900 mb-1">No Certificates Earned Yet</h3>
            <p className="text-sm text-slate-500 max-w-md mx-auto">
              When you attend and submit a qualifying Craft Society examination, your official Certificate of Participation will appear here.
            </p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {certificates.map((cert) => (
              <Card
                key={cert.id}
                className="relative overflow-hidden bg-white border-slate-200/90 shadow-sm hover:shadow-md transition-shadow rounded-2xl flex flex-col justify-between"
              >
                {/* Decorative Top Accent Bar */}
                <div className="h-2 bg-gradient-to-r from-amber-500 via-amber-400 to-indigo-600" />

                <div className="p-6 space-y-5">
                  {/* Category & Status */}
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-amber-600 bg-amber-50 border border-amber-200/80 px-2.5 py-1 rounded-full">
                      Participation Certificate
                    </span>
                    {cert.status === 'ISSUED' ? (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Verified
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
                        <Clock className="w-3.5 h-3.5" />
                        Processing
                      </span>
                    )}
                  </div>

                  {/* Exam & Recipient Details */}
                  <div>
                    <h2 className="text-lg font-bold text-slate-900 leading-snug">
                      {cert.exam_title}
                    </h2>
                    <p className="text-sm text-slate-600 mt-1">
                      Awarded to <span className="font-semibold text-slate-900">{cert.printed_name}</span>
                    </p>
                  </div>

                  {/* Metadata Row */}
                  <div className="pt-2 border-t border-slate-100 grid grid-cols-2 gap-3 text-xs text-slate-500">
                    <div>
                      <span className="block text-slate-400 font-medium">Issue Date</span>
                      <span className="font-semibold text-slate-700 flex items-center gap-1.5 mt-0.5">
                        <Calendar className="w-3.5 h-3.5 text-slate-400" />
                        {cert.issued_at
                          ? new Date(cert.issued_at).toLocaleDateString('en-US', {
                              month: 'short',
                              day: 'numeric',
                              year: 'numeric',
                            })
                          : 'Pending'}
                      </span>
                    </div>

                    <div>
                      <span className="block text-slate-400 font-medium">Certificate ID</span>
                      <div className="flex items-center gap-1.5 mt-0.5 font-mono font-semibold text-slate-700">
                        <span>{cert.certificate_id}</span>
                        <button
                          onClick={() => copyVerificationLink(cert.certificate_id)}
                          title="Copy Certificate ID / Link"
                          className="text-slate-400 hover:text-slate-600 transition"
                        >
                          {copiedId === cert.certificate_id ? (
                            <Check className="w-3.5 h-3.5 text-emerald-600" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Actions Footer */}
                <div className="p-4 bg-slate-50/70 border-t border-slate-100 flex items-center justify-between gap-3">
                  <button
                    onClick={() => handleDownload(cert)}
                    disabled={cert.status !== 'ISSUED' || downloadingId === cert.id}
                    className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 rounded-xl transition shadow-sm"
                  >
                    <Download className={`w-4 h-4 ${downloadingId === cert.id ? 'animate-bounce' : ''}`} />
                    {downloadingId === cert.id ? 'Downloading...' : 'Download PDF'}
                  </button>

                  <a
                    href={`/verify/${cert.certificate_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-2.5 text-slate-600 hover:text-indigo-600 hover:bg-white rounded-xl border border-slate-200 transition text-sm flex items-center gap-1.5 font-medium shadow-2xs"
                    title="View Public Verification"
                  >
                    <ExternalLink className="w-4 h-4" />
                    Verify
                  </a>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
export default StudentCertificatesPage;
