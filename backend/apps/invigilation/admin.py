from django.contrib import admin
from apps.invigilation.models import (
    ProctorAssignment,
    ProctorIntervention,
    ProctorDutySession,
    ProctorChatMessage,
    ProctorReattemptAuthorization,
)


@admin.register(ProctorAssignment)
class ProctorAssignmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'proctor', 'assessment', 'is_active', 'max_candidates', 'created_at')
    list_filter = ('is_active', 'assessment')
    search_fields = ('proctor__email', 'assessment__title')


@admin.register(ProctorIntervention)
class ProctorInterventionAdmin(admin.ModelAdmin):
    list_display = ('id', 'attempt', 'proctor', 'student', 'event_type', 'reason_code', 'issued_at')
    list_filter = ('event_type', 'issued_at')
    search_fields = ('student__email', 'proctor__email', 'reason_code', 'reason_text')
    readonly_fields = [f.name for f in ProctorIntervention._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProctorDutySession)
class ProctorDutySessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'proctor', 'assessment', 'is_active', 'active_monitored_count', 'started_at', 'ended_at')
    list_filter = ('is_active',)
    search_fields = ('proctor__email', 'assessment__title')


@admin.register(ProctorChatMessage)
class ProctorChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'attempt', 'sender', 'recipient', 'is_read', 'sent_at')
    list_filter = ('is_read', 'sent_at')
    search_fields = ('sender__email', 'recipient__email', 'message_text')
    readonly_fields = ('id', 'attempt', 'sender', 'recipient', 'message_text', 'sent_at')


@admin.register(ProctorReattemptAuthorization)
class ProctorReattemptAuthorizationAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'student', 'assessment', 'status', 'reason',
        'authorized_by', 'authorized_at', 'available_at', 'new_attempt'
    )
    list_filter = ('status', 'reason', 'authorized_at')
    search_fields = ('student__email', 'assessment__title', 'authorized_by__email')
    readonly_fields = [f.name for f in ProctorReattemptAuthorization._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
