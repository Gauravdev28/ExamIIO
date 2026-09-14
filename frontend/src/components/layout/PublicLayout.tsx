import React from 'react';
import { Outlet } from 'react-router-dom';
import { PublicNavbar } from './PublicNavbar';
import { PublicFooter } from './PublicFooter';
import { ErrorBoundary } from '../common/ErrorBoundary';

export const PublicLayout: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col bg-[#F4F1EA] text-[#243247] selection:bg-[#2878D8]/20 selection:text-[#243247] w-full">
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
