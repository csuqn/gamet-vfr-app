"""
Carrega o motor da app (app.py) sem o Streamlit.

O protótipo NiceGUI NÃO tem uma cópia do motor: executa as mesmas secções
de app.py que os testes usam (tests/conftest.py), mais a secção de rede.
Assim, qualquer correcção ao motor no app.py vale para as duas interfaces,
e os 400+ testes continuam a cobrir a lógica de ambas.
"""
import re
import sys
import types
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
APP = RAIZ / "app.py"
sys.path.insert(0, str(RAIZ / "tests"))
import conftest  # noqa: E402  (extracção das secções do motor)

_MARCA_REDE = ("_IPMA_BASE =", "\n# -------------------------------------------------\n# UI — carregamento")


def carregar():
    src = APP.read_text(encoding="utf-8")
    mod = types.ModuleType("motor_gamet")
    mod.__dict__["__file__"] = str(APP)
    exec(compile(conftest._extract_engine(src), str(APP), "exec"), mod.__dict__)
    # Rede (IPMA e arquivo) — o mesmo código da app Streamlit
    a, b = src.index(_MARCA_REDE[0]), src.index(_MARCA_REDE[1])
    import requests
    import time
    mod.__dict__.update({"requests": requests, "time": time})
    exec(compile(src[a:b], str(APP), "exec"), mod.__dict__)
    return mod


M = carregar()
