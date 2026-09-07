"""
security.py — Go-live hardening for the Ekhaya Nexus Flask app.

Provides:
  * SECURE_MODE detection (Render / explicit SECURE=1) so we only enforce
    HTTPS cookies + redirects in production, never while developing locally.
  * Reverse-proxy support (ProxyFix) for Render's HTTPS termination.
  * Force-HTTPS redirects (production only).
  * CSRF defence via Origin / Referer checking on state-changing requests
    (defence-in-depth on top of SameSite=Lax cookies).
  * A set of security response headers + HSTS when secure.
  * A small in-memory rate limiter for admin/registration endpoints.
"""

import os
import time

from flask import request, redirect, abort, session

# ---------------------------------------------------------------------------
# Mode detection
# ---------------------------------------------------------------------------
def secure_mode_enabled():
    """True when we should enforce HTTPS-only behaviour.

    Enabled automatically on Render (the platform sets $RENDER=1 and the app
    is always terminated TLS by Render's load balancer), or explicitly when
    SECURE=1 is set in the environment.
    """
    if os.environ.get("SECURE") is not None:
        return os.environ.get("SECURE", "").strip() in ("1", "true", "TRUE", "yes")
    return bool(os.environ.get("RENDER"))


def is_secure_request():
    """Best-effort detection of whether this request arrived over HTTPS."""
    if request.scheme == "https":
        return True
    return (request.headers.get("X-Forwarded-Proto", "").lower() == "https"
            or request.headers.get("X-Forwarded-Ssl", "").lower() == "on")


# ---------------------------------------------------------------------------
# Middleware / hooks installed by configure()
# ---------------------------------------------------------------------------
def _before_request():
    # 1) Force HTTPS in production (ignore redirects for non-GET/HEAD, let
    #    the default 308/301 machinery handle it via 'redirect(request.url)').
    if secure_mode_enabled() and not is_secure_request():
        if request.method in ("GET", "HEAD"):
            url = request.url.replace("http://", "https://", 1)
            return redirect(url, code=301)
        abort(403)  # never accept (or echo back) plaintext POSTs in prod

    # 2) CSRF defence-in-depth: state-changing requests must come from this
    #    site. SameSite=Lax already stops cross-site cookie-carrying form
    #    posts; this blocks the remaining corner cases (subdomain tricks).
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("Origin") or \
            request.headers.get("Referer")
        if origin:
            host = request.headers.get("Host", "").split(":")[0]
            try:
                from urllib.parse import urlparse
                ohost = urlparse(origin).netloc.split(":")[0].lower()
                if ohost != host.lower():
                    abort(403, "Cross-site request blocked")
            except Exception:  # noqa: BLE001
                abort(400)
    return None


def _after_request(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()")
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self' https://fonts.gstatic.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "script-src 'self' 'unsafe-inline'; "
        "frame-ancestors 'self'; "
        "base-uri 'self'; "
        "form-action 'self'")
    if secure_mode_enabled():
        resp.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains")
    # Best effort: hide the framework/reference server banner.
    if resp.headers.get("Server"):
        resp.headers["Server"] = "Ekhaya"
    # Don't cache authenticated / sensitive pages.
    p = request.path
    if p.startswith(("/admin", "/fan", "/verify", "/team")) and \
            (session.get("admin_logged_in") or session.get("fan_id")):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
    return resp


def configure(app):
    """Apply all production security settings to a Flask app."""
    app.config["SECURE_MODE"] = secure_mode_enabled()

    # Session cookies: HttpOnly + SameSite always; Secure only in production
    # (a Secure cookie would be dropped by browsers over plain http in dev).
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = secure_mode_enabled()
    app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 7
    app.config.setdefault("MAX_CONTENT_LENGTH", 5 * 1024 * 1024)

    if secure_mode_enabled():
        app.config["PREFERRED_URL_SCHEME"] = "https"
        app.config["SESSION_COOKIE_SECURE"] = True

    # Render terminates TLS at the load balancer; teach Flask it sees https.
    try:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    except ImportError:  # pragma: no cover
        pass

    app.before_request(_before_request)
    app.after_request(_after_request)


# ---------------------------------------------------------------------------
# Rate limiting (in-memory; sufficient for a single-worker app)
# ---------------------------------------------------------------------------
_HITS = {}


def rate_limit(bucket, limit=5, window=60):
    """Return True if the bucket is under 'limit' requests per 'window' sec.

    Caller decides action on False (e.g. flash + redirect, or 429).
    """
    now = time.time()
    hits = [t for t in _HITS.get(bucket, []) if now - t < window]
    if len(hits) >= limit:
        _HITS[bucket] = hits
        return False
    hits.append(now)
    _HITS[bucket] = hits
    return True


def reset_rate(bucket):
    _HITS.pop(bucket, None)