import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Eye, EyeOff, AlertCircle, Clock, ShieldCheck } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
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
      // Safe, informative error categorization
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
    <div className="w-full min-h-[calc(100vh-8rem)] flex items-center justify-center px-4 sm:px-6 lg:px-8 py-12">
      <div className="w-full max-w-md space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-3">
          <div className="flex justify-center">
            <ExamIIOLogo size="lg" />
          </div>
          <p className="text-xs sm:text-sm text-navy-600 font-medium">
            Sign in to your institutional examination account
          </p>
        </div>

        {/* Login Card */}
        <Card variant="warm" className="p-8 space-y-6">
          {isInactiveLogout && (
            <div
              role="alert"
              className="p-3.5 rounded-xl bg-brand-50 border border-brand-200 text-brand-900 text-xs flex items-center gap-2.5 font-medium"
            >
              <Clock className="w-4 h-4 text-brand-600 shrink-0" />
              <span>Session expired due to inactivity. Please sign in again.</span>
            </div>
          )}

          {formError && (
            <div
              role="alert"
              className="p-3.5 rounded-xl bg-coral-50 border border-coral-200 text-coral-800 text-xs flex items-start gap-2.5 shadow-warm-xs"
            >
              <AlertCircle className="w-4 h-4 text-coral-600 shrink-0 mt-0.5" />
              <span className="leading-relaxed font-medium">{formError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate className="space-y-5">
            {/* Identifier: Email or EUID */}
            <div className="space-y-1.5">
              <label
                htmlFor="identifier"
                className="block text-xs font-bold text-navy-900"
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
                className={`block w-full px-3.5 py-2.5 text-sm bg-surface border rounded-xl text-navy-900 placeholder:text-navy-400 focus:outline-hidden focus:ring-2 transition-all ${
                  fieldErrors.identifier
                    ? 'border-coral-300 focus:border-coral-500 focus:ring-coral-500/20'
                    : 'border-warm-200 focus:border-brand-500 focus:ring-brand-500/20'
                }`}
              />
              {fieldErrors.identifier ? (
                <p id="identifier-error" className="text-xs text-coral-600 font-medium">
                  {fieldErrors.identifier}
                </p>
              ) : (
                <p id="identifier-hint" className="text-[11px] text-navy-500">
                  Students may sign in with their institutional email or EUID.
                </p>
              )}
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <label
                htmlFor="password"
                className="block text-xs font-bold text-navy-900"
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
                  className={`block w-full pl-3.5 pr-11 py-2.5 text-sm bg-surface border rounded-xl text-navy-900 placeholder:text-navy-400 focus:outline-hidden focus:ring-2 transition-all ${
                    fieldErrors.password
                      ? 'border-coral-300 focus:border-coral-500 focus:ring-coral-500/20'
                      : 'border-warm-200 focus:border-brand-500 focus:ring-brand-500/20'
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-navy-400 hover:text-navy-700 transition-colors"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {fieldErrors.password && (
                <p id="password-error" className="text-xs text-coral-600 font-medium">
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
                className="w-full py-2.5 text-sm font-semibold justify-center"
              >
                {isLoading ? 'Signing in...' : 'Sign In'}
              </Button>
            </div>
          </form>

          <div className="pt-2 border-t border-warm-200 flex items-center justify-center gap-1.5 text-[11px] text-navy-500">
            <ShieldCheck className="w-3.5 h-3.5 text-brand-600" />
            <span>End-to-end encrypted authentication session</span>
          </div>
        </Card>

        {/* Help note */}
        <p className="text-center text-xs text-navy-500">
          Need assistance? Contact your institution's examination coordinator.
        </p>
      </div>
    </div>
  );
};

export default LoginPage;
