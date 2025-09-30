# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: MIT-0

"""
Unit tests for internationalization (i18n) functionality.
"""

import pytest
from content_accessibility_utility_on_aws.utils.i18n import (
    translate,
    set_language,
    get_language,
    get_available_languages,
    TranslationManager
)
from content_accessibility_utility_on_aws.audit.standards.issue_types import (
    get_issue_description,
    get_issue_remediation,
    get_issue_info_translated
)


class TestTranslationManager:
    """Test TranslationManager functionality."""
    
    def test_singleton_pattern(self):
        """Test that TranslationManager follows singleton pattern."""
        manager1 = TranslationManager()
        manager2 = TranslationManager()
        assert manager1 is manager2
    
    def test_default_language(self):
        """Test default language is English."""
        # Use get_language() function instead of accessing private attribute
        assert get_language() == "en"
    
    def test_available_languages(self):
        """Test available languages include en, es, fr."""
        languages = get_available_languages()
        assert "en" in languages
        assert "es" in languages
        assert "fr" in languages
    
    def test_set_language(self):
        """Test setting language."""
        set_language("es")
        assert get_language() == "es"
        
        set_language("fr")
        assert get_language() == "fr"
        
        # Reset to English
        set_language("en")
        assert get_language() == "en"


class TestTranslation:
    """Test translation functionality."""
    
    def test_english_translation(self):
        """Test English translations."""
        set_language("en")
        
        assert translate("cli.conversion_results") == "Conversion Results:"
        assert translate("cli.audit_results") == "Audit Results:"
        assert translate("ui.process_button") == "Process Document"
    
    def test_spanish_translation(self):
        """Test Spanish translations."""
        set_language("es")
        
        assert translate("cli.conversion_results") == "Resultados de Conversión:"
        assert translate("cli.audit_results") == "Resultados de Auditoría:"
        assert translate("ui.process_button") == "Procesar Documento"
        
        # Reset to English
        set_language("en")
    
    def test_french_translation(self):
        """Test French translations."""
        set_language("fr")
        
        assert translate("cli.conversion_results") == "Résultats de Conversion :"
        assert translate("cli.audit_results") == "Résultats d'Audit :"
        assert translate("ui.process_button") == "Traiter le Document"
        
        # Reset to English
        set_language("en")
    
    def test_parameter_substitution(self):
        """Test parameter substitution in translations."""
        set_language("en")
        
        result = translate("cli.main_html", path="/path/to/file.html")
        assert "/path/to/file.html" in result
        assert "Main HTML:" in result
        
        result = translate("cli.total_html_files", count=5)
        assert "5" in result
        assert "Total HTML files:" in result
    
    def test_missing_translation_fallback(self):
        """Test fallback for missing translations."""
        set_language("en")
        
        # Non-existent key should return the key itself
        result = translate("nonexistent.key")
        assert result == "nonexistent.key"
    
    def test_missing_language_fallback(self):
        """Test fallback to English for missing language."""
        # Set to non-existent language
        set_language("de")  # German not implemented
        
        # Should fall back to English
        result = translate("cli.conversion_results")
        assert result == "Conversion Results:"
        
        # Reset to English
        set_language("en")


class TestIssueTypeTranslations:
    """Test issue type translation functionality."""
    
    def test_get_issue_description_english(self):
        """Test getting issue description in English."""
        set_language("en")
        
        desc = get_issue_description("missing-alt-text")
        assert desc == "Image missing alternative text"
        
        desc = get_issue_description("missing-page-title")
        assert desc == "Page missing title element"
    
    def test_get_issue_description_spanish(self):
        """Test getting issue description in Spanish."""
        set_language("es")
        
        desc = get_issue_description("missing-alt-text")
        assert desc == "Imagen sin texto alternativo"
        
        desc = get_issue_description("missing-page-title")
        assert desc == "Página sin elemento de título"
        
        # Reset to English
        set_language("en")
    
    def test_get_issue_description_french(self):
        """Test getting issue description in French."""
        set_language("fr")
        
        desc = get_issue_description("missing-alt-text")
        assert desc == "Image sans texte alternatif"
        
        desc = get_issue_description("missing-page-title")
        assert desc == "Page sans élément de titre"
        
        # Reset to English
        set_language("en")
    
    def test_get_issue_remediation_english(self):
        """Test getting issue remediation in English."""
        set_language("en")
        
        remediation = get_issue_remediation("missing-alt-text")
        assert remediation == "Add descriptive alt text to the image"
        
        remediation = get_issue_remediation("missing-page-title")
        assert remediation == "Add descriptive title element to document"
    
    def test_get_issue_info_translated(self):
        """Test getting complete issue info with translations."""
        set_language("en")
        
        info = get_issue_info_translated("missing-alt-text")
        assert info["description"] == "Image missing alternative text"
        assert info["remediation"] == "Add descriptive alt text to the image"
        assert info["severity"] == "critical"
        assert info["wcag"] == "1.1.1"
    
    def test_issue_description_fallback(self):
        """Test fallback for non-existent issue type."""
        desc = get_issue_description("non-existent-issue")
        # Should return the issue type itself as fallback
        assert desc == "non-existent-issue"


class TestMultipleLanguageSwitching:
    """Test switching between multiple languages."""
    
    def test_language_switching(self):
        """Test switching languages multiple times."""
        # Start with English
        set_language("en")
        assert translate("cli.process_completed") == "Process completed successfully!"
        
        # Switch to Spanish
        set_language("es")
        assert translate("cli.process_completed") == "¡Proceso completado exitosamente!"
        
        # Switch to French
        set_language("fr")
        assert translate("cli.process_completed") == "Processus terminé avec succès !"
        
        # Switch back to English
        set_language("en")
        assert translate("cli.process_completed") == "Process completed successfully!"


class TestReportTranslations:
    """Test report-related translations."""
    
    def test_report_sections_english(self):
        """Test report section translations in English."""
        set_language("en")
        
        assert translate("reports.audit_summary") == "Audit Summary"
        assert translate("reports.remediation_summary") == "Remediation Summary"
        assert translate("reports.severity") == "Severity"
        assert translate("reports.status") == "Status"
    
    def test_report_sections_spanish(self):
        """Test report section translations in Spanish."""
        set_language("es")
        
        assert translate("reports.audit_summary") == "Resumen de Auditoría"
        assert translate("reports.remediation_summary") == "Resumen de Remediación"
        assert translate("reports.severity") == "Gravedad"
        assert translate("reports.status") == "Estado"
        
        # Reset to English
        set_language("en")


class TestErrorTranslations:
    """Test error message translations."""
    
    def test_error_messages_english(self):
        """Test error message translations in English."""
        set_language("en")
        
        msg = translate("errors.file_not_found", path="/test/file.pdf")
        assert "File not found" in msg
        assert "/test/file.pdf" in msg
        
        msg = translate("errors.conversion_failed", reason="Invalid format")
        assert "Conversion failed" in msg
        assert "Invalid format" in msg
    
    def test_error_messages_spanish(self):
        """Test error message translations in Spanish."""
        set_language("es")
        
        msg = translate("errors.file_not_found", path="/test/file.pdf")
        assert "Archivo no encontrado" in msg
        assert "/test/file.pdf" in msg
        
        # Reset to English
        set_language("en")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
