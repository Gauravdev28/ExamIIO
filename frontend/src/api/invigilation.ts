import api from './client';
import {
  ProctorAssignment,
  ProctorIntervention,
  StudentIntervention,
  ProctorChatMessage,
  TriageCandidate,
  WarningPayload,
  PausePayload,
  ResumePayload,
  TerminatePayload,
  ReattemptPayload,
  ProctorReattemptAuthorizationResponse,
} from '../types/invigilation';

export const InvigilationAPI = {
  // Proctor Endpoints
  authorizeReattempt: async (attemptId: string, payload: ReattemptPayload): Promise<ProctorReattemptAuthorizationResponse> => {
    const response = await api.post(`/proctor/attempts/${attemptId}/reattempt/`, payload);
    return response.data;
  },
  getAssignedAssessments: async (): Promise<ProctorAssignment[]> => {
    const response = await api.get('/proctor/assessments/');
    return response.data;
  },

  getLiveRoster: async (assessmentId: string): Promise<{ assessment_id: string; count: number; candidates: TriageCandidate[] }> => {
    const response = await api.get(`/proctor/assessments/${assessmentId}/live-roster/`);
    return response.data;
  },

  issueWarning: async (attemptId: string, payload: WarningPayload): Promise<ProctorIntervention> => {
    const response = await api.post(`/proctor/attempts/${attemptId}/warning/`, payload);
    return response.data;
  },

  pauseAttempt: async (attemptId: string, payload: PausePayload = {}): Promise<ProctorIntervention> => {
    const response = await api.post(`/proctor/attempts/${attemptId}/pause/`, payload);
    return response.data;
  },

  resumeAttempt: async (attemptId: string, payload: ResumePayload = {}): Promise<ProctorIntervention> => {
    const response = await api.post(`/proctor/attempts/${attemptId}/resume/`, payload);
    return response.data;
  },

  requestRoomScan: async (attemptId: string, reason = ''): Promise<ProctorIntervention> => {
    const response = await api.post(`/proctor/attempts/${attemptId}/room-scan/`, { reason });
    return response.data;
  },

  terminateAttempt: async (attemptId: string, payload: TerminatePayload): Promise<{ status: string; attempt_status: string; intervention: ProctorIntervention }> => {
    const response = await api.post(`/proctor/attempts/${attemptId}/terminate/`, payload);
    return response.data;
  },

  cancelTermination: async (attemptId: string, reason = '', internalNotes = ''): Promise<{
    status: string;
    attempt_id: string;
    attempt_status: string;
    cancelled_at: string;
    cancelled_by: string;
    intervention_id: string;
    message: string;
  }> => {
    const response = await api.post(`/proctor/attempts/${attemptId}/cancel-termination/`, {
      reason,
      internal_notes: internalNotes,
    });
    return response.data;
  },

  getInterventionHistory: async (attemptId: string): Promise<ProctorIntervention[]> => {
    const response = await api.get(`/proctor/attempts/${attemptId}/interventions/`);
    return response.data;
  },

  getChatHistory: async (attemptId: string): Promise<ProctorChatMessage[]> => {
    const response = await api.get(`/proctor/attempts/${attemptId}/chat/`);
    return response.data;
  },

  sendMessage: async (attemptId: string, messageText: string, recipientId?: string): Promise<ProctorChatMessage> => {
    const response = await api.post(`/proctor/attempts/${attemptId}/chat/`, {
      message_text: messageText,
      recipient_id: recipientId || null,
    });
    return response.data;
  },

  // Student Endpoints
  acknowledgeWarning: async (attemptId: string, interventionId: string): Promise<StudentIntervention> => {
    const response = await api.post(`/student/attempts/${attemptId}/acknowledge-warning/`, {
      intervention_id: interventionId,
    });
    return response.data;
  },

  completeRoomScan: async (attemptId: string, scanEventId: string): Promise<StudentIntervention> => {
    const response = await api.post(`/student/attempts/${attemptId}/complete-room-scan/`, {
      scan_event_id: scanEventId,
    });
    return response.data;
  },

  getStudentInterventions: async (attemptId: string): Promise<StudentIntervention[]> => {
    const response = await api.get(`/student/attempts/${attemptId}/interventions/`);
    return response.data;
  },
};
