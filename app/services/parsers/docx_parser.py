import io

from docx import Document

def parse_docx(file_bytes: bytes) -> str:
    document = Document(io.BytesIO(file_bytes))
    return "\n".join(pag.text for pag in document.paragraphs if pag.text.strip())