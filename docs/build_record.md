# Build Record

## 2026-05-31 - Phase 12 Financial Reporting, Mock QRT Pack, Board Report, And Final Hardening

- Added financial reporting helpers in `src/miniinsure/reporting.py`.
- Implemented a management income statement with gross written premium, gross earned premium, net earned premium, paid claims, change in gross claims provision, gross claims incurred, ceded recoveries, reinsurance premium cost, net claims incurred, expenses, investment result, profit before tax, disabled tax, and profit after tax.
- Added combined ratio and return on capital KPIs.
- Added a Solvency II-style balance sheet view with reinsurance recoverables shown as assets, gross technical provisions shown as liabilities, excess assets over liabilities, and unrestricted Tier 1 own funds.
- Added Markdown board risk report generation with executive summary, valuation date/scenario, solvency ratio, SCR/MCR, own funds, technical provisions, reserve risk, risk commentary, traffic-light KRIs, limitations, validation status, timestamp, and assumption hash.
- Added the `src/miniinsure/qrt` mock reporting package.
- Added auditable QRT mapping definitions and applicability matrix.
- Added mock QRT-shaped generators for `S.01.01.02`, `S.01.02.01`, `S.02.01.02`, `S.05.01.02`, `S.06.02.01`, `S.06.03.01`, `S.08.01.01`, `S.17.01.02`, `S.23.01.01`, and `S.28.01.01`.
- Explicitly marked `S.12.01.02` and `S.28.02.01` as not applicable.
- Added DNB-style mock validation rules `DNB001` through `DNB008`, with errors blocking export and warnings allowing export.
- Added mock Excel and ZIP export helpers using deterministic names and scenario metadata.
- Confirmed there is no real XBRL export path.
- Added Financial Reporting, QRT Reporting Pack, and Board Risk Report Streamlit pages.
- Added tests for reporting formulas, QRT template generation and validation, board report content, end-to-end reporting sequence, export naming, no-XBRL output, hidden truth isolation, balance sheet reconciliations, and QRT validation blocking.

Production regulatory filing, real XBRL, authentication, background workers, and production filing persistence were not added.

## 2026-05-31 - Phase 11 One-Year Capital, Standard Formula, MCR, Own Funds, And Balance Sheet

- Added one-year economic capital engine in `src/miniinsure/risk_engine/one_year_engine.py`.
- Implemented the one-year own funds movement formula and one-year loss definition.
- Added economic capital as VaR 99.5% loss less expected loss and added TVaR 99.5%.
- Added aggregate premium risk simulation using expected premium loss cost and frequency/severity approximations.
- Retained opening reserve risk from the existing reserve risk engine.
- Added sampled expense ratio with floor at zero and the required operational loss proxy.
- Added market, operational, and credit-loss components to the one-year loss distribution.
- Added simplified Standard Formula calculations in `src/miniinsure/standard_formula.py`.
- Implemented non-life premium/reserve risk, catastrophe risk, market risk, counterparty default risk, operational risk, BSCR aggregation, and final SCR.
- Added market stress helpers in `src/miniinsure/risk_engine/stress_tests.py` and correlation aggregation in `src/miniinsure/risk_engine/aggregation.py`.
- Added MCR calculation in `src/miniinsure/mcr.py`.
- Added own funds and opening balance sheet helpers in `src/miniinsure/own_funds.py`.
- Added shared capital workflow orchestration in `src/miniinsure/risk_engine/capital_workflow.py`.
- Added Capital Model page with economic capital, loss distribution, risk contributions, Standard Formula SCR, MCR, solvency ratio, and stress summaries.
- Added Solvency II Balance Sheet page with assets, liabilities, technical provisions, own funds, eligible own funds, SCR, MCR, coverage ratios, and reconciliation status.
- Added tests for one-year capital, Standard Formula components, MCR corridor/floor, own funds, deterministic reproducibility, and small-mode runtime sanity.

Full regulatory Standard Formula, internal model validation, tax adjustments, future management actions, and official Solvency II filing outputs were not started in this phase.

