# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Download utilities for the Document Accessibility Streamlit application.
"""

import os
import json
import zipfile
import tempfile
import streamlit as st
from typing import Optional, Dict, Any

from content_accessibility_utility_on_aws.report.pdf_exporter import export_pdf, FPDF2_AVAILABLE
from content_accessibility_utility_on_aws.report.vpat_generator import generate_vpat
from content_accessibility_utility_on_aws.report.acr_generator import generate_acr

def create_download_button_for_file(file_path: str, button_text: str, download_filename: Optional[str] = None) -> None:
    """
    Create a download button for a file.
    
    Args:
        file_path: Path to the file
        button_text: Text to display on the button
        download_filename: Optional filename to use for download (defaults to basename of file_path)
    """
    if not os.path.exists(file_path):
        st.warning(f"File not found: {file_path}")
        return
    
    if download_filename is None:
        download_filename = os.path.basename(file_path)
    
    # Determine the MIME type
    mime_type = "application/octet-stream"
    if file_path.lower().endswith(".html"):
        mime_type = "text/html"
    elif file_path.lower().endswith(".json"):
        mime_type = "application/json"
    elif file_path.lower().endswith(".zip"):
        mime_type = "application/zip"
    elif file_path.lower().endswith(".pdf"):
        mime_type = "application/pdf"
    
    # Read and create download button
    with open(file_path, "rb", encoding=None) as file:
        st.download_button(
            label=button_text,
            data=file,
            file_name=download_filename,
            mime=mime_type,
        )

def create_download_button_for_directory(directory_path: str, button_text: str, download_filename: str) -> None:
    """
    Create a download button for a directory by zipping its contents.
    
    Args:
        directory_path: Path to the directory
        button_text: Text to display on the button
        download_filename: Filename to use for the zip download
    """
    import tempfile
    
    if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
        st.warning(f"Directory not found: {directory_path}")
        return
    
    # Create a temporary zip file - using secure mkstemp instead of insecure mktemp
    fd, temp_zip_path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)  # Close the file descriptor immediately
    
    try:
        # Create a zip file containing the directory contents
        with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(directory_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, directory_path)
                    zipf.write(file_path, arcname)
        
        # Create download button for the zip file
        with open(temp_zip_path, "rb") as file:
            st.download_button(
                label=button_text,
                data=file,
                file_name=download_filename,
                mime="application/zip",
            )
    
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_zip_path):
            try:
                os.remove(temp_zip_path)
            except Exception:
                print(f"Failed to remove temporary file: {temp_zip_path}")

def create_download_section_for_remediated_files(remediated_path: str) -> None:
    """
    Create a download section for remediated files.
    
    Args:
        remediated_path: Path to the remediated files
    """
    if not os.path.exists(remediated_path):
        st.warning(f"No remediated files found at {remediated_path}")
        return
    
    st.subheader("Download Remediated Files")
    
    if os.path.isdir(remediated_path):
        # Directory with multiple files
        html_files = [f for f in os.listdir(remediated_path) 
                      if f.lower().endswith(".html") and os.path.isfile(os.path.join(remediated_path, f))]
        
        if len(html_files) > 1:
            # Multiple HTML files - offer both individual and zip download
            col1, col2 = st.columns(2)
            
            with col1:
                create_download_button_for_directory(
                    remediated_path,
                    "Download All Files (ZIP)",
                    "remediated_files.zip"
                )
                
            with col2:
                # Allow downloading individual files
                selected_file = st.selectbox(
                    "Select individual file to download:",
                    html_files
                )
                if selected_file:
                    create_download_button_for_file(
                        os.path.join(remediated_path, selected_file),
                        f"Download {selected_file}",
                        selected_file
                    )
        
        elif len(html_files) == 1:
            # Single HTML file
            create_download_button_for_file(
                os.path.join(remediated_path, html_files[0]),
                "Download Remediated HTML",
                "remediated_document.html"
            )
        
        else:
            st.info("No HTML files found in the remediation directory.")
    
    else:
        # Single file
        create_download_button_for_file(
            remediated_path,
            "Download Remediated HTML",
            "remediated_document.html"
        )

def _load_json_report(file_path: str) -> Optional[Dict[str, Any]]:
    """Load a JSON report file."""
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _generate_pdf_report(
    report_data: Dict[str, Any],
    report_type: str,
    output_dir: str,
    product_info: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """
    Generate a PDF report from audit/remediation data.

    Args:
        report_data: The report data dictionary
        report_type: Type of report ("audit", "vpat", or "acr")
        output_dir: Directory to save the PDF
        product_info: Optional product information for VPAT/ACR

    Returns:
        Path to generated PDF or None if generation failed
    """
    if not FPDF2_AVAILABLE:
        return None

    try:
        if report_type == "audit":
            output_path = os.path.join(output_dir, "accessibility_audit.pdf")
            export_pdf(report_data, output_path, report_type="audit")
            return output_path

        elif report_type == "vpat":
            # Generate VPAT data first, then export to PDF
            vpat_data = generate_vpat(
                audit_report=report_data,
                product_info=product_info or {"name": "Document", "version": "1.0"},
                target_level="AA"
            )
            output_path = os.path.join(output_dir, "vpat_report.pdf")
            export_pdf(vpat_data, output_path, report_type="vpat")
            return output_path

        elif report_type == "acr":
            # Generate ACR data first, then export to PDF
            acr_data = generate_acr(
                audit_report=report_data,
                organization_info=product_info or {"name": "Organization", "product": "Document"},
                target_level="AA",
                include_remediation_guidance=True
            )
            output_path = os.path.join(output_dir, "acr_report.pdf")
            export_pdf(acr_data, output_path, report_type="acr")
            return output_path

    except Exception as e:
        st.warning(f"Could not generate {report_type.upper()} PDF: {str(e)}")
        return None

    return None


def create_pdf_download_section(
    audit_data: Optional[Dict[str, Any]],
    temp_dir: str,
    product_info: Optional[Dict[str, str]] = None,
) -> None:
    """
    Create download buttons for PDF reports (Audit, VPAT, ACR).

    Args:
        audit_data: The audit report data
        temp_dir: Temporary directory for generating PDFs
        product_info: Optional product/organization info for reports
    """
    if not FPDF2_AVAILABLE:
        st.info("PDF export is not available. Install fpdf2 to enable PDF reports.")
        return

    if not audit_data:
        return

    st.subheader("PDF Reports")
    st.caption("Generate professional PDF reports from the audit results")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Generate Audit PDF", key="gen_audit_pdf", use_container_width=True):
            with st.spinner("Generating Audit PDF..."):
                pdf_path = _generate_pdf_report(audit_data, "audit", temp_dir, product_info)
                if pdf_path and os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            label="Download Audit PDF",
                            data=f.read(),
                            file_name="accessibility_audit.pdf",
                            mime="application/pdf",
                            key="dl_audit_pdf",
                        )

    with col2:
        if st.button("Generate VPAT PDF", key="gen_vpat_pdf", use_container_width=True):
            with st.spinner("Generating VPAT PDF..."):
                pdf_path = _generate_pdf_report(audit_data, "vpat", temp_dir, product_info)
                if pdf_path and os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            label="Download VPAT PDF",
                            data=f.read(),
                            file_name="vpat_report.pdf",
                            mime="application/pdf",
                            key="dl_vpat_pdf",
                        )

    with col3:
        if st.button("Generate ACR PDF", key="gen_acr_pdf", use_container_width=True):
            with st.spinner("Generating ACR PDF..."):
                pdf_path = _generate_pdf_report(audit_data, "acr", temp_dir, product_info)
                if pdf_path and os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            label="Download ACR PDF",
                            data=f.read(),
                            file_name="acr_report.pdf",
                            mime="application/pdf",
                            key="dl_acr_pdf",
                        )


def create_download_section_for_reports(temp_dir: str) -> None:
    """
    Create a download section for report files.

    Args:
        temp_dir: Temporary directory containing report files
    """
    if not os.path.exists(temp_dir):
        return

    # Find report files
    html_report_path = os.path.join(temp_dir, "remediation_report.html")
    json_report_path = os.path.join(temp_dir, "remediation_report.json")
    audit_report_path = os.path.join(temp_dir, "accessibility_audit.json")

    has_reports = (os.path.exists(html_report_path) or
                  os.path.exists(json_report_path) or
                  os.path.exists(audit_report_path))

    if has_reports:
        st.subheader("Download Reports")

        # HTML remediation report
        if os.path.exists(html_report_path):
            create_download_button_for_file(
                html_report_path,
                "Download HTML Report",
                "remediation_report.html"
            )

        # JSON remediation report
        if os.path.exists(json_report_path):
            create_download_button_for_file(
                json_report_path,
                "Download JSON Remediation Report",
                "remediation_report.json"
            )

        # Audit report
        if os.path.exists(audit_report_path):
            create_download_button_for_file(
                audit_report_path,
                "Download Audit Report (JSON)",
                "accessibility_audit.json"
            )

        # PDF Reports section
        st.divider()

        # Load audit data for PDF generation
        audit_data = _load_json_report(audit_report_path)
        if not audit_data:
            # Try loading from remediation report
            audit_data = _load_json_report(json_report_path)

        if audit_data:
            create_pdf_download_section(audit_data, temp_dir)
