# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Shared inline-CSS dimension parsing.

The target-size audit check and its remediation strategy both need to read and
rewrite explicit ``width``/``height`` declarations on elements. Centralizing
that parsing here keeps the size they detect against and the size they enforce
to from drifting apart, and gives both a single place that understands the
``!important`` modifier.
"""

import re
from typing import Optional

from bs4 import Tag

# Matches a single CSS declaration like "width: 10px" or "min-height: 24px !important".
# Groups: (1) property name, (2) numeric value, (3) "!important" or "".
_PX_DECLARATION = re.compile(
    r"^\s*([a-z-]+)\s*:\s*([0-9.]+)px\s*(!important)?\s*$",
    re.IGNORECASE,
)


def declared_dimension(element: Tag, dimension: str) -> Optional[float]:
    """
    Return an element's explicitly declared pixel size for ``width``/``height``.

    Inline ``style`` is consulted first (preferring ``min-<dimension>`` since it
    sets the rendered floor), then the legacy HTML ``width``/``height``
    attribute. Returns the value in CSS pixels, or None if none is declared.

    Args:
        element: The element to inspect.
        dimension: Either "width" or "height".

    Returns:
        The declared size in CSS pixels, or None.
    """
    style = (element.get("style") or "") if hasattr(element, "get") else ""
    for prop in (f"min-{dimension}", dimension):
        match = re.search(rf"\b{prop}\s*:\s*([0-9.]+)px", style, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

    attr_value = element.get(dimension) if hasattr(element, "get") else None
    if attr_value:
        match = re.match(r"^\s*([0-9.]+)\s*(px)?\s*$", str(attr_value))
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

    return None


def strip_undersized_dimensions(style: str, minimum_px: float) -> str:
    """
    Remove explicit width/height declarations below ``minimum_px``.

    Both plain (``width: 10px``) and ``!important`` (``width: 10px !important``)
    declarations are dropped when undersized, so an ``!important`` rule cannot
    survive to override the enforced minimum. Declarations that are not px
    width/height (or that meet the minimum) are preserved verbatim.

    Args:
        style: The element's inline style string.
        minimum_px: The minimum acceptable size in CSS pixels.

    Returns:
        The style string with undersized width/height declarations removed.
    """

    def keep(declaration: str) -> bool:
        match = _PX_DECLARATION.match(declaration)
        if not match:
            return True
        prop = match.group(1).lower()
        if prop not in ("width", "height"):
            return True
        try:
            return float(match.group(2)) >= minimum_px
        except ValueError:
            return True

    declarations = [d for d in style.split(";") if d.strip()]
    return "; ".join(d.strip() for d in declarations if keep(d))
