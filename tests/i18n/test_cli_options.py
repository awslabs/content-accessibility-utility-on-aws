# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Offline tests for the CLI i18n option-building helpers.

These verify that a config-file ``i18n.model_id`` is honored (not clobbered by
the ``--model-id`` argument's default) and that the batch-size default is a
single shared value.
"""

from content_accessibility_utility_on_aws.cli import _build_i18n_options
from content_accessibility_utility_on_aws.utils.constants import (
    DEFAULT_MODEL_ID,
    DEFAULT_TRANSLATION_BATCH_SIZE,
)


def test_build_options_omits_model_id_when_at_default():
    # --model-id left at its default must NOT be forwarded, so a config-file
    # i18n.model_id (merged later by the API's get_config) is not clobbered.
    args = {
        "target_languages": "es",
        "model_id": DEFAULT_MODEL_ID,  # argparse default (user did not override)
    }
    options = _build_i18n_options(args)
    assert "model_id" not in options


def test_build_options_forwards_explicit_model_id():
    # An explicit override differs from the default and MUST be forwarded.
    args = {"target_languages": "es", "model_id": "us.anthropic.custom-model"}
    options = _build_i18n_options(args)
    assert options["model_id"] == "us.anthropic.custom-model"


def test_batch_size_default_is_single_source():
    # config default, api fallback, and translator constant all agree.
    from content_accessibility_utility_on_aws.utils.config import config_manager
    from content_accessibility_utility_on_aws.i18n.translator import (
        DEFAULT_BATCH_SIZE,
    )

    assert DEFAULT_BATCH_SIZE == DEFAULT_TRANSLATION_BATCH_SIZE
    assert (
        config_manager.get_config(section="i18n")["batch_size"]
        == DEFAULT_TRANSLATION_BATCH_SIZE
    )
