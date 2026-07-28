""" 
Módulo de rutas para la gestión de informes clínicos generados por IA.
Este router maneja la comunicación con OpenRouter y la persistencia de resúmenes
"""

from fastapi import APIRouter, HTTPException, Depends,status, Request
from typing import List

from app.core.limiter import limiter


from app.models.schemas import (
    ModeloResumen,
    ModeloRequest, 
    ResumeniaRequest, 
    ResumeniaResponse, 
    ModelInfo
)
from app.services.ai_service import AIService

import app.repositories.ia_repository as db_ia
import app.services.filtrar_visitas_service as filtro_v
from app.api.dependencies import get_ai_service
from app.core.logging import get_logger
import time

# Configuración de Logger y Router
logger = get_logger(__name__)
router = APIRouter(prefix="/informes", tags=["informes"])

#-----------------------------------------------------------------------------------
# ENDPOINTS DE DIAGNOSTICO (Utilidades)
#-----------------------------------------------------------------------------------

@router.get("/models", response_model=List[ModelInfo])
async def list_models(ai_service: AIService = Depends(get_ai_service)):
    """
    Obtiene el listado de modelos disponibles desde el proveedor (OpenRouter).
    Sirve para verificar la conectividad con la API externa.
    """
    try:
        models = await ai_service.list_models()
        return models
    except Exception as e:
        logger.error(f"Error al obtener modelos: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error de conexión con el proveedor {str(e)}"
            )

#-----------------------------------------------------------------------------------    
# ENDPOINTS DE NEGOCIO (Gestión de informes)
#-----------------------------------------------------------------------------------

@router.post("/resumenia", response_model=ResumeniaResponse)
@limiter.limit("10/minute")
async def resumen_ia(request : Request, body: ResumeniaRequest, ai_service: AIService = Depends(get_ai_service)):
    """
    Genera un nuveo resumen clínico utilizando IA.
    1. Registra la petición en la base de datos (Input).
    2. Envía los datos clínicos al modelo seleccionado.
    3. Persiste el resumen generado por la IA en la base de datos (Output).
    4. Devuelve el análisis procesado al cliente.
    """

    #----- INICIO CRONOMETRO --------
    inicio_c = time.perf_counter()
    resultado_metrica = "FALLO_DESCONOCIDO"
    error_msg = None
    id_request = None #Inicialización en None para evitar errores de ambito en el except. 


    try:
        logger.info(f"Procesando resumen con modelo: {body.model}")
        
        await filtro_v.filtrar_visitas(body)
        # Guardar registro de la solicitud (input)
        guardar_request = await db_ia.save_request(
            body.id_paciente,
            body.datos_clinicos
        )
        if not guardar_request:
            # Si es None, enviamos al cliente el resumen persistido para ese request exacto
            resultado_metrica = "CACHE_HIT"
            id_paciente = body.id_paciente
            data = db_ia.total_resumenes_ia_paciente(id_paciente)

            # VALIDACIÓN ANTI-INDEXERROR: verifica si la lista tiene elementos
            if not data:
                logger.warning(f"Cache hit detectado pero no se encontraron resúmenes previos para el paciente {id_paciente}. ")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Solicitud duplicada. No se encontraror resúmenes previos para este caso."
                )
            
            return data[0]
        else:
            resultado_metrica = "CACHE_MISS"
            id_request = guardar_request["id_request_ia"]
            fecha_actual = guardar_request["fecha_request"]
        
        # Generación y persistencia automática del resumen (Output)
        # Nota: 'generar_resumenia' internamente guarda el resultado en DB
            
            data = await ai_service.generar_resumenia(
                body,
                id_request,
                fecha_actual
                )
            return data

    except ValueError as e:
        resultado_metrica = "FALLO"
        error_msg = str(e)

        # Solo se intenta eliminar de la DB si se genera un id_request válido
        if id_request:
            try:
                db_ia.eliminar_registro(id_request)
                logger.info(f"Registro {id_request} eliminado por fallo en IA.")
            except Exception as delete_error:
                logger.error(f"No se pudo limpiar el registro fallido: {str(delete_error)}")
        
        # Mapeo de errores específicos del servicio de IA
        if error_msg in ( "AI_TIMEOUT", "AI_TIMEOUT_CONNECTION", "AI_TIMEOUT_READ", "AI_CIRCUIT_OPEN"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                detail="El servicio de IA no está disponible temporalmente. Por favor, intenta de nuevo."
            )
        elif error_msg == "AI_AUTH_ERROR":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail="Error de configuración interna (Auth)."
            )
        elif error_msg == "AI_VALIDATION_ERROR":
            raise HTTPException(status_code=500, detail="La IA rechazo los datos por formato invalido.")
        
        elif error_msg == "AI_PROVIDER_ERROR":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, 
                detail="El servicio de IA no está disponible en este momento."
            )
        # Manejo de validacion de salida
        elif error_msg == "AI_RESPONSE_INVALID":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, 
                detail="La IA respondió correctamente pero el formato del resumen no es válido."
            )
        elif error_msg == "AI_INPUT_INVALID":
            raise HTTPException(
                status_code=422, 
                detail="El contenido proporcionado no es un caso clínico veterinario válido."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail="Ocurrió un error inesperado al procesar la IA."
            )

    finally:
        fin_c = time.perf_counter()
        latencia = fin_c - inicio_c

        db_ia.registrar_metricas_db(
            resultado= resultado_metrica,
            segundos= latencia,
            error= error_msg
        )

