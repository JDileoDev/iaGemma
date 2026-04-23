import fitz

def parse_pdf(file_bytes: bytes) -> str:
    document = fitz.open(stream=file_bytes, filetype="pdf")
    return "".join(page.get_text() for page in document).strip()