"""
database.py - Ekhaya Nexus database.
Teams, players, stats, competitions, matches.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ekhaya_nexus.db")

TEAM_NAMES = ["First Team", "Women", "Reserve", "Youth"]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)

    cur.execute("SELECT COUNT(*) FROM admins")
    if cur.fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO admins (username, password_hash)
            VALUES ('admin', 'admin')
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            squad_number INTEGER,
            position TEXT,
            date_of_birth TEXT,
            nationality TEXT,
            strong_foot TEXT DEFAULT 'Right',
            photo_url TEXT,
            status TEXT DEFAULT 'Active',
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL UNIQUE,
            goals INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            yellow_cards INTEGER DEFAULT 0,
            red_cards INTEGER DEFAULT 0,
            appearances INTEGER DEFAULT 0,
            minutes_played INTEGER DEFAULT 0,
            distance_km REAL DEFAULT 0.0,
            FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS competitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            comp_type TEXT NOT NULL,
            season TEXT,
            is_champion INTEGER DEFAULT 0,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
        )
    """)

    ccols = [r[1] for r in cur.execute("PRAGMA table_info(competitions)").fetchall()]
    if "is_champion" not in ccols:
        cur.execute("ALTER TABLE competitions ADD COLUMN is_champion INTEGER DEFAULT 0")

    ccols = [r[1] for r in cur.execute("PRAGMA table_info(teams)").fetchall()]
    if "video_url" not in ccols:
        cur.execute("ALTER TABLE teams ADD COLUMN video_url TEXT")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            competition_id INTEGER,
            match_date TEXT,
            opponent TEXT,
            venue TEXT,
            team_score INTEGER,
            opponent_score INTEGER,
            result TEXT,
            scorers TEXT,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (competition_id) REFERENCES competitions(id) ON DELETE SET NULL
        )
    """)

    mcols = [r[1] for r in cur.execute("PRAGMA table_info(matches)").fetchall()]
    if "scorers" not in mcols:
        cur.execute("ALTER TABLE matches ADD COLUMN scorers TEXT")
    if "notes" not in mcols:
        cur.execute("ALTER TABLE matches ADD COLUMN notes TEXT")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS match_player_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            goals INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            yellow_card INTEGER DEFAULT 0,
            red_card INTEGER DEFAULT 0,
            minutes_played INTEGER DEFAULT 0,
            distance_km REAL DEFAULT 0.0,
            rating REAL,
            FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
            FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS injuries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            injury_type TEXT NOT NULL,
            description TEXT,
            date_occurred TEXT,
            expected_return TEXT,
            status TEXT DEFAULT 'Active',
            FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS league_standings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            league_name TEXT NOT NULL DEFAULT 'FDH Premiership',
            team_name TEXT NOT NULL,
            logo_file TEXT,
            played INTEGER DEFAULT 0,
            won INTEGER DEFAULT 0,
            drawn INTEGER DEFAULT 0,
            lost INTEGER DEFAULT 0,
            goals_for INTEGER DEFAULT 0,
            goals_against INTEGER DEFAULT 0,
            goal_diff INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            position INTEGER,
            form TEXT,
            UNIQUE(league_name, team_name)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS performance_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            opponent TEXT,
            competition TEXT,
            match_date TEXT,
            venue TEXT,
            total_time TEXT,
            distance_m REAL,
            hs_distance_m REAL,
            accel_decel_count INTEGER,
            athletes_count INTEGER,
            team_shape_file TEXT,
            home_score INTEGER,
            away_score INTEGER,
            home_away TEXT,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS performance_player_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            performance_match_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            position TEXT,
            distance_m REAL,
            hs_distance_m REAL,
            max_acceleration REAL,
            max_deceleration REAL,
            player_load REAL,
            overall_pct REAL,
            sprint_distance_m REAL,
            accel_decel_efforts INTEGER,
            FOREIGN KEY (performance_match_id) REFERENCES performance_matches(id) ON DELETE CASCADE,
            FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS performance_physical (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL UNIQUE,
            position TEXT,
            sessions_tracked INTEGER DEFAULT 0,
            avg_distance REAL DEFAULT 0,
            avg_hs_distance REAL DEFAULT 0,
            avg_player_load REAL DEFAULT 0,
            avg_max_accel REAL DEFAULT 0,
            avg_max_decel REAL DEFAULT 0,
            avg_ad_efforts REAL DEFAULT 0,
            FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS performance_minutes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            match_label TEXT NOT NULL,
            minutes INTEGER NOT NULL,
            FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
        )
    """)

    cols = [r[1] for r in cur.execute("PRAGMA table_info(league_standings)").fetchall()]
    if "form" not in cols:
        cur.execute("ALTER TABLE league_standings ADD COLUMN form TEXT")
    if "league_name" not in cols:
        cur.execute("DROP TABLE league_standings")
        cur.execute("""
            CREATE TABLE league_standings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_name TEXT NOT NULL DEFAULT 'FDH Premiership',
                team_name TEXT NOT NULL,
                logo_file TEXT,
                played INTEGER DEFAULT 0,
                won INTEGER DEFAULT 0,
                drawn INTEGER DEFAULT 0,
                lost INTEGER DEFAULT 0,
                goals_for INTEGER DEFAULT 0,
                goals_against INTEGER DEFAULT 0,
                goal_diff INTEGER DEFAULT 0,
                points INTEGER DEFAULT 0,
                position INTEGER,
                form TEXT,
                UNIQUE(league_name, team_name)
            )
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS fixtures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matchweek INTEGER,
            match_date TEXT,
            kick_off TEXT,
            home_team TEXT,
            away_team TEXT,
            home_score INTEGER,
            away_score INTEGER,
            venue TEXT,
            status TEXT DEFAULT 'upcoming'
        )
    """)

    cur.execute("SELECT COUNT(*) FROM teams")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO teams (name) VALUES (?)",
            [(name,) for name in TEAM_NAMES]
        )

    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_medical (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            injury_type TEXT NOT NULL,
            body_part TEXT,
            severity TEXT DEFAULT '1',
            status TEXT DEFAULT 'active',
            diagnosed_date TEXT,
            expected_return TEXT,
            actual_return TEXT,
            notes TEXT,
            FOREIGN KEY (player_id) REFERENCES players (id)
        )
    """)

    pcols = [r[1] for r in cur.execute(
        "PRAGMA table_info(performance_matches)").fetchall()]
    for pcol, ptype in (("home_score", "INTEGER"), ("away_score", "INTEGER"),
                        ("home_away", "TEXT"), ("volume_pct", "REAL"),
                        ("intensity_pct", "REAL"), ("overall_pct", "REAL")):
        if pcol not in pcols:
            cur.execute("ALTER TABLE performance_matches ADD COLUMN %s %s"
                        % (pcol, ptype))

    conn.commit()
    conn.close()


def get_all_teams():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM teams ORDER BY id")
    teams = cur.fetchall()
    conn.close()
    return teams


def get_team_by_id(team_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM teams WHERE id = ?", (team_id,))
    team = cur.fetchone()
    conn.close()
    return team


def get_players_by_team(team_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.*, ps.goals, ps.assists, ps.yellow_cards, ps.red_cards,
               ps.appearances, ps.minutes_played, ps.distance_km
        FROM players p
        LEFT JOIN player_stats ps ON p.id = ps.player_id
        WHERE p.team_id = ?
        ORDER BY p.squad_number
    """, (team_id,))
    players = cur.fetchall()
    conn.close()
    return players


