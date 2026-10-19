# Event-Variance Decomposition of Implied Correlation

**Macro co-jumps, earnings jumps and theta-weighted dispersion in the S&P 500, 1996–2025**

Kenneth Anthony Wijaya · MSc Risk Management & Financial Engineering, Imperial College Business School
Capstone project, *Data Structures and Algorithms* (October 2026) · [Full report (PDF)](report/report.pdf)

## Summary

S&P 500 implied correlation has historically exceeded the correlation subsequently realised, and dispersion trading (short index volatility, long constituent volatility) is the standard way to harvest the gap. This project tests whether part of that premium is scheduled-event variance rather than compensation for diffusive correlation risk. Earnings announcements are idiosyncratic jumps that inflate single-stock implied variance; FOMC and CPI releases are co-jumps that affect every stock at once. Each should move measured implied correlation mechanically, without any change in true co-movement.

Using OptionMetrics, CRSP and Compustat data for the point-in-time top fifty S&P 500 companies, the project decomposes 30-day implied variance into diffusive and event components, builds an ex-event implied correlation, and backtests theta-weighted, delta-hedged straddle dispersion at executable bid–ask prices. Hypotheses, the sample split and all strategy variants were pre-registered in [`docs/research_log.md`](docs/research_log.md).

## Key findings

- **Measurement.** The implied correlation constructed here tracks Cboe COR1M with a correlation of 0.984 in levels and 0.934 in daily changes.
- **Earnings variance drives the calendar pattern.** Raw implied correlation falls by 6 points in 1996–2012 and 11 points in 2013–2025 when the whole basket reports within the option's life (*t* = −6.5 and −8.4). The ex-event measure removes the effect out of sample.
- **Macro releases are genuine co-jumps.** An FOMC decision resolves 4–6% of the index's 30-day implied variance and 2–3% of each constituent's, so implied correlation does not move across macro windows. This half of the original hypothesis is rejected.
- **The recent premium is an event premium.** In 2013–2025 the correlation risk premium is +0.025 raw (*t* = 2.9) but +0.007 ex-event (*t* = 0.8).
- **The tradeable edge does not survive out of sample.** Annualised Sharpe ratios at half-spread costs:

| Variant | 1996–2012 (design) | 2013–2025 (test) | Deflated Sharpe (test) |
|:---|---:|---:|---:|
| V1 Vanilla monthly dispersion | 1.17 | 0.10 | 0.51 |
| V2 Event-timed dispersion | 1.10 | 0.28 | 0.76 |
| V3 Signal-filtered dispersion | 1.29 | 0.29 | 0.69 |

Event-timing ranks ahead of vanilla dispersion out of sample, as the decomposition implies, but no variant is significant after correction for multiple testing.

## Repository structure

```
├── notebook.ipynb            Full pipeline: acquisition → cleaning → features → event decomposition
│                             → strategy → backtest → efficiency and risk diagnostics
├── wrds_extract.py           Scripted, resumable WRDS extraction (OptionMetrics, CRSP, Compustat)
├── wrds_discovery.py         Checks which WRDS tables and date ranges a subscription covers
├── report/
│   ├── report.pdf            Written report (methodology, results, pitfalls, reflection)
│   ├── report.md             Markdown source of the report
│   └── figures/              Figures used in the report
├── docs/
│   └── research_log.md       Pre-registration, amendments and outcome
├── data/
│   ├── raw/fed/              FOMC meeting dates parsed from the Federal Reserve website
│   ├── raw/fred/             CPI and payroll release dates; three-month T-bill rate (FRED)
│   └── processed/            Derived results: daily implied/realised correlation measures,
│                             macro event calendar, monthly backtest P&L
└── requirements.txt          Python environment (Python 3.13)
```

## Reproducing the results

```bash
pip install -r requirements.txt
```

1. **WRDS data.** Run `python wrds_extract.py` with an institutional WRDS account. It prompts for the username; the password is kept in the user's own `pgpass` file and is never written to the project. The script writes to `data/raw/wrds/` and resumes if interrupted.
2. **FRED key.** Set the environment variable `FRED_API_KEY` (a free key from the St. Louis Fed) if `data/raw/fred/` needs to be rebuilt.
3. **Notebook.** Run `notebook.ipynb` from the repository root, top to bottom. Every download step caches to `data/raw/` and skips work already done. Sections 2–7 run in under a minute once the data are present.

## Data and licensing

OptionMetrics, CRSP and Compustat data are licensed through Wharton Research Data Services for non-commercial academic use and cannot be redistributed. This repository therefore contains no raw or vendor-derived price, volatility or quote data: only public calendars, derived correlation statistics and strategy results. Cboe index files, Yahoo Finance prices and SEC filings are downloaded by the notebook on demand rather than stored here.

## Main references

- Bennett, C. (2014) *Trading Volatility: Trading Volatility, Correlation, Term Structure and Skew*.
- Driessen, J., Maenhout, P.J. and Vilkov, G. (2009) 'The price of correlation risk: evidence from equity options', *Journal of Finance*, 64(3).
- Dubinsky, A., Johannes, M., Kaeck, A. and Seeger, N.J. (2019) 'Option pricing of earnings announcement risks', *Review of Financial Studies*, 32(2).
- Bailey, D.H. and López de Prado, M. (2014) 'The deflated Sharpe ratio', *Journal of Portfolio Management*, 40(5).
