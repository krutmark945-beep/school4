import sys
import os
import importlib

local_dir = os.path.dirname(os.path.abspath(__file__))

if local_dir in sys.path:
    sys.path.remove(local_dir)

try:
    real_utils = importlib.import_module("aiogram.utils")
finally:
    sys.path.insert(0, local_dir)

this_module = sys.modules[__name__]
for name in dir(real_utils):
    if not name.startswith("_"):
        setattr(this_module, name, getattr(real_utils, name))
