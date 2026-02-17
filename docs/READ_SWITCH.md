# Read Path Switch (Gray Release)

## Switch

Environment variable:

- `USE_REGISTRATION_ANCHOR=false` (default): keep legacy read path.
- `USE_REGISTRATION_ANCHOR=true`: enable registration-anchor read path for product detail.

Mapped setting:

- `app.core.config.Settings.use_registration_anchor`

## Behavior

### `false` (legacy)

- Search/list/detail use existing `products` fields directly.
- No anchor summary is attached.

### `true` (anchor detail mode)

For `GET /api/products/{product_id}`:

1. Prefer `products.registration_id -> registrations`.
2. If missing, attempt registration resolution from:
   - `products.reg_no`
   - `product_variants.product_id -> registry_no`
   - normalized `registry_no` matching normalized `products.reg_no`
3. Use resolved `registrations` fields to enrich detail output:
   - `registration_id`
   - `reg_no`
   - `status`
   - `approved_date`
   - `expiry_date`
4. Aggregate summary from:
   - `nmpa_snapshots`
   - `registration_events`

Search endpoint remains unchanged to minimize frontend impact.

## Rollback

Fast rollback is config-only:

1. Set `USE_REGISTRATION_ANCHOR=false`
2. Restart API service

No schema or data rollback needed.

## Verification

Suggested checks after switch:

1. Compare `/api/search` totals under same query before/after switch.
2. Sample `/api/products/{id}` responses:
   - `registration_id` null rate should decrease.
   - `anchor_summary` should appear only when switch is on.
