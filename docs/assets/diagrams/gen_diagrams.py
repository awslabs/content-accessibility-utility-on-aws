#!/usr/bin/env python3
# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0
"""Generate editable drawio (.drawio / mxGraph XML) sources for the docs diagrams.

Each diagram is declared as a compact Python spec (nodes + edges) below. Running
this script writes one ``<name>.drawio`` file per spec into this directory. Those
files are fully editable in the drawio desktop / web app — this generator only
exists so the diagrams are authored as reviewable data and stay consistent
(shared palette, spacing, and — importantly — clean edge routing).

Edges carry explicit connection anchors (``exit``/``entry`` on 0..1 box
coordinates) and orthogonal ``points`` (waypoints), so lines run in the gaps
*between* columns instead of being routed by the auto-router through the middle
boxes. That is what keeps the exported SVGs free of overlapping lines/boxes.

Export the ``.drawio`` sources to SVG with ``export.sh`` (drawio-desktop CLI).
"""

from __future__ import annotations

import html
import os
from dataclasses import dataclass, field
from typing import Optional

# --- Shared style swatches (drawio standard fill/stroke pairs) ----------------
BLUE = "rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
GREEN = "rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;"
ORANGE = "rounded=1;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;"
GRAY = "rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;"
PURPLE = "rounded=1;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;"
CYL = "shape=cylinder3;whiteSpace=wrap;html=1;boxedPerimeter=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
# Monospace left-aligned node for the output-tree diagrams.
MONO = (
    "rounded=0;whiteSpace=wrap;html=1;align=left;spacingLeft=10;"
    "fontFamily=monospace;fontSize=12;fillColor=#f5f5f5;strokeColor=#b3b3b3;"
)
_EDGE_BASE = (
    "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;"
    "endArrow=block;endFill=1;strokeColor=#4d4d4d;"
)


@dataclass
class Node:
    id: str
    label: str
    x: float
    y: float
    w: float = 170
    h: float = 46
    style: str = BLUE


@dataclass
class Edge:
    src: str
    dst: str
    label: str = ""
    dashed: bool = False
    exit: Optional[tuple[float, float]] = None   # (x, y) on 0..1 of source box
    entry: Optional[tuple[float, float]] = None  # (x, y) on 0..1 of target box
    points: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class Diagram:
    name: str
    nodes: list[Node]
    edges: list[Edge] = field(default_factory=list)
    width: int = 850
    height: int = 600


def _esc(s: str) -> str:
    # Labels are plain text; drop newlines and let whiteSpace=wrap handle width.
    return html.escape(s.replace("\n", " "), quote=True)


def _edge_style(e: Edge) -> str:
    style = _EDGE_BASE
    if e.exit is not None:
        style += f"exitX={e.exit[0]};exitY={e.exit[1]};exitDx=0;exitDy=0;"
    if e.entry is not None:
        style += f"entryX={e.entry[0]};entryY={e.entry[1]};entryDx=0;entryDy=0;"
    if e.dashed:
        style += "dashed=1;"
    return style


def render(d: Diagram) -> str:
    cells: list[str] = []
    for n in d.nodes:
        cells.append(
            f'        <mxCell id="{_esc(n.id)}" value="{_esc(n.label)}" '
            f'style="{n.style}" vertex="1" parent="1">\n'
            f'          <mxGeometry x="{int(n.x)}" y="{int(n.y)}" '
            f'width="{int(n.w)}" height="{int(n.h)}" as="geometry"/>\n'
            f"        </mxCell>"
        )
    for i, e in enumerate(d.edges):
        pts = ""
        if e.points:
            inner = "".join(
                f'<mxPoint x="{int(x)}" y="{int(y)}"/>' for x, y in e.points
            )
            pts = f'<Array as="points">{inner}</Array>'
        cells.append(
            f'        <mxCell id="e{i}" value="{_esc(e.label)}" '
            f'style="{_edge_style(e)}" edge="1" parent="1" '
            f'source="{_esc(e.src)}" target="{_esc(e.dst)}">\n'
            f'          <mxGeometry relative="1" as="geometry">{pts}</mxGeometry>\n'
            f"        </mxCell>"
        )
    body = "\n".join(cells)
    return (
        '<mxfile host="gen_diagrams.py">\n'
        f'  <diagram name="{_esc(d.name)}" id="{_esc(d.name)}">\n'
        f'    <mxGraphModel dx="{d.width}" dy="{d.height}" grid="0" gridSize="10" '
        'guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" '
        f'pageScale="1" pageWidth="{d.width}" pageHeight="{d.height}" '
        'math="0" shadow="0">\n'
        "      <root>\n"
        '        <mxCell id="0"/>\n'
        '        <mxCell id="1" parent="0"/>\n'
        f"{body}\n"
        "      </root>\n"
        "    </mxGraphModel>\n"
        "  </diagram>\n"
        "</mxfile>\n"
    )


