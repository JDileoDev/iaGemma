from app.core.database import supabase
from app.core.logging import get_logger

logger = get_logger(__name__)
async def filtrar_visitas(request):
    try: 
        datos = request.datos_clinicos.model_dump()
        ids_visitas_request =[visita["id_visitas"] for visita in datos["visitas"]]
        resultado = (
            supabase
            .table("ia_request")
            .select("datos_clinicos->visitas")
            .eq("id_paciente", request.id_paciente)
            .execute()
        )
    

        ids_sucios =[v.get("id_visitas") for visitas in resultado.data for v in visitas.get("visitas") ]
        
        ids_visitas_db = set(ids_sucios)
        
        ids_nuevos = [ids for ids in ids_visitas_request if ids not in ids_visitas_db]
        
        if ids_nuevos:
                request.datos_clinicos.visitas = [
                    v for v in request.datos_clinicos.visitas if v.id_visitas in ids_nuevos
                ]
        return request
    except Exception as e:
        logger.error(f"error al filtrar las visitas {e}")