## 2026-05-31 - Phase 10 Economic Assumptions, ALM, And Dependency Validation

- Added economic scenario assumptions in `src/miniinsure/simulation/economic_scenarios.py`.
- Implemented the required annual effective risk-free curve and linear interpolation.
- Added monthly discount factors for economic cash-flow timing.
- Implemented deterministic cash return, bond return, and truncated equity return formulas.
- Added ALM summaries in `src/miniinsure/alm.py`.
- Calibrated opening assets as liabilities plus `1.40 * SCR`.
- Implemented the required asset weights: cash 15%, short bonds 50%, long bonds 25%, and equities 10%.
- Added short bond duration 2.0, long bond duration 7.0, spread duration at 80% of interest duration, equity expected return 6.5%, and equity volatility 18%.
- Added asset allocation, liability cash-flow profile, liquidity gap, duration gap, and simple market stress outputs.
- Added risk-driver metadata and Gaussian copula dependency validation under `src/miniinsure/risk_engine`.
- Implemented the fixed dependency matrix for drivers `PF`, `PS`, `RD`, `CI`, `CAT`, `EQ`, `IR`, `SP`, `EX`, `LV`, and `RDf`.
- Added positive semidefinite validation with blocking errors when the minimum eigenvalue is below `-1e-8`.
- Added the ALM Streamlit page with asset allocation, liability cash-flow profile, liquidity gap, duration gap, market stresses, and dependency matrix validation status.
- Added tests for curve interpolation, return formulas, asset calibration, asset weights, ALM output fields, PSD validation, invalid matrix blocking, and Gaussian copula driver shape.

Full market risk capital, ALM optimization, economic scenario generator, and SCR aggregation were not started in this phase.

## 2026-05-31 - Phase 9 One-Year Reserve Risk Quick Mode

- Added quick-mode one-year reserve risk simulation in `src/miniinsure/reserving/reserve_risk.py`.
- Added stochastic reserving helpers in `src/miniinsure/reserving/stochastic_methods.py`.
- Implemented bootstrap chain ladder with fitted cumulative values, fitted incremental values, centered Pearson residuals by development period, residual resampling within development period, pseudo triangle reconstruction, chain-ladder refitting, overdispersed Poisson process variation, and tail-factor uncertainty.
- Applied tail-factor uncertainty with sigma `0.03` for motor vehicle liability and `0.01` for other motor.
- Added bodily injury reserve risk with negative binomial IBNR counts and lognormal severity emergence.
- Added large BI claim-level lognormal development around current case estimates.
- Added catastrophe event-level lognormal ultimate uncertainty.
- Calculated one-year reserve loss as next 12-month payments plus closing best estimate less opening best estimate.
- Re-estimated closing best estimate from simulated one-year observed development using the deterministic method-selection framework rather than copying simulated remaining unpaid.
- Added reserve risk statistics: mean, standard deviation, VaR 95%, VaR 99%, VaR 99.5%, TVaR 99.5%, probability of adverse development, expected reserve loss, and reserve capital.
- Updated the Technical Provisions page with quick-mode seed and simulation-count controls, rerun control, reserve risk summary, reserve loss distribution chart, reserve capital, and component summary.
- Added tests for deterministic reproducibility, required output statistics, reserve capital formula, adverse-development probability, closing reserve re-estimation, default 1,000 quick-mode simulations, and small-mode runtime sanity.

Full reserve-risk settings, stochastic technical provisions, SCR aggregation, and capital reporting were not started in this phase.

## 2026-05-30 - Phase 8 Technical Provisions And Risk Margin

