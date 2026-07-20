# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
HTML content internationalization (i18n).

This optional package translates the accessible HTML produced by the rest of
the utility into one or more target languages using the same Amazon Bedrock
Converse path used for remediation, and can emit a single multilingual HTML
document with a language selector and browser-language auto-detection.

Installed via the optional extra::

    pip install content-accessibility-utility-on-aws[i18n]

The translation itself runs on the core ``boto3``/Bedrock dependencies. The
``[i18n]`` extra adds ``babel`` (language display names and ``Accept-Language``
negotiation) and ``langdetect`` (source-language auto-detection); both degrade
gracefully to built-in fallbacks when absent.
"""

from content_accessibility_utility_on_aws.i18n.api import (
    translate_html_accessibility,
)

__all__ = [
    "translate_html_accessibility",
]
