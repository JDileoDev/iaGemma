from fastapi import UploadFile
import httpx
from app.services.parsers import PARSERS, EXTENSION_FALLBACK
from app.models.schemas import ImportResponse
from app.core.logging import get_logger

logger = get_logger(__name__)

async def procesar_archivo(file: UploadFile) -> ImportResponse:
    
    try:
    # Detectar parser
        parser = PARSERS.get(file.content_type)
        if not parser:
            extension = "." + file.filenamersplit(".", 1)[-1].lower()
            parser = EXTENSION_FALLBACK.get(extension)
        # Parsear
        content = parser(await file.read())
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code

        logger.error(f"error {status_code} Tipo de dato no soportado: {file.content_type}")
        if status_code == 415:
            raise ValueError ("AI_PARSER_ERROR")
        if status_code == 422:
            logger.error(f"error al parsear {e}")
            raise ValueError("AI_PARSER_ERROR")
    return ImportResponse(
        filename=file.filename,
        mime_type=file.content_type,
        caracteres=len(content),
        contenido=content
    )