- Added monthly cash-flow discounting helpers with annual effective risk-free curve interpolation.
- Added claims provision projection for already incurred obligations using selected deterministic reserves.
- Added allocated loss adjustment expense at 4% of unpaid loss and unallocated loss adjustment expense at 2% of unpaid loss.
- Added claim-type future payment patterns conditional on paid percentage at the valuation date.
- Added premium provision for future coverage inside existing annual contract boundaries, excluding future renewals.
- Added premium payment pattern treatment with 85% upfront and 15% monthly installments, with acquisition expenses treated as incurred at inception and administrative expenses retained on unearned exposure.
- Allowed negative premium provisions where future premium inflows exceed expected future outflows.
- Added discounted default-adjusted reinsurance recoverables integrated with the fixed reinsurance module.
- Added cost-of-capital risk margin using 6% cost of capital and the required 10-year runoff factors.
- Included reserve risk, premium provision risk, reinsurance counterparty risk, and operational risk in the non-hedgeable SCR base.
- Added gross and net technical provision views with valuation tolerance reconciliation.
- Updated the Technical Provisions page to show claims provision, premium provision, recoverables, risk margin, gross TP, net TP, and reconciliation status.
- Added tests for claims provision, discounting, claims handling expenses, negative premium provision, recoverables reconciliation, risk margin, TP arithmetic, and valuation tolerance.

No stochastic reserve risk, SCR capital model, discount curve scenario engine, or regulatory reporting module was started in this phase.

## 2026-05-30 - Phase 7 Annual Triangles And Deterministic Reserving

- Added annual paid, incurred, count, and average-cost triangle construction in `src/miniinsure/reserving/triangles.py`.
- Implemented development year as calendar year minus accident year plus one.
- Built triangles by Solvency II line of business and homogeneous risk group using observed valuation data only.
- Excluded zero insured amount claims from paid triangles while retaining them in count diagnostics.
- Added cumulative paid non-decreasing validation for grouped annual paid triangles.
- Added deterministic paid chain ladder, incurred chain ladder, Bornhuetter-Ferguson, and Cape Cod methods in `src/miniinsure/reserving/deterministic_methods.py`.
- Added explicit tail factors, expected loss ratios, method weights, maturity rules, negative IBNR floor, and sparse HRG fallback.
- Added the Technical Provisions Streamlit page with paid and incurred triangles, development factors, method selections, ultimate, IBNR, and selected reserve by LoB/HRG.
- Extended the observed valuation snapshot with observed LoB and HRG segmentation fields so reserving does not need hidden truth.
- Added tests for golden triangles, development year calculation, paid triangle validation, deterministic reserving formulas, method weights, tail factor application, negative IBNR floor, and sparse HRG fallback.

No stochastic reserve risk, technical provisions discounting, risk margin, capital model, or regulatory reporting module was started in this phase.

## 2026-05-30 - Phase 6 Default Reinsurance Program

- Added a separately testable fixed reinsurance program in `src/miniinsure/simulation/reinsurance_simulation.py`.
- Implemented quota share as disabled by default with selectable ceded percentage from 0% to 40%.
- Implemented per-risk XOL with EUR 250,000 retention, EUR 1,000,000 limit, 18% rate on line, and one paid reinstatement pro rata as to amount.
- Implemented aggregate stop loss attaching at 90% gross loss ratio with EUR 10,000,000 limit and premium equal to 1.25 times recovery.
- Added counterparty default adjustment using PD 0.50% and LGD 50%.
- Added claim-level and annual aggregate audit outputs, including gross-to-net reconciliation.
- Added Streamlit Reinsurance page with quota share controls, gross losses, ceded losses, recoveries, default-adjusted recoverables, net losses, reconciliation table, and gross/net chart.
- Added tests for formulas, treaty ordering, quota share behavior, recovery caps, default-adjusted recoverables, and deterministic generated-data output.

No broader treaty framework, capital model, reserving model, or reporting module was started in this phase.

## 2026-05-30 - Phase 5 Claim Simulation And Observed Valuation Snapshot

