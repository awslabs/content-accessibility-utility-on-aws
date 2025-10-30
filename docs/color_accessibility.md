# Color Accessibility Features (WCAG 2.1)

This document describes the comprehensive color accessibility features implemented in the Content Accessibility Utility.

## Overview

The utility now provides extensive WCAG 2.1 color accessibility compliance checking and remediation, covering:

- **Enhanced Color Contrast Detection** (WCAG 1.4.3, 1.4.6)
- **Use of Color Detection** (WCAG 1.4.1)
- **Non-Text Contrast Detection** (WCAG 1.4.11)
- **AI-Powered Color Remediation**

## Features by WCAG Criterion

### 1.4.1 Use of Color (Level A)

**Purpose**: Ensures that color is not the only visual means of conveying information.

**What's Detected:**
- Required field indicators (red asterisks without `aria-required`)
- Links distinguished from text only by color (no underline)
- Form validation errors shown only in red
- Status badges/indicators using only color coding

**Example Issues:**
```html
<!-- BAD: Red asterisk without aria-required -->
<label>Name <span style="color: red;">*</span></label>
<input type="text">

<!-- GOOD: Multiple indicators -->
<label>Name <span style="color: red;">*</span> (required)</label>
<input type="text" aria-required="true">

<!-- BAD: Link only distinguished by color -->
<p>Visit our <a href="#" style="color: blue; text-decoration: none;">website</a></p>

<!-- GOOD: Link has underline -->
<p>Visit our <a href="#" style="color: blue; text-decoration: underline;">website</a></p>
```

**Remediation:**
- Adds `required` and `aria-required` attributes
- Adds visible "(required)" text labels
- Adds underlines to links
- Adds error icons and "Error:" prefix to validation messages
- Adds explicit status text or icons to badges

### 1.4.3 Contrast (Minimum) - Level AA

**Purpose**: Ensures text has sufficient contrast with its background.

**Requirements:**
- Normal text: 4.5:1 contrast ratio
- Large text (18pt+ or 14pt+ bold): 3:1 contrast ratio

**What's Detected:**
- Insufficient text/background contrast
- Uses **computed CSS styles** (not just inline)
- Parses `<style>` tags and external stylesheets
- Resolves CSS cascade and specificity

**Example Issues:**
```html
<!-- BAD: Low contrast (2.5:1) -->
<p style="color: #999; background: #FFF;">Low contrast text</p>

<!-- GOOD: High contrast (4.5:1+) -->
<p style="color: #595959; background: #FFF;">Readable text</p>
```

**Remediation:**
- Programmatic: Adjusts to black/white for guaranteed contrast
- AI-Powered: Suggests accessible colors maintaining brand identity

### 1.4.6 Contrast (Enhanced) - Level AAA

**Purpose**: Higher contrast for better readability.

**Requirements:**
- Normal text: 7:1 contrast ratio
- Large text: 4.5:1 contrast ratio

**What's Detected:**
- Enabled when `contrast_level='AAA'` is set
- Same detection as 1.4.3 but with stricter thresholds

### 1.4.11 Non-text Contrast (Level AA)

**Purpose**: Ensures UI components and graphical objects are perceivable.

**Requirements:**
- UI components: 3:1 contrast ratio
- Graphical objects: 3:1 contrast ratio
- Focus indicators: 3:1 contrast ratio

**What's Detected:**
- Button and input borders/backgrounds
- SVG icon fills and strokes
- Focus indicator outlines

**Example Issues:**
```html
<!-- BAD: Light gray button on white background -->
<button style="border: 1px solid #DDD; background: #FFF;">Click</button>

<!-- GOOD: Dark border for visibility -->
<button style="border: 2px solid #000; background: #FFF;">Click</button>

<!-- BAD: Light icon on white background -->
<svg fill="#E0E0E0"><circle cx="12" cy="12" r="10"/></svg>

<!-- GOOD: Dark icon for visibility -->
<svg fill="#000000"><circle cx="12" cy="12" r="10"/></svg>
```

**Remediation:**
- Adjusts border colors to meet 3:1 ratio
- Adjusts SVG fill/stroke colors
- Enhances focus indicator visibility

## Technical Architecture

### CSS Style Resolution

**Component**: `utils/style_resolver.py`

The `StyleResolver` class extracts computed styles from:
- Inline styles (`style="..."`)
- `<style>` tags in HTML
- External CSS files (when provided)

**Key Features:**
- CSS specificity calculation
- Cascade resolution (inline > stylesheet > default)
- Color normalization (hex, rgb(), named colors)
- Font size and weight extraction

**Usage:**
```python
from content_accessibility_utility_on_aws.utils.style_resolver import StyleResolver

soup = BeautifulSoup(html, 'html.parser')
resolver = StyleResolver(soup, stylesheet_paths=['styles.css'])

element = soup.find('p')
text_color = resolver.get_text_color(element)      # Returns '#000000'
bg_color = resolver.get_background_color(element)  # Returns '#FFFFFF'
```

### Audit Checks

**Enhanced Checks:**
- `ColorContrastCheck` - Text contrast (AA/AAA)
- `NonTextContrastCheck` - UI component contrast
- `ColorUsageCheck` - Use of color detection

**Check Registration:**
All checks are automatically registered in `audit/auditor.py` and run on every audit.

**Customization:**
```python
# AA level (default)
ColorContrastCheck(soup, callback, contrast_level='AA')

# AAA level
ColorContrastCheck(soup, callback, contrast_level='AAA')

# With external stylesheets
ColorContrastCheck(soup, callback, stylesheet_paths=['style.css'])
```

