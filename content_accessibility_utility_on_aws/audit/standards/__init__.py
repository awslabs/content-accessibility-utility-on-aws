# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
HTML Accessibility Standards.

This module provides constants and utilities for working with WCAG 2.1 and 2.2 accessibility standards.
"""

# Define severity levels for accessibility issues
# Higher value = more severe
SEVERITY_LEVELS = {
    "critical": 3,  # Must be fixed - causes accessibility barriers
    "major": 2,  # Should be fixed - significant accessibility issues
    "minor": 1,  # Good to fix - minor accessibility improvements
    "info": 0,  # Informational only - not necessarily an issue
}

# Define severity impact matrix for better classification
SEVERITY_MATRIX = {
    "critical": {
        "impact": "Prevents access",
        "scope": "Affects all users",
        "frequency": "Occurs on every page",
    },
    "major": {
        "impact": "Significantly hinders access",
        "scope": "Affects specific user groups",
        "frequency": "Occurs frequently",
    },
    "minor": {
        "impact": "Causes inconvenience",
        "scope": "Affects few users",
        "frequency": "Occurs occasionally",
    },
    "info": {
        "impact": "Informational only",
        "scope": "Best practice",
        "frequency": "Not an accessibility barrier",
    },
}

# WCAG 2.1 Success Criteria
WCAG_CRITERIA = {
    # Perceivable
    "1.1.1": {"name": "Non-text Content", "level": "A"},
    "1.2.1": {"name": "Audio-only and Video-only (Prerecorded)", "level": "A"},
    "1.2.2": {"name": "Captions (Prerecorded)", "level": "A"},
    "1.2.3": {"name": "Audio Description or Media Alternative", "level": "A"},
    "1.2.4": {"name": "Captions (Live)", "level": "AA"},
    "1.2.5": {"name": "Audio Description", "level": "AA"},
    "1.2.6": {"name": "Sign Language", "level": "AAA"},
    "1.2.7": {"name": "Extended Audio Description", "level": "AAA"},
    "1.2.8": {"name": "Media Alternative", "level": "AAA"},
    "1.2.9": {"name": "Audio-only (Live)", "level": "AAA"},
    "1.3.1": {"name": "Info and Relationships", "level": "A"},
    "1.3.2": {"name": "Meaningful Sequence", "level": "A"},
    "1.3.3": {"name": "Sensory Characteristics", "level": "A"},
    "1.3.4": {"name": "Orientation", "level": "AA"},
    "1.3.5": {"name": "Identify Input Purpose", "level": "AA"},
    "1.3.6": {"name": "Identify Purpose", "level": "AAA"},
    "1.4.1": {"name": "Use of Color", "level": "A"},
    "1.4.2": {"name": "Audio Control", "level": "A"},
    "1.4.3": {"name": "Contrast (Minimum)", "level": "AA"},
    "1.4.4": {"name": "Resize Text", "level": "AA"},
    "1.4.5": {"name": "Images of Text", "level": "AA"},
    "1.4.6": {"name": "Contrast (Enhanced)", "level": "AAA"},
    "1.4.7": {"name": "Low or No Background Audio", "level": "AAA"},
    "1.4.8": {"name": "Visual Presentation", "level": "AAA"},
    "1.4.9": {"name": "Images of Text (No Exception)", "level": "AAA"},
    "1.4.10": {"name": "Reflow", "level": "AA"},
    "1.4.11": {"name": "Non-text Contrast", "level": "AA"},
    "1.4.12": {"name": "Text Spacing", "level": "AA"},
    "1.4.13": {"name": "Content on Hover or Focus", "level": "AA"},
    # Operable
    "2.1.1": {"name": "Keyboard", "level": "A"},
    "2.1.2": {"name": "No Keyboard Trap", "level": "A"},
    "2.1.3": {"name": "Keyboard (No Exception)", "level": "AAA"},
    "2.1.4": {"name": "Character Key Shortcuts", "level": "A"},
    "2.2.1": {"name": "Timing Adjustable", "level": "A"},
    "2.2.2": {"name": "Pause, Stop, Hide", "level": "A"},
    "2.2.3": {"name": "No Timing", "level": "AAA"},
    "2.2.4": {"name": "Interruptions", "level": "AAA"},
    "2.2.5": {"name": "Re-authenticating", "level": "AAA"},
    "2.2.6": {"name": "Timeouts", "level": "AAA"},
    "2.3.1": {"name": "Three Flashes or Below Threshold", "level": "A"},
    "2.3.2": {"name": "Three Flashes", "level": "AAA"},
    "2.3.3": {"name": "Animation from Interactions", "level": "AAA"},
    "2.4.1": {"name": "Bypass Blocks", "level": "A"},
    "2.4.2": {"name": "Page Titled", "level": "A"},
    "2.4.3": {"name": "Focus Order", "level": "A"},
    "2.4.4": {"name": "Link Purpose (In Context)", "level": "A"},
    "2.4.5": {"name": "Multiple Ways", "level": "AA"},
    "2.4.6": {"name": "Headings and Labels", "level": "AA"},
    "2.4.7": {"name": "Focus Visible", "level": "AA"},
    "2.4.8": {"name": "Location", "level": "AAA"},
    "2.4.9": {"name": "Link Purpose (Link Only)", "level": "AAA"},
    "2.4.10": {"name": "Section Headings", "level": "AAA"},
    "2.4.11": {"name": "Focus Not Obscured (Minimum)", "level": "AA"},  # WCAG 2.2
    "2.4.12": {"name": "Focus Not Obscured (Enhanced)", "level": "AAA"},  # WCAG 2.2
    "2.4.13": {"name": "Focus Appearance", "level": "AAA"},  # WCAG 2.2
    "2.5.1": {"name": "Pointer Gestures", "level": "A"},
    "2.5.2": {"name": "Pointer Cancellation", "level": "A"},
    "2.5.3": {"name": "Label in Name", "level": "A"},
    "2.5.4": {"name": "Motion Actuation", "level": "A"},
    "2.5.5": {"name": "Target Size (Enhanced)", "level": "AAA"},
    "2.5.6": {"name": "Concurrent Input Mechanisms", "level": "AAA"},
    "2.5.7": {"name": "Dragging Movements", "level": "AA"},  # WCAG 2.2
    "2.5.8": {"name": "Target Size (Minimum)", "level": "AA"},  # WCAG 2.2
    # Understandable
    "3.1.1": {"name": "Language of Page", "level": "A"},
    "3.1.2": {"name": "Language of Parts", "level": "AA"},
    "3.1.3": {"name": "Unusual Words", "level": "AAA"},
    "3.1.4": {"name": "Abbreviations", "level": "AAA"},
    "3.1.5": {"name": "Reading Level", "level": "AAA"},
    "3.1.6": {"name": "Pronunciation", "level": "AAA"},
    "3.2.1": {"name": "On Focus", "level": "A"},
    "3.2.2": {"name": "On Input", "level": "A"},
    "3.2.3": {"name": "Consistent Navigation", "level": "AA"},
    "3.2.4": {"name": "Consistent Identification", "level": "AA"},
    "3.2.5": {"name": "Change on Request", "level": "AAA"},
    "3.2.6": {"name": "Consistent Help", "level": "A"},  # WCAG 2.2
    "3.3.1": {"name": "Error Identification", "level": "A"},
    "3.3.2": {"name": "Labels or Instructions", "level": "A"},
    "3.3.3": {"name": "Error Suggestion", "level": "AA"},
    "3.3.4": {"name": "Error Prevention (Legal, Financial, Data)", "level": "AA"},
    "3.3.5": {"name": "Help", "level": "AAA"},
    "3.3.6": {"name": "Error Prevention (All)", "level": "AAA"},
    "3.3.7": {"name": "Redundant Entry", "level": "A"},  # WCAG 2.2
    "3.3.8": {"name": "Accessible Authentication (Minimum)", "level": "AA"},  # WCAG 2.2
    "3.3.9": {"name": "Accessible Authentication (Enhanced)", "level": "AAA"},  # WCAG 2.2
    # Robust
    "4.1.1": {"name": "Parsing", "level": "A", "obsolete_in": "2.2"},
    "4.1.2": {"name": "Name, Role, Value", "level": "A"},
    "4.1.3": {"name": "Status Messages", "level": "AA"},
}


# The WCAG version audits target. Override per run with the audit option
# ``wcag_version`` ("2.1" or "2.2").
DEFAULT_WCAG_VERSION = "2.2"
SUPPORTED_WCAG_VERSIONS = ("2.1", "2.2")

# Criteria removed in a WCAG version, mapped to where their remaining
# accessibility impact is assessed. WCAG 2.2 made 4.1.1 Parsing obsolete
# (always satisfied); duplicate ids that break label/ARIA references or
# focusable-element identity are failures of 4.1.2 Name, Role, Value.
OBSOLETE_CRITERIA = {
    "2.2": {"4.1.1": "4.1.2"},
}


def criterion_for_version(criterion_id, wcag_version=None):
    """Return the criterion to report for ``criterion_id`` under a WCAG version.

    Unknown versions fall back to ``DEFAULT_WCAG_VERSION``.
    """
    version = (
        wcag_version if wcag_version in SUPPORTED_WCAG_VERSIONS else DEFAULT_WCAG_VERSION
    )
    return OBSOLETE_CRITERIA.get(version, {}).get(criterion_id, criterion_id)


def relabel_issue_for_version(issue, wcag_version=None):
    """Relabel an issue dict whose criterion is obsolete in ``wcag_version``.

    Updates ``wcag_criterion``, ``criterion_name`` and ``criterion_level`` in
    place and keeps the original id in ``original_wcag_criterion``. Returns
    the issue.
    """
    original = issue.get("wcag_criterion")
    target = criterion_for_version(original, wcag_version)
    if target != original:
        info = get_criterion_info(target)
        issue["original_wcag_criterion"] = original
        issue["wcag_criterion"] = target
        issue["criterion_name"] = info.get("name", "")
        issue["criterion_level"] = info.get("level", "")
    return issue


def get_criterion_info(criterion_id):
    """
    Get information about a specific WCAG criterion.

    Args:
        criterion_id: The WCAG criterion ID (e.g., '1.1.1')

    Returns:
        Dictionary with criterion information, or empty dict if not found.
    """
    return WCAG_CRITERIA.get(criterion_id, {})


# Import issue types
