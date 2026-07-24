from fastapi import APIRouter, UploadFile, File , HTTPException
from app.services.parse_service import procesar_archivo
from app.models.schemas import ImportResponse
import os
from app.services.parsers import PARSERS, EXTENSION_FALLBACK
router = APIRouter(tags=["Import"])

@router.post("/import" , response_model=ImportResponse)
async def importar_archivo(file: UploadFile = File (...)):
    try:
        parseo = await procesar_archivo(file)
        return parseo
    except ValueError as v :
        msg_info = str(v)
        ext = os.path.splitext(file.filename)[1].lower()

        if msg_info == "AI_PARSER_ERROR":
            if file.content_type not in PARSERS and ext not in EXTENSION_FALLBACK:
                raise HTTPException(
                    status_code=415,
                    detail=f"Formato {ext} no soportado. TIPO DE ARCHIVO NO VALIDO"
                )
            else: 
                raise HTTPException(
                    status_code=422,
                    detail="ERROR DURANTE EL PARSEO"
                )
