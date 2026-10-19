"""WRDS discovery: what does Imperial's subscription contain, and how recent is it?

Run from the project folder (VS Code terminal):
    C:\\Users\\kencl\\venvs\\capstone\\Scripts\\python.exe wrds_discovery.py

You will be asked for your WRDS username and password (and may get a Duo push).
Answer 'y' when asked to create a .pgpass file: the password is then stored in your Windows user profile
(%APPDATA%\\postgresql\\pgpass.conf), NOT in this project, so later scripts can connect without asking again.
Results are printed and saved to data/raw/wrds/discovery.txt.
"""
import os, sys, io, traceback
from pathlib import Path

import pandas as pd
import wrds

OUT = Path(__file__).resolve().parent / "data" / "raw" / "wrds"
OUT.mkdir(parents=True, exist_ok=True)
log = io.StringIO()

def say(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    log.write(s + "\n")

def safe(label, fn):
    try:
        res = fn()
        say(f"{label}:\n{res}\n" if isinstance(res, pd.DataFrame) else f"{label}: {res}")
    except Exception as e:
        say(f"{label}: FAILED ({type(e).__name__}: {str(e).splitlines()[0][:200]})")

user = os.environ.get("WRDS_USERNAME") or input("WRDS username: ").strip()
db = wrds.Connection(wrds_username=user)
q = db.raw_sql

libs = db.list_libraries()
say("Option libraries:", [l for l in libs if l.startswith("optionm")])
say("crsp:", "crsp" in libs, "| comp:", "comp" in libs, "| ravenpack:", [l for l in libs if "raven" in l][:5])
say("Link / wrdsapps libraries:", [l for l in libs if "link" in l or l.startswith("wrdsapps")][:20])

om = db.list_tables("optionm") if "optionm" in libs else []
say("\noptionm non-yearly tables:", sorted(t for t in om if not t[-4:].isdigit()))
for t in ["opprcd", "stdopd", "vsurfd", "secprd", "fwdprd"]:
    yrs = sorted(int(x[-4:]) for x in om if x.startswith(t) and x[-4:].isdigit())
    say(f"{t}: {yrs[0] if yrs else None} -> {yrs[-1] if yrs else None}")

last_std = max((int(x[-4:]) for x in om if x.startswith("stdopd") and x[-4:].isdigit()), default=None)
last_opp = max((int(x[-4:]) for x in om if x.startswith("opprcd") and x[-4:].isdigit()), default=None)
safe("SPX secid lookup", lambda: q("select secid, ticker, issuer, effect_date from optionm.secnmd "
                                   "where ticker in ('SPX','AAPL','MSFT') order by ticker, effect_date desc"))
if last_std:
    safe(f"stdopd{last_std} date range for SPX (secid 108105)",
         lambda: q(f"select min(date) as first, max(date) as last, count(*) as n from optionm.stdopd{last_std} where secid = 108105"))
    safe("stdopd tenors available (days)", lambda: q(f"select distinct days from optionm.stdopd{last_std} where secid = 108105 order by days").T)
    safe("stdopd sample row", lambda: q(f"select * from optionm.stdopd{last_std} where secid = 108105 order by date desc limit 3"))
if last_opp:
    safe(f"opprcd{last_opp} date range for SPX",
         lambda: q(f"select min(date) as first, max(date) as last from optionm.opprcd{last_opp} where secid = 108105"))
    safe("opprcd columns", lambda: list(q(f"select * from optionm.opprcd{last_opp} where secid = 108105 limit 1").columns))

for lib, tbl, sql in [
    ("crsp", "dsf", "select min(date) as first, max(date) as last from crsp.dsf"),
    ("crsp", "msp500list", "select * from crsp.msp500list order by 3 desc limit 3"),
    ("crsp", "dsp500list_v2", "select * from crsp.dsp500list_v2 limit 3"),
    ("crsp", "dsedelist", "select max(dlstdt) as last_delist from crsp.dsedelist"),
    ("crsp", "ccmxpf_linktable", "select count(*) as n from crsp.ccmxpf_linktable"),
    ("comp", "fundq", "select max(rdq) as last_rdq, count(*) as n from comp.fundq where rdq >= '2019-01-01'"),
    ("wrdsapps", "opcrsphist", "select count(*) as n from wrdsapps.opcrsphist"),
    ("wrdsapps_link_crsp_optionm", "opcrsphist", "select count(*) as n from wrdsapps_link_crsp_optionm.opcrsphist"),
]:
    safe(f"{lib}.{tbl}", lambda sql=sql: q(sql))

(OUT / "discovery.txt").write_text(log.getvalue())
print(f"\nSaved to {OUT / 'discovery.txt'}")
db.close()
