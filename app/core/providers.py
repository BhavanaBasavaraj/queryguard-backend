"""Provider identifiers.

These values follow OpenTelemetry's GenAI semantic conventions
(gen_ai.system) and are written directly into LogWatch's
llm_calls.provider column and joined against model_pricing.
They must not be renamed independently of that schema.
"""
GEMINI = "gcp.gemini"
NIM = "nvidia.nim"
CACHE = "cache"
