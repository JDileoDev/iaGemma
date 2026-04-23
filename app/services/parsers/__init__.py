from . import pdf_parser, docx_parser, image_parse

PARSERS = {
    "application/pdf": pdf_parser.parse_pdf,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": docx_parser.parse_docx,
    "image/jpeg": image_parse.parse_image,
    "image/png": image_parse.parse_image,
}

EXTENSION_FALLBACK = {
    ".pdf": pdf_parser.parse_pdf,
    ".docx": docx_parser.parse_docx,
    ".jpg": image_parse.parse_image,
    ".jpeg": image_parse.parse_image,
    ".png": image_parse.parse_image,
}