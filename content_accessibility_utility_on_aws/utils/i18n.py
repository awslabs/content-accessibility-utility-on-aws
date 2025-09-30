# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Internationalization (i18n) support for the Content Accessibility Utility.

This module provides translation services for all user-facing text in the application.
It supports multiple languages and graceful fallback to English when translations
are missing.
"""

import json
from typing import Dict, Any, Optional
from pathlib import Path

from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)


class TranslationManager:
    """
    Manages translations for the application.
    
    Supports loading translation files and providing translated strings
    with fallback to English when translations are missing.
    """
    
    # Default and fallback language
    DEFAULT_LANGUAGE = "en"
    FALLBACK_LANGUAGE = "en"
    
    def __init__(self):
        """Initialize the translation manager."""
        self._translations: Dict[str, Dict[str, Any]] = {}
        self._current_language = self.DEFAULT_LANGUAGE
        self._locales_dir = self._get_locales_dir()
        
        # Load default language on initialization
        self._load_language(self.DEFAULT_LANGUAGE)
    
    def _get_locales_dir(self) -> Path:
        """Get the path to the locales directory."""
        # Locales directory is in the same package
        utils_dir = Path(__file__).parent
        locales_dir = utils_dir.parent / "locales"
        return locales_dir
    
    def _load_language(self, language_code: str) -> bool:
        """
        Load translations for a specific language.
        
        Args:
            language_code: ISO 639-1 language code (e.g., 'en', 'es', 'fr')
            
        Returns:
            True if loaded successfully, False otherwise
        """
        if language_code in self._translations:
            return True
        
        locale_file = self._locales_dir / f"{language_code}.json"
        
        if not locale_file.exists():
            logger.warning(f"Translation file not found: {locale_file}")
            return False
        
        try:
            with open(locale_file, 'r', encoding='utf-8') as f:
                self._translations[language_code] = json.load(f)
            logger.debug(f"Loaded translations for language: {language_code}")
            return True
        except Exception as e:
            logger.error(f"Error loading translation file {locale_file}: {e}")
            return False
    
    def set_language(self, language_code: str) -> bool:
        """
        Set the current language.
        
        Args:
            language_code: ISO 639-1 language code (e.g., 'en', 'es', 'fr')
            
        Returns:
            True if language was set successfully, False otherwise
        """
        # Always ensure fallback language is loaded
        if self.FALLBACK_LANGUAGE not in self._translations:
            self._load_language(self.FALLBACK_LANGUAGE)
        
        # Try to load the requested language
        if language_code != self.FALLBACK_LANGUAGE:
            if not self._load_language(language_code):
                logger.warning(
                    f"Could not load language '{language_code}', "
                    f"falling back to '{self.FALLBACK_LANGUAGE}'"
                )
                self._current_language = self.FALLBACK_LANGUAGE
                return False
        
        self._current_language = language_code
        logger.debug(f"Current language set to: {language_code}")
        return True
    
    def get_language(self) -> str:
        """Get the current language code."""
        return self._current_language
    
    def _get_nested_value(self, data: Dict[str, Any], key_path: str) -> Optional[Any]:
        """
        Get a nested value from a dictionary using dot notation.
        
        Args:
            data: Dictionary to search
            key_path: Dot-separated path to the value (e.g., 'cli.conversion_results')
            
        Returns:
            The value if found, None otherwise
        """
        keys = key_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current
    
    def translate(self, key: str, **kwargs) -> str:
        """
        Get a translated string for the given key.
        
        Args:
            key: Translation key in dot notation (e.g., 'cli.conversion_results')
            **kwargs: Format parameters for the translated string
            
        Returns:
            Translated string with format parameters applied, or the key itself if not found
        """
        # Try current language first
        translation = self._get_nested_value(
            self._translations.get(self._current_language, {}),
            key
        )
        
        # Fall back to default language if not found
        if translation is None and self._current_language != self.FALLBACK_LANGUAGE:
            translation = self._get_nested_value(
                self._translations.get(self.FALLBACK_LANGUAGE, {}),
                key
            )
        
        # If still not found, return the key itself as a fallback
        if translation is None:
            logger.debug(f"Translation not found for key: {key}")
            return key
        
        # Apply format parameters if provided
        if kwargs:
            try:
                return translation.format(**kwargs)
            except KeyError as e:
                logger.warning(f"Missing format parameter for key '{key}': {e}")
                return translation
        
        return translation
    
    def get_available_languages(self) -> list[str]:
        """
        Get a list of available language codes.
        
        Returns:
            List of ISO 639-1 language codes
        """
        if not self._locales_dir.exists():
            return [self.DEFAULT_LANGUAGE]
        
        languages = []
        for file in self._locales_dir.glob("*.json"):
            language_code = file.stem
            languages.append(language_code)
        
        return sorted(languages)
    
    def get_language_name(self, language_code: str) -> str:
        """
        Get the native name of a language.
        
        Args:
            language_code: ISO 639-1 language code
            
        Returns:
            Native language name or the code if not found
        """
        # Common language names - can be extended
        language_names = {
            "en": "English",
            "es": "Español",
            "fr": "Français",
            "de": "Deutsch",
            "it": "Italiano",
            "pt": "Português",
            "ja": "日本語",
            "zh": "中文",
            "ko": "한국어",
            "ar": "العربية",
            "ru": "Русский",
        }
        return language_names.get(language_code, language_code)


# Global translation manager instance
_translation_manager = None


def get_translation_manager() -> TranslationManager:
    """
    Get the global translation manager instance.
    
    Returns:
        TranslationManager instance
    """
    global _translation_manager
    if _translation_manager is None:
        _translation_manager = TranslationManager()
    return _translation_manager


def translate(key: str, language: Optional[str] = None, **kwargs) -> str:
    """
    Convenience function to get a translated string.
    
    Args:
        key: Translation key in dot notation (e.g., 'cli.conversion_results')
        language: Optional language code to use (if None, uses current language)
        **kwargs: Format parameters for the translated string
        
    Returns:
        Translated string with format parameters applied
    """
    tm = get_translation_manager()
    
    # Temporarily switch language if specified
    if language is not None:
        original_language = tm.get_language()
        tm.set_language(language)
        result = tm.translate(key, **kwargs)
        tm.set_language(original_language)
        return result
    
    return tm.translate(key, **kwargs)


def set_language(language_code: str) -> bool:
    """
    Set the current language globally.
    
    Args:
        language_code: ISO 639-1 language code (e.g., 'en', 'es', 'fr')
        
    Returns:
        True if language was set successfully, False otherwise
    """
    tm = get_translation_manager()
    return tm.set_language(language_code)


def get_language() -> str:
    """
    Get the current language code.
    
    Returns:
        Current ISO 639-1 language code
    """
    tm = get_translation_manager()
    return tm.get_language()


def get_available_languages() -> list[str]:
    """
    Get a list of available language codes.
    
    Returns:
        List of ISO 639-1 language codes
    """
    tm = get_translation_manager()
    return tm.get_available_languages()


def get_language_name(language_code: str) -> str:
    """
    Get the native name of a language.
    
    Args:
        language_code: ISO 639-1 language code
        
    Returns:
        Native language name
    """
    tm = get_translation_manager()
    return tm.get_language_name(language_code)
