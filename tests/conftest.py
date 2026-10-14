"""
Carrega o motor meteorológico a partir do ficheiro da app Streamlit.

A app é um único ficheiro que executa código de UI ao ser importado, pelo
que não pode ser importada directamente pelo pytest. Este conftest extrai
apenas as secções de lógica pura (parser, decisão, geometria, PDF) e
executa-as num módulo isolado.

Se reorganizares o ficheiro da app, só é preciso ajustar os marcadores em
_SECTIONS — não é preciso mexer nos testes.
"""
import re
import sys
import types
from pathlib import Path

import pytest

APP_FILE = "app.py"

# (nome, marcador_inicio, marcador_fim) — por ordem de dependência
_SECTIONS = [
    ("normalize",  "def normalize(text):",
                   "\n# -------------------------------------------------\n# GEO"),
    ("zones",      "# GEOGRAFIA — área do GAMET",
                   "AERODROMES = {"),
    ("core",       "AERODROMES = {",
                   "\n# -------------------------------------------------\n# DECISION"),
    ("wind",       "def parse_wind(secn2: str) -> list:",
                   "\n# -------------------------------------------------\n# PARSER — v"),
    ("parser",     "def parse_gamet(text):",
                   "\n# -------------------------------------------------\n# PDF EXPORT"),
    ("pdf",        "def _pdf_briefing_page",
                   "\n\n# -------------------------------------------------\n# EXECU"),
]

# Módulos da app que o motor não usa (UI e rede).
_SKIP_IMPORTS = ("streamlit", "requests", "folium", "pandas")


def _app_imports(src: str) -> str:
    """
    Usa os imports DA PRÓPRIA APP (linhas de topo), em vez de uma lista
    fixa. Até à 1.0 a lista era fixa e incluía `defaultdict`, que a app
    deixou de importar — os testes passavam e a app rebentava ao analisar.
    """
    linhas = ["import matplotlib", "matplotlib.use('Agg')"]
    for linha in src.splitlines():
        if re.match(r"^(import|from)\s", linha):
            mod = linha.split()[1].split(".")[0]
            if mod not in _SKIP_IMPORTS:
                linhas.append(linha)
    return "\n".join(linhas) + "\n"



def _find_app() -> Path:
    """Localiza o ficheiro da app (nome fixo desde a 1.0)."""
    root = Path(__file__).resolve().parent.parent
    app = root / APP_FILE
    if not app.exists():
        pytest.fail(f"{APP_FILE} não encontrado em {root}")
    return app


def _extract_engine(src: str) -> str:
    """Junta as secções de lógica pura numa fonte executável."""
    parts = [_app_imports(src)]

    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', src)
    parts.append(f'APP_VERSION = "{m.group(1) if m else "0.0"}"\n')

    for name, start, end in _SECTIONS:
        if start not in src:
            pytest.fail(f"Marcador de início da secção '{name}' não encontrado: {start!r}")
        i = src.index(start)
        if end not in src[i:]:
            pytest.fail(f"Marcador de fim da secção '{name}' não encontrado: {end!r}")
        j = src.index(end, i)
        parts.append(src[i:j])

    return "\n\n".join(parts)


@pytest.fixture(scope="session")
def app_path() -> Path:
    return _find_app()


@pytest.fixture(scope="session")
def eng(app_path):
    """Motor meteorológico carregado da app, sem executar a UI."""
    source = _extract_engine(app_path.read_text(encoding="utf-8"))
    module = types.ModuleType("gamet_engine")
    module.__dict__["__file__"] = str(app_path)
    try:
        exec(compile(source, str(app_path), "exec"), module.__dict__)
    except Exception as exc:  # pragma: no cover
        pytest.fail(f"Falha ao carregar o motor de {app_path.name}: {exc}")
    sys.modules["gamet_engine"] = module
    return module


@pytest.fixture(scope="session")
def net(app_path):
    """
    Secção de rede (fetch do IPMA) isolada, para testes com respostas
    simuladas. Fica separada do motor por depender de `requests`.
    """
    src = app_path.read_text(encoding="utf-8")
    start = "_IPMA_BASE ="
    end = "\n# -------------------------------------------------\n# UI — carregamento"
    if start not in src or end not in src:
        pytest.skip("Secção de rede não encontrada na app")
    block = src[src.index(start):src.index(end)]

    import time
    import requests
    from datetime import datetime, timezone, timedelta

    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', src)
    module = types.ModuleType("gamet_net")
    module.__dict__.update({
        "re": re, "time": time, "requests": requests,
        "datetime": datetime, "timezone": timezone, "timedelta": timedelta,
        "APP_VERSION": m.group(1) if m else "0.0",
    })
    exec(compile(block, str(app_path), "exec"), module.__dict__)
    return module


# ---------------------------------------------------------------------
# Auxiliares partilhados
# ---------------------------------------------------------------------

HDR = "LPPC GAMET VALID {v} LPPT-LPPC LISBOA FIR/MAINLAND AREA BLW FL150 "
NIL_TAIL = " SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN II MNM QNH:{q}HPA="
SIG_TAIL = " SIGMET APPLICABLE: {s} SECN II MNM QNH:{q}HPA="


def build_gamet(body, validity="201500/202100", qnh="1013", sigmet=None):
    """Monta um GAMET completo a partir do corpo da Secção I."""
    tail = (SIG_TAIL.format(s=sigmet, q=qnh) if sigmet
            else NIL_TAIL.format(q=qnh))
    return HDR.format(v=validity) + body + tail


@pytest.fixture
def analyse(eng):
    """
    Corre o pipeline completo tal como a app faz e devolve um resumo
    fácil de usar nas asserções.
    """
    def _run(text):
        has_sig, sig_text = eng.extract_sigmet_applicable(text)
        blocks, fzlvl, qnh, wind = eng.parse_gamet(text)
        regions = eng.compute_dynamic_regions(blocks)
        if has_sig:
            regions = eng.apply_sigmet_override(regions, sig_text)
        return {
            "has_sigmet": has_sig,
            "sigmet_text": sig_text,
            "blocks": blocks,
            "regions": regions,
            "fzlvl": fzlvl,
            "qnh": qnh,
            "wind": wind,
            "decisions": [r["decision"] for r in regions],
            "vis":   sorted({b.value for b in blocks if b.phenomenon == "VIS"}),
            "base":  sorted({b.value for b in blocks if b.phenomenon == "BASE_AGL"}),
            "ts":    {b.value for b in blocks if b.phenomenon == "TS"},
            "turb":  {b.value for b in blocks if b.phenomenon == "TURB"},
            "ice":   {b.value for b in blocks if b.phenomenon == "ICE"},
            "mt_obsc": any(b.phenomenon == "MT_OBSC" for b in blocks),
            "va":      any(b.phenomenon == "VA" for b in blocks),
            "layers":  " ".join(b.layer for b in blocks if b.layer),
        }
    return _run