### Remediation Strategies

**Files:**
- `color_contrast_remediation.py` - Text contrast fixes
- `color_usage_remediation.py` - Color-only indication fixes
- `ui_contrast_remediation.py` - UI component fixes

**Remediation Types:**

1. **Programmatic (Default)**
   - Fast, deterministic fixes
   - Uses WCAG formulas for guaranteed compliance
   - No AI required

2. **AI-Powered (Optional)**
   - Uses Amazon Bedrock for intelligent suggestions
   - Maintains brand identity
   - Considers design context

**AI-Powered Example:**
```python
from content_accessibility_utility_on_aws.remediate.services.bedrock_client import BedrockClient
from content_accessibility_utility_on_aws.remediate.remediation_strategies.color_contrast_remediation import (
    remediate_insufficient_color_contrast_ai
)

# Initialize Bedrock client
bedrock = BedrockClient(model_id='us.amazon.nova-lite-v1:0')

# Define brand colors
brand_colors = {
    'primary': '#1E3A8A',   # Dark blue
    'secondary': '#F59E0B'  # Orange
}

# Remediate with AI
result = remediate_insufficient_color_contrast_ai(
    soup,
    issue,
    bedrock_client=bedrock,
    brand_colors=brand_colors
)
# AI suggests: "Use #1F4B9C (slightly lighter blue) for 4.5:1 contrast"
```

## Issue Types

New issue types added:

| Issue Type | WCAG | Severity | Description |
|------------|------|----------|-------------|
| `insufficient-color-contrast` | 1.4.3 | major | Text contrast < 4.5:1 (AA) |
| `insufficient-color-contrast-aaa` | 1.4.6 | minor | Text contrast < 7:1 (AAA) |
| `potential-color-contrast-issue` | 1.4.3 | minor | Colors couldn't be determined |
| `color-only-indication` | 1.4.1 | major | Information conveyed by color alone |
| `insufficient-ui-component-contrast` | 1.4.11 | major | UI component contrast < 3:1 |
| `insufficient-icon-contrast` | 1.4.11 | major | Icon/graphic contrast < 3:1 |
| `insufficient-focus-indicator-contrast` | 1.4.11 | major | Focus indicator contrast < 3:1 |

## Usage Examples

### Basic Audit

```bash
# Run audit with color checks (AA level by default)
content-accessibility audit input.html -o report.json
```

### Programmatic Usage

```python
from content_accessibility_utility_on_aws.audit.auditor import AccessibilityAuditor

# Create auditor
auditor = AccessibilityAuditor(html_file='document.html')

# Run audit
report = auditor.audit()

# Filter for color issues
color_issues = [
    issue for issue in report['issues']
    if issue['wcag'] in ['1.4.1', '1.4.3', '1.4.6', '1.4.11']
]

print(f"Found {len(color_issues)} color accessibility issues")
```

### With Remediation

```python
from content_accessibility_utility_on_aws.remediate.api import remediate_html

# Remediate color issues
result = remediate_html(
    html_file='document.html',
    output_file='remediated.html'
)

print(f"Remediated {result['remediations_applied']} issues")
```

## Testing

Comprehensive unit tests are provided in `tests/`:

```bash
# Run all color accessibility tests
pytest tests/test_color_contrast_checks.py
pytest tests/test_color_usage_checks.py
pytest tests/test_style_resolver.py

# Run all tests
pytest tests/
```

**Test Coverage:**
- 31 unit tests
- 100% pass rate
- Tests for all check types
- Tests for remediation strategies
- Tests for style resolution

## Performance Considerations

### CSS Parsing

The `StyleResolver` parses CSS without browser rendering:
- **Pros**: Lightweight, no external dependencies
- **Cons**: May miss complex CSS features (e.g., `:focus` pseudo-classes)
- **Recommendation**: Works well for most use cases; browser rendering available as future enhancement

### AI Remediation

AI-powered remediation adds latency and cost:
- **Latency**: ~2-5 seconds per issue
- **Cost**: Based on Bedrock token usage
- **Recommendation**: Use for high-value content or when brand consistency is critical

### Batch Processing

For large documents:
- Checks run in parallel where possible
- CSS is parsed once per document
- AI calls can be batched or disabled

## Limitations

1. **CSS Pseudo-classes**: Cannot detect `:hover`, `:focus` states without browser rendering
2. **Dynamic Styles**: JavaScript-applied styles not analyzed
3. **External Resources**: External stylesheets must be provided explicitly
4. **Image Text**: Cannot analyze text within images (consider OCR as future enhancement)

## Future Enhancements

Potential improvements:
- Browser rendering integration (Playwright) for complete CSS support
- Screenshot analysis with vision models for visual verification
- Automatic brand color extraction from existing design
- Color blindness simulation
- Interactive color picker for manual remediation

## Resources

- [WCAG 2.1 Understanding 1.4.1 Use of Color](https://www.w3.org/WAI/WCAG21/Understanding/use-of-color.html)
- [WCAG 2.1 Understanding 1.4.3 Contrast (Minimum)](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html)
- [WCAG 2.1 Understanding 1.4.6 Contrast (Enhanced)](https://www.w3.org/WAI/WCAG21/Understanding/contrast-enhanced.html)
- [WCAG 2.1 Understanding 1.4.11 Non-text Contrast](https://www.w3.org/WAI/WCAG21/Understanding/non-text-contrast.html)

## Support

For issues or questions:
- Check the main documentation in `docs/`
- Review code comments in source files
- Examine test cases in `tests/`
