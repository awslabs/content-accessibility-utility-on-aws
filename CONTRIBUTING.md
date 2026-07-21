<!--
 Copyright 2025 Amazon.com, Inc. or its affiliates.
 SPDX-License-Identifier: Apache-2.0
-->

# Contributing Guidelines

Thank you for your interest in contributing to our project. Whether it's a bug report, new feature, correction, or additional
documentation, we greatly value feedback and contributions from our community.

Please read through this document before submitting any issues or pull requests to ensure we have all the necessary
information to effectively respond to your bug report or contribution.


## Reporting Bugs/Feature Requests

We welcome you to use the GitHub issue tracker to report bugs or suggest features.

When filing an issue, please check existing open, or recently closed, issues to make sure somebody else hasn't already
reported the issue. Please try to include as much information as you can. Details like these are incredibly useful:

* A reproducible test case or series of steps
* The version of our code being used
* Any modifications you've made relevant to the bug
* Anything unusual about your environment or deployment


## Contributing via Pull Requests
Contributions via pull requests are much appreciated. Before sending us a pull request, please ensure that:

1. You are working against the latest source on the *main* branch.
2. You check existing open, and recently merged, pull requests to make sure someone else hasn't addressed the problem already.
3. You open an issue to discuss any significant work - we would hate for your time to be wasted.

To send us a pull request, please:

1. Fork the repository.
2. Modify the source; please focus on the specific change you are contributing. If you also reformat all the code, it will be hard for us to focus on your change.
3. Ensure local tests pass:

   ```bash
   pip install -e ".[test]"
   pytest
   ```

   The default `pytest` run is offline, fast, and free — it excludes the
   AWS-backed AI quality tests. See [TESTING_PLAN.md](TESTING_PLAN.md) for the
   full test strategy, including the opt-in `pytest -m aws` tier.
4. **Update the documentation.** Any change to user-visible behavior must include
   the matching documentation updates in the *same* pull request — see
   [Documentation](#documentation) below.
5. Commit to your fork using clear commit messages.
6. Send us a pull request, answering any default questions in the pull request interface.
7. Pay attention to any automated CI failures reported in the pull request, and stay involved in the conversation.

GitHub provides additional document on [forking a repository](https://help.github.com/articles/fork-a-repo/) and
[creating a pull request](https://help.github.com/articles/creating-a-pull-request/).


## Documentation

Documentation is a first-class part of this project, and **keeping it current is
a requirement of every contribution — not an optional follow-up.** A pull request
that changes user-visible behavior is not complete until the documentation is
updated in the same PR.

The user-facing documentation lives in [`docs/`](docs/) and is published as a
**GitHub Pages** site (Jekyll + the [just-the-docs](https://just-the-docs.com)
theme) by [`.github/workflows/pages.yml`](.github/workflows/pages.yml). The
short overview in [`README.md`](README.md) links out to that site.

When your change touches any of the following, update the matching page(s) in
the same pull request:

| If you change… | Update… |
|---|---|
| A CLI command, flag, or default | [`docs/cli_guide.md`](docs/cli_guide.md) **and** [`docs/parameter_reference.md`](docs/parameter_reference.md) |
| A public API function or its options | [`docs/api_integration_guide.md`](docs/api_integration_guide.md) (and `parameter_reference.md` for shared params) |
| The managed pipeline / deployment | [`docs/pipeline_guide.md`](docs/pipeline_guide.md) |
| Remediation behavior | [`docs/accessibility_remediation.md`](docs/accessibility_remediation.md) |
| The rendered audit / agent layer | [`docs/rendered_agent_guide.md`](docs/rendered_agent_guide.md) |
| Module structure | [`docs/architecture.md`](docs/architecture.md) |
| Anything user-visible in the overview | [`README.md`](README.md) |

Guidelines:

- **README links to docs pages must be absolute** (`https://awslabs.github.io/...`)
  because the README is also rendered on PyPI, which does not resolve relative
  repository links. Cross-page links *inside* `docs/` are relative and
  extensionless (e.g. `[CLI Guide](cli_guide)`).
- **Diagrams are drawio-authored SVGs**, not Mermaid (GitHub Pages renders
  neither Mermaid nor relative links without extra plugins). The editable
  sources and tooling live in [`docs/assets/diagrams/`](docs/assets/diagrams/)
  and the exported SVGs in `docs/assets/img/`. To change a diagram, edit its
  spec in `gen_diagrams.py` (or the `.drawio` file directly), regenerate with
  `./docs/assets/diagrams/export.sh`, and commit both the source and the updated
  SVG. Keep image **alt text descriptive** — this is an accessibility project.
- You can preview the site locally with `cd docs && bundle install && bundle exec jekyll serve`.

AI coding agents working in this repo should also read [CLAUDE.md](CLAUDE.md)
(and [AGENTS.md](AGENTS.md), which points to it).


## Finding contributions to work on
Looking at the existing issues is a great way to find something to contribute on. As our projects, by default, use the default GitHub issue labels (enhancement/bug/duplicate/help wanted/invalid/question/wontfix), looking at any 'help wanted' issues is a great place to start.


## Code of Conduct
This project has adopted the [Amazon Open Source Code of Conduct](https://aws.github.io/code-of-conduct).
For more information see the [Code of Conduct FAQ](https://aws.github.io/code-of-conduct-faq) or contact
opensource-codeofconduct@amazon.com with any additional questions or comments.


## Security issue notifications
If you discover a potential security issue in this project we ask that you notify AWS/Amazon Security via our [vulnerability reporting page](http://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a public github issue.


## Licensing

See the [LICENSE](LICENSE) file for our project's licensing. We will ask you to confirm the licensing of your contribution.