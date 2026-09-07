"""
membership_db.py — Ekhaya FC Fan Hub data access layer.

All SQLite access for the fan membership system lives here so the web layer
stays thin and a payment provider can be swapped without touching queries.
"""

import sqlite3
import uuid
from datetime import datetime, timedelta
from database import get_connection

FAVOURITE_TEAMS = ["Main Team", "Reserve", "Women", "Youth"]


def now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def today():
    return datetime.utcnow().strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def get_setting(key, default=None):
    conn = get_connection()
    row = conn.execute(
        "SELECT value FROM site_settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_connection()
    conn.execute(
        "INSERT INTO site_settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value))
    conn.commit()
    conn.close()


def get_all_settings():
    conn = get_connection()
    rows = conn.execute(
        "SELECT key, value FROM site_settings ORDER BY key").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


# ---------------------------------------------------------------------------
# Membership packages
# ---------------------------------------------------------------------------
def get_packages(active_only=True):
    conn = get_connection()
    q = "SELECT * FROM membership_packages"
    if active_only:
        q += " WHERE is_active = 1"
    q += " ORDER BY level"
    rows = conn.execute(q).fetchall()
    conn.close()
    return rows


def get_all_packages():
    return get_packages(active_only=False)


def get_package(package_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM membership_packages WHERE id = ?",
        (package_id,)).fetchone()
    conn.close()
    return row


def get_package_by_name(name):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM membership_packages WHERE name = ?", (name,)).fetchone()
    conn.close()
    return row


def add_package(name, level, price, duration_days, description=None,
                benefits=None, is_active=1):
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO membership_packages
            (name, level, price_mwk, duration_days, is_active, description, benefits)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, level, float(price), int(duration_days), int(is_active),
          description, benefits))
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid


def update_package(package_id, name, level, price, duration_days,
                   description=None, benefits=None, is_active=1):
    conn = get_connection()
    conn.execute("""
        UPDATE membership_packages SET name=?, level=?, price_mwk=?,
            duration_days=?, description=?, benefits=?, is_active=?
        WHERE id=?
    """, (name, int(level), float(price), int(duration_days), description,
          benefits, int(is_active), package_id))
    conn.commit()
    conn.close()


def set_package_active(package_id, is_active):
    conn = get_connection()
    conn.execute("UPDATE membership_packages SET is_active=? WHERE id=?",
                 (1 if is_active else 0, package_id))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Fans (registered members)
