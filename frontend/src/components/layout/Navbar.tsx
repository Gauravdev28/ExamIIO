import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { 
  LogOut, 
  LogIn, 
  LayoutDashboard, 
  Users, 
  BookOpen, 
  Database, 
  Eye, 
  FileCode,
  ShieldCheck,
  BarChart3,
  ChevronDown,
  Award,
  Shield
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Button } from '../common/Button';
import { getDashboardPath } from '../common/ProtectedRoute';
import { ExamIIOLogo } from '../common/ExamIIOLogo';

export const Navbar: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const dashboardPath = getDashboardPath(user?.role);

  return (
    <header className="sticky top-0 z-50 bg-[#F4F1EA]/95 backdrop-blur-md border-b border-[#DDD8CE] shadow-xs">
      <div className="w-full px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo */}
          <Link
            to={isAuthenticated ? dashboardPath : '/'}
            className="flex items-center group py-1"
            aria-label="ExamIIO Home"
          >
            <ExamIIOLogo variant="full" size="md" />
          </Link>

          {/* Navigation Links */}
          <nav className="flex items-center gap-1 sm:gap-2">
            {/* Public Links */}
            {!isAuthenticated && (
              <>
                <Link
                  to="/"
                  className={`text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname === '/' ? 'text-[#2878D8] bg-[#EEF5FC] font-semibold border border-[#D9DDE3]' : 'text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80'
                  }`}
                >
                  Home
                </Link>
                <Link
                  to="/about"
                  className={`text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname === '/about' ? 'text-[#2878D8] bg-[#EEF5FC] font-semibold border border-[#D9DDE3]' : 'text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80'
                  }`}
                >
                  About
                </Link>
                <Link
                  to="/features"
                  className={`text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname === '/features' ? 'text-[#2878D8] bg-[#EEF5FC] font-semibold border border-[#D9DDE3]' : 'text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80'
                  }`}
                >
                  Features
                </Link>
                <Link
                  to="/security"
                  className={`text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname === '/security' ? 'text-[#2878D8] bg-[#EEF5FC] font-semibold border border-[#D9DDE3]' : 'text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80'
                  }`}
                >
                  Security
                </Link>
              </>
            )}

            {/* Clean Admin Navigation */}
            {isAuthenticated && user?.role === 'ADMIN' && (
              <>
                <Link
                  to="/admin"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname === '/admin' || location.pathname === '/admin/dashboard'
                      ? 'text-[#2878D8] bg-[#EEF5FC] font-semibold border border-[#D9DDE3]'
                      : 'text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80'
                  }`}
                >
                  <LayoutDashboard className="w-3.5 h-3.5 text-[#2878D8]" />
                  <span className="hidden md:inline">Dashboard</span>
                </Link>

                <Link
                  to="/admin/assessments"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/admin/assessments')
                      ? 'text-[#2878D8] bg-[#EEF5FC] font-semibold border border-[#D9DDE3]'
                      : 'text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80'
                  }`}
                >
                  <FileCode className="w-3.5 h-3.5 text-[#2878D8]" />
                  <span className="hidden md:inline">Assessments</span>
                </Link>

                <Link
                  to="/admin/questions"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/admin/questions')
                      ? 'text-[#2878D8] bg-[#EEF5FC] font-semibold border border-[#D9DDE3]'
                      : 'text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80'
                  }`}
                >
                  <BookOpen className="w-3.5 h-3.5 text-amber-600" />
                  <span className="hidden md:inline">Questions</span>
                </Link>

                <Link
                  to="/admin/students"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/admin/students')
                      ? 'text-[#2878D8] bg-[#EEF5FC] font-semibold border border-[#D9DDE3]'
                      : 'text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80'
                  }`}
                >
                  <Users className="w-3.5 h-3.5 text-[#2878D8]" />
                  <span className="hidden md:inline">Students</span>
                </Link>

                <Link
                  to="/admin/administrators"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/admin/administrators')
                      ? 'text-[#2878D8] bg-[#EEF5FC] font-semibold border border-[#D9DDE3]'
                      : 'text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80'
                  }`}
                >
                  <ShieldCheck className="w-3.5 h-3.5 text-purple-600" />
                  <span className="hidden md:inline">Administrators</span>
                </Link>

                <Link
                  to="/admin/results"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/admin/results')
                      ? 'text-[#2878D8] bg-[#EEF5FC] font-semibold border border-[#D9DDE3]'
                      : 'text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80'
                  }`}
                >
                  <BarChart3 className="w-3.5 h-3.5 text-[#2FA878]" />
                  <span className="hidden md:inline">Results</span>
                </Link>

                <Link
                  to="/admin/certificates"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/admin/certificates')
                      ? 'text-[#2878D8] bg-[#EEF5FC] font-semibold border border-[#D9DDE3]'
                      : 'text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80'
                  }`}
                >
                  <Award className="w-3.5 h-3.5 text-amber-600" />
                  <span className="hidden md:inline">Certificates</span>
                </Link>

                <Link
                  to="/admin/retention"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/admin/retention')
                      ? 'text-[#2878D8] bg-[#EEF5FC] font-semibold border border-[#D9DDE3]'
                      : 'text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80'
                  }`}
                >
                  <Database className="w-3.5 h-3.5 text-slate-500" />
                  <span className="hidden lg:inline">Retention</span>
                </Link>
              </>
            )}

            {/* Proctor Links */}
            {isAuthenticated && user?.role === 'PROCTOR' && (
              <Link
                to="/proctor"
                className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                  location.pathname === '/proctor' || location.pathname === '/proctor/dashboard'
                    ? 'text-[#2878D8] bg-[#EEF5FC] font-semibold border border-[#D9DDE3]'
                    : 'text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80'
                }`}
              >
                <Eye className="w-4 h-4 text-amber-600" />
                <span className="hidden md:inline">Live Assessments</span>
              </Link>
            )}

            {/* Student Links */}
            {isAuthenticated && user?.role === 'STUDENT' && (
              <>
                <Link
                  to="/student"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname === '/student' || location.pathname === '/student/dashboard'
                      ? 'text-[#2878D8] bg-[#EEF5FC] font-semibold border border-[#D9DDE3]'
                      : 'text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80'
                  }`}
                >
                  <LayoutDashboard className="w-4 h-4 text-[#2878D8]" />
                  <span className="hidden md:inline">Dashboard</span>
                </Link>
                <Link
                  to="/student/assessments"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/student/assessments')
                      ? 'text-[#2878D8] bg-[#EEF5FC] font-semibold border border-[#D9DDE3]'
                      : 'text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80'
                  }`}
                >
                  <FileCode className="w-4 h-4 text-[#2878D8]" />
                  <span className="hidden md:inline">My Exams</span>
                </Link>
                <Link
                  to="/student/certificates"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/student/certificates')
                      ? 'text-[#2878D8] bg-[#EEF5FC] font-semibold border border-[#D9DDE3]'
                      : 'text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80'
                  }`}
                >
                  <Award className="w-4 h-4 text-amber-600" />
                  <span className="hidden md:inline">My Certificates</span>
                </Link>
                <Link
                  to="/student/privacy"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/student/privacy')
                      ? 'text-[#2878D8] bg-[#EEF5FC] font-semibold border border-[#D9DDE3]'
                      : 'text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80'
                  }`}
                >
                  <Shield className="w-4 h-4 text-[#2878D8]" />
                  <span className="hidden md:inline">Privacy</span>
                </Link>
              </>
            )}

            {/* Auth / Account Controls */}
            {isAuthenticated && user ? (
              <div className="relative ml-2 pl-2 border-l border-[#DDD8CE]">
                <button
                  onClick={() => setAccountMenuOpen(!accountMenuOpen)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg hover:bg-[#EDE9E1]/80 transition-colors text-left"
                >
                  <span className="text-xs font-bold text-[#243247] leading-tight whitespace-nowrap truncate max-w-[160px] sm:max-w-none">
                    {user.display_name || user.first_name || (user.role === 'ADMIN' ? 'Administrator' : user.email.split('@')[0])}
                  </span>
                  <ChevronDown className="w-3.5 h-3.5 text-[#5E6B7D] shrink-0" />
                </button>

                {/* Account Dropdown Menu */}
                {accountMenuOpen && (
                  <div className="absolute right-0 mt-2 w-56 bg-[#FAF9F6] rounded-xl shadow-lg border border-[#DDD8CE] py-1.5 z-50 divide-y divide-[#DDD8CE]">
                    <div className="px-3.5 py-2.5">
                      <div className="text-xs font-bold text-[#243247]">
                        {user.display_name || user.first_name || (user.role === 'ADMIN' ? 'Administrator' : 'User')}
                      </div>
                      <div className="text-[11px] text-[#5E6B7D] font-medium mt-0.5">
                        {user.email}
                      </div>
                    </div>

                    {user.role === 'ADMIN' && (
                      <div className="py-1">
                        <Link
                          to="/admin/administrators"
                          onClick={() => setAccountMenuOpen(false)}
                          className="flex items-center gap-2 px-3.5 py-2 text-xs text-[#243247] hover:bg-[#EDE9E1] hover:text-[#2878D8] font-medium"
                        >
                          <ShieldCheck className="w-4 h-4 text-purple-600" />
                          <span>Administrators</span>
                        </Link>
                      </div>
                    )}

                    <div className="py-1">
                      <button
                        onClick={() => {
                          setAccountMenuOpen(false);
                          handleLogout();
                        }}
                        className="w-full flex items-center gap-2 px-3.5 py-2 text-xs text-rose-600 hover:bg-rose-50 font-medium"
                      >
                        <LogOut className="w-4 h-4" />
                        <span>Sign Out</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <Link to="/login">
                <Button variant="primary" size="sm" className="flex items-center gap-1.5">
                  <LogIn className="w-3.5 h-3.5" />
                  <span>Sign In</span>
                </Button>
              </Link>
            )}
          </nav>
        </div>
      </div>
    </header>
  );
};

export default Navbar;