@router.get("/resumenia", response_model=List[ModeloResumen])
def listar_todos_los_resumenes():
    """
    Recupera el historial completo de resúmenes generados por la IA en el sistema.
    """
    try:
        return db_ia.total_resumenes_ia()
    except ValueError:
        raise HTTPException(
            status_code=500,
            detail="Error al acceder a la base de datos de resúmenes"
        )

@router.get("/resumenia/{id_paciente}", response_model=list[ModeloResumen])
def resumenes_paciente(
    id_paciente :  str, 
    ):
    
    """
    Obtiene todos los informes/resúmenes generados para un paciente específico.
    """
    try:
        # 1. Llamada al servicio: consultamos la persistencia (DB) filtando por ID de paciente
        data = db_ia.total_resumenes_ia_paciente(id_paciente)
        
        # 2. Validación de existencia: si la lista vuelve vacia, informamos al cliente
        # Es importante distinguir ente un error de servidor y un dato no encontrado (404)
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"No hay historial de informes para el paciente ID: {id_paciente}"
            )
        # 3. Retorno de datos: FastAPI se encarfa de serializar la lista 'data' a formato JSON
        return data
    
    except ValueError:
        # 4. Manejo de excepciones: capturamos errores de lógica de negocio o de base de datos
        # Respondemos con un 500 para indicar que el problema fue del lado del servidor
        raise HTTPException(
            status_code=500,
            detail="Error al consultar el historial del paciente"
        )

#---------------------------------------------------------------------------------------
# ENDPOINTS DE PERSISTENCIA (Logs de Solicitudes)
#---------------------------------------------------------------------------------------

@router.get("/request", response_model=List[ModeloRequest])
def listar_requests():
    """
    Lista todos los logs de peticiones enviadas (Input original del usuario).
    """
    try:
        # 1. Recuperamos la totalidad de los inputs enviados a la IA.
        # Útil para auditoria y ver qué datos están enviando los usuarios.
        return db_ia.total_requests()
    
    except Exception as e:
        # 2. logueamos el error técnico para el desarrollador.
        logger.error(f"Error al cargar datos: {str(e)}")
        # 3. Respondemos un mensaje genérico al cliente por seguridad.
        raise HTTPException(
            status_code=500,
            detail=f"No se pudieron cargar los registros de peticiones. {str(e)}")


