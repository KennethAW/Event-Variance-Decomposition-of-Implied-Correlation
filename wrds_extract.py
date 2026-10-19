"""WRDS extraction for the capstone (OptionMetrics + CRSP + Compustat). Resumable: every step/year is cached.

Run from the project folder (VS Code terminal):
    C:\\Users\\kencl\\venvs\\capstone\\Scripts\\python.exe wrds_extract.py

Outputs (data/raw/wrds/):
  sp500_members.parquet   CRSP point-in-time S&P 500 membership (permno, start, ending)
  link_optionm_crsp.parquet  OptionMetrics secid <-> CRSP permno link (WRDS linking suite)
  permco.parquet          permno -> permco (company id, used to merge share classes like GOOG/GOOGL)
  trading_days.parquet    trading days (from SPX in OptionMetrics)
  basket.parquet          quarterly top-50 by market cap (one line per company), weights
  secprd/YYYY.parquet     daily prices, returns, shares for basket names + SPX
  stdopd/YYYY.parquet     standardized ATM options (10/30/60/91-day) for basket names + SPX
  entry_dates.parquet     monthly entry dates (first trading day after each 3rd-Friday expiry)
  opprcd/YYYY.parquet     option chains on entry dates (expiry <= 70 days, 0.2 <= |delta| <= 0.8)
  earnings_rdq.parquet    Compustat quarterly earnings report dates linked to CRSP permno
"""
import os, json, time
from pathlib import Path
import numpy as np
import pandas as pd
import wrds

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "raw" / "wrds"
for sub in ("", "secprd", "stdopd", "opprcd"):
    (OUT / sub).mkdir(parents=True, exist_ok=True)

START, END = "1996-01-01", "2025-08-29"      # OptionMetrics coverage at Imperial
CRSP_LAST = pd.Timestamp("2024-12-31")       # CRSP S&P list ends here; members still in at that date are carried to END
N_BASKET = 50
CHAIN_MAX_DTE, DELTA_LO, DELTA_HI = 70, 0.20, 0.80
STD_DAYS = (10, 30, 60, 91)
SPX = 108105
YEARS = range(pd.Timestamp(START).year, pd.Timestamp(END).year + 1)

db = wrds.Connection(wrds_username=os.environ.get("WRDS_USERNAME") or input("WRDS username: ").strip())
q = db.raw_sql
t0 = time.time()

def log(msg):
    print(f"[{(time.time() - t0) / 60:5.1f} min] {msg}", flush=True)

def path(name):
    return OUT / f"{name}.parquet"

def cached_or(name, fn):
    p = path(name)
    if p.exists():
        return pd.read_parquet(p)
    df = fn()
    df.to_parquet(p, index=False)
    log(f"saved {name}: {len(df):,} rows")
    return df

def ints(xs):
    return ", ".join(str(int(x)) for x in sorted(set(xs)))

def dates(xs):
    return ", ".join(f"'{pd.Timestamp(x):%Y-%m-%d}'" for x in sorted(set(xs)))

# ------------------------------------------------------------------ 1. membership, links, company ids
members = cached_or("sp500_members", lambda: q(
    f"select permno, start, ending from crsp.msp500list where ending >= '{START}'", date_cols=["start", "ending"]))
members["ending"] = pd.to_datetime(members["ending"])
members.loc[members["ending"] >= CRSP_LAST, "ending"] = pd.Timestamp(END)        # still a member at CRSP's last update

link = cached_or("link_optionm_crsp", lambda: q(
    "select secid, permno, sdate, edate, score from wrdsapps_link_crsp_optionm.opcrsphist",
    date_cols=["sdate", "edate"]))
link["edate"] = pd.to_datetime(link["edate"]).fillna(pd.Timestamp(END))
link.loc[link["edate"] >= CRSP_LAST, "edate"] = pd.Timestamp(END)

permco = cached_or("permco", lambda: q(
    f"select distinct permno, permco from crsp.stocknames where permno in ({ints(members['permno'])})"))
permco_of = permco.drop_duplicates("permno").set_index("permno")["permco"]

# ------------------------------------------------------------------ 2. trading days and quarterly rebalance dates
def _days():
    return pd.concat([q(f"select date from optionm.secprd{y} where secid = {SPX}", date_cols=["date"]) for y in YEARS])
tdays = pd.DatetimeIndex(sorted(cached_or("trading_days", _days)["date"]))
tdays = tdays[(tdays >= START) & (tdays <= END)]
rebal = [tdays[tdays.searchsorted(d)] for d in pd.date_range(START, END, freq="QS") if d <= tdays[-1]]
prev_of = {d: tdays[tdays.searchsorted(d) - 1] if tdays.searchsorted(d) > 0 else d for d in rebal}

