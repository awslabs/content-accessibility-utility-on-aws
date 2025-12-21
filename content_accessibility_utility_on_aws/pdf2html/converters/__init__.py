# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
PDF to HTML converters module.

This module provides multiple backends for converting PDF documents to HTML,
including Bedrock Data Automation (BDA) and pdf2htmlEX.
"""

from content_accessibility_utility_on_aws.pdf2html.converters.base import (
    BaseConverter,
    ConversionResult,
    ConverterType,
)
from content_accessibility_utility_on_aws.pdf2html.converters.factory import (
    ConverterFactory,
)

__all__ = [
    "BaseConverter",
    "ConversionResult",
    "ConverterType",
    "ConverterFactory",
]
