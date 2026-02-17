from __future__ import annotations

from enum import Enum


class IngestErrorCode(str, Enum):
    E_NO_REG_NO = "E_NO_REG_NO"
    E_REG_NO_NORMALIZE_FAILED = "E_REG_NO_NORMALIZE_FAILED"
    E_PARSE_FAILED = "E_PARSE_FAILED"
    E_CONFLICT_UNRESOLVED = "E_CONFLICT_UNRESOLVED"
