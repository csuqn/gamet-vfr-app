"""
Recolhe o GAMET e os SIGMETs LPPC actuais do IPMA e guarda-os em
gamets/AAAA/MM/ e sigmets/AAAA/MM/, uma vez por texto distinto (as
emissões repetidas são ignoradas).

Corre de 15 em 15 minutos no GitHub Actions — assim apanha também as emendas
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


_SIGMET_RE = re.compile(
    r"(LPPC\s+(?:SIGMET|AIRMET)\s+\S+\s+VALID\s+\d{6}/\d{6}.+?=)", re.DOTALL)


def _pagina_bruta(rede):
    """A resposta tal como vem do IPMA (primeiro endpoint que responda)."""
    for caminho in rede._GAMET_ENDPOINTS:
        try:
            r = requests.get(
                rede._IPMA_BASE + caminho,
                params=dict(rede._GAMET_PARAMS, _=int(time.time() * 1000)),
                headers={"User-Agent": f"Mozilla/5.0 (compatible; GAMET-Decoder/{rede.APP_VERSION})",
                         "Referer": f"{rede._IPMA_BASE}/",
                         "X-Requested-With": "XMLHttpRequest",
                         "Accept": "text/html, */*; q=0.01"},
                timeout=10)
        except requests.RequestException:
            continue
        if r.status_code == 200 and r.text.strip():
            return r.text
    return ""


def _limpar(raw):
    t = raw.replace("\\n", " ").replace("\\r", " ").replace('\\"', '"').replace("\\/", "/")
    t = re.sub(r"<[^>]+>", " ", t).replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", t).strip()


def _guardar(pasta, prefixo_validade, texto, agora):
    texto = re.sub(r"\s+", " ", texto).strip()
    h = hashlib.sha256(texto.encode()).hexdigest()[:10]
    if list(pasta.rglob(f"*_{h}.txt")):
        return None
    m = re.search(r"VALID\s+(\d{6})/(\d{6})", texto)
    validade = f"{m.group(1)}-{m.group(2)}" if m else "semvalidade"
    destino = pasta / f"{agora:%Y}" / f"{agora:%m}" / f"{agora:%Y%m%dT%H%MZ}_{prefixo_validade}{validade}_{h}.txt"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto + "\n", encoding="utf-8")
    return destino


def recolher_sigmets(rede, agora):
    raw = _pagina_bruta(rede)
    if os.environ.get("GUARDAR_PAGINA") == "1" and raw:
        pag = DESTINO.parent / "paginas" / f"{agora:%Y%m%dT%H%MZ}.html"
        pag.parent.mkdir(parents=True, exist_ok=True)
        pag.write_text(raw, encoding="utf-8")
        print("Página guardada:", pag)
    pasta = DESTINO.parent / "sigmets"
    # Cada boletim vem num bloco <pre>. Guardar todos os que não sejam o
    # GAMET: SIGMET/AIRMET no formato OACI ficam classificados; qualquer
    # outra coisa fica em sigmets/desconhecidos/ para análise — assim um
    # formato inesperado não se perde.
    for bloco in re.findall(r"<pre[^>]*>(.*?)</pre>", raw, re.DOTALL | re.IGNORECASE):
        texto = _limpar(bloco)
        if not texto or re.match(r"LPPC\s+GAMET\b", texto):
            continue
        m = _SIGMET_RE.search(texto)
        if m:
            texto = m.group(1)
            tipo = "AIRMET" if " AIRMET " in f" {texto} " else "SIGMET"
            num = re.search(r"(?:SIGMET|AIRMET)\s+(\S+)", texto).group(1)
            d = _guardar(pasta, f"{tipo}{num}_", texto, agora)
        else:
            d = _guardar(pasta / "desconhecidos", "", texto, agora)
        if d:
            print("Novo boletim:", d)


def main() -> int:
    rede = _carregar_rede()
    agora = datetime.now(timezone.utc)
    try:
        recolher_sigmets(rede, agora)
    except Exception as exc:  # noqa: BLE001 — a recolha do GAMET não pode parar por isto
        print("Falha na recolha de SIGMETs:", exc)
    ok, texto = rede.fetch_gamet_ipma()
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
