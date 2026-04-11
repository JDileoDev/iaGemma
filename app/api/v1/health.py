"""Health check API endpoints."""

from fastapi import APIRouter , Depends
from datetime import datetime

from app.models.schemas import HealthResponse
from app.config.settings import settings
from app.core.logging import get_logger
from app.test.test_ia import ping_ia
import time , supabase
from app.services.ai_service import AIService
from app.api.dependencies import get_ai_service
import app.test.test_ia as test_ia


logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health_check(ai_service: AIService = Depends(get_ai_service)):
    """
    Health check endpoint.
    
    Returns the current health status of the service.
    """
    # Reango ajustados para IA (en segundos)
    LATENCIA_OK = 3.5
    LATENCIA_WARN = 7.0
    
    # --- CHECK DE NVIDIA NIM ---
    # 1. Empezamos el cronómetro de alta precisión
    nim_status = "ok"
    inicio = time.perf_counter() 

    try:
        await ping_ia()

        # 2. calculamos la diferencia
        latencia = time.perf_counter()  - inicio 
    except Exception as e: 
        nim_status = "unreachable"
        logger.error(f"Health check NIM failed: {e}")
    
    # --- CHECK SUPABASE ---
    supabase_status = "ok"
    try:
        supabase.table("resumen_ia").select("id_resumenia").limit(1).execute()
    except Exception as e:
        supabase_status = "unreachable"
        logger.error(f"Helath check Supabase failed: {e}")

    # --- Estado  general ---
    if nim_status == "unreachable" or supabase_status == "unreachable":
        tipo_estado = "unhealty"
        mensaje_estado = f"Servicios no disponibles - NVIDIA NIM: {nim_status} | Supabase: {supabase_status}"
    # 3. Lógica de decisión según el rendimiento (Umbral de 0.5 seg)
    elif latencia <= LATENCIA_OK:
        # Estado óptimo: Todo funciona según los estándares
        mensaje_estado = f"Servicio operativo - NVIA NIM: {nim_status} | Supabase: {supabase_status}"
        tipo_estado = "healthy"
    elif latencia <= LATENCIA_WARN:
        # Estado degradado: El servicio responde, pero está lento
        mensaje_estado = f"Latencia alta - NVIDIA NIM : {nim_status} | Supabase: {supabase_status}"
        tipo_estado = "degraded"
    else:
        mensaje_estado = f"Latencia crítica - NVIDIA NIM : {nim_status} | Supabase: {supabase_status}"
        tipo_estado = "Unhealthy"

    
    # 4. Construir y retornar la respuesta estructurada
    return HealthResponse(
        status=tipo_estado,
        timestamp=datetime.now(),
        version=settings.app_version,
        message=f"{mensaje_estado}. Latencia NVIDIA NIM: {latencia:.4f}s" 
    )
