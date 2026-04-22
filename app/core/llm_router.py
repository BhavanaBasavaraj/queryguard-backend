import time
from app.services import openai_client, nvidia_client

class CircuitBreaker:
    def __init__(self, failure_threshold=5, cooldown_seconds=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.last_failure_time = None
        self.is_open = False

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.is_open = True

    def record_success(self):
        self.failure_count = 0
        self.is_open = False

    def can_attempt(self) -> bool:
        if not self.is_open:
            return True
        seconds_since_failure = time.time() - self.last_failure_time
        if seconds_since_failure >= self.cooldown_seconds:
            self.is_open = False
            self.failure_count = 0
            return True
        return False


gemini_breaker = CircuitBreaker()

class LLMRouter:

    def generate_sql(self, question: str, anonymized_schema: dict, schema_hints: dict = None) -> tuple[str, str]:
        if gemini_breaker.can_attempt():
            for attempt in range(3):
                try:
                    sql = openai_client.generate_sql(question, anonymized_schema, schema_hints)
                    gemini_breaker.record_success()
                    return sql, "gemini"
                except Exception as e:
                    gemini_breaker.record_failure()
                    if attempt < 2:
                        time.sleep(2 ** attempt)

        try:
            sql = nvidia_client.generate_sql(question, anonymized_schema, schema_hints)
            return sql, "nvidia-nim"
        except Exception as e:
            raise Exception(f"All LLM providers failed: {str(e)}")
