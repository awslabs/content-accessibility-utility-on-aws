# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Remediation fails closed when model calls fail.

Covers the Bedrock preflight (botocore Stubber, no network), ``needs_review``
for failed model-backed fixes, ``--no-ai``, CLI exit codes, and the related
deterministic fixes (single skip link, relative image paths preserved). Nothing
here can reach AWS: the CLI tests run with an empty AWS config, no credential
variables, IMDS disabled, and the Bedrock endpoint pointed at a closed local
port as a backstop.
"""

import json
import sys

import boto3
import pytest
from botocore.stub import Stubber
from bs4 import BeautifulSoup
from PIL import Image

from content_accessibility_utility_on_aws import cli
from content_accessibility_utility_on_aws.api import audit_html_accessibility
from content_accessibility_utility_on_aws.remediate.helpers.text_generation import (
    generate_short_text,
)
from content_accessibility_utility_on_aws.remediate.remediation_manager import (
    RemediationManager,
    issues_need_model,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.landmark_remediation import (
    remediate_missing_footer_landmark,
    remediate_missing_main_landmark,
    remediate_missing_skip_link,
)
from content_accessibility_utility_on_aws.remediate.remediation_strategies.link_remediation import (
    remediate_empty_link_text,
    remediate_generic_link_text,
)
from content_accessibility_utility_on_aws.remediate.services import bedrock_client as bc
from content_accessibility_utility_on_aws.utils.image_utils import copy_images_to_output
from content_accessibility_utility_on_aws.utils.logging_helper import (
    BedrockUnavailableError,
    NeedsReviewError,
)
from tests.conftest import FakeBedrockClient, make_issue

PLACEHOLDERS = ("Image description unavailable", "Image related to this content")

MODEL_ID = "us.anthropic.claude-sonnet-5"


# --- helpers ----------------------------------------------------------------


def _stubbed_client():
    """A real BedrockClient on dummy static credentials, with a Stubber."""
    session = boto3.Session(
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        region_name="us-east-1",
    )
    client = bc.BedrockClient(model_id=MODEL_ID, session=session)
    return client, Stubber(client.client)


def _converse_ok(text):
    return {
        "output": {"message": {"role": "assistant", "content": [{"text": text}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 3, "outputTokens": 3, "totalTokens": 6},
        "metrics": {"latencyMs": 1},
    }


def _make_png(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (4, 4), (200, 30, 30)).save(path, format="PNG")


def _image_doc(tmp_path):
    """An HTML page with one alt-less image under images/ and a real PNG."""
    _make_png(tmp_path / "images" / "chart-a.png")
    html = (
        "<!DOCTYPE html><html><head></head><body>"
        "<h1>Report</h1><p>Sales by region.</p>"
        '<img src="images/chart-a.png">'
        "</body></html>"
    )
    html_path = tmp_path / "doc.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path


class _FailingClient(FakeBedrockClient):
    """Fake client whose every model call raises, like Bedrock with no access."""

    def generate_text(self, prompt, purpose="general", max_tokens=2000, **kwargs):
        raise bc.AltTextGenerationError("AccessDeniedException: no model access")

    def generate_alt_text_for_image(self, image_path, prompt, max_tokens=2000):
        raise bc.AltTextGenerationError("AccessDeniedException: no model access")


@pytest.fixture
def no_aws(monkeypatch, tmp_path):
    """Strip every AWS credential source for the duration of a test."""
    empty = tmp_path / "empty_aws"
    empty.write_text("", encoding="utf-8")
    for var in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
        "AWS_PROFILE",
        "AWS_DEFAULT_PROFILE",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
        "AWS_CONTAINER_AUTHORIZATION_TOKEN",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
        "AWS_ROLE_ARN",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", str(empty))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(empty))
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    # Backstop: even if a credential leaked in, nothing reaches Bedrock.
    monkeypatch.setenv("AWS_ENDPOINT_URL_BEDROCK_RUNTIME", "http://127.0.0.1:9")


def _run_cli(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["content-accessibility-utility-on-aws", *argv])
    return cli.main()


def _audit_to_file(html_path, tmp_path, monkeypatch, capsys):
    """Write an audit report the way users do: with the CLI audit command."""
    report_path = tmp_path / "audit.json"
    rc = _run_cli(
        monkeypatch, ["audit", "-i", str(html_path), "-o", str(report_path), "-f", "json"]
    )
    assert rc == 0
    assert json.loads(report_path.read_text(encoding="utf-8"))["issues"]
    capsys.readouterr()  # discard audit output
    return report_path


# --- preflight ---------------------------------------------------------------


def test_preflight_passes_with_stubbed_model():
    client, stub = _stubbed_client()
    stub.add_response(
        "converse",
        _converse_ok("pong"),
        {
            "modelId": MODEL_ID,
            "messages": [{"role": "user", "content": [{"text": "ping"}]}],
            "inferenceConfig": {"maxTokens": 16},
        },
    )
    with stub:
        client.check_access()
    stub.assert_no_pending_responses()


@pytest.mark.parametrize(
    "code, expected",
    [
        ("AccessDeniedException", "bedrock:InvokeModel"),
        ("ValidationException", "not available in region 'us-east-1'"),
        ("ResourceNotFoundException", "Check --model-id"),
        ("UnrecognizedClientException", "invalid or expired"),
    ],
)
def test_preflight_maps_errors_to_actionable_messages(code, expected):
    client, stub = _stubbed_client()
    stub.add_client_error("converse", service_error_code=code, service_message="nope")
    with stub, pytest.raises(BedrockUnavailableError) as exc:
        client.check_access()
    assert expected in str(exc.value)
    assert "--no-ai" in str(exc.value)


def test_preflight_reports_missing_credentials(no_aws):
    with pytest.raises(BedrockUnavailableError) as exc:
        bc.check_bedrock_access(model_id=MODEL_ID)
    assert "no AWS credentials" in str(exc.value)


def test_preflight_only_needed_for_model_backed_issues():
    assert issues_need_model([{"type": "missing-alt-text"}])
    assert issues_need_model([{"type": "table_missing_scope"}])
    assert not issues_need_model([{"type": "missing-document-language"}])
    assert not issues_need_model([])


# --- needs_review on model failure ----------------------------------------------


def _manager_for(html_path, client, monkeypatch):
    monkeypatch.setattr(RemediationManager, "_make_bedrock_client", lambda self: client)
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    soup.original_url = str(html_path)
    return RemediationManager(soup, {"model_id": MODEL_ID})


def _alt_issue(html_path):
    report = audit_html_accessibility(str(html_path))
    return [i for i in report["issues"] if i["type"] == "missing-alt-text"]


def test_stubbed_model_failure_marks_needs_review(tmp_path, monkeypatch):
    html_path = _image_doc(tmp_path)
    client, stub = _stubbed_client()
    stub.add_client_error(
        "converse", service_error_code="AccessDeniedException", service_message="denied"
    )
    mgr = _manager_for(html_path, client, monkeypatch)
    with stub:
        result = mgr.remediate_issues(_alt_issue(html_path))

    img = mgr.soup.find("img")
    assert not img.has_attr("alt")  # unchanged, no placeholder
    assert result["issues_remediated"] == 0
    assert result["issues_needs_review"] == 1
    assert result["model_failures"] == 1
    detail = result["needs_review_details"][0]
    assert detail["remediation_status"] == "needs_review"
    assert detail["needs_review_reason"] == "model_failed"
    assert "AccessDeniedException" in detail["error"]
    assert not any(p in str(mgr.soup) for p in PLACEHOLDERS)


def test_stubbed_model_success_still_writes_alt_text(tmp_path, monkeypatch):
    html_path = _image_doc(tmp_path)
    client, stub = _stubbed_client()
    stub.add_response("converse", _converse_ok("Bar chart of sales by region"))
    mgr = _manager_for(html_path, client, monkeypatch)
    with stub:
        result = mgr.remediate_issues(_alt_issue(html_path))
    stub.assert_no_pending_responses()

    assert mgr.soup.find("img")["alt"] == "Bar chart of sales by region"
    assert result["issues_remediated"] == 1
    assert result["model_failures"] == 0


def test_short_text_raises_needs_review_when_model_call_fails():
    with pytest.raises(NeedsReviewError) as exc:
        generate_short_text(
            _FailingClient(), instruction="x", context="ctx", purpose="heading_generation"
        )
    assert exc.value.model_failed


def test_generic_link_failure_leaves_link_unchanged(fake_bedrock_client):
    soup = BeautifulSoup(
        "<html><body><p>Our <a href='/pricing'>click here</a> page.</p></body></html>",
        "html.parser",
    )
    issue = make_issue(
        "generic-link-text", path="html > body > p > a", element="a", href="/pricing"
    )
    with pytest.raises(NeedsReviewError):
        remediate_generic_link_text(soup, issue, _FailingClient())
    assert soup.find("a").get_text() == "click here"


def test_generic_link_without_model_or_domain_needs_review():
    soup = BeautifulSoup(
        "<html><body><p>Our <a href='/pricing'>click here</a> page.</p></body></html>",
        "html.parser",
    )
    issue = make_issue(
        "generic-link-text", path="html > body > p > a", element="a", href="/pricing"
    )
    with pytest.raises(NeedsReviewError) as exc:
        remediate_generic_link_text(soup, issue, None)
    assert not exc.value.model_failed
    # No "View details" / "More about ..." generic replacement.
    assert soup.find("a").get_text() == "click here"


def test_empty_fragment_link_is_not_given_generic_text():
    soup = BeautifulSoup(
        "<html><body><div><a href='#settings'></a></div></body></html>", "html.parser"
    )
    issue = make_issue("empty-link-text", path="html > body > div > a", element="a", href="#settings")
    with pytest.raises(NeedsReviewError):
        remediate_empty_link_text(soup, issue)
    assert soup.find("a").get_text() == ""


# --- CLI: no credentials, --no-ai, exit code 2 --------------------------------


def test_cli_without_credentials_fails_fast_and_writes_nothing(
    tmp_path, monkeypatch, capsys, no_aws
):
    html_path = _image_doc(tmp_path)
    report_path = _audit_to_file(html_path, tmp_path, monkeypatch, capsys)
    out = tmp_path / "out" / "remediated.html"

    rc = _run_cli(
        monkeypatch,
        ["remediate", "-i", str(html_path), "-o", str(out),
         "--audit-report", str(report_path), "--auto-fix"],
    )

    assert rc != 0
    assert "no AWS credentials" in capsys.readouterr().out
    assert not out.exists()


def test_cli_no_ai_applies_only_deterministic_fixes(tmp_path, monkeypatch, capsys, no_aws):
    html_path = _image_doc(tmp_path)
    report_path = _audit_to_file(html_path, tmp_path, monkeypatch, capsys)
    out = tmp_path / "out" / "remediated.html"

    rc = _run_cli(
        monkeypatch,
        ["remediate", "-i", str(html_path), "-o", str(out),
         "--audit-report", str(report_path), "--auto-fix", "--no-ai"],
    )

    assert rc == 0
    printed = capsys.readouterr().out
    assert "Needs review (left unchanged): 1" in printed
    assert "Model-backed fixes failed" not in printed

    html = out.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    assert not any(p in html for p in PLACEHOLDERS)
    assert not soup.find("img").has_attr("alt")  # left for review
    assert soup.find("html").get("lang")  # deterministic fix applied
    skip_links = [a for a in soup.find_all("a") if "skip" in a.get_text().lower()]
    assert len(skip_links) == 1
    # Relative image path preserved and the file copied alongside it.
    assert soup.find("img")["src"] == "images/chart-a.png"
    assert (out.parent / "images" / "chart-a.png").exists()


def test_cli_exits_2_when_model_fixes_fail(tmp_path, monkeypatch, capsys, no_aws):
    html_path = _image_doc(tmp_path)
    report_path = _audit_to_file(html_path, tmp_path, monkeypatch, capsys)
    out = tmp_path / "out" / "remediated.html"
    # Preflight passes, then every model call fails mid-run.
    monkeypatch.setattr(bc, "check_bedrock_access", lambda **kwargs: None)
    monkeypatch.setattr(
        RemediationManager, "_make_bedrock_client", lambda self: _FailingClient()
    )

    rc = _run_cli(
        monkeypatch,
        ["remediate", "-i", str(html_path), "-o", str(out),
         "--audit-report", str(report_path), "--auto-fix"],
    )

    assert rc == cli.EXIT_MODEL_FAILURES == 2
    printed = capsys.readouterr().out
    assert "Model-backed fixes failed:" in printed
    assert "AccessDeniedException" in printed
    assert not any(p in out.read_text(encoding="utf-8") for p in PLACEHOLDERS)


# --- deterministic fixes on the same path ------------------------------------------


def test_landmark_fixes_add_a_single_skip_link():
    soup = BeautifulSoup("<html><head></head><body><p>Hi</p></body></html>", "html.parser")
    remediate_missing_main_landmark(soup, make_issue("missing-main-landmark"))
    remediate_missing_footer_landmark(soup, make_issue("missing-footer-landmark"))
    remediate_missing_skip_link(soup, make_issue("missing-skip-link"))
    skip = [a for a in soup.find_all("a") if "skip" in a.get_text().lower()]
    assert len(skip) == 1


def test_copy_images_preserves_relative_paths_and_skips_remote(tmp_path):
    src_dir = tmp_path / "src" / "images"
    _make_png(src_dir / "a.png")
    _make_png(tmp_path / "src" / "b.png")
    soup = BeautifulSoup(
        '<img src="images/a.png"><img src="https://cdn.example.com/c.png">'
        '<img src="../b.png">',
        "html.parser",
    )
    dest = tmp_path / "out"
    copy_images_to_output(str(src_dir), str(dest), soup)
    imgs = soup.find_all("img")
    assert imgs[0]["src"] == "images/a.png"
    assert (dest / "images" / "a.png").exists()
    assert imgs[1]["src"] == "https://cdn.example.com/c.png"
    # A path escaping the output dir is still flattened into it.
    assert imgs[2]["src"] == "./b.png"
    assert (dest / "b.png").exists()
