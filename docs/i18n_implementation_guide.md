# Internationalization (i18n) Implementation Guide

## Overview

This document describes the internationalization implementation for the Content Accessibility Utility on AWS. The solution enables multi-lingual support across all three usage modes: API, CLI, and Streamlit app.

## Architecture

### Core Components

1. **Translation Manager** (`content_accessibility_utility_on_aws/utils/i18n.py`)
   - Manages loading and accessing translation files
   - Provides fallback to English when translations are missing
   - Supports dot notation for accessing nested translations (e.g., `cli.conversion_results`)

2. **Translation Files** (`content_accessibility_utility_on_aws/locales/*.json`)
   - JSON format for easy editing and extension
   - Organized by functional area (CLI, issues, reports, UI, errors, etc.)
   - Default language: English (`en.json`)

3. **Configuration** (`config_defaults.yaml`)
   - Default language setting: `en`
   - Fallback language setting: `en`

## Usage

### CLI Usage

```bash
# Use default language (English)
content-accessibilty-utility-on-aws process --input document.pdf

# Specify a different language
content-accessibilty-utility-on-aws process --input document.pdf --language es

# Short form
content-accessibilty-utility-on-aws process --input document.pdf -l fr
```

### API Usage

```python
from content_accessibility_utility_on_aws.api import process_pdf_accessibility

# Process with specific language
result = process_pdf_accessibility(
    pdf_path="document.pdf",
    output_dir="output/",
    language="es"  # Spanish
)
```

### Programmatic Language Control

```python
from content_accessibility_utility_on_aws.utils.i18n import set_language, translate

# Set global language
set_language("es")

# Get translated string
message = translate("cli.conversion_results")

# Get translated string with parameters
message = translate("cli.total_html_files", count=5)
```

## Translation File Structure

Translation files use a hierarchical structure with dot notation:

```json
{
  "cli": {
    "conversion_results": "Conversion Results:",
    "total_html_files": "Total HTML files: {count}"
  },
  "issues": {
    "missing-alt-text": {
      "description": "Image missing alternative text",
      "remediation": "Add descriptive alt text to the image"
    }
  },
  "reports": {
    "audit_summary": "Audit Summary",
    "total_issues": "Total Issues: {count}"
  }
}
```

### Translation Categories

1. **CLI Messages** (`cli.*`)
   - Command output messages
   - Progress indicators
   - Result summaries

2. **Issue Descriptions** (`issues.*`)
   - Accessibility issue types
   - Issue descriptions
   - Remediation guidance

3. **Report Content** (`reports.*`)
   - Report headers and labels
   - Summary text
   - Status indicators

4. **UI Text** (`ui.*`)
   - Streamlit interface labels
   - Button text
   - Form labels

5. **Error Messages** (`errors.*`)
   - Error descriptions
   - Exception messages

6. **Common Terms** (`common.*`)
   - Frequently used terms
   - Status values

## Adding a New Language

### 1. Create Translation File

Create a new JSON file in `content_accessibility_utility_on_aws/locales/`:

```bash
# Example: Adding Spanish
cp content_accessibility_utility_on_aws/locales/en.json \
   content_accessibility_utility_on_aws/locales/es.json
```

### 2. Translate Content

Edit the new file and translate all strings:

```json
{
  "cli": {
    "conversion_results": "Resultados de la conversión:",
    "total_html_files": "Total de archivos HTML: {count}"
  }
}
```

### 3. Test the Translation

```bash
content-accessibilty-utility-on-aws process --input test.pdf --language es
```

## Implementation Status

### ✅ Completed

1. Core i18n infrastructure
   - Translation Manager class
   - Translation loading and caching
   - Fallback mechanism
   - Nested value access with dot notation

2. Translation file structure
   - English baseline (`en.json`)
   - All user-facing strings cataloged
   - Organized by functional area

3. Configuration system
   - Language parameter in config defaults
   - Configuration file support