# =============================================================================
# Layout helper: input -> module -> {steps} -> output  ("hub" / fan-out+fan-in)
# =============================================================================
def hub(
    name: str,
    input_label: str,
    module_label: str,
    module_style: str,
    steps: list[str],
    output_label: str,
    step_style: str,
    output_style: str = GREEN,
    input_style: str = GRAY,
) -> Diagram:
    W, H, vgap = 180, 54, 30
    IX, MX, SX, OX = 40, 250, 480, 740
    top = 40
    n = len(steps)
    total = n * H + (n - 1) * vgap
    cy = top + total / 2
    tx1 = (MX + W + SX) / 2  # trunk in the module→steps gap
    tx2 = (SX + W + OX) / 2  # trunk in the steps→output gap

    nodes = [
        Node("in", input_label, IX, cy - H / 2, W, H, input_style),
        Node("mod", module_label, MX, cy - H / 2, W, H, module_style),
        Node("out", output_label, OX, cy - H / 2, W, H, output_style),
    ]
    edges = [Edge("in", "mod", exit=(1, 0.5), entry=(0, 0.5))]
    for i, s in enumerate(steps):
        sid = f"s{i}"
        scy = top + i * (H + vgap) + H / 2
        nodes.append(Node(sid, s, SX, top + i * (H + vgap), W, H, step_style))
        edges.append(
            Edge("mod", sid, exit=(1, 0.5), entry=(0, 0.5),
                 points=[(tx1, cy), (tx1, scy)])
        )
        edges.append(
            Edge(sid, "out", exit=(1, 0.5), entry=(0, 0.5),
                 points=[(tx2, scy), (tx2, cy)])
        )
    return Diagram(name, nodes, edges, width=int(OX + W + 40),
                   height=int(top + total + 40))


DIAGRAMS: list[Diagram] = []

# --- 1. Top-level architecture (README + architecture.md) --------------------
# A clean horizontal pipeline with the two optional layers hung below the exact
# stage they attach to (clean vertical dashed connectors, no crossings).
DIAGRAMS.append(
    Diagram(
        name="architecture-overview",
        width=1040,
        height=300,
        nodes=[
            Node("pdf", "PDF2HTML", 40, 40, 170, 48, BLUE),
            Node("audit", "Audit", 300, 40, 170, 48, GREEN),
            Node("rem", "Remediate", 560, 40, 170, 48, ORANGE),
            Node("out", "Accessible HTML", 820, 40, 170, 48, GREEN),
            Node("batch", "Batch (optional): orchestrates the whole pipeline at scale",
                 245, 190, 280, 64, PURPLE),
            Node("agent", "Agent (optional): render → fix → verify",
                 555, 190, 180, 64, GRAY),
        ],
        edges=[
            Edge("pdf", "audit", exit=(1, 0.5), entry=(0, 0.5)),
            Edge("audit", "rem", exit=(1, 0.5), entry=(0, 0.5)),
            Edge("rem", "out", exit=(1, 0.5), entry=(0, 0.5)),
            Edge("audit", "batch", dashed=True, exit=(0.5, 1), entry=(0.5, 0)),
            Edge("rem", "agent", dashed=True, exit=(0.5, 1), entry=(0.5, 0)),
        ],
    )
)

# --- 2..5. Core module diagrams (hub layout) ---------------------------------
DIAGRAMS.append(
    hub("module-pdf2html", "PDF Source", "PDF2HTML", BLUE,
        ["BDA Integration", "Image Processing", "HTML Generation"],
        "HTML Output", BLUE)
)
DIAGRAMS.append(
    hub("module-audit", "HTML Input", "Audit Module", GREEN,
        ["Document Checks", "Structure Checks", "Image Checks", "Table Checks"],
        "Audit Report", GREEN, output_style=ORANGE)
)
DIAGRAMS.append(
    hub("module-remediate", "HTML with Issues", "Remediate Module", ORANGE,
        ["AI Remediation Strategies", "Direct Fixes",
         "Table Remediation (direct + AI)"],
        "Remediated HTML", ORANGE)
)
DIAGRAMS.append(
    hub("module-batch", "Document Source", "Batch Module", PURPLE,
        ["Job Management", "AWS Integration (S3 & DynamoDB)",
         "Processing Pipeline (Lambda)"],
        "Job Completion", PURPLE)
)

