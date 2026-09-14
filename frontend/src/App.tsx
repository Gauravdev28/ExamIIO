import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { Navbar } from './components/layout/Navbar';
import { PublicLayout } from './components/layout/PublicLayout';
import { HomePage } from './pages/public/HomePage';
import { AboutPage } from './pages/public/AboutPage';
import { FeaturesPage } from './pages/public/FeaturesPage';
import { SecurityPage } from './pages/public/SecurityPage';
import { HowItWorksPage } from './pages/public/HowItWorksPage';
import { LoginPage } from './pages/auth/LoginPage';
import { HealthCheckPage } from './pages/HealthCheckPage';
import { DashboardPage } from './pages/DashboardPage';
import { AdminStudentsPage } from './pages/admin/AdminStudentsPage';
import { AdminQuestionsPage } from './pages/admin/AdminQuestionsPage';
import { QuestionEditorPage } from './pages/admin/QuestionEditorPage';
import { AdminAssessmentsPage } from './pages/admin/AdminAssessmentsPage';
import { AssessmentEditorPage } from './pages/admin/AssessmentEditorPage';
import { AdminProctoringDashboardPage } from './pages/admin/AdminProctoringDashboardPage';
import { AdminAssessmentResultsPage } from './pages/admin/AdminAssessmentResultsPage';
import { AdminCandidateResultDetailPage } from './pages/admin/AdminCandidateResultDetailPage';
import { AdminAssessmentAttendancePage } from './pages/admin/AdminAssessmentAttendancePage';
import { AdminRetentionDashboardPage } from './pages/admin/AdminRetentionDashboardPage';
import { AdminManagementPage } from './pages/admin/AdminManagementPage';
import { AdminProfilePage } from './pages/admin/AdminProfilePage';
import { ProctorLiveConsolePage } from './pages/admin/ProctorLiveConsolePage';
import { ProctorDashboardPage } from './pages/proctor/ProctorDashboardPage';
import { StudentDashboardPage } from './pages/student/StudentDashboardPage';
import { StudentAssessmentsPage } from './pages/student/StudentAssessmentsPage';
import { StudentTestRoomPage } from './pages/student/StudentTestRoomPage';
import { StudentResultPage } from './pages/student/StudentResultPage';
import { StudentProfilePage } from './pages/student/StudentProfilePage';
import { StudentPrivacyPage } from './pages/student/StudentPrivacyPage';
import { StudentCertificatesPage } from './pages/student/StudentCertificatesPage';
import { AdminCertificatesPage } from './pages/admin/AdminCertificatesPage';
import { PublicCertificateVerificationPage } from './pages/public/PublicCertificateVerificationPage';
import { 
  AdminRoute, 
  ProctorRoute, 
  StudentRoute, 
  AuthenticatedRoute 
} from './components/common/ProtectedRoute';
import { ForcePasswordChangeModal } from './components/auth/ForcePasswordChangeModal';
import { OfficialNameSetupModal } from './components/auth/OfficialNameSetupModal';
import { SessionTimeoutManager } from './components/auth/SessionTimeoutManager';
import { ErrorBoundary } from './components/common/ErrorBoundary';

