import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Award,
  XCircle,
  Calendar,
  Building,
  ShieldCheck,
  ArrowLeft,
  FileCheck,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';
import { Card } from '../../components/common/Card';
import { ResultsAPI } from '../../api/results';
import { PublicCertificateVerification } from '../../types/results';

export const PublicCertificateVerificationPage: React.FC = () => {
  const { certificateId } = useParams<{ certificateId: string }>();
  const [data, setData] = useState<PublicCertificateVerification | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (certificateId) {
      verifyCertificate(certificateId);
    }
  }, [certificateId]);

  const verifyCertificate = async (id: string) => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const res = await ResultsAPI.verifyPublicCertificate(id);
      setData(res);
    } catch (err: any) {
      setErrorMessage(err?.response?.data?.message || 'Unable to connect to verification server. Please check your connection.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F4F1EA] py-12 px-4 sm:px-6 lg:px-8 flex flex-col justify-center items-center">
      <div className="w-full max-w-xl space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-[#FAF9F6] border border-[#DDD8CE] text-[#2878D8] shadow-xs mb-2">
            <Award className="w-8 h-8 text-[#2878D8]" />
          </div>
          <h1 className="text-xl font-bold text-[#243247] tracking-tight">
            ExamIIO Verification Authority
          </h1>
          <p className="text-xs text-[#5E6B7D] uppercase tracking-widest font-semibold">
            Official Certificate Verification Portal
          </p>
        </div>

        {/* Verification Card */}
        {loading ? (
          <Card className="p-10 text-center bg-[#FAF9F6] border-[#DDD8CE] shadow-xs">
            <div className="w-8 h-8 border-3 border-[#2878D8] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm font-medium text-[#5E6B7D]">Verifying certificate credentials...</p>
          </Card>
        ) : errorMessage ? (
          <Card className="p-8 text-center bg-[#FAF9F6] border-[#D9DDE3] shadow-xs">
            <div className="w-12 h-12 rounded-full bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600 mx-auto mb-4">
              <XCircle className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-bold text-[#243247] mb-1">
              Verification Service Error
            </h2>
            <p className="text-sm text-[#5E6B7D] max-w-sm mx-auto mb-6">
              {errorMessage}
            </p>
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={() => certificateId && verifyCertificate(certificateId)}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-[#2878D8] hover:bg-[#2065B8] rounded-lg transition shadow-xs"
              >
                <RefreshCw className="w-4 h-4" />
                Retry
              </button>
              <Link
                to="/login"
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-[#243247] bg-[#EDE9E1] hover:bg-[#DDD8CE] rounded-lg transition border border-[#DDD8CE]"
              >
                <ArrowLeft className="w-4 h-4" />
                Return to Platform
              </Link>
            </div>
          </Card>
        ) : !data || !data.is_valid ? (
          data?.status === 'REVOKED' ? (
            <Card className="p-8 text-center bg-[#FAF9F6] border-[#C98A2E]/40 shadow-xs">
              <div className="w-12 h-12 rounded-full bg-amber-50 border border-[#C98A2E]/30 flex items-center justify-center text-[#C98A2E] mx-auto mb-4">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <span className="text-xs font-bold uppercase tracking-widest text-[#C98A2E] bg-amber-50 px-2.5 py-0.5 rounded-full border border-[#C98A2E]/30">
                Status: Revoked
              </span>
              <h2 className="text-lg font-bold text-[#243247] mt-2 mb-1">
                Certificate Officially Revoked
              </h2>
              <p className="text-sm text-[#5E6B7D] max-w-sm mx-auto mb-4">
                The certificate ID <span className="font-mono font-semibold text-[#243247]">{certificateId}</span> has been revoked by the Examination Authority and is no longer valid.
              </p>
              {data.printed_name && (
                <div className="p-3 bg-[#EDE9E1] border border-[#DDD8CE] rounded-xl text-xs text-[#243247] mb-6 text-left space-y-1">
                  <div><span className="text-[#5E6B7D] font-medium">Original Recipient:</span> {data.printed_name}</div>
                  {data.exam_title && <div><span className="text-[#5E6B7D] font-medium">Exam:</span> {data.exam_title}</div>}
                  {data.issued_at && <div><span className="text-[#5E6B7D] font-medium">Issued on:</span> {new Date(data.issued_at).toLocaleDateString()}</div>}
                </div>
              )}
              <Link
                to="/login"
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-[#243247] bg-[#EDE9E1] hover:bg-[#DDD8CE] rounded-lg transition border border-[#DDD8CE]"
              >
                <ArrowLeft className="w-4 h-4" />
                Return to Platform
              </Link>
            </Card>
          ) : (
            <Card className="p-8 text-center bg-[#FAF9F6] border-[#D9DDE3] shadow-xs">
              <div className="w-12 h-12 rounded-full bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600 mx-auto mb-4">
                <XCircle className="w-6 h-6" />
              </div>
              <span className="text-xs font-bold uppercase tracking-widest text-rose-700 bg-rose-50 px-2.5 py-0.5 rounded-full border border-rose-200">
                Status: Invalid
              </span>
              <h2 className="text-lg font-bold text-[#243247] mt-2 mb-1">
                Invalid or Nonexistent Certificate
              </h2>
              <p className="text-sm text-[#5E6B7D] max-w-sm mx-auto mb-6">
                The certificate ID <span className="font-mono font-semibold text-[#243247]">{certificateId}</span> could not be verified in our authoritative database.
              </p>
              <Link
                to="/login"
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-[#243247] bg-[#EDE9E1] hover:bg-[#DDD8CE] rounded-lg transition border border-[#DDD8CE]"
              >
                <ArrowLeft className="w-4 h-4" />
                Return to Platform
              </Link>
            </Card>
          )
        ) : (
          <Card className="relative overflow-hidden bg-[#FAF9F6] border-[#DDD8CE] shadow-xs rounded-2xl">
            {/* Top Verification Status Banner */}
            <div className="bg-[#E8F5F3] border-b border-[#2FA878]/30 px-6 py-3 text-[#243247] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-[#2FA878]" />
                <span className="text-xs font-bold uppercase tracking-wider text-[#243247]">
                  Verified Official Document
                </span>
              </div>
              <span className="text-xs font-semibold bg-[#2FA878]/10 text-[#2FA878] px-2 py-0.5 rounded border border-[#2FA878]/20">
                Status: Authentic
              </span>
            </div>


            <div className="p-6 sm:p-8 space-y-6">
              {/* Recipient Headline */}
              <div className="text-center pb-4 border-b border-[#DDD8CE]">
                <span className="text-xs font-bold uppercase tracking-widest text-[#2878D8]">
                  Certificate of Participation
                </span>
                <h2 className="text-2xl font-bold text-[#243247] mt-2">
                  {data.printed_name}
                </h2>
                <p className="text-sm text-[#5E6B7D] mt-1">
                  for active participation in the examination
                </p>
                <div className="text-base font-semibold text-[#2878D8] mt-1">
                  {data.exam_title}
                </div>
              </div>

              {/* Credential Data Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div className="p-3.5 bg-[#EDE9E1] rounded-xl border border-[#DDD8CE]">
                  <div className="text-[#5E6B7D] font-medium">Certificate ID</div>
                  <div className="font-mono font-bold text-[#243247] text-sm mt-0.5">
                    {data.certificate_id}
                  </div>
                </div>

                <div className="p-3.5 bg-[#EDE9E1] rounded-xl border border-[#DDD8CE]">
                  <div className="text-[#5E6B7D] font-medium">Issue Date</div>
                  <div className="font-semibold text-[#243247] text-sm mt-0.5 flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-[#5E6B7D]" />
                    {new Date(data.issued_at).toLocaleDateString('en-US', {
                      month: 'long',
                      day: 'numeric',
                      year: 'numeric',
                    })}
                  </div>
                </div>

                <div className="p-3.5 bg-[#EDE9E1] rounded-xl border border-[#DDD8CE] sm:col-span-2">
                  <div className="text-[#5E6B7D] font-medium">Issuing Organization</div>
                  <div className="font-semibold text-[#243247] text-sm mt-0.5 flex items-center gap-1.5">
                    <Building className="w-3.5 h-3.5 text-[#5E6B7D]" />
                    {data.organization_name || 'ExamIIO Authority'}
                  </div>
                </div>
              </div>

              {/* Integrity Notice */}
              <div className="p-3 bg-[#E8F5F3] border border-[#2FA878]/30 rounded-xl text-xs text-[#243247] flex items-start gap-2.5">
                <FileCheck className="w-4 h-4 text-[#2FA878] flex-shrink-0 mt-0.5" />
                <span className="text-[#5E6B7D]">
                  This credential was generated by the ExamIIO automated examination system upon authoritative verification of examination completion.
                </span>
              </div>
            </div>

            {/* Bottom Footer */}
            <div className="px-6 py-4 bg-[#EDE9E1] border-t border-[#DDD8CE] text-center">
              <Link
                to="/login"
                className="text-xs text-[#2878D8] hover:text-[#2065B8] font-medium transition"
              >
                Go to Platform Login &rarr;
              </Link>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
};
export default PublicCertificateVerificationPage;