# --- 6. Managed pipeline (pipeline_guide.md) ---------------------------------
DIAGRAMS.append(
    Diagram(
        name="managed-pipeline",
        width=1130,
        height=460,
        nodes=[
            Node("up", "Upload to S3 (pdf/ or html/)", 40, 165, 160, 54, GRAY),
            Node("trig", "Trigger Lambda", 250, 170, 150, 44, ORANGE),
            Node("conv", "Convert via BDA (PDF path)", 470, 60, 170, 54, BLUE),
            Node("audit", "Audit", 470, 170, 170, 44, GREEN),
            Node("rem", "Agent remediate (AgentCore Runtime)", 700, 165, 180, 54, ORANGE),
            Node("browser", "AgentCore Browser Tool", 700, 55, 180, 54, GRAY),
            Node("out", "accessible/ prefix in S3", 930, 170, 160, 44, GREEN),
            Node("ddb", "DynamoDB job records", 250, 320, 150, 60, CYL),
        ],
        edges=[
            Edge("up", "trig", exit=(1, 0.5), entry=(0, 0.5)),
            # Branch at a shared split corridor (x=435): up to Convert, across to Audit.
            Edge("trig", "conv", "pdf/*.pdf", exit=(1, 0.5), entry=(0, 0.5),
                 points=[(435, 192), (435, 87)]),
            Edge("trig", "audit", "html/*", exit=(1, 0.5), entry=(0, 0.5),
                 points=[(435, 192)]),
            Edge("conv", "audit", exit=(0.5, 1), entry=(0.5, 0)),
            Edge("audit", "rem", exit=(1, 0.5), entry=(0, 0.5)),
            Edge("rem", "browser", exit=(0.5, 0), entry=(0.5, 1)),
            Edge("rem", "out", exit=(1, 0.5), entry=(0, 0.5)),
            Edge("trig", "ddb", "job records", dashed=True,
                 exit=(0.5, 1), entry=(0.5, 0)),
            Edge("rem", "ddb", dashed=True, exit=(0.5, 1), entry=(0.5, 1),
                 points=[(790, 420), (325, 420)]),
        ],
    )
)

# --- 7. API processing pipeline (api_integration_guide.md) -------------------
DIAGRAMS.append(
    Diagram(
        name="api-pipeline-flow",
        width=850,
        height=470,
        nodes=[
            Node("pdf", "PDF Document", 60, 40, 200, 44, GRAY),
            Node("conv", "convert_pdf_to_html()", 60, 120, 200, 44, BLUE),
            Node("html", "HTML Content", 60, 200, 200, 44, BLUE),
            Node("audit", "audit_html_accessibility()", 330, 200, 220, 44, GREEN),
            Node("report", "Accessibility Report", 600, 200, 200, 44, ORANGE),
            Node("rem", "remediate_html_accessibility()", 60, 320, 240, 44, ORANGE),
            Node("remhtml", "Remediated HTML", 360, 300, 200, 40, GREEN),
            Node("remrep", "Remediation Report", 360, 360, 200, 40, GREEN),
        ],
        edges=[
            Edge("pdf", "conv", exit=(0.5, 1), entry=(0.5, 0)),
            Edge("conv", "html", exit=(0.5, 1), entry=(0.5, 0)),
            Edge("html", "audit", exit=(1, 0.5), entry=(0, 0.5)),
            Edge("audit", "report", exit=(1, 0.5), entry=(0, 0.5)),
            Edge("html", "rem", exit=(0.5, 1), entry=(0.42, 0),
                 points=[(160, 300)]),
            Edge("report", "rem", "report", exit=(0.5, 1), entry=(0.5, 1),
                 points=[(700, 430), (180, 430)]),
            Edge("rem", "remhtml", exit=(1, 0.3), entry=(0, 0.5),
                 points=[(330, 322), (330, 320)]),
            Edge("rem", "remrep", exit=(1, 0.7), entry=(0, 0.5),
                 points=[(330, 342), (330, 380)]),
        ],
    )
)