// Authenticated Application Shell layout
const AuthenticatedAppLayout: React.FC = () => {
  const location = useLocation();
  const isExamRoom = location.pathname.startsWith('/student/room/');

  if (isExamRoom) {
    return (
      <div className="h-screen w-screen overflow-hidden flex flex-col bg-slate-50 text-slate-900">
        <SessionTimeoutManager />
        <ForcePasswordChangeModal />
        <OfficialNameSetupModal />
        <ErrorBoundary fallbackTitle="Exam Room Error">
          <Outlet />
        </ErrorBoundary>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#F4F1EA] text-[#243247] selection:bg-[#2878D8]/20 selection:text-[#243247] w-full">
      <Navbar />
      <SessionTimeoutManager />
      <ForcePasswordChangeModal />
      <OfficialNameSetupModal />
      <main className="flex-1 w-full min-w-0">
        <ErrorBoundary fallbackTitle="Page Load Error">
          <Outlet />
        </ErrorBoundary>
      </main>
      <footer className="border-t border-[#DDD8CE] bg-[#E8E4DC] py-6 text-center text-xs text-[#5E6B7D] font-medium w-full">
        ExamIIO &copy; {new Date().getFullYear()}
      </footer>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* ============================================================
              PUBLIC ROUTES (No authentication required)
              ============================================================ */}
          <Route element={<PublicLayout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/features" element={<FeaturesPage />} />
            <Route path="/security" element={<SecurityPage />} />
            <Route path="/how-it-works" element={<HowItWorksPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/health" element={<HealthCheckPage />} />
            <Route path="/verify/:certificateId" element={<PublicCertificateVerificationPage />} />
          </Route>

          {/* ============================================================
              AUTHENTICATED ROUTES (Role-protected internal workspaces)
              ============================================================ */}
          <Route element={<AuthenticatedAppLayout />}>
            {/* --- ADMIN APPLICATION ROUTES --- */}
            <Route
              path="/admin"
              element={
                <AdminRoute>
                  <DashboardPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/dashboard"
              element={
                <AdminRoute>
                  <DashboardPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/assessments"
              element={
                <AdminRoute>
                  <AdminAssessmentsPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/assessments/create"
              element={
                <AdminRoute>
                  <AssessmentEditorPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/assessments/:id"
              element={
                <AdminRoute>
                  <AssessmentEditorPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/assessments/:assessmentId/proctoring"
              element={
                <AdminRoute>
                  <AdminProctoringDashboardPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/assessments/:assessmentId/results"
              element={
                <AdminRoute>
                  <AdminAssessmentResultsPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/assessments/:assessmentId/results/:resultId"
              element={
                <AdminRoute>
                  <AdminCandidateResultDetailPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/assessments/:assessmentId/attendance"
              element={
                <AdminRoute>
                  <AdminAssessmentAttendancePage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/questions"
              element={
                <AdminRoute>
                  <AdminQuestionsPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/questions/create"
              element={
                <AdminRoute>
                  <QuestionEditorPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/questions/:id/versions/:version"
              element={
                <AdminRoute>
                  <QuestionEditorPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/students"
              element={
                <AdminRoute>
                  <AdminStudentsPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/administrators"
              element={
                <AdminRoute>
                  <AdminManagementPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/profile"
              element={
                <AdminRoute>
                  <AdminProfilePage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/results"
              element={
                <AdminRoute>
                  <AdminAssessmentResultsPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/certificates"
              element={
                <AdminRoute>
                  <AdminCertificatesPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/retention"
              element={
                <AdminRoute>
                  <AdminRetentionDashboardPage />
                </AdminRoute>
              }
            />

            {/* --- PROCTOR APPLICATION ROUTES --- */}
            <Route
              path="/proctor"
              element={
                <ProctorRoute>
                  <ProctorDashboardPage />
                </ProctorRoute>
              }
            />
            <Route
              path="/proctor/dashboard"
              element={
                <ProctorRoute>
                  <ProctorDashboardPage />
                </ProctorRoute>
              }
            />
            <Route
              path="/proctor/console/:assessmentId"
              element={
                <ProctorRoute>
                  <ProctorLiveConsolePage />
                </ProctorRoute>
              }
            />
            {/* Backward-compatible proctor console route */}
            <Route
              path="/admin/proctor/console/:assessmentId"
              element={
                <AuthenticatedRoute>
                  <ProctorLiveConsolePage />
                </AuthenticatedRoute>
              }
            />

            {/* --- STUDENT APPLICATION ROUTES --- */}
            <Route
              path="/student"
              element={
                <StudentRoute>
                  <StudentDashboardPage />
                </StudentRoute>
              }
            />
            <Route
              path="/student/dashboard"
              element={
                <StudentRoute>
                  <StudentDashboardPage />
                </StudentRoute>
              }
            />
            <Route
              path="/student/assessments"
              element={
                <StudentRoute>
                  <StudentAssessmentsPage />
                </StudentRoute>
              }
            />
            <Route
              path="/student/room/:attemptId"
              element={
                <StudentRoute>
                  <StudentTestRoomPage />
                </StudentRoute>
              }
            />
            <Route
              path="/student/attempts/:attemptId/result"
              element={
                <StudentRoute>
                  <StudentResultPage />
                </StudentRoute>
              }
            />
            <Route
              path="/student/results/:resultId"
              element={
                <StudentRoute>
                  <StudentResultPage />
                </StudentRoute>
              }
            />
            <Route
              path="/student/profile"
              element={
                <StudentRoute>
                  <StudentProfilePage />
                </StudentRoute>
              }
            />
            <Route
              path="/student/certificates"
              element={
                <StudentRoute>
                  <StudentCertificatesPage />
                </StudentRoute>
              }
            />
            <Route
              path="/student/privacy"
              element={
                <StudentRoute>
                  <StudentPrivacyPage />
                </StudentRoute>
              }
            />
          </Route>

          {/* Fallback to Home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
