# WCAG 2.1 Quick Reference - Supported Criteria

**Content Accessibility Utility on AWS**

This is a condensed reference showing which WCAG 2.1 criteria are supported. For the complete coverage matrix, see [WCAG_2.1_COVERAGE_MATRIX.md](./WCAG_2.1_COVERAGE_MATRIX.md).

---

## Fully Supported Criteria (✅)

These criteria have **complete audit and remediation** support:

### Level A (9 criteria)

| ID | Name | Implementation |
|----|------|----------------|
| 1.1.1 | Non-text Content | AI-powered alt text generation (Bedrock vision models) |
| 1.3.1 | Info and Relationships | Headings, tables, forms, landmarks detection & fixes |
| 1.4.1 | Use of Color | 4 pattern detection types + programmatic fixes ✨ NEW |
| 2.4.1 | Bypass Blocks | Skip links and landmark detection/addition |
| 2.4.2 | Page Titled | Title detection and AI generation |
| 2.4.4 | Link Purpose | Generic link text detection + AI improvement |
| 3.1.1 | Language of Page | Lang attribute detection and addition |
| 3.3.2 | Labels or Instructions | Form label detection and generation |
| 4.1.2 | Name, Role, Value | ARIA attribute detection and addition |

### Level AA (4 criteria)

| ID | Name | Implementation |
|----|------|----------------|
| 1.4.3 | Contrast (Minimum) | CSS parser + 4.5:1 ratio + AI remediation ✨ ENHANCED |
| 1.4.11 | Non-text Contrast | UI components, icons, focus - 3:1 ratio ✨ NEW |
| 2.4.6 | Headings and Labels | Empty/uninformative heading detection |
| (Partial) | Various | See matrix for partial implementations |

### Level AAA (1 criterion)

| ID | Name | Implementation |
|----|------|----------------|
| 1.4.6 | Contrast (Enhanced) | 7:1 ratio support + AI remediation ✨ NEW |

---

## Partially Supported Criteria (🟡)

These criteria have **audit support** but limited or no remediation:

| ID | Level | Name | What's Supported |
|----|-------|------|------------------|
| 1.2.2 | A | Captions (Prerecorded) | Detects missing `<track>` elements |
| 1.3.5 | AA | Identify Input Purpose | Can add `autocomplete` attributes |
| 1.4.5 | AA | Images of Text | Can detect `<img>` elements |
| 1.4.13 | AA | Content on Hover or Focus | Can detect tooltips |
| 2.4.7 | AA | Focus Visible | Via 1.4.11 focus indicator checks |
| 2.4.9 | AAA | Link Purpose (Link Only) | Stricter version of 2.4.4 |
| 2.4.10 | AAA | Section Headings | Can detect heading presence |
| 2.5.3 | A | Label in Name | Can compare labels to visible text |
| 3.1.2 | AA | Language of Parts | Can detect missing `lang` on elements |
| 3.3.1 | A | Error Identification | Via 1.4.1 color-only error detection |
| 4.1.1 | A | Parsing | BeautifulSoup auto-fixes HTML |
| 4.1.3 | AA | Status Messages | Can add `role="alert"` |

---

## Coverage by Number

| Conformance Level | Total | Fully Supported | Partial | Coverage % |
|-------------------|-------|-----------------|---------|------------|
| **Level A** | 30 | 9 | 3 | 40% |
| **Level AA** | 20 | 4 | 4 | 40% |
| **Level AAA** | 28 | 1 | 0 | 4% |
| **Total** | 78 | 14 | 7 | 27% |

---

## By Principle

| Principle | Supported / Total | Key Strengths |
|-----------|-------------------|---------------|
| **1. Perceivable** | 11/31 | Images, headings, color, contrast |
| **2. Operable** | 4/25 | Navigation, links, skip links |
| **3. Understandable** | 3/19 | Language, forms, labels |
| **4. Robust** | 2/3 | ARIA, parsing |

---

## What's NEW in Latest Release ✨

### Enhanced Color Accessibility (WCAG 1.4.x)

1. **1.4.1 Use of Color (Level A)** - NEW
   - Detects 4 color-only patterns
   - Programmatic remediation

