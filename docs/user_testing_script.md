# User Testing Script

## Phase 12 Manual Test Steps

1. Run the automated tests with `pytest`.
2. Start the app with `streamlit run app/Home.py`.
3. Open the `Financial Reporting` page.
4. Confirm gross earned premium, net claims incurred, expenses, combined ratio, and return on capital are visible.
5. Confirm the management income statement is visible.
6. Confirm the Solvency II-style balance sheet is visible.
7. Confirm reconciliation checks show `pass`.
8. Open the `QRT Reporting Pack` page.
9. Confirm the page clearly says outputs are mock QRT-shaped only and not real XBRL.
10. Confirm the applicability matrix shows generated, conditional, empty generated, and not-applicable templates.
11. Confirm `S.12.01.02` and `S.28.02.01` are explicitly marked not applicable.
12. Select several templates in the template viewer and confirm the tables render.
13. Confirm the validation report has no blocking errors, or only expected warnings.
14. Download the mock QRT Excel workbook.
15. Download the mock QRT ZIP and confirm it includes the mock workbook, board report Markdown, and `scenario_metadata.json`.
16. Confirm no `.xbrl` or real filing XML is downloaded.
17. Open the `Board Risk Report` page.
18. Confirm the Markdown preview includes executive summary, valuation date and scenario, SCR/MCR, own funds, technical provisions, reserve risk, traffic-light KRIs, limitations, validation status, timestamp, and assumption hash.
19. Download the board risk report Markdown.
20. Confirm no authentication, background worker, real filing system, or production database workflow is exposed.

## Phase 11 Manual Test Steps

1. Run the automated tests with `pytest`.
2. Start the app with `streamlit run app/Home.py`.
3. Open the `Capital Model` page.
4. Confirm economic capital, VaR 99.5%, TVaR 99.5%, Standard Formula SCR, MCR, and solvency ratio are visible.
5. Confirm the one-year loss distribution chart is visible.
6. Confirm reserve risk, premium risk, market risk, and operational risk contributions are visible.
7. Confirm simplified Standard Formula module charges are visible.
8. Confirm stress summaries are visible.
9. Open the `Solvency II Balance Sheet` page.
10. Confirm assets, liabilities, technical provisions, own funds, eligible own funds, SCR, MCR, solvency ratio, and MCR ratio are visible.
11. Confirm the reconciliation status is `PASS`.
12. Confirm the page states that it is educational and not a regulatory filing.

## Phase 10 Manual Test Steps

1. Run the automated tests with `pytest`.
2. Start the app with `streamlit run app/Home.py`.
3. Open the `ALM` page.
4. Confirm the dependency matrix validation status is visible and shows `PASS`.
5. Confirm the risk-free curve table is visible.
6. Confirm asset allocation is visible as a chart and table.
7. Confirm the asset calibration metrics show opening assets, SCR proxy, and opening liabilities.
8. Confirm the liability cash-flow profile is visible.
9. Confirm the liquidity gap table is visible.
10. Confirm the duration gap table is visible.
11. Confirm simple market stress outputs are visible.
12. Confirm no ALM optimization, market risk SCR aggregation, or regulatory reporting output is exposed.

## Phase 9 Manual Test Steps

1. Run the automated tests with `pytest`.
2. Start the app with `streamlit run app/Home.py`.
3. Open the `Technical Provisions` page.
4. Confirm the page shows quick-mode reserve risk controls for seed and simulation count.
5. Confirm the default reserve simulation count is `1,000`.
6. Confirm reserve capital, mean reserve loss, VaR 99.5%, TVaR 99.5%, and adverse probability are visible.
7. Confirm the reserve risk summary table is visible.
8. Confirm the reserve loss distribution chart is visible.
9. Confirm the component summary table is visible.
10. Click `Rerun reserve risk` without changing the seed or simulation count and confirm the page rerenders without changing the reproducibility settings.
11. Confirm full-mode reserve risk settings are not presented as the default workflow.

## Phase 8 Manual Test Steps

1. Run the automated tests with `pytest`.
2. Start the app with `streamlit run app/Home.py`.
3. Open the `Technical Provisions` page.
4. Confirm claims provision, premium provision, reinsurance recoverables, risk margin, gross technical provisions, and net technical provisions are visible.
5. Confirm the reconciliation status is `PASS`.
6. Confirm the provision bridge table shows gross best estimate, net best estimate, risk margin, valuation tolerance, and reconciliation difference.
7. Confirm claims provision cash flows are visible.
8. Confirm reinsurance recoverables cash flows are visible.
9. Confirm risk margin runoff is visible for 10 years.
10. Confirm the page does not expose stochastic reserve risk, SCR capital model, or regulatory reporting outputs.

## Phase 7 Manual Test Steps

