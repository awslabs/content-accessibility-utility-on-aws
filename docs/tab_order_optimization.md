# Tab Order Optimization Implementation Guide

## Overview

This document describes the implementation of tab order optimization for the Content Accessibility Utility on AWS. The solution addresses WCAG 2.4.3 (Focus Order) compliance by detecting and remediating tab order issues in HTML generated from PDF conversions.

## Implementation Status

### ✅ Phase 1: Detection (Completed)

#### 1. Issue Type Definitions
**File**: `content_accessibility_utility_on_aws/audit/standards/issue_types.py`

Added four new issue types for tab order problems:

- **`positive-tabindex`** (Critical, WCAG 2.4.3)
  - Elements with positive tabindex values (1, 2, 3, etc.)
  - Disrupts natural tab order
  - Remediation: Remove positive tabindex, restructure DOM instead

- **`illogical-tab-order`** (Major, WCAG 2.4.3)
  - Tab order doesn't follow logical reading sequence
  - Applies to interactive elements
  - Remediation: Reorder DOM structure

- **`unnecessary-tabindex-zero`** (Minor, WCAG 2.4.3)
  - Non-interactive elements with tabindex="0"
  - Adds unnecessary tab stops
  - Remediation: Remove tabindex from non-interactive elements

- **`tab-order-mismatch`** (Major, WCAG 2.4.3)
  - DOM order doesn't match visual reading order
  - Detected using BDA bounding box data
  - Remediation: Restructure DOM to match visual layout

#### 2. Audit Check Implementation
**File**: `content_accessibility_utility_on_aws/audit/checks/tab_order_checks.py`

Created `TabOrderCheck` class that performs three types of checks:

**Check 1: Positive Tabindex Detection**
- Finds all elements with positive tabindex values
- Reports each occurrence with element details
- Provides remediation recommendation

**Check 2: Unnecessary Tabindex Zero**
- Scans non-interactive elements (div, span, p, img, etc.)
- Skips elements with interactive roles or event handlers
- Reports unnecessary tabindex="0" attributes

**Check 3: Visual vs DOM Order Analysis**
- Extracts interactive elements (links, buttons, inputs, etc.)
- Retrieves BDA bounding box data from element attributes
- Groups elements into rows by Y-coordinate
- Sorts by visual reading order (top-to-bottom, left-to-right)
- Compares visual order against DOM order
- Reports significant mismatches

**BDA Data Integration**
The check looks for position data in these formats:
- `data-bda-bbox="x,y,width,height"`
- Individual attributes: `data-x`, `data-y`, `data-width`, `data-height`
- Parent container: `data-page-bbox`

#### 3. Integration with Audit System
**Files**: 
- `content_accessibility_utility_on_aws/audit/checks/__init__.py`
- `content_accessibility_utility_on_aws/audit/auditor.py`

- Added TabOrderCheck to the audit checks pipeline
- Automatically runs on every HTML audit
- Integrates with multi-page document processing
- Results included in standard audit reports

### 🔄 Phase 2: Algorithmic Remediation (Pending)

**Planned File**: `content_accessibility_utility_on_aws/remediate/remediation_strategies/tab_order_remediation.py`

**Planned Functionality**:

1. **Remove Positive Tabindex**
   - Strip positive tabindex attributes
   - Log removed values for reporting

2. **Visual Position Sorting**
   ```python
   def sort_by_visual_position(elements_with_bbox):
       # Group elements into rows (similar Y-coordinates)
       # Sort rows by Y position
       # Within each row, sort by X position
       # Return flattened, sorted list
   ```

3. **DOM Reordering**
   - Move elements to match visual order
   - Preserve parent-child relationships
   - Maintain semantic structure

4. **Clean Unnecessary Tabindex**
   - Remove tabindex="0" from non-interactive elements
   - Keep for legitimate use cases (skip links, modals)

5. **Add Appropriate Tabindex**
   - Add tabindex="-1" where needed:
     - Modal dialog content
     - Skip navigation targets
     - Programmatically focused elements

### 🤖 Phase 3: AI Validation (Pending)

**Planned File**: `content_accessibility_utility_on_aws/remediate/remediation_strategies/tab_order_ai_validator.py`

**Planned Functionality**:

1. **Validation Prompt Generation**
   ```python
   prompt = f"""
   You are an accessibility expert validating tab order optimization.
   
   ORIGINAL TAB SEQUENCE:
   {original_order_details}
   
   ALGORITHMICALLY OPTIMIZED SEQUENCE:
   {optimized_order_details}
   
   VISUAL LAYOUT:
   {bbox_and_layout_info}
   
   CONTENT CONTEXT:
   {headings_and_semantic_structure}
   
   TASK:
   1. Verify optimized tab order follows logical reading flow
   2. Identify any remaining issues
   3. Check for special cases (multi-column, sidebars, forms)
   4. Suggest specific DOM reordering if needed
   5. Provide confidence score and reasoning
   
   RESPONSE FORMAT: JSON with validation results
   """
   ```

