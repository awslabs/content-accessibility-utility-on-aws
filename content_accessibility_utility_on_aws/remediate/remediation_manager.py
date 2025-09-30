# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Remediation manager for HTML accessibility issues.

This module provides functionality for managing the remediation of accessibility issues.
"""

from typing import Dict, Any, List, Optional, Callable
from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.utils.logging_helper import (
    setup_logger,
    AIRemediationRequiredError,
)
from content_accessibility_utility_on_aws.remediate.services.bedrock_client import (
    BedrockClient,
    AltTextGenerationError,
)

# Import remediation strategies
from content_accessibility_utility_on_aws.remediate.remediation_strategies.link_remediation import (
    remediate_empty_link_text,
    remediate_generic_link_text,
    remediate_url_as_link_text,
    remediate_new_window_link_no_warning,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.image_remediation import (
    remediate_missing_alt_text,
    remediate_empty_alt_text,
    remediate_generic_alt_text,
    remediate_long_alt_text,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.table_remediation import (
    remediate_table_missing_headers,
    remediate_table_missing_scope,
    remediate_table_missing_caption,
    remediate_table_missing_thead,
    remediate_table_missing_tbody,
    remediate_table_irregular_headers,
    remediate_table_headers_id,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.color_contrast_remediation import (
    remediate_insufficient_color_contrast,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.landmark_remediation import (
    remediate_missing_main_landmark,
    remediate_missing_navigation_landmark,
    remediate_missing_header_landmark,
    remediate_missing_footer_landmark,
    remediate_missing_skip_link,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.heading_remediation import (
    remediate_skipped_heading_level,
    remediate_empty_heading_content,
    remediate_missing_h1,
    remediate_missing_headings,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.document_structure_remediation import (
    remediate_missing_document_title,
    remediate_missing_language,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.form_remediation import (
    remediate_missing_form_labels,
    remediate_missing_required_indicators,
    remediate_missing_fieldsets,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.figure_remediation import (
    remediate_improper_figure_structure,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.tab_order_remediation import (
    TabOrderRemediation,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.tab_order_ai_validator import (
    AITabOrderValidator,
)

# Set up module-level logger
logger = setup_logger(__name__)


class RemediationManager:
    """Manager for HTML accessibility remediation."""

    def __init__(self, soup: BeautifulSoup, options: Optional[Dict[str, Any]] = None):
        """
        Initialize the remediation manager.

        Args:
            soup: The BeautifulSoup object representing the HTML document
            options: Remediation options
        """
        self.soup = soup
        self.options = options or {}
        self.remediation_strategies = self._get_remediation_strategies()
        self.bda_client = None

        # Initialize Bedrock client unless explicitly disabled
        self.bedrock_client = None
        self.bda_client = None

        if not self.options.get("disable_ai", False):
            try:
                model_id = self.options.get("model_id", "us.amazon.nova-lite-v1:0")
                profile = self.options.get("profile")
                self.bedrock_client = BedrockClient(model_id=model_id, profile=profile)
                logger.debug(
                    f"Initialized Bedrock client with model: {model_id}, profile: {profile}"
                )
                self.bda_client = self.bedrock_client
            except Exception as e:
                logger.warning(f"Failed to initialize Bedrock client: {e}")
                # Ensure attributes are properly initialized even after failure
                self.bedrock_client = None
                self.bda_client = None

    def _get_remediation_strategies(self) -> Dict[str, Callable]:
        """
        Get the remediation strategies for different issue types.

        Returns:
            Dictionary mapping issue types to remediation functions
        """
        return {
            # Link remediation strategies
            "empty_link": remediate_empty_link_text,
            "generic_link_text": remediate_generic_link_text,
            "url_as_link_text": remediate_url_as_link_text,
            "new_window_link_no_warning": remediate_new_window_link_no_warning,
            # Image remediation strategies
            "missing_alt_text": remediate_missing_alt_text,
            "empty_alt_text": remediate_empty_alt_text,
            "generic_alt_text": remediate_generic_alt_text,
            "generic-alt-text": remediate_generic_alt_text,  # Alternative hyphenated format
            "long_alt_text": remediate_long_alt_text,
            # Table remediation strategies
            "table_missing_headers": remediate_table_missing_headers,
            "table-missing-headers": remediate_table_missing_headers,  # Alternative hyphenated format
            "table_no_headers": remediate_table_missing_headers,
            "table-no-headers": remediate_table_missing_headers,  # Alternative hyphenated format
            "table_missing_scope": remediate_table_missing_scope,
            "table-missing-scope": remediate_table_missing_scope,  # Alternative hyphenated format
            "table_missing_caption": remediate_table_missing_caption,
            "table-missing-caption": remediate_table_missing_caption,  # Alternative hyphenated format
            "table_missing_thead": remediate_table_missing_thead,
            "table-missing-thead": remediate_table_missing_thead,  # Alternative hyphenated format
            "table_missing_tbody": remediate_table_missing_tbody,
            "table-missing-tbody": remediate_table_missing_tbody,  # Alternative hyphenated format
            "table_irregular_headers": remediate_table_irregular_headers,
            "table-irregular-headers": remediate_table_irregular_headers,  # Alternative hyphenated format
            "table-missing-headers-id": remediate_table_headers_id,  # New strategy
            # Heading remediation strategies
            "skipped-heading-level": remediate_skipped_heading_level,
            "empty-heading": remediate_empty_heading_content,
            "generic-heading-content": remediate_empty_heading_content,
            "no-h1": remediate_missing_h1,  # New strategy
            "no-headings": remediate_missing_headings,  # New strategy
            # Color contrast remediation strategies
            "insufficient_color_contrast": remediate_insufficient_color_contrast,
            "insufficient-color-contrast": remediate_insufficient_color_contrast,  # Alternative hyphenated format
            # Landmark remediation strategies
            "missing-main-landmark": remediate_missing_main_landmark,
            "missing-navigation-landmark": remediate_missing_navigation_landmark,
            "missing-header-landmark": remediate_missing_header_landmark,
            "missing-footer-landmark": remediate_missing_footer_landmark,
            "missing-skip-link": remediate_missing_skip_link,
            # Document structure remediation strategies
            "missing-page-title": remediate_missing_document_title,
            "missing-language": remediate_missing_language,
            # Form remediation strategies
            "missing-input-label": remediate_missing_form_labels,
            "missing-required-indicator": remediate_missing_required_indicators,
            "missing-fieldset": remediate_missing_fieldsets,
            # Figure remediation strategies
            "improper-figure-structure": remediate_improper_figure_structure,
        }

    def remediate_issue(self, issue: Dict[str, Any]) -> Optional[str]:
        """
        Remediate a single accessibility issue.

        Args:
            issue: The accessibility issue to remediate

        Returns:
            A message describing the remediation, or None if no remediation was performed
        """
        issue_type = issue.get("type")

        # Check if we have a remediation strategy for this issue type
        if issue_type in self.remediation_strategies:
            try:
                # Apply the remediation strategy with BedrockClient if available
                client_to_use = self.bedrock_client

                # Always ensure we have a client for table remediation
                if issue_type.startswith("table-") or issue_type.startswith("table_"):
                    if not client_to_use:
                        logger.warning(
                            f"No BedrockClient available for {issue_type}. Creating one with profile: {self.options.get('profile')}"
                        )
                        try:
                            # Try to create a new BedrockClient with the profile
                            from content_accessibility_utility_on_aws.remediate.services.bedrock_client import (
                                BedrockClient,
                            )

                            model_id = self.options.get(
                                "model_id", "us.amazon.nova-lite-v1:0"
                            )
                            profile = self.options.get("profile")
                            client_to_use = BedrockClient(
                                model_id=model_id, profile=profile
                            )
                            logger.debug(
                                f"Successfully created BedrockClient for table remediation: {issue_type}"
                            )
                        except Exception as client_error:
                            logger.error(
                                f"Failed to create BedrockClient: {client_error}"
                            )
                            # Continue without client, table_remediation will handle fallbacks

                # Apply the remediation strategy with enhanced debugging for table issues
                if issue_type.startswith("table-") or issue_type.startswith("table_"):
                    logger.debug(
                        f"Attempting to remediate {issue_type} with client: {client_to_use is not None}"
                    )
                    if "element" in issue:
                        logger.debug(
                            f"Table element length: {len(issue.get('element', ''))}"
                        )
                    if "selector" in issue:
                        logger.debug(f"Table selector: {issue.get('selector', '')}")

                result = self.remediation_strategies[issue_type](
                    self.soup, issue, client_to_use
                )
                if result:
                    # Check if this is an "already exists" message
                    if "already exists" in result.lower():
                        logger.debug(f"{issue_type}: {result}")
                    else:
                        logger.debug(f"Remediated {issue_type}: {result}")
                    # Both cases are considered successful
                    return result
                else:
                    logger.warning(
                        f"Failed to remediate {issue_type} (ID: {issue.get('id', 'N/A')}) - issue details: {issue.get('selector', '')}"
                    )
                    return None
            except AIRemediationRequiredError as e:
                # Handle AI requirement error - create a client if possible
                logger.warning(f"AI required for {issue_type}: {e}")

                try:
                    # Always attempt to create a fresh client for this remediation
                    from content_accessibility_utility_on_aws.remediate.services.bedrock_client import (
                        BedrockClient,
                    )

                    model_id = self.options.get("model_id", "us.amazon.nova-lite-v1:0")
                    profile = self.options.get("profile")

                    if profile:
                        logger.debug(
                            f"Creating BedrockClient with profile {profile} for {issue_type}"
                        )
                        try:
                            client = BedrockClient(model_id=model_id, profile=profile)
                            # Try remediation again with the new client
                            logger.debug(f"Retrying {issue_type} with new client")
                            result = self.remediation_strategies[issue_type](
                                self.soup, issue, client
                            )
                            if result:
                                logger.debug(
                                    f"Remediated {issue_type} with newly created client"
                                )
                                return result
                            else:
                                logger.error(
                                    f"Still failed to remediate {issue_type} with new client"
                                )
                        except Exception as client_error:
                            logger.error(
                                f"Failed to create BedrockClient: {client_error}"
                            )
                except Exception as recovery_error:
                    logger.error(
                        f"Failed to recover from AIRemediationRequiredError: {recovery_error}"
                    )

                # For table issues, use aggressive fallback instead of failing
                if issue_type.startswith("table-") or issue_type.startswith("table_"):
                    from content_accessibility_utility_on_aws.remediate.remediation_strategies.table_remediation import (
                        infer_scope_from_position,
                    )

                    try:
                        logger.warning(f"Using fallback approach for {issue_type}")

                        # Try specific table first
                        from content_accessibility_utility_on_aws.remediate.remediation_strategies.table_remediation import (
                            get_table_from_issue,
                        )

                        table = get_table_from_issue(self.soup, issue)

                        if table and table.name == "table":
                            # Find all header cells without scope
                            headers = table.find_all("th")
                            modified = False

                            # Use fallback method to add scope
                            for th in headers:
                                if not th.get("scope"):
                                    th["scope"] = infer_scope_from_position(table, th)
                                    modified = True

                            if modified:
                                return f"Added scope attributes to table header cells using fallback method"
                        else:
                            # If we can't find the specific table, apply to ALL tables as a last resort
                            logger.warning(
                                f"Could not find specific table for {issue_type}. Applying fix to ALL tables."
                            )
                            all_tables = self.soup.find_all("table")
                            total_tables_modified = 0
                            total_headers_modified = 0

                            for table in all_tables:
                                headers = table.find_all("th")
                                table_modified = False
                                headers_modified = 0

                                for th in headers:
                                    if not th.get("scope"):
                                        th["scope"] = infer_scope_from_position(
                                            table, th
                                        )
                                        table_modified = True
                                        headers_modified += 1

                                if table_modified:
                                    total_tables_modified += 1
                                    total_headers_modified += headers_modified

                            if total_tables_modified > 0:
                                return f"Added scope attributes to {total_headers_modified} header cells across {total_tables_modified} tables using aggressive fallback method"
                            else:
                                logger.error(
                                    "No tables found or modified in the document"
                                )
                    except Exception as fallback_error:
                        logger.error(f"Failed fallback attempt: {fallback_error}")

                # If we couldn't recover or use fallback, re-raise the error
                raise
            except AltTextGenerationError as e:
                logger.error(f"AI alt text generation error: {e}")
                # Return a message about the error rather than None to indicate we tried
                return f"Failed to generate alt text: {str(e)}"
            except FileNotFoundError as e:
                logger.error(f"Image file not found: {e}")
                return f"Image file not found: {str(e)}"
            except Exception as e:
                logger.error(f"Error remediating issue {issue_type}: {e}")
                return None
        else:
            logger.debug(f"No remediation strategy for issue type: {issue_type}")
            return None

    def remediate_tab_order_issues(
        self, tab_order_issues: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Remediate tab order issues using sequential two-phase approach.

        Phase 1: Algorithmic remediation (always runs)
        Phase 2: AI validation (enabled by default, can be disabled)

        Args:
            tab_order_issues: List of tab order issues to remediate

        Returns:
            Dictionary with remediation results including changes made
        """
        if not tab_order_issues:
            logger.debug("No tab order issues to remediate")
            return {
                "issues_processed": 0,
                "issues_remediated": 0,
                "changes": [],
                "ai_validation_performed": False,
            }

        logger.debug(f"Remediating {len(tab_order_issues)} tab order issues")

        # Get current HTML as string
        original_html = str(self.soup)

        # Phase 1: Algorithmic Remediation (Required)
        logger.debug("Phase 1: Running algorithmic tab order remediation")
        remediator = TabOrderRemediation(
            html_content=original_html, issues=tab_order_issues, options=self.options
        )
        remediated_html, changes = remediator.remediate()

        # Update soup with algorithmic changes
        self.soup.clear()
        self.soup.append(BeautifulSoup(remediated_html, "html.parser"))

        result = {
            "issues_processed": len(tab_order_issues),
            "issues_remediated": len(changes),
            "changes": changes,
            "ai_validation_performed": False,
            "ai_confidence": None,
            "ai_suggestions_applied": False,
        }

        # Phase 2: AI Validation (Enabled by default, but can be disabled)
        if self.options.get("optimize_tab_order", True) and self.options.get(
            "ai_validate_tab_order", True
        ):
            if self.bedrock_client:
                try:
                    logger.debug("Phase 2: Running AI validation of tab order fixes")

                    # Get confidence threshold from options
                    confidence_threshold = self.options.get(
                        "ai_confidence_threshold", 0.8
                    )

                    # Initialize AI validator
                    ai_validator = AITabOrderValidator(
                        bedrock_client=self.bedrock_client,
                        confidence_threshold=confidence_threshold,
                    )

                    # Validate algorithmic changes
                    validation_result = ai_validator.validate_and_enhance(
                        original_html=original_html,
                        remediated_html=remediated_html,
                        changes=changes,
                        issues=tab_order_issues,
                    )

                    result["ai_validation_performed"] = True
                    result["ai_confidence"] = validation_result.get("confidence", 0.0)

                    # Apply AI suggestions if confidence is high enough
                    if (
                        validation_result.get("suggested_changes")
                        and validation_result.get("confidence", 0)
                        >= confidence_threshold
                    ):
                        logger.debug(
                            f"Applying AI suggestions (confidence: {validation_result['confidence']:.2f})"
                        )

                        final_html, ai_changes = ai_validator.apply_suggestions(
                            html_content=remediated_html,
                            suggestions=validation_result["suggested_changes"],
                        )

                        # Update soup with AI-enhanced changes
                        self.soup.clear()
                        self.soup.append(BeautifulSoup(final_html, "html.parser"))

                        # Merge AI changes with algorithmic changes
                        result["changes"].extend(ai_changes)
                        result["issues_remediated"] = len(result["changes"])
                        result["ai_suggestions_applied"] = True

                        logger.debug(
                            f"Applied {len(ai_changes)} AI-suggested enhancements"
                        )
                    else:
                        logger.debug(
                            f"AI validation complete but confidence too low to apply suggestions (confidence: {validation_result.get('confidence', 0):.2f}, threshold: {confidence_threshold})"
                        )

                except Exception as e:
                    logger.warning(
                        f"AI validation failed, using algorithmic fixes only: {e}"
                    )
                    result["ai_validation_error"] = str(e)
            else:
                logger.debug("AI validation skipped: Bedrock client not available")
        else:
            logger.debug("AI validation disabled by configuration")

        return result

    def remediate_issues(self, issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Remediate multiple accessibility issues.

        Args:
            issues: List of accessibility issues to remediate

        Returns:
            Dictionary with remediation results
        """
        results = {
            "issues_processed": len(issues),
            "issues_remediated": 0,
            "issues_failed": 0,
            "skipped_issues": 0,
            "failed_issue_types": [],
            "details": [],  # Will contain detailed results for each issue
            "remediated_issues_details": [],  # Will contain successfully remediated issues
            "failed_issues_details": [],  # Will contain issues that failed remediation
        }

        # Log how many issues we're going to attempt to remediate
        logger.debug(f"Attempting to remediate {len(issues)} issues")

        # Get max issues to remediate
        max_issues = self.options.get("max_issues")
        if max_issues is not None:
            issues = issues[:max_issues]

        # Get issue types to remediate
        issue_types = self.options.get("issue_types")
        if issue_types:
            issues = [issue for issue in issues if issue.get("type") in issue_types]

        # Get severity threshold
        severity_threshold = self.options.get("severity_threshold", "minor")
        severity_levels = {"critical": 3, "major": 2, "minor": 1}
        threshold_level = severity_levels.get(severity_threshold, 1)

        # Filter issues by severity
        if severity_threshold:
            issues = [
                issue
                for issue in issues
                if severity_levels.get(issue.get("severity", "minor"), 1)
                >= threshold_level
            ]

        # Track failed issue types
        failed_issue_types = set()

        # Track changes applied across all issues
        total_changes_applied = 0

        # Separate tab order issues from other issues for batch processing
        tab_order_issue_types = {
            "positive-tabindex",
            "illogical-tab-order",
            "unnecessary-tabindex-zero",
            "tab-order-mismatch",
        }

        tab_order_issues = [
            issue for issue in issues if issue.get("type") in tab_order_issue_types
        ]
        other_issues = [
            issue for issue in issues if issue.get("type") not in tab_order_issue_types
        ]

        # Process tab order issues together if tab order optimization is enabled
        if tab_order_issues and self.options.get("optimize_tab_order", True):
            logger.debug(
                f"Processing {len(tab_order_issues)} tab order issues together"
            )
            try:
                tab_order_result = self.remediate_tab_order_issues(tab_order_issues)

                # Add tab order results to overall results
                results["issues_remediated"] += tab_order_result.get(
                    "issues_remediated", 0
                )
                total_changes_applied += len(tab_order_result.get("changes", []))

                # Create detail entries for each tab order issue
                for i, issue in enumerate(tab_order_issues):
                    issue_id = issue.get("id", f"issue-{id(issue)}")

                    # Determine if this specific issue was remediated based on changes
                    changes_for_issue = [
                        c
                        for c in tab_order_result.get("changes", [])
                        if c.get("issue_type") == issue.get("type")
                    ]

                    detail = {
                        "id": issue_id,
                        "type": issue.get("type"),
                        "severity": issue.get("severity", "minor"),
                        "message": f"Tab order optimized ({tab_order_result.get('issues_remediated', 0)} fixes applied)",
                        "context": issue.get("context", ""),
                        "selector": issue.get("selector", ""),
                        "remediated": len(changes_for_issue) > 0,
                        "remediation_status": (
                            "remediated" if changes_for_issue else "failed"
                        ),
                        "before_content": issue.get("before_content", ""),
                        "after_content": issue.get("after_content", ""),
                        "fix_description": "; ".join(
                            [c.get("description", "") for c in changes_for_issue]
                        ),
                        "failure_reason": (
                            None if changes_for_issue else "No changes applied"
                        ),
                        "changes_applied": len(changes_for_issue),
                        "file_path": issue.get("file_path", ""),
                        "file_name": issue.get("file_name", ""),
                        "page_number": issue.get("page_number"),
                        "ai_validation_performed": tab_order_result.get(
                            "ai_validation_performed", False
                        ),
                        "ai_suggestions_applied": tab_order_result.get(
                            "ai_suggestions_applied", False
                        ),
                    }

                    # Add location field
                    if "location" not in detail:
                        detail["location"] = {
                            "file_path": detail.get("file_path", ""),
                            "file_name": detail.get("file_name", ""),
                            "page_number": detail.get("page_number"),
                        }
                        if (
                            detail.get("file_name")
                            and detail.get("page_number") is not None
                        ):
                            detail["location"][
                                "description"
                            ] = f"File: {detail['file_name']} (Page {detail['page_number']})"
                        elif detail.get("file_name"):
                            detail["location"][
                                "description"
                            ] = f"File: {detail['file_name']}"
                        elif detail.get("page_number") is not None:
                            detail["location"][
                                "description"
                            ] = f"Page {detail['page_number']}"

                    results["details"].append(detail)
                    if changes_for_issue:
                        results["remediated_issues_details"].append(detail)
                    else:
                        results["failed_issues_details"].append(detail)
                        results["issues_failed"] += 1

            except Exception as e:
                logger.error(f"Error remediating tab order issues: {e}")
                # Mark all tab order issues as failed
                for issue in tab_order_issues:
                    issue_id = issue.get("id", f"issue-{id(issue)}")
                    detail = {
                        "id": issue_id,
                        "type": issue.get("type"),
                        "severity": issue.get("severity", "minor"),
                        "message": f"Failed to remediate: {str(e)}",
                        "context": issue.get("context", ""),
                        "selector": issue.get("selector", ""),
                        "remediated": False,
                        "remediation_status": "failed",
                        "before_content": issue.get("before_content", ""),
                        "after_content": issue.get("after_content", ""),
                        "fix_description": "",
                        "failure_reason": str(e),
                        "changes_applied": 0,
                        "file_path": issue.get("file_path", ""),
                        "file_name": issue.get("file_name", ""),
                        "page_number": issue.get("page_number"),
                    }
                    results["details"].append(detail)
                    results["failed_issues_details"].append(detail)
                results["issues_failed"] += len(tab_order_issues)
                failed_issue_types.update(tab_order_issue_types)

        # Process other issues individually
        for issue in other_issues:
            issue_type = issue.get("type")

            # Ensure issue has a proper ID - preserve the original ID from audit
            issue_id = issue.get("id")
            if not issue_id:
                issue_id = f"issue-{id(issue)}"  # Generate a unique ID if none exists

            try:
                # For landmark issues, we need to handle counting differently
                # since one landmark issue can cause multiple fixes
                is_landmark_issue = issue_type.startswith(
                    "missing-"
                ) and issue_type.endswith("-landmark")

                result = self.remediate_issue(issue)

                # Create detailed result entry - preserve original ID
                detail = {
                    "id": issue_id,  # Preserve original ID from audit report
                    "type": issue_type,
                    "severity": issue.get("severity", "minor"),
                    "message": result or f"Failed to remediate {issue_type}",
                    "context": issue.get("context", ""),
                    "selector": issue.get("selector", ""),
                    "remediated": result is not None,
                    "remediation_status": (
                        "remediated" if result is not None else "failed"
                    ),
                    "before_content": issue.get("before_content", ""),
                    "after_content": issue.get("after_content", ""),
                    "fix_description": (
                        result
                        if result and not result.endswith("no remediation needed")
                        else ""
                    ),
                    "failure_reason": (
                        None if result else "Unable to apply fix automatically"
                    ),
                    "file_path": issue.get("file_path")
                    or (issue.get("location", {}) or {}).get("file_path", ""),
                    "file_name": issue.get("file_name")
                    or (issue.get("location", {}) or {}).get("file_name", ""),
                    "page_number": issue.get("page_number")
                    or (issue.get("location", {}) or {}).get("page_number"),
                }

                # For unified format in report generation, include a location field if not present
                if "location" not in detail:
                    detail["location"] = {
                        "file_path": detail.get("file_path", ""),
                        "file_name": detail.get("file_name", ""),
                        "page_number": detail.get("page_number"),
                    }
                    # Add a human-readable description
                    if (
                        detail.get("file_name")
                        and detail.get("page_number") is not None
                    ):
                        detail["location"][
                            "description"
                        ] = f"File: {detail['file_name']} (Page {detail['page_number']})"
                    elif detail.get("file_name"):
                        detail["location"][
                            "description"
                        ] = f"File: {detail['file_name']}"
                    elif detail.get("page_number") is not None:
                        detail["location"][
                            "description"
                        ] = f"Page {detail['page_number']}"

                # Track changes applied to this issue
                if result:
                    changes_applied = 1

                    # For landmark issues, determine actual changes from the result
                    if is_landmark_issue:
                        # Set different values based on issue type
                        if issue_type == "missing-main-landmark":
                            # Main landmark triggers navigation, header, footer, skip link
                            changes_applied = 1
                            detail["actual_changes"] = "Added main landmark"
                        elif issue_type == "missing-navigation-landmark":
                            # Navigation triggers header, footer, skip link
                            changes_applied = 1
                            detail["actual_changes"] = "Added navigation landmark"
                        elif issue_type == "missing-header-landmark":
                            # Header triggers footer, skip link
                            changes_applied = 1
                            detail["actual_changes"] = "Added header landmark"
                        elif issue_type == "missing-footer-landmark":
                            # Footer triggers skip link
                            changes_applied = 1
                            detail["actual_changes"] = "Added footer landmark"
                        else:
                            # Other landmarks like skip link are standalone
                            changes_applied = 1
                            detail["actual_changes"] = (
                                f'Added {issue_type.replace("missing-", "")}'
                            )
                    # For table remediation, we might have applied multiple fixes
                    elif "header cells across" in result:
                        # Extract the count from the message like "Added scope attributes to 15 header cells..."
                        import re

                        cells_match = re.search(r"to (\d+) header cells", result)
                        if cells_match:
                            cells_count = int(cells_match.group(1))
                            if cells_count > 1:
                                changes_applied = (
                                    1  # Count as 1 issue fixed, not multiple cells
                                )

                    detail["changes_applied"] = changes_applied
                    total_changes_applied += changes_applied
                else:
                    detail["changes_applied"] = 0

            except AIRemediationRequiredError as e:
                # Handle AI requirement error
                error_message = f"AI is required for remediating {issue_type}: {str(e)}"
                logger.error(error_message)

                # Create detailed failure entry - preserve original ID
                detail = {
                    "id": issue_id,  # Preserve original ID from audit report
                    "type": issue_type,
                    "severity": issue.get("severity", "minor"),
                    "message": error_message,
                    "context": issue.get("context", ""),
                    "selector": issue.get("selector", ""),
                    "remediated": False,
                    "remediation_status": "failed",
                    "before_content": issue.get("before_content", ""),
                    "after_content": issue.get("after_content", ""),
                    "fix_description": "",
                    "failure_reason": "AI service required but not available",
                    "changes_applied": 0,
                    "file_path": issue.get("file_path")
                    or (issue.get("location", {}) or {}).get("file_path", ""),
                    "file_name": issue.get("file_name")
                    or (issue.get("location", {}) or {}).get("file_name", ""),
                    "page_number": issue.get("page_number")
                    or (issue.get("location", {}) or {}).get("page_number"),
                }

                # For unified format in report generation, include a location field if not present
                if "location" not in detail:
                    detail["location"] = {
                        "file_path": detail.get("file_path", ""),
                        "file_name": detail.get("file_name", ""),
                        "page_number": detail.get("page_number"),
                    }
                    # Add a human-readable description
                    if (
                        detail.get("file_name")
                        and detail.get("page_number") is not None
                    ):
                        detail["location"][
                            "description"
                        ] = f"File: {detail['file_name']} (Page {detail['page_number']})"
                    elif detail.get("file_name"):
                        detail["location"][
                            "description"
                        ] = f"File: {detail['file_name']}"
                    elif detail.get("page_number") is not None:
                        detail["location"][
                            "description"
                        ] = f"Page {detail['page_number']}"
                # Set result to None for failure counting
                result = None

                # Add to failed issue types
                failed_issue_types.add(issue_type)

            # Update counts based on result
            if result:
                # Check if this is an "already exists" message
                if "already exists" in result.lower():
                    # Count as remediated since the feature is already present
                    results["issues_remediated"] += 1
                    results["remediated_issues_details"].append(detail)
                    logger.debug(f"{issue_type}: {result}")
                else:
                    # Successful new remediation
                    results["issues_remediated"] += 1
                    results["remediated_issues_details"].append(detail)
                    logger.debug(f"Remediated {issue_type}: {result}")
            else:
                if issue_type in self.remediation_strategies:
                    # Failed remediation (strategy exists but failed)
                    results["issues_failed"] += 1
                    results["failed_issues_details"].append(detail)
                    failed_issue_types.add(issue_type)
                    logger.warning(f"Failed to remediate {issue_type}")
                else:
                    # Skipped remediation (no strategy exists)
                    results["skipped_issues"] += 1
                    results["failed_issues_details"].append(detail)
                    failed_issue_types.add(issue_type)
                    logger.debug(f"Skipped remediation for {issue_type} (no strategy)")

            results["details"].append(detail)

        # Add failed issue types to result
        results["failed_issue_types"] = list(failed_issue_types)

        # Record the total number of changes applied (accounts for multiple fixes per processed issue)
        results["total_changes_applied"] = total_changes_applied

        # Add explanation for file results counts
        results["actual_issues_fixed"] = results["issues_remediated"]
        results["explanation"] = (
            "For landmark issues, multiple landmarks are often added as part of a single fix. The 'issues_remediated' count reflects the number of issues fixed, while the actual number of HTML elements added may be higher."
        )

        # Log the actual number of changes made vs issues processed
        logger.debug(
            f"Processed {results['issues_processed']} issues, applied {total_changes_applied} total changes"
        )

        return results
