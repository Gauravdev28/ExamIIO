import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import {
  getStudentAttemptDetail,
  saveAttemptAnswer,
  submitAttempt,
  terminateAttempt,
} from '../../api/assessments';
import { getCookie } from '../../api/client';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import {
  Clock,
  CheckCircle2,
  Code2,
  Wifi,
  WifiOff,
  ChevronLeft,
  ChevronRight,
  Send,
  Lock,
  HelpCircle,
  AlertTriangle,
  Camera,
  CameraOff,
  Mic,
  MicOff,
  Shield,
  Pause,
  XCircle,
  AlertCircle,
  Play,
} from 'lucide-react';
import {
  StudentAttemptDetail,
  StudentSnapshotQuestion,
  StudentAnswerData,
} from '../../types/assessment';
import { evaluatorApi } from '../../api/evaluator';
import { CodeSubmissionResult } from '../../types/evaluator';
import {
  startProctoringSession,
  reportBrowserEvent,
  uploadProctoringFrame,
  acknowledgeWarning,
  sendProctoringHeartbeat,
} from '../../api/proctoring';
import { ProctoringWarning } from '../../types/proctoring';
import { InvigilationAPI } from '../../api/invigilation';

export const StudentTestRoomPage: React.FC = () => {
  const { attemptId } = useParams<{ attemptId: string }>();
  const navigate = useNavigate();

  const [attemptData, setAttemptData] = useState<StudentAttemptDetail | null>(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState<number>(0);
  const [answers, setAnswers] = useState<Record<string, StudentAnswerData>>({});

  // Timer & Real-time State
  const [remainingSeconds, setRemainingSeconds] = useState<number>(0);
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [saveStatus, setSaveStatus] = useState<'SAVED' | 'SAVING' | 'ERROR'>('SAVED');

  // Submit Modal & State
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitErrorMessage, setSubmitErrorMessage] = useState<string | null>(null);

  // UI state
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Evaluator Execution State
  const [executingQuestionId, setExecutingQuestionId] = useState<string | null>(null);
  const [executionMode, setExecutionMode] = useState<'RUN' | 'SUBMIT' | null>(null);
  const [submissionResults, setSubmissionResults] = useState<Record<string, CodeSubmissionResult | undefined>>({});
  const [activeTestCaseTabs, setActiveTestCaseTabs] = useState<Record<string, number>>({});
  const [executionError, setExecutionError] = useState<Record<string, string | null>>({});

  // AI Proctoring & Telemetry State
  const [isProctoringActive, setIsProctoringActive] = useState<boolean>(false);
  const [cameraStatus, setCameraStatus] = useState<'CONNECTED' | 'DISCONNECTED' | 'DENIED'>('DISCONNECTED');
  const [micStatus, setMicStatus] = useState<'CONNECTED' | 'DISCONNECTED' | 'DENIED'>('DISCONNECTED');
  const [activeWarning, setActiveWarning] = useState<ProctoringWarning | null>(null);
  const [ackError, setAckError] = useState<string | null>(null);
  const [isAcknowledging, setIsAcknowledging] = useState<boolean>(false);
  const [confirmedViolationsCount, setConfirmedViolationsCount] = useState<number>(0);

  // Live Intervention & Pause State
  const [isAttemptPaused, setIsAttemptPaused] = useState<boolean>(false);
  const [pauseReason, setPauseReason] = useState<string>('');
  const [isRoomScanModalOpen, setIsRoomScanModalOpen] = useState<boolean>(false);
  const [activeRoomScanId, setActiveRoomScanId] = useState<string | null>(null);
  const [roomScanInstructions, setRoomScanInstructions] = useState<string>('');
  const [isTerminatedModalOpen, setIsTerminatedModalOpen] = useState<boolean>(false);
  const [terminationInfo, setTerminationInfo] = useState<{ reason: string; justification: string; terminatedAt?: string } | null>(null);
  const [pendingTermination, setPendingTermination] = useState<{
    pending: boolean;
    deadline?: string | null;
    remainingSeconds: number;
    reason: string;
  } | null>(null);
  const [isCameraVerified, setIsCameraVerified] = useState<boolean>(false);
  const [isReenteringFullscreen, setIsReenteringFullscreen] = useState<boolean>(false);
  const [fullscreenActionError, setFullscreenActionError] = useState<string | null>(null);
  const [isExitCountdownActive, setIsExitCountdownActive] = useState<boolean>(false);
  const [exitCountdownSeconds, setExitCountdownSeconds] = useState<number>(10);

  // Immediate Local-Lock UI Architecture (Wayground / Quizizz style)
  const [integrityLock, setIntegrityLock] = useState<null | 'TAB_SWITCH' | 'WINDOW_SWITCH' | 'FULLSCREEN_EXIT' | 'UNAUTHORIZED_EXIT'>(null);
  const [isExamActive, setIsExamActive] = useState<boolean>(() => {
    if (!attemptId) return false;
    return sessionStorage.getItem(`exam_entry_verified_${attemptId}`) === 'true';
  });
  const [integrityCountdown, setIntegrityCountdown] = useState<number>(120);
  const [integrityDeadline, setIntegrityDeadline] = useState<string | null>(null);

  const integrityLockRef = useRef(integrityLock);
  integrityLockRef.current = integrityLock;
  const isExamActiveRef = useRef(isExamActive);
  isExamActiveRef.current = isExamActive;
  const isUnloadingRef = useRef<boolean>(false);

  // 120-Second Integrity Lock Countdown Ticker
  useEffect(() => {
    if (!integrityLock || integrityLock === 'FULLSCREEN_EXIT') return;

    const interval = setInterval(() => {
      setIntegrityCountdown((prev) => {
        let newSec: number;
        if (integrityDeadline) {
          newSec = Math.max(0, Math.ceil((new Date(integrityDeadline).getTime() - Date.now()) / 1000));
        } else {
          newSec = Math.max(0, prev - 1);
        }

        if (newSec <= 0) {
          clearInterval(interval);
          setIntegrityLock(null);
          setIsTerminatedModalOpen(true);
          setTerminationInfo({
            reason: 'DISQUALIFIED',
            justification: 'EXAMINATION TERMINATED — WINDOW FOCUS LOST',
            terminatedAt: new Date().toISOString(),
          });
          setAttemptData((a) => (a ? { ...a, status: 'CANCELLED' } : null));
          return 0;
        }
        return newSec;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [integrityLock, integrityDeadline]);

  const isCameraVerifiedRef = useRef<boolean>(isCameraVerified);
  isCameraVerifiedRef.current = isCameraVerified;
  const isSubmittingRef = useRef<boolean>(false);
  const isTerminalRef = useRef<boolean>(false);
  const isTerminatedRef = useRef<boolean>(false);
  const pendingTerminationRef = useRef(pendingTermination);
  pendingTerminationRef.current = pendingTermination;
  const lastScreenshotReportedRef = useRef<number>(0);

  const socketRef = useRef<WebSocket | null>(null);
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const revisionsRef = useRef<Record<string, number>>({});
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const frameSeqRef = useRef<number>(0);
  const examContainerRef = useRef<HTMLDivElement | null>(null);

  // Initialize Proctoring & Media Devices
  useEffect(() => {
    if (!attemptId) return;

    let isMounted = true;
    let sampleInterval: NodeJS.Timeout | null = null;
    let heartbeatInterval: NodeJS.Timeout | null = null;

    const setupProctoring = async () => {
      try {
        await startProctoringSession(attemptId);
        if (isMounted) setIsProctoringActive(true);
      } catch (err) {
        console.warn('Proctoring start fallback:', err);
      }

      // Request media devices gracefully
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 320 }, height: { ideal: 240 }, frameRate: { ideal: 10 } },
          audio: true,
        });

        if (!isMounted) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }

        mediaStreamRef.current = stream;
        setCameraStatus('CONNECTED');
        setMicStatus('CONNECTED');

        // Listen for hardware disconnection / track endings
        const videoTrack = stream.getVideoTracks()[0];
        if (videoTrack) {
          videoTrack.onended = () => {
            if (isMounted) {
              setCameraStatus('DISCONNECTED');
              reportBrowserEvent(attemptId, 'CAMERA_UNAVAILABLE').catch(() => {});
            }
          };
          videoTrack.onmute = () => {
            if (isMounted) {
              setCameraStatus('DISCONNECTED');
              reportBrowserEvent(attemptId, 'CAMERA_UNAVAILABLE').catch(() => {});
            }
          };
          videoTrack.onunmute = () => {
            if (isMounted) setCameraStatus('CONNECTED');
          };
        }

        const audioTrack = stream.getAudioTracks()[0];
        if (audioTrack) {
          audioTrack.onended = () => {
            if (isMounted) {
              setMicStatus('DISCONNECTED');
              reportBrowserEvent(attemptId, 'MICROPHONE_UNAVAILABLE').catch(() => {});
            }
          };
          audioTrack.onmute = () => {
            if (isMounted) {
              setMicStatus('DISCONNECTED');
              reportBrowserEvent(attemptId, 'MICROPHONE_UNAVAILABLE').catch(() => {});
            }
          };
          audioTrack.onunmute = () => {
            if (isMounted) setMicStatus('CONNECTED');
          };
        }

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }

        // Periodic Frame Capture (Target 0.5 FPS = 1 frame every 2.0s)
        sampleInterval = setInterval(() => {
          if (!videoRef.current || !canvasRef.current) return;
          const video = videoRef.current;
          if (video.srcObject !== mediaStreamRef.current && mediaStreamRef.current) {
            video.srcObject = mediaStreamRef.current;
          }
          const canvas = canvasRef.current;
          if (video.videoWidth === 0 || video.videoHeight === 0) return;

          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          const ctx = canvas.getContext('2d');
          if (!ctx) return;

          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          canvas.toBlob(
            async (blob) => {
              if (blob && attemptId) {
                frameSeqRef.current += 1;
                try {
                  const res = await uploadProctoringFrame(attemptId, blob, frameSeqRef.current);
                  if (res && res.warning_issued && res.warning) {
                    setActiveWarning(res.warning);
                    if (res.confirmed_violations_count !== undefined) {
                      setConfirmedViolationsCount(res.confirmed_violations_count);
                    }
                  }
                  if (res && (res.disqualified || res.disqualified_reason)) {
                    setTerminationInfo({
                      reason: 'DISQUALIFIED',
                      justification: res.disqualified_reason || 'Security violations threshold exceeded.',
                      terminatedAt: new Date().toISOString(),
                    });
                    setIsTerminatedModalOpen(true);
                    setAttemptData((prev) => (prev ? { ...prev, status: 'CANCELLED' } : null));
                  }
                } catch {
                  // Handled gracefully
                }
              }
            },
            'image/jpeg',
            0.6
          );
        }, 2000);
      } catch (mediaErr) {
        console.warn('Media capture unavailable:', mediaErr);
        if (isMounted) {
          setCameraStatus('DENIED');
          setMicStatus('DENIED');
          reportBrowserEvent(attemptId, 'CAMERA_UNAVAILABLE').catch(() => {});
        }
      }

      // Periodic REST Heartbeat fallback (every 15s)
      heartbeatInterval = setInterval(() => {
        if (attemptId) {
          sendProctoringHeartbeat(attemptId)
            .then((res: any) => {
              if (res && res.warning) {
                const isFsWarn = res.warning.warning_type === 'FULLSCREEN' ||
                  (res.warning as any).reason_code?.includes('FULLSCREEN') ||
                  res.warning.message?.toLowerCase().includes('fullscreen');
                if (!isFsWarn || !document.fullscreenElement) {
                  setActiveWarning(res.warning);
                }
              }
              if (res && res.confirmed_violations_count !== undefined) {
                setConfirmedViolationsCount(res.confirmed_violations_count);
              }
              if (res && res.termination_pending) {
                const rem = res.termination_remaining_seconds !== undefined && res.termination_remaining_seconds !== null
                  ? res.termination_remaining_seconds
                  : (res.termination_deadline ? Math.max(0, Math.ceil((new Date(res.termination_deadline).getTime() - Date.now()) / 1000)) : 120);
                if (!integrityLockRef.current) {
                  setIntegrityLock('WINDOW_SWITCH');
                }
                setIntegrityCountdown(rem);
                setIntegrityDeadline(res.termination_deadline || null);
              }
              if (res && (res.disqualified || res.session_status === 'TERMINATED' || res.attempt_status === 'CANCELLED')) {
                setTerminationInfo({
                  reason: 'DISQUALIFIED',
                  justification: res.disqualified_reason || 'Security violations threshold exceeded.',
                  terminatedAt: new Date().toISOString(),
                });
                setIsTerminatedModalOpen(true);
                setAttemptData((prev) => (prev ? { ...prev, status: 'CANCELLED' } : null));
              }
            })
            .catch(() => {});
        }
      }, 15000);
    };

    setupProctoring();

    // Phase 2: Simplified DOM Event Listeners for Immediate Local Locking
    const handleVisibilityChange = () => {
      if (isUnloadingRef.current || !isExamActiveRef.current) return;
      if (document.hidden || document.visibilityState === 'hidden') {
        setIntegrityLock('TAB_SWITCH');
        setIntegrityCountdown(120);
        if (attemptId && !isTerminalRef.current && !isTerminatedRef.current) {
          reportBrowserEvent(attemptId, 'TAB_SWITCH', { source: 'visibilitychange', state: 'hidden' })
            .then((res: any) => {
              if (res?.termination_deadline) {
                setIntegrityDeadline(res.termination_deadline);
              }
            })
            .catch(() => {});
        }
      }
    };

    const handleWindowBlur = () => {
      if (isUnloadingRef.current || !isExamActiveRef.current) return;
      if (document.visibilityState !== 'hidden' && !document.hidden) {
        setIntegrityLock('WINDOW_SWITCH');
        setIntegrityCountdown(120);
        if (attemptId && !isTerminalRef.current && !isTerminatedRef.current) {
          reportBrowserEvent(attemptId, 'WINDOW_BLUR', { source: 'window_blur' })
            .then((res: any) => {
              if (res?.termination_deadline) {
                setIntegrityDeadline(res.termination_deadline);
              }
            })
            .catch(() => {});
        }
      }
    };

    const handleFullscreenChange = () => {
      if (isUnloadingRef.current || !isExamActiveRef.current) return;
      if (!document.fullscreenElement) {
        setIntegrityLock('FULLSCREEN_EXIT');
        if (attemptId && !isTerminalRef.current && !isTerminatedRef.current) {
          reportBrowserEvent(attemptId, 'FULLSCREEN_EXIT', { source: 'fullscreenchange' }).catch(() => {});
        }
      } else {
        // Automatically clear FULLSCREEN_EXIT lock when fullscreen is restored
        setIntegrityLock((prev) => (prev === 'FULLSCREEN_EXIT' ? null : prev));
        if (attemptId) {
          reportBrowserEvent(attemptId, 'FULLSCREEN_ENTER', { source: 'fullscreenchange' }).catch(() => {});
        }
      }
    };

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      isUnloadingRef.current = true;
      e.preventDefault();
      e.returnValue = '';
      return '';
    };

    const handlePageHide = () => {
      isUnloadingRef.current = true;
    };

    const handlePopState = (e: PopStateEvent) => {
      console.log('[EXAMINATION ROOM] Browser navigation detected (popstate):', e.state);
      setIntegrityLock('UNAUTHORIZED_EXIT');
      setIntegrityCountdown(120);
      if (
        attemptId &&
        !isSubmittingRef.current &&
        !isTerminalRef.current &&
        !isTerminatedRef.current
      ) {
        isTerminalRef.current = true;
        isTerminatedRef.current = true;
        sessionStorage.removeItem(`exam_entry_verified_${attemptId}`);

        // Exactly ONE authoritative termination request via keepalive fetch
        const token = getCookie('csrftoken') || '';
        try {
          fetch(`/api/v1/student/attempts/${attemptId}/terminate/`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': token,
            },
            credentials: 'include',
            body: JSON.stringify({ reason: 'EXAMINATION ABANDONED — BROWSER NAVIGATION / ROOM EXIT' }),
            keepalive: true,
          })
            .then(async (res) => {
              const data = await res.json().catch(() => ({}));
              setTerminationInfo({
                reason: 'DISQUALIFIED',
                justification: data.disqualification_reason || 'Examination abandoned via browser navigation.',
                terminatedAt: new Date().toISOString(),
              });
              setIsTerminatedModalOpen(true);
              setAttemptData((prev) =>
                prev
                  ? {
                      ...prev,
                      status: 'CANCELLED',
                      is_disqualified: true,
                      disqualification_reason: data.disqualification_reason || 'Examination abandoned via browser navigation.',
                    }
                  : null
              );
            })
            .catch(() => {
              setIsTerminatedModalOpen(true);
            });
        } catch {
          setIsTerminatedModalOpen(true);
        }
        reportBrowserEvent(attemptId, 'WINDOW_BLUR', { source: 'popstate', reason: 'UNAUTHORIZED_EXIT' }).catch(() => {});
      }
    };

    // Best-effort browser keyboard telemetry for screenshot attempts
    const handleKeyDown = (e: KeyboardEvent) => {
      const isScreenshotShortcut =
        ((e.metaKey || e.ctrlKey) && e.shiftKey && ['3', '4', '5'].includes(e.key)) ||
        e.key === 'PrintScreen';

      if (isScreenshotShortcut && attemptId && !isSubmittingRef.current && !isTerminalRef.current) {
        const now = Date.now();
        if (now - lastScreenshotReportedRef.current > 3000) {
          lastScreenshotReportedRef.current = now;
          const shortcutKey = `${e.metaKey ? 'Cmd+' : e.ctrlKey ? 'Ctrl+' : ''}${e.shiftKey ? 'Shift+' : ''}${e.key}`;
          reportBrowserEvent(attemptId, 'SCREENSHOT_ATTEMPT' as any, {
            shortcut: shortcutKey,
            source: 'KEYBOARD_TELEMETRY',
            note: 'Native OS-level screenshots cannot be reliably detected by a standard browser; recorded as best-effort telemetry.',
          }).catch(() => {});
        }
      }
    };

    // Browser-Level Copy / Cut / Paste & Context Menu Protection during Active Exam
    const blockClipboardAction = (e: Event) => {
      e.preventDefault();
      e.stopPropagation();
      return false;
    };

    const blockProtectedKeys = (e: KeyboardEvent) => {
      const isCopyCutPaste =
        (e.ctrlKey || e.metaKey) &&
        ['c', 'v', 'x', 'insert'].includes(e.key.toLowerCase());

      if (isCopyCutPaste) {
        e.preventDefault();
        e.stopPropagation();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('blur', handleWindowBlur);
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    window.addEventListener('beforeunload', handleBeforeUnload);
    window.addEventListener('pagehide', handlePageHide);
    window.addEventListener('popstate', handlePopState);
    window.addEventListener('keydown', handleKeyDown);

    // Active exam clipboard protection
    document.addEventListener('copy', blockClipboardAction, true);
    document.addEventListener('cut', blockClipboardAction, true);
    document.addEventListener('paste', blockClipboardAction, true);
    document.addEventListener('contextmenu', blockClipboardAction, true);
    document.addEventListener('keydown', blockProtectedKeys, true);

    // Browser Back Trap
    try {
      window.history.pushState({ examActive: true, attemptId }, '', window.location.href);
    } catch {}

    return () => {
      isMounted = false;
      if (sampleInterval) clearInterval(sampleInterval);
      if (heartbeatInterval) clearInterval(heartbeatInterval);
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('blur', handleWindowBlur);
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      window.removeEventListener('beforeunload', handleBeforeUnload);
      window.removeEventListener('pagehide', handlePageHide);
      window.removeEventListener('popstate', handlePopState);
      window.removeEventListener('keydown', handleKeyDown);

      document.removeEventListener('copy', blockClipboardAction, true);
      document.removeEventListener('cut', blockClipboardAction, true);
      document.removeEventListener('paste', blockClipboardAction, true);
      document.removeEventListener('contextmenu', blockClipboardAction, true);
      document.removeEventListener('keydown', blockProtectedKeys, true);
    };
  }, [attemptId]);

  const handleAcknowledgeWarning = async () => {
    if (!activeWarning || !attemptId) {
      return;
    }
    setAckError(null);
    setIsAcknowledging(true);
    try {
      if (activeWarning.id) {
        try {
          await InvigilationAPI.acknowledgeWarning(attemptId, activeWarning.id);
        } catch {
          await acknowledgeWarning(attemptId, activeWarning.id);
        }
      }
      setActiveWarning(null);
    } catch {
      setAckError('Warning acknowledgement could not be synchronized. Please retry.');
    } finally {
      setIsAcknowledging(false);
    }
  };

  const handleCompleteRoomScan = async () => {
    if (activeRoomScanId && attemptId) {
      try {
        await InvigilationAPI.completeRoomScan(attemptId, activeRoomScanId);
      } catch (err) {
        console.warn('Room scan complete error:', err);
      }
    }
    setIsRoomScanModalOpen(false);
    setActiveRoomScanId(null);
  };

  // Load Attempt State
  const loadAttemptState = useCallback(async () => {
    if (!attemptId) return;
    try {
      const res = await getStudentAttemptDetail(attemptId);
      if (res.data) {
        const d = res.data;
        setAttemptData(d);
        setRemainingSeconds(d.remaining_seconds);
        setAnswers(d.answers || {});

        if (d.active_warning) {
          setActiveWarning(d.active_warning);
        }
        if (typeof d.confirmed_violations_count === 'number') {
          setConfirmedViolationsCount(d.confirmed_violations_count);
        }

        // Decouple attempt lifecycle from exam entry verification.
        const hasSessionVerified = sessionStorage.getItem(`exam_entry_verified_${attemptId}`) === 'true';
        if (hasSessionVerified) {
          setIsCameraVerified(true);
          setIsExamActive(true);
        }

        if (d.is_disqualified || d.status === 'CANCELLED') {
          sessionStorage.removeItem(`exam_entry_verified_${attemptId}`);
          setIntegrityLock(null);
          setTerminationInfo({
            reason: 'DISQUALIFIED',
            justification: d.disqualification_reason || 'Security violations threshold exceeded.',
            terminatedAt: new Date().toISOString(),
          });
          setIsTerminatedModalOpen(true);
        } else if (d.termination_pending) {
          const rem = d.termination_remaining_seconds !== undefined && d.termination_remaining_seconds !== null
            ? d.termination_remaining_seconds
            : (d.termination_deadline ? Math.max(0, Math.ceil((new Date(d.termination_deadline).getTime() - Date.now()) / 1000)) : 120);
          if (!integrityLockRef.current) {
            setIntegrityLock('WINDOW_SWITCH');
          }
          setIntegrityCountdown(rem);
          setIntegrityDeadline(d.termination_deadline ?? null);
          setPendingTermination({
            pending: true,
            deadline: d.termination_deadline ?? null,
            remainingSeconds: rem,
            reason: d.termination_reason || 'EXAM WINDOW LOST FOCUS',
          });
        } else {
          // If integrityLock is active, STRICTLY IGNORE incoming state reporting termination_pending: false!
          if (!integrityLockRef.current) {
            setIntegrityDeadline(null);
            setPendingTermination(null);
          }
        }

        // Initialize local revisions
        const revMap: Record<string, number> = {};
        Object.entries(d.answers || {}).forEach(([qId, ans]) => {
          revMap[qId] = ans.revision || 1;
        });
        revisionsRef.current = revMap;
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to load test attempt.');
    } finally {
      setIsLoading(false);
    }
  }, [attemptId]);

  useEffect(() => {
    loadAttemptState();
  }, [loadAttemptState]);

  // WebSocket Connection with Bounded Exponential Backoff Reconnection
  useEffect(() => {
    if (!attemptId) return;

    let isDisposed = false;
    let reconnectAttempts = 0;
    const maxReconnectDelay = 30000;
    let reconnectTimer: any = null;
    let pingInterval: any = null;

    const connectWebSocket = () => {
      if (isDisposed) return;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/attempts/${attemptId}/`;

      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        if (isDisposed) {
          ws.close();
          return;
        }
        setWsConnected(true);
        reconnectAttempts = 0;
        ws.send(JSON.stringify({ action: 'PING' }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'PONG' || data.type === 'SYNC_STATE') {
            if (typeof data.remaining_seconds === 'number') {
              setRemainingSeconds(data.remaining_seconds);
            }
            if (data.status === 'EXPIRED' || data.status === 'SUBMITTED') {
              setAttemptData((prev) => (prev ? { ...prev, status: data.status } : null));
            }
          } else if (data.type === 'CODE_SUBMISSION_COMPLETED' || data.type === 'CODE_SUBMISSION_QUEUED' || data.type === 'CODE_SUBMISSION_PROCESSING') {
            const submData = data.data;
            if (submData && submData.question_id && data.type === 'CODE_SUBMISSION_COMPLETED') {
              evaluatorApi.getSubmissionResult(submData.submission_id).then((res) => {
                if (res.data) {
                  setSubmissionResults((prev) => ({
                    ...prev,
                    [submData.question_id]: res.data,
                  }));
                }
                setExecutingQuestionId(null);
                setExecutionMode(null);
              }).catch(() => {
                setExecutingQuestionId(null);
                setExecutionMode(null);
              });
            }
          } else {
            const evt = (data.data && typeof data.data === 'object' ? data.data : data) || {};
            const eventName = evt.event || data.event || data.type;

            if (eventName === 'PAUSE_STARTED') {
              setIsAttemptPaused(true);
              setPauseReason(evt.reason || evt.message || 'Attempt paused by proctor.');
            } else if (eventName === 'PAUSE_ENDED') {
              setIsAttemptPaused(false);
              if (typeof evt.remaining_seconds === 'number') {
                setRemainingSeconds(evt.remaining_seconds);
              }
            } else if (eventName === 'WARNING_ISSUED') {
              setActiveWarning({
                id: evt.intervention_id || evt.id,
                warning_type: evt.reason_code || evt.warning_type || 'FOCUS_LOSS',
                message: evt.message || 'Assessment window lost focus. Please return to the examination window.',
                issued_at: evt.issued_at || new Date().toISOString(),
                acknowledged_at: null,
              });
              if (typeof evt.warnings_count === 'number') {
                setConfirmedViolationsCount(evt.warnings_count);
              } else {
                setConfirmedViolationsCount((c) => c + 1);
              }
            } else if (eventName === 'ROOM_SCAN_REQUESTED') {
              setActiveRoomScanId(evt.intervention_id || evt.id);
              setRoomScanInstructions(evt.instructions || 'Please perform a 360 room scan using your webcam.');
              setIsRoomScanModalOpen(true);
            } else if (eventName === 'TERMINATION_PENDING') {
              const rem = evt.remaining_seconds !== undefined && evt.remaining_seconds !== null
                ? evt.remaining_seconds
                : (evt.termination_deadline ? Math.max(0, Math.ceil((new Date(evt.termination_deadline).getTime() - Date.now()) / 1000)) : 120);
              if (!integrityLockRef.current) {
                setIntegrityLock('WINDOW_SWITCH');
              }
              setIntegrityCountdown(rem);
              setIntegrityDeadline(evt.termination_deadline || null);
              setPendingTermination({
                pending: true,
                deadline: evt.termination_deadline,
                remainingSeconds: rem,
                reason: evt.reason || 'EXAM WINDOW LOST FOCUS',
              });
            } else if (eventName === 'PROCTOR_RESCUE' || eventName === 'TERMINATION_CANCELLED') {
              // The ONLY way to clear the integrityLock state from backend
              setIntegrityLock(null);
              setIntegrityDeadline(null);
              setPendingTermination(null);
            } else if (eventName === 'TERMINATED' || eventName === 'TERMINATION_CONFIRMED' || eventName === 'TERMINATION_REQUESTED') {
              setIntegrityLock(null);
              setPendingTermination(null);
              setTerminationInfo({
                reason: evt.reason_code || 'DISQUALIFIED',
                justification: evt.disqualification_reason || evt.justification || 'EXAMINATION TERMINATED — WINDOW FOCUS LOST',
                terminatedAt: evt.server_time || evt.terminated_at || new Date().toISOString(),
              });
              setIsTerminatedModalOpen(true);
              setAttemptData((prev) => (prev ? { ...prev, status: 'CANCELLED' } : null));
            }
          }
        } catch (err) {
          console.error('WS error parsing message', err);
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        if (pingInterval) clearInterval(pingInterval);
        if (!isDisposed) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), maxReconnectDelay);
          reconnectAttempts += 1;
          reconnectTimer = setTimeout(() => {
            connectWebSocket();
          }, delay);
        }
      };
    };

    connectWebSocket();

    return () => {
      isDisposed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (socketRef.current) socketRef.current.close();
    };
  }, [attemptId]);

  const getWarningTitle = (warningType?: string, reasonCode?: string) => {
    const code = (warningType || reasonCode || '').toUpperCase();
    if (code.includes('FACE_MISS') || code.includes('FACE_VISIBILITY')) {
      return '⚠ FACE NOT DETECTED';
    }
    if (code.includes('MULTIPLE_PEOPLE') || code.includes('MULTIPLE_FACES')) {
      return '⚠ MULTIPLE PERSONS DETECTED';
    }
    if (code.includes('DEVICE') || code.includes('PHONE')) {
      return '⚠ PHONE DETECTED';
    }
    if (code.includes('HEAD') || code.includes('GAZE') || code.includes('POSE')) {
      return '⚠ PLEASE FACE THE CAMERA';
    }
    if (code.includes('CAMERA')) {
      return '⚠ CAMERA CONNECTION LOST';
    }
    if (code.includes('AUDIO') || code.includes('MIC')) {
      return '⚠ MICROPHONE CONNECTION LOST';
    }
    if (code.includes('FULLSCREEN')) {
      return '⚠ FULLSCREEN EXITED';
    }
    return '⚠ EXAMINATION WARNING';
  };

  // Handle Code Run (Public Tests Only — Does not finalize or award coins)
  const handleRunCode = async (questionId: string) => {
    if (!attemptId) return;
    const currentAns = answers[questionId];
    const code = currentAns?.code_response || '';
    const lang = currentAns?.code_language || 'PYTHON';

    setExecutingQuestionId(questionId);
    setExecutionMode('RUN');
    setExecutionError((prev) => ({ ...prev, [questionId]: null }));

    try {
      const res = await evaluatorApi.runCode(attemptId, questionId, code, lang);
      if (res.data) {
        const subId = res.data.submission_id;
        let pollCount = 0;
        const pollInterval = setInterval(async () => {
          pollCount += 1;
          try {
            const subRes = await evaluatorApi.getSubmissionResult(subId);
            if (subRes.data && (subRes.data.status === 'COMPLETED' || subRes.data.status === 'FAILED')) {
              clearInterval(pollInterval);
              setSubmissionResults((prev) => ({ ...prev, [questionId]: subRes.data }));
              setExecutingQuestionId(null);
              setExecutionMode(null);
            } else if (pollCount >= 15) {
              clearInterval(pollInterval);
              setExecutingQuestionId(null);
              setExecutionMode(null);
              setExecutionError((prev) => ({
                ...prev,
                [questionId]: 'Execution is taking longer than expected. Please try again.',
              }));
            }
          } catch {
            clearInterval(pollInterval);
            setExecutingQuestionId(null);
            setExecutionMode(null);
          }
        }, 1000);
      }
    } catch (err: any) {
      setExecutionError((prev) => ({
        ...prev,
        [questionId]: err.error?.message || err.message || 'Execution request failed.',
      }));
      setExecutingQuestionId(null);
      setExecutionMode(null);
    }
  };

  // Handle Code Submit (Authoritative Hidden-Test Evaluation)
  const handleSubmitCode = async (questionId: string) => {
    if (!attemptId) return;
    const currentAns = answers[questionId];
    const code = currentAns?.code_response || '';
    const lang = currentAns?.code_language || 'PYTHON';

    setExecutingQuestionId(questionId);
    setExecutionMode('SUBMIT');
    setExecutionError((prev) => ({ ...prev, [questionId]: null }));

    try {
      const res = await evaluatorApi.submitCode(attemptId, questionId, code, lang);
      if (res.data) {
        const subId = res.data.submission_id;
        let pollCount = 0;
        const pollInterval = setInterval(async () => {
          pollCount += 1;
          try {
            const subRes = await evaluatorApi.getSubmissionResult(subId);
            if (subRes.data && (subRes.data.status === 'COMPLETED' || subRes.data.status === 'FAILED')) {
              clearInterval(pollInterval);
              setSubmissionResults((prev) => ({ ...prev, [questionId]: subRes.data }));
              setExecutingQuestionId(null);
              setExecutionMode(null);
              setAnswers((prev) => ({
                ...prev,
                [questionId]: {
                  ...prev[questionId],
                  is_answered: true,
                  code_response: code,
                  code_language: lang,
                }
              }));
            } else if (pollCount >= 15) {
              clearInterval(pollInterval);
              setExecutingQuestionId(null);
              setExecutionMode(null);
              setExecutionError((prev) => ({
                ...prev,
                [questionId]: 'Execution is taking longer than expected. Please try again.',
              }));
            }
          } catch {
            clearInterval(pollInterval);
            setExecutingQuestionId(null);
            setExecutionMode(null);
          }
        }, 1000);
      }
    } catch (err: any) {
      setExecutionError((prev) => ({
        ...prev,
        [questionId]: err.error?.message || err.message || 'Submission evaluation failed.',
      }));
      setExecutingQuestionId(null);
      setExecutionMode(null);
    }
  };

  // Local Countdown Timer
  useEffect(() => {
    if (remainingSeconds <= 0) return;

    const timer = setInterval(() => {
      setRemainingSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          loadAttemptState();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [remainingSeconds, loadAttemptState]);

  // Debounced Autosave Handler
  const triggerAutosave = (questionId: string, updatedFields: Partial<StudentAnswerData>) => {
    if (!attemptId || attemptData?.status !== 'IN_PROGRESS') return;

    setSaveStatus('SAVING');

    setAnswers((prev) => {
      const existing = prev[questionId] || {
        question_id: questionId,
        question_type: currentQuestion?.question_type || 'MCQ',
        revision: revisionsRef.current[questionId] || 1,
        is_answered: true,
      };
      return {
        ...prev,
        [questionId]: {
          ...existing,
          ...updatedFields,
          is_answered: true,
        },
      };
    });

    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    saveTimeoutRef.current = setTimeout(async () => {
      const nextRev = (revisionsRef.current[questionId] || 1) + 1;
      revisionsRef.current[questionId] = nextRev;

      try {
        const payload: any = {
          ...updatedFields,
          revision: nextRev,
        };
        const res = await saveAttemptAnswer(attemptId, questionId, payload);
        if (res.data?.status === 'SAVED') {
          setSaveStatus('SAVED');
          revisionsRef.current[questionId] = res.data.server_revision;
        } else {
          setSaveStatus('SAVED');
        }
      } catch (err) {
        console.error('Autosave error', err);
        setSaveStatus('ERROR');
      }
    }, 600);
  };

  const handleSubmit = async () => {
    if (!attemptId) return;
    isSubmittingRef.current = true;
    setIsSubmitting(true);
    setSubmitErrorMessage(null);
    try {
      const res = await submitAttempt(attemptId);
      if (res.data) {
        setAttemptData((prev) => (prev ? { ...prev, status: 'SUBMITTED' } : null));
        setIsSubmitModalOpen(false);
        if (document.fullscreenElement) {
          try {
            await document.exitFullscreen();
          } catch (e) {
            // ignore
          }
        }
      }
    } catch (err: any) {
      isSubmittingRef.current = false;
      setSubmitErrorMessage(err.error?.message || err.message || 'Failed to submit assessment. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReturnToFullscreen = async () => {
    setIsReenteringFullscreen(true);
    setFullscreenActionError(null);
    try {
      const target = examContainerRef.current || document.documentElement;
      if (target.requestFullscreen) {
        await target.requestFullscreen();
      } else if ((target as any).webkitRequestFullscreen) {
        await (target as any).webkitRequestFullscreen();
      } else if ((target as any).msRequestFullscreen) {
        await (target as any).msRequestFullscreen();
      }
    } catch (err) {
      console.warn('Re-entering fullscreen rejected by browser:', err);
      try {
        if (document.documentElement.requestFullscreen) {
          await document.documentElement.requestFullscreen();
        } else if ((document.documentElement as any).webkitRequestFullscreen) {
          await (document.documentElement as any).webkitRequestFullscreen();
        }
      } catch (fallbackErr) {
        console.warn('Document fallback fullscreen also rejected:', fallbackErr);
      }
    } finally {
      setIsReenteringFullscreen(false);
      if (document.fullscreenElement) {
        setFullscreenActionError(null);
        setActiveWarning((prev) => {
          if (
            prev &&
            (prev.warning_type === 'FULLSCREEN' ||
              (prev as any).reason_code?.includes('FULLSCREEN') ||
              prev.message?.toLowerCase().includes('fullscreen') ||
              prev.message?.toLowerCase().includes('full-screen'))
          ) {
            return null;
          }
          return prev;
        });
        if (attemptId) {
          reportBrowserEvent(attemptId, 'FULLSCREEN_ENTER').catch(() => {});
        }
      } else {
        setFullscreenActionError('Fullscreen must be restored before continuing.');
      }
    }
  };

  const handleExecuteTermination = async () => {
    if (!attemptId || isTerminatedRef.current) return;
    isTerminatedRef.current = true;
    isTerminalRef.current = true;
    setIsExitCountdownActive(false);

    try {
      await terminateAttempt(attemptId, 'EXAMINATION TERMINATED BY CANDIDATE — VOLUNTARY EXIT');
    } catch (err) {
      console.warn('Voluntary termination error:', err);
    } finally {
      if (document.fullscreenElement) {
        try {
          await document.exitFullscreen();
        } catch (e) {
          // ignore
        }
      }
      setTerminationInfo({
        reason: 'VOLUNTARY_EXIT',
        justification: 'Examination was terminated by candidate after exiting fullscreen.',
        terminatedAt: new Date().toISOString(),
      });
      setIsTerminatedModalOpen(true);
      setAttemptData((prev) => (prev ? { ...prev, status: 'CANCELLED', is_disqualified: true, disqualification_reason: 'Examination was terminated by candidate after exiting fullscreen.' } : null));
    }
  };

  const handleCancelExitAndReturnToFullscreen = async () => {
    setIsExitCountdownActive(false);
    setExitCountdownSeconds(10);
    await handleReturnToFullscreen();
  };

  useEffect(() => {
    if (!isExitCountdownActive) {
      setExitCountdownSeconds(10);
      return;
    }

    const countdownTimer = setInterval(() => {
      setExitCountdownSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(countdownTimer);
          handleExecuteTermination();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(countdownTimer);
  }, [isExitCountdownActive]);

  const enterExam = () => {
    const req = document.documentElement.requestFullscreen || (document.documentElement as any).webkitRequestFullscreen;
    if (req) {
      req.call(document.documentElement)
        .then(() => {
          setIsExamActive(true);
          setIsCameraVerified(true);
          if (attemptId) {
            sessionStorage.setItem(`exam_entry_verified_${attemptId}`, 'true');
          }
          window.history.pushState({ examActive: true, attemptId }, '', window.location.href);
        })
        .catch((err: any) => {
          console.warn('requestFullscreen rejected (e.g. non-interactive or testing environment):', err);
          setIsExamActive(true);
          setIsCameraVerified(true);
          if (attemptId) {
            sessionStorage.setItem(`exam_entry_verified_${attemptId}`, 'true');
          }
          window.history.pushState({ examActive: true, attemptId }, '', window.location.href);
        });
    } else {
      setIsExamActive(true);
      setIsCameraVerified(true);
      if (attemptId) {
        sessionStorage.setItem(`exam_entry_verified_${attemptId}`, 'true');
      }
      window.history.pushState({ examActive: true, attemptId }, '', window.location.href);
    }
  };

  const handleEnterExamination = enterExam;

  const questions = attemptData?.questions || [];
  const currentQuestion: StudentSnapshotQuestion | undefined = questions[currentQuestionIndex];
  const currentAnswer = currentQuestion ? answers[currentQuestion.snapshot_question_id] : undefined;

  const isTerminal =
    attemptData?.status === 'SUBMITTED' ||
    attemptData?.status === 'EXPIRED' ||
    attemptData?.status === 'CANCELLED' ||
    Boolean(attemptData?.is_disqualified) ||
    (attemptData !== null && remainingSeconds === 0);

  isTerminalRef.current = isTerminal;

  const isWarningFullscreen = Boolean(
    activeWarning && (
      activeWarning.warning_type === 'FULLSCREEN' ||
      (activeWarning as any).reason_code?.includes('FULLSCREEN') ||
      activeWarning.message?.toLowerCase().includes('fullscreen') ||
      activeWarning.message?.toLowerCase().includes('full-screen')
    )
  );

  // Format Timer MM:SS
  const formatTime = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const s = secs % 60;
    return `${String(mins).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  const answeredCount = Object.values(answers).filter((a) => a.is_answered).length;

  // Loading Screen (Light Theme)
  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center space-y-4 bg-slate-50 text-slate-800">
        <div className="w-10 h-10 border-3 border-emerald-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs text-slate-600 font-mono">Initializing secure examination room & snapshot...</p>
      </div>
    );
  }

  // Error Screen (Light Theme)
  if (errorMessage) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-slate-50 text-slate-900">
        <Card className="max-w-md w-full p-8 text-center space-y-6 border-slate-200 bg-white shadow-xl">
          <div className="w-14 h-14 rounded-2xl bg-rose-50 text-rose-600 border border-rose-200 flex items-center justify-center mx-auto">
            <AlertTriangle className="w-8 h-8 text-rose-600" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-900">Examination Access Error</h2>
            <p className="text-xs text-rose-700 mt-2 font-mono">{errorMessage}</p>
          </div>
          <Button variant="secondary" size="md" className="w-full" onClick={() => navigate('/student/assessments')}>
            Return to Assessments
          </Button>
        </Card>
      </div>
    );
  }

  // Terminal / Expired / Disqualified Screen (Light Theme)
  if (isTerminal && attemptData?.status !== 'IN_PROGRESS') {
    const isDisqualified = attemptData?.status === 'CANCELLED' || Boolean(attemptData?.is_disqualified);
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-slate-50 text-slate-900">
        <Card className="max-w-md w-full p-8 text-center space-y-6 border-slate-200 bg-white shadow-xl">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto">
            {isDisqualified ? (
              <div className="w-14 h-14 rounded-2xl bg-rose-50 text-rose-600 border border-rose-200 flex items-center justify-center">
                <XCircle className="w-8 h-8 text-rose-600" />
              </div>
            ) : attemptData?.status === 'SUBMITTED' ? (
              <div className="w-14 h-14 rounded-2xl bg-emerald-50 text-emerald-600 border border-emerald-200 flex items-center justify-center">
                <CheckCircle2 className="w-8 h-8 text-emerald-600" />
              </div>
            ) : (
              <div className="w-14 h-14 rounded-2xl bg-amber-50 text-amber-600 border border-amber-200 flex items-center justify-center">
                <Lock className="w-8 h-8 text-amber-600" />
              </div>
            )}
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-900">
              {isDisqualified
                ? 'Examination Terminated'
                : attemptData?.status === 'SUBMITTED'
                ? 'Assessment Submitted'
                : 'Assessment Time Expired'}
            </h2>
            <p className="text-xs text-slate-600 mt-2 font-mono leading-relaxed">
              {isDisqualified
                ? (attemptData?.disqualification_reason || 'This attempt has been cancelled and submitted for academic integrity review.')
                : 'Your examination responses have been recorded securely on the server.'}
            </p>
          </div>
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 font-mono text-xs text-slate-700 space-y-1.5 text-left">
            <div>Assessment: <strong className="text-slate-900">{attemptData?.title}</strong></div>
            <div>Status: <span className={isDisqualified ? 'text-rose-600 font-bold' : 'text-emerald-700 font-bold'}>{isDisqualified ? 'DISQUALIFIED' : attemptData?.status}</span></div>
            <div>Total Questions: <strong>{questions.length}</strong></div>
            <div>Answered: <strong className="text-emerald-700">{answeredCount}</strong></div>
          </div>
          <Button variant="primary" size="md" className="w-full" onClick={() => navigate('/student')}>
            Return to Student Dashboard
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div
      ref={examContainerRef}
      className="h-screen w-screen flex flex-col bg-slate-50 text-slate-900 selection:bg-brand-500/20 selection:text-brand-900 overflow-hidden select-none"
      onContextMenu={(e) => e.preventDefault()}
    >
      {/* Top HUD Bar (Light Theme) */}
      <header className="sticky top-0 z-40 bg-white border-b border-slate-200 shadow-xs px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase bg-slate-900 text-white shadow-xs">
                <Lock className="w-2.5 h-2.5 text-amber-400" /> SECURE EXAM
              </span>
              <h2 className="text-sm font-bold text-slate-900 truncate max-w-xs sm:max-w-md">
                {attemptData?.title}
              </h2>
            </div>
            <span className="text-[11px] font-mono text-slate-500">
              Attempt #{attemptData?.attempt_number} &bull; Q{currentQuestionIndex + 1} of {questions.length}
            </span>
          </div>
        </div>

        {/* Center: Timer & Proctoring Status */}
        <div className="flex items-center gap-4 sm:gap-6 font-mono text-xs">
          {/* Server Authoritative Timer */}
          <div
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl border font-bold ${
              remainingSeconds < 300
                ? 'bg-rose-50 border-rose-200 text-rose-700 animate-pulse'
                : 'bg-slate-100 border-slate-200 text-slate-800'
            }`}
          >
            <Clock className="w-4 h-4 text-slate-600" />
            <span className="text-sm">{formatTime(remainingSeconds)}</span>
          </div>

          {/* Autosave Status */}
          <div className="hidden sm:flex items-center gap-1.5 text-xs text-slate-500">
            <span
              className={`w-2 h-2 rounded-full ${
                saveStatus === 'SAVED'
                  ? 'bg-emerald-500'
                  : saveStatus === 'SAVING'
                  ? 'bg-amber-500 animate-pulse'
                  : 'bg-rose-500'
              }`}
            />
            <span>{saveStatus === 'SAVED' ? 'Saved' : saveStatus === 'SAVING' ? 'Saving...' : 'Sync Error'}</span>
          </div>

          {/* AI Proctoring HUD Status */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-xl bg-slate-50 border border-slate-200 text-[11px]">
            <span className={`flex items-center gap-1 ${cameraStatus === 'CONNECTED' ? 'text-emerald-700 font-semibold' : 'text-rose-700 font-semibold'}`}>
              {cameraStatus === 'CONNECTED' ? <Camera className="w-3.5 h-3.5" /> : <CameraOff className="w-3.5 h-3.5" />}
              <span>{cameraStatus === 'CONNECTED' ? 'Camera ● ON' : 'Camera ● OFFLINE'}</span>
            </span>
            <span className="text-slate-300">|</span>
            <span className={`flex items-center gap-1 ${micStatus === 'CONNECTED' ? 'text-emerald-700 font-semibold' : 'text-rose-700 font-semibold'}`}>
              {micStatus === 'CONNECTED' ? <Mic className="w-3.5 h-3.5" /> : <MicOff className="w-3.5 h-3.5" />}
              <span>{micStatus === 'CONNECTED' ? 'Mic ● ON' : 'Mic ● OFFLINE'}</span>
            </span>
            <span className="text-slate-300">|</span>
            {/* Shield Status */}
            {confirmedViolationsCount >= 2 || (attemptData?.camera_required && cameraStatus !== 'CONNECTED') ? (
              <span className="flex items-center gap-1 text-rose-700 font-bold animate-pulse">
                <Shield className="w-3.5 h-3.5" />
                <span>Shield 🔴 ATTENTION</span>
              </span>
            ) : activeWarning || confirmedViolationsCount > 0 ? (
              <span className="flex items-center gap-1 text-amber-700 font-bold animate-pulse">
                <Shield className="w-3.5 h-3.5" />
                <span>Shield ⚠ WARNING</span>
              </span>
            ) : isProctoringActive ? (
              <span className="flex items-center gap-1 text-indigo-700 font-semibold">
                <Shield className="w-3.5 h-3.5" />
                <span>Shield ● ACTIVE</span>
              </span>
            ) : (
              <span className="flex items-center gap-1 text-amber-700 font-semibold">
                <Shield className="w-3.5 h-3.5" />
                <span>Shield ⚠ MONITORING DEGRADED</span>
              </span>
            )}
            <span className="text-slate-300">|</span>
            <span className={`font-bold ${confirmedViolationsCount >= 2 ? 'text-rose-800' : activeWarning || confirmedViolationsCount > 0 ? 'text-amber-800' : 'text-slate-700'}`}>
              Integrity {confirmedViolationsCount}/{attemptData?.max_confirmed_violations || 3}
            </span>
          </div>

          {/* Connection */}
          <div className="hidden lg:flex items-center gap-1 text-[11px] text-slate-500">
            {wsConnected ? (
              <span className="flex items-center gap-1 text-emerald-700 font-semibold">
                <Wifi className="w-3.5 h-3.5 text-emerald-600" />
                <span>Live</span>
              </span>
            ) : (
              <span className="flex items-center gap-1 text-amber-700 font-semibold">
                <WifiOff className="w-3.5 h-3.5 text-amber-600" />
                <span>Reconnecting</span>
              </span>
            )}
          </div>
        </div>

        {/* Submit Action */}
        <Button variant="primary" size="sm" onClick={() => setIsSubmitModalOpen(true)}>
          <Send className="w-3.5 h-3.5 mr-1.5" />
          <span>Finish & Submit</span>
        </Button>
      </header>

      {/* Persistent Top Warning Banner */}
      {activeWarning && (!isWarningFullscreen || !document.fullscreenElement) && (
        <div className="bg-amber-50 border-b border-amber-300 px-4 py-3 text-amber-950 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs animate-fadeIn">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-amber-200/80 text-amber-800 flex-shrink-0 mt-0.5">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <div className="font-bold text-sm text-amber-950 flex flex-wrap items-center gap-2">
                <span>{getWarningTitle(activeWarning.warning_type, (activeWarning as any).reason_code)}</span>
                <span className="px-2 py-0.5 rounded-full text-xs bg-amber-200 text-amber-900 font-mono font-bold border border-amber-300">
                  Integrity Warning: {confirmedViolationsCount} / {attemptData?.max_confirmed_violations || 3}
                </span>
              </div>
              <p className="text-xs text-amber-800 mt-0.5 font-sans leading-relaxed">
                {isWarningFullscreen
                  ? 'Your examination requires fullscreen mode. Choose how you want to proceed.'
                  : activeWarning.message}
              </p>
              {isWarningFullscreen && fullscreenActionError && (
                <p className="text-xs text-rose-700 font-semibold mt-1 flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5" />
                  {fullscreenActionError}
                </p>
              )}
              {!isWarningFullscreen && ackError && (
                <p className="text-xs text-rose-700 font-semibold mt-1 flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5" />
                  {ackError}
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 self-end sm:self-center flex-shrink-0">
            {isWarningFullscreen ? (
              <>
                <Button
                  variant="primary"
                  size="sm"
                  isLoading={isReenteringFullscreen}
                  onClick={handleReturnToFullscreen}
                >
                  Return to Fullscreen
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  className="bg-rose-50 hover:bg-rose-100 text-rose-700 border-rose-200"
                  onClick={() => {
                    setExitCountdownSeconds(10);
                    setIsExitCountdownActive(true);
                  }}
                >
                  Exit Examination
                </Button>
              </>
            ) : (
              <Button
                variant="secondary"
                size="sm"
                isLoading={isAcknowledging}
                className="bg-amber-100 hover:bg-amber-200 text-amber-950 border-amber-300 font-bold text-xs"
                onClick={handleAcknowledgeWarning}
              >
                {ackError ? 'Retry' : 'I Understand'}
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Camera Disconnected Warning Banner */}
      {cameraStatus === 'DISCONNECTED' && attemptData?.camera_required && !activeWarning && (
        <div className="bg-rose-50 border-b border-rose-300 px-4 py-3 text-rose-950 flex items-center justify-between gap-3 shadow-xs animate-fadeIn">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-rose-100 text-rose-700 flex-shrink-0">
              <CameraOff className="w-5 h-5" />
            </div>
            <div>
              <div className="font-bold text-sm text-rose-950">CAMERA CONNECTION LOST</div>
              <p className="text-xs text-rose-800 mt-0.5">
                Your webcam is not currently available. Please reconnect your video camera to continue the monitored examination.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Main Workspace: Left Sidebar & Question Canvas */}
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
        {/* Left Question Roster Sidebar (Light Theme) */}
        <aside className="w-full md:w-64 border-r border-slate-200 bg-white p-4 space-y-4 overflow-y-auto flex-shrink-0 shadow-xs">
          <div className="flex items-center justify-between text-xs font-mono text-slate-500">
            <span className="font-bold text-slate-700">Questions</span>
            <span className="text-emerald-700 font-bold">{answeredCount}/{questions.length} answered</span>
          </div>

          {/* Question Grid Pills */}
          <div className="grid grid-cols-5 md:grid-cols-4 gap-2 font-mono text-xs">
            {questions.map((q, idx) => {
              const isCurr = idx === currentQuestionIndex;
              const isAns = answers[q.snapshot_question_id]?.is_answered;

              return (
                <button
                  key={q.snapshot_question_id}
                  onClick={() => setCurrentQuestionIndex(idx)}
                  className={`h-9 rounded-lg font-bold transition-all border ${
                    isCurr
                      ? 'bg-emerald-600 text-white border-emerald-600 shadow-sm ring-2 ring-emerald-300'
                      : isAns
                      ? 'bg-emerald-50 text-emerald-800 border-emerald-300 hover:bg-emerald-100'
                      : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100 hover:border-slate-300'
                  }`}
                >
                  {idx + 1}
                </button>
              );
            })}
          </div>

          {/* Legend */}
          <div className="pt-4 border-t border-slate-100 space-y-2 text-[11px] font-mono text-slate-500">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded bg-emerald-50 border border-emerald-300" />
              <span>Answered</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded bg-slate-50 border border-slate-200" />
              <span>Unanswered</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded bg-emerald-600 border border-emerald-600" />
              <span>Current</span>
            </div>
          </div>
        </aside>

        {/* Center: Active Question Canvas (Light Theme) */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6 space-y-6 w-full bg-slate-50 select-none">
          {currentQuestion ? (
            <Card className="p-6 sm:p-8 space-y-6 border-slate-200 bg-white shadow-xs rounded-2xl select-none">
              {/* Question Header & Meta */}
              <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-slate-50 border border-slate-200 font-mono text-xs">
                <div className="flex items-center gap-2">
                  <Badge variant="info">{currentQuestion.question_type}</Badge>
                  <Badge
                    variant={
                      currentQuestion.difficulty === 'EASY'
                        ? 'success'
                        : currentQuestion.difficulty === 'MEDIUM'
                        ? 'warning'
                        : 'danger'
                    }
                  >
                    {currentQuestion.difficulty}
                  </Badge>
                </div>

                <div className="flex items-center gap-4 text-slate-700 font-semibold">
                  <span>Points: <strong className="text-emerald-700">{currentQuestion.points}</strong></span>
                  {currentQuestion.negative_marking_enabled && (
                    <span className="text-rose-600">Penalty: -{currentQuestion.negative_points}</span>
                  )}
                </div>
              </div>

              {/* Title & Prompt */}
              <div className="space-y-3">
                <h1 className="text-lg font-bold text-slate-900">{currentQuestion.title}</h1>
                <div className="text-sm text-slate-800 whitespace-pre-wrap leading-relaxed bg-slate-50 p-4 rounded-xl border border-slate-200">
                  {currentQuestion.coding_config?.problem_statement || currentQuestion.description}
                </div>

                {/* Additional coding problem details */}
                {currentQuestion.question_type === 'CODING' && currentQuestion.coding_config && (
                  <div className="space-y-3">
                    {(currentQuestion.coding_config.input_description || currentQuestion.coding_config.output_description) && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                        {currentQuestion.coding_config.input_description && (
                          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                            <span className="font-mono font-bold text-slate-600 block mb-1">Input Format:</span>
                            <p className="text-slate-700 font-sans">{currentQuestion.coding_config.input_description}</p>
                          </div>
                        )}
                        {currentQuestion.coding_config.output_description && (
                          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                            <span className="font-mono font-bold text-slate-600 block mb-1">Output Format:</span>
                            <p className="text-slate-700 font-sans">{currentQuestion.coding_config.output_description}</p>
                          </div>
                        )}
                      </div>
                    )}

                    {currentQuestion.coding_config.constraints && (
                      <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs font-mono">
                        <span className="font-bold text-slate-600 block mb-1 uppercase tracking-wider">Constraints:</span>
                        <pre className="text-slate-800 whitespace-pre-wrap font-mono">{currentQuestion.coding_config.constraints}</pre>
                      </div>
                    )}

                    {currentQuestion.coding_config.examples && currentQuestion.coding_config.examples.length > 0 && (
                      <div className="space-y-2 pt-1">
                        <span className="text-xs font-mono font-bold text-slate-600 uppercase tracking-wider block">
                          Examples:
                        </span>
                        <div className="space-y-2.5">
                          {currentQuestion.coding_config.examples.map((ex: any, idx: number) => (
                            <div key={idx} className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs font-mono space-y-1.5">
                              <span className="text-emerald-700 font-bold block">Example {idx + 1}:</span>
                              <div><span className="text-slate-500 font-semibold">Input: </span><code className="text-slate-800 bg-white border border-slate-200 px-1.5 py-0.5 rounded">{ex.input}</code></div>
                              <div><span className="text-slate-500 font-semibold">Output: </span><code className="text-emerald-700 bg-white border border-slate-200 px-1.5 py-0.5 rounded">{ex.output}</code></div>
                              {ex.explanation && (
                                <div className="text-slate-600 font-sans pt-0.5"><span className="font-semibold text-slate-500">Explanation: </span>{ex.explanation}</div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {currentQuestion.instructions && (
                  <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-start gap-2">
                    <HelpCircle className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                    <span><strong>Instructions:</strong> {currentQuestion.instructions}</span>
                  </div>
                )}
              </div>

              {/* Type-Specific Answer Inputs */}
              <div className="pt-2">
                {/* MCQ */}
                {currentQuestion.question_type === 'MCQ' && (
                  <div className="space-y-3 font-sans">
                    <label className="text-xs font-mono font-bold text-slate-600 uppercase tracking-wider block">
                      Select One Option:
                    </label>
                    <div className="space-y-2.5">
                      {(currentQuestion.type_config?.options || []).map((opt: any) => {
                        const isSelected = (currentAnswer?.selected_options || []).includes(opt.id);
                        return (
                          <label
                            key={opt.id}
                            className={`flex items-center gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all ${
                              isSelected
                                ? 'bg-emerald-50/80 border-emerald-500 text-emerald-950 font-semibold shadow-xs'
                                : 'bg-white border-slate-200 text-slate-800 hover:border-slate-300 hover:bg-slate-50'
                            }`}
                          >
                            <input
                              type="radio"
                              name={`mcq_${currentQuestion.snapshot_question_id}`}
                              checked={isSelected}
                              onChange={() =>
                                triggerAutosave(currentQuestion.snapshot_question_id, {
                                  selected_options: [opt.id],
                                })
                              }
                              className="text-emerald-600 focus:ring-emerald-500 h-4 w-4 bg-white border-slate-300"
                            />
                            <span className="font-mono font-bold text-emerald-700 w-5">{opt.id}.</span>
                            <span className="text-sm">{opt.text}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Multi-Select */}
                {currentQuestion.question_type === 'MULTI_SELECT' && (
                  <div className="space-y-3 font-sans">
                    <label className="text-xs font-mono font-bold text-slate-600 uppercase tracking-wider block">
                      Select All Correct Options:
                    </label>
                    <div className="space-y-2.5">
                      {(currentQuestion.type_config?.options || []).map((opt: any) => {
                        const selectedList = currentAnswer?.selected_options || [];
                        const isChecked = selectedList.includes(opt.id);
                        return (
                          <label
                            key={opt.id}
                            className={`flex items-center gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all ${
                              isChecked
                                ? 'bg-emerald-50/80 border-emerald-500 text-emerald-950 font-semibold shadow-xs'
                                : 'bg-white border-slate-200 text-slate-800 hover:border-slate-300 hover:bg-slate-50'
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={(e) => {
                                const nextList = e.target.checked
                                  ? [...selectedList, opt.id]
                                  : selectedList.filter((id: string) => id !== opt.id);
                                triggerAutosave(currentQuestion.snapshot_question_id, {
                                  selected_options: nextList,
                                });
                              }}
                              className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4 bg-white border-slate-300"
                            />
                            <span className="font-mono font-bold text-emerald-700 w-5">{opt.id}.</span>
                            <span className="text-sm">{opt.text}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* True / False */}
                {currentQuestion.question_type === 'TRUE_FALSE' && (
                  <div className="space-y-3 font-mono">
                    <label className="text-xs font-bold text-slate-600 uppercase tracking-wider block">
                      Select Answer:
                    </label>
                    <div className="grid grid-cols-2 gap-4">
                      <button
                        type="button"
                        onClick={() =>
                          triggerAutosave(currentQuestion.snapshot_question_id, {
                            selected_options: ['True'],
                          })
                        }
                        className={`p-4 rounded-xl border-2 font-bold text-sm transition-all flex items-center justify-center gap-2 ${
                          (currentAnswer?.selected_options || []).includes('True')
                            ? 'bg-emerald-50 border-emerald-500 text-emerald-800 shadow-sm'
                            : 'bg-white border-slate-200 text-slate-700 hover:border-slate-300 hover:bg-slate-50'
                        }`}
                      >
                        <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                        TRUE
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          triggerAutosave(currentQuestion.snapshot_question_id, {
                            selected_options: ['False'],
                          })
                        }
                        className={`p-4 rounded-xl border-2 font-bold text-sm transition-all flex items-center justify-center gap-2 ${
                          (currentAnswer?.selected_options || []).includes('False')
                            ? 'bg-rose-50 border-rose-500 text-rose-800 shadow-sm'
                            : 'bg-white border-slate-200 text-slate-700 hover:border-slate-300 hover:bg-slate-50'
                        }`}
                      >
                        <XCircle className="w-5 h-5 text-rose-600" />
                        FALSE
                      </button>
                    </div>
                  </div>
                )}

                {/* Short Answer */}
                {currentQuestion.question_type === 'SHORT_ANSWER' && (
                  <div className="space-y-3 font-mono">
                    <label className="text-xs font-bold text-slate-600 uppercase tracking-wider block">
                      Your Text Response:
                    </label>
                    <input
                      type="text"
                      value={currentAnswer?.text_response || ''}
                      onChange={(e) =>
                        triggerAutosave(currentQuestion.snapshot_question_id, {
                          text_response: e.target.value,
                        })
                      }
                      onCopy={(e) => e.preventDefault()}
                      onCut={(e) => e.preventDefault()}
                      onPaste={(e) => e.preventDefault()}
                      onContextMenu={(e) => e.preventDefault()}
                      placeholder="Type your exact response here..."
                      className="w-full px-4 py-3 rounded-xl bg-white border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                    />
                  </div>
                )}

                {/* Coding Problem with Monaco Editor */}
                {currentQuestion.question_type === 'CODING' && currentQuestion.coding_config && (() => {
                  const codingConfig = currentQuestion.coding_config;
                  return (
                    <div className="space-y-4">
                      {/* Language Selection & Limits */}
                      <div className="flex flex-wrap items-center justify-between gap-3 text-xs font-mono text-slate-600 p-3 rounded-xl bg-slate-50 border border-slate-200">
                        <div className="flex items-center gap-3">
                          <Code2 className="w-4 h-4 text-emerald-700" />
                          <span>Language:</span>
                          <select
                            value={currentAnswer?.code_language || codingConfig.allowed_languages?.[0] || 'PYTHON'}
                            onChange={(e) => {
                              const nextLang = e.target.value;
                              const nextStarter = codingConfig.starter_codes?.[nextLang] || '';
                              const currentVal = currentAnswer?.code_response || '';
                              const isStarterOrEmpty = !currentVal || (codingConfig.starter_codes && Object.values(codingConfig.starter_codes).includes(currentVal));
                              triggerAutosave(currentQuestion.snapshot_question_id, {
                                code_language: nextLang,
                                code_response: isStarterOrEmpty ? nextStarter : currentVal,
                              });
                            }}
                            className="px-2.5 py-1 rounded-lg bg-white border border-slate-300 text-slate-900 font-bold focus:ring-2 focus:ring-emerald-500"
                          >
                            {(codingConfig.allowed_languages || ['PYTHON', 'CPP', 'JAVA', 'C']).map((lang) => (
                              <option key={lang} value={lang}>
                                {lang === 'C' ? 'C' : lang === 'CPP' ? 'C++' : lang === 'JAVA' ? 'Java' : 'Python'}
                              </option>
                            ))}
                          </select>
                        </div>

                        <div className="flex items-center gap-4 text-[11px] text-slate-500">
                          <span>Limit: <strong>{codingConfig.time_limit_ms}ms</strong></span>
                          <span>Mem: <strong>{codingConfig.memory_limit_mb}MB</strong></span>
                        </div>
                      </div>

                      {/* Monaco Code Editor */}
                      <div className="border border-slate-300 rounded-xl overflow-hidden shadow-xs">
                        <div className="bg-slate-100 px-4 py-2 border-b border-slate-200 text-xs font-mono text-slate-600 flex items-center justify-between">
                          <span>Solution Editor</span>
                          <span className="text-[10px] text-slate-500">Draft saved automatically</span>
                        </div>
                        {(() => {
                          const activeLang = currentAnswer?.code_language || codingConfig.allowed_languages?.[0] || 'PYTHON';
                          const starterCode = codingConfig.starter_codes?.[activeLang] || codingConfig.starter_codes?.['PYTHON'] || '';
                          const currentEditorValue = (currentAnswer?.code_response !== undefined && currentAnswer?.code_response !== null && currentAnswer.code_response !== '')
                            ? currentAnswer.code_response
                            : starterCode;

                          return (
                            <Editor
                              height="320px"
                              language={
                                activeLang.toLowerCase() === 'cpp'
                                  ? 'cpp'
                                  : activeLang.toLowerCase() === 'java'
                                  ? 'java'
                                  : activeLang.toLowerCase() === 'c'
                                  ? 'c'
                                  : 'python'
                              }
                              theme="vs-light"
                              value={currentEditorValue}
                              onMount={(editor, monaco) => {
                                (window as any).monacoEditor = editor;
                                (window as any).monaco = monaco;

                                // Prevent Monaco Editor internal copy / cut / paste commands
                                try {
                                  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyC, () => {});
                                  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyV, () => {});
                                  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyX, () => {});

                                  const domNode = editor.getDomNode();
                                  if (domNode) {
                                    domNode.addEventListener('copy', (e: Event) => { e.preventDefault(); e.stopPropagation(); }, true);
                                    domNode.addEventListener('cut', (e: Event) => { e.preventDefault(); e.stopPropagation(); }, true);
                                    domNode.addEventListener('paste', (e: Event) => { e.preventDefault(); e.stopPropagation(); }, true);
                                    domNode.addEventListener('contextmenu', (e: Event) => { e.preventDefault(); e.stopPropagation(); }, true);
                                  }

                                  editor.onKeyDown((e: any) => {
                                    if (
                                      (e.ctrlKey || e.metaKey) &&
                                      (e.keyCode === monaco.KeyCode.KeyC || e.keyCode === monaco.KeyCode.KeyV || e.keyCode === monaco.KeyCode.KeyX)
                                    ) {
                                      e.preventDefault();
                                      e.stopPropagation();
                                    }
                                  });
                                } catch {}
                              }}
                              onChange={(val) =>
                                triggerAutosave(currentQuestion.snapshot_question_id, {
                                  code_response: val || '',
                                  code_language: activeLang,
                                })
                              }
                              options={{
                                minimap: { enabled: false },
                                fontSize: 13,
                                lineNumbers: 'on',
                                scrollBeyondLastLine: false,
                                contextmenu: false,
                                copyWithSyntaxHighlighting: false,
                              }}
                            />
                          );
                        })()}
                      </div>

                      {/* Execution Action Bar */}
                      <div className="flex items-center justify-between gap-3 p-3.5 bg-slate-50 border border-slate-200 rounded-xl">
                        <div className="text-xs font-mono text-slate-600">
                          {executingQuestionId === currentQuestion.snapshot_question_id ? (
                            <span className="text-amber-700 flex items-center gap-2 font-semibold">
                              <span className="inline-block w-2 h-2 rounded-full bg-amber-500 animate-pulse"></span>
                              {executionMode === 'RUN' ? 'Executing against sample test cases...' : 'Evaluating authoritative hidden tests...'}
                            </span>
                          ) : executionError[currentQuestion.snapshot_question_id] ? (
                            <span className="text-rose-700 font-semibold">{executionError[currentQuestion.snapshot_question_id]}</span>
                          ) : (
                            <span>Ready to execute against sample tests or submit solution.</span>
                          )}
                        </div>

                        <div className="flex items-center gap-3">
                          <Button
                            variant="secondary"
                            size="sm"
                            disabled={executingQuestionId !== null}
                            onClick={() => handleRunCode(currentQuestion.snapshot_question_id)}
                          >
                            <Play className="w-3.5 h-3.5 mr-1 text-emerald-700" />
                            {executingQuestionId === currentQuestion.snapshot_question_id && executionMode === 'RUN'
                              ? 'Running...'
                              : 'Run Code (Sample Tests)'}
                          </Button>

                          <Button
                            variant="primary"
                            size="sm"
                            disabled={executingQuestionId !== null}
                            onClick={() => handleSubmitCode(currentQuestion.snapshot_question_id)}
                          >
                            <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                            {executingQuestionId === currentQuestion.snapshot_question_id && executionMode === 'SUBMIT'
                              ? 'Submitting...'
                              : 'Submit Solution'}
                          </Button>
                        </div>
                      </div>

                      {/* Live Execution Results Console */}
                      {submissionResults[currentQuestion.snapshot_question_id] && (
                        <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3 font-mono text-xs shadow-xs">
                          <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-slate-800">
                                {submissionResults[currentQuestion.snapshot_question_id]?.submission_type === 'RUN' ? 'Sample Test Run Output' : 'Authoritative Evaluation'}:
                              </span>
                              <Badge
                                variant={
                                  submissionResults[currentQuestion.snapshot_question_id]?.verdict === 'ACCEPTED'
                                    ? 'success'
                                    : submissionResults[currentQuestion.snapshot_question_id]?.verdict === 'COMPILATION_ERROR'
                                    ? 'danger'
                                    : 'warning'
                                }
                              >
                                {submissionResults[currentQuestion.snapshot_question_id]?.verdict || 'COMPLETED'}
                              </Badge>
                            </div>

                            <div className="flex items-center gap-4 text-slate-600 text-[11px]">
                              <span>
                                Passed: <strong className="text-emerald-700">{submissionResults[currentQuestion.snapshot_question_id]?.passed_test_cases}</strong> / {submissionResults[currentQuestion.snapshot_question_id]?.total_test_cases}
                              </span>
                              {submissionResults[currentQuestion.snapshot_question_id]?.submission_type === 'SUBMIT' && (
                                <span>
                                  Score: <strong className="text-emerald-700">{submissionResults[currentQuestion.snapshot_question_id]?.score_awarded}</strong> / {submissionResults[currentQuestion.snapshot_question_id]?.max_score}
                                </span>
                              )}
                              <span>Time: {submissionResults[currentQuestion.snapshot_question_id]?.execution_time_ms}ms</span>
                              <span>Mem: {submissionResults[currentQuestion.snapshot_question_id]?.memory_used_kb}KB</span>
                            </div>
                          </div>

                          {/* Compilation Error Display */}
                          {submissionResults[currentQuestion.snapshot_question_id]?.compilation_error && (
                            <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-800 space-y-1">
                              <span className="font-bold block text-rose-900">Compilation / Syntax Error:</span>
                              <pre className="text-[11px] overflow-x-auto whitespace-pre-wrap font-mono">{submissionResults[currentQuestion.snapshot_question_id]?.compilation_error}</pre>
                            </div>
                          )}

                          {/* Test Cases Tab / List */}
                          {submissionResults[currentQuestion.snapshot_question_id]?.test_cases && (
                            <div className="space-y-2">
                              <div className="flex flex-wrap gap-2">
                                {submissionResults[currentQuestion.snapshot_question_id]?.test_cases.map((tc, idx) => (
                                  <button
                                    key={idx}
                                    type="button"
                                    onClick={() => setActiveTestCaseTabs((prev) => ({ ...prev, [currentQuestion.snapshot_question_id]: idx }))}
                                    className={`px-3 py-1.5 rounded-lg font-bold text-[11px] transition-all flex items-center gap-1.5 border ${
                                      (activeTestCaseTabs[currentQuestion.snapshot_question_id] || 0) === idx
                                        ? 'bg-white border-emerald-600 text-emerald-800 shadow-xs'
                                        : 'bg-slate-100 border-slate-200 text-slate-600 hover:bg-slate-200/60'
                                    }`}
                                  >
                                    <span className={`w-2 h-2 rounded-full ${tc.verdict === 'PASSED' ? 'bg-emerald-500' : 'bg-rose-500'}`}></span>
                                    {tc.is_hidden ? `Hidden Case #${tc.index}` : `Case #${tc.index}`}
                                  </button>
                                ))}
                              </div>

                              {/* Active Tab Details */}
                              {(() => {
                                const activeIdx = activeTestCaseTabs[currentQuestion.snapshot_question_id] || 0;
                                const tc = submissionResults[currentQuestion.snapshot_question_id]?.test_cases[activeIdx];
                                if (!tc) return null;

                                return (
                                  <div className="p-3 bg-white border border-slate-200 rounded-lg space-y-2">
                                    <div className="flex items-center justify-between text-[11px]">
                                      <span className="text-slate-700">
                                        Status: <strong className={tc.verdict === 'PASSED' ? 'text-emerald-700' : 'text-rose-700'}>{tc.verdict}</strong>
                                        {tc.is_hidden ? ' (Authoritative Evaluation Test)' : ''}
                                      </span>
                                      <span className="text-slate-500">
                                        Points: {tc.points_awarded} / {tc.max_points} | Exec: {tc.execution_time_ms}ms | Mem: {tc.memory_used_kb}KB
                                      </span>
                                    </div>

                                    {!tc.is_hidden ? (
                                      <div className="grid grid-cols-2 gap-3 text-[11px]">
                                        <div>
                                          <span className="text-slate-500 block text-[10px]">Input (stdin):</span>
                                          <pre className="p-2 rounded bg-slate-50 border border-slate-200 text-slate-800 overflow-x-auto">{tc.input || '(empty)'}</pre>
                                        </div>
                                        <div>
                                          <span className="text-slate-500 block text-[10px]">Expected Output:</span>
                                          <pre className="p-2 rounded bg-slate-50 border border-slate-200 text-slate-800 overflow-x-auto">{tc.expected_output}</pre>
                                        </div>
                                        <div className="col-span-2">
                                          <span className="text-slate-500 block text-[10px]">Your Output (stdout):</span>
                                          <pre className={`p-2 rounded border overflow-x-auto ${tc.verdict === 'PASSED' ? 'bg-emerald-50 border-emerald-200 text-emerald-900' : 'bg-rose-50 border-rose-200 text-rose-900'}`}>
                                            {tc.actual_output || '(no output)'}
                                          </pre>
                                        </div>
                                      </div>
                                    ) : (
                                      <div className="p-3 bg-slate-50 rounded border border-slate-200 text-slate-600 text-[11px]">
                                        🔒 <em>Hidden test case inputs and expected outputs are protected for examination security.</em>
                                      </div>
                                    )}
                                  </div>
                                );
                              })()}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Example Public Test Cases */}
                      {codingConfig.public_test_cases && codingConfig.public_test_cases.length > 0 && (
                        <div className="space-y-2 pt-2">
                          <h4 className="text-xs font-mono font-bold text-slate-600 uppercase tracking-wider">
                            Sample Public Test Cases
                          </h4>
                          <div className="space-y-2">
                            {codingConfig.public_test_cases.map((tc, idx) => (
                              <div key={idx} className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs font-mono space-y-1.5">
                                <span className="text-slate-600 font-bold block">Sample Case #{idx + 1} ({tc.points} pts)</span>
                                <div className="grid grid-cols-2 gap-2">
                                  <div>
                                    <span className="text-slate-500 block text-[10px]">stdin:</span>
                                    <pre className="p-2 rounded bg-white border border-slate-200 text-slate-800 overflow-x-auto">{tc.input_data || '(empty)'}</pre>
                                  </div>
                                  <div>
                                    <span className="text-slate-500 block text-[10px]">expected stdout:</span>
                                    <pre className="p-2 rounded bg-white border border-slate-200 text-slate-800 overflow-x-auto">{tc.expected_output}</pre>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}

                {/* SQL Query Editor */}
                {currentQuestion.question_type === 'SQL' && currentQuestion.sql_config && (
                  <div className="space-y-4">
                    <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs font-mono space-y-2">
                      <span className="text-slate-700 font-bold block uppercase tracking-wider">Database Tables & Schema</span>
                      <pre className="p-3 rounded-lg bg-white text-slate-900 font-mono text-xs overflow-x-auto border border-slate-200">
                        {currentQuestion.sql_config.schema_setup_sql}
                      </pre>
                    </div>

                    <div className="space-y-2 font-mono text-xs">
                      <label className="text-slate-700 font-bold block uppercase tracking-wider">Your SQL Query:</label>
                      <textarea
                        rows={6}
                        value={currentAnswer?.sql_response || ''}
                        onChange={(e) =>
                          triggerAutosave(currentQuestion.snapshot_question_id, {
                            sql_response: e.target.value,
                          })
                        }
                        onCopy={(e) => e.preventDefault()}
                        onCut={(e) => e.preventDefault()}
                        onPaste={(e) => e.preventDefault()}
                        onContextMenu={(e) => e.preventDefault()}
                        placeholder="SELECT * FROM table_name..."
                        className="w-full p-3 rounded-xl bg-white border border-slate-300 text-slate-900 font-mono text-xs focus:ring-2 focus:ring-emerald-500"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Bottom Question Navigation */}
              <div className="flex items-center justify-between pt-6 border-t border-slate-100">
                <Button
                  variant="secondary"
                  size="md"
                  disabled={currentQuestionIndex === 0}
                  onClick={() => setCurrentQuestionIndex((prev) => Math.max(0, prev - 1))}
                >
                  <ChevronLeft className="w-4 h-4 mr-1" />
                  <span>Previous Question</span>
                </Button>

                {currentQuestionIndex === questions.length - 1 ? (
                  <Button
                    variant="primary"
                    size="md"
                    onClick={() => setIsSubmitModalOpen(true)}
                  >
                    <Send className="w-4 h-4 mr-1.5" />
                    <span>Finish & Submit</span>
                  </Button>
                ) : (
                  <Button
                    variant="primary"
                    size="md"
                    onClick={() => setCurrentQuestionIndex((prev) => Math.min(questions.length - 1, prev + 1))}
                  >
                    <span>Next Question</span>
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                )}
              </div>
            </Card>
          ) : null}
        </main>
      </div>

      {/* Final Submit Confirmation Modal (Light Theme) */}
      {isSubmitModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto animate-fadeIn">
          <Card className="max-w-md w-full p-6 space-y-5 border-slate-200 bg-white shadow-2xl relative">
            <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
              <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200">
                <Send className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-slate-900">Finish & Submit Examination</h3>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              Are you sure you want to finish and submit your examination? Once submitted, your answers will be permanently finalized for grading.
            </p>

            {submitErrorMessage && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
                <span>{submitErrorMessage}</span>
              </div>
            )}

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs font-mono space-y-2">
              <div className="flex justify-between">
                <span className="text-slate-500">Total Questions:</span>
                <span className="text-slate-900 font-bold">{questions.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Answered Questions:</span>
                <span className="text-emerald-700 font-bold">{answeredCount}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Unanswered Questions:</span>
                <span className="text-amber-700 font-bold">{questions.length - answeredCount}</span>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
              <Button variant="secondary" size="sm" onClick={() => setIsSubmitModalOpen(false)}>
                Continue Examination
              </Button>
              <Button
                variant="primary"
                size="sm"
                isLoading={isSubmitting}
                onClick={handleSubmit}
              >
                Yes, Final Submit
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Hidden Canvas for Video Sampling */}
      <canvas ref={canvasRef} style={{ display: 'none' }} />

      {/* Floating Live Camera Feed */}
      <div className="fixed bottom-4 right-4 z-30 shadow-xl rounded-2xl overflow-hidden border border-slate-300 bg-white w-36 h-28 flex flex-col items-center justify-center">
        <video
          ref={(el) => {
            videoRef.current = el;
            if (el && mediaStreamRef.current && el.srcObject !== mediaStreamRef.current) {
              el.srcObject = mediaStreamRef.current;
            }
          }}
          autoPlay
          playsInline
          muted
          style={{ transform: 'scaleX(-1)' }}
          className={`w-full h-full object-cover -scale-x-100 ${cameraStatus === 'CONNECTED' ? 'block' : 'hidden'}`}
        />
        {cameraStatus !== 'CONNECTED' && (
          <div className="flex flex-col items-center gap-1 p-2 text-center">
            <CameraOff className="w-5 h-5 text-rose-600" />
            <span className="text-[10px] font-semibold text-slate-700">Camera Offline</span>
          </div>
        )}
        <div className="absolute top-1.5 left-1.5 flex items-center gap-1 bg-white/90 backdrop-blur-xs border border-slate-200 px-2 py-0.5 rounded-full text-[9px] font-mono text-slate-700 shadow-xs">
          <span className={`w-1.5 h-1.5 rounded-full ${cameraStatus === 'CONNECTED' ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
          {cameraStatus === 'CONNECTED' ? 'Cam Active' : 'Cam Off'}
        </div>
      </div>

      {/* Frosted Pause Overlay (Light Theme) */}
      {isAttemptPaused && (
        <div className="fixed inset-0 z-40 flex flex-col items-center justify-center bg-slate-900/60 backdrop-blur-md">
          <div className="p-8 max-w-md w-full bg-white border border-slate-200 rounded-2xl shadow-2xl text-center space-y-4">
            <div className="w-16 h-16 mx-auto rounded-full bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-600">
              <Pause className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-bold text-slate-900">Examination Paused</h2>
            <p className="text-xs text-slate-600 leading-relaxed">
              {pauseReason || 'Your examination attempt has been temporarily paused by an invigilator. Countdown timer is suspended.'}
            </p>
            <div className="p-3 bg-slate-50 rounded-lg text-xs text-slate-600 border border-slate-200">
              Please remain at your desk. The examination will resume shortly.
            </div>
          </div>
        </div>
      )}

      {/* Room Scan Modal (Light Theme) */}
      {isRoomScanModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <Card className="max-w-md w-full p-6 space-y-5 border-slate-200 bg-white shadow-2xl">
            <div className="flex items-center gap-3 border-b border-slate-100 pb-3">
              <div className="p-2 rounded-xl bg-indigo-50 text-indigo-700 border border-indigo-200">
                <Camera className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">Room Scan Requested</h3>
                <span className="text-[11px] text-slate-500">Proctor Environment Verification</span>
              </div>
            </div>
            <p className="text-xs text-slate-700 leading-relaxed">{roomScanInstructions}</p>
            <p className="text-[11px] text-slate-500">
              Slowly rotate your webcam 360 degrees around your workspace, ensuring your desk and surroundings are clearly visible.
            </p>
            <div className="flex justify-end pt-2 border-t border-slate-100">
              <Button variant="primary" size="sm" onClick={handleCompleteRoomScan}>
                I Have Completed the Scan
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Fullscreen Exit Warning Modal */}
      {integrityLock === 'FULLSCREEN_EXIT' && !isTerminatedModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-sm animate-fadeIn">
          <Card className="max-w-md w-full p-6 space-y-5 border-amber-300 bg-white shadow-2xl text-center">
            <div className="w-14 h-14 mx-auto rounded-2xl bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-600">
              <AlertTriangle className="w-8 h-8 text-amber-600 animate-pulse" />
            </div>
            <div className="space-y-2">
              <div className="inline-block px-2.5 py-1 bg-amber-100 text-amber-700 text-xs font-bold uppercase tracking-wider rounded-md border border-amber-200">
                Fullscreen Required
              </div>
              <h3 className="text-lg font-black text-slate-900 tracking-tight">
                FULLSCREEN MODE EXITED
              </h3>
              <p className="text-xs font-semibold text-amber-700 leading-relaxed">
                Your examination requires fullscreen mode. Choose how you want to proceed.
              </p>
              <p className="text-xs text-slate-600 leading-relaxed">
                Exiting fullscreen is a security violation. Click below to return to fullscreen and resume your examination.
              </p>
            </div>
            <div className="flex flex-col gap-2 pt-2">
              <Button
                variant="primary"
                size="lg"
                className="w-full font-bold shadow-md"
                onClick={() => {
                  const req = document.documentElement.requestFullscreen || (document.documentElement as any).webkitRequestFullscreen;
                  if (req) {
                    req.call(document.documentElement).catch((err: any) => {
                      console.warn('Return to fullscreen failed:', err);
                    });
                  }
                }}
              >
                Return to Fullscreen
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Non-Dismissible 2-Minute Focus-Loss / Tab-Switch / Window-Switch Termination Warning Modal */}
      {((integrityLock && integrityLock !== 'FULLSCREEN_EXIT') || (pendingTermination?.pending)) && !isTerminatedModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-sm animate-fadeIn">
          <Card className="max-w-md w-full p-6 space-y-5 border-rose-300 bg-white shadow-2xl text-center">
            <div className="w-14 h-14 mx-auto rounded-2xl bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600">
              <AlertTriangle className="w-8 h-8 text-rose-600 animate-pulse" />
            </div>

            <div className="space-y-2">
              <div className="inline-block px-2.5 py-1 bg-rose-100 text-rose-700 text-xs font-bold uppercase tracking-wider rounded-md border border-rose-200">
                Security Breach Detected
              </div>
              <h3 className="text-lg font-black text-slate-900 tracking-tight">
                EXAMINATION TERMINATION WARNING
              </h3>
              <p className="text-xs font-semibold text-rose-700 leading-relaxed">
                {integrityLock === 'TAB_SWITCH' && 'You switched away to another browser tab.'}
                {integrityLock === 'WINDOW_SWITCH' && 'You switched away from the examination window/application.'}
                {integrityLock === 'UNAUTHORIZED_EXIT' && 'Unauthorized browser navigation detected.'}
                {!integrityLock && 'You switched away from the examination window/tab.'}
              </p>
              <p className="text-xs text-slate-600 leading-relaxed">
                Your examination is now <strong>PENDING TERMINATION</strong>. An authorized proctor has been alerted. Returning to this window does not dismiss this warning. Only an authorized proctor can cancel termination.
              </p>
            </div>

            {/* Continuous Live Countdown Clock */}
            <div className="p-4 bg-rose-50 rounded-2xl border border-rose-200 flex flex-col items-center justify-center gap-1">
              <div className="text-4xl font-black font-mono text-rose-700 tracking-wider">
                {formatTime(integrityCountdown)}
              </div>
              <span className="text-xs font-semibold text-rose-600">
                Time remaining before permanent automatic cancellation
              </span>
            </div>

            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-[11px] text-slate-600 text-left space-y-1">
              <div>
                • <strong>Incident Detected:</strong>{' '}
                {integrityLock === 'TAB_SWITCH' && 'Tab Switch (visibilitychange: hidden)'}
                {integrityLock === 'WINDOW_SWITCH' && 'Window Focus Lost (window.blur)'}
                {integrityLock === 'UNAUTHORIZED_EXIT' && 'Browser Back Navigation (popstate)'}
                {!integrityLock && (pendingTermination?.reason || 'Exam window lost focus')}
              </div>
              <div>• <strong>Policy:</strong> 2-minute grace period before permanent cancellation</div>
              <div>• <strong>Status:</strong> Waiting for proctor intervention...</div>
            </div>

            <p className="text-[11px] text-slate-400 italic">
              Do not close this window. If an authorized proctor cancels this termination, your examination will resume automatically.
            </p>
          </Card>
        </div>
      )}

      {/* Termination Notice Modal (Light Theme) */}
      {isTerminatedModalOpen && terminationInfo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/80 backdrop-blur-sm">
          <Card className="max-w-md w-full p-6 space-y-5 border-rose-300 bg-white shadow-2xl">
            <div className="flex items-center gap-3 border-b border-slate-100 pb-3">
              <div className="p-2 rounded-xl bg-rose-50 text-rose-600 border border-rose-200">
                <XCircle className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-rose-700">Examination Terminated</h3>
                <span className="text-[11px] text-slate-500">Disqualification Notice</span>
              </div>
            </div>
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 space-y-2 text-xs text-rose-900 leading-relaxed">
              <div><strong>Reason Code:</strong> {terminationInfo.reason}</div>
              <div><strong>Official Justification:</strong> {terminationInfo.justification}</div>
            </div>
            <p className="text-[11px] text-slate-500">
              This attempt has been cancelled and submitted for academic review. You can safely close this window.
            </p>
            <div className="flex justify-end pt-2 border-t border-slate-100">
              <Button variant="primary" size="sm" onClick={() => navigate('/student/assessments')}>
                Return to Assessments
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* 10-Second Voluntary Termination Countdown Modal */}
      {isExitCountdownActive && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 backdrop-blur-xs p-4 animate-fadeIn">
          <Card className="max-w-md w-full p-6 space-y-5 border-rose-200 bg-white shadow-2xl text-center">
            <div className="w-14 h-14 mx-auto rounded-2xl bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600">
              <AlertTriangle className="w-8 h-8 text-rose-600 animate-pulse" />
            </div>
            <div className="space-y-2">
              <h3 className="text-lg font-bold text-slate-900">Exit Examination?</h3>
              <p className="text-xs text-rose-700 font-semibold leading-relaxed">
                Your examination will be permanently terminated.
              </p>
              <p className="text-xs text-slate-500 leading-relaxed">
                Once terminated, your answers are submitted as-is and you cannot re-enter or resume this attempt.
              </p>
            </div>
            <div className="p-4 bg-rose-50/80 rounded-2xl border border-rose-200 flex flex-col items-center justify-center gap-1">
              <div className="text-3xl font-black font-mono text-rose-700">
                {exitCountdownSeconds}s
              </div>
              <span className="text-xs font-semibold text-rose-600">
                {exitCountdownSeconds} second{exitCountdownSeconds === 1 ? '' : 's'} remaining
              </span>
            </div>
            <div className="flex flex-col gap-2 pt-2">
              <Button
                variant="primary"
                size="md"
                className="w-full font-bold"
                onClick={handleCancelExitAndReturnToFullscreen}
              >
                Cancel &amp; Return to Fullscreen
              </Button>
              <Button
                variant="danger"
                size="sm"
                className="w-full font-medium text-xs text-rose-700 bg-rose-50 hover:bg-rose-100 border-rose-200"
                onClick={handleExecuteTermination}
              >
                Terminate Immediately
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Pre-Exam Entry & Fullscreen Readiness Verification Modal */}
      {attemptData && !isExamActive && !isTerminatedModalOpen && !integrityLock && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <Card className="max-w-md w-full p-6 space-y-5 border-slate-200 bg-white shadow-2xl text-center">
            {attemptData.camera_required ? (
              <>
                <div className="flex flex-col items-center gap-2">
                  <div className="p-3 rounded-2xl bg-indigo-50 text-indigo-700 border border-indigo-200">
                    <Camera className="w-8 h-8" />
                  </div>
                  <h3 className="text-lg font-bold text-slate-900">Camera Verification Required</h3>
                  <p className="text-xs text-slate-600 max-w-sm leading-relaxed">
                    This examination requires continuous webcam proctoring. Please grant camera access and ensure your face is clearly visible inside the frame.
                  </p>
                </div>

                {/* Live Preview Box */}
                <div className="relative aspect-video w-full rounded-2xl overflow-hidden bg-slate-100 border border-slate-200 flex items-center justify-center">
                  {cameraStatus === 'CONNECTED' ? (
                    <>
                      <video
                        ref={(el) => {
                          if (el && mediaStreamRef.current && el.srcObject !== mediaStreamRef.current) {
                            el.srcObject = mediaStreamRef.current;
                          }
                        }}
                        autoPlay
                        playsInline
                        muted
                        style={{ transform: 'scaleX(-1)' }}
                        className="w-full h-full object-cover -scale-x-100"
                      />
                      <div className="absolute inset-4 border-2 border-dashed border-indigo-400/60 rounded-xl pointer-events-none flex items-center justify-center">
                        <span className="text-[10px] font-mono text-indigo-700 bg-white/90 px-2 py-0.5 rounded shadow-xs">
                          Center face in frame
                        </span>
                      </div>
                      <div className="absolute top-2 left-2 flex items-center gap-1.5 bg-emerald-50 border border-emerald-200 text-emerald-700 px-2.5 py-1 rounded-full text-[10px] font-semibold shadow-xs">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                        Webcam Active
                      </div>
                    </>
                  ) : (
                    <div className="flex flex-col items-center gap-2 p-6 text-center">
                      <CameraOff className="w-8 h-8 text-amber-600" />
                      <span className="text-xs font-semibold text-slate-800">
                        {cameraStatus === 'DENIED' ? 'Camera Permission Denied' : 'Connecting to Camera...'}
                      </span>
                      <p className="text-[11px] text-slate-500">
                        {cameraStatus === 'DENIED'
                          ? 'Please allow camera access in your browser settings to proceed.'
                          : 'Please grant browser permission when prompted.'}
                      </p>
                    </div>
                  )}
                </div>

                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-left space-y-1.5 text-xs text-slate-700">
                  <div className="font-semibold text-slate-900">Exam Integrity Checklist:</div>
                  <ul className="list-disc list-inside text-[11px] text-slate-600 space-y-1">
                    <li>Remain centered and directly facing the screen.</li>
                    <li>Ensure a quiet, well-lit workspace without other people.</li>
                    <li>Mobile phones, second monitors, and tab switching are prohibited.</li>
                  </ul>
                </div>

                <Button
                  variant="primary"
                  size="lg"
                  className="w-full font-bold"
                  disabled={cameraStatus !== 'CONNECTED'}
                  onClick={handleEnterExamination}
                >
                  {cameraStatus === 'CONNECTED' ? 'Camera Ready — Enter Examination' : 'Awaiting Camera Access...'}
                </Button>
              </>
            ) : (
              <>
                <div className="flex flex-col items-center gap-2">
                  <div className="p-3 rounded-2xl bg-indigo-50 text-indigo-700 border border-indigo-200">
                    <Shield className="w-8 h-8" />
                  </div>
                  <h3 className="text-lg font-bold text-slate-900">Enter Examination</h3>
                  <p className="text-xs text-slate-600 max-w-sm leading-relaxed">
                    This examination must be completed in fullscreen mode. Click below to enter fullscreen and begin.
                  </p>
                </div>
                <Button
                  variant="primary"
                  size="lg"
                  className="w-full font-bold"
                  onClick={handleEnterExamination}
                >
                  Enter Examination
                </Button>
              </>
            )}
          </Card>
        </div>
      )}
    </div>
  );
};

export default StudentTestRoomPage;
