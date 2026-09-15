import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  Clock,
  Megaphone,
  AlertCircle,
  CheckCheck,
  Send,
  ExternalLink,
  X,
  Sparkles,
} from 'lucide-react';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import {
  NotificationsAPI,
  NotificationItem,
  NotificationType,
} from '../../api/notifications';

export interface NotificationPanelProps {
  isOpen: boolean;
  onClose: () => void;
  isAdmin?: boolean;
  onOpenAdminSend?: () => void;
  unreadCount: number;
  onUnreadCountChange: (count: number) => void;
}

export const NotificationPanel: React.FC<NotificationPanelProps> = ({
  isOpen,
  onClose,
  isAdmin = false,
  onOpenAdminSend,
  unreadCount,
  onUnreadCountChange,
}) => {
  const navigate = useNavigate();
  const panelRef = useRef<HTMLDivElement>(null);

  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [filter, setFilter] = useState<'all' | 'unread'>('all');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadNotifications();
    }
  }, [isOpen]);

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen, onClose]);

  // Escape key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const loadNotifications = async () => {
    setIsLoading(true);
    try {
      const data = await NotificationsAPI.getNotifications(false);
      setNotifications(data.notifications || []);
      onUnreadCountChange(data.unread_count || 0);
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  };

  const handleMarkAsRead = async (item: NotificationItem) => {
    if (item.is_read) return;
    try {
      const res = await NotificationsAPI.markAsRead(item.id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === item.id ? { ...n, is_read: true, read_at: new Date().toISOString() } : n))
      );
      onUnreadCountChange(res.unread_count);
    } catch {
      // ignore
    }
  };

  const handleMarkAllAsRead = async () => {
    try {
      const res = await NotificationsAPI.markAllAsRead();
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, is_read: true, read_at: new Date().toISOString() }))
      );
      onUnreadCountChange(res.unread_count);
    } catch {
      // ignore
    }
  };

  const handleAssessmentClick = (item: NotificationItem) => {
    onClose();
    if (isAdmin) {
      navigate(item.assessment ? `/admin/assessments/${item.assessment}` : '/admin/assessments');
    } else {
      navigate('/student/assessments');
    }
  };

  const formatRelativeTime = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMin = Math.floor(diffMs / 60000);
      const diffHour = Math.floor(diffMin / 60);
      const diffDay = Math.floor(diffHour / 24);

      if (diffMin < 1) return 'Just now';
      if (diffMin < 60) return `${diffMin}m ago`;
      if (diffHour < 24) return `${diffHour}h ago`;
      if (diffDay === 1) return 'Yesterday';
      if (diffDay < 7) return `${diffDay}d ago`;
      return date.toLocaleDateString();
    } catch {
      return '';
    }
  };

  const getTypeIcon = (type: NotificationType) => {
    switch (type) {
      case 'REMINDER':
        return <Clock className="w-4 h-4 text-amber-600" />;
      case 'ANNOUNCEMENT':
        return <Megaphone className="w-4 h-4 text-purple-600" />;
      case 'ALERT':
        return <AlertCircle className="w-4 h-4 text-coral-600" />;
      default:
        return <Bell className="w-4 h-4 text-brand-600" />;
    }
  };

  const getTypeBadge = (type: NotificationType) => {
    switch (type) {
      case 'REMINDER':
        return <Badge variant="amber" size="sm">Reminder</Badge>;
      case 'ANNOUNCEMENT':
        return <Badge variant="violet" size="sm">Announcement</Badge>;
      case 'ALERT':
        return <Badge variant="coral" size="sm">Alert</Badge>;
      default:
        return <Badge variant="blue" size="sm">Notice</Badge>;
    }
  };

  if (!isOpen) return null;

  const displayedNotifications = notifications.filter((n) => {
    if (filter === 'unread') return !n.is_read;
    return true;
  });

  return (
    <div
      ref={panelRef}
      className="absolute right-0 top-full mt-2 w-80 sm:w-96 rounded-2xl bg-[#FFFDF8] border border-warm-200 shadow-warm-xl z-50 animate-scale-in text-navy-900 overflow-hidden"
      role="dialog"
      aria-label="Notifications panel"
    >
      {/* Header */}
      <div className="p-4 border-b border-warm-200 bg-surface flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h3 className="font-bold text-sm font-display text-navy-900">Notifications</h3>
          {unreadCount > 0 && (
            <Badge variant="blue" size="sm">
              {unreadCount} new
            </Badge>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          {isAdmin && onOpenAdminSend && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                onClose();
                onOpenAdminSend();
              }}
              className="text-[11px] py-1 px-2.5 flex items-center gap-1"
            >
              <Send className="w-3 h-3 text-brand-600" />
              <span>Send</span>
            </Button>
          )}

          {unreadCount > 0 && (
            <button
              type="button"
              onClick={handleMarkAllAsRead}
              className="text-[11px] text-brand-600 hover:text-brand-700 font-semibold px-2 py-1 rounded-lg hover:bg-warm-100 transition-colors flex items-center gap-1"
              title="Mark all notifications as read"
            >
              <CheckCheck className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Mark read</span>
            </button>
          )}

          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-navy-400 hover:text-navy-700 hover:bg-warm-100 transition-colors"
            aria-label="Close notifications"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="px-4 py-2 border-b border-warm-200 bg-canvas-subtle/50 flex items-center gap-2">
        <button
          type="button"
          onClick={() => setFilter('all')}
          className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors ${
            filter === 'all'
              ? 'bg-surface text-brand-700 border border-warm-200 shadow-warm-xs'
              : 'text-navy-500 hover:text-navy-800'
          }`}
        >
          All ({notifications.length})
        </button>
        <button
          type="button"
          onClick={() => setFilter('unread')}
          className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors ${
            filter === 'unread'
              ? 'bg-surface text-brand-700 border border-warm-200 shadow-warm-xs'
              : 'text-navy-500 hover:text-navy-800'
          }`}
        >
          Unread ({unreadCount})
        </button>
      </div>

      {/* Notifications List */}
      <div className="max-h-88 overflow-y-auto divide-y divide-warm-100">
        {isLoading ? (
          <div className="py-12 text-center text-xs text-navy-400 font-mono">
            Loading notifications...
          </div>
        ) : displayedNotifications.length === 0 ? (
          <div className="py-12 px-6 text-center space-y-2">
            <div className="w-10 h-10 rounded-xl bg-brand-50 border border-brand-200 text-brand-600 mx-auto flex items-center justify-center">
              <Sparkles className="w-5 h-5" />
            </div>
            <div className="text-xs font-bold text-navy-900">
              {filter === 'unread' ? "You're all caught up!" : 'No notifications yet'}
            </div>
            <p className="text-[11px] text-navy-500 max-w-xs mx-auto leading-relaxed">
              {filter === 'unread'
                ? 'All incoming announcements and reminders have been marked as read.'
                : 'Examination notices, schedules, and institutional announcements will appear here.'}
            </p>
          </div>
        ) : (
          displayedNotifications.map((item) => (
            <div
              key={item.id}
              onClick={() => handleMarkAsRead(item)}
              className={`p-3.5 transition-colors cursor-pointer flex items-start gap-3 text-left ${
                item.is_read
                  ? 'hover:bg-warm-100/50 bg-surface'
                  : 'bg-brand-50/40 hover:bg-brand-50/70'
              }`}
            >
              {/* Category Icon */}
              <div className="w-8 h-8 rounded-lg bg-surface border border-warm-200 flex items-center justify-center shrink-0 mt-0.5 shadow-warm-xs">
                {getTypeIcon(item.notification_type)}
              </div>

              {/* Body */}
              <div className="flex-1 min-w-0 space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className={`text-xs font-bold truncate ${item.is_read ? 'text-navy-900' : 'text-brand-900 font-extrabold'}`}>
                      {item.title}
                    </span>
                    {!item.is_read && (
                      <span className="w-1.5 h-1.5 rounded-full bg-brand-600 shrink-0" />
                    )}
                  </div>
                  <span className="text-[10px] text-navy-400 font-mono shrink-0 whitespace-nowrap">
                    {formatRelativeTime(item.created_at)}
                  </span>
                </div>

                <p className="text-xs text-navy-600 leading-relaxed break-words">
                  {item.message}
                </p>

                <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                  <div className="flex items-center gap-1.5">
                    {getTypeBadge(item.notification_type)}
                    {item.sender_name && item.sender_name !== 'System' && (
                      <span className="text-[10px] text-navy-400">
                        by {item.sender_name}
                      </span>
                    )}
                  </div>

                  {item.assessment && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleAssessmentClick(item);
                      }}
                      className="text-[11px] font-semibold text-brand-600 hover:text-brand-800 flex items-center gap-1"
                    >
                      <span>View Exam</span>
                      <ExternalLink className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="p-2.5 bg-canvas-subtle/50 border-t border-warm-200 text-center text-[10px] text-navy-400 font-medium">
        <span>ExamIIO Secure Notification Delivery</span>
      </div>
    </div>
  );
};

export default NotificationPanel;
