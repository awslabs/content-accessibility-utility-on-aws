# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
pdf2htmlEX converter implementation.

This module provides the pdf2htmlEX-based PDF to HTML converter,
running pdf2htmlEX via Docker for high-fidelity layout preservation.
"""

import os
import re
import shutil
import uuid
from typing import Dict, Any, List, Optional

from content_accessibility_utility_on_aws.pdf2html.converters.base import (
    BaseConverter,
    ConversionResult,
    ConverterType,
)
from content_accessibility_utility_on_aws.pdf2html.services.docker_client import (
    DockerClient,
)
from content_accessibility_utility_on_aws.utils.logging_helper import (
    setup_logger,
    DockerError,
    ConverterNotAvailableError,
    PDFConversionError,
)
from content_accessibility_utility_on_aws.utils.resources import ensure_directory

logger = setup_logger(__name__)


class Pdf2HtmlExConverter(BaseConverter):
    """
    PDF to HTML converter using pdf2htmlEX via Docker.

    This converter uses the pdf2htmlEX tool running in a Docker container
    to convert PDFs to HTML with high layout fidelity.
    """

    DEFAULT_DOCKER_IMAGE = "pdf2htmlex/pdf2htmlex:0.18.8.rc2-master-20200820-ubuntu-20.04-x86_64"

    # Default options for pdf2htmlEX
    DEFAULT_OPTIONS = {
        "zoom": 1.0,
        "embed_font": True,
        "embed_css": True,
        "embed_image": True,
        "embed_javascript": True,
        "embed_outline": True,
        "split_pages": False,
        "process_outline": True,
        "bg_format": "png",
        "dpi": 144,
        "fit_width": None,
        "fit_height": None,
        "use_cropbox": True,
        "optimize_text": False,
        "fallback": False,
        "first_page": None,
        "last_page": None,
        "no_drm": True,
        "dest_dir": None,
    }

    def __init__(self, docker_image: Optional[str] = None):
        """
        Initialize the pdf2htmlEX converter.

        Args:
            docker_image: Docker image to use for pdf2htmlEX.
                Defaults to the official pdf2htmlEX image.
        """
        self._docker_image = docker_image or self.DEFAULT_DOCKER_IMAGE
        self._docker_client = DockerClient()

    @property
    def converter_type(self) -> ConverterType:
        """Return the type of this converter."""
        return ConverterType.PDF2HTMLEX

    @property
    def docker_image(self) -> str:
        """Return the Docker image being used."""
        return self._docker_image

    def is_available(self) -> bool:
        """
        Check if pdf2htmlEX converter is available.

        Returns:
            True if Docker is available and running.
        """
        return self._docker_client.is_available()

    def validate_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize pdf2htmlEX-specific options.

        Args:
            options: Raw options dictionary.

        Returns:
            Validated options with defaults applied.
        """
        validated = self.DEFAULT_OPTIONS.copy()

        if options:
            # Handle pdf2htmlex-specific options if nested
            pdf2htmlex_opts = options.get("pdf2htmlex", {})
            if pdf2htmlex_opts:
                validated.update(pdf2htmlex_opts)

            # Also check for top-level options
            for key in self.DEFAULT_OPTIONS:
                if key in options:
                    validated[key] = options[key]

            # Map common options
            if "single_file" in options:
                validated["split_pages"] = not options["single_file"]
            if "multi_page" in options and options["multi_page"]:
                validated["split_pages"] = True

        return validated

    def convert(
        self,
        pdf_path: str,
        output_dir: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> ConversionResult:
        """
        Convert a PDF to HTML using pdf2htmlEX via Docker.

        Args:
            pdf_path: Path to the source PDF file.
            output_dir: Directory to save the converted HTML files.
            options: Conversion options.

        Returns:
            ConversionResult with paths to generated files and metadata.

        Raises:
            FileNotFoundError: If the PDF file doesn't exist.
            ConverterNotAvailableError: If Docker is not available.
            PDFConversionError: If conversion fails.
        """
        # Validate PDF exists
        if not os.path.isfile(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Check Docker availability
        if not self.is_available():
            raise ConverterNotAvailableError(
                "Docker is not available. Please install Docker and ensure "
                "the daemon is running to use the pdf2htmlEX converter."
            )

        # Validate and apply default options
        validated_options = self.validate_options(options or {})

        # Ensure output directory exists
        ensure_directory(output_dir)

        # Create extracted_html subdirectory to match BDA output structure
        html_dir = os.path.join(output_dir, "extracted_html")
        ensure_directory(html_dir)

        try:
            # Ensure Docker image is available
            if not self._docker_client.image_exists(self._docker_image):
                logger.info(f"Pulling Docker image: {self._docker_image}")
                if not self._docker_client.pull_image(self._docker_image):
                    raise DockerError(f"Failed to pull Docker image: {self._docker_image}")

            # Get absolute paths
            pdf_path_abs = os.path.abspath(pdf_path)
            html_dir_abs = os.path.abspath(html_dir)
            pdf_filename = os.path.basename(pdf_path)

            # Build pdf2htmlEX command arguments
            cmd_args = self._build_command_args(validated_options, pdf_filename)

            # Set up volume mounts
            # Mount PDF directory as read-only, output directory as read-write
            pdf_dir = os.path.dirname(pdf_path_abs)
            volumes = {
                pdf_dir: {"bind": "/pdf", "mode": "ro"},
                html_dir_abs: {"bind": "/output", "mode": "rw"},
            }

            # Run pdf2htmlEX in Docker
            logger.debug(f"Running pdf2htmlEX: {' '.join(cmd_args)}")

            result = self._docker_client.run_container(
                image=self._docker_image,
                command=cmd_args,
                volumes=volumes,
                working_dir="/output",
                timeout=600,  # 10 minutes timeout
            )

            if not result.success:
                logger.error(f"pdf2htmlEX failed: {result.stderr}")
                raise PDFConversionError(
                    f"pdf2htmlEX conversion failed: {result.stderr}"
                )

            logger.debug(f"pdf2htmlEX output: {result.stdout}")

            # Normalize output to match expected structure
            return self._normalize_output(
                output_dir=output_dir,
                html_dir=html_dir,
                pdf_path=pdf_path,
                options=validated_options,
            )

        except (FileNotFoundError, ConverterNotAvailableError, DockerError):
            raise
        except PDFConversionError:
            raise
        except Exception as e:
            logger.error(f"Error converting PDF with pdf2htmlEX: {e}")
            raise PDFConversionError(f"pdf2htmlEX conversion failed: {e}") from e

    def _build_command_args(
        self, options: Dict[str, Any], pdf_filename: str
    ) -> List[str]:
        """
        Build pdf2htmlEX command-line arguments from options.

        Args:
            options: Validated options dictionary.
            pdf_filename: Name of the PDF file.

        Returns:
            List of command-line arguments.
        """
        args = []

        # Zoom level
        if options.get("zoom") and options["zoom"] != 1.0:
            args.extend(["--zoom", str(options["zoom"])])

        # Font embedding
        if options.get("embed_font"):
            args.append("--embed-font=1")
        else:
            args.append("--embed-font=0")

        # CSS embedding
        if options.get("embed_css"):
            args.append("--embed-css=1")
        else:
            args.append("--embed-css=0")

        # Image embedding
        if options.get("embed_image"):
            args.append("--embed-image=1")
        else:
            args.append("--embed-image=0")

        # JavaScript embedding
        if options.get("embed_javascript"):
            args.append("--embed-javascript=1")
        else:
            args.append("--embed-javascript=0")

        # Outline embedding
        if options.get("embed_outline"):
            args.append("--embed-outline=1")
        else:
            args.append("--embed-outline=0")

        # Split pages
        if options.get("split_pages"):
            args.append("--split-pages=1")
        else:
            args.append("--split-pages=0")

        # Process outline
        if options.get("process_outline"):
            args.append("--process-outline=1")
        else:
            args.append("--process-outline=0")

        # Background format
        if options.get("bg_format"):
            args.extend(["--bg-format", options["bg_format"]])

        # DPI setting (single value, not separate hdpi/vdpi)
        # Use hdpi value if provided, falling back to 144
        dpi = options.get("hdpi") or options.get("vdpi") or options.get("dpi")
        if dpi:
            args.extend(["--dpi", str(dpi)])

        # Fit dimensions
        if options.get("fit_width"):
            args.extend(["--fit-width", str(options["fit_width"])])
        if options.get("fit_height"):
            args.extend(["--fit-height", str(options["fit_height"])])

        # Use cropbox
        if options.get("use_cropbox"):
            args.append("--use-cropbox=1")
        else:
            args.append("--use-cropbox=0")

        # Optimize text
        if options.get("optimize_text"):
            args.append("--optimize-text=1")
        else:
            args.append("--optimize-text=0")

        # Fallback rendering (default is 0 in pdf2htmlEX)
        if options.get("fallback"):
            args.append("--fallback=1")

        # No DRM (required for most PDFs)
        if options.get("no_drm"):
            args.append("--no-drm=1")

        # Page range (using -f and -l shorthand)
        if options.get("first_page"):
            args.extend(["-f", str(options["first_page"])])
        if options.get("last_page"):
            args.extend(["-l", str(options["last_page"])])

        # Output directory (inside container)
        args.extend(["--dest-dir", "/output"])

        # Input PDF file (inside container)
        args.append(f"/pdf/{pdf_filename}")

        return args

    def _normalize_output(
        self,
        output_dir: str,
        html_dir: str,
        pdf_path: str,
        options: Dict[str, Any],
    ) -> ConversionResult:
        """
        Normalize pdf2htmlEX output to match expected result structure.

        Args:
            output_dir: Base output directory.
            html_dir: Directory containing HTML files.
            pdf_path: Original PDF path (for naming).
            options: Conversion options.

        Returns:
            ConversionResult with normalized paths.
        """
        html_files = []
        page_files = []
        image_files = []

        # Scan html_dir for generated files
        if os.path.isdir(html_dir):
            for filename in os.listdir(html_dir):
                filepath = os.path.join(html_dir, filename)
                if filename.endswith(".html"):
                    html_files.append(filepath)
                elif filename.endswith(".page"):
                    # pdf2htmlEX uses .page extension for split pages
                    page_files.append(filepath)
                elif filename.endswith((".png", ".jpg", ".jpeg", ".svg", ".gif")):
                    image_files.append(filepath)

        # Sort files for consistent ordering
        html_files.sort()
        page_files.sort()

        # Determine mode and primary HTML path
        if options.get("split_pages") and page_files:
            mode = "multi-page"
            html_path = html_dir
            # Rename .page files to page-X.html format
            html_files = self._rename_page_files_to_html(page_files)
        else:
            mode = "single-page"
            if html_files:
                # Rename single file to document.html for consistency
                original_file = html_files[0]
                document_html = os.path.join(html_dir, "document.html")
                if original_file != document_html and not os.path.exists(document_html):
                    shutil.move(original_file, document_html)
                    html_files = [document_html]
                elif os.path.exists(document_html):
                    html_files = [document_html]
                html_path = document_html
            else:
                html_path = html_dir

        # Count pages from HTML files or estimate from PDF
        if options.get("split_pages") and html_files:
            page_count = len(html_files)
        else:
            page_count = self._count_pdf_pages(pdf_path)

        # Generate document ID
        document_id = f"pdf2htmlex-{uuid.uuid4().hex[:8]}"

        return ConversionResult(
            html_path=html_path,
            html_files=html_files,
            image_files=image_files,
            is_image_only=False,  # pdf2htmlEX always extracts text
            result_data={},  # pdf2htmlEX doesn't provide element metadata
            mode=mode,
            document_id=document_id,
            page_count=page_count,
        )

    def _rename_page_files_to_html(self, page_files: List[str]) -> List[str]:
        """
        Rename .page files to page-X.html format.

        pdf2htmlEX generates files like: filename1.page, filename2.page
        We rename them to: page-1.html, page-2.html, etc.

        Args:
            page_files: List of .page file paths.

        Returns:
            List of renamed .html file paths.
        """
        renamed_files = []

        for i, filepath in enumerate(sorted(page_files), start=1):
            directory = os.path.dirname(filepath)
            new_name = f"page-{i}.html"
            new_path = os.path.join(directory, new_name)

            if filepath != new_path:
                shutil.move(filepath, new_path)

            renamed_files.append(new_path)

        return renamed_files

    def _rename_to_page_format(self, html_files: List[str]) -> List[str]:
        """
        Rename HTML files to BDA-compatible page format.

        pdf2htmlEX generates files like: filename.html, filename-1.html, filename-2.html
        We rename them to: page-1.html, page-2.html, etc.

        Args:
            html_files: List of HTML file paths.

        Returns:
            List of renamed file paths.
        """
        renamed_files = []

        for i, filepath in enumerate(html_files, start=1):
            directory = os.path.dirname(filepath)
            new_name = f"page-{i}.html"
            new_path = os.path.join(directory, new_name)

            if filepath != new_path:
                shutil.move(filepath, new_path)

            renamed_files.append(new_path)

        return renamed_files

    def _count_pdf_pages(self, pdf_path: str) -> int:
        """
        Count the number of pages in a PDF.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Number of pages, or 1 if counting fails.
        """
        try:
            import pypdf

            with open(pdf_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                return len(reader.pages)
        except Exception as e:
            logger.debug(f"Could not count PDF pages: {e}")
            return 1