- Added deterministic claim frequency simulation using a Gamma-Poisson negative binomial representation.
- Added claim severity simulation for attritional, theft/fire, BI, large BI, and catastrophe allocated claims.
- Added deductible-then-limit application while retaining zero insured amount claims for diagnostics.
- Added reporting delay, settlement delay, case estimate, case reserve, and payment generation.
- Added stochastic Dirichlet payment shares around fixed payment patterns, with final settled payment adjustment to insured ultimate.
- Added catastrophe event simulation with affected-policy probability by country, urbanicity, and vehicle multipliers, mapped to `HRG04`.
- Added end-to-end synthetic reality generation for policies, claims, payments, case reserves, catastrophe events, observed valuation snapshot, and isolated diagnostic truth.
- Updated Synthetic Data and Portfolio Overview pages to use observed generated data.
- Added Experience Analysis page using observed modelling inputs only.
- Added tests for frequency tolerance, severity tolerance, deductible and limit order, lifecycle dates, payment totals, future transaction exclusion, truth isolation, and deterministic reproducibility.

No reserving model, paid triangle module, capital model, GLM, or regulatory reporting module was started in this phase.

## 2026-05-30 - Phase 4 Deterministic Policy Generation And Pricing

- Added deterministic synthetic policy generation for underwriting and accident years 2021 through 2026.
- Added interactive policy generation modes: `small`, `medium`, and `full`.
- Added fixed portfolio mix distributions and conditional dependency rules in the required order.
- Added transparent deterministic pricing with expected frequency, expected severity, loss cost, technical premium, charged premium, written premium, and earned premium.
- Added minimum premium, nearest-EUR-5 rounding, market cycle factors, and deterministic competitive factors.
- Added chart helpers for portfolio overview pages.
- Updated the Synthetic Data page to generate and validate small-mode policy data.
- Added Portfolio Overview and Pricing Streamlit pages.
- Added tests for deterministic generation, required columns, distribution tolerance, conditional behavior, golden pricing outputs, minimum premium, rounding, and non-negative premiums.

No GLM, claims simulation, reserving model, capital model, or later actuarial modules were started in this phase.

## 2026-05-30 - Phase 3 Fixture Data And Strict Table Validation

- Added deterministic small portfolio fixture tables under `tests/fixtures/small_portfolio`.
- Added explicit schema validation for policies, claims, payments, case reserves, catastrophe events, reinsurance recoveries, economic scenarios, asset portfolio, synthetic truth, and observed valuation snapshot.
- Added data-quality rules `DQ001` through `DQ010`.
- Added primary key, foreign key, required column, numeric type, and date parsing checks.
- Added a validation summary model with export-blocking errors and non-blocking warnings.
- Added the Synthetic Data And Risk Engine Streamlit page to show fixture counts, validation status, errors, and warnings.
- Added tests for the valid golden fixture, each required DQ rule, primary key failures, foreign key failures, and missing columns.

No large synthetic data generation or actuarial calculation modules were started in this phase.

## 2026-05-30 - Phase 2 Assumption And Scenario Metadata Foundation

- Added typed Pydantic assumption models under `src/miniinsure/assumptions`.
- Added deterministic assumption loading with the required merge order: base, regulatory, scenario, stress, UI.
- Added supported scenario transformation modes: `replace`, `multiply`, `additive_percentage_point`, and `additive_amount`.
- Added base and regulatory YAML assumption files under `data/assumptions`.
- Added stable assumption hashing and scenario metadata JSON generation.
- Added `ScenarioState` for Streamlit pages.
- Updated the Home page with scenario name, portfolio mode, visible assumption hash, and scenario metadata download controls.
- Added tests for merge order, transformations, hashing, XBRL validation, seed policy, company profile fields, and metadata content.

No actuarial calculation modules were started in this phase.

## 2026-05-30 - Phase 1 Foundation

- Initialized the MiniInsure Europe NL modular monolith structure.
- Added Python package metadata for a Python 3.12+ project.
- Added the `src/miniinsure` package with deterministic randomness utilities and stable project metadata.
- Added the Streamlit Home page under `app`.
- Added README, audit trail, and manual user testing documentation.
- Added a smoke test for importability and deterministic random generator behavior.

No existing work was deleted because the repository directory was blank at inspection time.
