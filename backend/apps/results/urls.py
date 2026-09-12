from django.urls import path, re_path
from .views import (
    StudentAttemptResultView,
    StudentResultListView,
    StudentResultDetailView,
    StudentTopicAnalyticsView,
    StudentReportCreateView,
    StudentReportDetailView,
    StudentReportDownloadView,
    AdminAssessmentResultListView,
    AdminAssessmentResultDetailView,
    AdminAssessmentAnalyticsView,
    AdminQuestionAnalyticsView,
    AdminReleaseResultsView,
    AdminReportCreateView,
    AdminReportDetailView,
    AdminReportDownloadView,
    StudentCertificateListView,
    StudentCertificateDetailView,
    StudentCertificateDownloadView,
    AdminCertificateListView,
    AdminCertificateDetailView,
    AdminCertificateRetryView,
    AdminCertificateDownloadView,
    PublicCertificateVerifyView,
    StudentCoinSummaryView,
    StudentCoinLeaderboardView,
)

urlpatterns = [
    # Student Coin Endpoints
    path('student/coins/', StudentCoinSummaryView.as_view(), name='student-coins-summary'),
    path('student/coins/leaderboard/', StudentCoinLeaderboardView.as_view(), name='student-coins-leaderboard'),

    # Student Result Endpoints
    path('student/attempts/<uuid:attempt_id>/result/', StudentAttemptResultView.as_view(), name='student-attempt-result'),
    path('student/results/', StudentResultListView.as_view(), name='student-result-list'),
    path('student/results/<uuid:pk>/', StudentResultDetailView.as_view(), name='student-result-detail'),
    path('student/analytics/topics/', StudentTopicAnalyticsView.as_view(), name='student-topic-analytics'),
    path('student/reports/', StudentReportCreateView.as_view(), name='student-report-create'),
    path('student/reports/<uuid:pk>/', StudentReportDetailView.as_view(), name='student-report-detail'),
    path('student/reports/<uuid:pk>/download/', StudentReportDownloadView.as_view(), name='student-report-download'),

    # Student Certificate Endpoints
    path('student/certificates/', StudentCertificateListView.as_view(), name='student-certificate-list'),
    path('student/certificates/<uuid:pk>/', StudentCertificateDetailView.as_view(), name='student-certificate-detail'),
    path('student/certificates/<uuid:pk>/download/', StudentCertificateDownloadView.as_view(), name='student-certificate-download'),

    # Admin Result & Analytics Endpoints
    path('admin/assessments/<uuid:assessment_id>/results/', AdminAssessmentResultListView.as_view(), name='admin-assessment-results'),
    path('admin/assessments/<uuid:assessment_id>/analytics/', AdminAssessmentAnalyticsView.as_view(), name='admin-assessment-analytics'),
    path('admin/assessments/<uuid:assessment_id>/analytics/questions/', AdminQuestionAnalyticsView.as_view(), name='admin-question-analytics'),
    path('admin/assessments/<uuid:assessment_id>/release-results/', AdminReleaseResultsView.as_view(), name='admin-release-results'),
    path('admin/results/<uuid:pk>/', AdminAssessmentResultDetailView.as_view(), name='admin-result-detail'),
    path('admin/reports/', AdminReportCreateView.as_view(), name='admin-report-create'),
    path('admin/reports/<uuid:pk>/', AdminReportDetailView.as_view(), name='admin-report-detail'),
    path('admin/reports/<uuid:pk>/download/', AdminReportDownloadView.as_view(), name='admin-report-download'),

    # Admin Certificate Endpoints
    path('admin/certificates/', AdminCertificateListView.as_view(), name='admin-certificate-list'),
    path('admin/certificates/<uuid:pk>/', AdminCertificateDetailView.as_view(), name='admin-certificate-detail'),
    path('admin/certificates/<uuid:pk>/retry/', AdminCertificateRetryView.as_view(), name='admin-certificate-retry'),
    path('admin/certificates/<uuid:pk>/download/', AdminCertificateDownloadView.as_view(), name='admin-certificate-download'),

    # Public Verification Endpoint
    re_path(r'^public/certificates/verify/(?P<certificate_id>[^/]+)/?$', PublicCertificateVerifyView.as_view(), name='public-certificate-verify'),
]
