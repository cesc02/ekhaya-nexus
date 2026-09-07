"""
app.py - Ekhaya Nexus Flask entry point.
Run: python3 app.py
"""

from flask import Flask, render_template, redirect, url_for, abort, request, flash, session
from functools import wraps
from werkzeug.utils import secure_filename
from PIL import Image
import os
from database import (
    init_db, get_all_teams, get_team_by_id, get_players_by_team,
    get_player_by_id, add_player, update_player_stats, update_player_photo, delete_player,
    get_team_stats, get_competitions_by_team, add_competition,
    get_matches_by_team, add_match, seed_demo_data,
    get_standings, get_league_names, get_all_fixtures, get_ekhaya_fixtures,
    seed_standings, seed_fixtures, seed_reserve_standings,
    check_admin, update_admin_password, admin_uses_default_password,
    get_all_players, get_all_competitions, get_all_matches,
    get_competition_by_id, update_competition, delete_competition,
    get_match_by_id, update_match, delete_match,
    update_standings_entry, update_standing_name,
    get_performance_matches, get_performance_stats, get_player_performance_stats,
    get_player_performance_matches, get_performance_minutes,
    get_performance_physical, seed_reference_performance,
    seed_performance_data, seed_competitions,
    get_player_medical, add_medical_record, update_medical_record, delete_medical_record, get_team_medical_summary,
    seed_medical,
    seed_main_team_stats,
    add_fan, get_all_fans, get_fan_by_id, update_fan, delete_fan,
    get_fan_stats, seed_fans,
    get_connection,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ekhaya-nexus-secret-key-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 7

import security
security.configure(app)

from fanhub import bp as fanhub_bp
app.register_blueprint(fanhub_bp)

PLAYER_PHOTO_DIR = os.path.join(app.root_path, "static", "img", "players")
os.makedirs(PLAYER_PHOTO_DIR, exist_ok=True)

ALLOWED_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}

init_db()
seed_fixtures()
seed_standings()
seed_reserve_standings()
seed_demo_data()
from reseed import run as seed_real_rosters
seed_real_rosters()
seed_medical()
seed_main_team_stats()
seed_performance_data()
seed_competitions()
seed_reference_performance()
seed_fans()

# Fan Hub seed data (idempotent): packages, settings, content.
import membership_db as mdb
if not mdb.get_packages(active_only=False):
    mdb.add_package("Basic Fan", 0, 0, 365, "Free supporter membership",
                    "News & fixtures", 1)
    mdb.add_package("Silver", 1, 20000, 365, "Silver supporter package",
                    "News, discounted match tickets", 1)
    mdb.add_package("Gold", 2, 50000, 365, "Gold supporter package",
                    "Priority tickets, exclusive content", 1)
    mdb.add_package("Premium", 3, 100000, 365, "Premium supporter package",
                    "VIP access, meet & greets, gifts", 1)
mdb.set_setting("active_payment_provider", "sandbox")
mdb.set_setting("sandbox_auto_success", "1")
if not mdb.get_news(active_only=True):
    mdb.add_news("Ekhaya FC back in action", "The squad returns to training ahead of the next matchweek.")
    mdb.add_announcement("Welcome to the Fan Hub", "Thank you for supporting Ekhaya FC.")
if not mdb.get_benefits(active_only=True):
    mdb.add_benefit("Match-day discounts", "Members save on ticket prices.")
    mdb.add_benefit("Exclusive news", "Early access to club announcements.")
    mdb.add_benefit("Fan events", "Invitations to supporter gatherings.")
if not mdb.get_seat_types(active_only=False):
    mdb.add_seat_type("Open Stand", 3000, 2500,
                      "General admission terrace", 1, 1)
    mdb.add_seat_type("Covered Stand", 5000, 1200,
                      "Reserved shaded seating", 1, 2)
    mdb.add_seat_type("VIP Seat", 10000, 300,
                      "Premium bucket seat near the tunnel", 1, 3)
    mdb.add_seat_type("Executive Lounge", 20000, 120,
                      "Lounge access with refreshments", 1, 4)
