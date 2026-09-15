import React, { useState, useEffect } from 'react';
import {
  X,
  Send,
  Users,
  User,
  AlertCircle,
  CheckCircle2,
  Search,
} from 'lucide-react';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import {
  NotificationsAPI,
  NotificationType,
  NotificationAudience,
  StudentOption,
} from '../../api/notifications';
import { getAdminAssessments } from '../../api/assessments';
import { AssessmentAdminItem } from '../../types/assessment';

export interface AdminSendNotificationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export const AdminSendNotificationModal: React.FC<AdminSendNotificationModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [audience, setAudience] = useState<NotificationAudience>('INDIVIDUAL');
  const [notificationType, setNotificationType] = useState<NotificationType>('NOTICE');
  const [title, setTitle] = useState('');
  const [message, setMessage] = useState('');

  // Student selection
  const [students, setStudents] = useState<StudentOption[]>([]);
  const [selectedStudent, setSelectedStudent] = useState<StudentOption | null>(null);
  const [studentSearchQuery, setStudentSearchQuery] = useState('');
  const [isLoadingStudents, setIsLoadingStudents] = useState(false);

  // Optional assessment selection
  const [assessments, setAssessments] = useState<AssessmentAdminItem[]>([]);
  const [selectedAssessmentId, setSelectedAssessmentId] = useState<string>('');

  // Status & Feedback
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadStudents();
      loadAssessments();
      setErrorMessage(null);
      setSuccessMessage(null);
    }
  }, [isOpen]);

  const loadStudents = async (q = '') => {
    setIsLoadingStudents(true);
    try {
      const data = await NotificationsAPI.getStudentOptions(q);
      setStudents(data || []);
    } catch {
      // ignore
    } finally {
      setIsLoadingStudents(false);
    }
  };

  const loadAssessments = async () => {
    try {
      const res = await getAdminAssessments({ page_size: 50 });
      if (res && res.data && res.data.results) {
        setAssessments(res.data.results);
      }
    } catch {
      // ignore
    }
  };

  const handleStudentSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setStudentSearchQuery(val);
    loadStudents(val);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    const cleanTitle = title.trim();
    const cleanMessage = message.trim();

    if (!cleanTitle) {
      setErrorMessage('Please provide a notification title.');
      return;
    }
    if (!cleanMessage) {
      setErrorMessage('Please provide a notification message.');
      return;
    }

    if (audience === 'INDIVIDUAL' && !selectedStudent) {
      setErrorMessage('Please select a recipient student.');
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await NotificationsAPI.sendNotification({
        audience,
        recipient_id: audience === 'INDIVIDUAL' ? selectedStudent?.id : undefined,
        title: cleanTitle,
        message: cleanMessage,
        notification_type: notificationType,
        assessment_id: selectedAssessmentId || undefined,
      });

      setSuccessMessage(
        audience === 'INDIVIDUAL'
          ? `Notification dispatched to student ${selectedStudent?.display_name || selectedStudent?.email}.`
          : `Announcement broadcast to ${res.sent_count} active students.`
      );

      // Reset form
      setTitle('');
      setMessage('');
      setSelectedStudent(null);
      setSelectedAssessmentId('');

      if (onSuccess) {
        onSuccess();
      }

      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (err: any) {
      const msg = err.response?.data?.message || err.error?.message || err.message || 'Failed to dispatch notification.';
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  const filteredStudents = students.filter((s) => {
    if (!studentSearchQuery) return true;
    const q = studentSearchQuery.toLowerCase();
    return (
      s.email.toLowerCase().includes(q) ||
      s.display_name.toLowerCase().includes(q) ||
      s.roll_number.toLowerCase().includes(q) ||
      s.euid.toLowerCase().includes(q)
    );
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/50 backdrop-blur-xs overflow-y-auto">
      <div className="max-w-xl w-full p-6 space-y-5 border border-warm-200 bg-[#FFFDF8] shadow-warm-xl rounded-2xl relative my-8 animate-scale-in text-navy-900">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 border-b border-warm-200 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-xl bg-brand-50 border border-brand-200 text-brand-600 flex items-center justify-center shrink-0">
              <Send className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold font-display text-navy-900">
                Author &amp; Dispatch Notification
              </h3>
              <p className="text-xs text-navy-500">
                Send targeted announcements or individual reminders to candidates
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-navy-400 hover:text-navy-700 hover:bg-warm-100 transition-colors"
            disabled={isSubmitting}
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Feedback Alerts */}
        {errorMessage && (
          <div className="p-3.5 rounded-xl bg-coral-50 border border-coral-200 text-coral-800 text-xs flex items-start gap-2.5 shadow-warm-xs">
            <AlertCircle className="w-4 h-4 text-coral-600 shrink-0 mt-0.5" />
            <span className="leading-relaxed font-medium">{errorMessage}</span>
          </div>
        )}

        {successMessage && (
          <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-start gap-2.5 shadow-warm-xs">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <span className="leading-relaxed font-medium">{successMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Target Audience Selector */}
          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-navy-900 uppercase tracking-wider">
              Target Audience
            </label>
            <div className="grid grid-cols-2 gap-2.5">
              <button
                type="button"
                onClick={() => setAudience('INDIVIDUAL')}
                className={`flex items-center gap-2 p-3 rounded-xl border text-left text-xs font-semibold transition-all ${
                  audience === 'INDIVIDUAL'
                    ? 'bg-brand-50 border-brand-500 text-brand-700 shadow-warm-xs'
                    : 'bg-surface border-warm-200 text-navy-600 hover:bg-warm-100/70'
                }`}
              >
                <User className={`w-4 h-4 ${audience === 'INDIVIDUAL' ? 'text-brand-600' : 'text-navy-400'}`} />
                <div>
                  <div className="font-bold">Individual Student</div>
                  <div className="text-[10px] text-navy-500 font-normal">Direct notice to candidate</div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => setAudience('ALL_STUDENTS')}
                className={`flex items-center gap-2 p-3 rounded-xl border text-left text-xs font-semibold transition-all ${
                  audience === 'ALL_STUDENTS'
                    ? 'bg-brand-50 border-brand-500 text-brand-700 shadow-warm-xs'
                    : 'bg-surface border-warm-200 text-navy-600 hover:bg-warm-100/70'
                }`}
              >
                <Users className={`w-4 h-4 ${audience === 'ALL_STUDENTS' ? 'text-brand-600' : 'text-navy-400'}`} />
                <div>
                  <div className="font-bold">All Students</div>
                  <div className="text-[10px] text-navy-500 font-normal">Broadcast to all active examinees</div>
                </div>
              </button>
            </div>
          </div>

          {/* Individual Recipient Selector */}
          {audience === 'INDIVIDUAL' && (
            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-navy-900">
                Select Recipient Candidate
              </label>

              {selectedStudent ? (
                <div className="flex items-center justify-between p-3 rounded-xl bg-warm-100 border border-warm-200 text-xs">
                  <div>
                    <div className="font-bold text-navy-900">{selectedStudent.display_name || selectedStudent.email}</div>
                    <div className="text-[11px] text-navy-500 font-mono">
                      {selectedStudent.email} {selectedStudent.roll_number && `• Roll: ${selectedStudent.roll_number}`}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedStudent(null)}
                    className="text-navy-500 hover:text-navy-800"
                  >
                    Change
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-navy-400" />
                    <input
                      type="text"
                      value={studentSearchQuery}
                      onChange={handleStudentSearchChange}
                      placeholder="Search candidate by name, roll number, or email..."
                      className="w-full pl-8 pr-3 py-2 text-xs bg-surface border border-warm-200 rounded-xl text-navy-900 placeholder:text-navy-400 focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                    />
                  </div>

                  <div className="max-h-36 overflow-y-auto border border-warm-200 rounded-xl bg-surface divide-y divide-warm-100">
                    {isLoadingStudents ? (
                      <div className="p-3 text-center text-xs text-navy-400 font-mono">
                        Loading candidates...
                      </div>
                    ) : filteredStudents.length === 0 ? (
                      <div className="p-3 text-center text-xs text-navy-400">
                        No students found matching your search.
                      </div>
                    ) : (
                      filteredStudents.map((st) => (
                        <button
                          key={st.id}
                          type="button"
                          onClick={() => {
                            setSelectedStudent(st);
                            setStudentSearchQuery('');
                          }}
                          className="w-full text-left p-2.5 hover:bg-warm-100/70 transition-colors flex items-center justify-between gap-2 text-xs"
                        >
                          <div>
                            <div className="font-semibold text-navy-900">{st.display_name || st.email}</div>
                            <div className="text-[10px] text-navy-500 font-mono">
                              {st.email} {st.roll_number && `• Roll: ${st.roll_number}`}
                            </div>
                          </div>
                          <Badge variant="blue" size="sm">
                            Select
                          </Badge>
                        </button>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Category & Assessment Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Category / Type */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-navy-900">
                Notification Category
              </label>
              <select
                value={notificationType}
                onChange={(e) => setNotificationType(e.target.value as NotificationType)}
                className="w-full px-3 py-2 text-xs bg-surface border border-warm-200 rounded-xl text-navy-900 focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              >
                <option value="NOTICE">Notice (General Informational)</option>
                <option value="REMINDER">Reminder (Upcoming Schedule)</option>
                <option value="ANNOUNCEMENT">Announcement (Institutional)</option>
                <option value="ALERT">Alert (Important / Urgent)</option>
              </select>
            </div>

            {/* Optional Assessment Link */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-navy-900">
                Related Assessment <span className="text-navy-400 font-normal">(Optional)</span>
              </label>
              <select
                value={selectedAssessmentId}
                onChange={(e) => setSelectedAssessmentId(e.target.value)}
                className="w-full px-3 py-2 text-xs bg-surface border border-warm-200 rounded-xl text-navy-900 focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              >
                <option value="">None (General Notification)</option>
                {assessments.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.title} ({a.status})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Title */}
          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-navy-900">
              Notification Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Assessment Schedule Reminder or Lab Access Notice"
              maxLength={255}
              className="w-full px-3.5 py-2 text-xs bg-surface border border-warm-200 rounded-xl text-navy-900 placeholder:text-navy-400 focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
            />
          </div>

          {/* Message Body */}
          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-navy-900">
              Message Body
            </label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={3}
              placeholder="Enter instructions, schedule details, or institutional guidance..."
              className="w-full px-3.5 py-2 text-xs bg-surface border border-warm-200 rounded-xl text-navy-900 placeholder:text-navy-400 focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 resize-none"
            />
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-warm-200">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isSubmitting}
              disabled={isSubmitting}
              className="flex items-center gap-1.5"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{audience === 'ALL_STUDENTS' ? 'Broadcast to All' : 'Send Notification'}</span>
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AdminSendNotificationModal;
