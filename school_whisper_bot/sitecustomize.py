import sys
import types

# Совместимость с хостингом: aiogram v3 не имеет executor (как в v2),
# но сборка хостинга проверяет его наличие. Создаём заглушку.
try:
    import aiogram.utils  # noqa: F401
    if not hasattr(sys.modules["aiogram.utils"], "executor"):
        _executor = types.ModuleType("aiogram.utils.executor")
        _executor.dp = None

        async def _start_polling(*args, **kwargs):
            pass

        _executor.start_polling = _start_polling
        sys.modules["aiogram.utils"].executor = _executor
        sys.modules["aiogram.utils.executor"] = _executor
except Exception:
    pass
