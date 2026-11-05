# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0


"""
Image accessibility checks.

This module provides checks for proper image accessibility.
"""

import os
import re
from urllib.parse import unquote, urlparse

from content_accessibility_utility_on_aws.audit.base_check import AccessibilityCheck

# Alt text that names the kind of image instead of describing it.
GENERIC_ALT_TEXT = frozenset(
    {
        "image",
        "img",
        "diagram",
        "photo",
        "photograph",
        "picture",
        "pic",
        "graphic",
        "icon",
        "chart",
        "graph",
        "figure",
        "screenshot",
        "logo",
        "untitled",
        "placeholder",
        "image description unavailable",
    }
)

_IMAGE_EXTENSIONS = r"(?:png|jpe?g|gif|svg|webp|bmp|tiff?|avif|heic)"
# "IMG_1234.jpg", "chart-a.png", "DSC00042.JPG"
_FILENAME_ALT = re.compile(rf"^[\w\-. ]+\.{_IMAGE_EXTENSIONS}$", re.IGNORECASE)
# Camera-style names without an extension: "IMG_1234", "DSC00042", "PXL_2024..."
_CAMERA_NAME_ALT = re.compile(r"^(?:img|dsc|dscn|dcim|pxl|photo|image)[_\-]?\d+$", re.IGNORECASE)


def _src_basename(src: str) -> str:
    """Basename of an image src (URL or path), decoded, or ""."""
    if not src or src.strip().lower().startswith("data:"):
        return ""
    path = urlparse(src.strip()).path or src
    return os.path.basename(unquote(path))


def generic_alt_reason(alt_text: str, src: str = "") -> str:
    """Why ``alt_text`` is generic, or "" if it looks like a real description.

    Flags generic words ("chart", "image"), file names ("IMG_1234.jpg"),
    camera-style names, and alt text equal to the image's file name or stem.
    """
    alt = alt_text.strip()
    lowered = alt.lower()
    if lowered in GENERIC_ALT_TEXT:
        return "generic word"
    if _FILENAME_ALT.match(alt) or _CAMERA_NAME_ALT.match(alt):
        return "file name"
    basename = _src_basename(src)
    if basename:
        stem = os.path.splitext(basename)[0]
        if lowered in (basename.lower(), stem.lower()):
            return "same as image file name"
    return ""


def _decorative_marker(img) -> str:
    """The attribute marking an image as decorative/hidden, or ""."""
    role = (img.get("role") or "").strip().lower()
    if role in ("presentation", "none"):
        return f'role="{role}"'
    if (img.get("aria-hidden") or "").strip().lower() == "true":
        return 'aria-hidden="true"'
    return ""


class AltTextCheck(AccessibilityCheck):
    """Check for proper alt text on images (WCAG 1.1.1)."""

    def check(self) -> None:
        """
        Check if images have appropriate alt text.

        Issues:
            - missing-alt-text: When an image has no alt attribute and is not
              hidden with role="presentation"/"none" or aria-hidden="true"
            - generic-alt-text: When the alt text is a generic word ("image",
              "chart"), a file name ("IMG_1234.jpg"), or the image's file name
            - compliant-decorative-image: alt="" (the decorative marker), or a
              hidden image without alt
            - compliant-alt-text: When an image has proper alt text
        """
        images = self.soup.find_all("img")

        if not images:
            return  # No images to check

        for img in images:
            decorative_marker = _decorative_marker(img)
            if not img.has_attr("alt"):
                if decorative_marker:
                    # role="presentation"/"none" or aria-hidden="true" removes
                    # the image from the accessibility tree, which is how axe
                    # and other checkers treat it too.
                    self.add_issue(
                        "compliant-decorative-image",
                        "1.1.1",
                        "info",
                        element=img,
                        description=(
                            f"Decorative image hidden from assistive technology "
                            f"({decorative_marker})"
                        ),
                        status="compliant",
                    )
                    continue
                self.add_issue(
                    "missing-alt-text",
                    "1.1.1",
                    "critical",
                    element=img,
                    description="Image missing alt text",
                    status="needs_remediation",
                )
                continue

            alt_text = img["alt"].strip()
            if not alt_text:
                # alt="" is the standard way to mark an image as decorative
                # (WCAG technique H67); no extra role is required.
                self.add_issue(
                    "compliant-decorative-image",
                    "1.1.1",
                    "info",
                    element=img,
                    description='Decorative image marked with alt=""',
                    status="compliant",
                )
                continue

            reason = generic_alt_reason(alt_text, img.get("src", ""))
            if reason:
                self.add_issue(
                    "generic-alt-text",
                    "1.1.1",
                    "major",
                    element=img,
                    description=f"Image has generic alt text: '{alt_text}' ({reason})",
                    status="needs_remediation",
                )
            else:
                # Image has non-empty, non-generic alt text
                self.add_issue(
                    "compliant-alt-text",
                    "1.1.1",
                    "info",
                    element=img,
                    description="Image has proper alt text",
                    status="compliant",
                )


class FigureStructureCheck(AccessibilityCheck):
    """Check for proper figure structure (WCAG 1.1.1)."""

    def check(self) -> None:
        """
        Check if figures have proper structure and captions.

        Issues:
            - missing-figure-caption: When a figure has no caption
            - empty-figure-caption: When a figure has an empty caption
            - compliant-figure-structure: When a figure has proper structure
        """
        figures = self.soup.find_all("figure")

        if not figures:
            return  # No figures to check

        for figure in figures:
            caption = figure.find("figcaption")

            if not caption:
                self.add_issue(
                    "missing-figure-caption",
                    "1.1.1",
                    "major",
                    element=figure,
                    description="Figure missing caption",
                    status="needs_remediation",
                )
            else:
                caption_text = self.get_element_text(caption)
                if not caption_text:
                    self.add_issue(
                        "empty-figure-caption",
                        "1.1.1",
                        "major",
                        element=figure,
                        description="Figure has empty caption",
                        status="needs_remediation",
                    )
                else:
                    # Figure has proper structure and non-empty caption
                    self.add_issue(
                        "compliant-figure-structure",
                        "1.1.1",
                        "major",
                        element=figure,
                        description="Figure has proper structure and caption",
                        status="compliant",
                    )
