import time
from app.core.logging import get_logger

logger = get_logger(__name__)

class CircuitBreakerError(Exception):
    pass

class CircuitBreaker:
    def __init__(self, fail_max=3, reset_timeout=60):
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self.fail_counter = 0
        self.last_failure_time = None
        self.state = "closed"

    def call(self):
        if self.state == "open":
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.reset_timeout:
                logger.info("Circuit breaker NIM: open → half-open")
                self.state = "half-open"
            else:
                raise CircuitBreakerError(
                    f"Circuito abierto. Reintentá en {int(self.reset_timeout - elapsed)}s"
                )

    def success(self):
        if self.state in ("half-open", "open"):
            logger.info(f"Circuit breaker NIM: {self.state} → closed")
        self.fail_counter = 0
        self.state = "closed"

    def failure(self, exc):
        self.fail_counter += 1
        self.last_failure_time = time.time()
        logger.error(f"Circuit breaker NIM fallo {self.fail_counter}/{self.fail_max}: {exc}")
        if self.fail_counter >= self.fail_max:
            logger.warning("Circuit breaker NIM: closed → open")
            self.state = "open"

nim_breaker = CircuitBreaker(fail_max=3, reset_timeout=60)