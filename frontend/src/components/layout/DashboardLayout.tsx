import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { SessionTimeoutManager } from '../auth/SessionTimeoutManager';
import { ForcePasswordChangeModal } from '../auth/ForcePasswordChangeModal';
import { OfficialNameSetupModal } from '../auth/OfficialNameSetupModal';
import { ErrorBoundary } from '../common/ErrorBoundary';

export const DashboardLayout: React.FC = () => {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('examio_sidebar_collapsed') === 'true';
    } catch {
      return false;
    }
  });

  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  const toggleSidebarCollapse = () => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('examio_sidebar_collapsed', String(next));
      } catch {
        // ignore
      }
      return next;
    });
  };

  return (
    <div className="min-h-screen flex bg-canvas text-navy-900 selection:bg-brand-500/20 selection:text-navy-950">
      {/* Reusable Collapsible Navigation Sidebar */}
      <Sidebar
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={toggleSidebarCollapse}
        isMobileOpen={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 transition-all duration-200">
        {/* Global Authenticated Header */}
        <Header
          onOpenMobileSidebar={() => setIsMobileSidebarOpen(true)}
          isSidebarCollapsed={isSidebarCollapsed}
        />

        {/* Auth Modals & Session Watchers */}
        <SessionTimeoutManager />
        <ForcePasswordChangeModal />
        <OfficialNameSetupModal />

        {/* Dynamic Routed Workspace Content */}
        <main className="flex-1 w-full min-w-0">
          <ErrorBoundary fallbackTitle="Page Load Error">
            <Outlet />
          </ErrorBoundary>
        </main>

        {/* Institutional Minimal Footer */}
        <footer className="border-t border-warm-200 bg-surface-subtle/80 py-4 px-6 text-center text-xs text-navy-400 font-medium">
          <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
            <span>ExamIIO &copy; {new Date().getFullYear()} • Authoritative Examination Platform</span>
            <span className="text-[11px] text-navy-400">SOC-2 Type II Certified &amp; FERPA Compliant</span>
          </div>
        </footer>
      </div>
    </div>
  );
};

export default DashboardLayout;
