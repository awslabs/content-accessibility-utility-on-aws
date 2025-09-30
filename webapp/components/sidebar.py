# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Sidebar components for the Document Accessibility Streamlit application.
"""

import streamlit as st
from typing import Dict, Any, Tuple, Optional

from content_accessibility_utility_on_aws import __version__ as current_version
from content_accessibility_utility_on_aws.utils.i18n import (
    set_language,
    get_available_languages,
    translate,
    get_language
)
from utils.file_utils import detect_file_type


# Language name mapping
LANGUAGE_NAMES = {
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "pt": "Português",
    "it": "Italiano",
    "ja": "日本語",
    "zh": "中文"
}


def create_sidebar() -> (
    Tuple[Optional[st.runtime.uploaded_file_manager.UploadedFile], Dict[str, Any], bool]
):
    """
    Create the sidebar with file upload, processing options, and configuration.

    Returns:
        Tuple containing:
        - Uploaded file object or None
        - Dictionary of processing options
        - Boolean indicating whether the process button was clicked
    """
    with st.sidebar:
        # Language selector at the top
        available_languages = get_available_languages()
        current_language = get_language()
        
        # Ensure current language is in session state
        if 'language' not in st.session_state:
            st.session_state['language'] = current_language
        
        language_options = {code: LANGUAGE_NAMES.get(code, code) for code in available_languages}
        selected_language = st.selectbox(
            translate("ui.select_language"),
            options=available_languages,
            format_func=lambda x: language_options[x],
            index=available_languages.index(st.session_state['language']) if st.session_state['language'] in available_languages else 0,
            key="language_selector"
        )
        
        # Update language if changed
        if selected_language != st.session_state['language']:
            set_language(selected_language)
            st.session_state['language'] = selected_language
            st.rerun()
        
        st.title(translate("ui.document_accessibility_title"))
        st.markdown(translate("ui.upload_document_description"))

        # File uploader widget - accepts PDF, HTML, and ZIP files
        uploaded_file = st.file_uploader(
            translate("ui.choose_document"),
            type=["pdf", "html", "zip"],
            help=translate("ui.upload_help"),
        )

        # Determine file type (if file is uploaded)
        file_type = None
        if uploaded_file is not None:
            file_type = detect_file_type(uploaded_file.name)

        # Processing options in sidebar
        processing_options = get_processing_options(file_type)

        # Process button
        process_button = st.button(translate("ui.process_button"), type="primary")

        st.markdown(f"Using document-accessibility v{current_version}")
        st.markdown("Bedrock Model: `amazon.nova-lite-v1:0`")

        return uploaded_file, processing_options, process_button


def get_processing_options(file_type: Optional[str]) -> Dict[str, Any]:
    """
    Get processing options based on file type.

    Args:
        file_type: Type of file ('pdf', 'html', 'zip', or None)

    Returns:
        Dictionary of processing options
    """
    st.header(translate("ui.processing_options"))

    # Processing mode selection
    if file_type == "pdf":
        processing_mode = st.radio(
            translate("ui.processing_mode"),
            options=[
                translate("ui.convert_only"),
                translate("ui.convert_audit"),
                translate("ui.full_processing")
            ],
            index=2,  # Default to Full Processing
            help=translate("ui.processing_mode_help"),
        )
    elif file_type in ["html", "zip"]:
        processing_mode = st.radio(
            translate("ui.processing_mode"),
            options=[
                translate("ui.audit_only"),
                translate("ui.audit_remediate")
            ],
            index=1,  # Default to Audit + Remediate
            help=translate("ui.processing_mode_help"),
        )
    else:
        # No file uploaded yet, show all options
        processing_mode = st.radio(
            translate("ui.processing_mode"),
            options=[
                translate("ui.convert_only"),
                translate("ui.convert_audit"),
                translate("ui.full_processing")
            ],
            index=2,  # Default to Full Processing
            help=translate("ui.processing_mode_help"),
        )

    # Determine processing flags based on selected mode
    # Compare against translated strings
    convert_audit = translate("ui.convert_audit")
    full_processing = translate("ui.full_processing")
    audit_remediate = translate("ui.audit_remediate")
    
    if file_type == "pdf":
        perform_audit = processing_mode in [convert_audit, full_processing]
        perform_remediation = processing_mode == full_processing
    else:  # HTML or ZIP
        perform_audit = True  # Always audit HTML/ZIP
        perform_remediation = processing_mode == audit_remediate

    options = {
        "processing_mode": processing_mode,
        "perform_audit": perform_audit,
        "perform_remediation": perform_remediation,
    }

    # PDF to HTML conversion options - only show if PDF is selected
    if file_type == "pdf" or file_type is None:
        with st.expander(translate("ui.conversion_options"), expanded=False):
            options["extract_images"] = st.checkbox(translate("ui.extract_images"), value=True)
            options["image_format"] = st.selectbox(
                translate("ui.image_format"), ["png", "jpg"], index=0
            )
            options["multiple_documents"] = st.checkbox(
                translate("ui.multiple_documents"), value=False
            )

    # Audit options
    with st.expander(translate("ui.audit_options"), expanded=False):
        options["check_images"] = st.checkbox(translate("ui.check_images"), value=True)
        options["check_headings"] = st.checkbox(translate("ui.check_headings"), value=True)
        options["check_links"] = st.checkbox(translate("ui.check_links"), value=True)
        options["check_tables"] = st.checkbox(translate("ui.check_tables"), value=True)
        options["severity_threshold"] = st.selectbox(
            translate("ui.severity_threshold"), ["error", "warning", "info"], index=1
        )

    # Remediation options - only show if remediation is part of selected mode
    if (
        (file_type == "pdf" and processing_mode == full_processing)
        or (file_type in ["html", "zip"] and processing_mode == audit_remediate)
        or (file_type is None)
    ):
        with st.expander(translate("ui.remediation_options"), expanded=False):
            options["fix_images"] = st.checkbox(translate("ui.fix_images"), value=True)
            options["fix_headings"] = st.checkbox(translate("ui.fix_headings"), value=True)
            options["fix_links"] = st.checkbox(translate("ui.fix_links"), value=True)

    # Cost calculation options
    with st.expander(translate("ui.cost_calculation_options"), expanded=False):
        # Retrieve current values from session state or use defaults
        # Get cost rates from session state
        # Price defaults are for Amazon Bedrock Data Automation (BDA) and Bedrock API using of
        # Amazon Nova Lite Model with on-demand in US East (N. Virginia) region as of 2025-04-01
        # These rates are subject to change, please refer to the official AWS pricing page for the most up-to-date information.
        # https://aws.amazon.com/bedrock/pricing/
        if "cost_per_bda_page" in st.session_state:
            cost_per_bda_page = st.session_state["cost_per_bda_page"]
        else:
            cost_per_bda_page = 0.01
            st.session_state["cost_per_bda_page"] = cost_per_bda_page

        if "cost_per_input_token" in st.session_state:
            cost_per_input_token = st.session_state["cost_per_input_token"]
        else:
            cost_per_input_token = 0.00006
            st.session_state["cost_per_input_token"] = cost_per_input_token

        if "cost_per_output_token" in st.session_state:
            cost_per_output_token = st.session_state["cost_per_output_token"]
        else:
            cost_per_output_token = 0.00024
            st.session_state["cost_per_output_token"] = cost_per_output_token

        # Display cost input fields
        new_cost_per_bda_page = st.number_input(
            translate("ui.cost_per_bda_page"),
            min_value=0.0,
            value=float(cost_per_bda_page),
            format="%.2f",
            help=translate("ui.cost_per_bda_page_help"),
        )

        new_cost_per_input_token = st.number_input(
            translate("ui.cost_per_input_token"),
            min_value=0.0,
            value=float(cost_per_input_token),
            format="%.6f",
            help=translate("ui.cost_per_input_token_help"),
        )

        new_cost_per_output_token = st.number_input(
            translate("ui.cost_per_output_token"),
            min_value=0.0,
            value=float(cost_per_output_token),
            format="%.6f",
            help=translate("ui.cost_per_output_token_help"),
        )
        st.caption(
            "Note: Default costs are base on AWS Pricing of Amazon Bedrock Data Automation & Amazon Bedrock Nova Lite Model with on-demand consumption in US East (N. Virginia) region as of 2025-04-01. These costs may vary based on your consumption type, provisioned capacity, model and region. Please refer to the [AWS Pricing page](https://aws.amazon.com/bedrock/pricing/) for the most accurate and up-to-date information."
        )

        # Update session state values if they've changed
        if new_cost_per_bda_page != cost_per_bda_page:
            st.session_state["cost_per_bda_page"] = new_cost_per_bda_page

        if new_cost_per_input_token != cost_per_input_token:
            st.session_state["cost_per_input_token"] = new_cost_per_input_token

        if new_cost_per_output_token != cost_per_output_token:
            st.session_state["cost_per_output_token"] = new_cost_per_output_token

    return options
