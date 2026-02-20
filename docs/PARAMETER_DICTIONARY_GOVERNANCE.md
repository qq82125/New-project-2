# Core Parameter Dictionary Governance

Core 参数字典以 `/Users/GY/Documents/New project 2/docs/PARAMETER_DICTIONARY_CORE_V1.yaml` 为唯一事实来源（SSOT）。

## Governance Rules

- Core key 必须走 PR 变更。
- 只允许新增 key，或将 `deprecated` 从 `false` 变为 `true`。
- 禁止删除历史 key。
- 禁止重命名 key（在治理上等同删除旧 key）。
- 默认禁止将 `deprecated` 从 `true` 改回 `false`。

## Baseline Mechanism

- 基线文件：`/Users/GY/Documents/New project 2/docs/PARAMETER_DICTIONARY_CORE_BASELINE.json`
- PR 校验命令（只校验，不更新基线）：

```bash
python scripts/validate_core_param_dictionary.py
```

- 发布时显式更新基线：

```bash
python scripts/validate_core_param_dictionary.py --update-baseline
```

只有在确认字典版本发布时，才允许提交新的 baseline。
