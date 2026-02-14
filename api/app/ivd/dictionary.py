from __future__ import annotations

"""Back-compat dictionary module.

The canonical keyword sets live in `app.services.ivd_dictionary`.
This module keeps stable names for pipeline code while avoiding duplicated keyword maintenance.
"""

from app.services.ivd_dictionary import (
    INSTRUMENT_EXCLUDE as IVD_NEGATIVE,
    IVD_INSTRUMENT_INCLUDE as IVD_POSITIVE_INSTRUMENT,
    IVD_REAGENT_INCLUDE as IVD_POSITIVE_REAGENT,
    IVD_SOFTWARE_INCLUDE as IVD_POSITIVE_SOFTWARE,
)