2. **1.4.3 Contrast Minimum (Level AA)** - ENHANCED
   - CSS style resolver (not just inline styles)
   - AI-powered remediation
   - Brand-aware color suggestions

3. **1.4.6 Contrast Enhanced (Level AAA)** - NEW
   - 7:1 ratio support
   - Optional AAA level checking

4. **1.4.11 Non-text Contrast (Level AA)** - NEW
   - UI components (buttons, inputs)
   - SVG icons
   - Focus indicators

### Technical Improvements

- **CSS Parser**: Analyzes external stylesheets, `<style>` tags
- **Computed Styles**: Resolves CSS cascade and specificity
- **No Browser Dependency**: Lightweight, fast, batch-friendly
- **31 New Unit Tests**: 100% passing

---

## Quick Usage

### Run Full Audit

```bash
content-accessibility audit document.html
```

All supported checks run automatically.

### Check Specific Levels

```python
# Level A only
auditor = AccessibilityAuditor(html_file='page.html', level='A')

# Level AA (includes A)
auditor = AccessibilityAuditor(html_file='page.html', level='AA')

# Level AAA (includes A, AA, AAA)
auditor = AccessibilityAuditor(html_file='page.html', level='AAA')
```

### Filter Results by Criterion

```python
report = auditor.audit()

# Get specific criterion
color_contrast_issues = [
    i for i in report['issues']
    if i['wcag'] == '1.4.3'
]

# Get all color-related
color_issues = [
    i for i in report['issues']
    if i['wcag'] in ['1.4.1', '1.4.3', '1.4.6', '1.4.11']
]
```

---

## What Requires Manual Testing

The following criteria **cannot be fully automated** and require human testing:

### Always Manual
- **Keyboard functionality** (2.1.1, 2.1.2) - Requires functional testing
- **Time-based media** (1.2.x) - Requires human-created captions
- **Content quality** - Alt text accuracy, reading order, etc.
- **Behavioral aspects** - Timing, context changes, etc.

### Future Automation Potential
- **Keyboard navigation** - With browser automation (Playwright)
- **Focus order** - With tab order testing
- **Responsive design** - With viewport testing
- **Images of text** - With OCR analysis

---

## Priority Recommendations

If expanding coverage, prioritize these high-impact criteria:

### Tier 1 - Quick Wins
1. ✅ **2.1.1 Keyboard** - Automated keyboard testing
2. ✅ **1.4.5 Images of Text** - OCR detection
3. ✅ **2.4.3 Focus Order** - Tab order validation

### Tier 2 - Medium Effort
4. ✅ **1.4.10 Reflow** - Responsive validation
5. ✅ **1.4.12 Text Spacing** - CSS spacing checks
6. ✅ **3.3.3 Error Suggestion** - AI error corrections

---

## Limitations

### Static Analysis Only
- Cannot test dynamic JavaScript behavior
- Cannot simulate user interactions
- Cannot test timing/animations

### No Browser Rendering (Yet)
- CSS `:hover` and `:focus` partially supported
- Responsive design not tested
- No visual regression testing

### Content Understanding
- AI helps but isn't perfect
- Cannot assess content appropriateness
- Cannot determine logical reading order

---

## Best Practices

1. **Use as First Pass** - Catches ~40% of issues automatically
2. **Manual Review Essential** - Human testing required for full compliance
3. **Combine with Other Tools** - Browser dev tools, screen readers
4. **Regular Testing** - Integrate into CI/CD
5. **User Testing** - Test with people with disabilities

---

## Resources

- **Complete Matrix**: [WCAG_2.1_COVERAGE_MATRIX.md](./WCAG_2.1_COVERAGE_MATRIX.md)
- **Color Features**: [color_accessibility.md](./color_accessibility.md)
- **API Guide**: [api_integration_guide.md](./api_integration_guide.md)
- **WCAG 2.1 Spec**: https://www.w3.org/WAI/WCAG21/quickref/

---

**Quick Tip**: Start with Level A and AA criteria (34 automated checks) for the best ROI on accessibility compliance!
