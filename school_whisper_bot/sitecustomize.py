import sys
import types

# Совместимость с хостингом: aiogram v3 не имеет executor (как в v2),
# но сборка хостинга проверяет его наличие. Создаём заглушку заранее,
# чтобы при проверке from aiogram.utils import executor не падало.

# Создаём пустой пакет aiogram.utils, если его ещё нет
if "aiogram" not in sys.modules:
    aiogram_pkg = types.ModuleType("aiogram")
    aiogram_pkg.__path__ = []
    sys.modules["aiogram"] = aiogram_pkg

if "aiogram.utils" not in sys.modules:
    utils_pkg = types.ModuleType("aiogram.utils")
    utils_pkg.__path__ = []
    sys.modules["aiogram.utils"] = utils_pkg

# Добавляем executor в aiogram.utils
utils_mod = sys.modules["aiogram.utils"]
if not hasattr(utils_mod, "executor"):
    executor_mod = types.ModuleType("aiogram.utils.executor")
    executor_mod.dp = None

    async def _start_polling(*args, **kwargs):
        pass

    executor_mod.start_polling = _start_polling
    utils_mod.executor = executor_mod
    sys.modules["aiogram.utils.executor"] = executor_mod
