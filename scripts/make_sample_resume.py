"""Regenerate data/sample_resume.pdf with plain stdlib.

Neither reportlab nor fpdf2 is a dependency, so this writes a minimal valid
PDF by hand: one page, Helvetica, one text operator per line. The demo uploads
this file through the normal /api/resume/upload flow, so it must stay
extractable by PyPDF2 (ASCII only). Run from the repo root:

    python scripts/make_sample_resume.py
"""
from __future__ import annotations

import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sample_resume.pdf"

RESUME_TEXT = """\
Name: Chen Xiaoyu
Email: xiaoyu.chen@example.com
Phone: +86-13800138000

Education:
- The University of Hong Kong | MS Computer Science | 2024-2026
- Sun Yat-sen University | BS Software Engineering | 2020-2024

Experience:
- Moonshot AI | LLM Infrastructure Intern | 2025.03-2025.09: Built the evaluation harness for model releases in Python, automated regression runs with Docker and Kubernetes, and cut manual review time by half.
- Tencent | Backend Development Intern | 2023.06-2023.12: Implemented a Redis backed hot key cache for a high traffic mini program API in Python and Go; p99 latency dropped from 220ms to 90ms at 30k QPS in staging.

Skills:
Python, PyTorch, MySQL, Redis, Docker, Kubernetes, Linux, SQL, NLP, machine learning, recommendation systems, distributed systems, data analysis, Git

Projects:
- Retrieval augmented QA over arXiv papers with PyTorch and FAISS, bilingual reranking, 92 percent top-1 accuracy on an internal benchmark.
- A small Raft implementation in Python with fault injection tests for leader election and log replication.
"""

WRAP_WIDTH = 88


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrapped_lines() -> list[str]:
    lines: list[str] = []
    for raw in RESUME_TEXT.splitlines():
        if len(raw) <= WRAP_WIDTH:
            lines.append(raw)
            continue
        indent = "  " if raw.startswith("- ") else ""
        lines.extend(textwrap.wrap(raw, WRAP_WIDTH, subsequent_indent=indent))
    return lines


def build_pdf() -> bytes:
    ops = ["BT", "/F1 10 Tf", "50 760 Td", "13 TL"]
    for i, line in enumerate(_wrapped_lines()):
        if i:
            ops.append("T*")
        ops.append(f"({_escape(line)}) Tj")
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    return bytes(pdf)


if __name__ == "__main__":
    OUT.write_bytes(build_pdf())
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")