# ------------------------------------------------------------------ 3. point-in-time top-50 basket (one line per company)
LINK_BY_PERMNO = {p: g.sort_values("score") for p, g in link.groupby("permno")}   # hash map: O(1) lookup per permno

def secid_on(permno, d):
    g = LINK_BY_PERMNO.get(permno)
    if g is None:
        return None
    g = g[(g["sdate"] <= d) & (g["edate"] >= d)]
    return None if g.empty else int(g.iloc[0]["secid"])

def _basket():
    """Market cap = |CRSP price| x CRSP shares outstanding (class-specific, the academic standard).
    OptionMetrics' own share counts were checked and rejected: e.g. AT&T 1996 shows ~3x too many shares and
    each Alphabet class reports the whole company's shares. For 2025 (after CRSP's last date) the cap is the
    OptionMetrics close x the CRSP share count at 2024-12-31."""
    rows = []
    for y in YEARS:
        ds = [d for d in rebal if d.year == y]
        if not ds:
            continue
        mem = {d: members[(members["start"] <= d) & (members["ending"] >= d)]["permno"].tolist() for d in ds}
        allp = sorted({p for d in ds for p in mem[d]})
        prevs = sorted({prev_of[d] for d in ds})
        cap = {}
        early = [p for p in prevs if p <= CRSP_LAST]
        if early:
            c = q(f"select permno, date, prc, shrout from crsp.dsf where date in ({dates(early)}) "
                  f"and permno in ({ints(allp)})", date_cols=["date"])
            c = c.dropna(subset=["prc", "shrout"])                # CRSP returns nullable (pd.NA) values for missing prices
            cap.update({(r.date, int(r.permno)): abs(float(r.prc)) * float(r.shrout) * 1000 for r in c.itertuples()})
        late = [p for p in prevs if p > CRSP_LAST]
        if late:
            shr = q(f"select permno, shrout from crsp.dsf where date = (select max(date) from crsp.dsf) "
                    f"and permno in ({ints(allp)})").dropna().set_index("permno")["shrout"].astype(float)
            sid_of = {p: secid_on(p, late[0]) for p in allp}
            px = pd.concat([q(f"select secid, date, close from optionm.secprd{py} where date in "
                              f"({dates(p for p in late if p.year == py)}) and secid in ({ints(s for s in sid_of.values() if s)})",
                              date_cols=["date"]) for py in sorted({p.year for p in late})], ignore_index=True)
            px = px.dropna().set_index(["date", "secid"])["close"].astype(float)
            for p, sid in sid_of.items():
                for dd in late:
                    if sid and p in shr.index and (dd, sid) in px.index:
                        cap[(dd, p)] = abs(px.loc[(dd, sid)]) * shr.loc[p] * 1000
        for d in ds:
            for p in mem[d]:
                s_ = secid_on(p, d)
                if s_ and (prev_of[d], p) in cap:
                    rows.append({"rebal_date": d, "permno": p, "permco": permco_of.get(p, p), "secid": s_,
                                 "mcap": float(cap[(prev_of[d], p)])})
        log(f"basket {y}: {len(ds)} rebalances")
    caps = pd.DataFrame(rows).dropna()
    # merge share classes of one company (e.g. GOOG + GOOGL): company cap = sum of class caps; keep the larger class
    comp = caps.groupby(["rebal_date", "permco"]).agg(mcap=("mcap", "sum")).reset_index()
    rep = caps.sort_values("mcap", ascending=False).drop_duplicates(["rebal_date", "permco"])[["rebal_date", "permco", "permno", "secid"]]
    comp = comp.merge(rep, on=["rebal_date", "permco"])
    top = comp.sort_values(["rebal_date", "mcap"], ascending=[True, False]).groupby("rebal_date").head(N_BASKET).copy()
    top["weight"] = top["mcap"] / top.groupby("rebal_date")["mcap"].transform("sum")
    return top
basket = cached_or("basket_v2", _basket)       # v1 (OptionMetrics shares) rejected - see docstring
basket["rebal_date"] = pd.to_datetime(basket["rebal_date"])
log(f"basket: {basket['rebal_date'].nunique()} rebalances, {basket['secid'].nunique()} unique names")
for d in [basket["rebal_date"].min(), basket["rebal_date"][basket["rebal_date"] >= "2008-10-01"].min(), basket["rebal_date"].max()]:
    x = basket[basket["rebal_date"] == d].nlargest(5, "mcap")
    log(f"  top-5 {d.date()}: " + ", ".join(f"permno {p} {c / 1e9:,.0f}bn" for p, c in zip(x["permno"], x["mcap"])))

def secids_in_year(y):
    b = basket[(basket["rebal_date"].dt.year == y) | (basket["rebal_date"] == basket.loc[basket["rebal_date"].dt.year < y, "rebal_date"].max())]
    return sorted(set(b["secid"].astype(int)) | {SPX})


