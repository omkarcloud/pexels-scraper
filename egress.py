"""The one network helper the pexels module needs: the Accept-Language its
sessions send. Requests go out direct from your own connection (or your
PEXELS_PROXY), so every session announces the plain English list a desktop
Chrome in the US sends. Pass `locale` to an endpoint for another language."""

ACCEPT_LANGUAGE = "en-US,en;q=0.9"


def site_accept_language(site=None):
    return ACCEPT_LANGUAGE


def accept_language(proxy=None, country=None):
    return ACCEPT_LANGUAGE