1. Run the automated tests with `pytest`.
2. Start the app with `streamlit run app/Home.py`.
3. Open the `Technical Provisions` page.
4. Confirm the page states that deterministic reserving uses observed valuation data only.
5. Confirm the paid triangle is visible.
6. Confirm the incurred triangle is visible.
7. Confirm development factors are visible.
8. Confirm selected deterministic reserve rows show selected method, ultimate, IBNR, and selected reserve.
9. Confirm the selected reserve by LoB and HRG summary is visible.
10. Confirm there is no stochastic reserve risk, discounting, capital model, or regulatory reporting output on the page.

## Phase 6 Manual Test Steps

1. Run the automated tests with `pytest`.
2. Start the app with `streamlit run app/Home.py`.
3. Open the `Reinsurance` page.
4. Confirm the quota share toggle is visible and off by default.
5. Confirm the quota share ceded percentage control allows values from 0% to 40% when quota share is enabled.
6. Confirm gross losses, ceded losses, recoveries, default-adjusted recoverables, and net losses are visible.
7. Confirm the gross-to-net reconciliation table is visible.
8. Enable quota share and choose a ceded percentage.
9. Confirm ceded losses and net losses update.
10. Confirm the basic gross/net comparison chart or table renders without errors.

## Phase 5 Manual Test Steps

1. Run the automated tests with `pytest`.
2. Start the app with `streamlit run app/Home.py`.
3. Open the `Synthetic Data And Risk Engine` page.
4. Confirm policy count, claim count, payment count, case reserve count, catastrophe event count, and observed snapshot count are visible.
5. Confirm validation status is `PASS`.
6. Confirm the observed valuation snapshot table is visible and does not show hidden true ultimate fields.
7. Open the `Portfolio Overview` page.
8. Confirm observed claims and observed paid by year render without errors.
9. Open the `Experience Analysis` page.
10. Confirm frequency by year, severity by claim type, loss ratio by year, and paid emergence view render without errors.
11. Confirm the Experience Analysis page states that hidden synthetic truth is not loaded.

## Phase 4 Manual Test Steps

1. Run the automated tests with `pytest`.
2. Start the app with `streamlit run app/Home.py`.
3. Open the `Synthetic Data And Risk Engine` page.
4. Confirm small-mode policy generation creates `60,000` policies across underwriting years 2021 through 2026.
5. Confirm the counts by underwriting year show `10,000` policies for each year.
6. Confirm policy validation status is `PASS`.
7. Open the `Portfolio Overview` page.
8. Confirm business mix, exposure by year, written and earned premium by year, and LoB mix render without errors.
9. Open the `Pricing` page.
10. Confirm average technical premium, average charged premium, and rate adequacy render without errors.
11. Confirm the segment profitability table renders.
12. Confirm the Pricing page states `GLM diagnostics will be added after deterministic pricing is stable.`

## Phase 3 Manual Test Steps

1. Run the automated tests with `pytest`.
2. Start the app with `streamlit run app/Home.py`.
3. Open the `Synthetic Data And Risk Engine` page from the Streamlit sidebar.
4. Confirm the page states that this phase validates deterministic golden fixtures only.
5. Confirm fixture record counts are visible for policies, claims, payments, case reserves, catastrophe events, reinsurance recoveries, economic scenarios, asset portfolio, synthetic truth, and observed valuation snapshot.
6. Confirm validation status is `PASS` for the golden fixture.
7. Confirm error count is `0` and warning count is `0`.
8. Confirm future exports are shown as allowed when there are no errors.
9. Confirm the page has separate `Errors` and `Warnings` sections.
10. Confirm no large synthetic data generation control is available yet.

## Phase 2 Manual Test Steps

1. Run the automated tests with `pytest`.
2. Start the app with `streamlit run app/Home.py`.
3. Confirm the Home page opens and shows `MiniInsure Europe NL`.
4. Enter a custom scenario name.
5. Change the portfolio mode between `small`, `medium`, and `full`.
6. Confirm the displayed portfolio mode changes after selection.
7. Confirm an assumption hash is visible on the page.
8. Confirm the assumption hash changes when the portfolio mode changes.
9. Click `Download scenario metadata JSON`.
10. Confirm the downloaded JSON includes scenario name, seed `20261231`, valuation date `2026-12-31`, assumption hash, app version, generation timestamp, and selected portfolio mode.
11. Confirm the page still warns that the app is educational and does not produce real Solvency II filings or real XBRL.
12. Confirm no actuarial calculation modules are exposed yet.

## Phase 1 Manual Test Steps

1. Install the project with `pip install -e .`.
2. Run the automated smoke test with `pytest`.
3. Start the app with `streamlit run app/Home.py`.
4. Confirm the Home page opens and shows `MiniInsure Europe NL`.
5. Confirm the page shows valuation date `2026-12-31`.
6. Confirm the page shows reporting quarter `2026 Q4`.
7. Confirm the page summarizes the synthetic Netherlands motor insurer scope.
8. Confirm the page warns that the app is educational and does not produce real Solvency II filings or real XBRL.
9. Confirm there are no actuarial calculations or scenario modules exposed yet.
