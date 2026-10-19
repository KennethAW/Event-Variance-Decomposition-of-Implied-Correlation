# Research Log — Event-Variance Decomposition of Implied Correlation

Purpose: pre-register hypotheses before seeing results, and log every strategy variant tried.
This log is the evidence for the "Overfitting / data-snooping" answer and the trial count used in the Deflated Sharpe Ratio.
(Not a separate submission item — summarise it in the report.)

## Pre-registration (written 19 Oct 2026, before any results)

**Sample design**
- Sample: 2019-01-01 to 2026-10-16 (DoltHub options history starts Feb 2019).
- Design / in-sample: 2019–2022. Held-out test: 2023-01-01 onward. No parameter is changed after viewing held-out results.
- Universe: point-in-time top-50 S&P 500 names by market cap, rebalanced quarterly. Index leg: SPY options.

**Hypotheses**
- H1 (measurement): 30-day implied correlation rises when the option tenor spans scheduled macro releases (FOMC/CPI) and falls when it spans constituent earnings. Removing the extracted event variance removes most of this calendar pattern.
- H2 (pricing): The correlation risk premium (implied minus subsequently realised correlation) differs between the raw and ex-event measures. Which leg carries the premium — macro-event index variance vs earnings-jump single-stock variance — is the empirical question.
- H3 (trading): Event-timed theta-weighted dispersion (short index vol across macro events, long single-stock vol across earnings) beats vanilla monthly dispersion out of sample, after bid/ask costs.

**What would falsify the idea**
- No difference between raw and ex-event implied correlation around event windows (H1 fails).
- Event-timed and vanilla dispersion P&L statistically indistinguishable out of sample, or the edge disappears at realistic bid/ask costs (H3 fails).

## Variant log

| # | Date | Change | Period evaluated | Kept? | Reason |
|---|------|--------|------------------|-------|--------|
| 1 | 19 Oct 2026 | V1 Vanilla monthly theta-weighted dispersion (baseline) | design, then test once | Reported | Baseline. Half-spread Sharpe 1.17 design / 0.10 test; DSR test 0.51 |
| 2 | 19 Oct 2026 | V2 Event-timed: long straddles only on names with earnings inside the holding period, theta-matched to the short SPX straddle; no trade if no name reports | design, then test once | Reported | Sharpe 1.10 design / 0.28 test; best test break-even (1.31x half-spread); DSR test 0.76, not significant |
| 3 | 19 Oct 2026 | V3 Signal-filtered: V1 only when the point-in-time ex-event implied correlation is above its trailing 252-day median (threshold fixed, not tuned) | design, then test once | Reported | Sharpe 1.29 design / 0.29 test; DSR test 0.69, not significant |

## Amendment 1 (19 Oct 2026, before any results were computed)

WRDS access was granted (OptionMetrics, CRSP, Compustat). The primary data source switches from free DoltHub/Yahoo data to OptionMetrics + CRSP; the free-data pipeline is kept as an independent cross-check for 2019-2025.

- Sample: 1996-01-02 to 2025-08-29 (full OptionMetrics coverage at Imperial). Index leg: SPX options (secid 108105) instead of SPY.
- Design / in-sample: 1996-2012. Held-out test: 2013-01-01 to 2025-08-29. (Reason: longer history, includes 2008/2010/2011/2020 stress periods; the in-sample period overlaps Driessen, Maenhout & Vilkov (2009) so their correlation-risk-premium magnitudes can be used as a replication check.)
- Universe: point-in-time top-50 S&P 500 companies by market cap (CRSP membership, OptionMetrics prices x shares), one line per company (share classes merged via CRSP permco), rebalanced quarterly.
- Earnings dates: Compustat rdq (CCM-linked). Macro dates: FRED release calendar.
- Hypotheses H1-H3 and falsification criteria are unchanged.

## Amendment 2 (19 Oct 2026, measurement choices made before any strategy backtest)

- FOMC dates come from the Federal Reserve website (meeting calendars 1996-2025), not FRED: FRED release 101 ("FOMC Press Release") updates almost daily and is not a meeting calendar. Scheduled decision day = last day of each scheduled meeting; validated at 8 per year (7 in 2020, when the March meeting was cancelled). Unscheduled moves and conference calls are kept separately and are not used as ex-ante events.
- CPI: when FRED lists two CPI dates in one month (February seasonal-factor release), the later one (the CPI release itself) is kept; validated at 12 per year.
- Index event variance, first attempt: a pooled term-structure regression on the standardized 10/30/60/91-day SPX vols. It gave zero/negative estimates (event counts are almost proportional to maturity and the diffusive term structure is not flat), so it was replaced by the "vol-crush" regression (drop in 30-day implied variance on event days relative to ordinary days, expanding window, point-in-time). This is logged as a methodology trial; it was decided on measurement grounds (estimates outside the admissible range), before any strategy result.
- Macro releases are treated as co-jumps: the same crush regression pooled over single stocks gives the share of each stock's 30-day variance resolved by FOMC/CPI/NFP, removed from the stock leg as well as the index leg.
- Strategy variants V1-V3 (variant log above), execution rules and cost scenarios (mid, 50% and 100% of the quoted half-spread; 1 bp stock / 0.5 bp index hedge cost) were fixed before running the backtest. The design period (1996-2012) is evaluated first; the test period (2013-2025) is evaluated once with no changes.

## Outcome (19 Oct 2026, after the single test-period run)

- No parameter or rule was changed after the test period was evaluated. All three variants are reported; none was dropped.
- H1: earnings half supported (raw implied correlation falls with the weight reporting inside the window; the ex-event measure removes it out of sample). Macro half rejected (no FOMC/CPI effect on raw implied correlation; macro releases scale both legs).
- H2: test-period correlation premium +0.025 raw (t 2.9) vs +0.007 ex-event (t 0.8) - the recent premium is event variance.
- H3: event-timed beats vanilla out of sample, but not significantly (DSR < 0.95) and not robust to full-spread costs -> not supported under the pre-registered criterion.