mdb.set_setting("max_tickets_per_fan", "6")
mdb.set_setting("ticket_member_discount_pct", "0")


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        bucket = "admin_login:%s:%s" % (username,
                                        request.remote_addr or "local")
        if not security.rate_limit(bucket, limit=5, window=300):
            flash("Too many login attempts. Please wait a few minutes.",
                  "error")
            return render_template("admin_login.html")
        if check_admin(username, password):
            session["admin_logged_in"] = True
            session["admin_username"] = username
            security.reset_rate(bucket)
            if admin_uses_default_password(username):
                flash("Security: you are using the default password. "
                      "Change it now at /admin/change-password.", "warning")
            flash("Welcome back, Super Admin!", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("admin_login.html")


@app.route("/admin/change-password", methods=["GET", "POST"])
@admin_required
def admin_change_password():
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        username = session.get("admin_username", "admin")
        if not check_admin(username, current):
            flash("Current password is incorrect.", "error")
        elif len(new) < 10:
            flash("New password must be at least 10 characters.", "error")
        elif new != confirm:
            flash("New passwords do not match.", "error")
        elif new == current:
            flash("New password must differ from the current one.", "error")
        else:
            update_admin_password(username, new)
            flash("Password changed successfully.", "success")
            return redirect(url_for("admin_dashboard"))
    return render_template("admin_change_password.html",
                           current_user=session.get("admin_username"))


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_username", None)
    flash("Logged out.", "info")
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    teams = []
    for t in get_all_teams():
        stats = get_team_stats(t["id"])
        comps = get_competitions_by_team(t["id"])
        team_league = {3: "FincaDL1"}.get(t["id"], "FDH Premiership")
        standings = get_standings(team_league)
        pos = None
        name_key = "Ekhaya Reserve" if t["id"] == 3 else "Ekhaya"
        for s in standings:
            if s["team_name"] == name_key:
                pos = s["position"]
                break
        teams.append({
            "id": t["id"], "name": t["name"],
            "players": stats["total_players"],
            "goals": stats["total_goals"],
            "competitions": len(comps),
            "league_position": pos,
            "league": team_league,
        })
    return render_template("admin_dashboard.html", teams=teams,
                           current_user=session.get("admin_username"))


@app.route("/")
def team_select():
    """Public landing: the Ekhaya FC Fan Hub (membership system)."""
    teams = get_all_teams()
    packages = mdb.get_packages(active_only=True)
    return render_template("fan_home.html", teams=teams, packages=packages)


@app.route("/club")
def club_landing():
    """Club / team management home — kept for staff & admin access."""
    teams = get_all_teams()
    return render_template("team_select.html", teams=teams)


@app.route("/fans/join", methods=["GET", "POST"])
def fans_join():
    """Public membership signup form."""
    if request.method == "POST":
        add_fan(
            request.form.get("first_name", "").strip(),
            request.form.get("last_name", "").strip(),
            email=request.form.get("email", "").strip() or None,
            phone=request.form.get("phone", "").strip() or None,
            city=request.form.get("city", "").strip() or None,
            membership_tier=request.form.get("membership_tier", "Fan"),
            membership_status="Active",
            joined_date=request.form.get("joined_date", "").strip() or None,
            source="Web",
            notes=None,
        )
        flash("Welcome to the Ekhaya FC family! Your membership request has been received.", "success")
        return redirect(url_for("fans_join"))
    return render_template("fans_join.html")


@app.route("/team/<int:team_id>")
def dashboard(team_id):
    team = get_team_by_id(team_id)
    if team is None:
        abort(404)
    stats = get_team_stats(team_id)
    competitions = get_competitions_by_team(team_id)
    team_leagues = {1: "FDH Premiership", 3: "FincaDL1"}
    team_league = team_leagues.get(team_id)
    standings = get_standings(team_league) if team_league else []
    standings_team_name = "Ekhaya Reserve" if team_id == 3 else "Ekhaya"
    ekhaya_fixtures = get_ekhaya_fixtures() if team_id == 1 else []
    upcoming = [f for f in ekhaya_fixtures if f["status"] != "played"][:5]
    recent = [f for f in ekhaya_fixtures if f["status"] == "played"][-5:]
    return render_template("dashboard.html", team=team, stats=stats,
                           competitions=competitions, fixtures=upcoming,
                           recent_results=recent,
                           standings=standings, league_name=team_league,
                           standings_team_name=standings_team_name)


@app.route("/team/<int:team_id>/players")
def players(team_id):
    team = get_team_by_id(team_id)
    if team is None:
        abort(404)
    player_list = get_players_by_team(team_id)
    return render_template("players.html", team=team, players=player_list)


@app.route("/team/<int:team_id>/players/add", methods=["GET", "POST"])
def add_player_route(team_id):
    team = get_team_by_id(team_id)
    if team is None:
        abort(404)
    if request.method == "POST":
        add_player(
            team_id,
            request.form["first_name"],
            request.form["last_name"],
            int(request.form["squad_number"]),
            request.form["position"],
            request.form.get("date_of_birth", ""),
            request.form.get("nationality", ""),
            request.form.get("strong_foot", "Right")
        )
        flash("Player added successfully!", "success")
        return redirect(url_for("players", team_id=team_id))
    return render_template("add_player.html", team=team)


@app.route("/team/<int:team_id>/players/<int:player_id>")
def player_profile(team_id, player_id):
    team = get_team_by_id(team_id)
    if team is None:
        abort(404)
    player = get_player_by_id(player_id)
    if player is None or player["team_id"] != team_id:
        abort(404)
    perf = get_player_performance_stats(player_id)
    perf["distance_km"] = round(perf["total_distance"] / 1000.0, 1)
    perf_matches = [dict(m) for m in get_player_performance_matches(player_id)]
    for m in perf_matches:
        m["distance_km"] = round((m["distance_m"] or 0) / 1000.0, 1)
        if m["home_away"] == "home":
            m["result"] = ("W" if m["home_score"] > m["away_score"]
                           else "D" if m["home_score"] == m["away_score"] else "L")
        else:
            m["result"] = ("W" if m["away_score"] > m["home_score"]
                           else "D" if m["away_score"] == m["home_score"] else "L")
        m["result_class"] = m["result"].lower()
    return render_template("player_profile.html", team=team, player=player,
                           perf=perf, perf_matches=perf_matches)


@app.route("/team/<int:team_id>/players/<int:player_id>/edit", methods=["GET", "POST"])
def edit_player(team_id, player_id):
    team = get_team_by_id(team_id)
    if team is None:
        abort(404)
    player = get_player_by_id(player_id)
    if player is None or player["team_id"] != team_id:
        abort(404)
    if request.method == "POST":
        update_player_stats(
            player_id,
            goals=int(request.form.get("goals", 0)),
            assists=int(request.form.get("assists", 0)),
            yellow_cards=int(request.form.get("yellow_cards", 0)),
            red_cards=int(request.form.get("red_cards", 0)),
            appearances=int(request.form.get("appearances", 0)),
            minutes_played=int(request.form.get("minutes_played", 0)),
            distance_km=float(request.form.get("distance_km", 0)),
        )
        flash("Stats updated!", "success")
        return redirect(url_for("player_profile", team_id=team_id, player_id=player_id))
    return render_template("edit_player.html", team=team, player=player)


@app.route("/team/<int:team_id>/players/<int:player_id>/photo", methods=["POST"])
def upload_player_photo(team_id, player_id):
    team = get_team_by_id(team_id)
    if team is None:
        abort(404)
    player = get_player_by_id(player_id)
    if player is None or player["team_id"] != team_id:
        abort(404)
    file = request.files.get("photo")
    if file is None or file.filename == "":
        flash("No photo selected.", "error")
        return redirect(url_for("player_profile", team_id=team_id, player_id=player_id))
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_PHOTO_EXT:
        flash("Photo must be JPG, PNG or WebP.", "error")
        return redirect(url_for("player_profile", team_id=team_id, player_id=player_id))
    # Verify the uploaded file is a real image (prevents data-exfiltration)
    try:
        img = Image.open(file.stream)
        img.verify()
        img.format  # force load to ensure it's not a crafted blob
    except Exception:
        flash("Invalid image file.", "error")
        return redirect(url_for("player_profile", team_id=team_id, player_id=player_id))
    for old in os.listdir(PLAYER_PHOTO_DIR):
        if old.startswith(f"p{player_id}_"):
            os.remove(os.path.join(PLAYER_PHOTO_DIR, old))
    filename = f"p{player_id}{ext}"
    file.save(os.path.join(PLAYER_PHOTO_DIR, filename))
    photo_url = f"img/players/{filename}"
    update_player_photo(player_id, photo_url)
    flash("Photo updated!", "success")
    return redirect(url_for("player_profile", team_id=team_id, player_id=player_id))


@app.route("/team/<int:team_id>/players/<int:player_id>/delete", methods=["POST"])
def delete_player_route(team_id, player_id):
    player = get_player_by_id(player_id)
    if player is None or player["team_id"] != team_id:
        abort(404)
    delete_player(player_id)
    flash("Player removed.", "info")
    return redirect(url_for("players", team_id=team_id))


@app.route("/team/<int:team_id>/competitions")
def competitions(team_id):
    team = get_team_by_id(team_id)
    if team is None:
        abort(404)
    comps = get_competitions_by_team(team_id)
    grouped = {"league": [], "cup": [], "international": [], "friendly": []}
    for c in comps:
        grouped.get(c["comp_type"], grouped["league"]).append(c)
    return render_template("competitions.html", team=team, competitions=comps,
                           grouped=grouped)


@app.route("/team/<int:team_id>/competitions/add", methods=["GET", "POST"])
def add_competition_route(team_id):
    team = get_team_by_id(team_id)
    if team is None:
        abort(404)
    if request.method == "POST":
        add_competition(
            team_id,
            request.form["name"],
            request.form["comp_type"],
            request.form.get("season", "2025/26")
        )
        flash("Competition added!", "success")
        return redirect(url_for("competitions", team_id=team_id))
    return render_template("add_competition.html", team=team)


@app.route("/team/<int:team_id>/competitions/<int:comp_id>")
def competition_detail(team_id, comp_id):
    team = get_team_by_id(team_id)
    if team is None:
        abort(404)
    comp = get_competition_by_id(comp_id)
    if comp is None:
        abort(404)
    matches = get_matches_by_team(team_id, comp_id)
    upcoming = []
    if comp and comp["comp_type"] == "league":
        upcoming = [f for f in get_ekhaya_fixtures() if f["status"] != "played"]
    logo_map = {
        "Big Bullets": "nyasa-bullets.png", "Blue Eagles": "blue-eagles.png",
        "Chitipa United": "chitipa.png", "Civo Utd": "civo.png",
        "Creck Sporting": "creck.png", "Dedza Dynamos": "dedza.png",
        "Kamuzu Barracks": "kamuzu-barracks.png", "Karonga United": "karonga.png",
        "MAFCO": "mafco.png", "Masters FC": "masters-fc.png",
        "Mighty Tigers": "mighty-tigers.png", "Mighty Wanderers": "wanderers.png",
        "Mitundu Baptist": "luanar.png", "Moyale Barracks": "moyale.png",
        "Mzuzu City": "mzuzu-city.png", "Red Lions": "red-lions.png",
        "Silver Strikers": "silver-strikers.png", "Songwe Border": "songwe-border.png",
        "FCB Nyasa Big Bullets": "nyasa-bullets.png",
    }
    matches = get_matches_by_team(team_id, comp_id)
    upcoming = []
    standings = []
    if comp and comp["comp_type"] == "league":
        upcoming = [f for f in get_ekhaya_fixtures() if f["status"] != "played"]
        from database import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT position, team_name, logo_file, played, won, drawn, lost,
                   goals_for, goals_against, goal_diff, points, form
            FROM league_standings
            WHERE league_name = ?
            ORDER BY position
        """, (comp['name'],))
        standings = cur.fetchall()
        conn.close()
    return render_template("competition_detail.html", team=team,
                           comp=comp, matches=matches, comp_id=comp_id,
                           upcoming=upcoming, standings=standings, logo_map=logo_map)


@app.route("/team/<int:team_id>/competitions/<int:comp_id>/add_match",
           methods=["GET", "POST"])
def add_match_route(team_id, comp_id):
    team = get_team_by_id(team_id)
    if team is None:
        abort(404)
    if request.method == "POST":
        ts = int(request.form["team_score"])
        os_ = int(request.form["opponent_score"])
        if ts > os_:
            result = "W"
        elif ts < os_:
            result = "L"
        else:
            result = "D"
        add_match(
            team_id, comp_id,
            request.form["match_date"],
            request.form["opponent"],
            request.form.get("venue", "Home"),
            ts, os_, result
        )
        flash("Match added!", "success")
        return redirect(url_for("competition_detail", team_id=team_id, comp_id=comp_id))
    return render_template("add_match.html", team=team, comp_id=comp_id)


@app.route("/team/<int:team_id>/attendance")
def attendance(team_id):
    team = get_team_by_id(team_id)
    if team is None:
        abort(404)
    return render_template("coming_soon.html", team=team,
                           module_name="Attendance", stage=3)


MIN_BANDS = ['1-5', '6-10', '11-15', '16-20', '21-25', '26-30', '31-35',
             '36-40', '41-45', '46-50', '51-55', '56-60', '61-65', '66-70',
             '71-75', '76-80', '81-85', '86-90', '91+']
POS_CODE_MAP = {"Goalkeeper": "GK", "Center Back": "CB", "Full Back": "FB",
                "Central Midfielder": "CM", "Winger": "WM", "Forward": "FW"}


def band_for(mins):
    if not mins or mins <= 0:
        return None
    if mins > 90:
        return '91+'
    return MIN_BANDS[(mins - 1) // 5]


def pos_code(position):
    return POS_CODE_MAP.get(position or "", "CM")


@app.route("/team/<int:team_id>/performance")
def performance(team_id):
    team = get_team_by_id(team_id)
    if team is None:
        abort(404)
    if team['id'] != 1:
        abort(404)
    comp = get_competition_by_id(1)  # FDH Premiership
    logo_map = {
        "Big Bullets": "nyasa-bullets.png", "Blue Eagles": "blue-eagles.png",
        "Chitipa United": "chitipa.png", "Civo Utd": "civo.png",
        "Creck Sporting": "creck.png", "Dedza Dynamos": "dedza.png",
        "Kamuzu Barracks": "kamuzu-barracks.png", "Karonga United": "karonga.png",
        "MAFCO": "mafco.png", "Masters FC": "masters-fc.png",
        "Mighty Tigers": "mighty-tigers.png", "Mighty Wanderers": "wanderers.png",
        "Mitundu Baptist": "luanar.png", "Moyale Barracks": "moyale.png",
        "Mzuzu City": "mzuzu-city.png", "Red Lions": "red-lions.png",
        "Silver Strikers": "silver-strikers.png", "Songwe Border": "songwe-border.png",
        "FCB Nyasa Big Bullets": "nyasa-bullets.png",
        "Civil Service United": "civo.png", "Luanar Mitundu": "luanar.png",
        "Mafco FC": "mafco.png", "Masters": "masters-fc.png",
    }

    # GPS match analytics (reference totals).
    tracked = []
    for m in get_performance_matches(team_id):
        if m["distance_m"] is None:
            continue
        ours = m["home_score"]
        theirs = m["away_score"]
        home = m["home_away"] != "away"
        if ours is None or theirs is None:
            result = None
        else:
            so = ours if home else theirs
            st = theirs if home else ours
            result = "W" if so > st else ("D" if so == st else "L")
        tracked.append({
            "id": m["id"],
            "opponent": m["opponent"],
            "competition": m["competition"],
            "match_date": m["match_date"],
            "venue": m["venue"],
            "total_time": m["total_time"],
            "distance_m": m["distance_m"],
            "hs_distance_m": m["hs_distance_m"],
            "accel_decel_count": m["accel_decel_count"],
            "athletes_count": m["athletes_count"],
            "volume_pct": m["volume_pct"],
            "intensity_pct": m["intensity_pct"],
            "overall_pct": m["overall_pct"],
            "home_score": m["home_score"],
            "away_score": m["away_score"],
            "home_away": m["home_away"],
            "result": result,
        })
    tracked.sort(key=lambda x: x["match_date"] or "")

    def gps_summary():
        if not tracked:
            return {"peak": None, "toughest": None, "average": 0,
                    "count": 0}
        peak = max(tracked, key=lambda x: (x["overall_pct"] or 0))
        toughest = max(tracked, key=lambda x: (x["distance_m"] or 0))
        overalls = [x["overall_pct"] for x in tracked
                    if x["overall_pct"] is not None]
        avg_overall = round(sum(overalls) / len(overalls)) if overalls else 0
        return {"peak": peak, "toughest": toughest, "average": avg_overall,
                "count": len(tracked)}

    # Minutes logs aggregated per player.
    minutes_entries = get_performance_minutes(team_id)
    from collections import OrderedDict
    min_rows = OrderedDict()
    for e in minutes_entries:
        row = min_rows.setdefault(e["player_id"], {
            "id": e["player_id"],
            "name": e["name"],
            "position": e["position"] or "",
            "squad_number": e["squad_number"],
            "total": 0,
            "apps": 0,
            "entries": [],
            "bands": {b: 0 for b in MIN_BANDS},
        })
        row["total"] += e["minutes"]
        row["apps"] += 1
        row["entries"].append({"match": e["match_label"],
                               "minutes": e["minutes"]})
        b = band_for(e["minutes"])
        if b:
            row["bands"][b] += 1
    for row in min_rows.values():
        row["avg"] = round(row["total"] / row["apps"]) if row["apps"] else 0
        counts = row["bands"]
        top = max(MIN_BANDS, key=lambda b: (counts[b],
                                            MIN_BANDS.index(b)))
        row["mode"] = top if counts[top] > 0 else None
        max_count = max(counts.values()) or 1
        row["distribution"] = [
            {"band": b, "count": counts[b],
             "pct": round(counts[b] / max_count * 100)}
            for b in MIN_BANDS]
        # 2 most common bands for a compact summary chip.
        order = sorted(MIN_BANDS, key=lambda b: (counts[b],
                                                 MIN_BANDS.index(b)),
                       reverse=True)
        row["top_bands"] = [b for b in order[:2] if counts[b] > 0]

    # Physical aggregates + position averages.
    physical = get_performance_physical(team_id)
    phys_by_id = {r["player_id"]: r for r in physical}

    from performance_data import POSITION_AVERAGES, POSITION_LABELS
    position_averages = []
    for code in ["GK", "CB", "FB", "CM", "WM", "FW"]:
        av = POSITION_AVERAGES.get(code)
        if not av:
            continue
        label = POSITION_LABELS.get(code, code)
        matches_ = [b for b in tracked]
        position_averages.append({
            "code": code, "label": label,
            "distance": av["avgDistance"],
            "hs_distance": av["avgHSDistance"],
            "player_load": av["avgPlayerLoad"],
            "count": av["playerCount"],
        })

    # Squad overview for header cards.
    players = get_players_by_team(team_id)

    standings = get_standings("FDH Premiership")
    return render_template("performance.html", team=team,
                           matches=tracked,
                           gps_summary=gps_summary(),
                           minutes_rows=list(min_rows.values()),
                           min_bands=MIN_BANDS,
                           physical=physical,
                           phys_by_id=phys_by_id,
                           position_averages=position_averages,
                           pos_code_map=POS_CODE_MAP,
                           players=players,
                           standings=standings,
                           comp=comp,
                           comp_id=comp[0],
                           logo_map=logo_map,
                           is_admin=team['id'] == 1)


def team_aggregates(stats):
    """Roll per-player GPS rows into match-level team figures."""
    total_distance = round(sum((s.get("distance_m") or 0) for s in stats))
    total_hs = round(sum((s.get("hs_distance_m") or 0) for s in stats))
    total_sprint = round(sum((s.get("sprint_distance_m") or 0) for s in stats))
    volumes = [s.get("player_load") or 0 for s in stats if s.get("player_load")]
    overalls = [s.get("overall_pct") for s in stats
                if s.get("overall_pct") is not None]
    intensity = round(sum(volumes) / len(volumes)) if volumes else None
    overall = round(sum(overalls) / len(overalls)) if overalls else None
    return {"distance": total_distance,
            "hs_distance": total_hs,
            "sprint_distance": total_sprint,
            "volume": intensity,
            "intensity": intensity,
            "overall": overall,
            "athletes": len(stats)}


def compute_gps_summary(match_data):
    """Compute the season-header GPS cards (peak output, toughest, average)."""
    tracked = [blk for blk in match_data if blk["agg"]["athletes"] > 0
               and blk["agg"]["distance"] > 0]
    if not tracked:
        return {"peak": None, "toughest": None, "average": None,
                "tracked_count": 0}
    peak = max(tracked, key=lambda b: (b["agg"]["overall"] or 0,
                                       b["agg"]["volume"] or 0))
    toughest = max(tracked, key=lambda b: b["agg"]["distance"])
    volumes = [b["agg"]["volume"] for b in tracked if b["agg"]["volume"]]
    overalls = [b["agg"]["overall"] for b in tracked if b["agg"]["overall"]]
    average = round(sum(volumes) / len(volumes)) if volumes else None
    avg_overall = round(sum(overalls) / len(overalls)) if overalls else None
    max_vol = max(volumes) if volumes else None
    max_overall = max(overalls) if overalls else None
    return {"peak": peak, "toughest": toughest, "average": average,
            "avg_overall": avg_overall, "tracked_count": len(tracked),
            "max_vol": max_vol, "max_overall": max_overall}


def match_result(m):
    """Return W/D/L based on scoreline; '—' if no score."""
    if m["home_score"] is None or m["away_score"] is None:
        return "—"
    is_home = m["home_away"] != "away"
    ours = m["home_score"] if is_home else m["away_score"]
    theirs = m["away_score"] if is_home else m["home_score"]
    if ours > theirs:
        return "W"
    if ours < theirs:
        return "L"
    return "D"


def annotate_performance_stats(stats, total_time=None):
    """Attach estimated minutes played and heatmap intensity classes.

    Minutes are estimated from the player's distance relative to the busiest
    player in the session (capped at session length if total_time is given).
    Each workload stat is normalized into a heat colour band for the table.
    """
    rows = [dict(s) for s in stats]
    if not rows:
        return []
    max_dist = max((r.get("distance_m") or 0) for r in rows) or 0
    total_secs = parse_session_seconds(total_time)

    def minutes_for(dist):
        if max_dist <= 0:
            return 0
        minutes = round(dist / max_dist * 90)
        if total_secs:
            minutes = min(minutes, round(total_secs / 60))
        return minutes

    def band(val):
        if val is None:
            return 0
        try:
            val = float(val)
        except (TypeError, ValueError):
            return 0
        if val <= 0:
            return 0
        if val < 33:
            return 1
        if val < 66:
            return 2
        return 3

    stats_by_player = {}
    for r in rows:
        pid = r["player_id"]
        bucket = stats_by_player.setdefault(pid, {"distance": 0, "load": 0,
                                                  "hs": 0, "sprint": 0,
                                                  "acc": 0})
        bucket["distance"] = max(bucket["distance"], r.get("distance_m") or 0)
        bucket["load"] = max(bucket["load"], r.get("player_load") or 0)
        bucket["hs"] = max(bucket["hs"], r.get("hs_distance_m") or 0)
        bucket["sprint"] = max(bucket["sprint"], r.get("sprint_distance_m") or 0)
        bucket["acc"] = max(bucket["acc"], r.get("accel_decel_efforts") or 0)
        r["minutes_played"] = minutes_for(bucket["distance"])

    for pid, bucket in stats_by_player.items():
        stats_by_player[pid] = {k: band(v) for k, v in bucket.items()}

    for r in rows:
        b = stats_by_player.get(r["player_id"], {})
        for key, attr in (("distance_m", "distance"), ("player_load", "load"),
                          ("hs_distance_m", "hs"), ("sprint_distance_m", "sprint"),
                          ("accel_decel_efforts", "acc")):
            r["heat_" + key] = b.get(attr, 0)
    return rows


def parse_session_seconds(total_time):
    """Convert 'H:MM:SS' or 'MM:SS' to seconds; None if not parseable."""
    if not total_time:
        return None
    parts = str(total_time).strip().split(":")
    try:
        nums = [int(x) for x in parts]
    except ValueError:
        return None
    secs = 0
    for n in nums:
        secs = secs * 60 + n
    return secs


def build_season_player_table(team_id, match_data, scorers):
    """Aggregate a player season table: mins, high mins, goals, assists,
    cards, distance covered, a per-match heatmap strip, and a per-player
    match-by-match breakdown for the expandable detail row."""
    from collections import OrderedDict
    players = get_players_by_team(team_id)
    base = {}
    for p in players:
        base[p["id"]] = {
            "id": p["id"],
            "name": "{} {}".format(p["first_name"], p["last_name"]),
            "position": p["position"] or "",
            "goals": p["goals"] or 0,
            "assists": p["assists"] or 0,
            "yellow": p["yellow_cards"] or 0,
            "red": p["red_cards"] or 0,
            "minutes": 0,
            "peak": 0,
            "apps": 0,
            "distance_m": 0.0,
            "load": 0.0,
            "bands": [],
            "match_breakdown": [],
        }

    tracked_dates = [block["match"]["match_date"]
                     for block in match_data
                     if block["stats"]]
    date_cols = list(dict.fromkeys(tracked_dates))

    for block in match_data:
        m = block["match"]
        result_ = match_result(m)
        for s in block["stats"]:
            pid = s["player_id"]
            if pid not in base:
                continue
            row = base[pid]
            mins = s.get("minutes_played") or 0
            dist = s.get("distance_m") or 0
            row["minutes"] += mins
            row["peak"] = max(row["peak"], mins)
            row["apps"] += 1 if dist > 0 else 0
            row["distance_m"] += dist
            row["load"] += s.get("player_load") or 0
            band = s.get("heat_distance_m")
            row["bands"].append((m["match_date"], band))
            row["match_breakdown"].append({
                "match_date": m["match_date"],
                "opponent": m["opponent"],
                "result": result_,
                "position": s.get("position") or s.get("player_position") or "",
                "minutes": mins,
                "distance_m": dist,
                "hs_distance_m": s.get("hs_distance_m") or 0,
                "player_load": s.get("player_load") or 0,
                "overall_pct": s.get("overall_pct"),
                "sprint_distance_m": s.get("sprint_distance_m") or 0,
            })

    rows = [row for row in base.values()
            if row["minutes"] > 0 or row["distance_m"] > 0
            or row["goals"] > 0 or row["assists"] > 0
            or row["yellow"] > 0 or row["red"] > 0]

    def merge_bands(row):
        by_date = dict(row["bands"])
        return [by_date.get(d, 0) for d in date_cols]

    for row in rows:
        row["heatmap"] = merge_bands(row)
        row["distance_km"] = round(row["distance_m"] / 1000.0, 1)
        row["match_breakdown"].sort(key=lambda mb: mb["match_date"])

    rows.sort(key=lambda r: (r["minutes"], r["distance_m"],
                             r["goals"], r["assists"]), reverse=True)
    return rows, date_cols



@app.route("/team/<int:team_id>/medical")
def medical(team_id):
    team = get_team_by_id(team_id)
    if team is None:
        abort(404)
    medical_summary = get_team_medical_summary(team_id)
    players = get_players_by_team(team_id)
    return render_template("medical.html", team=team, medical_summary=medical_summary, players=players)

@app.route("/team/<int:team_id>/medical/add", methods=["GET", "POST"])
def add_medical_route(team_id):
    team = get_team_by_id(team_id)
    if team is None:
        abort(404)
    players = get_players_by_team(team_id)
    if request.method == "POST":
        player_id = int(request.form["player_id"])
        injury_type = request.form["injury_type"]
        body_part = request.form["body_part"]
        severity = request.form["severity"]
        status = request.form["status"]
        diagnosed_date = request.form["diagnosed_date"]
        expected_return = request.form.get("expected_return") or None
        notes = request.form.get("notes") or ""
        add_medical_record(player_id, injury_type, body_part, severity, status, diagnosed_date, expected_return, notes)
        flash("Medical record added!", "success")
        return redirect(url_for("medical", team_id=team_id))
    return render_template("medical_form.html", team=team, players=players, medical=None)

@app.route("/team/<int:team_id>/medical/<int:record_id>/edit", methods=["GET", "POST"])
def edit_medical_route(team_id, record_id):
    team = get_team_by_id(team_id)
    if team is None:
        abort(404)
    # Get the record
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM player_medical WHERE id = ?", (record_id,))
    record = cur.fetchone()
    conn.close()
    if not record:
        abort(404)
    players = get_players_by_team(team_id)
    if request.method == "POST":
        update_medical_record(record_id,
            injury_type=request.form["injury_type"],
            body_part=request.form["body_part"],
            severity=request.form["severity"],
            status=request.form["status"],
            diagnosed_date=request.form["diagnosed_date"],
            expected_return=request.form.get("expected_return") or None,
            actual_return=request.form.get("actual_return") or None,
            notes=request.form.get("notes") or "")
        flash("Medical record updated!", "success")
        return redirect(url_for("medical", team_id=team_id))
    return render_template("medical_form.html", team=team, players=players, medical=record)

@app.route("/team/<int:team_id>/medical/<int:record_id>/delete", methods=["POST"])
def delete_medical_route(team_id, record_id):
    delete_medical_record(record_id)
    flash("Medical record deleted!", "success")
    return redirect(url_for("medical", team_id=team_id))

@app.route("/team/<int:team_id>/league")
def league(team_id):
    team = get_team_by_id(team_id)
    if team is None:
        abort(404)
    team_leagues = {1: "FDH Premiership", 3: "FincaDL1"}
    team_league = team_leagues.get(team_id)
    standings = get_standings(team_league) if team_league else []
    return render_template("standings.html", team=team, standings=standings,
                           league_name=team_league)


@app.route("/team/<int:team_id>/fixtures")
def fixtures(team_id):
    team = get_team_by_id(team_id)
    if team is None:
        abort(404)
    mw = request.args.get("matchweek", type=int)
    all_fixtures = get_all_fixtures(matchweek=mw)
    ekhaya_fixtures = get_ekhaya_fixtures()
    ekhaya_played = sum(1 for f in ekhaya_fixtures if f["status"] == "played")
    matchweeks = sorted(set(f["matchweek"] for f in all_fixtures if f["matchweek"]))
    return render_template("fixtures.html", team=team,
                           fixtures=matchweeks, ekhaya_fixtures=ekhaya_fixtures,
                           all_fixtures=all_fixtures, selected_mw=mw,
                           ekhaya_played=ekhaya_played)


@app.route("/admin/fans")
@admin_required
def admin_fans():
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    tier = request.args.get("tier", "").strip()
    fans = get_all_fans(search=search or None, status=status or None,
                        tier=tier or None)
    stats = get_fan_stats()
    return render_template("admin_fans.html", fans=fans, stats=stats,
                           search=search, status=status, tier=tier,
                           current_user=session.get("admin_username"))


@app.route("/admin/fans/add", methods=["GET", "POST"])
@admin_required
def admin_add_fan():
    if request.method == "POST":
        add_fan(
            request.form.get("first_name", "").strip(),
            request.form.get("last_name", "").strip(),
            email=request.form.get("email", "").strip() or None,
            phone=request.form.get("phone", "").strip() or None,
            city=request.form.get("city", "").strip() or None,
            membership_tier=request.form.get("membership_tier", "Fan"),
            membership_status=request.form.get("membership_status", "Active"),
            joined_date=request.form.get("joined_date", "").strip() or None,
            source=request.form.get("source", "Admin"),
            notes=request.form.get("notes", "").strip() or None,
        )
        flash("Fan added!", "success")
        return redirect(url_for("admin_fans"))
    return render_template("admin_fan_form.html", fan=None,
                           current_user=session.get("admin_username"))


@app.route("/admin/fans/<int:fan_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_fan(fan_id):
    fan = get_fan_by_id(fan_id)
    if fan is None:
        abort(404)
    if request.method == "POST":
        update_fan(
            fan_id,
            request.form.get("first_name", "").strip(),
            request.form.get("last_name", "").strip(),
            email=request.form.get("email", "").strip() or None,
            phone=request.form.get("phone", "").strip() or None,
            city=request.form.get("city", "").strip() or None,
            membership_tier=request.form.get("membership_tier", "Fan"),
            membership_status=request.form.get("membership_status", "Active"),
            joined_date=request.form.get("joined_date", "").strip() or None,
            notes=request.form.get("notes", "").strip() or None,
        )
        flash("Fan updated!", "success")
        return redirect(url_for("admin_fans"))
    return render_template("admin_fan_form.html", fan=fan,
                           current_user=session.get("admin_username"))


@app.route("/admin/fans/<int:fan_id>/delete", methods=["POST"])
@admin_required
def admin_delete_fan(fan_id):
    delete_fan(fan_id)
    flash("Fan removed.", "info")
    return redirect(url_for("admin_fans"))


@app.route("/admin/players")
@admin_required
def admin_players():
    players = get_all_players()
    teams = get_all_teams()
    return render_template("admin_players.html", players=players, teams=teams,
                           current_user=session.get("admin_username"))


@app.route("/admin/players/add", methods=["GET", "POST"])
@admin_required
def admin_add_player():
    teams = get_all_teams()
    if request.method == "POST":
        team_id = int(request.form["team_id"])
        player_id = add_player(
            team_id,
            request.form["first_name"],
            request.form["last_name"],
            int(request.form["squad_number"]),
            request.form["position"],
            request.form.get("date_of_birth", ""),
            request.form.get("nationality", ""),
            request.form.get("strong_foot", "Right")
        )
        update_player_stats(
            player_id,
            goals=int(request.form.get("goals", 0)),
            assists=int(request.form.get("assists", 0)),
            yellow_cards=int(request.form.get("yellow_cards", 0)),
            red_cards=int(request.form.get("red_cards", 0)),
            appearances=int(request.form.get("appearances", 0)),
            minutes_played=int(request.form.get("minutes_played", 0)),
            distance_km=float(request.form.get("distance_km", 0)),
        )
        flash("Player added!", "success")
        return redirect(url_for("admin_players"))
    return render_template("admin_player_form.html", teams=teams,
                           player=None, current_user=session.get("admin_username"))


@app.route("/admin/players/<int:player_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_player(player_id):
    player = get_player_by_id(player_id)
    if player is None:
        abort(404)
    teams = get_all_teams()
    if request.method == "POST":
        team_id = int(request.form["team_id"])
        conn = None
        from database import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE players
            SET team_id = ?, first_name = ?, last_name = ?, squad_number = ?,
                position = ?, date_of_birth = ?, nationality = ?, strong_foot = ?
            WHERE id = ?
        """, (team_id, request.form["first_name"], request.form["last_name"],
              int(request.form["squad_number"]), request.form["position"],
              request.form.get("date_of_birth", ""), request.form.get("nationality", ""),
              request.form.get("strong_foot", "Right"), player_id))
        conn.commit()
        conn.close()
        update_player_stats(
            player_id,
            goals=int(request.form.get("goals", 0)),
            assists=int(request.form.get("assists", 0)),
            yellow_cards=int(request.form.get("yellow_cards", 0)),
            red_cards=int(request.form.get("red_cards", 0)),
            appearances=int(request.form.get("appearances", 0)),
            minutes_played=int(request.form.get("minutes_played", 0)),
            distance_km=float(request.form.get("distance_km", 0)),
        )
        flash("Player updated!", "success")
        return redirect(url_for("admin_players"))
    return render_template("admin_player_form.html", teams=teams, player=player,
                           current_user=session.get("admin_username"))


