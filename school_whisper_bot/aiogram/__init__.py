import sys
import os
import importlib
import types

local_dir = os.path.dirname(os.path.abspath(__file__))

# Убираем локальную директорию из пути, чтобы импортировать настоящий aiogram
if local_dir in sys.path:
    sys.path.remove(local_dir)

try:
    real_aiogram = importlib.import_module("aiogram")
finally:
    sys.path.insert(0, local_dir)

# Копируем все публичные атрибуты настоящего aiogram в наш модуль
this_module = sys.modules[__name__]
for name in dir(real_aiogram):
    if not name.startswith("_"):
        setattr(this_module, name, getattr(real_aiogram, name))

# Добавляем заглушку executor в aiogram.utils (для прохождения сборки хостинга)
real_utils = getattr(real_aiogram, "utils", None)
if real_utils is not None:
    if not hasattr(real_utils, "executor"):
        executor_mod = types.ModuleType("aiogram.utils.executor")
        executor_mod.dp = None

        async def _start_polling(*args, **kwargs):
            pass

        executor_mod.start_polling = _start_polling
        real_utils.executor = executor_mod
        sys.modules["aiogram.utils.executor"] = executor_mod

    # Убеждаемся, что sys.modules['aiogram'] указывает на настоящий aiogram
    sys.modules["aiogram"] = real_aiogram
