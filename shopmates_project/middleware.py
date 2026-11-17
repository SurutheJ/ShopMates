"""Adds an enforced Content-Security-Policy header.

Scripts may only come from this site: there are no inline scripts and no
'unsafe-inline' in script-src (docs/MASTER_PLAN.md 1.23). Styles still allow
'unsafe-inline' because 500.html carries a small inline <style> so that it can
render with no static files. There is no report endpoint, so a blocked resource
shows only in the browser console.
"""

POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: https://tile.openstreetmap.org",   # map tiles on the Deal Radar page
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self' https://accounts.google.com",   # the Google button posts here, then redirects there
])


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Content-Security-Policy'] = POLICY
        return response
