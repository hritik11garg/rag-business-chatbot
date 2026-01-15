from pathlib import Path
from pypdf import PdfReader
import re



def normalize_text(text: str) -> str:
    """
    Normalize PDF-extracted text by merging broken lines
    and cleaning excessive whitespace.
    """

    # Split into raw lines
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    merged_lines: list[str] = []
    buffer = ""

    for line in lines:
        # If line ends with sentence punctuation, flush buffer
        if re.search(r"[.!?]$", line):
            buffer = f"{buffer} {line}".strip()
            merged_lines.append(buffer)
            buffer = ""
        else:
            # Otherwise, assume line continues
            buffer = f"{buffer} {line}".strip()

    # Flush remaining buffer
    if buffer:
        merged_lines.append(buffer)

    # Join paragraphs
    cleaned_text = "\n\n".join(merged_lines)

    # Final cleanup of excessive spaces
    cleaned_text = re.sub(r"\s+", " ", cleaned_text)

    return cleaned_text.strip()


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extracts and returns all text from a PDF file.

    Assumptions:
    - PDF is text-based (not scanned images)
    - OCR is not handled here
    """

    pdf_path = Path(file_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found at {file_path}")

    reader = PdfReader(pdf_path)

    extracted_text: list[str] = []

    for page_number, page in enumerate(reader.pages):
        text = page.extract_text()

        if text:
            extracted_text.append(text)

    return "\n".join(extracted_text)




def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100,
) -> list[str]:
    """
    Split text into overlapping chunks.

    Args:
        text: Full extracted document text
        chunk_size: Number of characters per chunk
        overlap: Number of overlapping characters

    Returns:
        List of text chunks
    """

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[str] = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]

        chunks.append(chunk.strip())

        start = end - overlap

    return chunks
