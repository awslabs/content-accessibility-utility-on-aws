# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Pytest configuration and fixtures for Content Accessibility Utility tests.
"""

import pytest
from pathlib import Path
from bs4 import BeautifulSoup

# Base paths
TESTS_DIR = Path(__file__).parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
HTML_FIXTURES_DIR = FIXTURES_DIR / "html"


@pytest.fixture
def fixtures_dir():
    """Return path to fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def html_fixtures_dir():
    """Return path to HTML fixtures directory."""
    return HTML_FIXTURES_DIR


# ============================================================================
# HTML Content Fixtures - Various accessibility issues for testing
# ============================================================================

@pytest.fixture
def html_missing_alt_text():
    """HTML with images missing alt text."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head><title>Test Page</title></head>
    <body>
        <h1>Test Page</h1>
        <img src="image1.png">
        <img src="image2.png">
        <img src="decorative.png" role="presentation" alt="">
    </body>
    </html>
    """


@pytest.fixture
def html_generic_alt_text():
    """HTML with generic alt text on images."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head><title>Test Page</title></head>
    <body>
        <h1>Test Page</h1>
        <img src="chart.png" alt="IMAGE">
        <img src="diagram.png" alt="FIGURE">
        <img src="icon.png" alt="ICON">
        <img src="photo.png" alt="picture 1">
    </body>
    </html>
    """


@pytest.fixture
def html_missing_language():
    """HTML missing language attribute."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Test Page</title></head>
    <body>
        <h1>Test Page</h1>
        <p>This page has no language attribute.</p>
    </body>
    </html>
    """


@pytest.fixture
def html_missing_title():
    """HTML missing page title."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head></head>
    <body>
        <h1>Test Page</h1>
        <p>This page has no title element.</p>
    </body>
    </html>
    """


@pytest.fixture
def html_heading_hierarchy_issues():
    """HTML with heading hierarchy problems."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head><title>Test Page</title></head>
    <body>
        <h1>Main Title</h1>
        <h3>Skipped h2</h3>
        <h5>Skipped multiple levels</h5>
        <h2>Back to h2</h2>
    </body>
    </html>
    """


@pytest.fixture
def html_empty_headings():
    """HTML with empty headings."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head><title>Test Page</title></head>
    <body>
        <h1>Main Title</h1>
        <h2></h2>
        <h2>   </h2>
        <h3>Valid Heading</h3>
    </body>
    </html>
    """


@pytest.fixture
def html_table_no_headers():
    """HTML table without proper headers."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head><title>Test Page</title></head>
    <body>
        <h1>Data Table</h1>
        <table>
            <tr>
                <td>Name</td>
                <td>Age</td>
                <td>City</td>
            </tr>
            <tr>
                <td>John</td>
                <td>30</td>
                <td>NYC</td>
            </tr>
        </table>
    </body>
    </html>
    """


@pytest.fixture
def html_table_missing_scope():
    """HTML table with headers missing scope attribute."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head><title>Test Page</title></head>
    <body>
        <h1>Data Table</h1>
        <table>
            <tr>
                <th>Name</th>
                <th>Age</th>
                <th>City</th>
            </tr>
            <tr>
                <td>John</td>
                <td>30</td>
                <td>NYC</td>
            </tr>
        </table>
    </body>
    </html>
    """


@pytest.fixture
def html_form_missing_labels():
    """HTML form with inputs missing labels."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head><title>Test Page</title></head>
    <body>
        <h1>Contact Form</h1>
        <form>
            <input type="text" name="name" placeholder="Name">
            <input type="email" name="email" placeholder="Email">
            <textarea name="message" placeholder="Message"></textarea>
            <button type="submit">Submit</button>
        </form>
    </body>
    </html>
    """


@pytest.fixture
def html_links_empty_text():
    """HTML with links that have empty or generic text."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head><title>Test Page</title></head>
    <body>
        <h1>Links Test</h1>
        <a href="/page1"></a>
        <a href="/page2"><img src="icon.png"></a>
        <a href="/page3">click here</a>
        <a href="/page4">read more</a>
        <a href="https://example.com">https://example.com</a>
    </body>
    </html>
    """


