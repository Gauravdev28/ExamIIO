import React from 'react';
import { Outlet } from 'react-router-dom';
import { PublicNavbar } from './PublicNavbar';
import { PublicFooter } from './PublicFooter';
import { ErrorBoundary } from '../common/ErrorBoundary';

export const PublicLayout: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col bg-canvas text-navy-900 selection:bg-brand-500/20 selection:text-navy-950 w-full">
      <PublicNavbar />
      <main className="flex-1 w-full min-w-0">
        <ErrorBoundary fallbackTitle="Page Load Error">
          <Outlet />
        </ErrorBoundary>
      </main>
      <PublicFooter />
    </div>
  );
};

export default PublicLayout;