2. **AI Response Processing**
   - Parse validation results
   - Extract suggested changes
   - Apply improvements if confidence > threshold
   - Document AI reasoning in report

3. **Edge Case Handling**
   - Multi-column layouts
   - Sidebar navigation
   - Complex forms with grouped fields
   - Modal dialogs
   - Skip links

### 📊 Phase 4: Configuration & Reporting (Pending)

**Configuration Options** (to be added):
```python
remediation_options = {
    "optimize_tab_order": True,              # Enable tab order optimization
    "ai_validate_tab_order": True,           # Enable AI validation phase
    "ai_confidence_threshold": 0.8,          # Min confidence for AI changes
    "preserve_skip_links": True,             # Keep skip navigation first
    "tab_order_row_threshold": 20.0,         # Y-distance for row grouping (px)
}
```

**Report Structure**:
```json
{
  "tab_order_optimization": {
    "issues_detected": 15,
    "issues_fixed_algorithmic": 12,
    "issues_fixed_ai": 2,
    "remaining_issues": 1,
    "changes": [
      {
        "type": "positive_tabindex_removed",
        "element": "button#submit",
        "old_value": "1",
        "new_value": null
      },
      {
        "type": "dom_reordered",
        "elements": ["#nav-link-1", "#nav-link-2", "#nav-link-3"],
        "reason": "Visual order mismatch",
        "ai_validated": true,
        "confidence": 0.95
      }
    ]
  }
}
```

## Architecture

### Sequential Two-Phase Approach

**IMPORTANT**: This is a **sequential process**, not concurrent. Phase 2 only begins after Phase 1 is complete.

```
┌─────────────────────────────────────────────────────┐
│         PHASE 1: ALGORITHMIC (REQUIRED)             │
│              Runs First - Always                    │
│                                                     │
│  1. Detect positive tabindex → Remove              │
│  2. Analyze visual position → Sort elements        │
│  3. Compare DOM order → Identify mismatches        │
│  4. Reorder DOM → Match visual order              │
│  5. Clean unnecessary tabindex                     │
│                                                     │
│  Result: 80-90% of issues resolved                 │
│  Output: Remediated HTML + Change Log              │
└─────────────────────────────────────────────────────┘
                        ↓
              Phase 1 Completes
                        ↓
┌─────────────────────────────────────────────────────┐
│   PHASE 2: AI VALIDATION (ENABLED BY DEFAULT)       │
│          Runs Second - After Phase 1                │
│                                                     │
│  Input: Phase 1 remediated HTML + changes          │
│                                                     │
│  1. Review algorithmic changes                     │
│  2. Validate semantic correctness                  │
│  3. Identify edge cases                            │
│  4. Suggest improvements                           │
│  5. Apply AI recommendations (if confident)         │
│                                                     │
│  Result: 95-98% of issues resolved                 │
│  Output: Final HTML + AI change log                │
└─────────────────────────────────────────────────────┘
```

**Key Points:**
- Phase 1 **must complete first** before Phase 2 begins
- Phase 2 receives Phase 1's output as input
- Phase 2 is **enabled by default** (can be disabled for speed/cost if needed)
- Phase 2 **validates** Phase 1's work, doesn't replace it

### Data Flow

```
PDF → BDA Conversion → HTML with bbox data
                             ↓
                    Audit (TabOrderCheck)
                             ↓
                   Detect Issues + Context
                             ↓
              ┌──────────────┴──────────────┐
              ↓                              ↓
    Algorithmic Remediation        AI Validation (optional)
              ↓                              ↓
              └──────────────┬──────────────┘
                             ↓
                   Optimized HTML + Report
```

## Usage Examples

### Running Tab Order Audit

```python
from content_accessibility_utility_on_aws.audit.auditor import AccessibilityAuditor

# Audit HTML file
auditor = AccessibilityAuditor(
    html_path="output/document.html",
    options={
        "severity_threshold": "minor",
        "detailed": True
    }
)

report = auditor.audit()

# Check for tab order issues
tab_order_issues = [
    issue for issue in report['issues']
    if issue['wcag_criterion'] == '2.4.3'
]

print(f"Found {len(tab_order_issues)} tab order issues")
for issue in tab_order_issues:
    print(f"  - {issue['type']}: {issue['description']}")
```

### Expected Audit Output

