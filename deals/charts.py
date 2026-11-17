"""
A dependency-free chart: customers sent per day by each shop, as inline SVG.

Drawn on the server from the same query the summary uses, so there is no
JavaScript chart library to load and nothing to go out of sync. Shop names are
escaped because they are user-typed.
"""

from collections import OrderedDict
from datetime import timedelta

from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe

from .models import Redemption

COLORS = ('#0f766e', '#b45309')  # same as --accent and --warm in base.css


def daily_counts(deal):
    """OrderedDict date -> [sent_by_proposer, sent_by_recipient], continuous from first to last day."""
    redemptions = (Redemption.objects.filter(voucher__deal=deal)
                   .select_related('voucher').order_by('confirmed_at'))
    counts = OrderedDict()
    for r in redemptions:
        day = timezone.localtime(r.confirmed_at).date()
        slot = counts.setdefault(day, [0, 0])
        slot[0 if r.voucher.referring_shop_id == deal.proposer_id else 1] += 1
    if not counts:
        return counts
    first, last = min(counts), max(counts)
    filled = OrderedDict()
    day = first
    while day <= last:
        filled[day] = counts.get(day, [0, 0])
        day += timedelta(days=1)
    return filled


def redemptions_chart(deal):
    """Return an SVG string (safe to embed) or '' when there are no redemptions yet."""
    data = daily_counts(deal)
    if not data:
        return ''
    days = list(data)
    top = max(max(v) for v in data.values()) or 1
    width, height = 640, 240
    left, right, bottom, topmargin = 36, 10, 36, 14
    plot_w, plot_h = width - left - right, height - bottom - topmargin
    slot_w = plot_w / len(days)
    bar_w = max(2.0, min(22.0, slot_w * 0.38))

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" class="chart" '
             f'aria-label="Customers sent per day by each shop">']
    for tick in range(0, top + 1, max(1, top // 4)):
        y = topmargin + plot_h - plot_h * tick / top
        parts.append(f'<line x1="{left}" x2="{width - right}" y1="{y:.1f}" y2="{y:.1f}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="#6b7280">{tick}</text>')
    label_every = max(1, len(days) // 8)
    for i, day in enumerate(days):
        cx = left + slot_w * (i + 0.5)
        for j, value in enumerate(data[day]):
            if not value:
                continue
            bar_h = plot_h * value / top
            x = cx - bar_w + j * bar_w
            parts.append(f'<rect x="{x:.1f}" y="{topmargin + plot_h - bar_h:.1f}" width="{bar_w:.1f}" '
                         f'height="{bar_h:.1f}" rx="2" fill="{COLORS[j]}"/>')
        if i % label_every == 0:
            parts.append(f'<text x="{cx:.1f}" y="{height - 16}" text-anchor="middle" font-size="11" '
                         f'fill="#6b7280">{day:%b} {day.day}</text>')
    names = (escape(deal.proposer.name), escape(deal.recipient.name))
    legend_x = left
    for j, name in enumerate(names):
        parts.append(f'<rect x="{legend_x}" y="{height - 10}" width="9" height="9" rx="2" fill="{COLORS[j]}"/>')
        parts.append(f'<text x="{legend_x + 13}" y="{height - 2}" font-size="11" fill="#374151">{name} sent</text>')
        legend_x += 150 + 6 * len(name)
    parts.append('</svg>')
    return mark_safe(''.join(parts))
