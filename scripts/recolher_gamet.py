"""
Recolhe o GAMET LPPC actual do IPMA e guarda-o em gamets/AAAA/MM/,
uma vez por texto distinto (as emissões repetidas são ignoradas).

Corre de hora a hora no GitHub Actions — assim apanha também as emendas
(GAMET AMD) e correcções (COR), não só as emissões de 6 em 6 horas.

Usa o MESMO código de recolha da app (secção de rede de app.py),
para que o teste exercite exactamente o que a app faz.
"""
import hashlib
import re
import sys
import time
import types
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

import os

RAIZ = Path(__file__).resolve().parent.parent
APP = RAIZ / "app.py"
# Os GAMETs vão para o ramo `dados` (checkout em ./dados no workflow), para
# que cada recolha não reinicie a app publicada a partir do `main`.
DESTINO = Path(os.environ.get("GAMET_DIR", RAIZ / "gamets"))


def _carregar_rede():
    src = APP.read_text(encoding="utf-8")
    ini = src.index("_IPMA_BASE =")
    fim = src.index("\n# -------------------------------------------------\n# UI — carregamento")
    ver = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', src)
    mod = types.ModuleType("rede")
    mod.__dict__.update(re=re, time=time, requests=requests, datetime=datetime,
                        timezone=timezone, timedelta=timedelta,
                        APP_VERSION=ver.group(1) if ver else "0")
    exec(compile(src[ini:fim], str(APP), "exec"), mod.__dict__)
    return mod


def main() -> int:
    rede = _carregar_rede()
    ok, texto = rede.fetch_gamet_ipma()
    agora = datetime.now(timezone.utc)
    if not ok:
        # Registar a falha também é dado útil para o relatório
        log = DESTINO / "falhas.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(f"{agora:%Y-%m-%dT%H:%MZ} {texto.splitlines()[0]}\n")
        print("FALHA:", texto)
        return 0          # não falhar o workflow — a falha fica registada

    texto = re.sub(r"\s+", " ", texto).strip()
    h = hashlib.sha256(texto.encode()).hexdigest()[:10]
    if list(DESTINO.rglob(f"*_{h}.txt")):
        print("Sem GAMET novo.")
        return 0
    m = re.search(r"VALID\s+(\d{6})/(\d{6})", texto)
    validade = f"{m.group(1)}-{m.group(2)}" if m else "semvalidade"
    destino = DESTINO / f"{agora:%Y}" / f"{agora:%m}" / f"{agora:%Y%m%dT%H%MZ}_{validade}_{h}.txt"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto + "\n", encoding="utf-8")
    print("Novo GAMET:", destino)
    return 0


if __name__ == "__main__":
    sys.exit(main())
