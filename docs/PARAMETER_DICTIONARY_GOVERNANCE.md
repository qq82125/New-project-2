# Parameter Dictionary Governance

参数字典分两层治理（SSOT）：
- Core：`/Users/GY/Documents/New project 2/docs/PARAMETER_DICTIONARY_CORE_V1.yaml`
- Approved：`/Users/GY/Documents/New project 2/docs/PARAMETER_DICTIONARY_APPROVED_V1.yaml`

二者 key 必须全局不重叠。

## Core vs Approved

- Core：跨页面/跨流程的稳定核心口径，变更门槛最高。
- Approved：通过评审后可进入 allowlist 的扩展参数，支持更快迭代。
- allowlist 可引用集合：`Core ∪ Approved`。
- 任何未登记 key 都不能进入 allowlist（dry-run 警告，execute 失败）。

## Governance Rules

- Core/Approved key 必须走 PR 变更。
- 只允许新增 key，或将 `deprecated` 从 `false` 变为 `true`。
- 禁止删除历史 key。
- 禁止重命名 key（在治理上等同删除旧 key）。
- 默认禁止将 `deprecated` 从 `true` 改回 `false`。

## Baseline Mechanism

- 基线文件：`/Users/GY/Documents/New project 2/docs/PARAMETER_DICTIONARY_CORE_BASELINE.json`
- 基线文件：`/Users/GY/Documents/New project 2/docs/PARAMETER_DICTIONARY_APPROVED_BASELINE.json`
- PR 校验命令（只校验，不更新基线）：

```bash
python scripts/validate_core_param_dictionary.py
```

- 发布时显式更新基线（仅在字典版本发布时）：

```bash
python scripts/validate_core_param_dictionary.py --update-baseline core
python scripts/validate_core_param_dictionary.py --update-baseline approved
# 或一次更新两者
python scripts/validate_core_param_dictionary.py --update-baseline all
```

## Approved 准入标准

- 覆盖率：非空覆盖率达到可用阈值（建议 >= 20%，按字段类型可调整）。
- 噪声：文本字段噪声可控，样本值可解释。
- 业务价值：可用于检索、对标、风险、证据展示中的至少一项。
- 可追踪：字段定义、单位、口径明确，可审计。

## Allowlist 灰度流程

`candidate -> approved -> allowlist -> (可选) promote to core`

- candidate：仅候选池观察，不可直接写主口径。
- approved：通过评审后进入 Approved 字典。
- allowlist：在 `admin_configs['udi_params_allowlist']` 启用写入。
- promote to core：稳定后提升为 Core（保留治理记录）。

## 回滚策略

- 通过 `udi_params_allowlist_version` 快速回退口径版本。
- 必要时按 `product_params.param_key_version` 做对比/重放/回滚。