# --- 8. Exception hierarchy (api_integration_guide.md) -----------------------
# File-tree style: one shared trunk dropping from the base class, clean stubs.
_exc_children = [
    ("pdf", "PDFConversionError", BLUE),
    ("audit", "AccessibilityAuditError", GREEN),
    ("rem", "AccessibilityRemediationError", ORANGE),
    ("cfg", "ConfigurationError", PURPLE),
    ("res", "ResourceError", GRAY),
]
_exc_nodes = [Node("base", "DocumentAccessibilityError", 60, 40, 260, 44, GRAY)]
_exc_edges: list[Edge] = []
_trunk_x = 60 + 0.15 * 260  # 99
for i, (cid, clabel, cstyle) in enumerate(_exc_children):
    cy = 110 + i * 48
    _exc_nodes.append(Node(cid, clabel, 150, cy, 250, 34, cstyle))
    _exc_edges.append(
        Edge("base", cid, exit=(0.15, 1), entry=(0, 0.5),
             points=[(_trunk_x, cy + 17)])
    )
DIAGRAMS.append(
    Diagram("exception-hierarchy", _exc_nodes, _exc_edges, width=440, height=400)
)

# --- 9. Agent verify loop (rendered_agent_guide.md) --------------------------
DIAGRAMS.append(
    Diagram(
        name="agent-verify-loop",
        width=940,
        height=230,
        nodes=[
            Node("render", "render_and_probe", 40, 40, 150, 46, BLUE),
            Node("choose", "choose a fix", 230, 40, 130, 46, GRAY),
            Node("apply", "apply_fix", 400, 40, 120, 46, ORANGE),
            Node("verify", "verify (re-render)", 560, 40, 140, 46, GREEN),
            Node("resolved", "resolved", 740, 40, 120, 46, GREEN),
        ],
        edges=[
            Edge("render", "choose", exit=(1, 0.5), entry=(0, 0.5)),
            Edge("choose", "apply", exit=(1, 0.5), entry=(0, 0.5)),
            Edge("apply", "verify", exit=(1, 0.5), entry=(0, 0.5)),
            Edge("verify", "resolved", "passed", exit=(1, 0.5), entry=(0, 0.5)),
            Edge("verify", "choose", "not fixed: try again", dashed=True,
                 exit=(0.5, 1), entry=(0.5, 1), points=[(630, 150), (295, 150)]),
        ],
    )
)

# --- 10 & 11. CLI output trees (cli_guide.md) --------------------------------
DIAGRAMS.append(
    Diagram(
        name="output-tree-convert",
        width=640,
        height=330,
        nodes=[
            Node("root", "output-directory/", 40, 30, 560, 34, MONO),
            Node("ehtml", "extracted_html/  — HTML files", 90, 78, 510, 30, MONO),
            Node("doc", "document.html  — combined file (with --single-file)", 140, 114, 460, 30, MONO),
            Node("p0", "page-0.html  — individual pages (otherwise)", 140, 150, 460, 30, MONO),
            Node("edots", "…", 140, 186, 460, 26, MONO),
            Node("images", "images/  — extracted images", 90, 224, 510, 30, MONO),
            Node("img0", "image-0.png", 140, 260, 460, 30, MONO),
            Node("idots", "…", 140, 296, 460, 26, MONO),
        ],
    )
)
DIAGRAMS.append(
    Diagram(
        name="output-tree-process",
        width=700,
        height=250,
        nodes=[
            Node("root", "output-directory/", 40, 30, 620, 34, MONO),
            Node("html", "html/  — converted HTML + extracted images", 90, 78, 570, 30, MONO),
            Node("audit", "audit_report.[json|html|txt]  — audit report", 90, 114, 570, 30, MONO),
            Node("rem", "remediated_NAME.html  — final remediated HTML", 90, 150, 570, 30, MONO),
            Node("note",
                 "(remediated_document.html with --single-page; "
                 "remediated_html/ with --multi-page)",
                 140, 186, 520, 40, MONO + "fontColor=#777777;"),
        ],
    )
)


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    for d in DIAGRAMS:
        path = os.path.join(here, f"{d.name}.drawio")
        with open(path, "w", encoding="utf-8") as f:
            f.write(render(d))
        print(f"wrote {path}")
    print(f"\n{len(DIAGRAMS)} diagram source(s) generated.")


if __name__ == "__main__":
    main()
