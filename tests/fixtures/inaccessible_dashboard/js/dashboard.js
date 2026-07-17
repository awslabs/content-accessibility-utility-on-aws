// Copyright 2025 Amazon.com, Inc. or its affiliates.
// SPDX-License-Identifier: Apache-2.0
//
// Interactivity for the deliberately-inaccessible dashboard fixture. The
// widgets are wired with click handlers only (no keyboard handlers, no ARIA
// state updates) — part of the intended WCAG 4.1.2 / 2.1.1 failures.

function switchTab(el) {
  document.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('active'); });
  el.classList.add('active');
}

function toggleSwitch(el) {
  el.classList.toggle('on'); // visual only; no aria-checked update
}

function openModal() {
  document.getElementById('settings-modal').classList.add('open');
}

function closeModal() {
  document.getElementById('settings-modal').classList.remove('open');
}

function refresh() { console.log('refresh'); }
function exportData() { console.log('export'); }