def topup(ds_name, y, build_sql, extra=""):
    """Per-year cache that tops up only the secids not fetched before (so a corrected basket costs little)."""
    p, side = OUT / ds_name / f"{y}.parquet", OUT / ds_name / "_fetched.json"
    fetched = json.loads(side.read_text()) if side.exists() else {}
    have = set(fetched.get(str(y), []))
    if p.exists() and not have:
        have = set(pd.read_parquet(p, columns=["secid"])["secid"].astype(int))
    miss = sorted(set(secids_in_year(y)) - have)
    if miss:
        df = q(build_sql(miss), date_cols=["date"] + (["exdate"] if ds_name == "opprcd" else []))
        out = pd.concat([pd.read_parquet(p), df], ignore_index=True) if p.exists() else df
        out.to_parquet(p, index=False)
        log(f"{ds_name} {y}: +{len(df):,} rows for {len(miss)} secids {extra}")
    fetched[str(y)] = sorted(have | set(miss))
    side.write_text(json.dumps(fetched))

# ------------------------------------------------------------------ 4. daily prices (basket names + SPX)
for y in YEARS:
    topup("secprd", y, lambda ids, y=y: f"select secid, date, open, high, low, close, return, cfadj, shrout, volume "
                                        f"from optionm.secprd{y} where secid in ({ints(ids)})")

# ------------------------------------------------------------------ 5. standardized ATM options (constant maturity)
for y in YEARS:
    topup("stdopd", y, lambda ids, y=y: f"select secid, date, days, forward_price, strike_price, premium, impl_volatility, "
                                        f"delta, vega, cp_flag from optionm.stdopd{y} where secid in ({ints(ids)}) "
                                        f"and days in ({ints(STD_DAYS)})")

# ------------------------------------------------------------------ 6. monthly entry dates + option chains on those dates
def third_friday(y, m):
    d = pd.Timestamp(year=y, month=m, day=15)
    return d + pd.Timedelta(days=(4 - d.weekday()) % 7)

def _entries():
    out = []
    for m in pd.date_range(START, END, freq="MS"):
        i = tdays.searchsorted(third_friday(m.year, m.month) + pd.Timedelta(days=1))
        if i < len(tdays):
            out.append(tdays[i])
    return pd.DataFrame({"entry_date": sorted(set(out))})
entries = pd.to_datetime(cached_or("entry_dates", _entries)["entry_date"])

for y in YEARS:
    ed = [d for d in entries if d.year == y]
    if ed:
        topup("opprcd", y, lambda ids, y=y, ed=ed: (
            f"select secid, date, exdate, cp_flag, strike_price, best_bid, best_offer, impl_volatility, delta, gamma, vega, "
            f"theta, volume, open_interest, forward_price, am_settlement, expiry_indicator, cfadj, optionid "
            f"from optionm.opprcd{y} where date in ({dates(ed)}) and secid in ({ints(ids)}) "
            f"and exdate > date and exdate <= date + {CHAIN_MAX_DTE} and abs(delta) between {DELTA_LO} and {DELTA_HI}"),
            extra=f"on {len(ed)} entry dates")

# ------------------------------------------------------------------ 7. earnings report dates (Compustat, CCM-linked)
cached_or("earnings_rdq_v2", lambda: q(
    "select distinct b.lpermno as permno, a.gvkey, a.datadate, a.rdq "
    "from comp.fundq a join crsp.ccmxpf_linktable b on a.gvkey = b.gvkey "
    "where a.indfmt = 'INDL' and a.datafmt = 'STD' and a.popsrc = 'D' and a.consol = 'C' "
    f"and a.rdq between '{START}' and '{END}' and b.linktype in ('LU', 'LC') and b.linkprim in ('P', 'C') "
    "and a.rdq >= b.linkdt and (a.rdq <= b.linkenddt or b.linkenddt is null) "
    f"and b.lpermno in ({ints(basket['permno'])})", date_cols=["datadate", "rdq"]))

# ------------------------------------------------------------------ summary
summary = {
    "sample": [START, END],
    "rebalances": int(basket["rebal_date"].nunique()),
    "unique_basket_names": int(basket["secid"].nunique()),
    "entry_dates": int(len(entries)),
    "files": {str(p.relative_to(ROOT)): p.stat().st_size for p in sorted(OUT.rglob("*.parquet"))},
    "minutes": round((time.time() - t0) / 60, 1),
}
(OUT / "extract_summary.json").write_text(json.dumps(summary, indent=1))
log(f"done - {summary['rebalances']} rebalances, {summary['unique_basket_names']} names, {summary['entry_dates']} entry dates; "
    f"{sum(summary['files'].values()) / 1e6:.0f} MB")
db.close()
