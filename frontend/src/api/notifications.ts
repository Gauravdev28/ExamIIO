import api from './client';

export type NotificationType = 'NOTICE' | 'REMINDER' | 'ANNOUNCEMENT' | 'ALERT';
export type NotificationAudience = 'INDIVIDUAL' | 'ALL_STUDENTS';

export interface NotificationItem {
  id: string;
  title: string;
  message: string;
  notification_type: NotificationType;
  audience: NotificationAudience;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
  sender_name: string;
  assessment: string | null;
  assessment_title: string | null;
}

export interface StudentOption {
  id: string;
  email: string;
  display_name: string;
  roll_number: string;
  euid: string;
}

export interface SendNotificationPayload {
  audience: NotificationAudience;
  recipient_id?: string;
  title: string;
  message: string;
  notification_type: NotificationType;
  assessment_id?: string;
}

export const NotificationsAPI = {
  getNotifications: async (unreadOnly = false): Promise<{
    notifications: NotificationItem[];
    unread_count: number;
    total_count: number;
  }> => {
    const response = await api.get('/notifications/', {
      params: { unread_only: unreadOnly ? 'true' : 'false' }
    });
    return response.data.data;
  },

  getUnreadCount: async (): Promise<number> => {
    const response = await api.get('/notifications/unread-count/');
    return response.data.data.unread_count;
  },

  markAsRead: async (id: string): Promise<{
    notification: NotificationItem;
    unread_count: number;
  }> => {
    const response = await api.patch(`/notifications/${id}/read/`);
    return response.data.data;
  },

  markAllAsRead: async (): Promise<{
    marked_count: number;
    unread_count: number;
  }> => {
    const response = await api.post('/notifications/mark-all-read/');
    return response.data.data;
  },

  sendNotification: async (payload: SendNotificationPayload): Promise<{
    sent_count: number;
    audience: string;
    notification?: NotificationItem;
  }> => {
    const response = await api.post('/notifications/send/', payload);
    return response.data.data;
  },

  getStudentOptions: async (query = ''): Promise<StudentOption[]> => {
    const response = await api.get('/notifications/students/', {
      params: { q: query }
    });
    return response.data.data.students;
  },
};
