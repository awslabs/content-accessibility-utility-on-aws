# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Shared WCAG color-contrast math and a deterministic color-nudge helper.

The audit's ``ColorContrastCheck`` and the rendered/agent contrast remediation
both need the same luminance/ratio math (WCAG 2.x relative-luminance formula).
Centralizing it here keeps the value they *detect against* and the value they
*fix to* from drifting apart, and gives the deterministic remediation path
(``disable_ai`` / the agent's rule-based fallback) a way to pick a compliant
color without a model.
"""

from __future__ import annotations

from typing import Optional, Tuple

# WCAG 2.x minimum contrast ratios.
AA_NORMAL_TEXT = 4.5
AA_LARGE_TEXT = 3.0
AA_NON_TEXT = 3.0  # UI components / graphical objects (1.4.11)


def _gamma(value: float) -> float:
    """Gamma-expand one sRGB channel (0-1) per the WCAG definition."""
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """Relative luminance of an sRGB color, per WCAG 2.x."""
    r, g, b = (c / 255 for c in rgb)
    return 0.2126 * _gamma(r) + 0.7152 * _gamma(g) + 0.0722 * _gamma(b)


def contrast_ratio(rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> float:
    """Contrast ratio between two sRGB colors (1.0 – 21.0)."""
    l1 = relative_luminance(rgb1)
    l2 = relative_luminance(rgb2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def parse_color(value: str) -> Optional[Tuple[int, int, int]]:
    """Parse ``#rgb``/``#rrggbb`` or ``rgb()/rgba()`` into an (r, g, b) tuple.

    Returns ``None`` for anything else (named colors, gradients, transparent),
    so callers can decline to nudge a color they cannot reason about.
    """
    if not value:
        return None
    v = value.strip().lower()
    if v.startswith("#"):
        h = v[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) == 6:
            try:
                return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
            except ValueError:
                return None
        return None
    if v.startswith(("rgb(", "rgba(")):
        inner = v[v.index("(") + 1 : v.rindex(")")]
        parts = [p.strip() for p in inner.split(",")]
        if len(parts) >= 3:
            try:
                return tuple(max(0, min(255, int(round(float(p))))) for p in parts[:3])  # type: ignore[return-value]
            except ValueError:
                return None
    return None


def to_hex(rgb: Tuple[int, int, int]) -> str:
    """Format an (r, g, b) tuple as ``#rrggbb``."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _scale(rgb: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    return tuple(max(0, min(255, int(round(c * factor)))) for c in rgb)  # type: ignore[return-value]


def adjust_for_contrast(
    fg: Tuple[int, int, int],
    bg: Tuple[int, int, int],
    target_ratio: float = AA_NORMAL_TEXT,
) -> Optional[Tuple[int, int, int]]:
    """Return a foreground color meeting ``target_ratio`` against ``bg``.

    Keeps the foreground's hue but darkens or lightens it (whichever direction
    the background favors) until the ratio is met, falling back to black or white
    if scaling the hue cannot reach the target. Returns ``None`` only if even
    pure black/white against this background cannot meet the target (i.e. the
    background itself is mid-tone enough that no text color works — rare; the
    caller should then also change the background).
    """
    if contrast_ratio(fg, bg) >= target_ratio:
        return fg  # already compliant

    bg_lum = relative_luminance(bg)
    # Darker text on light backgrounds, lighter text on dark backgrounds.
    darken = bg_lum > 0.5
    steps = 20
    for i in range(1, steps + 1):
        factor = 1 - i / steps if darken else 1 + i / steps
        candidate = _scale(fg, factor)
        if contrast_ratio(candidate, bg) >= target_ratio:
            return candidate
    # Fall back to the extreme with the better ratio.
    black, white = (0, 0, 0), (255, 255, 255)
    best = max((black, white), key=lambda c: contrast_ratio(c, bg))
    return best if contrast_ratio(best, bg) >= target_ratio else None
