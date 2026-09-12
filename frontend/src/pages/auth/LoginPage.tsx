import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Eye, EyeOff, AlertCircle, Clock } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Button } from '../../components/common/Button';
import { ExamIIOLogo } from '../../components/common/ExamIIOLogo';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const isInactiveLogout = searchParams.get('reason') === 'inactivity' || searchParams.get('expired') === '1';

  const { login, isAuthenticated, user } = useAuth();

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ identifier?: string; password?: string }>({});
  const [isLoading, setIsLoading] = useState(false);

  // If already authenticated, redirect to appropriate role workspace
  useEffect(() => {
    if (isAuthenticated && user) {
      if (user.role === 'ADMIN') {
        navigate('/admin', { replace: true });
      } else if (user.role === 'PROCTOR') {
        navigate('/proctor', { replace: true });
      } else {
        navigate('/student', { replace: true });
      }
    }
  }, [isAuthenticated, user, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Client-side application validation
    const errors: { identifier?: string; password?: string } = {};
    const cleanId = identifier.trim();

    if (!cleanId) {
      errors.identifier = 'Email address or EUID is required.';
    } else if (cleanId.toUpperCase().startsWith('EUAD-') || cleanId.toUpperCase().startsWith('CG-ADM-')) {
      errors.identifier = 'Admin ID is an identity display property, not a login credential. Please sign in with your email address.';
    }

    if (!password) {
      errors.password = 'Password is required.';
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      setFormError(null);
      return;
    }

    setFieldErrors({});
    setFormError(null);
    setIsLoading(true);

    try {
      const loggedInUser = await login({ identifier: cleanId, password });
      // Authoritative backend role redirect
      if (loggedInUser.role === 'ADMIN') {
        navigate('/admin', { replace: true });
      } else if (loggedInUser.role === 'PROCTOR') {
        navigate('/proctor', { replace: true });
      } else {
        navigate('/student', { replace: true });
      }
    } catch (err: any) {
      // Safe, informative error categorization matching Part 10 specifications
      const statusCode = err.status_code || err.response?.status;
      const errorCode = err.error?.code || '';
      const errorMessage = (err.error?.message || '').toLowerCase();

      if (errorCode === 'ACCOUNT_DISABLED' || errorCode === 'USER_INACTIVE') {
        setFormError('Your account is inactive. Contact your administrator.');
      } else if (errorCode === 'PASSWORD_CHANGE_REQUIRED') {
        setFormError('Password change required before continuing.');
      } else if (
        errorCode === 'CSRF_FAILED' ||
        (statusCode === 403 && errorMessage.includes('csrf'))
      ) {
        setFormError('Your session security token expired. Please refresh and try again.');
      } else if (statusCode === 429 || errorCode === 'THROTTLED') {
        setFormError('Too many login attempts. Please wait a moment and try again.');
      } else if (
        statusCode === 401 ||
        statusCode === 400 ||
        errorCode === 'INVALID_CREDENTIALS'
      ) {
        setFormError('Invalid email/EUID or password.');
      } else if (
        errorCode === 'NETWORK_ERROR' ||
        !statusCode ||
        statusCode >= 500
      ) {
        setFormError('Unable to reach the server. Please try again.');
      } else {
        setFormError(err.error?.message || 'Invalid email/EUID or password.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-8rem)] flex items-center justify-center px-4 sm:px-6 lg:px-8 py-12">
      <div className="w-full max-w-md space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-3">
          <div className="flex justify-center">
            <ExamIIOLogo size="lg" />
          </div>
          <p className="text-sm text-slate-600 font-medium">
            Sign in to your institutional account
          </p>
        </div>

        {/* Login Card */}
        <div className="p-8 space-y-6 bg-[#FAF9F6] border border-[#DDD8CE] shadow-sm rounded-2xl">
          {isInactiveLogout && (
            <div
              role="alert"
              className="p-3.5 rounded-lg bg-[#EAF2FC] border border-[#D9DDE3] text-[#243247] text-xs flex items-center gap-2.5 font-medium"
            >
              <Clock className="w-4 h-4 text-[#2878D8] shrink-0" />
              <span>Session expired due to inactivity. Please sign in again.</span>
            </div>
          )}

          {formError && (
            <div
              role="alert"
              className="p-3.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2.5"
            >
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span className="leading-relaxed font-medium">{formError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate className="space-y-5">
            {/* Identifier: Email or EUID */}
            <div className="space-y-1.5">
              <label
                htmlFor="identifier"
                className="block text-xs font-semibold text-[#243247]"
              >
                Email address or EUID
              </label>
              <input
                id="identifier"
                name="identifier"
                type="text"
                autoComplete="username"
                value={identifier}
                onChange={(e) => {
                  setIdentifier(e.target.value);
                  if (fieldErrors.identifier) {
                    setFieldErrors((prev) => ({ ...prev, identifier: undefined }));
                  }
                }}
                placeholder="name@institution.edu or EUID"
                aria-invalid={!!fieldErrors.identifier}
                aria-describedby={fieldErrors.identifier ? 'identifier-error' : 'identifier-hint'}
                className={`block w-full px-3.5 py-2.5 text-sm bg-white border rounded-lg text-[#243247] placeholder:text-[#5E6B7D] focus:outline-none focus:ring-2 transition-colors ${
                  fieldErrors.identifier
                    ? 'border-rose-300 focus:border-rose-500 focus:ring-rose-500/20'
                    : 'border-[#D9DDE3] focus:border-[#2878D8] focus:ring-[#2878D8]/20'
                }`}
              />
              {fieldErrors.identifier ? (
                <p id="identifier-error" className="text-xs text-rose-600 font-medium">
                  {fieldErrors.identifier}
                </p>
              ) : (
                <p id="identifier-hint" className="text-[11px] text-[#5E6B7D]">
                  Students may sign in with their institutional email or EUID.
                </p>
              )}
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <label
                htmlFor="password"
                className="block text-xs font-semibold text-[#243247]"
              >
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (fieldErrors.password) {
                      setFieldErrors((prev) => ({ ...prev, password: undefined }));
                    }
                  }}
                  placeholder="Enter your password"
                  aria-invalid={!!fieldErrors.password}
                  aria-describedby={fieldErrors.password ? 'password-error' : undefined}
                  className={`block w-full pl-3.5 pr-11 py-2.5 text-sm bg-white border rounded-lg text-[#243247] placeholder:text-[#5E6B7D] focus:outline-none focus:ring-2 transition-colors ${
                    fieldErrors.password
                      ? 'border-rose-300 focus:border-rose-500 focus:ring-rose-500/20'
                      : 'border-[#D9DDE3] focus:border-[#2878D8] focus:ring-[#2878D8]/20'
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-[#5E6B7D] hover:text-[#243247] transition-colors"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {fieldErrors.password && (
                <p id="password-error" className="text-xs text-rose-600 font-medium">
                  {fieldErrors.password}
                </p>
              )}
            </div>

            {/* Submit Button */}
            <div className="pt-2">
              <Button
                type="submit"
                variant="primary"
                size="md"
                disabled={isLoading}
                isLoading={isLoading}
                className="w-full py-2.5 text-sm font-semibold justify-center bg-[#2878D8] hover:bg-[#2065B8] active:bg-[#18539C] text-white shadow-sm focus:ring-[#2878D8]"
              >
                {isLoading ? 'Signing in...' : 'Sign In'}
              </Button>
            </div>
          </form>
        </div>

        {/* Help note */}
        <p className="text-center text-xs text-[#5E6B7D]">
          Need help? Contact your institution's examination coordinator.
        </p>
      </div>
    </div>
  );
};

export default LoginPage;
