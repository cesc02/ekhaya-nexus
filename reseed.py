"""Repopulate teams 1, 2, 3 with real rosters.

``run()`` is called automatically by app.py on every startup so a fresh
Render deploy (ephemeral SQLite) always has the correct squad data.
"""
import os, sys


def run():
    """Wipe demo players and re-insert the real squads for teams 1–3."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from database import get_connection, init_db

    init_db()
    conn = get_connection()
    cur = conn.cursor()

    # Clear child rows first (some FKs lack ON DELETE CASCADE, and wiped
    # players are re-created with new ids), then wipe players for teams 1-3.
    for table in ("player_medical", "player_stats",
                  "performance_player_stats", "performance_physical",
                  "performance_minutes"):
        cur.execute("DELETE FROM %s" % table)
    for tid in [1, 2, 3]:
        cur.execute("DELETE FROM players WHERE team_id = ?", (tid,))

    # --- FIRST TEAM (team_id=1) from Excel ---
    first_team = [
        ("Amos", "Sande", 1, "Goalkeeper", "2007-03-03"),
        ("Clever", "Mkungula", 31, "Goalkeeper", "2000-02-13"),
        ("Joshua", "Waka", 99, "Goalkeeper", "2004-04-28"),
        ("Lucky", "Tizola", 13, "Goalkeeper", "2003-03-25"),
        ("Charles", "Mafaiti", 21, "Defender", "2003-06-11"),
        ("Happy", "Mphepo", 19, "Defender", "2006-02-01"),
        ("Fanizo", "Mwansambo", 15, "Defender", "2000-12-30"),
        ("Mohamed Mudrick", "Salum", None, "Defender", "1999-12-01"),
        ("Andrew", "Lameck", 14, "Defender", "2004-12-25"),
        ("Josephy", "McDonald", 26, "Defender", "2004-01-22"),
        ("Joseph", "Saiwa", 16, "Defender", "2006-05-09"),
        ("Aubrey", "Simbi", 5, "Defender", "2003-01-21"),
        ("Hermas", "Masinja", 17, "Defender", "2006-02-19"),
        ("Alick", "Lungu", 3, "Defender", "2002-01-01"),
        ("Samuel", "Rukura", 29, "Defender", "2004-05-15"),
        ("Vincent", "Salawira", 4, "Midfielder", "2004-08-28"),
        ("Moses", "Banda", 8, "Midfielder", "2002-09-11"),
        ("Hadji", "James", 6, "Midfielder", "2004-04-07"),
        ("Isaiah", "Nyirenda", 7, "Midfielder", "2003-12-01"),
        ("Blessings", "Malinda", 47, "Midfielder", "2003-05-21"),
        ("Limbani", "Kutambe", None, "Midfielder", "2004-09-17"),
        ("Alfred", "Chizinga", 42, "Midfielder", "1998-02-04"),
        ("Levison", "Mnyenyembe", 98, "Forward", "2005-12-13"),
        ("James", "Lumbe", 25, "Forward", "2009-12-15"),
        ("Wongani", "Kaponya", 23, "Forward", "2003-03-29"),
        ("Gift", "Magola", 30, "Forward", "2000-04-01"),
        ("Chimwemwe", "Chunga", 11, "Forward", "2002-05-11"),
        ("George", "Mateyo", 22, "Forward", "2001-11-28"),
        ("Allen", "Chihana", 20, "Forward", "2004-08-18"),
        ("James", "Stambuli", 9, "Forward", "2006-09-05"),
        ("Gift", "Chunga", 27, "Forward", "2000-10-17"),
        ("Davie", "Juao", 18, "Forward", "2004-05-25"),
    ]

    for fn, ln, num, pos, dob in first_team:
        cur.execute("""
            INSERT INTO players (team_id, first_name, last_name, squad_number,
                position, date_of_birth, nationality, strong_foot)
            VALUES (1, ?, ?, ?, ?, ?, 'Malawian', 'Right')
        """, (fn, ln, num, pos, dob))
        pid = cur.lastrowid
        cur.execute("INSERT INTO player_stats (player_id) VALUES (?)", (pid,))

    # --- WOMEN TEAM (team_id=2) ---
    women = [
        ("Evelyn", "Lloyo"), ("Rossette", "Mwadijuma"), ("Fortune", "Bwitu"),
        ("Precious", "Mipallino"), ("Catherine", "Mthambeko"), ("Mpiza", "Carlos"),
        ("Eliza", "Mugira"), ("Temwa", "Issa"), ("Sina", "John"),
        ("Tupochile", "Mbeza"), ("Thandi", "Elma"), ("Rabecca", "Miale"),
        ("Eunice", "Moses"), ("Hope", "Chikumba"), ("Miriam", "Dafter"),
        ("Agnes", "Jonathan"), ("Wonderful", "Jenala"), ("Esther", "Mhando"),
        ("Stella", "Chinkusa"), ("Eneless", "Fasiano"), ("Alepha", "Msova"),
        ("Scholastichah", "Chakalamba"), ("Kettie", "Munthali"),
        ("Merisha", "Memba"), ("Fatuma", "Zokomela"), ("Joyce", "Kaira"),
    ]

    for i, (fn, ln) in enumerate(women, 1):
        cur.execute("""
            INSERT INTO players (team_id, first_name, last_name, squad_number,
                position, nationality, strong_foot)
            VALUES (2, ?, ?, ?, 'Forward', 'Malawian', 'Right')
        """, (fn, ln, i))
        pid = cur.lastrowid
        cur.execute("INSERT INTO player_stats (player_id) VALUES (?)", (pid,))

    # --- RESERVE TEAM (team_id=3) ---
    reserve = [
        ("Luciano", "Fanuel"), ("Ninu", "Khosomora"), ("Jacob", "Phiri"),
        ("Evans", "Sambani"), ("Rex", "Chikaya"), ("Chimwemwe", "Masha"),
        ("Blessings", "Mathyola"), ("Tamandani", "Damiano"),
        ("Precious", "Manjawira"), ("Arthur", "Chindaya"), ("Innocent", "Munga"),
        ("Francis", "Chimbayo"), ("Maxwell", "Sakanamba"), ("Peter", "Kasiya"),
        ("Dominic", "Kayamba"), ("Patrick", "Dominic"), ("Rafael", "Iman"),
        ("Daniel", "Maulidi"), ("Geofrey", "Chinyama"), ("Yusuf", "Namtunga"),
        ("Davie", "Chinkhanga"), ("Hastings", "Malinda"),
        ("Dalis on", "Yawanda"), ("Yohane", "Jim"),
    ]

    for i, (fn, ln) in enumerate(reserve, 1):
        cur.execute("""
            INSERT INTO players (team_id, first_name, last_name, squad_number,
                position, nationality, strong_foot)
            VALUES (3, ?, ?, ?, 'Forward', 'Malawian', 'Right')
        """, (fn, ln, i))
        pid = cur.lastrowid
        cur.execute("INSERT INTO player_stats (player_id) VALUES (?)", (pid,))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    from database import init_db, get_connection
    init_db()
    run()
    # Verify counts
    conn = get_connection()
    cur = conn.cursor()
    for tid, name in [(1, "First Team"), (2, "Women"), (3, "Reserve")]:
        cur.execute("SELECT COUNT(*) FROM players WHERE team_id = ?", (tid,))
        print(f"{name}: {cur.fetchone()[0]} players")
    conn.close()
