"""
extract_performance.py - Extract per-player Catapult GPS performance data,
match summary and team heat map from Ekhaya FC Catapult activity report PDFs.

Usage:
  python3 tools/extract_performance.py [path/to/pdf] [--out dir]
  (with no args, scans the Downloads folder for Catapult reports)
"""

import os
import re
import sys
import json
import warnings

warnings.filterwarnings("ignore")

import fitz
from rapidocr_onnxruntime import RapidOCR

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOADS = os.path.expanduser("~/Downloads")
HEAT_DIR = os.path.join(BASE_DIR, "static", "img", "performance")
DATA_DIR = os.path.join(BASE_DIR, "data")

POSITION_CODES = {"GK", "CB", "CM", "FB", "WM", "ST", "CF", "AM", "LB", "RB", "CDM", "CAM", "RW", "LW", "DM"}

COL_HEADERS = ["Name", "Position", "Distance (m)", "High Speed Distance (m)",
               "Max Acceleration", "Max Deceleration", "Player Load",
               "Overall (%)", "Sprint Distance (m)", "Accel & Decel Efforts"]


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def parse_date_from_name(name):
    m = re.search(r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})?", name, re.I)
    months = {mo: i + 1 for i, mo in enumerate(
        ["January", "February", "March", "April", "May", "June", "July",
         "August", "September", "October", "November", "December"])}
    if m:
        day = int(m.group(1))
        month = months[m.group(2).title()]
        year = int(m.group(3)) if m.group(3) else 2026
        return f"{year:04d}-{month:02d}-{day:02d}"
    m = re.search(r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", name, re.I)
    if m:
        months = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                  "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
        return f"2026-{months[m.group(2).title()]:02d}-{int(m.group(1)):02d}"
    m = re.search(r"(\d{1,2})\s+(\d{1,2})\s+(\d{2,4})", name)
    if m:
        return f"2026-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None


def guess_comp(name):
    n = norm(name)
    if "airtel" in n:
        if "semi" in n or "final" in n:
            return "Airtel Cup"
        return "Airtel Cup"
    return "FDH Premiership"


def guess_opponent(name):
    base = os.path.splitext(os.path.basename(name))[0]
    base = re.sub(r"\s*catapult\s*report", "", base, flags=re.I)
    base = re.sub(r"\s*report\s*", "", base, flags=re.I)
    base = re.sub(r"\s*vs\.?\s*", "|", base, flags=re.I)
    base = re.sub(r"\s+\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{4}|\d{2})", "", base, flags=re.I)
    base = re.sub(r"\s+\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)[a-z]*\.?\s+(\d{4})?", "", base, flags=re.I)
    base = re.sub(r"\s+\d{1,2}\s+\d{1,2}\s+\d{2,4}", "", base)
    base = re.sub(r"(\s+semifinal|\s+final|\s+airtel\s*cup|\s*airtel|\s*cup)", "", base, flags=re.I)
    base = re.sub(r"[^A-Za-z ]+", " ", base)
    parts = [re.sub(r"\s+", " ", p).strip() for p in base.split("|") if p.strip()]
    if parts:
        return parts[0].strip()
    return "Unknown"


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", norm(s)).strip("-")


def is_number(tok):
    t = tok.replace(",", "").replace("%", "").replace(":", "")
    if not t:
        return False
    try:
        float(t)
        return True
    except ValueError:
        return False


def is_time(tok):
    return bool(re.fullmatch(r"\d+:\d\d(:\d\d)?(\s?(am|pm))?", tok, re.I))


class OcrPage:
    def __init__(self, result):
        self.tokens = []
        if not result:
            return
        for box, text, conf in result:
            x = int(box[0][0])
            y = int(box[0][1])
            x1 = int(box[2][0])
            y1 = int(box[2][1])
            cx = (x + x1) / 2
            cy = (y + y1) / 2
            self.tokens.append({
                "text": text, "x": x, "y": y, "x1": x1, "y1": y1,
                "cx": cx, "cy": cy, "num": is_number(text), "time": is_time(text),
            })

    def texts(self):
        return [t["text"] for t in self.tokens]

    def has(self, needle):
        for t in self.tokens:
            if norm(needle) in norm(t["text"]):
                return True
        return False

    def find(self, needle):
        for t in self.tokens:
            if norm(needle) in norm(t["text"]):
                return t
        return None


def detect_columns(page):
    """Return dict col_name -> x center, using header labels on the page."""
    cols = {}
    labels = {
        "Name": "Name", "Position": "Position", "Distance": "Distance (m)",
        "High Speed": "High Speed Distance (m)", "Max Accel": "Max Acceleration",
        "Max Decel": "Max Deceleration", "Player Load": "Player Load",
        "Overall": "Overall (%)", "Sprint": "Sprint Distance (m)",
        "Efforts": "Accel & Decel Efforts",
    }
    for needle, col in labels.items():
        t = page.find(needle)
        if t:
            cols[col] = t["cx"]
    return cols


METER_COLUMN_ORDER = ["High Speed Distance (m)", "Distance (m)",
                      "Max Acceleration", "Max Deceleration",
                      "Player Load", "Overall (%)",
                      "Sprint Distance (m)", "Accel & Decel Efforts"]

COLUMN_HEADER_WORDS = {"name", "position", "distance", "high", "speed", "max",
                       "accel", "decel", "player", "load", "overall", "sprint",
                       "accel&decel", "efforts"}


def cluster_rows(tokens):
    """Group numeric tokens into rows by y proximity."""
    rows = []
    tok = sorted(tokens, key=lambda t: t["y"])
    for t in tok:
        placed = False
        for r in rows:
            if abs(r["y"] - t["y"]) <= 30:
                r["y"] = (r["y"] * r["n"] + t["y"]) / (r["n"] + 1)
                r["n"] += 1
                r["toks"].append(t)
                placed = True
                break
        if not placed:
            rows.append({"y": t["y"], "n": 1, "toks": [t]})
    return rows


def cluster_columns(value_tokens):
    """Group value tokens into x-column clusters; return list of clusters
    sorted by x, each as {cx, toks}."""
    toks = sorted(value_tokens, key=lambda t: t["cx"])
    clusters = []
    for t in toks:
        if clusters and abs(clusters[-1]["cx"] - t["cx"]) <= 55:
            c = clusters[-1]
            c["n"] += 1
            c["cx"] = (c["cx"] * (c["n"] - 1) + t["cx"]) / c["n"]
            c["toks"].append(t)
        else:
            clusters.append({"n": 1, "cx": t["cx"], "toks": [t]})
    return clusters


def looks_like_header_token(t):
    words = [w for w in re.split(r"[^a-z0-9]+", norm(t["text"])) if w]
    if not words:
        return False
    return all(w in COLUMN_HEADER_WORDS for w in words)


def group_name_occurrences(name_tokens):
    """Group consecutive name tokens by vertical proximity (<45px gap
    = same multi-line cell; larger gap = next player). Returns dicts with
    toks, y (median) and text."""
    occ = []
    cur = []
    prev_y = None
    for t in sorted(name_tokens, key=lambda t: (t["y"], t["x"])):
        if cur and (prev_y is not None) and (t["y"] - prev_y > 45):
            occ.append(cur)
            cur = []
        cur.append(t)
        prev_y = t["y"]
    if cur:
        occ.append(cur)
    out = []
    for o in occ:
        ys = [t["y"] for t in o]
        ys.sort()
        out.append({"toks": o,
                    "y": ys[len(ys) // 2],
                    "text": " ".join(t["text"] for t in o)})
    return out


def parse_breakdown_page(page):
    """Parse one Athlete Breakdown page into player rows."""
    cols = detect_columns(page)
    name_col_x = (cols.get("Name") or 0) + 60
    if name_col_x < 200:
        name_col_x = 310

    value_tokens = [t for t in page.tokens
                    if (t["num"] or t["time"]) and t["cx"] > name_col_x]
    if not value_tokens:
        return []
    rows = sorted(cluster_rows(value_tokens), key=lambda x: x["y"])

    col_clusters = cluster_columns(value_tokens)

    def col_of(t):
        best, best_d = None, 1000
        for c in col_clusters:
            d = abs(c["cx"] - t["cx"])
            if d < best_d:
                best, best_d = c, d
        by_cx = sorted(col_clusters, key=lambda cc: cc["cx"])
        return METER_COLUMN_ORDER[by_cx.index(best)]

    name_tokens = [t for t in page.tokens
                   if t["cx"] < name_col_x
                   and not t["num"] and not t["time"]
                   and not POSITION_CODES.intersection({t["text"].strip(",.")})
                   and not looks_like_header_token(t)]
    min_row_y = min(r["y"] for r in rows)
    name_tokens = [t for t in name_tokens if t["y"] > min_row_y - 40]
    occurrences = group_name_occurrences(name_tokens)

    def row_name(row):
        # nearest name occurrence to this row's y
        best, best_d = None, None
        for oy in [o.get("y") for o in occurrences]:
            d = abs(oy - row["y"])
            if best_d is None or d < best_d:
                best, best_d = oy, d
        for o in occurrences:
            if o.get("y") == best:
                return re.sub(r"\s+", " ", " ".join(t["text"] for t in o["toks"])).strip()
        return ""

    def build(row, name):
        vals = {k: None for k in METER_COLUMN_ORDER}
        for t in row["toks"]:
            col = col_of(t)
            if col:
                vals[col] = t["text"]
        pos = ""
        best_d = None
        for t in page.tokens:
            if POSITION_CODES.intersection({t["text"].strip(",.")}):
                d = abs(t["cy"] - row["y"])
                if best_d is None or d < best_d:
                    best_d, pos = d, t["text"]
        return {"name_raw": name, "position": pos,
                "row_y": round(row["y"]), "values": vals}

    parsed = []
    if len(occurrences) <= len(rows):
        paired = []
        for row in rows:
            name = row_name(row)
            paired.append((row, name))
        for row, name in paired:
            if "averag" in norm(name):
                continue
            parsed.append(build(row, name))
        return parsed

    for row, occ in zip(rows, occurrences):
        name = re.sub(r"\s+", " ", occ["text"]).strip()
        if "averag" in norm(name):
            continue
        parsed.append(build(row, name))
    return parsed


def extract_summary(page):
    """Parse Period Breakdown / summary numbers into key metric pairs."""
    metrics = {}
    tokens = page.tokens
    labels = {
        "Distance (m)": ["Distance"],
        "High Speed Dist (m)": ["HS Dist"],
        "Accel+Decel (#)": ["Accel+Decel"],
        "Athletes": ["Athletes"],
        "Duration": ["Duration"],
        "Start": ["Start"],
    }
    for key, needles in labels.items():
        for t in tokens:
            if any(norm(n) in norm(t["text"]) for n in needles):
                cands = [nxt for nxt in tokens
                         if abs(nxt["y"] - t["y"]) <= 45 and nxt["cx"] > t["cx"]
                         and (nxt["num"] or nxt["time"])]
                if not cands:
                    break
                want_time = key in ("Duration", "Start")
                timed = [c for c in cands if c["time"]]
                if want_time and timed:
                    best = min(timed, key=lambda c: abs(c["x"] - t["x1"]))
                else:
                    best = min(cands, key=lambda c: abs(c["x"] - t["x1"]))
                metrics[key] = best["text"]
                break
    return metrics


_OCR = None


def get_ocr():
    global _OCR
    if _OCR is None:
        _OCR = RapidOCR()
    return _OCR


def find_heat_map(doc):
    """Find the large team-shape/pitch diagram image (mostly graphic)."""
    best = None
    ocr = get_ocr()
    for pi in range(min(3, len(doc))):
        page = doc[pi]
        for img in page.get_images(full=True):
            xref = img[0]
            w, h = img[2], img[3]
            if w < 800 or h < 200:
                continue
            rects = page.get_image_rects(xref)
            if not rects:
                continue
            area = w * h
            pix = fitz.Pixmap(doc, xref)
            if pix.n > 4:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            pix.save("/tmp/_heat_candidate.png")
            try:
                res, _ = ocr("/tmp/_heat_candidate.png")
                text_len = len("".join(t for _, t, _ in (res or [])).strip())
            except Exception:
                text_len = -1
            if text_len == 0 and area > best_area(best):
                best = ({"page": pi, "xref": xref, "w": w, "h": h}, pix)
    return best


best_area_cache = {}


def best_area(best):
    if best is None:
        return 0
    return best[0]["w"] * best[0]["h"]


def process_pdf(path, ocr):
    doc = fitz.open(path)
    result = {"file": os.path.basename(path), "date": parse_date_from_name(path),
              "competition": guess_comp(path), "opponent": guess_opponent(path),
              "players": [], "summary": {}, "pages": len(doc)}
    for pi in range(len(doc)):
        page = doc[pi]
        pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
        pix.save("/tmp/_page.png")
        res, _ = ocr("/tmp/_page.png")
        op = OcrPage(res)
        if op.has("Athlete") and op.has("Breakdown") and not op.has("Period"):
            players = parse_breakdown_page(op)
            result["players"].extend(players)
        if op.has("Period") and op.has("Breakdown"):
            result["summary"].update(extract_summary(op))
        if op.has("TOTAL TIME") or (op.has("Time") and op.has("Team")):
            tokens = op.tokens
            for i, t in enumerate(tokens):
                if norm("TOTAL TIME") in norm(t["text"]):
                    nxt = next((n for n in tokens
                                if abs(n["y"] - t["y"]) <= 40 and n["cx"] > t["cx"]
                                and (n["time"] or n["num"])), None)
                    if nxt:
                        result["summary"]["total_time"] = nxt["text"]
                if norm("VENUE") in norm(t["text"]):
                    nxt = next((n for n in tokens
                                if abs(n["y"] - t["y"]) <= 40 and n["cx"] > t["cx"]),
                               None)
                    if nxt:
                        result["summary"]["venue"] = nxt["text"]
    # team shape (pitch diagram)
    hm = find_heat_map(doc)
    if hm:
        info, pix = hm
        slug = slugify(result["opponent"])
        fname = f"teamshape_{slug}.png"
        pix.save(os.path.join(HEAT_DIR, fname))
        result["team_shape"] = fname
    doc.close()
    return result


def run(paths, out_dir):
    os.makedirs(HEAT_DIR, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    ocr = get_ocr()
    out = os.path.join(out_dir, "performance.json")
    done = set()
    if os.path.exists(out):
        try:
            existing = json.load(open(out))
            done = {r["file"] for r in existing}
        except Exception:
            existing = []
    else:
        existing = []
    all_data = [r for r in existing if r.get("file") in done]
    for i, p in enumerate(paths, 1):
        name = os.path.basename(p)
        if name in done:
            print(f"[{i}/{len(paths)}] {name} (done)")
            continue
        print(f"[{i}/{len(paths)}] {name}")
        try:
            r = process_pdf(p, ocr)
            all_data.append(r)
            done.add(name)
            with open(out, "w") as f:
                json.dump(all_data, f, indent=2)
            print(f"   opp={r['opponent']} date={r['date']} players={len(r['players'])} "
                  f"shape={r.get('team_shape')} summary={r['summary']}")
        except Exception as e:
            print(f"   ERROR: {e}")
    with open(out, "w") as f:
        json.dump(all_data, f, indent=2)
    print(f"Saved {out} ({len(all_data)} reports)")


if __name__ == "__main__":
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        run(sys.argv[1:2], DATA_DIR)
    else:
        pdfs = []
        for f in sorted(os.listdir(DOWNLOADS)):
            if f.lower().endswith(".pdf") and ("catapult" in f.lower() or "barracks" in f.lower() or "lions" in f.lower() or "eagles" in f.lower() or "civil" in f.lower()):
                fp = os.path.join(DOWNLOADS, f)
                if os.path.getsize(fp) > 50000:
                    pdfs.append(fp)
        # drop exact duplicate names/sizes
        seen = set()
        uniq = []
        for fp in pdfs:
            key = os.path.getsize(fp)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(fp)
        run(uniq, DATA_DIR)