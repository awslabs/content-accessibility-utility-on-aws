# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
WCAG 2.1 standards and criteria information.

This module provides comprehensive information about WCAG 2.1 success criteria,
including support for filtering by conformance level (A, AA, AAA).
"""

from typing import Dict

# Severity levels (higher number = more severe)
SEVERITY_LEVELS = {
    "minor": 1,
    "major": 2,
    "critical": 3,
    "compliant": 0,  # Special case for compliant issues
}

# WCAG conformance levels with numeric ranking
WCAG_LEVELS = {
    "A": 1,
    "AA": 2,
    "AAA": 3,
}

# WCAG 2.1 criteria information (all 78 success criteria)
WCAG_CRITERIA = {
    # Principle 1: Perceivable
    # Guideline 1.1: Text Alternatives
    "1.1.1": {
        "name": "Non-text Content",
        "level": "A",
        "description": "All non-text content that is presented to the user has a text alternative that serves the equivalent purpose.",
        "principle": "Perceivable",
        "guideline": "1.1 Text Alternatives",
    },

    # Guideline 1.2: Time-based Media
    "1.2.1": {
        "name": "Audio-only and Video-only (Prerecorded)",
        "level": "A",
        "description": "For prerecorded audio-only and prerecorded video-only media, alternatives are provided.",
        "principle": "Perceivable",
        "guideline": "1.2 Time-based Media",
    },
    "1.2.2": {
        "name": "Captions (Prerecorded)",
        "level": "A",
        "description": "Captions are provided for all prerecorded audio content in synchronized media.",
        "principle": "Perceivable",
        "guideline": "1.2 Time-based Media",
    },
    "1.2.3": {
        "name": "Audio Description or Media Alternative (Prerecorded)",
        "level": "A",
        "description": "An alternative for time-based media or audio description of the prerecorded video content is provided.",
        "principle": "Perceivable",
        "guideline": "1.2 Time-based Media",
    },
    "1.2.4": {
        "name": "Captions (Live)",
        "level": "AA",
        "description": "Captions are provided for all live audio content in synchronized media.",
        "principle": "Perceivable",
        "guideline": "1.2 Time-based Media",
    },
    "1.2.5": {
        "name": "Audio Description (Prerecorded)",
        "level": "AA",
        "description": "Audio description is provided for all prerecorded video content in synchronized media.",
        "principle": "Perceivable",
        "guideline": "1.2 Time-based Media",
    },
    "1.2.6": {
        "name": "Sign Language (Prerecorded)",
        "level": "AAA",
        "description": "Sign language interpretation is provided for all prerecorded audio content in synchronized media.",
        "principle": "Perceivable",
        "guideline": "1.2 Time-based Media",
    },
    "1.2.7": {
        "name": "Extended Audio Description (Prerecorded)",
        "level": "AAA",
        "description": "Extended audio description is provided for all prerecorded video content in synchronized media.",
        "principle": "Perceivable",
        "guideline": "1.2 Time-based Media",
    },
    "1.2.8": {
        "name": "Media Alternative (Prerecorded)",
        "level": "AAA",
        "description": "An alternative for time-based media is provided for all prerecorded synchronized media and all prerecorded video-only media.",
        "principle": "Perceivable",
        "guideline": "1.2 Time-based Media",
    },
    "1.2.9": {
        "name": "Audio-only (Live)",
        "level": "AAA",
        "description": "An alternative for time-based media that presents equivalent information for live audio-only content is provided.",
        "principle": "Perceivable",
        "guideline": "1.2 Time-based Media",
    },

    # Guideline 1.3: Adaptable
    "1.3.1": {
        "name": "Info and Relationships",
        "level": "A",
        "description": "Information, structure, and relationships conveyed through presentation can be programmatically determined.",
        "principle": "Perceivable",
        "guideline": "1.3 Adaptable",
    },
    "1.3.2": {
        "name": "Meaningful Sequence",
        "level": "A",
        "description": "When the sequence in which content is presented affects its meaning, a correct reading sequence can be programmatically determined.",
        "principle": "Perceivable",
        "guideline": "1.3 Adaptable",
    },
    "1.3.3": {
        "name": "Sensory Characteristics",
        "level": "A",
        "description": "Instructions provided for understanding and operating content do not rely solely on sensory characteristics.",
        "principle": "Perceivable",
        "guideline": "1.3 Adaptable",
    },
    "1.3.4": {
        "name": "Orientation",
        "level": "AA",
        "description": "Content does not restrict its view and operation to a single display orientation unless essential.",
        "principle": "Perceivable",
        "guideline": "1.3 Adaptable",
    },
    "1.3.5": {
        "name": "Identify Input Purpose",
        "level": "AA",
        "description": "The purpose of each input field collecting information about the user can be programmatically determined.",
        "principle": "Perceivable",
        "guideline": "1.3 Adaptable",
    },
    "1.3.6": {
        "name": "Identify Purpose",
        "level": "AAA",
        "description": "The purpose of User Interface components, icons, and regions can be programmatically determined.",
        "principle": "Perceivable",
        "guideline": "1.3 Adaptable",
    },

    # Guideline 1.4: Distinguishable
    "1.4.1": {
        "name": "Use of Color",
        "level": "A",
        "description": "Color is not used as the only visual means of conveying information.",
        "principle": "Perceivable",
        "guideline": "1.4 Distinguishable",
    },
    "1.4.2": {
        "name": "Audio Control",
        "level": "A",
        "description": "A mechanism is available to pause or stop audio that plays automatically for more than 3 seconds.",
        "principle": "Perceivable",
        "guideline": "1.4 Distinguishable",
    },
    "1.4.3": {
        "name": "Contrast (Minimum)",
        "level": "AA",
        "description": "The visual presentation of text and images of text has a contrast ratio of at least 4.5:1.",
        "principle": "Perceivable",
        "guideline": "1.4 Distinguishable",
    },
    "1.4.4": {
        "name": "Resize Text",
        "level": "AA",
        "description": "Text can be resized without assistive technology up to 200 percent without loss of content or functionality.",
        "principle": "Perceivable",
        "guideline": "1.4 Distinguishable",
    },
    "1.4.5": {
        "name": "Images of Text",
        "level": "AA",
        "description": "If the technologies being used can achieve the visual presentation, text is used to convey information rather than images of text.",
        "principle": "Perceivable",
        "guideline": "1.4 Distinguishable",
    },
    "1.4.6": {
        "name": "Contrast (Enhanced)",
        "level": "AAA",
        "description": "The visual presentation of text and images of text has a contrast ratio of at least 7:1.",
        "principle": "Perceivable",
        "guideline": "1.4 Distinguishable",
    },
    "1.4.7": {
        "name": "Low or No Background Audio",
        "level": "AAA",
        "description": "For prerecorded audio-only content that contains primarily speech, the background sounds are minimized.",
        "principle": "Perceivable",
        "guideline": "1.4 Distinguishable",
    },
    "1.4.8": {
        "name": "Visual Presentation",
        "level": "AAA",
        "description": "For the visual presentation of blocks of text, specific formatting options are available.",
        "principle": "Perceivable",
        "guideline": "1.4 Distinguishable",
    },
    "1.4.9": {
        "name": "Images of Text (No Exception)",
        "level": "AAA",
        "description": "Images of text are only used for pure decoration or where a particular presentation of text is essential.",
        "principle": "Perceivable",
        "guideline": "1.4 Distinguishable",
    },
    "1.4.10": {
        "name": "Reflow",
        "level": "AA",
        "description": "Content can be presented without loss of information or functionality, and without requiring scrolling in two dimensions.",
        "principle": "Perceivable",
        "guideline": "1.4 Distinguishable",
    },
    "1.4.11": {
        "name": "Non-text Contrast",
        "level": "AA",
        "description": "The visual presentation of UI components and graphical objects has a contrast ratio of at least 3:1.",
        "principle": "Perceivable",
        "guideline": "1.4 Distinguishable",
    },
    "1.4.12": {
        "name": "Text Spacing",
        "level": "AA",
        "description": "No loss of content or functionality occurs when text spacing is adjusted.",
        "principle": "Perceivable",
        "guideline": "1.4 Distinguishable",
    },
    "1.4.13": {
        "name": "Content on Hover or Focus",
        "level": "AA",
        "description": "Content that appears on hover or focus is dismissible, hoverable, and persistent.",
        "principle": "Perceivable",
        "guideline": "1.4 Distinguishable",
    },

    # Principle 2: Operable
    # Guideline 2.1: Keyboard Accessible
    "2.1.1": {
        "name": "Keyboard",
        "level": "A",
        "description": "All functionality is operable through a keyboard interface.",
        "principle": "Operable",
        "guideline": "2.1 Keyboard Accessible",
    },
    "2.1.2": {
        "name": "No Keyboard Trap",
        "level": "A",
        "description": "If keyboard focus can be moved to a component, then focus can be moved away using only a keyboard interface.",
        "principle": "Operable",
        "guideline": "2.1 Keyboard Accessible",
    },
    "2.1.3": {
        "name": "Keyboard (No Exception)",
        "level": "AAA",
        "description": "All functionality of the content is operable through a keyboard interface without requiring specific timings.",
        "principle": "Operable",
        "guideline": "2.1 Keyboard Accessible",
    },
    "2.1.4": {
        "name": "Character Key Shortcuts",
        "level": "A",
        "description": "If a keyboard shortcut is implemented using only letter, punctuation, number, or symbol characters, it can be turned off or remapped.",
        "principle": "Operable",
        "guideline": "2.1 Keyboard Accessible",
    },

    # Guideline 2.2: Enough Time
    "2.2.1": {
        "name": "Timing Adjustable",
        "level": "A",
        "description": "For each time limit set by the content, user can turn off, adjust, or extend the time limit.",
        "principle": "Operable",
        "guideline": "2.2 Enough Time",
    },
    "2.2.2": {
        "name": "Pause, Stop, Hide",
        "level": "A",
        "description": "For moving, blinking, scrolling, or auto-updating information, the user can pause, stop, or hide it.",
        "principle": "Operable",
        "guideline": "2.2 Enough Time",
    },
    "2.2.3": {
        "name": "No Timing",
        "level": "AAA",
        "description": "Timing is not an essential part of the event or activity except for non-interactive synchronized media.",
        "principle": "Operable",
        "guideline": "2.2 Enough Time",
    },
    "2.2.4": {
        "name": "Interruptions",
        "level": "AAA",
        "description": "Interruptions can be postponed or suppressed by the user, except for emergencies.",
        "principle": "Operable",
        "guideline": "2.2 Enough Time",
    },
    "2.2.5": {
        "name": "Re-authenticating",
        "level": "AAA",
        "description": "When an authenticated session expires, the user can continue the activity without loss of data after re-authenticating.",
        "principle": "Operable",
        "guideline": "2.2 Enough Time",
    },
    "2.2.6": {
        "name": "Timeouts",
        "level": "AAA",
        "description": "Users are warned of the duration of any user inactivity that could cause data loss, unless data is preserved.",
        "principle": "Operable",
        "guideline": "2.2 Enough Time",
    },

    # Guideline 2.3: Seizures and Physical Reactions
    "2.3.1": {
        "name": "Three Flashes or Below Threshold",
        "level": "A",
        "description": "Content does not contain anything that flashes more than three times in any one second period.",
        "principle": "Operable",
        "guideline": "2.3 Seizures and Physical Reactions",
    },
    "2.3.2": {
        "name": "Three Flashes",
        "level": "AAA",
        "description": "Content does not contain anything that flashes more than three times in any one second period.",
        "principle": "Operable",
        "guideline": "2.3 Seizures and Physical Reactions",
    },
    "2.3.3": {
        "name": "Animation from Interactions",
        "level": "AAA",
        "description": "Motion animation triggered by interaction can be disabled, unless the animation is essential.",
        "principle": "Operable",
        "guideline": "2.3 Seizures and Physical Reactions",
    },

    # Guideline 2.4: Navigable
    "2.4.1": {
        "name": "Bypass Blocks",
        "level": "A",
        "description": "A mechanism is available to bypass blocks of content that are repeated on multiple Web pages.",
        "principle": "Operable",
        "guideline": "2.4 Navigable",
    },
    "2.4.2": {
        "name": "Page Titled",
        "level": "A",
        "description": "Web pages have titles that describe topic or purpose.",
        "principle": "Operable",
        "guideline": "2.4 Navigable",
    },
    "2.4.3": {
        "name": "Focus Order",
        "level": "A",
        "description": "If a Web page can be navigated sequentially, components receive focus in an order that preserves meaning.",
        "principle": "Operable",
        "guideline": "2.4 Navigable",
    },
    "2.4.4": {
        "name": "Link Purpose (In Context)",
        "level": "A",
        "description": "The purpose of each link can be determined from the link text alone or from the link text together with its programmatically determined link context.",
        "principle": "Operable",
        "guideline": "2.4 Navigable",
    },
    "2.4.5": {
        "name": "Multiple Ways",
        "level": "AA",
        "description": "More than one way is available to locate a Web page within a set of Web pages.",
        "principle": "Operable",
        "guideline": "2.4 Navigable",
    },
    "2.4.6": {
        "name": "Headings and Labels",
        "level": "AA",
        "description": "Headings and labels describe topic or purpose.",
        "principle": "Operable",
        "guideline": "2.4 Navigable",
    },
    "2.4.7": {
        "name": "Focus Visible",
        "level": "AA",
        "description": "Any keyboard operable user interface has a mode of operation where the keyboard focus indicator is visible.",
        "principle": "Operable",
        "guideline": "2.4 Navigable",
    },
    "2.4.8": {
        "name": "Location",
        "level": "AAA",
        "description": "Information about the user's location within a set of Web pages is available.",
        "principle": "Operable",
        "guideline": "2.4 Navigable",
    },
    "2.4.9": {
        "name": "Link Purpose (Link Only)",
        "level": "AAA",
        "description": "A mechanism is available to allow the purpose of each link to be identified from link text alone.",
        "principle": "Operable",
        "guideline": "2.4 Navigable",
    },
    "2.4.10": {
        "name": "Section Headings",
        "level": "AAA",
        "description": "Section headings are used to organize the content.",
        "principle": "Operable",
        "guideline": "2.4 Navigable",
    },

    # Guideline 2.5: Input Modalities
    "2.5.1": {
        "name": "Pointer Gestures",
        "level": "A",
        "description": "All functionality that uses multipoint or path-based gestures can be operated with a single pointer.",
        "principle": "Operable",
        "guideline": "2.5 Input Modalities",
    },
    "2.5.2": {
        "name": "Pointer Cancellation",
        "level": "A",
        "description": "For functionality operated using a single pointer, at least one mechanism is available to cancel or abort the operation.",
        "principle": "Operable",
        "guideline": "2.5 Input Modalities",
    },
    "2.5.3": {
        "name": "Label in Name",
        "level": "A",
        "description": "For user interface components with labels that include text or images of text, the name contains the text that is presented visually.",
        "principle": "Operable",
        "guideline": "2.5 Input Modalities",
    },
    "2.5.4": {
        "name": "Motion Actuation",
        "level": "A",
        "description": "Functionality triggered by device motion or user motion can also be operated by user interface components.",
        "principle": "Operable",
        "guideline": "2.5 Input Modalities",
    },
    "2.5.5": {
        "name": "Target Size",
        "level": "AAA",
        "description": "The size of the target for pointer inputs is at least 44 by 44 CSS pixels.",
        "principle": "Operable",
        "guideline": "2.5 Input Modalities",
    },
    "2.5.6": {
        "name": "Concurrent Input Mechanisms",
        "level": "AAA",
        "description": "Content does not restrict use of input modalities available on a platform.",
        "principle": "Operable",
        "guideline": "2.5 Input Modalities",
    },

    # Principle 3: Understandable
    # Guideline 3.1: Readable
    "3.1.1": {
        "name": "Language of Page",
        "level": "A",
        "description": "The default human language of each Web page can be programmatically determined.",
        "principle": "Understandable",
        "guideline": "3.1 Readable",
    },
    "3.1.2": {
        "name": "Language of Parts",
        "level": "AA",
        "description": "The human language of each passage or phrase can be programmatically determined.",
        "principle": "Understandable",
        "guideline": "3.1 Readable",
    },
    "3.1.3": {
        "name": "Unusual Words",
        "level": "AAA",
        "description": "A mechanism is available for identifying specific definitions of words or phrases used in an unusual way.",
        "principle": "Understandable",
        "guideline": "3.1 Readable",
    },
    "3.1.4": {
        "name": "Abbreviations",
        "level": "AAA",
        "description": "A mechanism for identifying the expanded form or meaning of abbreviations is available.",
        "principle": "Understandable",
        "guideline": "3.1 Readable",
    },
    "3.1.5": {
        "name": "Reading Level",
        "level": "AAA",
        "description": "When text requires reading ability more advanced than lower secondary education level, supplemental content is available.",
        "principle": "Understandable",
        "guideline": "3.1 Readable",
    },
    "3.1.6": {
        "name": "Pronunciation",
        "level": "AAA",
        "description": "A mechanism is available for identifying specific pronunciation of words where meaning is ambiguous.",
        "principle": "Understandable",
        "guideline": "3.1 Readable",
    },

    # Guideline 3.2: Predictable
    "3.2.1": {
        "name": "On Focus",
        "level": "A",
        "description": "When any user interface component receives focus, it does not initiate a change of context.",
        "principle": "Understandable",
        "guideline": "3.2 Predictable",
    },
    "3.2.2": {
        "name": "On Input",
        "level": "A",
        "description": "Changing the setting of any user interface component does not automatically cause a change of context.",
        "principle": "Understandable",
        "guideline": "3.2 Predictable",
    },
    "3.2.3": {
        "name": "Consistent Navigation",
        "level": "AA",
        "description": "Navigational mechanisms that are repeated on multiple Web pages occur in the same relative order.",
        "principle": "Understandable",
        "guideline": "3.2 Predictable",
    },
    "3.2.4": {
        "name": "Consistent Identification",
        "level": "AA",
        "description": "Components that have the same functionality within a set of Web pages are identified consistently.",
        "principle": "Understandable",
        "guideline": "3.2 Predictable",
    },
    "3.2.5": {
        "name": "Change on Request",
        "level": "AAA",
        "description": "Changes of context are initiated only by user request or a mechanism is available to turn off such changes.",
        "principle": "Understandable",
        "guideline": "3.2 Predictable",
    },

    # Guideline 3.3: Input Assistance
    "3.3.1": {
        "name": "Error Identification",
        "level": "A",
        "description": "If an input error is automatically detected, the item that is in error is identified and described in text.",
        "principle": "Understandable",
        "guideline": "3.3 Input Assistance",
    },
    "3.3.2": {
        "name": "Labels or Instructions",
        "level": "A",
        "description": "Labels or instructions are provided when content requires user input.",
        "principle": "Understandable",
        "guideline": "3.3 Input Assistance",
    },
    "3.3.3": {
        "name": "Error Suggestion",
        "level": "AA",
        "description": "If an input error is automatically detected and suggestions are known, then suggestions are provided.",
        "principle": "Understandable",
        "guideline": "3.3 Input Assistance",
    },
    "3.3.4": {
        "name": "Error Prevention (Legal, Financial, Data)",
        "level": "AA",
        "description": "For Web pages that cause legal commitments or financial transactions, submissions are reversible, checked, or confirmed.",
        "principle": "Understandable",
        "guideline": "3.3 Input Assistance",
    },
    "3.3.5": {
        "name": "Help",
        "level": "AAA",
        "description": "Context-sensitive help is available.",
        "principle": "Understandable",
        "guideline": "3.3 Input Assistance",
    },
    "3.3.6": {
        "name": "Error Prevention (All)",
        "level": "AAA",
        "description": "For all Web pages that require user submitted information, submissions are reversible, checked, or confirmed.",
        "principle": "Understandable",
        "guideline": "3.3 Input Assistance",
    },

    # Principle 4: Robust
    # Guideline 4.1: Compatible
    "4.1.1": {
        "name": "Parsing",
        "level": "A",
        "description": "In content implemented using markup languages, elements have complete start and end tags.",
        "principle": "Robust",
        "guideline": "4.1 Compatible",
    },
    "4.1.2": {
        "name": "Name, Role, Value",
        "level": "A",
        "description": "For all user interface components, the name and role can be programmatically determined.",
        "principle": "Robust",
        "guideline": "4.1 Compatible",
    },
    "4.1.3": {
        "name": "Status Messages",
        "level": "AA",
        "description": "Status messages can be programmatically determined through role or properties so they can be presented without receiving focus.",
        "principle": "Robust",
        "guideline": "4.1 Compatible",
    },
}


def get_criterion_info(criterion_id: str) -> dict:
    """
    Get information about a WCAG criterion.

    Args:
        criterion_id: WCAG criterion ID (e.g., '1.1.1')

    Returns:
        Dictionary with criterion information
    """
    return WCAG_CRITERIA.get(
        criterion_id,
        {
            "name": "Unknown Criterion",
            "level": "Unknown",
            "description": "No description available",
            "principle": "Unknown",
            "guideline": "Unknown",
        },
    )


def get_criteria_for_level(target_level: str = "AA") -> Dict[str, dict]:
    """
    Get all WCAG criteria at or below the specified conformance level.

    Args:
        target_level: Target conformance level ("A", "AA", or "AAA")

    Returns:
        Dictionary of criteria that match the level requirements
    """
    max_level_value = WCAG_LEVELS.get(target_level.upper(), 2)  # Default to AA

    return {
        criterion_id: info
        for criterion_id, info in WCAG_CRITERIA.items()
        if WCAG_LEVELS.get(info["level"], 1) <= max_level_value
    }


def get_criteria_by_level(level: str) -> Dict[str, dict]:
    """
    Get all WCAG criteria at exactly the specified level.

    Args:
        level: Conformance level ("A", "AA", or "AAA")

    Returns:
        Dictionary of criteria at exactly that level
    """
    return {
        criterion_id: info
        for criterion_id, info in WCAG_CRITERIA.items()
        if info["level"] == level.upper()
    }


def get_criteria_by_principle(principle: str) -> Dict[str, dict]:
    """
    Get all WCAG criteria for a specific principle.

    Args:
        principle: WCAG principle ("Perceivable", "Operable", "Understandable", "Robust")

    Returns:
        Dictionary of criteria for that principle
    """
    return {
        criterion_id: info
        for criterion_id, info in WCAG_CRITERIA.items()
        if info.get("principle", "").lower() == principle.lower()
    }


def get_criteria_by_guideline(guideline: str) -> Dict[str, dict]:
    """
    Get all WCAG criteria for a specific guideline.

    Args:
        guideline: WCAG guideline (e.g., "1.1 Text Alternatives")

    Returns:
        Dictionary of criteria for that guideline
    """
    return {
        criterion_id: info
        for criterion_id, info in WCAG_CRITERIA.items()
        if guideline.lower() in info.get("guideline", "").lower()
    }


def get_level_summary() -> Dict[str, int]:
    """
    Get a summary of criteria counts by level.

    Returns:
        Dictionary with counts for each level
    """
    summary = {"A": 0, "AA": 0, "AAA": 0}
    for info in WCAG_CRITERIA.values():
        level = info.get("level", "A")
        if level in summary:
            summary[level] += 1
    return summary
