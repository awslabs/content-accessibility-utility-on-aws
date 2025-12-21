# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Converter factory for creating PDF to HTML converter instances.

This module provides a factory class for instantiating the appropriate
converter based on the requested type.
"""

from typing import Any, Dict, Optional

from content_accessibility_utility_on_aws.pdf2html.converters.base import (
    BaseConverter,
    ConverterType,
)
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)


class ConverterFactory:
    """
    Factory for creating PDF to HTML converter instances.

    This factory provides a centralized way to create converter instances
    based on the requested type, handling all necessary configuration.
    """

    @staticmethod
    def create(
        converter_type: ConverterType,
        **kwargs: Any,
    ) -> BaseConverter:
        """
        Create a converter instance based on the specified type.

        Args:
            converter_type: The type of converter to create.
            **kwargs: Additional arguments passed to the converter constructor.
                For BDA:
                    - project_arn: ARN of the BDA project
                    - create_project: Whether to create a new project
                    - s3_bucket: S3 bucket name
                    - profile: AWS profile name
                For pdf2htmlEX:
                    - docker_image: Docker image to use

        Returns:
            An instance of the requested converter type.

        Raises:
            ValueError: If an unknown converter type is requested.
        """
        if converter_type == ConverterType.BDA:
            # Lazy import to avoid circular dependencies
            from content_accessibility_utility_on_aws.pdf2html.converters.bda_converter import (
                BDAConverter,
            )

            return BDAConverter(
                project_arn=kwargs.get("project_arn"),
                create_project=kwargs.get("create_project", False),
                s3_bucket=kwargs.get("s3_bucket"),
                profile=kwargs.get("profile"),
            )

        elif converter_type == ConverterType.PDF2HTMLEX:
            # Lazy import to avoid circular dependencies
            from content_accessibility_utility_on_aws.pdf2html.converters.pdf2htmlex_converter import (
                Pdf2HtmlExConverter,
            )

            return Pdf2HtmlExConverter(
                docker_image=kwargs.get("docker_image"),
            )

        else:
            raise ValueError(f"Unknown converter type: {converter_type}")

    @staticmethod
    def get_default() -> ConverterType:
        """
        Get the default converter type.

        Returns:
            ConverterType.BDA for backward compatibility.
        """
        return ConverterType.BDA

    @staticmethod
    def from_string(converter_name: str) -> ConverterType:
        """
        Convert a string to a ConverterType enum.

        Args:
            converter_name: String name of the converter ('bda' or 'pdf2htmlex').

        Returns:
            The corresponding ConverterType enum value.

        Raises:
            ValueError: If the converter name is not recognized.
        """
        try:
            return ConverterType(converter_name.lower())
        except ValueError:
            valid_types = [t.value for t in ConverterType]
            raise ValueError(
                f"Unknown converter: '{converter_name}'. "
                f"Valid options are: {', '.join(valid_types)}"
            )

    @staticmethod
    def is_available(converter_type: ConverterType, **kwargs: Any) -> bool:
        """
        Check if a converter type is available.

        Args:
            converter_type: The type of converter to check.
            **kwargs: Additional arguments for availability checking.

        Returns:
            True if the converter is available, False otherwise.
        """
        try:
            converter = ConverterFactory.create(converter_type, **kwargs)
            return converter.is_available()
        except Exception as e:
            logger.debug(f"Converter {converter_type.value} not available: {e}")
            return False
