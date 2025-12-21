# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Base converter abstraction for PDF to HTML conversion.

This module defines the abstract base class and common types for all
PDF to HTML converters.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional


class ConverterType(Enum):
    """Enumeration of available PDF to HTML converter backends."""

    BDA = "bda"
    PDF2HTMLEX = "pdf2htmlex"


@dataclass
class ConversionResult:
    """
    Standardized result structure for all PDF to HTML converters.

    This class provides a consistent interface for conversion results
    regardless of which converter backend is used.
    """

    html_path: str
    """Path to the main HTML file or directory containing HTML files."""

    html_files: List[str] = field(default_factory=list)
    """List of paths to all generated HTML files."""

    image_files: List[str] = field(default_factory=list)
    """List of paths to all extracted/generated image files."""

    is_image_only: bool = False
    """Whether the source PDF contained only images (no extractable text)."""

    temp_dir: Optional[str] = None
    """Path to temporary directory if one was created."""

    result_data: Dict[str, Any] = field(default_factory=dict)
    """
    Additional metadata from the conversion.
    For BDA: Contains element data with bounding boxes and semantic info.
    For pdf2htmlEX: Empty dict (no element metadata available).
    """

    mode: str = "multi-page"
    """Output mode: 'single-page' or 'multi-page'."""

    document_id: Optional[str] = None
    """Unique identifier for the converted document."""

    page_count: int = 0
    """Number of pages in the source PDF."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a dictionary for API compatibility."""
        return {
            "html_path": self.html_path,
            "html_files": self.html_files,
            "image_files": self.image_files,
            "is_image_only": self.is_image_only,
            "temp_dir": self.temp_dir,
            "result_data": self.result_data,
            "mode": self.mode,
            "document_id": self.document_id,
            "page_count": self.page_count,
        }


class BaseConverter(ABC):
    """
    Abstract base class for PDF to HTML converters.

    All converter implementations must inherit from this class and
    implement its abstract methods.
    """

    @abstractmethod
    def convert(
        self,
        pdf_path: str,
        output_dir: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> ConversionResult:
        """
        Convert a PDF document to HTML.

        Args:
            pdf_path: Path to the source PDF file.
            output_dir: Directory to save the converted HTML files.
            options: Converter-specific options dictionary.

        Returns:
            ConversionResult containing paths to generated files and metadata.

        Raises:
            FileNotFoundError: If the PDF file doesn't exist.
            DocumentAccessibilityError: If conversion fails.
        """
        pass

    @abstractmethod
    def validate_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize converter-specific options.

        Args:
            options: Raw options dictionary from user input.

        Returns:
            Validated and normalized options dictionary with defaults applied.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this converter is available and properly configured.

        Returns:
            True if the converter can be used, False otherwise.
        """
        pass

    @property
    @abstractmethod
    def converter_type(self) -> ConverterType:
        """Return the type of this converter."""
        pass

    @property
    def name(self) -> str:
        """Return a human-readable name for this converter."""
        return self.converter_type.value
