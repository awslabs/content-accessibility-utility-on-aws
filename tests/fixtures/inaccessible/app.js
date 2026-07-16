// Copyright 2025 Amazon.com, Inc. or its affiliates.
// SPDX-License-Identifier: Apache-2.0
// Stub interactions for the deliberately-inaccessible test fixture.
function refresh() { console.log('refresh'); }
function exportCsv() { console.log('export'); }
function toggleLive() {
  var t = document.querySelector('.toggle');
  t.style.background = t.style.background === 'rgb(21, 101, 192)' ? '#ccc' : '#1565c0';
}