@app.route("/admin/players/<int:player_id>/delete", methods=["POST"])
@admin_required
def admin_delete_player(player_id):
    delete_player(player_id)
    flash("Player removed.", "info")
    return redirect(url_for("admin_players"))


@app.route("/admin/competitions")
@admin_required
def admin_competitions():
    comps = get_all_competitions()
    teams = get_all_teams()
    return render_template("admin_competitions.html", competitions=comps, teams=teams,
                           current_user=session.get("admin_username"))


@app.route("/admin/competitions/add", methods=["GET", "POST"])
@admin_required
def admin_add_competition():
    teams = get_all_teams()
    if request.method == "POST":
        add_competition(
            int(request.form["team_id"]),
            request.form["name"],
            request.form["comp_type"],
            request.form.get("season", "2025/26")
        )
        flash("Competition added!", "success")
        return redirect(url_for("admin_competitions"))
    return render_template("admin_competition_form.html", teams=teams, competition=None,
                           current_user=session.get("admin_username"))


@app.route("/admin/competitions/<int:comp_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_competition(comp_id):
    comp = get_competition_by_id(comp_id)
    if comp is None:
        abort(404)
    teams = get_all_teams()
    if request.method == "POST":
        update_competition(
            comp_id,
            request.form["name"],
            request.form["comp_type"],
            request.form.get("season", "")
        )
        flash("Competition updated!", "success")
        return redirect(url_for("admin_competitions"))
    return render_template("admin_competition_form.html", teams=teams, competition=comp,
                           current_user=session.get("admin_username"))


@app.route("/admin/competitions/<int:comp_id>/delete", methods=["POST"])
@admin_required
def admin_delete_competition(comp_id):
    delete_competition(comp_id)
    flash("Competition removed.", "info")
    return redirect(url_for("admin_competitions"))


@app.route("/admin/matches")
@admin_required
def admin_matches():
    matches = get_all_matches()
    teams = get_all_teams()
    return render_template("admin_matches.html", matches=matches, teams=teams,
                           current_user=session.get("admin_username"))


@app.route("/admin/matches/add", methods=["GET", "POST"])
@admin_required
def admin_add_match():
    teams = get_all_teams()
    comps = get_all_competitions()
    if request.method == "POST":
        ts = int(request.form["team_score"])
        os_ = int(request.form["opponent_score"])
        result = "W" if ts > os_ else ("L" if ts < os_ else "D")
        team_id = int(request.form["team_id"])
        comp_id = int(request.form["competition_id"]) if request.form.get("competition_id") else None
        add_match(team_id, comp_id, request.form["match_date"], request.form["opponent"],
                  request.form.get("venue", "Home"), ts, os_, result)
        flash("Match added!", "success")
        return redirect(url_for("admin_matches"))
    return render_template("admin_match_form.html", teams=teams, competitions=comps, match=None,
                           current_user=session.get("admin_username"))


@app.route("/admin/matches/<int:match_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_match(match_id):
    match = get_match_by_id(match_id)
    if match is None:
        abort(404)
    teams = get_all_teams()
    comps = get_all_competitions()
    if request.method == "POST":
        update_match(match_id, request.form["match_date"], request.form["opponent"],
                     request.form.get("venue", "Home"), int(request.form["team_score"]),
                     int(request.form["opponent_score"]), request.form["result"])
        flash("Match updated!", "success")
        return redirect(url_for("admin_matches"))
    return render_template("admin_match_form.html", teams=teams, competitions=comps, match=match,
                           current_user=session.get("admin_username"))


@app.route("/admin/matches/<int:match_id>/delete", methods=["POST"])
@admin_required
def admin_delete_match(match_id):
    delete_match(match_id)
    flash("Match removed.", "info")
    return redirect(url_for("admin_matches"))


@app.route("/admin/standings")
@admin_required
def admin_standings():
    leagues = get_league_names()
    selected = request.args.get("league", leagues[0] if leagues else "FDH Premiership")
    standings = get_standings(selected)
    return render_template("admin_standings.html", standings=standings, leagues=leagues,
                           selected=selected, current_user=session.get("admin_username"))


@app.route("/admin/standings/update", methods=["POST"])
@admin_required
def admin_update_standings():
    entry_id = int(request.form["entry_id"])
    team_name = request.form.get("team_name")
    if team_name:
        update_standing_name(entry_id, team_name)
    update_standings_entry(
        entry_id,
        int(request.form.get("played", 0)),
        int(request.form.get("won", 0)),
        int(request.form.get("drawn", 0)),
        int(request.form.get("lost", 0)),
        int(request.form.get("goals_for", 0)),
        int(request.form.get("goals_against", 0)),
        int(request.form.get("goal_diff", 0)),
        int(request.form.get("points", 0)),
    )
    flash("Standings updated!", "success")
    return redirect(request.referrer or url_for("admin_standings"))


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    init_db()
    seed_demo_data()
    seed_standings()
    seed_fixtures()
    seed_reserve_standings()
    from reseed import run as seed_real_rosters
    seed_real_rosters()
    seed_medical()
    seed_main_team_stats()
    seed_reference_performance()
    try:
        app.run(debug=False, host="0.0.0.0", port=5000,
                ssl_context=("cert.pem", "key.pem"))
    except Exception:
        app.run(debug=False, host="0.0.0.0", port=5000)
