"""
The Shopmates playbook: a short, hand-written guide to cross-promotion deal types.

This is our own domain knowledge (written by the team, not scraped), kept small
on purpose so retrieval stays fast on free hosting and every answer can cite
exactly which passage it came from. See ai/playbook.py for retrieval.

`tags` are shop categories the passage is most relevant to.
"""

PASSAGES = [
    {
        'id': 'reciprocal-discount',
        'title': 'Reciprocal discount',
        'tags': [],
        'text': (
            'Each shop gives customers sent by the other a percentage off one purchase. It is the '
            'simplest deal to explain and to verify with a receipt or code. It is fair when both '
            'shops have a similar typical spend. When spend differs a lot, the same percentage costs '
            'the cheaper shop far less, so add a redemption cap or use a smaller percentage at the '
            'higher-priced shop. Typical range is 10 to 15 percent for 30 days.'
        ),
    },
    {
        'id': 'purchase-triggered',
        'title': 'Purchase-triggered benefit',
        'tags': [],
        'text': (
            'A customer who buys at shop A receives a free small item or a bonus at shop B, such as '
            'a free cookie with a book purchase. The benefit costs the honoring shop only the item, '
            'not a percentage of the basket, which protects margins on expensive baskets. It works '
            'best when the free item is cheap to make and brings the customer through the door.'
        ),
    },
    {
        'id': 'bundled-experience',
        'title': 'Bundled experience',
        'tags': [],
        'text': (
            'Two shops package one outing at a fixed price: for example a class plus a smoothie, or '
            'dinner plus flowers. Bundles raise the average order for both shops but need more '
            'coordination on pricing and who keeps what. Run it as a short pilot weekend before '
            'committing to a longer deal.'
        ),
    },
    {
        'id': 'cafe-bookstore',
        'title': 'Cafe and bookstore pairing',
        'tags': ['cafe', 'bookstore'],
        'text': (
            'Cafes and bookstores share customers who stay a long time. A good deal is a drink '
            'discount with a book receipt and a book discount with a cafe receipt. Readers linger, '
            'so redemption rates are usually high and steady on weekends. Because books cost more '
            'than coffee, cap the bookstore discount lower or limit redemptions to keep costs even.'
        ),
    },
    {
        'id': 'bakery-flowers',
        'title': 'Bakery and flower shop pairing',
        'tags': ['bakery', 'flowers'],
        'text': (
            'Bakeries and flower shops both sell gifts for birthdays, anniversaries and holidays. '
            'Offer a cake or pastry discount with a flower purchase and the reverse. Demand peaks '
            'around holidays, so schedule the deal to cover them and raise the cap for that week. '
            'Flower orders are higher value, so a free pastry from the bakery balances a percentage '
            'off from the florist.'
        ),
    },
    {
        'id': 'cafe-fitness',
        'title': 'Cafe and fitness studio pairing',
        'tags': ['cafe', 'fitness'],
        'text': (
            'Studios send customers to a cafe right after class. A smoothie or coffee discount for '
            'members and a free class pass for cafe regulars both work. Class times drive demand, so '
            'the cafe sees bursts in the morning and early evening. Staff should know the class '
            'schedule so the line is ready.'
        ),
    },
    {
        'id': 'salon-retail',
        'title': 'Salon and boutique pairing',
        'tags': ['salon', 'retail'],
        'text': (
            'Salon visits leave customers with waiting time and an appearance-minded mood. Salons '
            'can hand a boutique discount card to customers and the boutique can hand out a salon '
            'trial offer. Appointments are high value, so keep the salon side to a fixed-amount '
            'credit rather than a large percentage.'
        ),
    },
    {
        'id': 'restaurant-flowers',
        'title': 'Restaurant and flower shop pairing',
        'tags': ['restaurant', 'flowers'],
        'text': (
            'Restaurants and florists meet at date nights and celebrations. A restaurant can offer a '
            'dessert or drink with a flower purchase, and the florist can discount a bouquet for '
            'diners. Promote it around Valentine\'s Day, Mother\'s Day and anniversaries.'
        ),
    },
    {
        'id': 'lopsided-deals',
        'title': 'Fixing a lopsided deal',
        'tags': [],
        'text': (
            'A deal is lopsided when one shop sends noticeably more customers than it receives, or '
            'one shop pays much more in discounts. Resentful deals quietly lapse. Fixes: raise the '
            'cap or discount for the shop that sends more, shorten the term, add a fixed-value '
            'perk from the shop that receives more, or promote the deal harder at the quieter shop. '
            'Review after at least a few redemptions, not after the first one.'
        ),
    },
    {
        'id': 'caps-and-dates',
        'title': 'Choosing caps and dates',
        'tags': [],
        'text': (
            'A redemption cap limits how much a deal can cost. Pick a cap the shop could afford if '
            'every code were used, for example fifty redemptions at ten percent. Thirty days is long '
            'enough to measure results and short enough to adjust. Start a deal on a Monday so staff '
            'have the whole week to learn it.'
        ),
    },
    {
        'id': 'staff-training',
        'title': 'Training staff to redeem codes',
        'tags': [],
        'text': (
            'Redemptions fail at the counter, not on screen. Show every staff member where the '
            'redeem page is, how to enter a code, and what to say when a code is expired or already '
            'used. Keep the printed QR code next to the register so customers see it. Staff confirm '
            'each code once; a second confirmation of the same code does nothing.'
        ),
    },
    {
        'id': 'measuring-fairness',
        'title': 'Measuring fairness',
        'tags': [],
        'text': (
            'Count customers sent and received by each shop and estimate the discount each shop paid '
            'as redemptions honored times the discount times typical spend. Equal counts do not mean '
            'equal cost when typical spend differs, so look at both. A gap of forty percent or more '
            'of total redemptions, with at least four redemptions, is a sign to renegotiate.'
        ),
    },
    {
        'id': 'seasonal-timing',
        'title': 'Seasonal timing',
        'tags': [],
        'text': (
            'Campus-area shops see surges at move-in, parents weekend, finals and graduation, and '
            'slow periods over breaks. Time a deal to cover a surge and cap it so a rush does not '
            'exhaust the budget. Avoid starting a deal the week before a long break.'
        ),
    },
    {
        'id': 'competing-categories',
        'title': 'Avoiding competitor pairings',
        'tags': ['cafe', 'bakery', 'restaurant'],
        'text': (
            'Two shops that sell the same thing, such as two cafes, compete for the same customer, '
            'so a referral deal mostly moves sales around instead of creating new ones. Prefer a '
            'neighbor in a different category whose customers would not otherwise visit you. If you '
            'do pair similar shops, differentiate the offer, for example pastries from one and '
            'coffee from the other.'
        ),
    },
]
