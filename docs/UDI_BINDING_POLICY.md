# UDI Binding Policy

## 目标

在 `udi_di_parser` 入口下，保证 UDI 记录按“DI 规格层 + 注册证锚点”入库：

- `di` 是规格/包装层唯一标识，必须写入 `product_variants(di UNIQUE)`。
- `registration_no` 是规范化后的唯一锚点，能解析时必须先落 `registrations` 再绑定变体。

## 处理规则

### 1) 每条 UDI 记录都要写 `product_variants`

- 从 payload 提取 `di`（`udi_di`/`di`）。
- 若缺 `di`，该条不写变体（无法满足唯一键）。
- 若有 `di`，执行 upsert（`ON CONFLICT (di)`）。

### 2) payload 含 `registry_no`（或等价字段）

顺序必须是：

1. `normalize_registration_no`。
2. `upsert registrations(registration_no)`。
3. 回填 `product_variants.registry_no`。
4. 回填 `product_variants.product_id`：
   - 先查 `products.registration_id = registration.id`；
   - 若不存在，创建一个最小 `products` 快照（`udi_di/reg_no/registration_id/name` 等最小字段）。

说明：一个注册证可对应多个 DI（1:N），多个 DI 可挂到同一 `product_id`（注册证级展示实体）。

### 3) payload 不含 `registry_no`

- 仍然写 `product_variants`（保留 DI 资产）。
- 写 `pending_records`，`reason_code='NO_REG_NO'`，用于后续人工/规则补链。

## 审计命令

新增命令：

```bash
python -m app.workers.cli udi:audit --dry-run
```

输出包含：

- 每个 `registration_no` 关联 DI 数量分布（`P50/P90/P99`）。
- 未绑定注册证的 DI 数量（`registry_no` 为空的 `product_variants` 数量）。
- 超阈值异常注册证列表（可通过 `--outlier-threshold` 调整）。

## 幂等与兼容性

- 变体写入使用 `di` 唯一键 upsert，重复执行幂等。
- 对已有 `product_variants`，若新批次缺 `registry_no/product_id`，不会覆盖已有非空绑定。
- 不改变现有前端 IVD 展示口径（`products.is_ivd = true`）。
