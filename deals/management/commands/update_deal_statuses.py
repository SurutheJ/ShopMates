from django.core.management.base import BaseCommand

from deals import services
from deals.models import Deal


class Command(BaseCommand):
    help = 'Apply time-based deal transitions (expire stale proposals, start and finish deals).'

    def handle(self, *args, **options):
        deals = list(Deal.objects.exclude(status__in=Deal.CLOSED).select_related('proposer', 'recipient'))
        before = {d.pk: d.status for d in deals}
        services.sync_all(deals)
        changed = sum(1 for d in deals if before[d.pk] != d.status)
        self.stdout.write(f'Checked {len(deals)} deals, updated {changed}.')
