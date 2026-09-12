from django.core.management.base import BaseCommand, CommandError
from apps.accounts.services import AuditService
from apps.accounts.models import AuditLog


class Command(BaseCommand):
    help = 'Safely and permanently purges Security Audit Trail records (AuditLog) in the testing environment.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Purge all Security Audit Trail records completely.'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Explicit safety confirmation required for destructive purge.'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report the count of records that would be purged without actually deleting them.'
        )

    def handle(self, *args, **options):
        clear_all = options['all']
        confirm = options['confirm']
        dry_run = options['dry_run']

        if not clear_all:
            raise CommandError("No purge scope specified. Use --all to specify full security audit trail cleanup.")

        current_count = AuditLog.objects.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] {current_count} Security Audit Trail records would be purged."
                )
            )
            return

        if not confirm:
            raise CommandError(
                "Destructive operation aborted: clearing all audit logs requires explicit confirmation. "
                "Pass --confirm to execute."
            )

        deleted_count = AuditService.purge_security_audit_trail(clear_all=True, confirm=True)
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully purged {deleted_count} Security Audit Trail records."
            )
        )