@router.get("/request/{id_paciente}", response_model=list[ModeloRequest])
def requests_paciente(
    id_paciente : str , 
):
    
    """
    Lista los logs de peticiones de un paciente específico.
    """
    try:
        # 1. filtramos los inputs originales en la base de datos por el ID del paciente
        data = db_ia.total_request_paciente(id_paciente)
        
        # 2. Control de flujo: Si el paciente existe pero nunca envió nada a la IA
        # devolvemos un 404 para indicar ausencia de datos
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"No se registraron peticíones para el paciente ID: {id_paciente}"
            )
        
        # 3. Retornamos la lista de objetos 'ModeloRequest'
        return data
    
    except ValueError:
        # 4. En caso de error en la consulta o falla de base de datos.
        raise HTTPException(
            status_code=500,
            detail="Error al consultar los registros del paciente"
        )

    
from fastapi.responses import FileResponse
import os
@router.get("/descargar-logs")
async def descargar_logs():
    # El nombre del archivo que se crea en la raíz del contenedor
    log_filename = "api_vetween_ia.log"
    
    # Verificamos si el archivo existe en el sistema de archivos de Docker
    if not os.path.exists(log_filename):
        raise HTTPException(status_code=404, detail="El archivo de log aún no se ha generado.")

    try:
        # FileResponse es perfecto para esto: fuerza la descarga del archivo completo
        return FileResponse(
            path=log_filename, 
            filename="logs_produccion_vetween.txt", 
            media_type='text/plain'
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al leer el log: {str(e)}")

#---------------------------------------------------------------------------------------
# ENDPOINTS DE EXPORTACIÓN (Generación de Reportes PDF)
#---------------------------------------------------------------------------------------


import ast
from app.services.generar_reporte_pdf import crear_reporte_clinico_pdf
@router.get("/resumenia/{id_paciente}/pdf")
async def descargar_resumen_pdf(id_paciente: str):
    """
    Busca el último resumen clínico guardado de un paciente,
    delega la creación del PDF al servicio y fuerza su descarga.
    """
    try:
        # 1. Recuperamos el historial desde la base de datos
        data = db_ia.total_resumenes_ia_paciente(id_paciente)
        
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró historial clínico guardado para el paciente ID: {id_paciente}."
            )
        
        # 2. Tomamos el registro más reciente y lo formateamos
        ultimo_resumen = data[0]
        resumen_dict = ultimo_resumen.dict() if hasattr(ultimo_resumen, "dict") else ultimo_resumen

        # Parseo seguro del string de IA con ast
        raw_resumen = resumen_dict.get("resumen_estructurado", "{}")
        if isinstance(raw_resumen, str):
            try:
                ia_data = ast.literal_eval(raw_resumen)
            except Exception:
                ia_data = {"descripcion_clinica": raw_resumen}
        else:
            ia_data = raw_resumen

        # 2. Obtenemos los datos demográficos desde tu otra tabla (requests/pacientes)
        data_paciente = db_ia.total_request_paciente(id_paciente) 
        if not data_paciente:
            raise HTTPException(status_code=404, detail="No se encontraron datos clínicos de filiación para el paciente.")
        # Desenvolvemos la lista
        primer_registro = data_paciente[0] if isinstance(data_paciente, list) else data_paciente
        paciente_dict = primer_registro.dict() if hasattr(primer_registro, "dict") else primer_registro
        
        # 🔍 LA CLAVE MAESTRA: Todo vive dentro de 'datos_clinicos'
        datos_clinicos = paciente_dict.get("datos_clinicos", {})
        
        # Ahora sí extraemos 'paciente' desde donde corresponde
        paciente_info = datos_clinicos.get("paciente", {})
        # 3. Definimos el nombre del archivo final
        pdf_filename = f"resumen_clinico_{id_paciente}.pdf"

        # 4. Delegamos la creación al servicio modularizado
        crear_reporte_clinico_pdf(
            id_paciente=id_paciente,
            paciente_info=paciente_info,
            ia_data=ia_data,
            file_path=pdf_filename
        )

        # 5. Respondemos enviando el PDF
        return FileResponse(
            path=pdf_filename,
            filename=pdf_filename,
            media_type="application/pdf"
        )

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error en el endpoint de exportación PDF: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Ocurrió un error inesperado al compilar el documento PDF. {str(e)}"
        )