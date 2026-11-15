from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from accounts.models import Shop

from .models import Deal, Redemption


def public_stats():
    """
    Anonymized aggregates for the public API and stats page.

    Never includes shop names, addresses or codes. A category with fewer than
    STATS_MIN_GROUP approved shops is hidden, because a small group could
    identify an individual shop.
    """
    min_group = settings.STATS_MIN_GROUP
    labels = dict(Shop.Category.choices)
    rows = (Shop.objects.filter(status=Shop.Status.APPROVED)
            .values('category').annotate(n=Count('id')).order_by('category'))

    groups, hidden = [], 0
    for row in rows:
        if row['n'] < min_group:
            hidden += 1
            continue
        category = row['category']
        deals = (Deal.objects
                 .exclude(status=Deal.Status.DRAFT)
                 .filter(Q(proposer__category=category) | Q(recipient__category=category))
                 .distinct().count())
        redemptions = Redemption.objects.filter(voucher__honoring_shop__category=category).count()
        groups.append({
            'category': labels.get(category, category),
            'shops': row['n'],
            'deals': deals,
            'redemptions': redemptions,
            'redemptions_per_shop': round(redemptions / row['n'], 2),
        })

    return {
        'generated_at': timezone.now().isoformat(),
        'min_group_size': min_group,
        'totals': {
            'shops': Shop.objects.filter(status=Shop.Status.APPROVED).count(),
            'deals_started': Deal.objects.exclude(status=Deal.Status.DRAFT).count(),
            'redemptions': Redemption.objects.count(),
        },
        'by_category': groups,
        'hidden_categories': hidden,
    }
