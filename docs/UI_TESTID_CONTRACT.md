# UI TestID Contract

## Naming Rule
- Format: `page__section__element`
- Character set: lowercase letters, numbers, `_`
- Separator: double underscore `__`

## Page Enum
- `login`
- `dashboard`
- `search`
- `detail`
- `admin`
- `admin_queue`
- `admin_reason`
- `pro`

## Section Enum
- `header`
- `kpi`
- `lri_top`
- `risk_top`
- `competitive_top`
- `trend`
- `lri_map`
- `filters`
- `saved_views`
- `results`
- `export`
- `overview`
- `fields`
- `evidence`
- `timeline`
- `nav`
- `cards`
- `reason_top`
- `list`
- `bulk`
- `sample`
- `cta`

## Element Rule
- `element` is custom but must stay stable after release.
- Recommended examples: `title`, `button`, `row`, `table`, `toggle`.

## Scope
- This contract is applied to Snapshot Map points P0-P6.
- New UI elements should follow this contract first, then be added to smoke coverage.
- Existing compatibility selector kept for ProGate popup: `progate__cta__panel`.
