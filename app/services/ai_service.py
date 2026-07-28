"""
Servicio central de Inteligencia Artificial.
Gestiona la lógica de comunicación con OpenROuter, el procesamiento de 
prompts y la persistencia de datos en Supabase.
"""

import httpx
import json

from datetime import datetime
from typing import List
from app.core.database import supabase
from app.config.settings import settings
from app.models.schemas import (  
    ResumeniaRequest, 
    ResumeniaResponse, 
    ModelInfo,
)
from app.core.logging import get_logger
from app.core.security import mask_api_key
from app.services.gestion_vacunas import evaluar_vacunas
from app.core.prompt_manager import cargar_prompt
from app.repositories import ia_repository as db_ia
from app.services.filtrar_visitas_service import filtrar_visitas
from app.core.circuit_breaker import nim_breaker , CircuitBreaker


logger = get_logger(__name__)


class AIService:
    """
    Sercivio para imteractuar con la API de OpenROuter y gestionar 
    el ciclo de vida de los informes de IA.
    """

    def __init__(self):
        """
        inicializa el cliente HTTP asíncronico con la configuracion de OpenRouter.
        Se utiliza httpx para manejar petiiones no bloqueantes de forma eficiente.
        """
        # Configruación del cliente con headers obligatorios de OpenRouter
        self.client = httpx.AsyncClient(
            base_url=settings.nvidia_api_url,
            headers={
                "Authorization": f"Bearer {settings.nvidia_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/JDileoDev/template-python-fastapi",
                "X-Title": settings.app_name,
            },
            timeout=httpx.Timeout(
                connect=10.0, # 10 seg- para establecer conexion con NIM
                read=120.0,  # 60 seg. para recibir la respuesta
                write=10.0, # 10 seg. para enviar payload
                pool=5.0 # 5 seg. para obtener una conexión del pool
            ) 
        )
        # Log de confirmación con enmascaramiento de credenciales por seguridad
        logger.info(f"AI Service initialized with API key: {mask_api_key(settings.nvidia_api_key)}")  

    async def list_models(self) -> List[ModelInfo]:
        """List available models from OpenRouter."""
        try:
            logger.info("Fetching available models from NVIDIA NMI")
            response = await self.client.get("/models")
            response.raise_for_status()
            
            data = response.json()
            models_data = data.get("data", [])
            
            models = [
                ModelInfo(
                    id=model.get("id", ""),
                    name=model.get("name"),
                    description=model.get("description"),
                    pricing=model.get("pricing")
                )
                for model in models_data
            ]
            
            logger.info(f"Retrieved {len(models)} models")
            return models
            
        except httpx.HTTPStatusError as e:
            error_msg = f"NVIDIA NMI API error: {e.response.status_code} - {e.response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Error fetching models: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    async def health_check(self) -> bool:
        """Check if the AI service is healthy."""
        try:
            # Try to fetch models as a simple health check
            await self.list_models()
            return True
        except Exception as e:
            logger.error(f"AI service health check failed: {str(e)}")
            return False

    async def generar_resumenia(self, 
                                request: ResumeniaRequest ,
                                id_request_ia: str,
                                fecha_actual: str
                                ) -> ResumeniaResponse :
        """Cordina la generación del resumen médico con IA y su persistencia
        en la base de datos."""
        
        fecha_referencia = datetime.fromisoformat(fecha_actual).strftime("%Y-%m-%d")
        
        datos_modelo = request.datos_clinicos

        resultado_sanitario = evaluar_vacunas(
            datos_modelo.vacunas,
            fecha_referencia
        )
        
        datos = datos_modelo.model_dump()
        
        datos["evaluacion_sanitaria"] = resultado_sanitario
        datos["fecha_actual"] = fecha_referencia

        visitas = datos["visitas"]

        visitas_ordenadas = sorted(
        visitas,
        key=lambda v: v["fecha"],
        reverse=True
        )

        datos["visitas"] = visitas_ordenadas
        
        # 1. Prompt Engineering: Cargamos instruccions externas y armamos el historial
        system_prompt = cargar_prompt()
        resumen_previo = await db_ia.obtener_ultimo_resumen(request.id_paciente)
        messages = [
            {
                "role": "system", 
                "content": f"{system_prompt}<|eot|>"
            },
            {
                "role": "user", 
                "content": (
                    f"CON ESTE CONTEXTO {resumen_previo}\n Y ESTOS DATOS DEL PACIENTE:\n"
                    f"```json\n{datos}\n```\n"
                    f"{'El paciente es RECURRENTE, ya tiene historial previo. El tipo_paciente DEBE ser Recurrente.' if resumen_previo else ''}\n"
                    "Transformalos en un resumen narrativo fluido, profesional y humano.<|eot|>"
                )
            }
        ]   

        # 2. Preparacion del Payload siguiendo el contrato de OpenRoute/Gemini
        modelo_utilizado = request.model
        payload = {
            "model": modelo_utilizado,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": request.stream,
            "response_format": { "type": "json_object" }
        }

        try:
            # 3. LLamada a la API externa
            logger.info(f"Enviando solicitud de completado a modelo: {request.model}")
            
            try:
                # -- INTENTO 1: modelo Principal con su respectivo breaker --
                nim_breaker.call()
                response = await self.client.post(
                    "/chat/completions", 
                    json=payload,
                    timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0)
                )
                response.raise_for_status()
                data = response.json()
                
                # VALICACION SEMANTICA - INTENTO 1
                texto_ia = data["choices"][0]["message"]["content"]
                try:
                    contenido_json = json.loads(texto_ia)
                    if contenido_json.get("error") == "INPUT_INVALIDO":
                        if contenido_json.get("motivo") == "fuera_de_ambito":
                            logger.info("[Intento 1] Fuera de ámbito detectado. Cortando flujo sin respaldos.")
                            raise ValueError("AI_INPUT_INVALID")

                        logger.warning(f"[Intento 1] Fallo de procesamiento clínico en {modelo_utilizado}. Forzando fallback... ")
                        raise ValueError("IA_SEMANTIC_PROCESSING_ERROR")
                except json.JSONDecodeError:
                    logger.warning(f"[Intento 1] JSON roto devuelto por {modelo_utilizado}. forzando fallback...")
                    raise ValueError("IA_JSON_DECODE_ERROR")
                nim_breaker.success()
                

            except Exception as e_principal:
                if str(e_principal) == "AI_INPUT_INVALID":
                    raise e_principal
                # Captura por si falla el principal o el breaker está abierto.
                logger.warning(
                    f"Falla en modelo principal ({modelo_utilizado}) o Circuit Breaker abierto. "
                    f"Detalle: {str(e_principal)}. Activando motor de respaldo 1..."
                )
                
                if "CircuitBreaker" in type(e_principal).__name__ or "Open" in type(e_principal).__name__:
                    logger.error(f"Circuit breaker abierto - NVIDIA NIM no disponible temporalmente {e_principal}")
                    raise ValueError("AI_CIRCUIT_OPEN")
                
                try:
                    # --- INTENTO 2: Fallback automático a Llama 3.2 90b ---
                    modelo_utilizado = "nvidia/llama-3.3-nemotron-super-49b-v1"
                    payload["model"] = modelo_utilizado
                    payload["temperature"] = 0.0  # Forzamos consistencia en el JSON
                    
                    logger.info(f"Reintentando peticion con modelo de respaldo: {modelo_utilizado}")
                    
                    response = await self.client.post(
                        "/chat/completions", 
                        json=payload,
                        timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0)
                    )
                    response.raise_for_status()
                    data = response.json()

                    # VALIDACIÓN SEMÁNTICA - INTETO 2
                    texto_ia = data["choices"][0]["message"]["content"]
                    try:
                        contenido_json = json.loads(texto_ia)
                        if contenido_json.get("error") == "INPUT_INVALIDO":
                            if contenido_json.get("motivo") == "fuera_de_ambito":
                                logger.info("[Intento 2] Fuera de ámbito detectado. Cortando flujo.")
                                raise ValueError("AI_INPUT_INVALID")

                            logger.warning(f"[Intento 2] Fallo clínico en {modelo_utilizado}. Yendo al último recurso...")
                            raise ValueError("IA_SEMANTIC_PROCESSING_ERROR")
                    except json.JSONDecodeError:
                        logger.warning(f"[Intento 2] JSON roto en {modelo_utilizado}. Yendo al último recurso.")
                        raise ValueError("IA_JSON_DECODE_ERROR")
                    
                
                except Exception as e_backup_1:
                    if str(e_backup_1) == "AI_INPUT_INVALID":
                        raise e_backup_1
                    logger.warning(
                        f"Falla en primer modelo de respaldo ({modelo_utilizado}). "
                        f"Detalle: {str(e_backup_1)}. Activando segundo motor de respaldo..."
                    )
                    
                    # --- INTENTO 3: Fallback automático a Llama 3.1 70b ---
                    modelo_utilizado = "meta/llama-3.1-70b-instruct"
                    payload["model"] = modelo_utilizado
                    payload["temperature"] = 0.0  
                    
                    logger.info(f"Reintentando peticion con segundo modelo de respaldo: {modelo_utilizado}")
                    
                    response = await self.client.post(
                        "/chat/completions", 
                        json=payload,
                        timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0)
                    )
                    response.raise_for_status() # lanza excepción si el status no es 2xx
                    data = response.json()

                    texto_ia = data["choices"][0]["message"]["content"]
                    try:
                        contenido_json = json.loads(texto_ia)
                    #  LA CLAVE ACÁ: Si el último recurso también confirma que es inválido/fuera de ámbito...
                        if contenido_json.get("error") == "INPUT_INVALIDO":
                            logger.warning("[Intento 3] Último modelo de respaldo también devolvió un JSON no válido.")
                            raise ValueError("AI_INPUT_INVALID")  # <-- Esto gatilla tu 422 en el controladoro 
                        
                    except Exception as final_e:
                        if str(final_e) == "AI_INPUT_INVALID":
                            raise final_e
                        logger.error(
                            "El último modelo de respaldo también devolvió un JSON no válido."
                            f"Detalle: {str(final_e)}"
                            )

            
            # 4. Validación de respuesta: Verificamos que la IA haya devuelto texto
            if "choices" not in data or not data["choices"]:
                raise ValueError("AI_RESPONSE_INVALID")
            content = data["choices"][0]["message"]["content"]

            # 5. Limpieza del contenido: quitamos posibles bloques de código Markdown
            content_clean = content.replace("```json", "").replace("```", "").strip()
            
            # 6. Carga del JSON generado por la IA
            print(f"--- CONTENIDO RECIBIDO ---\n{content_clean}\n--- FIN ---")
            ia_output = json.loads(content_clean)
            
            # 7. Lógica de limpieza: Si el input fue inválido, eliminamos el registro de auditoria
            if isinstance(ia_output, dict) and ia_output.get("error") == "INPUT_INVALIDO":
                    logger.warning(f"Inteto de resumen invalido para paciente {request.id_paciente}")
                    logger.error(f"AI_INPUT_INVALID: {str(request)}")
                    raise ValueError("AI_INPUT_INVALID")
            
            # 8. Extracción de campos obligatorios según el Schema
            resumen_completo = ia_output["resumen_completo"]
            resumen_estructurado = ia_output["resumen_estructurado"]

            # 9. Persistencia del Output: Guardamos el análisis final en la DB
            db_response = supabase.table("resumen_ia").insert({
                "id_paciente" : request.id_paciente,
                "id_request_ia": id_request_ia,
                "modelo": request.model,
                "resumen_completo": resumen_completo,
                "resumen_estructurado": resumen_estructurado,
                "usage": data.get("usage")
            }).execute()

            # 10. Mapeo: Retornamos el primer objeto del inssert para el esquema de respuesta
            registro = db_response.data[0]
            usage_data = data.get("usage")
            if usage_data:
                usage_data.pop("prompt_tokens_details", None)
    

            return {
                    "id_resumenia": registro["id_resumenia"],
                    "id_paciente": registro["id_paciente"],
                    "modelo": registro["modelo"],
                    "resumen_completo": registro["resumen_completo"],
                    "resumen_estructurado": registro["resumen_estructurado"],
                    "fecha_generacion": registro["fecha_generacion"],
                    "usage": usage_data
                    }
        
        # -------------------------------------------------------------------------------------------------
        # SECCION MANEJO DE EXCEPCIONES
        # -------------------------------------------------------------------------------------------------
        
        except httpx.ConnectTimeout as e:
            nim_breaker.failure(e)
            logger.error("Timeout de conexión con NVIDIA NMI - el servicio no responde.")
            raise ValueError("AI_TIMEOUT_CONNECTION")
        except httpx.ReadTimeout as e:
            nim_breaker.failure(e)
            logger.error("Timeout de lectura con NVIDIA NIM - el modelo tradó demasiado en responder")
            raise ValueError("AI_TIMEOUT_READ")
        except httpx.TimeoutException as e:
            nim_breaker.failure(e)
            logger.error("Timeout general con NVIDIA NIIM")
            raise ValueError("AI_TIMEOUT")
        except httpx.HTTPStatusError as e:
            nim_breaker.failure(e)
            # Mapeo de errores HTTP a errores de negocio internos
            status_code = e.response.status_code
            logger.error(f"Error {status_code} de Nvidia: {e.response.text}")
            if status_code == 401:
                logger.error(f"AI_AUTH_ERROR: {str(e)}")
                raise ValueError("AI_AUTH_ERROR")
            elif status_code == 422:
                logger.error(f"AI_VALIDATION_ERROR: {str(e)}")
                raise ValueError("AI_VALIDATION_ERROR") 
            else:
                logger.error(f"AI_PROVIDER_ERROR: {str(e)}")
                raise ValueError("AI_PROVIDER_ERROR")
        except ValueError:
            # RELANZAMIENTO: Permite que errores de negocio (INPUT_INVALIDO) lleguen al Router
            raise
        except Exception as e:
            # Fallback crítico; logueamos el error y limpiamos el request huérfano
            logger.error(f"Error inesperado: {str(e)}")
            db_ia.eliminar_registro(id_request_ia)
            raise ValueError("AI_UNKNOWN_ERROR")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
        logger.info("AI service client closed")


# Global AI service instance
ai_service = AIService()