# ---------------------------------------------------------------------------
def next_member_number():
    conn = get_connection()
    row = conn.execute(
        "SELECT member_number FROM fan_members "
        "WHERE member_number LIKE 'EKH-FAN-%' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row and row["member_number"]:
        try:
            seq = int(row["member_number"].split("-")[-1]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return "EKH-FAN-%06d" % seq


def create_fan_member(first_name, last_name, dob, gender, phone, email,
                      district, password_hash, favourite_team,
                      emergency_name=None, emergency_phone=None):
    conn = get_connection()
    member_number = next_member_number()
    cur = conn.execute("""
        INSERT INTO fan_members
            (member_number, first_name, last_name, dob, gender, phone, email,
             district, password_hash, favourite_team,
             emergency_name, emergency_phone, is_active, is_verified,
             created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1,0,?)
    """, (member_number, first_name, last_name, dob, gender, phone, email,
          district, password_hash, favourite_team, emergency_name,
          emergency_phone, now()))
    conn.commit()
    fid = cur.lastrowid
    conn.close()
    return fid, member_number


def get_fan_by_email(email):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM fan_members WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row


def get_fan_by_id(fan_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM fan_members WHERE id = ?", (fan_id,)).fetchone()
    conn.close()
    return row


def get_fan_by_member_number(number):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM fan_members WHERE member_number = ?",
        (number,)).fetchone()
    conn.close()
    return row


def search_fans(query=None, active=None):
    conn = get_connection()
    sql = "SELECT * FROM fan_members WHERE 1=1"
    params = []
    if query:
        like = "%%%s%%" % query
        sql += (" AND (first_name LIKE ? OR last_name LIKE ? OR email LIKE ? "
                "OR phone LIKE ? OR member_number LIKE ? OR district LIKE ?)")
        params = [like] * 6
    if active is not None:
        sql += " AND is_active = ?"
        params.append(1 if active else 0)
    sql += " ORDER BY id DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def update_fan_profile(fan_id, **fields):
    conn = get_connection()
    for k, v in fields.items():
        conn.execute("UPDATE fan_members SET {}=? WHERE id=?".format(k),
                     (v, fan_id))
    conn.commit()
    conn.close()


def update_fan_photo(fan_id, path):
    conn = get_connection()
    conn.execute("UPDATE fan_members SET profile_photo=? WHERE id=?",
                 (path, fan_id))
    conn.commit()
    conn.close()


def set_fan_active(fan_id, is_active):
    conn = get_connection()
    conn.execute("UPDATE fan_members SET is_active=? WHERE id=?",
                 (1 if is_active else 0, fan_id))
    conn.commit()
    conn.close()


def set_fan_verified(fan_id, verified):
    conn = get_connection()
    conn.execute("UPDATE fan_members SET is_verified=? WHERE id=?",
                 (1 if verified else 0, fan_id))
    conn.commit()
    conn.close()


def touch_login(fan_id):
    conn = get_connection()
    conn.execute("UPDATE fan_members SET last_login=? WHERE id=?",
                 (now(), fan_id))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Email OTP verification
# ---------------------------------------------------------------------------
def set_otp(fan_id, code, ttl_minutes=10):
    """Store a one-time password for a fan, with attempt counter reset."""
    from datetime import datetime as _dt
    exp = (_dt.utcnow() + timedelta(minutes=ttl_minutes)).strftime(
        "%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    conn.execute("""
        UPDATE fan_members SET otp_code=?, otp_expires_at=?, otp_attempts=0
        WHERE id=?
    """, (code, exp, fan_id))
    conn.commit()
    conn.close()


def clear_otp(fan_id):
    conn = get_connection()
    conn.execute("""
        UPDATE fan_members SET otp_code=NULL, otp_expires_at=NULL,
            otp_attempts=0 WHERE id=?
    """, (fan_id,))
    conn.commit()
    conn.close()


def mark_email_verified(fan_id):
    conn = get_connection()
    conn.execute("""
        UPDATE fan_members SET is_verified=1, email_verified_at=?, otp_code=NULL,
            otp_expires_at=NULL, otp_attempts=0 WHERE id=?
    """, (now(), fan_id))
    conn.commit()
    conn.close()


def bump_otp_attempt(fan_id):
    conn = get_connection()
    conn.execute("UPDATE fan_members SET otp_attempts = "
                 "COALESCE(otp_attempts,0) + 1 WHERE id=?", (fan_id,))
    conn.commit()
    conn.close()


def get_fan_otp_state(fan_id):
    """Return dict with the fan's stored OTP code, expiry, and attempt count."""
    fan = get_fan_by_id(fan_id)
    if not fan:
        return None
    return {"code": fan["otp_code"], "expires_at": fan["otp_expires_at"],
            "attempts": fan["otp_attempts"] or 0,
            "verified": bool(fan["is_verified"])}


# ---------------------------------------------------------------------------
# Membership records (a fan's enrolment)
# ---------------------------------------------------------------------------
def get_memberships_for_fan(fan_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT m.*, p.name AS package_name, p.level AS package_level,
               p.currency AS package_currency
        FROM fan_memberships m
        LEFT JOIN membership_packages p ON m.package_id = p.id
        WHERE m.fan_id = ?
        ORDER BY m.id DESC
    """, (fan_id,)).fetchall()
    conn.close()
    return rows


def get_current_membership(fan_id):
    """Return the most recent active-or-pending membership (or the latest)."""
    rows = get_memberships_for_fan(fan_id)
    if not rows:
        return None
    return rows[0]


def status_of_membership(m):
    """Recompute effective status: EXPIRED if past expiry, else stored value."""
    status = m["status"]
    if status == "ACTIVE" and m["expiry_date"]:
        try:
            if datetime.strptime(str(m["expiry_date"]), "%Y-%m-%d") < \
               datetime.utcnow():
                return "EXPIRED"
        except ValueError:
            pass
    return status


def get_active_membership(fan_id):
    for m in get_memberships_for_fan(fan_id):
        if status_of_membership(m) == "ACTIVE":
            return m
    return None


def create_membership(fan_id, package_id, start_date, expiry_date,
                      amount_paid, payment_ref):
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO fan_memberships
            (fan_id, package_id, status, start_date, expiry_date,
             amount_paid, payment_ref, created_at)
        VALUES (?,?,?,?,?,?,?,?)
    """, (fan_id, package_id, "PENDING", start_date, expiry_date,
          amount_paid or 0, payment_ref, now()))
    conn.commit()
    mid = cur.lastrowid
    conn.close()
    return mid


def activate_membership(membership_id):
    conn = get_connection()
    # Expire any other ACTIVE memberships for this fan first (handled in caller).
    conn.execute("UPDATE fan_memberships SET status='ACTIVE' WHERE id=?",
                 (membership_id,))
    conn.commit()
    conn.close()


def set_membership_status(membership_id, status):
    conn = get_connection()
    conn.execute("UPDATE fan_memberships SET status=? WHERE id=?",
                 (status, membership_id))
    conn.commit()
    conn.close()


def expire_stale_memberships():
    conn = get_connection()
    conn.execute("""
        UPDATE fan_memberships SET status='EXPIRED'
        WHERE status='ACTIVE' AND expiry_date IS NOT NULL
          AND date(expiry_date) < date('now')
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
def create_payment(fan_id, membership_id, package_id, amount, provider,
                   reference, item_type="membership", booking_id=None):
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO fan_payments
            (fan_id, membership_id, package_id, amount, currency, provider,
             reference, status, item_type, booking_id, created_at)
        VALUES (?,?,?,?,?,?,?, 'PENDING', ?, ?, ?)
    """, (fan_id, membership_id, package_id, float(amount), "MWK", provider,
          reference, item_type, booking_id, now()))
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid


def get_payment(payment_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM fan_payments WHERE id=?",
                       (payment_id,)).fetchone()
    conn.close()
    return row


def get_payment_by_reference(reference):
    conn = get_connection()
    row = conn.execute("SELECT * FROM fan_payments WHERE reference=?",
                       (reference,)).fetchone()
    conn.close()
    return row


def get_payments_for_fan(fan_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.*, pk.name AS package_name,
               tb.seat_type_name AS ticket_seat_name, tb.match_date AS ticket_date,
               tb.home_team AS ticket_home, tb.away_team AS ticket_away,
               tb.booking_ref
        FROM fan_payments p
        LEFT JOIN membership_packages pk ON p.package_id = pk.id
        LEFT JOIN ticket_bookings tb ON p.booking_id = tb.id
        WHERE p.fan_id = ?
        ORDER BY p.id DESC
    """, (fan_id,)).fetchall()
    conn.close()
    return rows


def get_all_payments(limit=500):
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.*, f.first_name, f.last_name, f.member_number,
               pk.name AS package_name,
               tb.seat_type_name AS ticket_seat_name, tb.match_date AS ticket_date,
               tb.home_team AS ticket_home, tb.away_team AS ticket_away,
               tb.booking_ref
        FROM fan_payments p
        LEFT JOIN fan_members f ON p.fan_id = f.id
        LEFT JOIN membership_packages pk ON p.package_id = pk.id
        LEFT JOIN ticket_bookings tb ON p.booking_id = tb.id
        ORDER BY p.id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows


def set_payment_success(payment_id, provider_txn_id=None):
    conn = get_connection()
    conn.execute("""
        UPDATE fan_payments
        SET status='SUCCESSFUL', provider_txn_id=?, paid_at=?
        WHERE id=?
    """, (provider_txn_id, now(), payment_id))
    conn.commit()
    conn.close()


def set_payment_status(payment_id, status, provider_txn_id=None):
    conn = get_connection()
    conn.execute("""
        UPDATE fan_payments SET status=?, provider_txn_id=? WHERE id=?
    """, (status, provider_txn_id, payment_id))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Matchday ticket booking (seat types, bookings, e-tickets)
# ---------------------------------------------------------------------------
def get_seat_types(active_only=True):
    conn = get_connection()
    q = "SELECT * FROM ticket_seat_types"
    if active_only:
        q += " WHERE is_active = 1"
    q += " ORDER BY sort_order, id"
    rows = conn.execute(q).fetchall()
    conn.close()
    return rows


def get_all_seat_types():
    return get_seat_types(active_only=False)


def get_seat_type(seat_type_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM ticket_seat_types WHERE id=?",
                       (seat_type_id,)).fetchone()
    conn.close()
    return row


def add_seat_type(name, price_mwk, capacity, description=None, is_active=1,
                  sort_order=0):
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO ticket_seat_types
            (name, price_mwk, capacity, description, is_active, sort_order)
        VALUES (?,?,?,?,?,?)
    """, (name, float(price_mwk), int(capacity), description, int(is_active),
          int(sort_order)))
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def update_seat_type(seat_type_id, name, price_mwk, capacity, description=None,
                     is_active=1, sort_order=0):
    conn = get_connection()
    conn.execute("""
        UPDATE ticket_seat_types SET name=?, price_mwk=?, capacity=?,
            description=?, is_active=?, sort_order=? WHERE id=?
    """, (name, float(price_mwk), int(capacity), description, int(is_active),
          int(sort_order), seat_type_id))
    conn.commit()
    conn.close()


def set_seat_type_active(seat_type_id, is_active):
    conn = get_connection()
    conn.execute("UPDATE ticket_seat_types SET is_active=? WHERE id=?",
                 (1 if is_active else 0, seat_type_id))
    conn.commit()
    conn.close()


def available_seats(fixture_id, seat_type_id):
    """Capacity minus seats already committed (PENDING or paid bookings)."""
    conn = get_connection()
    row = conn.execute("""
        SELECT capacity - COALESCE((
            SELECT SUM(qty) FROM ticket_bookings
            WHERE fixture_id=? AND seat_type_id=? AND status IN ('PENDING','SUCCESSFUL')
        ), 0) AS avail
        FROM ticket_seat_types WHERE id=?
    """, (fixture_id, seat_type_id, seat_type_id)).fetchone()
    conn.close()
    if row is None:
        return 0
    return max(int(row["avail"]), 0)


def next_ticket_number():
    conn = get_connection()
    row = conn.execute(
        "SELECT ticket_number FROM tickets "
        "WHERE ticket_number LIKE 'EKH-TKT-%' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row and row["ticket_number"]:
        try:
            seq = int(row["ticket_number"].split("-")[-1]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return "EKH-TKT-%06d" % seq


def create_ticket_booking(fan_id, fixture, seat_type, qty, unit_price,
                          seat_label=None):
    """Create a PENDING booking, snapshotting fixture details (the seed_fixtures
    wipe rebuilds the fixtures table each startup, so we keep a copy here)."""
    total = round(float(unit_price) * int(qty), 2)
    ref = "BK-%s" % uuid.uuid4().hex[:10].upper()
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO ticket_bookings
            (booking_ref, fan_id, fixture_id, home_team, away_team, match_date,
             kick_off, venue, seat_type_id, seat_type_name, qty, seat_label,
             unit_price, total_mwk, status, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'PENDING', ?)
    """, (ref, fan_id, fixture["id"], fixture["home_team"], fixture["away_team"],
          fixture["match_date"], fixture["kick_off"], fixture["venue"],
          seat_type["id"], seat_type["name"], int(qty), seat_label,
          float(unit_price), total, now()))
    conn.commit()
    bid = cur.lastrowid
    conn.close()
    return bid, ref


def get_booking(booking_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM ticket_bookings WHERE id=?",
                       (booking_id,)).fetchone()
    conn.close()
    return row


def get_booking_by_ref(reference):
    conn = get_connection()
    row = conn.execute("SELECT * FROM ticket_bookings WHERE booking_ref=?",
                       (reference,)).fetchone()
    conn.close()
    return row


def set_booking_status(booking_id, status):
    conn = get_connection()
    conn.execute("UPDATE ticket_bookings SET status=? WHERE id=?",
                 (status, booking_id))
    conn.commit()
    conn.close()


def get_bookings_for_fan(fan_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM ticket_bookings WHERE fan_id=? ORDER BY id DESC",
        (fan_id,)).fetchall()
    conn.close()
    return rows


def get_all_bookings(limit=500):
    conn = get_connection()
    rows = conn.execute("""
        SELECT b.*, f.first_name, f.last_name, f.member_number
        FROM ticket_bookings b
        LEFT JOIN fan_members f ON b.fan_id = f.id
        ORDER BY b.id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows


def create_tickets_for_booking(booking):
    """Issue one e-ticket per seat for a SUCCESSFUL booking."""
    import uuid as _uuid
    conn = get_connection()
    # Compute the next ticket numbers in the SAME transaction so concurrent
    # inserts within this booking can't collide on ticket_number.
    row = conn.execute(
        "SELECT ticket_number FROM tickets WHERE ticket_number LIKE "
        "'EKH-TKT-%' ORDER BY id DESC LIMIT 1").fetchone()
    if row and row["ticket_number"]:
        try:
            seq = int(row["ticket_number"].split("-")[-1]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    for i in range(int(booking["qty"])):
        conn.execute("""
            INSERT INTO tickets
                (booking_id, fan_id, fixture_id, home_team, away_team,
                 match_date, kick_off, venue, seat_type_id, seat_type_name,
                 ticket_number, qr_secret, seat_label, status, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, 'ISSUED', ?)
        """, (booking["id"], booking["fan_id"], booking["fixture_id"],
              booking["home_team"], booking["away_team"], booking["match_date"],
              booking["kick_off"], booking["venue"], booking["seat_type_id"],
              booking["seat_type_name"], "EKH-TKT-%06d" % (seq + i),
              "TKT-%s" % _uuid.uuid4().hex[:20].upper(),
              booking["seat_label"], now()))
    conn.commit()
    conn.close()
    return get_tickets_for_booking(booking["id"])


def get_tickets_for_fan(fan_id, limit=100):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM tickets WHERE fan_id=? ORDER BY id DESC LIMIT ?",
        (fan_id, limit)).fetchall()
    conn.close()
    return rows


def get_tickets_for_booking(booking_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM tickets WHERE booking_id=? ORDER BY id",
        (booking_id,)).fetchall()
    conn.close()
    return rows


def get_ticket_by_id(ticket_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM tickets WHERE id=?",
                       (ticket_id,)).fetchone()
    conn.close()
    return row


def lookup_ticket_by_qr_secret(secret):
    """Staff verification: find the ticket whose QR secret matches."""
    conn = get_connection()
    row = conn.execute("""
        SELECT t.*, f.first_name, f.last_name, f.member_number,
               f.email, f.phone
        FROM tickets t
        LEFT JOIN fan_members f ON t.fan_id = f.id
        WHERE t.qr_secret = ?
    """, (secret,)).fetchone()
    conn.close()
    return row


def set_ticket_scanned(ticket_id):
    conn = get_connection()
    conn.execute("UPDATE tickets SET status='USED', scanned_at=? WHERE id=?",
                 (now(), ticket_id))
    conn.commit()
    conn.close()


def ticket_stats():
    conn = get_connection()
    bookings = conn.execute(
        "SELECT COUNT(*) FROM ticket_bookings WHERE status='SUCCESSFUL'"
    ).fetchone()[0]
    issued = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE status='ISSUED'").fetchone()[0]
    used = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE status='USED'").fetchone()[0]
    revenue = conn.execute(
        "SELECT COALESCE(SUM(total_mwk),0) FROM ticket_bookings "
        "WHERE status='SUCCESSFUL'").fetchone()[0]
    conn.close()
    return {"bookings": bookings, "issued": issued, "used": used,
            "revenue": revenue}


def ticket_sales_per_fixture(limit=20):
    conn = get_connection()
    rows = conn.execute("""
        SELECT fixture_id, home_team, away_team, match_date, kick_off, venue,
               COUNT(DISTINCT id) AS bookings,
               SUM(CASE WHEN status='SUCCESSFUL' THEN qty ELSE 0 END) AS sold,
               SUM(CASE WHEN status='SUCCESSFUL' THEN total_mwk ELSE 0 END) AS revenue
        FROM ticket_bookings
        GROUP BY fixture_id, home_team, away_team, match_date, kick_off, venue
        ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Membership cards
# ---------------------------------------------------------------------------
def get_card_for_fan(fan_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT c.*, m.status AS membership_status, m.expiry_date,
               m.start_date, p.name AS package_name, p.level AS package_level
        FROM fan_cards c
        LEFT JOIN fan_memberships m ON c.membership_id = m.id
        LEFT JOIN membership_packages p ON m.package_id = p.id
        WHERE c.fan_id = ? ORDER BY c.id DESC LIMIT 1
    """, (fan_id,)).fetchone()
    conn.close()
    return row


def get_card_by_id(card_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM fan_cards WHERE id=?",
                       (card_id,)).fetchone()
    conn.close()
    return row


def deactivate_cards_for_fan(fan_id):
    conn = get_connection()
    conn.execute("UPDATE fan_cards SET is_active=0 WHERE fan_id=?",
                 (fan_id,))
    conn.commit()
    conn.close()


def create_card(fan_id, membership_id, card_number, qr_secret):
    conn = get_connection()
    deactivate_cards_for_fan(fan_id)
    cur = conn.execute("""
        INSERT INTO fan_cards
            (fan_id, membership_id, card_number, qr_secret, generated_at, is_active)
        VALUES (?,?,?,?,?,1)
    """, (fan_id, membership_id, card_number, qr_secret, now()))
    conn.commit()
    cid = cur.lastrowid
    conn.close()
    return cid


def lookup_card_by_qr_secret(secret):
    """Staff verification: find the card whose QR (secret) matches."""
    conn = get_connection()
    row = conn.execute("""
        SELECT c.*, f.first_name, f.last_name, f.member_number,
               f.profile_photo, f.email, f.phone,
               m.status AS membership_status, m.expiry_date, m.package_id,
               p.name AS package_name
        FROM fan_cards c
        JOIN fan_members f ON c.fan_id = f.id
        LEFT JOIN fan_memberships m ON c.membership_id = m.id
        LEFT JOIN membership_packages p ON m.package_id = p.id
        WHERE c.qr_secret = ?
    """, (secret,)).fetchone()
    conn.close()
    return row


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
def add_notification(fan_id, title, body=None):
    conn = get_connection()
    conn.execute("""
        INSERT INTO fan_notifications (fan_id, title, body, read, created_at)
        VALUES (?,?,?,0,?)
    """, (fan_id, title, body, now()))
    conn.commit()
    conn.close()


def get_notifications(fan_id, limit=20):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM fan_notifications WHERE fan_id=?
        ORDER BY id DESC LIMIT ?
    """, (fan_id, limit)).fetchall()
    conn.close()
    return rows


def unread_notifications_count(fan_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) FROM fan_notifications WHERE fan_id=? AND read=0",
        (fan_id,)).fetchone()
    conn.close()
    return row[0]


def mark_notifications_read(fan_id):
    conn = get_connection()
    conn.execute("UPDATE fan_notifications SET read=1 WHERE fan_id=?",
                 (fan_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------
def audit(admin_user, action, details=None, actor_type="admin"):
    conn = get_connection()
    conn.execute("""
        INSERT INTO audit_log (admin_user, actor_type, action, details, created_at)
        VALUES (?,?,?,?,?)
    """, (admin_user, actor_type, action, details, now()))
    conn.commit()
    conn.close()


def get_audit_log(limit=200):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
        (limit,)).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Content: news, announcements, benefits
# ---------------------------------------------------------------------------
def add_news(title, body, image=None, is_active=1):
    conn = get_connection()
    conn.execute("""
        INSERT INTO fan_news (title, body, image, published_at, is_active)
        VALUES (?,?,?,?,?)
    """, (title, body, image, now(), int(is_active)))
    conn.commit()
    conn.close()


def get_news(active_only=True, limit=20):
    conn = get_connection()
    q = "SELECT * FROM fan_news"
    if active_only:
        q += " WHERE is_active=1"
    q += " ORDER BY id DESC LIMIT ?"
    rows = conn.execute(q, (limit,)).fetchall()
    conn.close()
    return rows


def get_all_news():
    return get_news(active_only=False)


def add_announcement(title, body, is_active=1):
    conn = get_connection()
    conn.execute("""
        INSERT INTO fan_announcements (title, body, published_at, is_active)
        VALUES (?,?,?,?)
    """, (title, body, now(), int(is_active)))
    conn.commit()
    conn.close()


def get_announcements(active_only=True, limit=20):
    conn = get_connection()
    q = "SELECT * FROM fan_announcements"
    if active_only:
        q += " WHERE is_active=1"
    q += " ORDER BY id DESC LIMIT ?"
    rows = conn.execute(q, (limit,)).fetchall()
    conn.close()
    return rows


def add_benefit(name, description, is_active=1):
    conn = get_connection()
    conn.execute("""
        INSERT INTO fan_benefits (name, description, is_active)
        VALUES (?,?,?)
    """, (name, description, int(is_active)))
    conn.commit()
    conn.close()


def get_benefits(active_only=True):
    conn = get_connection()
    q = "SELECT * FROM fan_benefits"
    if active_only:
        q += " WHERE is_active=1"
    q += " ORDER BY id"
    rows = conn.execute(q).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Admin / CEO statistics & reports
# ---------------------------------------------------------------------------
def fan_stats():
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM fan_members").fetchone()[0]
    active = conn.execute(
        "SELECT COUNT(*) FROM fan_members WHERE is_active=1").fetchone()[0]
    conn.close()
    return {"total": total, "active": active}


def membership_stats():
    conn = get_connection()
    active = conn.execute(
        "SELECT COUNT(*) FROM fan_memberships WHERE status='ACTIVE'"
    ).fetchone()[0]
    expired = conn.execute(
        "SELECT COUNT(*) FROM fan_memberships WHERE status='EXPIRED'"
    ).fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM fan_memberships WHERE status='PENDING'"
    ).fetchone()[0]
    conn.close()
    return {"active": active, "expired": expired, "pending": pending}


def payment_stats():
    conn = get_connection()
    successful = conn.execute(
        "SELECT COUNT(*) FROM fan_payments WHERE status='SUCCESSFUL'"
    ).fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM fan_payments WHERE status='PENDING'"
    ).fetchone()[0]
    failed = conn.execute(
        "SELECT COUNT(*) FROM fan_payments WHERE status='FAILED'"
    ).fetchone()[0]
    revenue = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM fan_payments "
        "WHERE status='SUCCESSFUL'").fetchone()[0]
    conn.close()
    return {"successful": successful, "pending": pending, "failed": failed,
            "revenue": revenue}


def registrations_by_day(days=30):
    conn = get_connection()
    rows = conn.execute("""
        SELECT substr(created_at,1,10) AS day, COUNT(*) AS n
        FROM fan_members
        GROUP BY day ORDER BY day DESC LIMIT ?
    """, (days,)).fetchall()
    conn.close()
    return [{"day": r["day"], "n": r["n"]} for r in rows]


def membership_breakdown():
    conn = get_connection()
    rows = conn.execute("""
        SELECT COALESCE(p.name, 'None') AS package, COUNT(m.id) AS n
        FROM membership_packages p
        LEFT JOIN fan_memberships m ON m.package_id = p.id
          AND m.status = 'ACTIVE'
        GROUP BY p.id ORDER BY p.level
    """).fetchall()
    conn.close()
    return [{"package": r["package"], "n": r["n"]} for r in rows]
