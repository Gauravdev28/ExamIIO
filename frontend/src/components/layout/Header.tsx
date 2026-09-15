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
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Badge } from '../common/Badge';
import { ExamIIOLogo } from '../common/ExamIIOLogo';
import { NotificationPanel } from '../notifications/NotificationPanel';
import { AdminSendNotificationModal } from '../notifications/AdminSendNotificationModal';
import { NotificationsAPI } from '../../api/notifications';

export interface HeaderProps {
  onOpenMobileSidebar: () => void;
  isSidebarCollapsed?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ onOpenMobileSidebar }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  // Menus state
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [adminSendOpen, setAdminSendOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  const menuRef = useRef<HTMLDivElement>(null);

  // Load unread count on mount and polling interval (e.g. 60s)
  useEffect(() => {
    let isMounted = true;
    const fetchUnread = async () => {
      try {
        const count = await NotificationsAPI.getUnreadCount();
        if (isMounted && typeof count === 'number') {
          setUnreadCount(count);
        }
      } catch {
        // ignore
      }
    };

    fetchUnread();
    const interval = setInterval(fetchUnread, 60000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

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

  // Close menus on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setAccountMenuOpen(false);
        setNotificationOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
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
    <header className="sticky top-0 z-30 h-16 bg-[#FFFDF8] border-b border-warm-200 shadow-warm-xs">
      <div className="h-full px-4 sm:px-6 lg:px-8 flex items-center justify-between gap-4">
        {/* Left: Mobile Drawer Toggle + Logo + Role Context */}
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

          <div className="hidden lg:flex items-center gap-2.5">
            {getRoleBadge()}
          </div>
        </div>

        {/* Right: Notifications & User Profile Menu */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Real Notification Control */}
          <div className="relative">
            <button
              type="button"
              onClick={() => {
                setNotificationOpen(!notificationOpen);
                setAccountMenuOpen(false);
              }}
              className={`p-2 rounded-xl transition-colors relative ${
                notificationOpen
                  ? 'bg-warm-200/80 text-navy-900'
                  : 'text-navy-500 hover:text-navy-900 hover:bg-warm-100'
              }`}
              aria-label="Notifications"
              aria-expanded={notificationOpen}
              aria-haspopup="dialog"
              title="Notifications"
            >
              <Bell className="w-4 h-4" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 min-w-4 h-4 px-1 rounded-full bg-brand-600 text-white text-[10px] font-mono font-bold flex items-center justify-center ring-2 ring-surface">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </button>

            {/* Opaque Notification Panel */}
            <NotificationPanel
              isOpen={notificationOpen}
              onClose={() => setNotificationOpen(false)}
              isAdmin={user?.role === 'ADMIN'}
              onOpenAdminSend={() => setAdminSendOpen(true)}
              unreadCount={unreadCount}
              onUnreadCountChange={setUnreadCount}
            />
          </div>

          {/* User Profile Dropdown */}
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => {
                setAccountMenuOpen(!accountMenuOpen);
                setNotificationOpen(false);
              }}
              className={`flex items-center gap-2 p-1.5 rounded-xl transition-colors text-left group ${
                accountMenuOpen ? 'bg-warm-200/80' : 'hover:bg-warm-100'
              }`}
              aria-expanded={accountMenuOpen}
              aria-haspopup="true"
              aria-label="User account menu"
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

            {/* Fully Opaque Solid Dropdown Card */}
            {accountMenuOpen && (
              <div
                className="absolute right-0 top-full mt-2 w-64 sm:w-72 rounded-2xl bg-[#FFFDF8] border border-warm-200 shadow-warm-xl py-2 z-50 divide-y divide-warm-100 animate-scale-in text-navy-900"
                role="menu"
                aria-label="Account options"
              >
                {/* User Info Header */}
                <div className="px-4 py-3 bg-[#FCFAF4] rounded-t-xl">
                  <div className="text-xs font-bold text-navy-900 truncate">{displayName}</div>
                  <div className="text-[11px] text-navy-500 font-mono truncate mt-0.5">{user?.email}</div>
                  {user?.student_profile?.roll_number && (
                    <div className="text-[10px] text-navy-600 font-mono mt-1">
                      Roll: <span className="text-navy-900 font-bold">{user.student_profile.roll_number}</span>
                    </div>
                  )}
                  {user?.student_profile?.euid && (
                    <div className="text-[10px] text-navy-600 font-mono">
                      EUID: <span className="text-navy-900 font-bold">{user.student_profile.euid}</span>
                    </div>
                  )}
                </div>

                {/* Role Actions */}
                <div className="py-1">
                  <Link
                    to={profilePath}
                    onClick={() => setAccountMenuOpen(false)}
                    className="flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-navy-700 hover:bg-warm-100 hover:text-navy-950 transition-colors"
                    role="menuitem"
                  >
                    <User className="w-4 h-4 text-navy-400" />
                    <span>My Profile</span>
                  </Link>

                  {user?.role === 'ADMIN' && (
                    <Link
                      to="/admin/administrators"
                      onClick={() => setAccountMenuOpen(false)}
                      className="flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-navy-700 hover:bg-warm-100 hover:text-navy-950 transition-colors"
                      role="menuitem"
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
                        role="menuitem"
                      >
                        <Award className="w-4 h-4 text-amber-500" />
                        <span>My Certificates</span>
                      </Link>
                      <Link
                        to="/student/privacy"
                        onClick={() => setAccountMenuOpen(false)}
                        className="flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-navy-700 hover:bg-warm-100 hover:text-navy-950 transition-colors"
                        role="menuitem"
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
                    role="menuitem"
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

      {/* Admin Send Notification Modal */}
      {user?.role === 'ADMIN' && (
        <AdminSendNotificationModal
          isOpen={adminSendOpen}
          onClose={() => setAdminSendOpen(false)}
          onSuccess={() => {
            NotificationsAPI.getUnreadCount()
              .then(setUnreadCount)
              .catch(() => {});
          }}
        />
      )}
    </header>
  );
};

export default Header;
