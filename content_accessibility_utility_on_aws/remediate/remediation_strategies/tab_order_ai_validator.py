# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""AI-powered tab order validation and enhancement.

This module provides AI validation for tab order remediation using Amazon Bedrock.
"""

from typing import Dict, List, Any, Optional, Tuple
from bs4 import BeautifulSoup, Tag
import json
from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)


class AITabOrderValidator:
    """AI-powered validation and enhancement for tab order remediation."""

    def __init__(
        self,
        bedrock_client,
        model_id: str = "amazon.nova-lite-v1:0",
        confidence_threshold: float = 0.8,
    ):
        """
        Initialize AI tab order validator.

        Args:
            bedrock_client: Bedrock client for AI calls
            model_id: Bedrock model ID to use
            confidence_threshold: Minimum confidence score to apply AI suggestions
        """
        self.bedrock_client = bedrock_client
        self.model_id = model_id
        self.confidence_threshold = confidence_threshold

    def validate_and_enhance(
        self,
        original_html: str,
        remediated_html: str,
        changes: List[Dict[str, Any]],
        issues: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Validate algorithmic remediation and suggest enhancements.

        Args:
            original_html: Original HTML before remediation
            remediated_html: HTML after algorithmic remediation
            changes: List of changes made by algorithmic remediation
            issues: Original tab order issues from audit

        Returns:
            Validation results with suggestions
        """
        logger.info("Starting AI validation of tab order remediation")

        # Parse HTML
        original_soup = BeautifulSoup(original_html, "html.parser")
        remediated_soup = BeautifulSoup(remediated_html, "html.parser")

        # Extract tab sequences
        original_sequence = self._extract_tab_sequence(original_soup)
        remediated_sequence = self._extract_tab_sequence(remediated_soup)

        # Get visual layout context
        layout_context = self._extract_layout_context(remediated_soup)

        # Get semantic context
        semantic_context = self._extract_semantic_context(remediated_soup)

        # Generate validation prompt
        prompt = self._generate_validation_prompt(
            original_sequence,
            remediated_sequence,
            layout_context,
            semantic_context,
            changes,
            issues,
        )

        # Call Bedrock for validation
        try:
            validation_result = self._call_bedrock(prompt)
            logger.info(
                f"AI validation complete. Confidence: {validation_result.get('confidence', 0)}"
            )
            return validation_result
        except Exception as e:
            logger.error(f"AI validation failed: {e}")
            return {
                "is_valid": True,  # Default to accepting algorithmic changes
                "confidence": 0.5,
                "issues_found": [],
                "suggested_changes": [],
                "reasoning": f"AI validation unavailable: {str(e)}",
                "error": str(e),
            }

    def apply_suggestions(
        self, html_content: str, suggestions: List[Dict[str, Any]]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Apply AI-suggested changes to HTML.

        Args:
            html_content: HTML to modify
            suggestions: List of AI suggestions

        Returns:
            Tuple of (modified HTML, list of applied changes)
        """
        soup = BeautifulSoup(html_content, "html.parser")
        applied_changes = []

        for suggestion in suggestions:
            try:
                change = self._apply_single_suggestion(soup, suggestion)
                if change:
                    applied_changes.append(change)
            except Exception as e:
                logger.error(f"Failed to apply suggestion: {e}")

        return str(soup), applied_changes

    def _extract_tab_sequence(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract the current tab sequence from HTML."""
        tab_sequence = []

        # Find all potentially tabbable elements
        interactive_elements = soup.find_all(
            lambda tag: tag.name
            in ["a", "button", "input", "select", "textarea", "area"]
            or (tag.has_attr("tabindex") and tag.get("tabindex") != "-1")
        )

        for idx, element in enumerate(interactive_elements):
            # Skip disabled elements
            if element.has_attr("disabled"):
                continue

            tab_sequence.append(
                {
                    "index": idx,
                    "element_type": element.name,
                    "element_id": element.get("id"),
                    "element_class": element.get("class"),
                    "tabindex": element.get("tabindex"),
                    "text": (
                        element.get_text()[:50].strip() if element.get_text() else ""
                    ),
                    "href": element.get("href") if element.name == "a" else None,
                }
            )

        return tab_sequence

    def _extract_layout_context(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract visual layout information."""
        # Check for multi-column layouts
        multi_column_indicators = soup.find_all(
            lambda tag: tag.has_attr("style") and "column" in tag.get("style", "")
        ) or soup.find_all(
            class_=lambda x: x
            and any(col in str(x).lower() for col in ["col-", "column"])
        )

        # Check for sidebars
        sidebars = soup.find_all(
            lambda tag: "sidebar" in str(tag.get("class", "")).lower()
            or tag.name == "aside"
        )

        # Check for navigation
        nav_elements = soup.find_all("nav")

        return {
            "has_multi_column_layout": len(multi_column_indicators) > 0,
            "has_sidebar": len(sidebars) > 0,
            "has_navigation": len(nav_elements) > 0,
            "nav_count": len(nav_elements),
            "sidebar_count": len(sidebars),
        }

    def _extract_semantic_context(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract semantic structure information."""
        # Get landmarks
        landmarks = {
            "main": len(soup.find_all(["main", lambda tag: tag.get("role") == "main"])),
            "nav": len(
                soup.find_all(["nav", lambda tag: tag.get("role") == "navigation"])
            ),
            "aside": len(
                soup.find_all(["aside", lambda tag: tag.get("role") == "complementary"])
            ),
            "header": len(
                soup.find_all(["header", lambda tag: tag.get("role") == "banner"])
            ),
            "footer": len(
                soup.find_all(["footer", lambda tag: tag.get("role") == "contentinfo"])
            ),
        }

        # Get heading structure
        headings = []
        for level in range(1, 7):
            elements = soup.find_all(f"h{level}")
            for h in elements:
                headings.append({"level": level, "text": h.get_text()[:50].strip()})

        return {
            "landmarks": landmarks,
            "heading_count": len(headings),
            "headings": headings[:10],  # First 10 headings
        }

    def _generate_validation_prompt(
        self,
        original_sequence: List[Dict[str, Any]],
        remediated_sequence: List[Dict[str, Any]],
        layout_context: Dict[str, Any],
        semantic_context: Dict[str, Any],
        changes: List[Dict[str, Any]],
        issues: List[Dict[str, Any]],
    ) -> str:
        """Generate prompt for Bedrock validation."""
        prompt = f"""You are an accessibility expert validating tab order optimization for WCAG 2.4.3 (Focus Order) compliance.

ORIGINAL TAB SEQUENCE ({len(original_sequence)} elements):
{json.dumps(original_sequence[:20], indent=2)}
{f"... and {len(original_sequence) - 20} more elements" if len(original_sequence) > 20 else ""}

ALGORITHMICALLY OPTIMIZED SEQUENCE ({len(remediated_sequence)} elements):
{json.dumps(remediated_sequence[:20], indent=2)}
{f"... and {len(remediated_sequence) - 20} more elements" if len(remediated_sequence) > 20 else ""}

CHANGES MADE ({len(changes)} changes):
{json.dumps(changes[:10], indent=2)}

LAYOUT CONTEXT:
- Multi-column layout: {layout_context['has_multi_column_layout']}
- Has sidebar: {layout_context['has_sidebar']}
- Has navigation: {layout_context['has_navigation']}

SEMANTIC CONTEXT:
- Landmarks: {json.dumps(semantic_context['landmarks'])}
- Heading structure: {len(semantic_context['headings'])} headings

ORIGINAL ISSUES DETECTED:
{json.dumps([{{'type': i['type'], 'severity': i['severity'], 'description': i['description']}} for i in issues[:5]], indent=2)}

TASK:
1. Verify the optimized tab order follows logical reading flow
2. Check if the changes preserve semantic meaning
3. Identify any remaining issues or edge cases
4. Consider special cases:
   - Multi-column layouts (should tab down columns or across?)
   - Sidebar placement (before or after main content?)
   - Skip navigation links (should be first)
   - Form field grouping (logical order within forms)
   - Modal dialogs (if present)

5. Suggest specific improvements if needed

RESPONSE FORMAT (JSON only, no additional text):
{{
  "is_valid": true/false,
  "confidence": 0.0-1.0,
  "issues_found": [
    {{
      "description": "Issue description",
      "severity": "critical/major/minor",
      "affected_elements": ["element identifiers"]
    }}
  ],
  "suggested_changes": [
    {{
      "type": "reorder/add_tabindex/remove_tabindex",
      "elements": ["element identifiers"],
      "new_order": [indexes],
      "reason": "Explanation"
    }}
  ],
  "reasoning": "Detailed explanation of validation results"
}}"""

        return prompt

    def _call_bedrock(self, prompt: str) -> Dict[str, Any]:
        """Call Bedrock API for validation."""
        try:
            # Prepare the request
            request_body = {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": 4000, "temperature": 0.3, "topP": 0.9},
            }

            # Call Bedrock
            response = self.bedrock_client.converse(
                modelId=self.model_id,
                messages=request_body["messages"],
                inferenceConfig=request_body["inferenceConfig"],
            )

            # Extract response text
            response_text = response["output"]["message"]["content"][0]["text"]

            # Parse JSON response
            # Try to extract JSON from response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
                return result
            else:
                raise ValueError("No JSON found in response")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Bedrock response as JSON: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            # Return a default valid response
            return {
                "is_valid": True,
                "confidence": 0.6,
                "issues_found": [],
                "suggested_changes": [],
                "reasoning": "Unable to parse AI response, accepting algorithmic changes",
            }

    def _apply_single_suggestion(
        self, soup: BeautifulSoup, suggestion: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Apply a single AI suggestion to the HTML."""
        suggestion_type = suggestion.get("type")
        elements = suggestion.get("elements", [])

        if suggestion_type == "reorder":
            # Reorder elements based on AI suggestion
            new_order = suggestion.get("new_order", [])
            if new_order and len(new_order) == len(elements):
                # Find and reorder elements
                element_tags = []
                for elem_id in elements:
                    element = (
                        soup.find(id=elem_id.split("#")[-1]) if "#" in elem_id else None
                    )
                    if element:
                        element_tags.append(element)

                if element_tags and len(element_tags) == len(new_order):
                    # Reorder based on new_order indexes
                    parent = element_tags[0].parent
                    position = list(parent.children).index(element_tags[0])

                    for element in element_tags:
                        element.extract()

                    for idx in new_order:
                        if idx < len(element_tags):
                            parent.insert(position, element_tags[idx])
                            position += 1

                    return {
                        "type": "ai_reorder",
                        "elements": elements,
                        "reason": suggestion.get("reason", "AI-suggested reordering"),
                        "confidence": suggestion.get("confidence", 0.8),
                    }

        elif suggestion_type == "add_tabindex":
            # Add tabindex to elements
            for elem_id in elements:
                element = (
                    soup.find(id=elem_id.split("#")[-1]) if "#" in elem_id else None
                )
                if element:
                    element["tabindex"] = suggestion.get("value", "0")

            return {
                "type": "ai_tabindex_added",
                "elements": elements,
                "value": suggestion.get("value", "0"),
                "reason": suggestion.get("reason", "AI-suggested tabindex"),
            }

        elif suggestion_type == "remove_tabindex":
            # Remove tabindex from elements
            for elem_id in elements:
                element = (
                    soup.find(id=elem_id.split("#")[-1]) if "#" in elem_id else None
                )
                if element and element.has_attr("tabindex"):
                    del element["tabindex"]

            return {
                "type": "ai_tabindex_removed",
                "elements": elements,
                "reason": suggestion.get("reason", "AI-suggested removal"),
            }

        return None
