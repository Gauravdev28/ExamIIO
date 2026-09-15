import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import PermissionDenied

class TimeStampedModel(models.Model):
    """
    Abstract base model providing self-updating created_at and updated_at fields.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']


class UUIDModel(models.Model):
    """
    Abstract base model utilizing a cryptographically secure UUID v4 as primary key.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class ImmutableModel(models.Model):
    """
    Abstract base model enforcing application-level append-only immutability.
    Direct updates and deletions raise PermissionDenied.
    """
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionDenied(
                f"Modification of immutable record {self.__class__.__name__} (ID: {self.pk}) is prohibited."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied(
            f"Deletion of immutable record {self.__class__.__name__} (ID: {self.pk}) is prohibited."
        )


class NotificationType(models.TextChoices):
    NOTICE = 'NOTICE', 'Notice'
    REMINDER = 'REMINDER', 'Reminder'
    ANNOUNCEMENT = 'ANNOUNCEMENT', 'Announcement'
    ALERT = 'ALERT', 'Alert'


class NotificationAudience(models.TextChoices):
    INDIVIDUAL = 'INDIVIDUAL', 'Individual'
    ALL_STUDENTS = 'ALL_STUDENTS', 'All Students'


class Notification(UUIDModel, TimeStampedModel):
    """
    Persistent notification model for targeted administrative messages and announcements.
    Supports individual candidate notices and all-student broadcast materialization.
    """
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True,
        verbose_name="Recipient User"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_notifications',
        verbose_name="Sender Admin"
    )
    title = models.CharField(
        max_length=255,
        verbose_name="Notification Title"
    )
    message = models.TextField(
        verbose_name="Notification Body"
    )
    notification_type = models.CharField(
        max_length=32,
        choices=NotificationType.choices,
        default=NotificationType.NOTICE,
        db_index=True,
        verbose_name="Category"
    )
    audience = models.CharField(
        max_length=32,
        choices=NotificationAudience.choices,
        default=NotificationAudience.INDIVIDUAL,
        db_index=True,
        verbose_name="Target Audience"
    )
    assessment = models.ForeignKey(
        'assessments.Assessment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name="Associated Assessment"
    )
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Is Read"
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Read At"
    )

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
            models.Index(fields=['notification_type', '-created_at']),
        ]

    def __str__(self):
        return f"Notification({self.notification_type} -> {self.recipient.email}: {self.title})"

    def mark_as_read(self):
        from django.utils import timezone
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at', 'updated_at'])
