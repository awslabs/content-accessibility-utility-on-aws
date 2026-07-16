# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Regression tests for element resolution surviving DOM mutation.

Remediation applies fixes sequentially, and structural fixes (wrapping the body
in <main>, inserting <header>/<nav>) shift the ``:nth-of-type`` indices that the
audit-time path depends on. Before the fix, later issues (form labels, alt text)
silently failed to resolve and were skipped. ``find_element_from_issue`` now
falls back to identifiers that survive restructuring.
"""

from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.audit.context_collector import ContextCollector
from content_accessibility_utility_on_aws.remediate.helpers.selector_helper import (
    find_element_from_issue,
)

_HTML = """<html><body>
<div class="card"><form>
  <div><input type="email" name="email"></div>
  <div>
    <input type="radio" name="freq" value="daily">
    <input type="radio" name="freq" value="weekly">
  </div>
  <textarea name="notes"></textarea>
</form></div>
<img src="images/chart.png">
</body></html>"""


def _issue_for(element, path):
    """Build an audit-shaped issue (path + collected context) for an element."""
    return {
        "type": "x",
        "element": element.name,
        "location": {"path": f"[document] > {path}"},
        "context": ContextCollector(element).collect(),
    }


def _wrap_body_in_main(soup):
    """Simulate a landmark fix that invalidates absolute nth-of-type paths."""
    body = soup.find("body")
    main = soup.new_tag("main")
    for child in list(body.children):
        main.append(child.extract())
    body.append(main)


def test_input_resolves_after_body_wrapped_in_main():
    soup = BeautifulSoup(_HTML, "html.parser")
    target = soup.find_all("input")[2]  # radio value=weekly
    issue = _issue_for(target, "html > body > div.card > form > div:nth-of-type(2) > input:nth-of-type(2)")

    _wrap_body_in_main(soup)  # path is now stale

    resolved = find_element_from_issue(soup, issue)
    assert resolved is not None
    assert resolved.get("name") == "freq"
    assert resolved.get("value") == "weekly"


def test_image_resolves_by_src_after_mutation():
    soup = BeautifulSoup(_HTML, "html.parser")
    img = soup.find("img")
    issue = _issue_for(img, "html > body > img")
    _wrap_body_in_main(soup)
    resolved = find_element_from_issue(soup, issue)
    assert resolved is not None and resolved.name == "img"
    assert resolved.get("src") == "images/chart.png"


def test_textarea_resolves_by_name_after_mutation():
    soup = BeautifulSoup(_HTML, "html.parser")
    ta = soup.find("textarea")
    issue = _issue_for(ta, "html > body > div.card > form > textarea")
    _wrap_body_in_main(soup)
    resolved = find_element_from_issue(soup, issue)
    assert resolved is not None and resolved.name == "textarea"
    assert resolved.get("name") == "notes"


def test_deleted_element_does_not_resolve_to_a_sibling():
    """A removed element must resolve to None, not a different same-tag element.

    Regression: after an earlier remediation deletes the target, a stale generic
    path or the position fallback could hand back a surviving sibling, so alt
    text / fixes intended for A would be applied to B.
    """
    soup = BeautifulSoup(
        '<html><body><img src="a.png"><img src="b.png"></body></html>', "html.parser"
    )
    img_a = soup.find_all("img")[0]
    issue = _issue_for(img_a, "html > body > img")
    img_a.extract()  # earlier remediation removed image A
    resolved = find_element_from_issue(soup, issue)
    assert resolved is None


def test_data_bda_id_disambiguates_same_src_images():
    soup = BeautifulSoup(
        '<html><body><img src="x.png" data-bda-id="1">'
        '<img src="x.png" data-bda-id="2"></body></html>',
        "html.parser",
    )
    second = soup.find_all("img")[1]
    issue = _issue_for(second, "html > body > img:nth-of-type(2)")
    # Break the path so resolution must use data-bda-id.
    issue["location"]["path"] = "[document] > html > body > img"
    resolved = find_element_from_issue(soup, issue)
    assert resolved is not None and resolved.get("data-bda-id") == "2"


def test_exact_path_still_preferred_when_unchanged():
    soup = BeautifulSoup(_HTML, "html.parser")
    email = soup.find("input", attrs={"name": "email"})
    issue = _issue_for(email, "html > body > div.card > form > div:nth-of-type(1) > input")
    # No mutation: the exact path resolves.
    resolved = find_element_from_issue(soup, issue)
    assert resolved is email
