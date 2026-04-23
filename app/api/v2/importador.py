from fastapi import APIRouter, UploadFile, File
from app.services.parse_service import procesar_archivo
from app.models.schemas import ImportResponse

router = APIRouter(tags=["Import"])

@router.post("/import" , response_model=ImportResponse)
async def importar_archivo(file: UploadFile = File (...)):
    return await procesar_archivo(file)
