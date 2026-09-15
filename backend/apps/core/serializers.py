from rest_framework import serializers
from apps.accounts.models import User, Role
from apps.assessments.models import Assessment
from .models import Notification, NotificationType, NotificationAudience


class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for candidate/user notification read representations.
    Includes sender name and associated assessment metadata where applicable.
    """
    sender_name = serializers.SerializerMethodField()
    assessment_title = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id',
            'title',
            'message',
            'notification_type',
            'audience',
            'is_read',
            'read_at',
            'created_at',
            'sender_name',
            'assessment',
            'assessment_title',
        ]
        read_only_fields = fields

    def get_sender_name(self, obj) -> str:
        if obj.sender:
            return obj.sender.display_name or obj.sender.email.split('@')[0]
        return 'System'

    def get_assessment_title(self, obj) -> str | None:
        if obj.assessment:
            return obj.assessment.title
        return None


class AdminSendNotificationSerializer(serializers.Serializer):
    """
    Serializer for administrative notification dispatch.
    Strictly validates target audience, recipient authorization, and category.
    """
    audience = serializers.ChoiceField(
        choices=NotificationAudience.choices,
        default=NotificationAudience.INDIVIDUAL
    )
    recipient_id = serializers.UUIDField(
        required=False,
        allow_null=True
    )
    title = serializers.CharField(
        max_length=255,
        min_length=1,
        trim_whitespace=True
    )
    message = serializers.CharField(
        min_length=1,
        trim_whitespace=True
    )
    notification_type = serializers.ChoiceField(
        choices=NotificationType.choices,
        default=NotificationType.NOTICE
    )
    assessment_id = serializers.UUIDField(
        required=False,
        allow_null=True
    )

    def validate(self, attrs):
        audience = attrs.get('audience', NotificationAudience.INDIVIDUAL)
        recipient_id = attrs.get('recipient_id')
        assessment_id = attrs.get('assessment_id')

        # 1. Validate audience & recipient matching
        if audience == NotificationAudience.INDIVIDUAL:
            if not recipient_id:
                raise serializers.ValidationError({
                    'recipient_id': 'Recipient ID is required when sending to an individual student.'
                })
            
            recipient = User.objects.filter(id=recipient_id).first()
            if not recipient:
                raise serializers.ValidationError({
                    'recipient_id': 'Target recipient user does not exist.'
                })
            if recipient.role != Role.STUDENT:
                raise serializers.ValidationError({
                    'recipient_id': 'Notifications can only be addressed to student candidates.'
                })
            if not recipient.is_active:
                raise serializers.ValidationError({
                    'recipient_id': 'Cannot send notifications to an inactive student account.'
                })
            attrs['recipient_user'] = recipient

        # 2. Validate assessment if provided
        if assessment_id:
            assessment = Assessment.objects.filter(id=assessment_id).first()
            if not assessment:
                raise serializers.ValidationError({
                    'assessment_id': 'The specified assessment does not exist.'
                })
            attrs['assessment_obj'] = assessment
        else:
            attrs['assessment_obj'] = None

        return attrs


class StudentOptionSerializer(serializers.ModelSerializer):
    """
    Lightweight candidate representation for admin recipient selectors.
    """
    roll_number = serializers.CharField(source='student_profile.roll_number', default='', read_only=True)
    euid = serializers.CharField(source='student_profile.euid', default='', read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'display_name',
            'roll_number',
            'euid',
        ]
        read_only_fields = fields