@pytest.fixture
def html_missing_landmarks():
    """HTML missing ARIA landmarks."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head><title>Test Page</title></head>
    <body>
        <div class="header">
            <h1>Site Title</h1>
        </div>
        <div class="nav">
            <a href="/">Home</a>
            <a href="/about">About</a>
        </div>
        <div class="content">
            <h2>Main Content</h2>
            <p>Some content here.</p>
        </div>
        <div class="footer">
            <p>Footer content</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def html_color_contrast_issues():
    """HTML with inline color contrast issues."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head><title>Test Page</title></head>
    <body>
        <h1>Color Contrast Test</h1>
        <p style="color: #777777; background-color: #ffffff;">Low contrast text</p>
        <p style="color: #cccccc; background-color: #ffffff;">Very low contrast</p>
        <p style="color: #000000; background-color: #ffffff;">Good contrast</p>
    </body>
    </html>
    """


@pytest.fixture
def html_fully_accessible():
    """Fully accessible HTML page for baseline testing."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Fully Accessible Page</title>
    </head>
    <body>
        <a href="#main-content" class="skip-link">Skip to main content</a>
        <header role="banner">
            <nav role="navigation" aria-label="Main navigation">
                <ul>
                    <li><a href="/">Home</a></li>
                    <li><a href="/about">About Us</a></li>
                </ul>
            </nav>
        </header>
        <main id="main-content" role="main">
            <h1>Welcome to Our Accessible Site</h1>
            <section>
                <h2>About This Page</h2>
                <p>This page demonstrates proper accessibility practices.</p>
                <figure>
                    <img src="chart.png" alt="Bar chart showing quarterly sales growth from Q1 to Q4 2024">
                    <figcaption>Figure 1: Quarterly Sales Growth 2024</figcaption>
                </figure>
            </section>
            <section>
                <h2>Contact Form</h2>
                <form>
                    <div>
                        <label for="name">Name (required)</label>
                        <input type="text" id="name" name="name" required aria-required="true">
                    </div>
                    <div>
                        <label for="email">Email (required)</label>
                        <input type="email" id="email" name="email" required aria-required="true">
                    </div>
                    <button type="submit">Submit Form</button>
                </form>
            </section>
            <section>
                <h2>Data Table</h2>
                <table>
                    <caption>Employee Information</caption>
                    <thead>
                        <tr>
                            <th scope="col">Name</th>
                            <th scope="col">Department</th>
                            <th scope="col">Location</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>John Smith</td>
                            <td>Engineering</td>
                            <td>Seattle</td>
                        </tr>
                    </tbody>
                </table>
            </section>
        </main>
        <footer role="contentinfo">
            <p>Copyright 2024 Example Corp</p>
        </footer>
    </body>
    </html>
    """


# ============================================================================
# BeautifulSoup Fixtures
# ============================================================================

@pytest.fixture
def soup_factory():
    """Factory fixture to create BeautifulSoup objects from HTML strings."""
    def _create_soup(html_content):
        return BeautifulSoup(html_content, "html.parser")
    return _create_soup


# ============================================================================
# Auditor Fixtures
# ============================================================================

@pytest.fixture
def auditor_factory():
    """Factory fixture to create AccessibilityAuditor instances."""
    from content_accessibility_utility_on_aws.audit.auditor import AccessibilityAuditor

    def _create_auditor(html_content=None, html_path=None, options=None):
        return AccessibilityAuditor(
            html_content=html_content,
            html_path=html_path,
            options=options or {}
        )
    return _create_auditor


# ============================================================================
# Mock Fixtures for AWS Services
# ============================================================================

@pytest.fixture
def mock_bedrock_client(mocker):
    """Mock BedrockClient for testing without AWS calls."""
    mock_client = mocker.MagicMock()
    mock_client.generate_alt_text.return_value = "AI-generated alt text description"
    mock_client.invoke_model.return_value = {"content": "AI response"}
    return mock_client


@pytest.fixture
def mock_bda_client(mocker):
    """Mock BDA client for PDF conversion testing."""
    mock_client = mocker.MagicMock()
    mock_client.process_and_retrieve.return_value = {
        "html_path": "/tmp/test/extracted_html",
        "html_files": ["/tmp/test/extracted_html/page-1.html"],
        "image_files": [],
        "result_data": {}
    }
    return mock_client


# ============================================================================
# Temporary Directory Fixtures
# ============================================================================

@pytest.fixture
def temp_html_file(tmp_path):
    """Create a temporary HTML file for testing."""
    def _create_file(content, filename="test.html"):
        file_path = tmp_path / filename
        file_path.write_text(content)
        return str(file_path)
    return _create_file


@pytest.fixture
def temp_html_dir(tmp_path):
    """Create a temporary directory with multiple HTML files."""
    def _create_dir(html_contents):
        html_dir = tmp_path / "extracted_html"
        html_dir.mkdir()
        files = []
        for i, content in enumerate(html_contents, 1):
            file_path = html_dir / f"page-{i}.html"
            file_path.write_text(content)
            files.append(str(file_path))
        return str(html_dir), files
    return _create_dir
