"""
fanhub.py — Ekhaya FC Fan Hub Blueprint.

Fan-facing pages (registration, login, dashboard, membership, payment, card,
notifications, news, fixtures, results, benefits) and the Admin/CEO fan-hub
management (stats, fan management, packages, payments, card management,
notifications, reports, audit log).
"""

import os
import uuid
import time
from datetime import datetime, timedelta
from functools import wraps

from flask import (Blueprint, render_template, redirect, url_for, request,
                   flash, session, abort, jsonify)

from werkzeug.security import generate_password_hash, check_password_hash

from database import (get_connection, get_all_teams, get_all_fixtures,
                      get_standings, check_admin)
import membership_db as mdb
import payment_provider as pp

bp = Blueprint("fanhub", __name__, url_prefix=None)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE_DIR, "static")
FAN_PHOTO_DIR = os.path.join(STATIC, "img", "fans")
os.makedirs(FAN_PHOTO_DIR, exist_ok=True)
ALLOWED_IMG = {".jpg", ".jpeg", ".png", ".webp"}

FAN_FAVOURITE_TEAMS = ["Main Team", "Reserve", "Women", "Youth"]

# Simple in-memory rate limiter: {bucket: [(ts, count), ...]}
_LOGIN_ATTEMPTS = {}


def _rate_limited(bucket, limit=5, window=60):
    """Return True (allowed) if the bucket is under the limit."""
    now_ = time.time()
    hits = _LOGIN_ATTEMPTS.get(bucket, [])
    hits = [t for t in hits if now_ - t < window]
    if len(hits) >= limit:
        _LOGIN_ATTEMPTS[bucket] = hits
        return False
    hits.append(now_)
    _LOGIN_ATTEMPTS[bucket] = hits
    return True


