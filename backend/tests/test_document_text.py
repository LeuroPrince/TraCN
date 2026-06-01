from io import BytesIO

from docx import Document

from app.document_text import DocumentTextError, extract_document_text


def test_extracts_plain_text() -> None:
    text = extract_document_text("profile.txt", "text/plain", "神经动力学建模".encode("utf-8"))

    assert "神经动力学" in text


def test_extracts_docx_text() -> None:
    buffer = BytesIO()
    document = Document()
    document.add_paragraph("Computational neuroscience and fMRI decoding")
    document.save(buffer)

    text = extract_document_text(
        "profile.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        buffer.getvalue(),
    )

    assert "fMRI decoding" in text


def test_extracts_pdf_text() -> None:
    text = extract_document_text("profile.pdf", "application/pdf", make_pdf("Computational neuroscience PDF profile"))

    assert "Computational neuroscience" in text


def test_rejects_unsupported_file_type() -> None:
    try:
        extract_document_text("profile.png", "image/png", b"not text")
    except DocumentTextError as exc:
        assert "Unsupported file type" in str(exc)
    else:
        raise AssertionError("Expected unsupported file type to be rejected")


def make_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    buffer = BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, item in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{index} 0 obj\n".encode("ascii"))
        buffer.write(item)
        buffer.write(b"\nendobj\n")
    xref_offset = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    buffer.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return buffer.getvalue()
