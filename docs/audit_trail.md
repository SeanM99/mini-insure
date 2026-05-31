# Audit Trail

MiniInsure Europe NL is educational software for a synthetic Netherlands-based motor insurer. This audit trail records the project policies that later phases must follow.

## Assumption Source Policy

Assumptions must be explicit, traceable, and documented near the module or scenario that uses them. The controlling specification is the project whitepaper or existing repository documentation when present. If no source exists, assumptions must be marked as synthetic educational assumptions and must not be presented as market, regulatory, or company truth.

Effective assumptions are loaded in this deterministic order:

1. `base`
2. `regulatory`
3. `scenario`
4. `stress`
5. `ui`

The default merge mode replaces leaf values. Scenario and stress override layers may use the documented transformation modes `replace`, `multiply`, `additive_percentage_point`, and `additive_amount`. Transformation inputs must be explicit and auditable; hidden adjustments are not allowed.

## Seed Policy

The master seed is `20261231`. All stochastic work must use `numpy.random.default_rng`, either with the master seed or with documented scenario-specific seeds derived from it. Modules must not use hidden global randomness.

## Scenario Metadata Policy

Scenario outputs must include enough metadata for reproduction: valuation date, reporting quarter, model or module name, assumption set, seed, run timestamp where applicable, and any user-selected scenario controls. Later phases should keep metadata attached to exports and charts where practical.

Scenario metadata JSON must include the scenario name, seed, valuation date, reporting quarter, portfolio mode, stable assumption hash, app version, and generation timestamp. The assumption hash is based on canonical JSON from the validated effective assumption model.

## Validation Policy

Validation should be explicit and readable. Inputs should be checked close to their boundary, with clear error messages for invalid dates, negative amounts where not allowed, unsupported scenario names, and inconsistent dimensions. Tests should cover importability, deterministic behavior, and high-risk business rules as modules are added.

Typed assumptions are validated with Pydantic before use by the UI or later modules. Validation must fail if real XBRL is enabled or if mock reporting safeguards are disabled.

Fixture and table validation uses deterministic golden data before any large synthetic data generation is introduced. Fixture files may be CSV for readability. Future production-like generated outputs should use Parquet.

Validation messages are split into export-blocking errors and non-blocking warnings. Any validation error must block future export actions. Warnings may be displayed for user review but do not block export.

The current strict table validation rules are:

1. `DQ001`: policy premiums must be greater than or equal to zero.
2. `DQ002`: policy exposure must be in `(0, 1]`.
3. `DQ003`: claim ultimate must be greater than or equal to zero.
4. `DQ004`: payment date must be on or after accident date.
5. `DQ005`: report date must be on or after accident date.
6. `DQ006`: settlement date must be on or after report date.
7. `DQ007`: cumulative paid must be non-decreasing in paid triangles.
8. `DQ008`: case reserve must be greater than or equal to zero.
9. `DQ009`: reinsurance recovery must not exceed insured loss after treaty retention and limit.
10. `DQ010`: asset weights must sum to `1.0000` within `1e-6`.

Primary keys must be present and unique. Claims must connect to policies, and payments must connect to claims. Required columns must exist, and date columns must parse as dates.

Mock QRT validation uses DNB-style educational checks:

1. `DNB001`: `S.06.02` asset total reconciles to `S.02.01` investments plus cash.
2. `DNB002`: `S.17.01` technical provisions equal best estimate plus risk margin.
3. `DNB003`: `S.02.01` assets minus liabilities equal excess assets over liabilities.
4. `DNB004`: `S.23.01` eligible own funds reconcile to excess assets over liabilities.
5. `DNB005`: `S.28.01` MCR equals the MCR module output.
6. `DNB006`: `S.05.01` premium and claims totals reconcile to financial reporting; this is a warning.
7. `DNB007`: not-applicable templates are explicitly flagged in `S.01.01`.
8. `DNB008`: monetary values are EUR and rounded according to the mock export convention.

Any `DNB` validation error must block QRT ZIP export. `DNB006` warnings may be displayed without blocking export.

## Mock Reporting Limitation

Real XBRL is disabled and out of scope. Any future QRT-style output must be clearly labelled mock/QRT-shaped only. The app must not create, validate, or imply official Solvency II regulatory filings.

The mock QRT pack is an educational spreadsheet/ZIP artifact only. It may include QRT-like sheet names and a DNB-style validation report, but it is not a regulatory submission pack and must never be described as one. Export file names must include `qrt_mock`, and regression tests must prove that no `.xbrl` or real filing XML is generated.

## No Hidden Truth Leakage Rule

The project must not hide real-world insurer data, regulatory submission data, or external proprietary assumptions behind synthetic examples. Synthetic data and assumptions must remain visibly synthetic so users do not mistake educational outputs for real actuarial conclusions.

Claim simulation separates observed modelling inputs from synthetic truth. Observed tables may include report dates, visible settlement dates, paid amounts, case estimates, and case reserves as of the valuation date. Observed tables must not include hidden true ultimate fields, gross ultimate fields, insured ultimate fields, or diagnostic truth identifiers.

Synthetic truth may exist only as an isolated diagnostics output. Loading it requires an explicit diagnostics acknowledgement in code and Streamlit pages must not load it. Future reserving, reporting, and experience pages must use observed modelling inputs only.

The observed valuation snapshot is fixed at valuation date `2026-12-31`. It must exclude future payments and future claim status information after that date.