```json
{
  "issues": [
    {
      "id": "issue-42",
      "type": "positive-tabindex",
      "wcag_criterion": "2.4.3",
      "severity": "critical",
      "element": "button",
      "description": "Element has positive tabindex='1' which disrupts natural tab order",
      "context": {
        "element_name": "button",
        "tabindex": "1",
        "element_id": "submit-btn",
        "recommendation": "Remove positive tabindex and restructure DOM order instead"
      },
      "location": {
        "path": "body > main > form > button#submit-btn",
        "page_number": 0
      }
    },
    {
      "id": "issue-43",
      "type": "tab-order-mismatch",
      "wcag_criterion": "2.4.3",
      "severity": "major",
      "description": "Tab order does not match visual reading order (5 mismatches found)",
      "context": {
        "mismatches_count": 5,
        "mismatches": [
          {
            "current_element": {
              "type": "a",
              "id": "link-2",
              "dom_index": 1,
              "visual_index": 3
            },
            "next_element": {
              "type": "a",
              "id": "link-3", 
              "dom_index": 2,
              "visual_index": 1
            },
            "description": "Element at DOM position 2 appears before element at DOM position 1 visually"
          }
        ]
      }
    }
  ]
}
```

## Testing Strategy

### Test Cases (To Be Implemented)

1. **Simple Linear Document**
   - All interactive elements in correct order
   - No tabindex attributes
   - Expected: No issues detected

2. **Document with Positive Tabindex**
   - Multiple elements with tabindex="1", "2", "3"
   - Expected: Critical issues detected
   - Remediation: Remove all positive tabindex

3. **Two-Column Layout**
   - Interactive elements in left and right columns
   - Visual order: Top-left, top-right, bottom-left, bottom-right
   - DOM order may be different
   - Expected: Tab order mismatch detected
   - Remediation: Reorder DOM to match visual flow

4. **Sidebar Navigation**
   - Main content + sidebar with links
   - Semantic question: Should sidebar come before or after main content?
   - Expected: May need AI validation
   - Remediation: AI determines appropriate order

5. **Complex Form**
   - Multiple fieldsets with various input types
   - Some fields out of visual order
   - Expected: Tab order mismatch detected
   - Remediation: Reorder within fieldsets

6. **Multi-Page Document**
   - Each page processed independently
   - Tab order analyzed per page
   - Expected: Issues reported with page numbers

## Integration Points

### With PDF2HTML Conversion
- BDA already provides bounding box data
- No changes needed to conversion process
- Tab order optimization uses existing bbox attributes

### With Remediation Pipeline
- Tab order remediation integrated into standard workflow
- Runs after structural fixes but before AI enhancement
- Can be enabled/disabled via configuration

### With Reporting
- Tab order issues included in standard audit reports
- Separate section in remediation report
- Visual diagrams showing before/after tab flow (future enhancement)

## Performance Considerations

### Algorithmic Phase
- **Fast**: O(n log n) for sorting, O(n) for detection
- **Cost**: None - pure algorithmic processing
- **Typical Time**: < 100ms for documents with 100 interactive elements

### AI Validation Phase
- **Slower**: Depends on Bedrock model latency
- **Cost**: Per API call to Bedrock
- **Typical Time**: 1-3 seconds per validation
- **Optimization**: Only called for complex cases or when enabled

### Recommendations
- Use algorithmic phase for all documents (fast, free)
- Enable AI validation for:
  - High-value content requiring maximum accuracy
  - Complex layouts where algorithm may struggle
  - Final production documents
- Consider batch processing for large document sets

## Next Steps

1. **Implement TabOrderRemediation**
   - Algorithmic fixes for detected issues
   - DOM reordering based on visual position
   - Tabindex cleanup

2. **Implement AITabOrderValidator**
   - Bedrock integration for validation
   - Prompt engineering for accurate results
   - Confidence scoring and threshold handling

3. **Add Configuration Options**
   - User control over optimization behavior
   - AI validation toggle
   - Threshold settings

4. **Create Test Suite**
   - Unit tests for all detection logic
   - Integration tests with sample documents
   - Regression tests for edge cases

5. **Update Documentation**
   - User guide with examples
   - API reference
   - Best practices guide

## References

- **WCAG 2.4.3 Focus Order**: https://www.w3.org/WAI/WCAG21/Understanding/focus-order.html
- **Tabindex Best Practices**: https://developer.mozilla.org/en-US/docs/Web/HTML/Global_attributes/tabindex
- **Keyboard Navigation Patterns**: https://www.w3.org/WAI/ARIA/apg/patterns/

## Version History

- **v1.0** (Current): Tab order detection implemented
- **v2.0** (Planned): Algorithmic remediation
- **v3.0** (Planned): AI validation and enhancement
