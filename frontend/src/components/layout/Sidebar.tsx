import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  FileCode,
  BookOpen,
  Users,
  BarChart3,
  Award,
  ShieldCheck,
  Database,
  User,
  Shield,
  Eye,
  ChevronLeft,
  ChevronRight,
  X,
  Sparkles,
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { ExamIIOLogo } from '../common/ExamIIOLogo';

export interface SidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  isMobileOpen: boolean;
  onCloseMobile: () => void;
}

interface NavItemConfig {
  label: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  exact?: boolean;
  badge?: string | number;
}

interface NavGroupConfig {
  title?: string;
  items: NavItemConfig[];
}

export const Sidebar: React.FC<SidebarProps> = ({
  isCollapsed,
  onToggleCollapse,
  isMobileOpen,
  onCloseMobile,
}) => {
  const { user } = useAuth();
  const location = useLocation();

  const getNavGroups = (): NavGroupConfig[] => {
    if (user?.role === 'ADMIN') {
      return [
        {
          title: 'Management',
          items: [
            { label: 'Dashboard', path: '/admin', icon: LayoutDashboard, exact: true },
            { label: 'Assessments', path: '/admin/assessments', icon: FileCode },
            { label: 'Question Bank', path: '/admin/questions', icon: BookOpen },
            { label: 'Students', path: '/admin/students', icon: Users },
          ],
        },
        {
          title: 'Evaluation',
          items: [
            { label: 'Results', path: '/admin/results', icon: BarChart3 },
            { label: 'Certificates', path: '/admin/certificates', icon: Award },
          ],
        },
        {
          title: 'System',
          items: [
            { label: 'Administrators', path: '/admin/administrators', icon: ShieldCheck },
            { label: 'Data Retention', path: '/admin/retention', icon: Database },
            { label: 'My Profile', path: '/admin/profile', icon: User },
          ],
        },
      ];
    }

    if (user?.role === 'STUDENT') {
      return [
        {
          title: 'Examination',
          items: [
            { label: 'Dashboard', path: '/student', icon: LayoutDashboard, exact: true },
            { label: 'My Assessments', path: '/student/assessments', icon: FileCode },
            { label: 'Certificates', path: '/student/certificates', icon: Award },
          ],
        },
        {
          title: 'Account',
          items: [
            { label: 'My Profile', path: '/student/profile', icon: User },
            { label: 'Privacy & Rights', path: '/student/privacy', icon: Shield },
          ],
        },
      ];
    }

    if (user?.role === 'PROCTOR') {
      return [
        {
          title: 'Invigilation',
          items: [
            { label: 'Live Assessments', path: '/proctor', icon: Eye, exact: true },
          ],
        },
        {
          title: 'Account',
          items: [
            { label: 'My Profile', path: '/admin/profile', icon: User },
          ],
        },
      ];
    }

    return [];
  };

  const navGroups = getNavGroups();

  const isItemActive = (item: NavItemConfig) => {
    if (item.exact) {
      return location.pathname === item.path || location.pathname === `${item.path}/dashboard`;
    }
    return location.pathname.startsWith(item.path);
  };

  const content = (
    <div className="h-full flex flex-col justify-between bg-surface border-r border-warm-200 shadow-warm-xs">
      {/* Top Header / Branding */}
      <div>
        <div className={`h-16 flex items-center border-b border-warm-200 px-4 ${isCollapsed ? 'justify-center' : 'justify-between'}`}>
          <NavLink
            to={user?.role === 'ADMIN' ? '/admin' : user?.role === 'STUDENT' ? '/student' : '/proctor'}
            className="flex items-center gap-2 group focus:outline-hidden focus-visible:ring-2 focus-visible:ring-brand-500 rounded-lg p-1"
            onClick={() => isMobileOpen && onCloseMobile()}
          >
            {isCollapsed ? (
              <ExamIIOLogo variant="icon" size="sm" />
            ) : (
              <ExamIIOLogo variant="full" size="sm" />
            )}
          </NavLink>

          {/* Close button for mobile */}
          <button
            type="button"
            onClick={onCloseMobile}
            className="lg:hidden p-1.5 rounded-lg text-navy-400 hover:text-navy-700 hover:bg-warm-100 transition-colors"
            aria-label="Close navigation sidebar"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation Groups */}
        <nav className="p-3 space-y-6 overflow-y-auto max-h-[calc(100vh-140px)]" aria-label="Sidebar navigation">
          {navGroups.map((group, gIdx) => (
            <div key={gIdx} className="space-y-1.5">
              {!isCollapsed && group.title && (
                <div className="px-3 text-[10px] font-bold font-mono uppercase tracking-wider text-navy-400">
                  {group.title}
                </div>
              )}
              <div className="space-y-1">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active = isItemActive(item);

                  return (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      onClick={() => isMobileOpen && onCloseMobile()}
                      title={isCollapsed ? item.label : undefined}
                      className={`group relative flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all duration-150 ${
                        active
                          ? 'bg-brand-50 text-brand-700 font-bold shadow-warm-xs border border-brand-200/80'
                          : 'text-navy-600 hover:text-navy-900 hover:bg-warm-100/80'
                      } ${isCollapsed ? 'justify-center px-2' : ''}`}
                    >
                      <Icon
                        className={`w-4 h-4 shrink-0 transition-transform duration-150 group-hover:scale-110 ${
                          active ? 'text-brand-600' : 'text-navy-400 group-hover:text-navy-700'
                        }`}
                      />
                      {!isCollapsed && (
                        <span className="truncate flex-1">{item.label}</span>
                      )}
                      {!isCollapsed && item.badge && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full font-mono bg-brand-100 text-brand-700 font-bold">
                          {item.badge}
                        </span>
                      )}

                      {/* Tooltip on collapsed desktop view */}
                      {isCollapsed && (
                        <span className="absolute left-full ml-2 px-2.5 py-1 bg-navy-900 text-warm-50 text-[11px] font-medium rounded-md shadow-warm-md whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity z-50">
                          {item.label}
                        </span>
                      )}
                    </NavLink>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </div>

      {/* Bottom Footer Section */}
      <div className="p-3 border-t border-warm-200 bg-surface-warm/60">
        {!isCollapsed ? (
          <div className="flex items-center justify-between gap-2 px-2 py-1.5">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-7 h-7 rounded-lg bg-brand-50 border border-brand-200 flex items-center justify-center text-brand-600 shrink-0">
                <Sparkles className="w-3.5 h-3.5" />
              </div>
              <div className="truncate">
                <div className="text-[11px] font-bold text-navy-900 truncate">ExamIIO Platform</div>
                <div className="text-[10px] text-navy-500 truncate">Secure Evaluation</div>
              </div>
            </div>

            <button
              type="button"
              onClick={onToggleCollapse}
              className="hidden lg:flex p-1.5 rounded-lg text-navy-400 hover:text-navy-700 hover:bg-warm-100 transition-colors"
              aria-label="Collapse sidebar"
              title="Collapse sidebar"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="hidden lg:flex justify-center">
            <button
              type="button"
              onClick={onToggleCollapse}
              className="p-2 rounded-lg text-navy-400 hover:text-navy-700 hover:bg-warm-100 transition-colors"
              aria-label="Expand sidebar"
              title="Expand sidebar"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <aside
        className={`hidden lg:block shrink-0 transition-all duration-200 ease-in-out z-30 ${
          isCollapsed ? 'w-[72px]' : 'w-60'
        }`}
      >
        <div className={`fixed top-0 bottom-0 left-0 transition-all duration-200 ease-in-out ${
          isCollapsed ? 'w-[72px]' : 'w-60'
        }`}>
          {content}
        </div>
      </aside>

      {/* Mobile Drawer Backdrop */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 bg-navy-950/40 backdrop-blur-xs z-40 lg:hidden transition-opacity"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}

      {/* Mobile Drawer */}
      <aside
        className={`fixed inset-y-0 left-0 w-72 max-w-[85vw] z-50 lg:hidden transform transition-transform duration-250 ease-out shadow-warm-xl ${
          isMobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        aria-label="Mobile Navigation"
      >
        {content}
      </aside>
    </>
  );
};

export default Sidebar;
