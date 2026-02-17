# Registration Anchor Constraints (Indexes/Uniqueness Only)

目的：在不做任何数据回填、不改业务逻辑的前提下，强化“以 `registrations.registration_no` 为唯一锚点”的查询路径性能与一致性约束。

## 迁移

- Migration: `migrations/0021_enforce_registration_anchor.sql`
- Rollback: `scripts/rollback/0021_enforce_registration_anchor_down.sql`

## 新增/强化内容

### products
- `idx_products_reg_no_anchor`：`CREATE INDEX ... ON products(reg_no)`
- `idx_products_registration_id_anchor`：`CREATE INDEX ... ON products(registration_id)`
- `idx_products_reg_no_ivd_anchor`（partial，可选已启用）：
  - `CREATE INDEX ... ON products(reg_no) WHERE is_ivd IS TRUE AND reg_no IS NOT NULL AND btrim(reg_no) <> ''`

用途：
- 加速按 `reg_no`/`registration_id` 的定位与 join
- 加速 IVD-only 场景下按 `reg_no` 的过滤（符合前台默认口径）

### product_variants
- `idx_product_variants_registry_no_anchor`：`CREATE INDEX ... ON product_variants(registry_no)`
- `idx_product_variants_product_id_anchor`：`CREATE INDEX ... ON product_variants(product_id)`

用途：
- 加速 `registry_no` 映射查询
- 加速 `di -> product_id -> products/registrations` 的路径查询

### registrations
- 校验 `registrations.registration_no` 唯一性：
  - 若已存在 UNIQUE constraint 或唯一索引：不改动
  - 若不存在：补一个唯一索引 `uq_registrations_registration_no_anchor`

说明：该迁移不检查/修复历史脏数据（例如重复 `registration_no`），仅在缺失约束时补齐唯一性约束。

## 回滚方式

执行 `scripts/rollback/0021_enforce_registration_anchor_down.sql` 会按名字删除本迁移创建的索引：
- `idx_products_reg_no_anchor`
- `idx_products_registration_id_anchor`
- `idx_products_reg_no_ivd_anchor`
- `idx_product_variants_registry_no_anchor`
- `idx_product_variants_product_id_anchor`
- `uq_registrations_registration_no_anchor`

注意：若某环境中碰巧已经存在同名索引，回滚会把它一并删除（本仓库使用迁移专属命名以降低冲突概率）。

