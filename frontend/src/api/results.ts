import api from './client';
import {
  AssessmentResult,
  AssessmentAnalytics,
  QuestionAnalyticsItem,
  StudentTopicPerformance,
  ReportJob,
  Certificate,
  AssessmentCertificateSummary,
  PublicCertificateVerification,
  AdminCandidateResultDetail,
} from '../types/results';

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export const ResultsAPI = {
  // Student Endpoints
  getStudentAttemptResult: async (attemptId: string): Promise<AssessmentResult> => {
    const response = await api.get(`/student/attempts/${attemptId}/result/`);
    return response.data.data;
  },

  getStudentResults: async (page = 1): Promise<PaginatedResponse<AssessmentResult>> => {
    const response = await api.get(`/student/results/?page=${page}`);
    return response.data;
  },

  getStudentResultDetail: async (resultId: string): Promise<AssessmentResult> => {
    const response = await api.get(`/student/results/${resultId}/`);
    return response.data.data;
  },

  getStudentTopicAnalytics: async (): Promise<StudentTopicPerformance[]> => {
    const response = await api.get('/student/analytics/topics/');
    return response.data.data.topics;
  },

  createStudentReport: async (assessmentId: string, format: 'PDF' | 'XLSX' | 'CSV'): Promise<ReportJob> => {
    const response = await api.post('/student/reports/', {
      report_type: 'STUDENT_SCORECARD',
      format,
      assessment_id: assessmentId,
    });
    return response.data.data;
  },

  getStudentReportStatus: async (reportId: string): Promise<ReportJob> => {
    const response = await api.get(`/student/reports/${reportId}/`);
    return response.data.data;
  },

  getStudentCoinsSummary: async (): Promise<{
    total_coins: number;
    correct_questions_count: number;
    milestone_progress: {
      current_coins: number;
      next_milestone: number;
      progress_percent: number;
      remaining_coins: number;
    };
  }> => {
    const response = await api.get('/student/coins/');
    return response.data.data;
  },

  getStudentCoinsLeaderboard: async (): Promise<{
    leaderboard: Array<{
      rank: number;
      student_id: string;
      name: string;
      roll_number: string;
      coins: number;
    }>;
  }> => {
    const response = await api.get('/student/coins/leaderboard/');
    return response.data.data;
  },

  // Admin Endpoints
  getAdminAssessmentResults: async (
    assessmentId: string,
    params: {
      page?: number;
      search?: string;
      is_passed?: boolean;
      score_min?: number;
      score_max?: number;
      ordering?: string;
    } = {}
  ): Promise<PaginatedResponse<AssessmentResult>> => {
    const response = await api.get(`/admin/assessments/${assessmentId}/results/`, { params });
    return response.data;
  },

  getAdminResultDetail: async (resultId: string): Promise<AssessmentResult> => {
    const response = await api.get(`/admin/results/${resultId}/`);
    return response.data.data;
  },

  getAdminAssessmentResultDetail: async (
    assessmentId: string,
    resultId: string
  ): Promise<AdminCandidateResultDetail> => {
    const response = await api.get(`/admin/assessments/${assessmentId}/results/${resultId}/`);
    return response.data.data;
  },

  getAdminAssessmentAnalytics: async (assessmentId: string): Promise<AssessmentAnalytics> => {
    const response = await api.get(`/admin/assessments/${assessmentId}/analytics/`);
    return response.data.data;
  },

  getAdminQuestionAnalytics: async (assessmentId: string): Promise<QuestionAnalyticsItem[]> => {
    const response = await api.get(`/admin/assessments/${assessmentId}/analytics/questions/`);
    return response.data.data.questions;
  },

  releaseAdminAssessmentResults: async (assessmentId: string): Promise<{ released_count: number }> => {
    const response = await api.post(`/admin/assessments/${assessmentId}/release-results/`);
    return response.data.data;
  },

  createAdminReport: async (
    assessmentId: string,
    reportType: 'ASSESSMENT_SUMMARY' | 'ASSESSMENT_ROSTER',
    format: 'PDF' | 'XLSX' | 'CSV'
  ): Promise<ReportJob> => {
    const response = await api.post('/admin/reports/', {
      assessment_id: assessmentId,
      report_type: reportType,
      format,
    });
    return response.data.data;
  },

  getAdminReportStatus: async (reportId: string): Promise<ReportJob> => {
    const response = await api.get(`/admin/reports/${reportId}/`);
    return response.data.data;
  },

  // Participation Certificates (Student)
  getStudentCertificates: async (params?: { search?: string; status?: string }): Promise<Certificate[]> => {
    const response = await api.get('/student/certificates/', { params });
    return response.data.data;
  },

  getStudentCertificateDetail: async (id: string): Promise<Certificate> => {
    const response = await api.get(`/student/certificates/${id}/`);
    return response.data.data;
  },

  downloadStudentCertificate: async (id: string, certificateId: string): Promise<void> => {
    const response = await api.get(`/student/certificates/${id}/download/`, {
      responseType: 'blob',
    });
    const blob = new Blob([response.data], { type: 'application/pdf' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `certificate_${certificateId}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  // Participation Certificates (Admin)
  getAdminCertificateAssessmentSummary: async (params?: {
    search?: string;
  }): Promise<AssessmentCertificateSummary[]> => {
    const response = await api.get('/admin/certificates/assessments/', { params });
    return response.data.data;
  },

  getAdminAssessmentCertificates: async (
    assessmentId: string,
    params?: {
      page?: number;
      status?: string;
      search?: string;
    }
  ): Promise<
    PaginatedResponse<Certificate> & {
      assessment?: { id: string; title: string; status: string; total_certificates: number };
    }
  > => {
    const response = await api.get(`/admin/assessments/${assessmentId}/certificates/`, { params });
    return response.data;
  },

  getAdminCertificates: async (params?: {
    page?: number;
    exam_id?: string;
    status?: string;
    search?: string;
  }): Promise<PaginatedResponse<Certificate>> => {
    const response = await api.get('/admin/certificates/', { params });
    return response.data;
  },

  getAdminCertificateDetail: async (id: string): Promise<Certificate> => {
    const response = await api.get(`/admin/certificates/${id}/`);
    return response.data.data;
  },

  retryAdminCertificate: async (id: string): Promise<Certificate> => {
    const response = await api.post(`/admin/certificates/${id}/retry/`);
    return response.data.data;
  },

  downloadAdminCertificate: async (id: string, certificateId: string): Promise<void> => {
    const response = await api.get(`/admin/certificates/${id}/download/`, {
      responseType: 'blob',
    });
    const blob = new Blob([response.data], { type: 'application/pdf' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `certificate_${certificateId}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  // Public Verification
  verifyPublicCertificate: async (certificateId: string): Promise<PublicCertificateVerification> => {
    const response = await api.get(`/public/certificates/verify/${certificateId}/`);
    return response.data.data;
  },
};