def get_player_by_id(player_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.*, ps.goals, ps.assists, ps.yellow_cards, ps.red_cards,
               ps.appearances, ps.minutes_played, ps.distance_km,
               t.name as team_name
        FROM players p
        LEFT JOIN player_stats ps ON p.id = ps.player_id
        JOIN teams t ON p.team_id = t.id
        WHERE p.id = ?
    """, (player_id,))
    player = cur.fetchone()
    conn.close()
    return player


def add_player(team_id, first_name, last_name, squad_number, position,
               date_of_birth, nationality, strong_foot='Right'):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO players (team_id, first_name, last_name, squad_number,
            position, date_of_birth, nationality, strong_foot)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (team_id, first_name, last_name, squad_number, position,
          date_of_birth, nationality, strong_foot))
    player_id = cur.lastrowid
    cur.execute("""
        INSERT INTO player_stats (player_id) VALUES (?)
    """, (player_id,))
    conn.commit()
    conn.close()
    return player_id


def update_player_stats(player_id, goals=None, assists=None, yellow_cards=None,
                        red_cards=None, appearances=None, minutes_played=None,
                        distance_km=None):
    conn = get_connection()
    cur = conn.cursor()
    updates = []
    values = []
    if goals is not None:
        updates.append("goals = ?")
        values.append(goals)
    if assists is not None:
        updates.append("assists = ?")
        values.append(assists)
    if yellow_cards is not None:
        updates.append("yellow_cards = ?")
        values.append(yellow_cards)
    if red_cards is not None:
        updates.append("red_cards = ?")
        values.append(red_cards)
    if appearances is not None:
        updates.append("appearances = ?")
        values.append(appearances)
    if minutes_played is not None:
        updates.append("minutes_played = ?")
        values.append(minutes_played)
    if distance_km is not None:
        updates.append("distance_km = ?")
        values.append(distance_km)
    if updates:
        values.append(player_id)
        cur.execute(f"UPDATE player_stats SET {', '.join(updates)} WHERE player_id = ?", values)
    conn.commit()
    conn.close()


def update_player_photo(player_id, photo_url):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE players SET photo_url = ? WHERE id = ?", (photo_url, player_id))
    conn.commit()
    conn.close()


def delete_player(player_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM players WHERE id = ?", (player_id,))
    conn.commit()
    conn.close()


def get_team_stats(team_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM players WHERE team_id = ?", (team_id,))
    total_players = cur.fetchone()[0]
    cur.execute("""
        SELECT COALESCE(SUM(ps.goals), 0), COALESCE(SUM(ps.assists), 0),
               COALESCE(SUM(ps.yellow_cards), 0), COALESCE(SUM(ps.red_cards), 0),
               COALESCE(SUM(ps.appearances), 0)
        FROM players p
        JOIN player_stats ps ON p.id = ps.player_id
        WHERE p.team_id = ?
    """, (team_id,))
    row = cur.fetchone()
    conn.close()
    return {
        'total_players': total_players,
        'total_goals': row[0],
        'total_assists': row[1],
        'total_yellows': row[2],
        'total_reds': row[3],
        'total_appearances': row[4]
    }


def get_competitions_by_team(team_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*, COUNT(m.id) as match_count,
               SUM(CASE WHEN m.result = 'W' THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN m.result = 'D' THEN 1 ELSE 0 END) as draws,
               SUM(CASE WHEN m.result = 'L' THEN 1 ELSE 0 END) as losses,
               COALESCE(SUM(m.team_score), 0) as goals_for,
               COALESCE(SUM(m.opponent_score), 0) as goals_against
        FROM competitions c
        LEFT JOIN matches m ON c.id = m.competition_id
        WHERE c.team_id = ?
        GROUP BY c.id
        ORDER BY c.comp_type, c.name
    """, (team_id,))
    comps = cur.fetchall()
    conn.close()
    return comps


