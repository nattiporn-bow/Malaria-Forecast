"""Download monthly province-level malaria cases for one or more calendar
years from the DDC malaria MIS ("ภาพรวม รายจังหวัด" tab), one month per
request, and combine each year into one CSV.

Usage:
  python download_malaria_monthly_2568.py            # 2025 (2568)
  python download_malaria_monthly_2568.py 2021 2025  # 2021-2025, inclusive

Years whose CSV already exists are not downloaded again. For a range, the
per-year files are also stacked into malaria_province_monthly_<BE1>_<BE2>.csv.

Output per year (BE = CE + 543):
  malaria_province_monthly_<BE>.csv   one row per province per month
  malaria_<BE>_monthly_total.csv      the site's "total" row for each month
  malaria_<BE>_raw/<BE>_MM.html       raw HTML per month, for audit
"""
import calendar
import csv
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://malaria.ddc.moph.go.th/malariaR10"
REFERER = "https://malaria.ddc.moph.go.th/malariar10/malaria_summary.php"
OUT_DIR = Path(__file__).resolve().parent

MONTH_TH = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
            "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
GROUPS = ["TH", "M1", "M2", "All"]
SPECIES = ["PF", "PV", "PM", "PO", "PK", "Mix", "Unknow", "All"]
VALUE_COLS = [f"{g}_{s}" for g in GROUPS for s in SPECIES]


def fetch(url, retries=3):
    req = urllib.request.Request(url, headers={"Referer": REFERER, "User-Agent": "Mozilla/5.0"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read().decode("utf-8-sig")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                # Rate limited: stop at once, retrying only extends the block.
                raise SystemExit(f"HTTP 429 Too Many Requests; Retry-After = "
                                 f"{e.headers.get('Retry-After')} s. Try again later.")
            if attempt == retries:
                raise
            print(f"  retry {attempt} after error: {e}")
            time.sleep(5 * attempt)
        except Exception as e:
            if attempt == retries:
                raise
            print(f"  retry {attempt} after error: {e}")
            time.sleep(5 * attempt)


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def province_ids():
    html = fetch(f"{BASE}/inc/php/getProvinceUtil.php?graph_use=graph1&lang=th&data=PROVINCE_ID&val=")
    return {name.strip(): int(v)
            for v, name in re.findall(r"<option value=(\d+)>([^<]+)</option>", html) if v != "0"}


def overview_url(start, end):
    return (f"{BASE}/report/getHTML_overview.php?aa=aa&search_by_id=&search_by=province"
            f"&startdate={start}&enddate={end}"
            "&healthfarcility_type1=true&healthfarcility_type2=true&healthfarcility_type3=true")


def parse_table(html):
    """Return {province_name: [32 ints]}; 'total' included."""
    p = TableParser()
    p.feed(html)
    header = p.rows[1] if len(p.rows) > 1 else []
    if header != SPECIES * len(GROUPS):
        raise ValueError(f"unexpected header: {header}")
    out = {}
    for r in p.rows[2:]:
        vals = [v for v in r[1:] if v != ""]  # drop blank spacer cells
        if len(vals) != len(VALUE_COLS):
            raise ValueError(f"row {r[0]!r} has {len(vals)} values")
        out[r[0]] = [int(v.replace(",", "")) for v in vals]
    return out


def download_year(YEAR_CE, pid):
    YEAR_BE = YEAR_CE + 543
    RAW_DIR = OUT_DIR / f"malaria_{YEAR_BE}_raw"
    OUT_CSV = OUT_DIR / f"malaria_province_monthly_{YEAR_BE}.csv"
    TOTAL_CSV = OUT_DIR / f"malaria_{YEAR_BE}_monthly_total.csv"
    if OUT_CSV.exists():
        print(f"{OUT_CSV.name} exists, skipping {YEAR_BE}")
        return
    RAW_DIR.mkdir(exist_ok=True)

    rows, totals = [], []
    for m in range(1, 13):
        last = calendar.monthrange(YEAR_CE, m)[1]
        start, end = f"{YEAR_CE}{m:02d}01", f"{YEAR_CE}{m:02d}{last}"
        print(f"{YEAR_BE}-{m:02d} ({start}-{end})")
        html = fetch(overview_url(start, end))
        (RAW_DIR / f"{YEAR_BE}_{m:02d}.html").write_text(html, encoding="utf-8")
        table = parse_table(html)
        total = table.pop("total")

        missing = set(pid) - set(table)
        unknown = set(table) - set(pid)
        if missing or unknown:
            raise ValueError(f"month {m}: missing {missing}, unknown {unknown}")
        col_sums = [sum(v[i] for v in table.values()) for i in range(len(VALUE_COLS))]
        if col_sums != total:
            raise ValueError(f"month {m}: province sums != total row")

        meta = {"year_be": YEAR_BE, "year_ce": YEAR_CE, "month": m,
                "month_th": MONTH_TH[m - 1], "period": f"{YEAR_CE}-{m:02d}"}
        for name, vals in table.items():
            rows.append({**meta, "province_id": pid[name], "province": name,
                         **dict(zip(VALUE_COLS, vals))})
        totals.append({**meta, **dict(zip(VALUE_COLS, total))})
        print(f"  {len(table)} provinces, All_All = {total[-1]}")
        time.sleep(2)

    # Cross-check: 12 monthly totals must equal one full-year query.
    year_total = parse_table(fetch(overview_url(f"{YEAR_CE}0101", f"{YEAR_CE}1231")))["total"]
    month_sum = [sum(t[c] for t in totals) for c in VALUE_COLS]
    print(f"year query All_All = {year_total[-1]}, sum of months = {month_sum[-1]}")
    if month_sum != year_total:
        print("WARNING: sum of monthly totals differs from full-year query")

    meta_cols = ["year_be", "year_ce", "month", "month_th", "period"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=meta_cols + ["province_id", "province"] + VALUE_COLS)
        w.writeheader()
        w.writerows(rows)
    with open(TOTAL_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=meta_cols + VALUE_COLS)
        w.writeheader()
        w.writerows(totals)
    print(f"wrote {len(rows)} rows -> {OUT_CSV.name}")


def year_csv(year_ce):
    return OUT_DIR / f"malaria_province_monthly_{year_ce + 543}.csv"


def combine_years(first, last):
    """Stack the per-year files into malaria_province_monthly_<BE1>_<BE2>.csv."""
    out = OUT_DIR / f"malaria_province_monthly_{first + 543}_{last + 543}.csv"
    header, rows = None, []
    for year_ce in range(first, last + 1):
        with open(year_csv(year_ce), newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            h = next(reader)
            if header is not None and h != header:
                raise ValueError(f"{year_csv(year_ce).name}: header differs from earlier years")
            header = h
            rows.extend(reader)
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {out.name}")


def main():
    args = [int(a) for a in sys.argv[1:]]
    first, last = (args + [2025, 2025])[:2] if len(args) != 1 else (args[0], args[0])
    todo = [y for y in range(first, last + 1) if not year_csv(y).exists()]
    if todo:
        # Only ask the site for the province list when something is missing.
        pid = province_ids()
        print(f"province ids: {len(pid)}")
        for year_ce in todo:
            download_year(year_ce, pid)
    if last > first:
        combine_years(first, last)


if __name__ == "__main__":
    main()
