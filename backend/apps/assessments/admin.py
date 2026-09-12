from django.contrib import admin, messages
from django.urls import path, reverse
from django.http import HttpResponseRedirect
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.shortcuts import render
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.accounts.models import Role
from apps.assessments.models import (
    Assessment,
    AssessmentAssignment,
    TestAttempt,
    AttemptStatus,
)
from apps.invigilation.models import (
    ProctorReattemptAuthorization,
    ReattemptReason,
    ReattemptAuthStatus,
)
from apps.invigilation.services import ProctorReattemptService


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'start_datetime', 'end_datetime', 'duration_minutes', 'attempt_limit', 'created_by')
    list_filter = ('status', 'proctoring_enabled')
    search_fields = ('title', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(AssessmentAssignment)
class AssessmentAssignmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'assessment', 'student', 'status', 'assigned_by', 'assigned_at')
    list_filter = ('status', 'assessment')
    search_fields = ('student__email', 'assessment__title')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(TestAttempt)
class TestAttemptAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'student',
        'assessment',
        'attempt_number',
        'status',
        'is_disqualified',
        'started_at',
        'submitted_at',
        'reattempt_status_badge',
    )
    list_filter = ('status', 'is_disqualified', 'assessment')
    search_fields = ('student__email', 'assessment__title', 'id')
    readonly_fields = [
        'id',
        'student',
        'assessment',
        'assessment_snapshot',
        'attempt_number',
        'status',
        'started_at',
        'expires_at',
        'submitted_at',
        'is_disqualified',
        'disqualification_reason',
        'disqualified_at',
        'termination_pending',
        'termination_deadline',
        'termination_reason',
        'termination_cancelled_at',
        'termination_cancelled_by',
        'state_version',
        'randomization_seed',
        'question_order',
        'option_orders',
        'created_at',
        'updated_at',
        'reattempt_summary',
        'give_another_chance_action',
    ]
    actions = ['give_student_another_chance']

    fieldsets = (
        ('Attempt Overview', {
            'fields': (
                'id',
                'student',
                'assessment',
                'attempt_number',
                'status',
                'started_at',
                'expires_at',
                'submitted_at',
            )
        }),
        ('Second-Chance / Reattempt Management', {
            'fields': (
                'reattempt_summary',
                'give_another_chance_action',
            )
        }),
        ('Proctoring & Disqualification Status', {
            'fields': (
                'is_disqualified',
                'disqualification_reason',
                'disqualified_at',
                'termination_pending',
                'termination_deadline',
                'termination_reason',
                'termination_cancelled_at',
                'termination_cancelled_by',
            )
        }),
        ('Snapshot & Randomization Details', {
            'classes': ('collapse',),
            'fields': (
                'assessment_snapshot',
                'state_version',
                'randomization_seed',
                'question_order',
                'option_orders',
                'created_at',
                'updated_at',
            )
        }),
    )

    def has_add_permission(self, request):
        # Test attempts are created strictly through AttemptService.start_attempt
        return False

    def has_delete_permission(self, request, obj=None):
        # Test attempts are protected by audit and legal retention constraints
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/give-another-chance/',
                self.admin_site.admin_view(self.give_another_chance_view),
                name='assessments_testattempt_give_another_chance',
            ),
        ]
        return custom_urls + urls

    @admin.display(description="Reattempt Status")
    def reattempt_status_badge(self, obj):
        auth = ProctorReattemptAuthorization.objects.filter(
            assessment=obj.assessment,
            student=obj.student
        ).first()
        if not auth:
            if obj.status == AttemptStatus.CANCELLED:
                return mark_safe('<span style="color: #64748b;">Eligible</span>')
            return mark_safe('<span style="color: #94a3b8;">—</span>')

        if auth.status == ReattemptAuthStatus.CONSUMED:
            return format_html(
                '<span style="background-color: #d1fae5; color: #065f46; padding: 2px 6px; border-radius: 4px; font-weight: 600; font-size: 11px;">Consumed (Attempt #{})</span>',
                auth.new_attempt.attempt_number if auth.new_attempt else '?'
            )
        else:
            return mark_safe(
                '<span style="background-color: #fef3c7; color: #92400e; padding: 2px 6px; border-radius: 4px; font-weight: 600; font-size: 11px;">Authorized</span>'
            )

    @admin.display(description="Reattempt History")
    def reattempt_summary(self, obj):
        auth = ProctorReattemptAuthorization.objects.filter(
            assessment=obj.assessment,
            student=obj.student
        ).select_related('authorized_by', 'new_attempt', 'original_attempt').first()

        if not auth:
            if obj.status == AttemptStatus.CANCELLED:
                return "No reattempt authorized yet. This cancelled attempt is eligible for a second chance."
            return "No reattempt authorized (Attempt is not in CANCELLED status)."

        new_att_info = "None (Not yet started by candidate)"
        if auth.new_attempt:
            new_att_info = format_html(
                'Attempt #{} (<a href="{}">{}</a>) — Status: <strong>{}</strong>',
                auth.new_attempt.attempt_number,
                reverse('admin:assessments_testattempt_change', args=[auth.new_attempt.id]),
                auth.new_attempt.id,
                auth.new_attempt.status
            )

        return format_html(
            '<div style="line-height: 1.6;">'
            '<strong>Status:</strong> {}<br>'
            '<strong>Reason:</strong> {}<br>'
            '<strong>Authorized By:</strong> {}<br>'
            '<strong>Authorized At:</strong> {}<br>'
            '<strong>Available At:</strong> {}<br>'
            '<strong>New Attempt:</strong> {}<br>'
            '<strong>Note:</strong> {}'
            '</div>',
            auth.status,
            auth.get_reason_display(),
            auth.authorized_by.email,
            auth.authorized_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
            auth.available_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
            new_att_info,
            auth.note or '—'
        )

    @admin.display(description="Action")
    def give_another_chance_action(self, obj):
        if not obj or not obj.id:
            return "—"

        auth = ProctorReattemptAuthorization.objects.filter(
            assessment=obj.assessment,
            student=obj.student
        ).first()

        if auth:
            if auth.status == ReattemptAuthStatus.CONSUMED:
                return format_html(
                    '<span style="color: #059669; font-weight: 600;">Reattempt already consumed (Attempt #{})</span>',
                    auth.new_attempt.attempt_number if auth.new_attempt else '2'
                )
            return mark_safe(
                '<span style="color: #d97706; font-weight: 600;">Reattempt already authorized (Pending student start)</span>'
            )

        if obj.status != AttemptStatus.CANCELLED:
            return format_html(
                '<span style="color: #64748b;">Unavailable (Attempt status is {})</span>',
                obj.status
            )

        if hasattr(obj, 'reattempt_origin') and obj.reattempt_origin is not None:
            return mark_safe(
                '<span style="color: #dc2626; font-weight: 600;">Unavailable (Attempt is already a reattempt; Attempt #3 prohibited)</span>'
            )

        url = reverse('admin:assessments_testattempt_give_another_chance', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" style="background-color: #10b981; color: white; padding: 6px 14px; font-weight: 600; border-radius: 4px; text-decoration: none; display: inline-block;">'
            'Give Student Another Chance'
            '</a>',
            url
        )

    @admin.action(description="Give Student Another Chance")
    def give_student_another_chance(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly one test attempt to authorize a second chance.",
                messages.WARNING
            )
            return None

        attempt = queryset.first()
        url = reverse('admin:assessments_testattempt_give_another_chance', args=[attempt.id])
        return HttpResponseRedirect(url)

    def give_another_chance_view(self, request, object_id):
        # 1. Require Authenticated Admin / Superuser
        if not request.user.is_authenticated or not request.user.is_staff or not (
            request.user.is_superuser or getattr(request.user, 'role', None) == Role.ADMIN
        ):
            raise PermissionDenied("Only administrators may authorize a second-chance exam.")

        attempt = self.get_object(request, object_id)
        if not attempt:
            messages.error(request, f"Test attempt {object_id} not found.")
            return HttpResponseRedirect(reverse('admin:assessments_testattempt_changelist'))

        existing_auth = ProctorReattemptAuthorization.objects.filter(
            assessment=attempt.assessment,
            student=attempt.student
        ).select_related('authorized_by', 'new_attempt').first()

        is_cancelled = (attempt.status == AttemptStatus.CANCELLED)
        is_already_reattempt = bool(hasattr(attempt, 'reattempt_origin') and attempt.reattempt_origin is not None)
        can_authorize = is_cancelled and not is_already_reattempt and not existing_auth

        # 2. Process Confirmation Form Submission
        if request.method == 'POST' and 'confirm' in request.POST:
            if not can_authorize:
                messages.error(request, "This attempt is not eligible for a second chance authorization.")
                return HttpResponseRedirect(reverse('admin:assessments_testattempt_change', args=[attempt.id]))

            reason = request.POST.get('reason', '').strip()
            note = request.POST.get('note', '').strip()

            # Delegate completely to existing authorative service
            try:
                auth = ProctorReattemptService.authorize_reattempt(
                    proctor=request.user,
                    attempt_id=str(attempt.id),
                    reason=reason,
                    note=note,
                    request=request
                )
                self.message_user(
                    request,
                    f"Successfully authorized a second chance for {attempt.student.email} on {attempt.assessment.title}. "
                    f"The candidate will be eligible to begin Attempt #2 after the 60-second server preparation delay.",
                    messages.SUCCESS
                )
                return HttpResponseRedirect(reverse('admin:assessments_testattempt_change', args=[attempt.id]))
            except DRFValidationError as e:
                err_text = str(e.detail)
                if isinstance(e.detail, dict):
                    err_text = "; ".join(f"{k}: {v}" for k, v in e.detail.items())
                self.message_user(request, f"Reattempt authorization rejected: {err_text}", messages.ERROR)
            except Exception as e:
                self.message_user(request, f"Reattempt authorization error: {str(e)}", messages.ERROR)

        # 3. Render Confirmation Interface
        context = {
            **self.admin_site.each_context(request),
            'title': f"Give Student Another Chance: Attempt #{attempt.attempt_number} ({attempt.student.email})",
            'attempt': attempt,
            'opts': self.model._meta,
            'existing_auth': existing_auth,
            'is_cancelled': is_cancelled,
            'is_already_reattempt': is_already_reattempt,
            'can_authorize': can_authorize,
            'next_attempt_number': attempt.attempt_number + 1,
            'reasons': ReattemptReason.choices,
            'cancel_url': reverse('admin:assessments_testattempt_change', args=[attempt.id]),
        }
        return render(request, 'admin/assessments/give_another_chance.html', context)