def add_competition(team_id, name, comp_type, season=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO competitions (team_id, name, comp_type, season)
        VALUES (?, ?, ?, ?)
    """, (team_id, name, comp_type, season))
    comp_id = cur.lastrowid
    conn.commit()
    conn.close()
    return comp_id


def get_matches_by_team(team_id, competition_id=None):
    conn = get_connection()
    cur = conn.cursor()
    if competition_id:
        cur.execute("""
            SELECT m.*, c.name as comp_name
            FROM matches m
            LEFT JOIN competitions c ON m.competition_id = c.id
            WHERE m.team_id = ? AND m.competition_id = ?
            ORDER BY m.match_date DESC
        """, (team_id, competition_id))
    else:
        cur.execute("""
            SELECT m.*, c.name as comp_name
            FROM matches m
            LEFT JOIN competitions c ON m.competition_id = c.id
            WHERE m.team_id = ?
            ORDER BY m.match_date DESC
        """, (team_id,))
    matches = cur.fetchall()
    conn.close()
    return matches


def add_match(team_id, competition_id, match_date, opponent, venue,
              team_score, opponent_score, result):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO matches (team_id, competition_id, match_date, opponent,
            venue, team_score, opponent_score, result)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (team_id, competition_id, match_date, opponent, venue,
          team_score, opponent_score, result))
    match_id = cur.lastrowid
    conn.commit()
    conn.close()
    return match_id


def seed_demo_data():
    """Seed demo players for First Team (team_id=1) if empty."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM players WHERE team_id = 1")
    if cur.fetchone()[0] > 0:
        conn.close()
        return

    players = [
        (1, "Thabo", "Mokoena", 1, "Goalkeeper", "1995-03-12", "South African", "Right"),
        (1, "Sipho", "Dlamini", 4, "Defender", "1997-07-22", "South African", "Right"),
        (1, "Lungelo", "Nkosi", 5, "Defender", "1996-11-03", "South African", "Left"),
        (1, "Bongani", "Zulu", 6, "Midfielder", "1998-01-15", "South African", "Right"),
        (1, "David", "Okonkwo", 8, "Midfielder", "1999-05-30", "Nigerian", "Right"),
        (1, "Patrick", "Mwangi", 10, "Forward", "2000-09-18", "Kenyan", "Left"),
        (1, "Carlos", "Silva", 7, "Forward", "1998-12-01", "Brazilian", "Right"),
        (1, "Ahmed", "Hassan", 9, "Forward", "1997-04-25", "Egyptian", "Right"),
        (1, "Kabelo", "Mahlangu", 3, "Defender", "1999-06-10", "South African", "Right"),
        (1, "Tshepo", "Maseko", 11, "Midfielder", "2001-02-14", "South African", "Left"),
        (1, "John", "Banda", 2, "Defender", "1996-08-20", "Malawian", "Right"),
        (1, "Mandla", "Ndlovu", 14, "Midfielder", "2000-10-07", "South African", "Right"),
        (1, "Emmanuel", "Adeyemi", 15, "Forward", "1999-03-28", "Nigerian", "Right"),
        (1, "Sibusiso", "Khumalo", 13, "Defender", "1998-07-19", "South African", "Left"),
        (1, "Junior", "Peters", 12, "Goalkeeper", "2001-11-25", "South African", "Right"),
    ]

    for p in players:
        cur.execute("""
            INSERT INTO players (team_id, first_name, last_name, squad_number,
                position, date_of_birth, nationality, strong_foot)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, p)
        pid = cur.lastrowid
        cur.execute("INSERT INTO player_stats (player_id) VALUES (?)", (pid,))

    stats = [
        (6, 12, 5, 3, 1, 28, 2430, 267.5),
        (7, 8, 7, 2, 0, 26, 2280, 254.3),
        (8, 15, 3, 1, 0, 27, 2350, 241.8),
        (5, 4, 9, 4, 0, 28, 2520, 301.2),
        (4, 2, 6, 5, 1, 25, 2100, 278.6),
        (10, 6, 8, 2, 0, 24, 1980, 232.1),
        (9, 1, 1, 3, 0, 22, 1800, 215.4),
        (3, 0, 0, 2, 0, 28, 2520, 289.7),
        (2, 0, 0, 4, 1, 27, 2400, 271.3),
        (11, 1, 2, 3, 0, 20, 1650, 198.2),
        (12, 3, 4, 1, 0, 23, 1890, 225.6),
        (13, 7, 2, 2, 0, 25, 2100, 243.9),
        (1, 0, 0, 0, 0, 28, 2520, 12.5),
        (14, 0, 0, 1, 0, 18, 1440, 176.3),
        (15, 0, 0, 0, 0, 5, 450, 28.7),
    ]
    for s in stats:
        cur.execute("""
            UPDATE player_stats
            SET goals=?, assists=?, yellow_cards=?, red_cards=?,
                appearances=?, minutes_played=?, distance_km=?
            WHERE player_id=?
        """, s)

    conn.commit()
    conn.close()


def get_standings(league_name="FDH Premiership"):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM league_standings
        WHERE league_name = ?
        ORDER BY position
    """, (league_name,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_league_names():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT league_name FROM league_standings ORDER BY league_name")
    rows = [r["league_name"] for r in cur.fetchall()]
    conn.close()
    return rows


def check_admin(username, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM admins WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if row and row["password_hash"] == password:
        return True
    return False


def get_all_players():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.*, ps.goals, ps.assists, ps.yellow_cards, ps.red_cards,
               ps.appearances, ps.minutes_played, ps.distance_km,
               t.name as team_name
        FROM players p
        LEFT JOIN player_stats ps ON p.id = ps.player_id
        JOIN teams t ON p.team_id = t.id
        ORDER BY t.id, p.squad_number
    """)
    players = cur.fetchall()
    conn.close()
    return players


def get_all_competitions():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*, t.name as team_name,
               COUNT(m.id) as match_count,
               SUM(CASE WHEN m.result = 'W' THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN m.result = 'D' THEN 1 ELSE 0 END) as draws,
               SUM(CASE WHEN m.result = 'L' THEN 1 ELSE 0 END) as losses
        FROM competitions c
        JOIN teams t ON c.team_id = t.id
        LEFT JOIN matches m ON c.id = m.competition_id
        GROUP BY c.id
        ORDER BY c.team_id, c.comp_type, c.name
    """)
    comps = cur.fetchall()
    conn.close()
    return comps


def get_all_matches():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.*, t.name as team_name, c.name as comp_name
        FROM matches m
        JOIN teams t ON m.team_id = t.id
        LEFT JOIN competitions c ON m.competition_id = c.id
        ORDER BY m.match_date DESC
    """)
    matches = cur.fetchall()
    conn.close()
    return matches


def get_competition_by_id(comp_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*, t.name as team_name
        FROM competitions c
        JOIN teams t ON c.team_id = t.id
        WHERE c.id = ?
    """, (comp_id,))
    comp = cur.fetchone()
    conn.close()
    return comp


def update_competition(comp_id, name, comp_type, season):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE competitions SET name = ?, comp_type = ?, season = ?
        WHERE id = ?
    """, (name, comp_type, season, comp_id))
    conn.commit()
    conn.close()


def delete_competition(comp_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM matches WHERE competition_id = ?", (comp_id,))
    cur.execute("DELETE FROM competitions WHERE id = ?", (comp_id,))
    conn.commit()
    conn.close()


def get_match_by_id(match_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.*, t.name as team_name, c.name as comp_name
        FROM matches m
        JOIN teams t ON m.team_id = t.id
        LEFT JOIN competitions c ON m.competition_id = c.id
        WHERE m.id = ?
    """, (match_id,))
    match = cur.fetchone()
    conn.close()
    return match


def update_match(match_id, match_date, opponent, venue, team_score, opponent_score, result):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE matches SET match_date = ?, opponent = ?, venue = ?,
            team_score = ?, opponent_score = ?, result = ?
        WHERE id = ?
    """, (match_date, opponent, venue, team_score, opponent_score, result, match_id))
    conn.commit()
    conn.close()


def delete_match(match_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM matches WHERE id = ?", (match_id,))
    conn.commit()
    conn.close()


def update_standings_entry(entry_id, played, won, drawn, lost, goals_for,
                           goals_against, goal_diff, points):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE league_standings
        SET played = ?, won = ?, drawn = ?, lost = ?,
            goals_for = ?, goals_against = ?, goal_diff = ?, points = ?
        WHERE id = ?
    """, (played, won, drawn, lost, goals_for, goals_against, goal_diff, points, entry_id))
    conn.commit()
    conn.close()


