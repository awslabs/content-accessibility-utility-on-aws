#!/usr/bin/env python3
# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""Example usage of tab order optimization features.

This script demonstrates how to use the tab order detection and remediation
capabilities of the Content Accessibility Utility on AWS.
"""

import boto3
from content_accessibility_utility_on_aws.audit.auditor import AccessibilityAuditor
from content_accessibility_utility_on_aws.remediate.remediation_strategies import (
    TabOrderRemediation,
    AITabOrderValidator,
)


def example_1_detect_tab_order_issues():
    """Example 1: Detect tab order issues in HTML."""
    print("=" * 80)
    print("Example 1: Detecting Tab Order Issues")
    print("=" * 80)

    # Create auditor
    auditor = AccessibilityAuditor(
        html_path="output/document.html",
        options={"severity_threshold": "minor", "detailed": True},
    )

    # Run audit
    report = auditor.audit()

    # Filter for tab order issues (WCAG 2.4.3)
    tab_order_issues = [
        issue for issue in report["issues"] if issue["wcag_criterion"] == "2.4.3"
    ]

    print(f"\nFound {len(tab_order_issues)} tab order issues:")
    for issue in tab_order_issues:
        print(f"\n  [{issue['severity'].upper()}] {issue['type']}")
        print(f"  Description: {issue['description']}")
        if "context" in issue and issue["context"]:
            if "recommendation" in issue["context"]:
                print(f"  Recommendation: {issue['context']['recommendation']}")

    return tab_order_issues, report


def example_2_algorithmic_remediation():
    """Example 2: Apply algorithmic remediation to fix tab order issues."""
    print("\n" + "=" * 80)
    print("Example 2: Algorithmic Remediation")
    print("=" * 80)

    # First, detect issues
    tab_order_issues, report = example_1_detect_tab_order_issues()

    if not tab_order_issues:
        print("\nNo tab order issues to remediate!")
        return None, []

    # Load HTML content
    with open("output/document.html", "r") as f:
        html_content = f.read()

    # Create remediation instance
    remediator = TabOrderRemediation(
        html_content=html_content,
        issues=tab_order_issues,
        options={
            "reorder_dom_for_visual_order": True,
        },
    )

    # Perform remediation
    remediated_html, changes = remediator.remediate()

    print(f"\nRemediation complete! Made {len(changes)} changes:")
    for change in changes:
        print(f"\n  Type: {change['type']}")
        print(f"  Element: {change.get('element', 'N/A')}")
        print(f"  Reason: {change.get('reason', 'N/A')}")

    # Save remediated HTML
    with open("output/document_remediated.html", "w") as f:
        f.write(remediated_html)

    print("\nRemediated HTML saved to: output/document_remediated.html")

    return remediated_html, changes


def example_3_ai_validation():
    """Example 3: Use AI to validate and enhance remediation (DEFAULT BEHAVIOR).

    IMPORTANT: AI validation is ENABLED BY DEFAULT and runs after algorithmic
    remediation completes. This is a sequential process:
    1. First: Algorithmic remediation (Phase 1 - Required)
    2. Then: AI validation (Phase 2 - Enabled by default, can be disabled)

    To skip AI validation, set ai_validate_tab_order=False in options.
    """
    print("\n" + "=" * 80)
    print("Example 3: AI Validation and Enhancement (Default Behavior)")
    print("Sequential Process: Algorithmic → AI Validation")
    print("=" * 80)

    # STEP 1: Get algorithmic remediation results (must complete first)
    print("\nSTEP 1: Running algorithmic remediation (Phase 1)...")
    remediated_html, changes = example_2_algorithmic_remediation()

    if not remediated_html:
        print("\nNo remediation to validate!")
        return

    # Load original HTML
    with open("output/document.html", "r") as f:
        original_html = f.read()

    # Get original issues
    tab_order_issues, _ = example_1_detect_tab_order_issues()

    # STEP 2: AI Validation (runs by default after Phase 1)
    print("\n" + "=" * 60)
    print("STEP 2: Running AI validation (Phase 2 - Default)")
    print("=" * 60)

    # Initialize Bedrock client
    bedrock = boto3.client("bedrock-runtime", region_name="us-west-2")

    # Create AI validator
    ai_validator = AITabOrderValidator(
        bedrock_client=bedrock,
        model_id="amazon.nova-lite-v1:0",
        confidence_threshold=0.8,
    )

    # Validate remediation (this runs by default)
    print("\nCalling AI for validation (default behavior)...")
    validation_result = ai_validator.validate_and_enhance(
        original_html=original_html,
        remediated_html=remediated_html,
        changes=changes,
        issues=tab_order_issues,
    )

    # Display validation results
    print(f"\nAI Validation Results:")
    print(f"  Valid: {validation_result['is_valid']}")
    print(f"  Confidence: {validation_result['confidence']:.2f}")
    print(f"  Reasoning: {validation_result['reasoning']}")

    # Check for additional issues
    if validation_result.get("issues_found"):
        print(f"\n  Additional issues found: {len(validation_result['issues_found'])}")
        for issue in validation_result["issues_found"]:
            print(f"    - {issue.get('description', 'Unknown issue')}")

    # Apply AI suggestions if confidence is high enough
    if (
        validation_result.get("suggested_changes")
        and validation_result["confidence"] >= ai_validator.confidence_threshold
    ):
        print(
            f"\n  Applying {len(validation_result['suggested_changes'])} AI suggestions..."
        )

        final_html, ai_changes = ai_validator.apply_suggestions(
            remediated_html, validation_result["suggested_changes"]
        )

        print(f"  Applied {len(ai_changes)} AI-suggested changes")

        # Save final HTML
        with open("output/document_final.html", "w") as f:
            f.write(final_html)

        print("\nFinal HTML saved to: output/document_final.html")

    else:
        print(
            "\n  No AI suggestions to apply (confidence below threshold or no suggestions)"
        )


def example_4_complete_workflow():
    """Example 4: Complete workflow from PDF to optimized HTML."""
    print("\n" + "=" * 80)
    print("Example 4: Complete Workflow")
    print("=" * 80)

    # Step 1: Convert PDF to HTML (assuming already done)
    print("\nStep 1: PDF converted to HTML (assumed complete)")

    # Step 2: Audit for all accessibility issues
    print("\nStep 2: Running comprehensive accessibility audit...")
    auditor = AccessibilityAuditor(
        html_path="output/document.html",
        options={"severity_threshold": "minor", "detailed": True},
    )
    full_report = auditor.audit()

    print(f"  Total issues found: {full_report['summary']['total_issues']}")
    print(f"  By severity:")
    for severity, count in full_report["summary"]["severity_counts"].items():
        if count > 0:
            print(f"    {severity}: {count}")

    # Step 3: Filter and remediate tab order issues
    print("\nStep 3: Remediating tab order issues...")
    tab_order_issues = [
        issue for issue in full_report["issues"] if issue["wcag_criterion"] == "2.4.3"
    ]

    if tab_order_issues:
        with open("output/document.html", "r") as f:
            html_content = f.read()

        remediator = TabOrderRemediation(
            html_content=html_content,
            issues=tab_order_issues,
            options={"reorder_dom_for_visual_order": True},
        )

        remediated_html, changes = remediator.remediate()
        print(f"  Made {len(changes)} changes")

        # Optional: AI validation
        if input("\n  Run AI validation? (y/n): ").lower() == "y":
            bedrock = boto3.client("bedrock-runtime", region_name="us-west-2")
            ai_validator = AITabOrderValidator(
                bedrock_client=bedrock, confidence_threshold=0.8
            )

            validation = ai_validator.validate_and_enhance(
                original_html=html_content,
                remediated_html=remediated_html,
                changes=changes,
                issues=tab_order_issues,
            )

            if validation.get("suggested_changes"):
                remediated_html, ai_changes = ai_validator.apply_suggestions(
                    remediated_html, validation["suggested_changes"]
                )
                print(f"  Applied {len(ai_changes)} AI suggestions")

        # Save final HTML
        with open("output/document_optimized.html", "w") as f:
            f.write(remediated_html)

        print("\n✓ Tab order optimized HTML saved to: output/document_optimized.html")
    else:
        print("  No tab order issues found!")

    # Step 4: Re-audit to confirm fixes
    print("\nStep 4: Re-auditing to confirm fixes...")
    re_auditor = AccessibilityAuditor(
        html_content=remediated_html if tab_order_issues else html_content,
        options={"severity_threshold": "minor", "detailed": True},
    )
    final_report = re_auditor.audit()

    remaining_tab_issues = [
        issue for issue in final_report["issues"] if issue["wcag_criterion"] == "2.4.3"
    ]

    print(f"  Remaining tab order issues: {len(remaining_tab_issues)}")
    if len(remaining_tab_issues) < len(tab_order_issues):
        fixed_count = len(tab_order_issues) - len(remaining_tab_issues)
        print(f"  ✓ Fixed {fixed_count} tab order issues!")


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("Tab Order Optimization Examples")
    print("=" * 80)

    try:
        # Run example 1: Detection
        example_1_detect_tab_order_issues()

        # Run example 2: Algorithmic remediation
        example_2_algorithmic_remediation()

        # Run example 3: AI validation (requires Bedrock)
        try:
            example_3_ai_validation()
        except Exception as e:
            print(f"\nAI validation example skipped: {e}")

        # Run example 4: Complete workflow
        example_4_complete_workflow()

        print("\n" + "=" * 80)
        print("Examples complete!")
        print("=" * 80)

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
