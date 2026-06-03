from __future__ import annotations

# Backward-compatible entrypoint. New implementation lives in roundtrip_pandoc.py.
from roundtrip_pandoc import build_roundtrip_report as _build_roundtrip_report
from roundtrip_pandoc import main


def build_roundtrip_report(*args, **kwargs):
    if "style_map_used" in kwargs and "style_spec_used" not in kwargs:
        kwargs["style_spec_used"] = kwargs.pop("style_map_used")
    return _build_roundtrip_report(*args, **kwargs)


if __name__ == "__main__":
    main()
