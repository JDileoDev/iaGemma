import pybreaker
from app.core.logging import get_logger

logger = get_logger(__name__)

class NIMCircuitBreakerListener(pybreaker.CircuitBreakerListener):
    """Listener para loguear cambios de estado del circuit breaker"""

    def state_change(self, cb, old_state, new_state):
        logger.warning(f"Circuit breaker NIVIDA NIM: {old_state} -> {new_state}")

    def failure(self, cb, exc):
        logger.error(f"Circuit breaker NVIDIA NIM registró fallo: {exc}. Fallo consecutivo {cb.fail_counter}")

    def  success(self, cb):
        logger.info("Circuit breaker NVIDIA NIM: request exitoso")  

nim_breaker = pybreaker.CircuitBreaker(
    fail_max=3, # abre el circuito después de 3 fallos consecutivos
    reset_timeout=60, # espera 60 segundos antes de intentar de nuevo
    listeners=[NIMCircuitBreakerListener()]
)