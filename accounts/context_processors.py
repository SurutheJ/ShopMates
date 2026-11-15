from .access import get_membership


def current_shop(request):
    """Make the signed-in user's shop and role available to every template (navbar uses it)."""
    membership = get_membership(request.user) if hasattr(request, 'user') else None
    return {
        'my_membership': membership,
        'my_shop': membership.shop if membership else None,
    }
