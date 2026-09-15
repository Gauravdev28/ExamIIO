import React from 'react';
import { Outlet } from 'react-router-dom';
import { SessionTimeoutManager } from '../auth/SessionTimeoutManager';
import { ForcePasswordChangeModal } from '../auth/ForcePasswordChangeModal';
import { OfficialNameSetupModal } from '../auth/OfficialNameSetupModal';
import { ErrorBoundary } from '../common/ErrorBoundary';

/**
 * Isolated layout for the high-security candidate examination room (/student/room/*).
 *
 * NON-NEGOTIABLE SAFETY RULES:
 * - NO dashboard sidebar or mobile navigation drawer
 * - NO public or authenticated navigation headers
 * - NO distracting decorative background shapes or parallax animations
 * - Preserves full screen, security event detection, webcam, and proctoring isolation
 */
export const ExamRoomLayout: React.FC = () => {
  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-slate-50 text-slate-900 select-none">
      <SessionTimeoutManager />
      <ForcePasswordChangeModal />
      <OfficialNameSetupModal />
      <ErrorBoundary fallbackTitle="Exam Room Error">
        <Outlet />
      </ErrorBoundary>
    </div>
  );
};

export default ExamRoomLayout;