4. CLI integration
   - `--language/-l` parameter added
   - Language setting on startup
   - Ready for message translation

### 🔄 Remaining Work

1. **Complete CLI Translation Integration**
   - Replace hardcoded strings with `translate()` calls
   - Update print statements to use translations
   - Test all CLI commands with different languages

2. **API Integration**
   - Add `language` parameter to all public API functions
   - Pass language through to report generators
   - Update return message strings

3. **Issue Types Translation**
   - Update `issue_types.py` to use i18n for descriptions
   - Maintain backward compatibility
   - Keep WCAG codes unchanged

4. **Report Generation Translation**
   - Update HTML template with translation markers
   - Translate report headers and summaries
   - Support language parameter in generators

5. **Streamlit Integration**
   - Add language selector to sidebar
   - Store language in session state
   - Translate all UI elements
   - Update tab labels and messages

6. **Testing**
   - Unit tests for i18n module
   - Integration tests for each usage mode
   - Test fallback behavior
   - Test with missing translations

7. **Documentation**
   - Update README with language examples
   - Add translation guide
   - Document available languages
   - Add contributor guidelines for translations

## Translation Best Practices

### 1. String Format Parameters

Use named parameters for dynamic content:

```json
{
  "message": "Found {count} issues in {filename}"
}
```

Usage:
```python
translate("message", count=5, filename="test.html")
```

### 2. Keep WCAG References Unchanged

WCAG criterion codes should remain in English:

```json
{
  "issues": {
    "missing-alt-text": {
      "wcag": "1.1.1",  // Keep as-is
      "description": "Imagen sin texto alternativo"  // Translate this
    }
  }
}
```

### 3. Context-Specific Translations

Provide context when the same word has different meanings:

```json
{
  "ui": {
    "file_noun": "File",
    "file_verb": "File"
  }
}
```

### 4. Maintain Consistent Terminology

Use a glossary to ensure consistency across translations:

- **Audit** → Auditoría (Spanish), Audit (French)
- **Remediate** → Remediar (Spanish), Corriger (French)
- **Issue** → Problema (Spanish), Problème (French)

## Language Support Roadmap

### Phase 1 (Current)
- ✅ English (en)

### Phase 2 (Planned)
- [ ] Spanish (es)
- [ ] French (fr)
- [ ] German (de)

### Phase 3 (Future)
- [ ] Portuguese (pt)
- [ ] Japanese (ja)
- [ ] Chinese (zh)

## Notes for AI-Generated Content

The tool uses Amazon Bedrock for AI-generated content (alt text, remediation suggestions). Currently:

1. **Content Generation**: Performed in English (model training language)
2. **Optional Translation**: Generated content can be translated post-generation
3. **Limitation**: Quality depends on translation service
4. **Recommendation**: Document this limitation for users

## Example: Full Workflow with i18n

```python
from content_accessibility_utility_on_aws.utils.i18n import set_language, translate
from content_accessibility_utility_on_aws.api import process_pdf_accessibility

# Set language to Spanish
set_language("es")

# Process document
result = process_pdf_accessibility(
    pdf_path="document.pdf",
    output_dir="output/",
    language="es"
)

# Get translated status message
status = translate("status.completed")
print(f"{status}: {result['conversion_result']['html_path']}")
```

## Contributing Translations

To contribute a new language translation:

1. Fork the repository
2. Create a new translation file: `locales/{language_code}.json`
3. Translate all strings from `en.json`
4. Test the translation with CLI, API, and Streamlit
5. Submit a pull request

Translation guidelines:
- Maintain the same JSON structure
- Keep format parameters (e.g., `{count}`, `{path}`)
- Preserve WCAG codes and technical terms where appropriate
- Test with actual use cases

## Support and Resources

- Translation issues: Use `/reportbug` in Cline
- Language requests: Open a GitHub issue
- Translation updates: Submit pull requests
- Questions: Refer to project documentation

## License

All translations are released under the same license as the main project (Apache-2.0).