def update_standing_name(entry_id, team_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE league_standings SET team_name = ? WHERE id = ?", (team_name, entry_id))
    conn.commit()
    conn.close()


def get_ekhaya_fixtures():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM fixtures
        WHERE home_team LIKE '%Ekhaya%' OR away_team LIKE '%Ekhaya%'
        ORDER BY matchweek, match_date
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_all_fixtures(matchweek=None):
    conn = get_connection()
    cur = conn.cursor()
    if matchweek:
        cur.execute("SELECT * FROM fixtures WHERE matchweek = ? ORDER BY match_date", (matchweek,))
    else:
        cur.execute("SELECT * FROM fixtures ORDER BY matchweek, match_date")
    rows = cur.fetchall()
    conn.close()
    return rows


def seed_standings():
    conn = get_connection()
    cur = conn.cursor()
    # FDH Premiership table is derived seed data — rebuild it every startup
    # from the real round-by-round results.
    cur.execute("DELETE FROM league_standings WHERE league_name = 'FDH Premiership'")

    standings = [
        (1, "Big Bullets", "nyasa-bullets.png", 15, 8, 6, 1, 20, 7, 13, 30, "WDWWL"),
        (2, "Mighty Wanderers", "wanderers.png", 14, 8, 5, 1, 26, 9, 17, 29, "WWDDW"),
        (3, "Silver Strikers", "silver-strikers.png", 15, 8, 5, 2, 23, 10, 13, 29, "LDWWD"),
        (4, "Blue Eagles", "blue-eagles.png", 14, 9, 1, 4, 22, 15, 7, 28, "WLWWL"),
        (5, "Masters FC", "masters-fc.png", 15, 6, 4, 5, 17, 16, 1, 22, "DLDWD"),
        (6, "Moyale Barracks", "moyale.png", 15, 5, 6, 4, 16, 17, -1, 21, "WDLDW"),
        (7, "Chitipa United", "chitipa.png", 15, 6, 3, 6, 11, 16, -5, 21, "DDWLW"),
        (8, "Red Lions", "red-lions.png", 15, 5, 5, 5, 12, 13, -1, 20, "DLWDL"),
        (9, "Civo Utd", "civo.png", 15, 6, 2, 7, 10, 14, -4, 20, "WWWLL"),
        (10, "Mitundu Baptist", "luanar.png", 14, 5, 4, 5, 12, 13, -1, 19, "DLWDW"),
        (11, "Ekhaya", "ekhaya.png", 15, 4, 6, 5, 15, 14, 1, 18, "DLLDL"),
        (12, "Karonga United", "karonga.png", 15, 3, 5, 7, 14, 23, -9, 14, "DDLLW"),
        (13, "Dedza Dynamos", "dedza.png", 14, 3, 5, 6, 9, 19, -10, 14, "DDDWL"),
        (14, "MAFCO", "mafco.png", 15, 3, 4, 8, 12, 17, -5, 13, "LLDLL"),
        (15, "Kamuzu Barracks", "kamuzu-barracks.png", 15, 3, 3, 9, 15, 22, -7, 12, "LDLDW"),
        (16, "Creck Sporting", "creck.png", 15, 2, 4, 9, 11, 20, -9, 10, "DWDLL"),
    ]
    for pos, name, logo, p, w, d, l, gf, ga, gd, pts, form in standings:
        cur.execute("""
            INSERT INTO league_standings (league_name, position, team_name, logo_file, played, won, drawn, lost, goals_for, goals_against, goal_diff, points, form)
            VALUES ('FDH Premiership', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (pos, name, logo, p, w, d, l, gf, ga, gd, pts, form))
    conn.commit()
    conn.close()


def seed_fixtures():
    conn = get_connection()
    cur = conn.cursor()
    # Fixtures are derived seed data — rebuild them every startup so the
    # calendar always reflects the real FDH Bank Premiership 2026/27 season.
    cur.execute("DELETE FROM fixtures")

    fixtures = [
        # (matchweek, date, kick_off, home_team, away_team, home_score, away_score, venue, status)
        (1, "2026-04-26", "14:30", "Blue Eagles", "Ekhaya FC", 2, 1, "Nankhaka Stadium", "played"),
        (2, "2026-05-02", "14:30", "Ekhaya FC", "Red Lions", 1, 1, "Chiwembe Stadium", "played"),
        (3, "2026-05-09", "14:30", "Civo Utd", "Ekhaya FC", 1, 0, "Civo Stadium", "played"),
        (4, "2026-05-16", "14:30", "Ekhaya FC", "Moyale Barracks", 2, 0, "Chiwembe Stadium", "played"),
        (5, "2026-05-23", "14:30", "Kamuzu Barracks", "Ekhaya FC", 1, 4, "Champion Stadium", "played"),
        (6, "2026-05-30", "14:30", "Ekhaya FC", "Masters FC", 2, 0, "Chiwembe Stadium", "played"),
        (7, "2026-06-20", "14:30", "Mighty Wanderers", "Ekhaya FC", 1, 1, "Chiwembe Stadium", "played"),
        (8, "2026-06-28", "14:30", "Ekhaya FC", "MAFCO", 1, 0, "Chiwembe Stadium", "played"),
        (9, "2026-07-05", "14:30", "Mitundu Baptist", "Ekhaya FC", 0, 0, "Dedza Stadium", "played"),
        (10, "2026-07-19", "14:30", "Ekhaya FC", "Big Bullets", 0, 0, "Chiwembe Stadium", "played"),
        (11, "2026-07-25", "14:30", "Chitipa United", "Ekhaya FC", 1, 0, "Chitipa Stadium", "played"),
        (12, "2026-08-08", "14:30", "Ekhaya FC", "Dedza Dynamos", 1, 1, "Chiwembe Stadium", "played"),
        (13, "2026-08-15", "14:30", "Silver Strikers", "Ekhaya FC", 3, 0, "Silver Stadium", "played"),
        (14, "2026-08-22", "14:30", "Creck Sporting", "Ekhaya FC", 3, 2, "Aubrey Dimba Stadium", "played"),
        (15, "2026-09-06", "14:30", "Ekhaya FC", "Karonga United", 0, 0, "Chiwembe Stadium", "played"),
        (16, "2026-10-10", "14:30", "Ekhaya FC", "Kamuzu Barracks", None, None, "Chiwembe Stadium", "upcoming"),
        (17, "2026-10-18", "14:30", "Red Lions", "Ekhaya FC", None, None, "Zomba Stadium", "upcoming"),
        (18, "2026-10-25", "14:30", "Ekhaya FC", "Blue Eagles", None, None, "Chiwembe Stadium", "upcoming"),
        (19, "2026-11-01", "14:30", "MAFCO", "Ekhaya FC", None, None, "Champion Stadium", "upcoming"),
        (20, "2026-11-21", "14:30", "Ekhaya FC", "Civo Utd", None, None, "Chiwembe Stadium", "upcoming"),
        (21, "2026-11-28", "14:30", "Masters FC", "Ekhaya FC", None, None, "Bingu National Stadium", "upcoming"),
        (22, "2026-12-06", "14:30", "Ekhaya FC", "Mighty Wanderers", None, None, "Chiwembe Stadium", "upcoming"),
        (23, "2026-12-12", "14:30", "Moyale Barracks", "Ekhaya FC", None, None, "Rumphi Stadium", "upcoming"),
        (24, "2026-12-19", "14:30", "Ekhaya FC", "Mitundu Baptist", None, None, "Chiwembe Stadium", "upcoming"),
        (25, "2027-01-03", "14:30", "Big Bullets", "Ekhaya FC", None, None, "Chiwembe Stadium", "upcoming"),
        (26, "2027-01-16", "14:30", "Ekhaya FC", "Chitipa United", None, None, "Chiwembe Stadium", "upcoming"),
        (27, "2027-01-25", "14:30", "Dedza Dynamos", "Ekhaya FC", None, None, "Dedza Stadium", "upcoming"),
        (28, "2027-01-31", "14:30", "Ekhaya FC", "Silver Strikers", None, None, "Chiwembe Stadium", "upcoming"),
        (29, "2027-02-06", "14:30", "Ekhaya FC", "Creck Sporting", None, None, "Chiwembe Stadium", "upcoming"),
        (30, "2027-02-20", "14:30", "Karonga United", "Ekhaya FC", None, None, "Karonga Stadium", "upcoming"),
    ]
    for mw, date, ko, home, away, hs, as_, venue, status in fixtures:
        cur.execute("""
            INSERT INTO fixtures (matchweek, match_date, kick_off, home_team, away_team, home_score, away_score, venue, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (mw, date, ko, home, away, hs, as_, venue, status))
    conn.commit()
    conn.close()


def seed_reserve_standings():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM league_standings WHERE league_name = 'FincaDL1'")
    if cur.fetchone()[0] > 0:
        conn.close()
        return

    standings = [
        (1, "Ekhaya Reserve", "ekhaya.png", 12, 27),
        (2, "Thondwe", None, 14, 27),
        (3, "Liberty", None, 13, 26),
        (4, "Big Bullets Rsv", None, 12, 25),
        (5, "Immigration", None, 13, 25),
        (6, "Wanderers Rsv", None, 12, 20),
        (7, "Nyambadwe Utd", None, 12, 20),
        (8, "Mwanza Stars", None, 12, 20),
        (9, "QPL All Stars", None, 13, 14),
        (10, "Zingwangwa", None, 12, 13),
        (11, "The Boyz", None, 9, 12),
        (12, "Mwanza United", None, 13, 12),
        (13, "Nchima United", None, 13, 11),
        (14, "Ntopwa", None, 11, 9),
        (15, "Chilomoni", None, 14, 9),
        (16, "Chiradzulu United", None, 13, 6),
    ]
    for pos, name, logo, played, pts in standings:
        cur.execute("""
            INSERT INTO league_standings (league_name, position, team_name, logo_file, played, goals_for, goals_against, goal_diff, points)
            VALUES ('FincaDL1', ?, ?, ?, ?, 0, 0, 0, ?)
        """, (pos, name, logo, played, pts))
    conn.commit()
    conn.close()


def add_performance_match(team_id, opponent, competition, match_date, venue,
                          total_time, distance_m, hs_distance_m,
                          accel_decel_count, athletes_count, team_shape_file,
                          home_score=None, away_score=None, home_away=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO performance_matches
        (team_id, opponent, competition, match_date, venue, total_time,
         distance_m, hs_distance_m, accel_decel_count, athletes_count,
         team_shape_file, home_score, away_score, home_away)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (team_id, opponent, competition, match_date, venue, total_time,
          distance_m, hs_distance_m, accel_decel_count, athletes_count,
          team_shape_file, home_score, away_score, home_away))
    mid = cur.lastrowid
    conn.commit()
    conn.close()
    return mid


def add_performance_player_stat(mid, player_id, position, vals):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO performance_player_stats
        (performance_match_id, player_id, position, distance_m, hs_distance_m,
         max_acceleration, max_deceleration, player_load, overall_pct,
         sprint_distance_m, accel_decel_efforts)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (mid, player_id, position, vals.get("Distance (m)"),
          vals.get("High Speed Distance (m)"), vals.get("Max Acceleration"),
          vals.get("Max Deceleration"), vals.get("Player Load"),
          vals.get("Overall (%)"), vals.get("Sprint Distance (m)"),
          vals.get("Accel & Decel Efforts")))
    conn.commit()
    conn.close()


def get_performance_matches(team_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM performance_matches
        WHERE team_id = ?
        ORDER BY match_date ASC
    """, (team_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def seed_reference_performance():
    """Enter the Ekhaya Performance System reference data (players'
    positions, GPS match totals, physical aggregates, minutes logs).
    Idempotent — safe to re-run."""
    from performance_data import (POSITION_MAP, REF_MATCHES, PHYSICAL,
                                  POSITION_LABELS, MINUTES_RANGE,
                                  APPEARANCE_LIKELIHOOD, MINUTES_SEED)
    import random

    conn = get_connection()
    cur = conn.cursor()

    # 1. Player positions by full name (fall back to reversed-name match).
    name_to_id = {}
    reverse_to_id = {}
    cur.execute("SELECT id, first_name, last_name FROM players WHERE team_id = 1")
    for row in cur.fetchall():
        full = "{} {}".format(row["first_name"], row["last_name"]).strip()
        name_to_id[full] = row["id"]
        reverse_to_id["{} {}".format(row["last_name"],
                                      row["first_name"]).strip()] = row["id"]

    def resolve(full_name):
        pid = name_to_id.get(full_name)
        if pid is None:
            pid = reverse_to_id.get(full_name)
        return pid

    for full_name, info in POSITION_MAP.items():
        pid = resolve(full_name)
        if pid is None:
            continue
        cur.execute("UPDATE players SET position = ?, squad_number = ? "
                    "WHERE id = ?",
                    (info["position"], info["number"] or None, pid))

    # 2. Reference GPS match totals on the 12 matching performance_matches.
    for rm in REF_MATCHES:
        cur.execute("""
            UPDATE performance_matches
            SET opponent = ?, competition = ?, distance_m = ?,
                hs_distance_m = ?, accel_decel_count = ?,
                total_time = ?, volume_pct = ?, intensity_pct = ?,
                overall_pct = ?
            WHERE team_id = 1 AND match_date = ?
        """, (rm["opp"], rm["competition"], rm["dist"], rm["hs"], rm["ad"],
              rm["time"], rm["vol"], rm["inten"], rm["overall"], rm["date"]))

    # 3. Physical aggregates per player.
    for full_name, info in PHYSICAL.items():
        pid = resolve(full_name)
        if pid is None:
            continue
        cur.execute("""
            INSERT INTO performance_physical
            (player_id, position, sessions_tracked, avg_distance,
             avg_hs_distance, avg_player_load, avg_max_accel,
             avg_max_decel, avg_ad_efforts)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(player_id) DO UPDATE SET
                position = excluded.position,
                sessions_tracked = excluded.sessions_tracked,
                avg_distance = excluded.avg_distance,
                avg_hs_distance = excluded.avg_hs_distance,
                avg_player_load = excluded.avg_player_load,
                avg_max_accel = excluded.avg_max_accel,
                avg_max_decel = excluded.avg_max_decel,
                avg_ad_efforts = excluded.avg_ad_efforts
        """, (pid, info.get("position"),
              info.get("sessionsTracked", 0),
              info.get("avgDistance", 0), info.get("avgHSDistance", 0),
              info.get("avgPlayerLoad", 0), info.get("avgMaxAccel", 0),
              info.get("avgMaxDecel", 0),
              info.get("avgAccelDecelEfforts", 0)))

    # 4. Minutes logs — deterministic, role-based.
    cur.execute("""SELECT opponent, match_date FROM performance_matches
                   WHERE team_id = 1 AND match_date IS NOT NULL
                   ORDER BY match_date""")
    matches = cur.fetchall()
    if not matches:
        conn.commit()
        conn.close()
        return
    cur.execute("DELETE FROM performance_minutes WHERE player_id IN ("
                "SELECT id FROM players WHERE team_id = 1)")
    cur.execute("SELECT id, first_name, last_name, position "
                "FROM players WHERE team_id = 1")
    squad = cur.fetchall()
    label_map = {"Goalkeeper": "GK", "Center Back": "CB", "Full Back": "FB",
                 "Central Midfielder": "CM", "Winger": "WM",
                 "Forward": "FW"}
    rng = random.Random(MINUTES_SEED)
    for row in squad:
        full = "{} {}".format(row["first_name"], row["last_name"]).strip()
        info = POSITION_MAP.get(full, {})
        code = info.get("code") or label_map.get(row["position"], "CM")
        lo, hi = MINUTES_RANGE.get(code, (40, 95))
        like = APPEARANCE_LIKELIHOOD.get(code, 0.75)
        for m in matches:
            if rng.random() < like:
                mins = rng.randint(lo, hi)
                label = "vs {} — {}".format(m["opponent"], m["match_date"])
                cur.execute(
                    "INSERT INTO performance_minutes "
                    "(player_id, match_label, minutes) VALUES (?,?,?)",
                    (row["id"], label, mins))

    conn.commit()
    conn.close()


def get_performance_minutes(team_id):
    """All minutes-log entries for a team's squad."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT pm.player_id, pm.match_label, pm.minutes,
               p.first_name || ' ' || p.last_name AS name,
               p.position, p.squad_number
        FROM performance_minutes pm
        JOIN players p ON p.id = pm.player_id
        WHERE p.team_id = ?
        ORDER BY pm.id
    """, (team_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_performance_physical(team_id):
    """Per-player GPS physical aggregates for a team."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT pp.*, p.first_name || ' ' || p.last_name AS name
        FROM performance_physical pp
        JOIN players p ON p.id = pp.player_id
        WHERE p.team_id = ?
        ORDER BY pp.avg_player_load DESC
    """, (team_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_performance_stats(match_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT pps.*, p.first_name || ' ' || p.last_name AS name,
               p.photo_url AS photo, p.position AS player_position
        FROM performance_player_stats pps
        JOIN players p ON p.id = pps.player_id
        WHERE pps.performance_match_id = ?
        ORDER BY pps.distance_m DESC
    """, (match_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_player_performance_stats(player_id):
    """Catapult GPS aggregates for a single player so the profile's
    distance-covered stat is auto-filled from the GPS reports."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) AS tracked_matches,
               COALESCE(SUM(pps.distance_m), 0) AS total_distance,
               COALESCE(SUM(pps.hs_distance_m), 0) AS total_hs,
               COALESCE(SUM(pps.player_load), 0) AS total_load,
               COALESCE(SUM(pps.sprint_distance_m), 0) AS total_sprint,
               COALESCE(MAX(pps.distance_m), 0) AS peak_distance,
               COALESCE(MAX(pps.overall_pct), 0) AS peak_overall
        FROM performance_player_stats pps
        WHERE pps.player_id = ?
    """, (player_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else {}


def get_player_performance_matches(player_id):
    """Per-match Catapult GPS rows for a single player (newest first)."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT pm.match_date, pm.opponent,
               COALESCE(pm.home_score, 0) AS home_score,
               COALESCE(pm.away_score, 0) AS away_score,
               COALESCE(pm.home_away, 'home') AS home_away,
               pps.position, pps.distance_m, pps.hs_distance_m,
               pps.player_load, pps.overall_pct, pps.sprint_distance_m
        FROM performance_player_stats pps
        JOIN performance_matches pm ON pm.id = pps.performance_match_id
        WHERE pps.player_id = ?
        ORDER BY pm.match_date DESC
    """, (player_id,))
    rows = cur.fetchall()
    conn.close()
    return rows




def get_player_medical(player_id):
    """Get all medical records for a player."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM player_medical
        WHERE player_id = ?
        ORDER BY diagnosed_date DESC
    """, (player_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def add_medical_record(player_id, injury_type, body_part, severity, status, diagnosed_date, expected_return, notes):
    """Add a new medical record for a player."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO player_medical (player_id, injury_type, body_part, severity, status, diagnosed_date, expected_return, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (player_id, injury_type, body_part, severity, status, diagnosed_date, expected_return, notes))
    conn.commit()
    record_id = cur.lastrowid
    conn.close()
    return record_id

def update_medical_record(record_id, **kwargs):
    """Update a medical record."""
    if not kwargs:
        return
    conn = get_connection()
    cur = conn.cursor()
    fields = ', '.join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [record_id]
    cur.execute(f"UPDATE player_medical SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()

def delete_medical_record(record_id):
    """Delete a medical record."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM player_medical WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()

def get_team_medical_summary(team_id):
    """Get all active injuries for a team."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT pm.*, p.first_name, p.last_name, p.squad_number
        FROM player_medical pm
        JOIN players p ON pm.player_id = p.id
        WHERE p.team_id = ? AND pm.status = 'active'
        ORDER BY pm.diagnosed_date DESC
    """, (team_id,))
    rows = cur.fetchall()
    conn.close()
    return rows



def seed_performance_data():
    conn = get_connection()
    try:
        has_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='performance_matches'"
        ).fetchone()
        if not has_table:
            conn.close()
            return
    except sqlite3.OperationalError:
        conn.close()
        return

    import re
    import json

    data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "data", "performance.json")
    if not os.path.exists(data_file):
        conn.close()
        return

    with open(data_file) as f:
        reports = json.load(f)

    conn.execute("DELETE FROM performance_player_stats")
    conn.execute("DELETE FROM performance_matches")
    conn.commit()

    players = {row["id"]: row for row in conn.execute(
        "SELECT id, last_name, first_name, squad_number FROM players").fetchall()}

    def norm(s):
        return re.sub(r"[^a-z0-9]", "", s.lower())

    ALIASES = {
        "mateyu": "mateyo",
    }

    index = {}
    for pid, row in players.items():
        index.setdefault(ALIASES.get(norm(row["last_name"]), norm(row["last_name"])) +
                         ALIASES.get(norm(row["first_name"]), norm(row["first_name"])), pid)
        index.setdefault(ALIASES.get(norm(row["first_name"]), norm(row["first_name"])) +
                         ALIASES.get(norm(row["last_name"]), norm(row["last_name"])), pid)

    def match_player(name_raw):
        parts = [ALIASES.get(norm(x), norm(x)) for x in re.split(r"[\s,]+", name_raw) if norm(x)]
        seen = set()
        for i in range(len(parts)):
            for j in range(i + 1, len(parts) + 1):
                key = "".join(parts[i:j])
                if key in index:
                    return index[key]
                if key.endswith("jr") or key.endswith("jnr"):
                    for suffix in ("jr", "jnr"):
                        if key[: -len(suffix)] in index:
                            return index[key[: -len(suffix)]]
                seen.add(key)
        return None

    # Opponent names from the fixture calendar by date, so GPS reports
    # merge into the same match row (no date-based duplicates).
    try:
        frows = conn.execute("""
            SELECT * FROM fixtures
            WHERE (home_team LIKE '%Ekhaya%' OR away_team LIKE '%Ekhaya%')
              AND status = 'played'
            ORDER BY match_date
        """).fetchall()
    except sqlite3.OperationalError:
        frows = []

    fixture_opponent = {}
    for f in frows:
        is_home = f["home_team"].strip().lower() == "ekhaya fc"
        opp = f["away_team"] if is_home else f["home_team"]
        fixture_opponent[f["match_date"]] = opp

    for r in reports:
        summary = r.get("summary") or {}
        opp = r.get("opponent")
        date = r.get("date")
        if date and date in fixture_opponent:
            opp = fixture_opponent[date]
        mid = add_performance_match(
            team_id=1,
            opponent=opp,
            competition=r.get("competition"),
            match_date=date,
            venue=summary.get("venue"),
            total_time=summary.get("total_time"),
            distance_m=None,
            hs_distance_m=None,
            accel_decel_count=None,
            athletes_count=len(r.get("players", [])),
            team_shape_file=r.get("team_shape"),
        )
        for p in r.get("players", []):
            vals = p.get("values", {}) or {}
            pid = match_player(p.get("name_raw", ""))
            if pid is None:
                continue
            add_performance_player_stat(mid, pid, p.get("position"), vals)

    # Extra reports from the fixtures calendar: every played Ekhaya match
    # becomes an activity report; GPS-backed ones are already inserted above.
    added = 0
    try:
        frows2 = conn.execute("""
            SELECT * FROM fixtures
            WHERE (home_team LIKE '%Ekhaya%' OR away_team LIKE '%Ekhaya%')
              AND status = 'played'
            ORDER BY match_date
        """).fetchall()
    except sqlite3.OperationalError:
        frows2 = []

    existing = set()
    for row in conn.execute(
            "SELECT opponent, match_date FROM performance_matches WHERE team_id = 1"):
        existing.add((row["opponent"], row["match_date"]))

    for f in frows2:
        is_home = f["home_team"].strip().lower() == "ekhaya fc"
        opp = f["away_team"] if is_home else f["home_team"]
        if (opp, f["match_date"]) in existing:
            conn.execute("""
                UPDATE performance_matches
                SET home_score = ?, away_score = ?, home_away = ?
                WHERE opponent = ? AND match_date = ? AND team_id = 1
            """, (f["home_score"], f["away_score"],
                  "home" if is_home else "away", opp, f["match_date"]))
            conn.commit()
            continue
        add_performance_match(
            team_id=1,
            opponent=opp,
            competition="FDH Premiership",
            match_date=f["match_date"],
            venue=f["venue"],
            total_time=None,
            distance_m=None,
            hs_distance_m=None,
            accel_decel_count=None,
            athletes_count=None,
            team_shape_file=None,
            home_score=f["home_score"],
            away_score=f["away_score"],
            home_away="home" if is_home else "away",
        )
        existing.add((opp, f["match_date"]))
        added += 1

    conn.commit()
    conn.close()
    print(f"[seed] Loaded {len(reports)} performance report(s) "
          f"+ {added} fixture report(s).")


def seed_competitions():
    """Create competitions (FDH Premiership, FincaDL1, Airtel Top 8) and
    populate with Ekhaya's results. FDH Premiership carries Ekhaya's full
    Super League history from Flashscore (2025/26 + 2026/27 seasons),
    FincaDL1 comes from the reserve fixture calendar, and Airtel Top 8 is
    the 2026 cup run."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, team_id, name FROM competitions")
    existing = cur.fetchall()

    # competition name -> (team_id, comp_type, season, is_champion)
    comp_defs = [
        ("FDH Premiership", 1, "league", "2026/27", 0),
        ("FincaDL1",         3, "league", "2026/27", 0),
        ("Airtel Top 8",     1, "cup",    "2026",    1),
    ]
    comp_by_name = {}
    for row in existing:
        comp_by_name.setdefault(row["name"], row["id"])
    for (name, tid, ctype, season, champion) in comp_defs:
        if name in comp_by_name:
            cid = comp_by_name[name]
            cur.execute(
                "UPDATE competitions SET team_id=?, comp_type=?, season=?, is_champion=? WHERE id=?",
                (tid, ctype, season, champion, cid))
            comp_by_name[name] = cid
        else:
            cur.execute("""
                INSERT INTO competitions (team_id, name, comp_type, season, is_champion)
                VALUES (?, ?, ?, ?, ?)
            """, (tid, name, ctype, season, champion))
            comp_by_name[name] = cur.lastrowid

    # Rebuild results for every competition fresh each seed (idempotent).
    for cid in comp_by_name.values():
        cur.execute("DELETE FROM matches WHERE competition_id = ?", (cid,))

    # FincaDL1 reserve matches pulled from the fixture calendar.
    for f in conn.execute("""
            SELECT * FROM fixtures
            WHERE status = 'played'
            ORDER BY match_date
        """):
        if "Ekhaya Reserve" not in (f["home_team"], f["away_team"]):
            continue
        is_home = "Ekhaya Reserve" in f["home_team"]
        opponent = f["away_team"] if is_home else f["home_team"]
        team_score = f["home_score"] if is_home else f["away_score"]
        opp_score = f["away_score"] if is_home else f["home_score"]
        if team_score is None or opp_score is None:
            continue
        if team_score > opp_score:
            result = "W"
        elif team_score < opp_score:
            result = "L"
        else:
            result = "D"
        cur.execute("""
            INSERT INTO matches (team_id, competition_id, match_date, opponent,
                venue, team_score, opponent_score, result)
            VALUES (3, ?, ?, ?, ?, ?, ?, ?)
        """, (comp_by_name["FincaDL1"], f["match_date"], opponent,
              "Home" if is_home else "Away", team_score, opp_score, result))

    # FDH Premiership — Ekhaya's full Super League history from Flashscore.
    # (date, opponent, venue, Ekhaya goals, opponent goals)
    # Home/away and scores decoded from flashscore.com/team/ekhaya results
    # feed: WM = home team, AG = home goals, AH = away goals.
    fdh_matches = [
        # 2025/26 season
        ("2025-04-21", "Chitipa United",   "Away", 0, 1),
        ("2025-04-26", "Songwe Border",    "Away", 2, 1),
        ("2025-05-17", "Kamuzu Barracks",  "Away", 0, 1),
        ("2025-05-21", "Karonga United",   "Home", 2, 0),
        ("2025-05-31", "Blue Eagles",      "Away", 0, 0),
        ("2025-06-14", "Creck Sporting",   "Home", 1, 0),
        ("2025-06-22", "Mzuzu City",       "Away", 3, 1),
        ("2025-06-28", "Dedza Dynamos",    "Away", 0, 0),
        ("2025-07-02", "Big Bullets",      "Home", 0, 1),
        ("2025-07-13", "Mighty Wanderers", "Home", 0, 1),
        ("2025-07-20", "Moyale Barracks",  "Home", 3, 0),
        ("2025-07-26", "Silver Strikers",  "Away", 1, 3),
        ("2025-08-09", "MAFCO",            "Home", 1, 0),
        ("2025-08-24", "Mzuzu City",       "Home", 1, 2),
        ("2025-08-27", "Civo Utd",         "Away", 0, 1),
        ("2025-09-27", "MAFCO",            "Away", 1, 2),
        ("2025-10-04", "Songwe Border",    "Home", 4, 1),
        ("2025-10-22", "Kamuzu Barracks",  "Home", 3, 0),
        ("2025-10-25", "Blue Eagles",      "Home", 1, 2),
        ("2025-11-01", "Dedza Dynamos",    "Home", 1, 1),
        ("2025-11-22", "Chitipa United",   "Home", 3, 0),
        ("2025-11-30", "Karonga United",   "Away", 1, 0),
        ("2025-12-04", "Moyale Barracks",  "Away", 1, 2),
        ("2025-12-07", "Mighty Wanderers", "Away", 0, 1),
        ("2025-12-10", "Silver Strikers",  "Home", 0, 1),
        ("2025-12-14", "Big Bullets",      "Away", 0, 2),
        ("2025-12-17", "Creck Sporting",   "Away", 2, 4),
        ("2025-12-27", "Mighty Tigers",    "Away", 2, 0),
        ("2026-01-24", "Dedza Dynamos",    "Home", 0, 2),
        # 2026/27 season
        ("2026-04-26", "Blue Eagles",      "Away", 1, 2),
        ("2026-05-02", "Red Lions",        "Home", 1, 1),
        ("2026-05-09", "Civo Utd",         "Away", 0, 1),
        ("2026-05-16", "Moyale Barracks",  "Home", 2, 0),
        ("2026-05-23", "Kamuzu Barracks",  "Away", 4, 1),
        ("2026-05-30", "Masters FC",       "Home", 2, 0),
        ("2026-06-20", "Mighty Wanderers", "Away", 1, 1),
        ("2026-06-28", "MAFCO",            "Home", 1, 0),
        ("2026-07-05", "Mitundu Baptist",  "Away", 0, 0),
        ("2026-07-19", "Big Bullets",      "Home", 0, 0),
        ("2026-07-25", "Chitipa United",   "Away", 0, 1),
        ("2026-08-08", "Dedza Dynamos",    "Home", 1, 1),
        ("2026-08-15", "Silver Strikers",  "Away", 0, 3),
        ("2026-08-22", "Creck Sporting",   "Away", 2, 3),
        ("2026-09-06", "Karonga United",   "Home", 0, 0),
    ]
    for (mdate, opp, venue, ts, os_) in fdh_matches:
        result = "W" if ts > os_ else ("L" if ts < os_ else "D")
        cur.execute("""
            INSERT INTO matches (team_id, competition_id, match_date, opponent,
                venue, team_score, opponent_score, result)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?)
        """, (comp_by_name["FDH Premiership"], mdate, opp, venue, ts, os_, result))

    # Airtel Top 8 2026 — Ekhaya FC cup run.
    # (date, opponent, venue, team score, opp score, result, scorers)
    # Scorer lines: "Name (E, 70')" or "Name (O, 49' pen)" — E = Ekhaya, O = opposing.
    airtel_matches = [
        ("2026-06-13", "FCB Nyasa Big Bullets", "Bingu National Stadium",
         1, 1, "D",
         "Allen Chihana (E, 70'); George Chaomba (O, 46')"),
        ("2026-07-11", "FCB Nyasa Big Bullets", "Mpira Stadium",
         1, 1, "D",
         "Allen Chihana (E, 44'); Peter Banda (O, 59'). Won 7-6 on penalties"),
        ("2026-08-01", "Karonga United", "Silver Stadium",
         2, 1, "W",
         "Allen Chihana (E, 44'); Chimwemwe Chunga (E, 73'); Lonex Kiwambe (O, 49' pen)"),
        ("2026-08-30", "Mighty Wanderers", "Bingu National Stadium",
         2, 1, "W",
         "Blessings Malinda (E, 38' pen); Allen Chihana (E, 59'); Mphatso Kamanga (O, 49')"),
    ]
    for (mdate, opp, venue, ts, os_, res, scorers) in airtel_matches:
        cur.execute("""
            INSERT INTO matches (team_id, competition_id, match_date, opponent,
                venue, team_score, opponent_score, result, scorers)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (comp_by_name["Airtel Top 8"], mdate, opp, venue,
              ts, os_, res, scorers))
    conn.commit()
    conn.close()
    print(f"[seed] Competition results loaded.")


if __name__ == "__main__":
    init_db()
    seed_demo_data()
    seed_standings()
    seed_reserve_standings()
    seed_fixtures()
