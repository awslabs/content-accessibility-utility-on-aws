# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
BDA (Bedrock Data Automation) converter implementation.

This module provides the BDA-based PDF to HTML converter, wrapping the
ExtendedBDAClient for use with the converter abstraction.
"""

import os
import shutil
from typing import Dict, Any, Optional

from content_accessibility_utility_on_aws.pdf2html.converters.base import (
    BaseConverter,
    ConversionResult,
    ConverterType,
)
from content_accessibility_utility_on_aws.pdf2html.services.bedrock_client import (
    ExtendedBDAClient,
    resolve_bda_project,
)
from content_accessibility_utility_on_aws.pdf2html.utils.pdf_utils import is_image_only_pdf
from content_accessibility_utility_on_aws.utils.logging_helper import (
    setup_logger,
    PDFConversionError,
)
from content_accessibility_utility_on_aws.utils.resources import ensure_directory

logger = setup_logger(__name__)


class BDAConverter(BaseConverter):
    """
    PDF to HTML converter using Amazon Bedrock Data Automation.

    This converter uses AWS Bedrock Data Automation service to convert
    PDFs to HTML with rich semantic information and element metadata.
    """

    def __init__(
        self,
        project_arn: Optional[str] = None,
        create_project: bool = False,
        s3_bucket: Optional[str] = None,
        profile: Optional[str] = None,
    ):
        """
        Initialize the BDA converter.

        Args:
            project_arn: ARN of an existing BDA project to use.
            create_project: Whether to create a new BDA project if needed.
            s3_bucket: Name of an existing S3 bucket to use.
            profile: AWS profile name for authentication.
        """
        self._project_arn = project_arn
        self._create_project = create_project
        self._s3_bucket = s3_bucket
        self._profile = profile
        self._client: Optional[ExtendedBDAClient] = None

    @property
    def converter_type(self) -> ConverterType:
        """Return the type of this converter."""
        return ConverterType.BDA

    def is_available(self) -> bool:
        """
        Check if BDA converter is available.

        Returns:
            True if AWS credentials are configured and BDA is accessible.
        """
        try:
            import boto3

            session = (
                boto3.Session(profile_name=self._profile)
                if self._profile
                else boto3.Session()
            )
            sts_client = session.client("sts")
            sts_client.get_caller_identity()
            return True
        except Exception as e:
            logger.debug(f"BDA converter not available: {e}")
            return False

    def validate_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize BDA-specific options.

        Args:
            options: Raw options dictionary.

        Returns:
            Validated options with defaults applied.
        """
        default_options = {
            "extract_images": True,
            "image_format": "png",
            "embed_fonts": False,
            "single_html": False,
            "page_range": None,
            "single_file": False,
            "multiple_documents": False,
            "continuous": True,
            "inline_css": False,
            "embed_images": False,
            "exclude_images": False,
            "bda_project_name": None,
            "bda_profile_name": None,
            "audit_accessibility": False,
            "audit_options": {},
            "cleanup_bda_output": False,
            "create_bda_project": self._create_project,
            "profile": self._profile,
        }

        if options:
            default_options.update(options)

        return default_options

    def convert(
        self,
        pdf_path: str,
        output_dir: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> ConversionResult:
        """
        Convert a PDF to HTML using Bedrock Data Automation.

        Args:
            pdf_path: Path to the source PDF file.
            output_dir: Directory to save the converted HTML files.
            options: Conversion options.

        Returns:
            ConversionResult with paths to generated files and metadata.

        Raises:
            FileNotFoundError: If the PDF file doesn't exist.
            PDFConversionError: If conversion fails.
        """
        # Validate PDF exists
        if not os.path.isfile(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Validate and apply default options
        options = self.validate_options(options or {})

        # Check if PDF is image-only
        is_image_only = is_image_only_pdf(pdf_path)
        if is_image_only:
            logger.warning("PDF appears to be image-only. BDA will handle appropriately.")

        # Ensure output directory exists
        ensure_directory(output_dir)

        try:
            # Resolve BDA project
            project_arn = resolve_bda_project(
                cli_arg=self._project_arn,
                create_new=options.get("create_bda_project", self._create_project),
                project_name=options.get("bda_project_name"),
                profile=self._profile,
            )

            # Get the BDA profile ARN
            profile_arn = os.getenv("BDA_PROFILE_ARN")
            if not profile_arn:
                logger.debug(f"Getting standard BDA profile using AWS profile: {self._profile}")
                bda_client = ExtendedBDAClient(project_arn, profile=self._profile)
                profile_arn = bda_client.get_profile()

            # Initialize the BDA client
            bda_client = ExtendedBDAClient(project_arn, profile=self._profile)

            # Set up S3 bucket
            if options.get("create_bda_project", self._create_project):
                bda_client.set_s3_bucket(create_new=True)
            else:
                bda_client.set_s3_bucket(self._s3_bucket, create_new=False)

            logger.debug(f"Processing PDF with Bedrock Data Automation: {pdf_path}")

            # Set environment variables for output format control
            self._set_output_mode_env_vars(options)

            # Process PDF through BDA
            result = bda_client.process_and_retrieve(pdf_path, output_dir, options)

            # Clean up files based on mode
            self._cleanup_output_files(
                output_dir=output_dir,
                single_file=options.get("single_file", False),
                multiple_documents=options.get("multiple_documents", False),
            )

            # Update HTML files list based on mode
            html_dir = os.path.join(output_dir, "extracted_html")
            html_path, html_files, mode = self._finalize_html_paths(
                result, html_dir, options
            )

            # Copy images to extracted_html directory
            copied_images = self._copy_images_to_html_dir(
                output_dir, result.get("image_files")
            )

            return ConversionResult(
                html_path=html_path,
                html_files=html_files,
                image_files=result.get("image_files", []),
                is_image_only=is_image_only,
                result_data=result.get("result_data", {}),
                mode=mode,
                document_id=result.get("document_id"),
                page_count=result.get("page_count", 0),
            )

        except FileNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error converting PDF with BDA: {e}")
            raise PDFConversionError(f"BDA conversion failed: {e}") from e

    def _set_output_mode_env_vars(self, options: Dict[str, Any]) -> None:
        """Set environment variables to control BDA output format."""
        is_multi_page = options.get("multiple_documents", False) or options.get(
            "multi_page", False
        )
        is_single_page = options.get("single_file", False) or options.get(
            "single_page", False
        )

        if is_multi_page:
            logger.debug("Setting multi-page mode (multiple individual HTML files)")
            os.environ["PDF2HTML_SINGLE_FILE"] = "false"
            os.environ["PDF2HTML_MULTIPLE_DOCUMENTS"] = "true"
            options["single_file"] = False
            options["multiple_documents"] = True
        elif is_single_page:
            logger.debug("Setting single-page mode (one combined HTML file)")
            os.environ["PDF2HTML_SINGLE_FILE"] = "true"
            os.environ["PDF2HTML_MULTIPLE_DOCUMENTS"] = "false"
            options["single_file"] = True
            options["multiple_documents"] = False
        else:
            # Default to multi-page
            logger.debug("Defaulting to multi-page mode (multiple individual HTML files)")
            os.environ["PDF2HTML_SINGLE_FILE"] = "false"
            os.environ["PDF2HTML_MULTIPLE_DOCUMENTS"] = "true"
            options["single_file"] = False
            options["multiple_documents"] = True

    def _cleanup_output_files(
        self, output_dir: str, single_file: bool, multiple_documents: bool
    ) -> None:
        """Clean up output files based on conversion mode."""
        html_dir = os.path.join(output_dir, "extracted_html")
        if not os.path.exists(html_dir):
            logger.warning(f"HTML directory not found: {html_dir}")
            return

        if single_file:
            # In single file mode, keep document.html and remove page-X.html files
            for file in os.listdir(html_dir):
                if file.startswith("page-") and file.endswith(".html"):
                    try:
                        os.remove(os.path.join(html_dir, file))
                        logger.debug(f"Removed individual page file: {file}")
                    except Exception as e:
                        logger.warning(f"Failed to remove page file {file}: {e}")
        else:
            # In multi-page mode, remove combined document.html
            combined_file = os.path.join(html_dir, "document.html")
            if os.path.exists(combined_file):
                try:
                    os.remove(combined_file)
                    logger.debug("Removed combined document.html file")
                except Exception as e:
                    logger.warning(f"Failed to remove combined file: {e}")

    def _finalize_html_paths(
        self, result: Dict[str, Any], html_dir: str, options: Dict[str, Any]
    ) -> tuple:
        """Determine final HTML paths based on mode."""
        html_files = result.get("html_files", [])

        if options.get("single_file", False):
            # Single file mode
            filtered_files = [
                f for f in html_files
                if not (f.endswith(".html") and "page-" in os.path.basename(f))
            ]
            html_path = os.path.join(html_dir, "document.html")
            mode = "single-page"
            return html_path, filtered_files, mode
        else:
            # Multi-page mode
            page_files = [f for f in html_files if not f.endswith("document.html")]
            html_path = html_dir
            mode = "multi-page"
            return html_path, page_files, mode

    def _copy_images_to_html_dir(
        self, output_dir: str, image_files: Optional[list] = None
    ) -> int:
        """Copy images to extracted_html directory for proper path resolution."""
        if not image_files:
            return 0

        html_dir = os.path.join(output_dir, "extracted_html")
        if not os.path.exists(html_dir):
            os.makedirs(html_dir, exist_ok=True)

        copied_count = 0
        for image_file in image_files:
            if os.path.exists(image_file):
                try:
                    dest_file = os.path.join(html_dir, os.path.basename(image_file))
                    shutil.copy2(image_file, dest_file)
                    copied_count += 1
                except Exception as e:
                    logger.warning(f"Failed to copy image {image_file}: {e}")

        logger.debug(f"Copied {copied_count} images to HTML directory")
        return copied_count