def _reset_rate(bucket):
    _LOGIN_ATTEMPTS.pop(bucket, None)


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------
def fan_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        fan_id = session.get("fan_id")
        if not fan_id:
            return redirect(url_for("fanhub.fan_login",
                                    next=request.path))
        fan = mdb.get_fan_by_id(fan_id)
        if not fan or not fan["is_active"]:
            session.clear()
            flash("Your account is inactive. Contact the club.", "error")
            return redirect(url_for("fanhub.fan_login"))
        g_fan = fan
        return f(fan=g_fan, *args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


def _current_fan():
    sid = session.get("fan_id")
    return mdb.get_fan_by_id(sid) if sid else None


def _fan_context(fan=None):
    fan = fan or _current_fan()
    ctx = {}
    if fan:
        ctx["unread"] = mdb.unread_notifications_count(fan["id"])
    return ctx


# ---------------------------------------------------------------------------
# Fan registration & login
# ---------------------------------------------------------------------------
@bp.route("/fan/register", methods=["GET", "POST"])
def fan_register():
    teams = FAN_FAVOURITE_TEAMS
    if request.method == "POST":
        first = request.form.get("first_name", "").strip()
        last = request.form.get("last_name", "").strip()
        dob = request.form.get("dob", "").strip()
        gender = request.form.get("gender", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip().lower()
        district = request.form.get("district", "").strip()
        favorite = request.form.get("favourite_team", "Main Team")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        em_name = request.form.get("emergency_name", "").strip() or None
        em_phone = request.form.get("emergency_phone", "").strip() or None

        errs = []
        if not first or not last:
            errs.append("First and last name are required.")
        if "@" not in email or "." not in email:
            errs.append("A valid email is required.")
        if len(password) < 6:
            errs.append("Password must be at least 6 characters.")
        if password != confirm:
            errs.append("Passwords do not match.")
        if mdb.get_fan_by_email(email):
            errs.append("An account with that email already exists.")

        if errs:
            for e in errs:
                flash(e, "error")
            return render_template("fan_register.html", teams=teams,
                                   form=request.form)

        pwd_hash = generate_password_hash(password)
        try:
            fid, number = mdb.create_fan_member(
                first, last, dob, gender, phone, email, district, pwd_hash,
                favorite, em_name, em_phone)
        except Exception:  # noqa: BLE001
            flash("Registration failed. Please try again.", "error")
            return render_template("fan_register.html", teams=teams,
                                   form=request.form)
        mdb.audit(fan_id if False else email, "FAN_REGISTER",
                  "New fan registration: %s (%s)" % (email, number),
                  actor_type="fan")
        mdb.add_notification(fid, "Welcome to Ekhaya FC Fan Hub",
                             "Your membership number is %s. Welcome aboard!"
                             % number)
        session.clear()
        flash("Registration successful! Your member number is %s. "
              "Please log in." % number, "success")
        return redirect(url_for("fanhub.fan_login"))
    return render_template("fan_register.html", teams=teams, form={})


@bp.route("/fan/login", methods=["GET", "POST"])
def fan_login():
    next_url = request.args.get("next") or url_for("fanhub.fan_dashboard")
    if session.get("fan_id"):
        return redirect(url_for("fanhub.fan_dashboard"))
    if request.method == "POST":
        if not _rate_limited("fan_login"):
            flash("Too many attempts. Please wait a minute.", "error")
            return render_template("fan_login.html"), 429
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        fan = mdb.get_fan_by_email(email)
        if fan and check_password_hash(fan["password_hash"], password) \
                and fan["is_active"]:
            session.permanent = True
            session["fan_id"] = fan["id"]
            session["fan_name"] = fan["first_name"]
            mdb.touch_login(fan["id"])
            mdb.audit(email, "FAN_LOGIN", "Fan logged in", actor_type="fan")
            _reset_rate("fan_login")
            return redirect(next_url)
        flash("Invalid email or password.", "error")
    return render_template("fan_login.html")


@bp.route("/fan/logout")
def fan_logout():
    session.pop("fan_id", None)
    session.pop("fan_name", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("fanhub.fan_login"))


# ---------------------------------------------------------------------------
# Fan dashboard
# ---------------------------------------------------------------------------
@bp.route("/fan/dashboard")
@fan_required
def fan_dashboard(fan=None):
    memb = mdb.get_current_membership(fan["id"])
    status = mdb.status_of_membership(memb) if memb else None
    card = mdb.get_card_for_fan(fan["id"])
    payments = mdb.get_payments_for_fan(fan["id"])[:5]
    notifications = mdb.get_notifications(fan["id"], 5)
    news = mdb.get_news(active_only=True, limit=3)
    announcements = mdb.get_announcements(active_only=True, limit=3)
    benefits = mdb.get_benefits(active_only=True)
    packages = mdb.get_packages(active_only=True)
    return render_template("fan_dashboard.html", fan=fan, memb=memb,
                           memb_status=status, card=card, payments=payments,
                           notifications=notifications, news=news,
                           announcements=announcements, benefits=benefits,
                           packages=packages, **_fan_context(fan))


@bp.route("/fan/profile", methods=["GET", "POST"])
@fan_required
def fan_profile(fan=None):
    if request.method == "POST":
        try:
            mdb.update_fan_profile(
                fan["id"],
                first_name=request.form.get("first_name", "").strip(),
                last_name=request.form.get("last_name", "").strip(),
                dob=request.form.get("dob", "").strip(),
                gender=request.form.get("gender", "").strip(),
                phone=request.form.get("phone", "").strip(),
                district=request.form.get("district", "").strip(),
                favourite_team=request.form.get("favourite_team", fan["favourite_team"]),
                emergency_name=request.form.get("emergency_name", "").strip() or None,
                emergency_phone=request.form.get("emergency_phone", "").strip() or None,
            )
            photo = request.files.get("profile_photo")
            if photo and photo.filename:
                ext = os.path.splitext(photo.filename)[1].lower()
                if ext in ALLOWED_IMG:
                    for old in os.listdir(FAN_PHOTO_DIR):
                        if old.startswith("fan%d_" % fan["id"]):
                            os.remove(os.path.join(FAN_PHOTO_DIR, old))
                    fname = "fan%d%s" % (fan["id"], ext)
                    photo.save(os.path.join(FAN_PHOTO_DIR, fname))
                    mdb.update_fan_photo(fan["id"], "img/fans/" + fname)
                else:
                    flash("Photo must be JPG, PNG or WebP.", "error")
            flash("Profile updated.", "success")
        except Exception as e:  # noqa: BLE001
            flash("Could not update profile: %s" % e, "error")
        return redirect(url_for("fanhub.fan_profile"))
    return render_template("fan_profile.html", fan=fan,
                           teams=FAN_FAVOURITE_TEAMS, **_fan_context(fan))


@bp.route("/fan/password", methods=["POST"])
@fan_required
def fan_change_password(fan=None):
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    if not check_password_hash(fan["password_hash"], current):
        flash("Current password is incorrect.", "error")
    elif len(new) < 6:
        flash("New password must be at least 6 characters.", "error")
    elif new != confirm:
        flash("New passwords do not match.", "error")
    else:
        mdb.update_fan_profile(fan["id"],
                               password_hash=generate_password_hash(new))
        mdb.audit(fan["email"], "FAN_CHANGE_PASSWORD", "Fan changed password",
                  actor_type="fan")
        flash("Password updated.", "success")
    return redirect(url_for("fanhub.fan_profile"))


# ---------------------------------------------------------------------------
# Membership subscription
# ---------------------------------------------------------------------------
@bp.route("/fan/membership")
@fan_required
def fan_membership(fan=None):
    packages = mdb.get_packages(active_only=True)
    current = mdb.get_current_membership(fan["id"])
    status = mdb.status_of_membership(current) if current else None
    history = mdb.get_memberships_for_fan(fan["id"])
    active = mdb.get_active_membership(fan["id"])
    return render_template("fan_membership.html", fan=fan, packages=packages,
                           current=current, memb_status=status, history=history,
                           active=active, **_fan_context(fan))


@bp.route("/fan/subscribe/<int:package_id>", methods=["POST"])
@fan_required
def fan_subscribe(fan=None, package_id=None):
    package = mdb.get_package(package_id)
    if not package or not package["is_active"]:
        flash("That membership package is not available.", "error")
        return redirect(url_for("fanhub.fan_membership"))

    # A fan who is already active should not buy a duplicate until it expires.
    active = mdb.get_active_membership(fan["id"])
    if active:
        flash("You already have an active %s membership."
              % active["package_name"], "error")
        return redirect(url_for("fanhub.fan_membership"))

    provider = pp.get_provider()
    reference = "M-{}-{}".format(package["name"].upper(),
                                 uuid.uuid4().hex[:8].upper())
    return render_template("fan_checkout.html", fan=fan, package=package,
                           reference=reference, provider=provider,
                           provider_name=provider.name, **_fan_context(fan))


@bp.route("/fan/pay", methods=["POST"])
@fan_required
def fan_pay(fan=None):
    package_id = request.form.get("package_id", type=int)
    phone = request.form.get("phone", "").strip()
    provider_id = request.form.get("provider", "sandbox")
    package = mdb.get_package(package_id) if package_id else None
    if not package or not package["is_active"]:
        flash("Invalid membership package.", "error")
        return redirect(url_for("fanhub.fan_membership"))

    # Create the pending membership row first.
    start = datetime.utcnow().strftime("%Y-%m-%d")
    expiry = (datetime.utcnow() +
              timedelta(days=int(package["duration_days"] or 365))).strftime("%Y-%m-%d")
    membership_id = mdb.create_membership(fan["id"], package["id"], start,
                                          expiry, package["price_mwk"], None)

    import membership_db
    reference = "MP-{}-{}".format(fan["id"], uuid.uuid4().hex[:10].upper())
    try:
        payment_id, txn_id, pv = pp.initiate_payment(
            fan_id=fan["id"], membership_id=membership_id, package=package,
            amount=package["price_mwk"], phone=phone or fan["phone"],
            email=fan["email"], reference=reference)
    except pp.PaymentProviderError as e:
        mdb.set_membership_status(membership_id, "PENDING")
        flash("Payment could not be initiated: %s" % e, "error")
        return redirect(url_for("fanhub.fan_membership"))

    if pv == "sandbox":
        # In sandbox mode we immediately verify (the backend still authorises).
        res = pp.verify_and_activate(payment_id)
        if res.get("ok"):
            flash("Payment verified! Your membership is now ACTIVE and your "
                  "digital card has been issued.", "success")
            mdb.audit(fan["email"], "PAYMENT_VERIFIED",
                      "Sandbox payment %s verified" % reference,
                      actor_type="fan")
            return redirect(url_for("fanhub.fan_card"))
        flash("Payment could not be verified: %s" % res.get("message"), "error")
        return redirect(url_for("fanhub.fan_payments"))
    else:
        flash("Payment initiated. We will confirm once the provider "
              "verifies the transaction.", "info")
        return redirect(url_for("fanhub.fan_payments"))


@bp.route("/fan/payments")
@fan_required
def fan_payments(fan=None):
    payments = mdb.get_payments_for_fan(fan["id"])
    return render_template("fan_payments.html", fan=fan, payments=payments,
                           **_fan_context(fan))


# ---------------------------------------------------------------------------
# Digital membership card
# ---------------------------------------------------------------------------
@bp.route("/fan/card")
@fan_required
def fan_card(fan=None):
    card = mdb.get_card_for_fan(fan["id"])
    memb = mdb.get_current_membership(fan["id"])
    status = mdb.status_of_membership(memb) if memb else None
    return render_template("fan_card.html", fan=fan, card=card,
                           memb_status=status, **_fan_context(fan))


@bp.route("/fan/card/<int:card_id>/card.png")
def fan_card_png(card_id):
    from flask import send_file
    card = mdb.get_card_by_id(card_id)
    if not card:
        abort(404)
    # Only owner or admin may view.
    if session.get("fan_id") != card["fan_id"] and \
            not session.get("admin_logged_in"):
        abort(403)
    fan = mdb.get_fan_by_id(card["fan_id"])
    memb = mdb.get_memberships_for_fan(card["fan_id"])
    m = next((r for r in memb if r["id"] == card["membership_id"]), None)
    path = os.path.join(STATIC, "img", "fan_cards",
                        "card_%s.png" % card["id"])
    from cardgen import generate_card_png
    package_name = (m["package_name"] if m else None) or "FAN"
    expiry = m["expiry_date"] if m else None
    status = "ACTIVE" if m and mdb.status_of_membership(m) == "ACTIVE" \
        else "EXPIRED"
    photo = None
    if fan and fan["profile_photo"]:
        photo = os.path.join(STATIC, fan["profile_photo"])
    generate_card_png(fan, card, package_name, expiry, status, photo, path)
    return send_file(path, mimetype="image/png")


@bp.route("/verify", methods=["GET", "POST"])
def staff_verify():
    """Staff verification entry page — scan or enter a QR code."""
    msg = None
    ok = None
    card = None
    secret = (request.form.get("qr") if request.method == "POST"
              else request.args.get("qr", "")).strip()
    if secret:
        card = mdb.lookup_card_by_qr_secret(secret)
        if card:
            ok = _card_active(card)
            msg = ("Valid & ACTIVE" if ok else "Not active / expired")
        else:
            msg = "Unknown or invalid QR code."
    return render_template("staff_verify.html", card=card, ok=ok, msg=msg)


def _card_active(card):
    """card is the joined row from lookup_card_by_qr_secret."""
    card = dict(card) if not isinstance(card, dict) else card
    status = (card.get("membership_status") or "PENDING").upper()
    expiry = card.get("expiry_date")
    if status != "ACTIVE":
        return False
    if expiry:
        try:
            if datetime.strptime(str(expiry), "%Y-%m-%d") < datetime.utcnow():
                return False
        except ValueError:
            return False
    return True


# ---------------------------------------------------------------------------
# Notifications, news, announcements, benefits
# ---------------------------------------------------------------------------
@bp.route("/fan/notifications")
@fan_required
def fan_notifications(fan=None):
    notifications = mdb.get_notifications(fan["id"], 50)
    mdb.mark_notifications_read(fan["id"])
    return render_template("fan_notifications.html", fan=fan,
                           notifications=notifications, **_fan_context(fan))


@bp.route("/fan/news")
@fan_required
def fan_news(fan=None):
    news = mdb.get_news(active_only=True, limit=30)
    return render_template("fan_news.html", fan=fan, news=news,
                           **_fan_context(fan))


@bp.route("/fan/fixtures")
@fan_required
def fan_fixtures(fan=None):
    fixtures = get_all_fixtures()
    ekhaya = get_standings("FDH Premiership")
    return render_template("fan_fixtures.html", fan=fan, fixtures=fixtures,
                           standings=ekhaya, **_fan_context(fan))


@bp.route("/fan/benefits")
@fan_required
def fan_benefits(fan=None):
    benefits = mdb.get_benefits(active_only=True)
    return render_template("fan_benefits.html", fan=fan, benefits=benefits,
                           **_fan_context(fan))


@bp.route("/fan/settings")
@fan_required
def fan_settings(fan=None):
    return render_template("fan_settings.html", fan=fan, **_fan_context(fan))


# ===========================================================================
# ADMIN / CEO — Fan Hub management
# ===========================================================================
@bp.route("/admin/fanhub")
@admin_required
def admin_fanhub():
    fs = mdb.fan_stats()
    ms = mdb.membership_stats()
    ps = mdb.payment_stats()
    registrations = mdb.registrations_by_day(30)
    breakdown = mdb.membership_breakdown()
    recent = mdb.get_all_payments(10)
    packages = mdb.get_packages(active_only=False)
    return render_template("fanhub_admin.html", fs=fs, ms=ms, ps=ps,
                           registrations=registrations, breakdown=breakdown,
                           recent=recent, packages=packages,
                           current_user=session.get("admin_username"),
                           providers=pp.list_providers(),
                           active_provider=pp.get_active_provider())


@bp.route("/admin/fanhub/fans")
@admin_required
def admin_fanhub_fans():
    q = request.args.get("q", "").strip()
    fans = mdb.search_fans(q) if q else mdb.search_fans()
    return render_template("fanhub_admin_fans.html", fans=fans, q=q,
                           current_user=session.get("admin_username"))


@bp.route("/admin/fanhub/fans/<int:fan_id>")
@admin_required
def admin_fanhub_fan_view(fan_id):
    fan = mdb.get_fan_by_id(fan_id)
    if not fan:
        abort(404)
    memberships = mdb.get_memberships_for_fan(fan_id)
    payments = mdb.get_payments_for_fan(fan_id)
    card = mdb.get_card_for_fan(fan_id)
    return render_template("fanhub_admin_fan_view.html", fan=fan,
                           memberships=memberships, payments=payments,
                           card=card, current_user=session.get("admin_username"))


@bp.route("/admin/fanhub/fans/<int:fan_id>/status", methods=["POST"])
@admin_required
def admin_fanhub_fan_status(fan_id):
    action = request.form.get("action")
    fan = mdb.get_fan_by_id(fan_id)
    if not fan:
        abort(404)
    if action == "activate":
        mdb.set_fan_active(fan_id, True)
        mdb.add_notification(fan_id, "Account Active",
                             "Your Ekhaya FC Fan Hub account is active.")
        mdb.audit(session.get("admin_username"), "FAN_ACTIVATE",
                  "Activated fan %s" % fan["email"])
    elif action == "deactivate":
        mdb.set_fan_active(fan_id, False)
        mdb.audit(session.get("admin_username"), "FAN_DEACTIVATE",
                  "Deactivated fan %s" % fan["email"])
    flash("Fan status updated.", "success")
    return redirect(url_for("fanhub.admin_fanhub_fan_view", fan_id=fan_id))


@bp.route("/admin/fanhub/packages", methods=["GET", "POST"])
@admin_required
def admin_fanhub_packages():
    if request.method == "POST":
        name = request.form["name"].strip()
        level = request.form.get("level", 0, type=int)
        price = request.form.get("price", 0, type=float)
        duration = request.form.get("duration_days", 365, type=int)
        desc = request.form.get("description", "").strip() or None
        benefits = request.form.get("benefits", "").strip() or None
        active = 1 if request.form.get("is_active") == "on" else 0
        mdb.add_package(name, level, price, duration, desc, benefits, active)
        mdb.audit(session.get("admin_username"), "PACKAGE_CREATE",
                  "Created package %s @ %s MWK" % (name, price))
        flash("Package created.", "success")
        return redirect(url_for("fanhub.admin_fanhub_packages"))
    packages = mdb.get_packages(active_only=False)
    return render_template("fanhub_admin_packages.html", packages=packages,
                           current_user=session.get("admin_username"))


@bp.route("/admin/fanhub/packages/<int:pkg_id>", methods=["POST"])
@admin_required
def admin_fanhub_package_update(pkg_id):
    action = request.form.get("action", "update")
    pkg = mdb.get_package(pkg_id)
    if not pkg:
        abort(404)
    if action == "toggle":
        mdb.set_package_active(pkg_id, not pkg["is_active"])
        mdb.audit(session.get("admin_username"), "PACKAGE_TOGGLE",
                  "Toggled package %s" % pkg["name"])
    else:
        mdb.update_package(
            pkg_id, request.form["name"].strip(),
            request.form.get("level", 0, type=int),
            request.form.get("price", 0, type=float),
            request.form.get("duration_days", 365, type=int),
            request.form.get("description", "").strip() or None,
            request.form.get("benefits", "").strip() or None,
            1 if request.form.get("is_active") == "on" else 0)
        mdb.audit(session.get("admin_username"), "PACKAGE_UPDATE",
                  "Updated package %s" % pkg["name"])
    flash("Package updated.", "success")
    return redirect(url_for("fanhub.admin_fanhub_packages"))


@bp.route("/admin/fanhub/payments")
@admin_required
def admin_fanhub_payments():
    status = request.args.get("status", "").strip()
    payments = mdb.get_all_payments(1000)
    if status:
        payments = [p for p in payments if p["status"] == status]
    return render_template("fanhub_admin_payments.html", payments=payments,
                           status_filter=status,
                           current_user=session.get("admin_username"))


@bp.route("/admin/fanhub/payments/<int:pay_id>/verify", methods=["POST"])
@admin_required
def admin_fanhub_payment_verify(pay_id):
    res = pp.verify_and_activate(pay_id)
    if res.get("ok"):
        flash("Payment verified and membership activated / card issued.",
              "success")
        mdb.audit(session.get("admin_username"), "PAYMENT_VERIFY_ADMIN",
                  "Admin verified payment #%s" % pay_id)
    else:
        flash("Verification: %s" % res.get("message"), "error")
    return redirect(url_for("fanhub.admin_fanhub_payments"))


@bp.route("/admin/fanhub/cards")
@admin_required
def admin_fanhub_cards():
    conn = get_connection()
    rows = conn.execute("""
        SELECT c.*, f.first_name, f.last_name, f.member_number,
               p.name AS package_name, m.status AS membership_status
        FROM fan_cards c
        JOIN fan_members f ON c.fan_id = f.id
        LEFT JOIN fan_memberships m ON c.membership_id = m.id
        LEFT JOIN membership_packages p ON m.package_id = p.id
        ORDER BY c.id DESC
    """).fetchall()
    conn.close()
    return render_template("fanhub_admin_cards.html", cards=rows,
                           current_user=session.get("admin_username"))


@bp.route("/admin/fanhub/notifications", methods=["GET", "POST"])
@admin_required
def admin_fanhub_notifications():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        target = request.form.get("target", "all")
        if target == "all":
            fans = mdb.search_fans()
            for f in fans:
                mdb.add_notification(f["id"], title, body)
        else:
            fan_id = request.form.get("fan_id", type=int)
            if fan_id:
                mdb.add_notification(fan_id, title, body)
        mdb.audit(session.get("admin_username"), "NOTIFY",
                  "Sent notification '%s' to %s" % (title, target))
        flash("Notification sent.", "success")
        return redirect(url_for("fanhub.admin_fanhub_notifications"))
    fans = mdb.search_fans()
    return render_template("fanhub_admin_notifications.html", fans=fans,
                           current_user=session.get("admin_username"))


@bp.route("/admin/fanhub/content", methods=["GET", "POST"])
@admin_required
def admin_fanhub_content():
    if request.method == "POST":
        kind = request.form.get("kind")
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if not title:
            flash("Title is required.", "error")
        elif kind == "news":
            mdb.add_news(title, body, is_active=1)
        elif kind == "announcement":
            mdb.add_announcement(title, body, is_active=1)
        elif kind == "benefit":
            mdb.add_benefit(title, body, 1)
        mdb.audit(session.get("admin_username"), "CONTENT_ADD",
                  "Added %s: %s" % (kind, title))
        flash("Content published.", "success")
        return redirect(url_for("fanhub.admin_fanhub_content"))
    news = mdb.get_all_news()
    ann = mdb.get_announcements(active_only=False)
    benefits = mdb.get_benefits(active_only=False)
    return render_template("fanhub_admin_content.html", news=news,
                           announcements=ann, benefits=benefits,
                           current_user=session.get("admin_username"))


@bp.route("/admin/fanhub/settings", methods=["GET", "POST"])
@admin_required
def admin_fanhub_settings():
    if request.method == "POST":
        providers = pp.list_providers()
        for key, val in request.form.items():
            mdb.set_setting(key, val)
        mdb.set_setting("active_payment_provider",
                        request.form.get("active_payment_provider", "sandbox"))
        mdb.audit(session.get("admin_username"), "SETTINGS",
                  "Updated fan hub settings")
        flash("Settings saved.", "success")
        return redirect(url_for("fanhub.admin_fanhub_settings"))
    settings = mdb.get_all_settings()
    return render_template("fanhub_admin_settings.html", settings=settings,
                           providers=pp.list_providers(),
                           active_provider=pp.get_active_provider(),
                           current_user=session.get("admin_username"))


@bp.route("/admin/fanhub/reports")
@admin_required
def admin_fanhub_reports():
    fs = mdb.fan_stats()
    ms = mdb.membership_stats()
    ps = mdb.payment_stats()
    registrations = mdb.registrations_by_day(30)
    breakdown = mdb.membership_breakdown()
    return render_template("fanhub_admin_reports.html", fs=fs, ms=ms, ps=ps,
                           registrations=registrations, breakdown=breakdown,
                           current_user=session.get("admin_username"))


@bp.route("/admin/fanhub/audit")
@admin_required
def admin_fanhub_audit():
    log = mdb.get_audit_log(300)
    return render_template("fanhub_admin_audit.html", log=log,
                           current_user=session.get("admin_username"))
