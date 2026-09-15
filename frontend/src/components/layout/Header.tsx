import React, { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Menu,
  LogOut,
  User,
  Shield,
  ShieldCheck,
  ChevronDown,
  Award,
  Bell,
  Search,
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Badge } from '../common/Badge';
import { StatusIndicator } from '../common/StatusIndicator';
import { ExamIIOLogo } from '../common/ExamIIOLogo';

export interface HeaderProps {
  onOpenMobileSidebar: () => void;
  isSidebarCollapsed?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ onOpenMobileSidebar }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const handleLogout = async () => {
    setAccountMenuOpen(false);
    await logout();
    navigate('/login');
  };

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setAccountMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getRoleBadge = () => {
    if (user?.role === 'ADMIN') {
      return (
        <Badge variant="violet" size="sm" dot>
          Admin
        </Badge>
      );
    }
    if (user?.role === 'PROCTOR') {
      return (
        <Badge variant="amber" size="sm" dot>
          Proctor
        </Badge>
      );
    }
    return (
      <Badge variant="blue" size="sm" dot>
        Candidate
      </Badge>
    );
  };

  const displayName =
    user?.display_name ||
    user?.first_name ||
    (user?.role === 'ADMIN' ? 'Administrator' : user?.email ? user.email.split('@')[0] : 'User');

  const initials = displayName
    .split(' ')
    .map((n) => n[0])
    .join('')
    .substring(0, 2)
    .toUpperCase();

  const profilePath = user?.role === 'ADMIN' ? '/admin/profile' : '/student/profile';

  return (
    <header className="sticky top-0 z-20 h-16 bg-surface/95 backdrop-blur-md border-b border-warm-200 shadow-warm-xs">
      <div className="h-full px-4 sm:px-6 lg:px-8 flex items-center justify-between gap-4">
        {/* Left: Mobile Drawer Toggle + Logo */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onOpenMobileSidebar}
            className="lg:hidden p-2 rounded-xl text-navy-600 hover:text-navy-900 hover:bg-warm-100 transition-colors"
            aria-label="Open navigation menu"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div className="lg:hidden">
            <ExamIIOLogo variant="full" size="sm" />
          </div>

          <div className="hidden lg:flex items-center gap-3">
            {getRoleBadge()}
            <StatusIndicator
              status="online"
              size="sm"
              label="System Operational"
              className="text-[11px] text-navy-500 font-medium"
            />
          </div>
        </div>

        {/* Center: Subtle Quick Context or Search info */}
        <div className="hidden md:flex items-center flex-1 max-w-xs mx-4">
          <div className="w-full relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-navy-400" />
            <input
              type="text"
              readOnly
              placeholder="ExamIIO Enterprise Examination"
              className="w-full pl-8 pr-3 py-1.5 rounded-xl text-xs bg-canvas-subtle/70 border border-warm-200 text-navy-600 placeholder:text-navy-400 cursor-default select-none focus:outline-hidden"
            />
          </div>
        </div>

        {/* Right: Notifications & User Profile Menu */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Notifications Placeholder / Icon */}
          <div className="relative">
            <button
              type="button"
              className="p-2 rounded-xl text-navy-500 hover:text-navy-900 hover:bg-warm-100 transition-colors relative"
              aria-label="Notifications"
              title="Notifications"
            >
              <Bell className="w-4 h-4" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-brand-500 ring-2 ring-surface" />
            </button>
          </div>

          {/* User Profile Dropdown */}
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setAccountMenuOpen(!accountMenuOpen)}
              className="flex items-center gap-2 p-1.5 rounded-xl hover:bg-warm-100 transition-colors text-left group"
              aria-expanded={accountMenuOpen}
              aria-haspopup="true"
            >
              <div className="w-8 h-8 rounded-lg bg-brand-50 border border-brand-200 flex items-center justify-center text-brand-700 font-bold text-xs font-mono shadow-warm-xs group-hover:scale-105 transition-transform">
                {initials || 'U'}
              </div>
              <div className="hidden sm:block text-left">
                <div className="text-xs font-bold text-navy-900 leading-tight truncate max-w-[140px]">
                  {displayName}
                </div>
                <div className="text-[10px] text-navy-500 font-medium">
                  {user?.role === 'ADMIN' ? 'Administrator' : user?.role === 'PROCTOR' ? 'Proctor' : 'Candidate'}
                </div>
              </div>
              <ChevronDown className={`w-3.5 h-3.5 text-navy-400 transition-transform duration-150 ${accountMenuOpen ? 'rotate-180' : ''}`} />
            </button>

            {/* Dropdown Card */}
            {accountMenuOpen && (
              <div className="absolute right-0 mt-2 w-64 rounded-2xl bg-surface border border-warm-200 shadow-warm-lg py-2 z-50 divide-y divide-warm-100 animate-scale-in">
                {/* User Info Header */}
                <div className="px-4 py-3">
                  <div className="text-xs font-bold text-navy-900 truncate">{displayName}</div>
                  <div className="text-[11px] text-navy-500 font-mono truncate mt-0.5">{user?.email}</div>
                  {user?.student_profile?.roll_number && (
                    <div className="text-[10px] text-navy-500 font-mono mt-1">
                      Roll: <span className="text-navy-800 font-bold">{user.student_profile.roll_number}</span>
                    </div>
                  )}
                  {user?.student_profile?.euid && (
                    <div className="text-[10px] text-navy-500 font-mono">
                      EUID: <span className="text-navy-800 font-bold">{user.student_profile.euid}</span>
                    </div>
                  )}
                </div>

                {/* Role Actions */}
                <div className="py-1">
                  <Link
                    to={profilePath}
                    onClick={() => setAccountMenuOpen(false)}
                    className="flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-navy-700 hover:bg-warm-100 hover:text-navy-950 transition-colors"
                  >
                    <User className="w-4 h-4 text-navy-400" />
                    <span>My Profile</span>
                  </Link>

                  {user?.role === 'ADMIN' && (
                    <Link
                      to="/admin/administrators"
                      onClick={() => setAccountMenuOpen(false)}
                      className="flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-navy-700 hover:bg-warm-100 hover:text-navy-950 transition-colors"
                    >
                      <ShieldCheck className="w-4 h-4 text-violet-500" />
                      <span>Administrators</span>
                    </Link>
                  )}

                  {user?.role === 'STUDENT' && (
                    <>
                      <Link
                        to="/student/certificates"
                        onClick={() => setAccountMenuOpen(false)}
                        className="flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-navy-700 hover:bg-warm-100 hover:text-navy-950 transition-colors"
                      >
                        <Award className="w-4 h-4 text-amber-500" />
                        <span>My Certificates</span>
                      </Link>
                      <Link
                        to="/student/privacy"
                        onClick={() => setAccountMenuOpen(false)}
                        className="flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-navy-700 hover:bg-warm-100 hover:text-navy-950 transition-colors"
                      >
                        <Shield className="w-4 h-4 text-blue-500" />
                        <span>Privacy &amp; Policy</span>
                      </Link>
                    </>
                  )}
                </div>

                {/* Sign Out */}
                <div className="py-1">
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2.5 px-4 py-2 text-xs font-semibold text-coral-600 hover:bg-coral-50 transition-colors"
                  >
                    <LogOut className="w-4 h-4" />
                    <span>Sign Out</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
