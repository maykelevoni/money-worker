"""Run the nurture engine. Schedule with cron, e.g. every 10 min:
*/10 * * * * cd /path/to/money-worker && python3 manage.py run_engine
"""
from django.core.management.base import BaseCommand

from apps.sequences.engine import process_due_emails


class Command(BaseCommand):
    help = "Send any sequence emails that are now due to leads."

    def handle(self, *args, **options):
        result = process_due_emails()
        self.stdout.write(self.style.SUCCESS(result["detail"]))
