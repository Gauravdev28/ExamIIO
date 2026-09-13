import React, { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { updateStudentOfficialName } from '../../api/students';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Award, AlertCircle, ShieldCheck } from 'lucide-react';

export const OfficialNameSetupModal: React.FC = () => {
  const { user, refreshUser, logout } = useAuth();
  const [officialName, setOfficialName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Prefill with display_name if it exists and is not a generic placeholder
  useEffect(() => {
    if (
      user?.display_name &&
      !user.display_name.includes('@') &&
      user.display_name !== 'Student' &&
      user.display_name.trim() !== ''
    ) {
      setOfficialName(user.display_name);
    }
  }, [user]);

  // Strict conditional display:
  // 1. Must have an authenticated user
  // 2. Must be STUDENT role (never ADMIN or PROCTOR)
  // 3. Must require official name setup (official_name_required === true)
  // 4. If password change is required (first_login_required === true), allow ForcePasswordChangeModal to resolve first
  if (!user || user.role !== 'STUDENT' || !user.official_name_required || user.first_login_required) {
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const cleanName = officialName.trim();
    if (!cleanName) {
      setErrorMessage('Please enter your official name.');
      return;
    }

    if (cleanName.length < 2) {
      setErrorMessage('Official name must be at least 2 characters in length.');
      return;
    }

    if (cleanName.length > 255) {
      setErrorMessage('Official name cannot exceed 255 characters.');
      return;
    }

    setIsLoading(true);
    try {
      // Send strictly only official_name to the backend endpoint
      await updateStudentOfficialName(cleanName);

      // Server-authoritatively refresh the current user state
      await refreshUser();
    } catch (err: any) {
      const msg =
        err.response?.data?.error?.details?.official_name?.[0] ||
        err.response?.data?.error?.details?.certificate_name?.[0] ||
        err.response?.data?.error?.message ||
        err.response?.data?.message ||
        err.error?.message ||
        err.message ||
        'Failed to save official name. Please check your input and try again.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#243247]/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="official-name-setup-title"
      aria-describedby="official-name-setup-desc"
    >
      <Card className="max-w-md w-full p-8 border border-[#DDD8CE] shadow-2xl space-y-6 bg-[#FAF8F5]">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center justify-center mx-auto shadow-sm">
            <Award className="w-6 h-6" />
          </div>
          <h2 id="official-name-setup-title" className="text-xl font-bold text-[#243247]">
            Complete your profile
          </h2>
          <p id="official-name-setup-desc" className="text-xs text-[#5E6B7D] leading-relaxed">
            Enter your official name. This name will be used on your participation certificate.
          </p>
        </div>

        {/* Validation / Error Feedback */}
        {errorMessage && (
          <div
            role="alert"
            className="p-3.5 rounded-lg bg-rose-50 border border-rose-200 flex items-start gap-2.5 text-rose-800 text-xs shadow-sm"
          >
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <span className="font-medium">{errorMessage}</span>
          </div>
        )}

        {/* Input Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-1.5">
            <label
              htmlFor="official-name-input"
              className="block text-xs font-semibold text-[#243247]"
            >
              Official Name <span className="text-rose-500">*</span>
            </label>
            <input
              id="official-name-input"
              type="text"
              autoFocus
              required
              minLength={2}
              maxLength={255}
              disabled={isLoading}
              value={officialName}
              onChange={(e) => setOfficialName(e.target.value)}
              placeholder="e.g. Rahul Sharma"
              className="w-full px-3.5 py-2.5 rounded-lg bg-white border border-[#DDD8CE] text-[#243247] placeholder:text-[#5E6B7D]/60 text-sm focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600 transition-colors font-medium disabled:opacity-50"
            />
            <div className="flex items-center gap-1.5 pt-1 text-[11px] text-[#5E6B7D]">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
              <span>Please provide your accurate full name as it should appear on official certificates.</span>
            </div>
          </div>

          <div className="pt-2 space-y-2.5">
            <Button
              type="submit"
              variant="primary"
              size="md"
              isLoading={isLoading}
              disabled={isLoading || !officialName.trim()}
              className="w-full justify-center font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm"
            >
              Continue
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={isLoading}
              onClick={logout}
              className="w-full text-[#5E6B7D] hover:text-rose-600 text-xs font-medium"
            >
              Cancel &amp; Sign Out
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};

export default OfficialNameSetupModal;
