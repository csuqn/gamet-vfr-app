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


# Mesmo padrão da app (_BULLETIN_RE): o "=" final é opcional — os SIGMETs
# reais de 17-out-2026 vinham sem ele e foram parar a desconhecidos/.
_SIGMET_RE = re.compile(
    r"(LPPC\s+(?:SIGMET|AIRMET)\s+\S+\s+VALID\s+\d{6}/\d{6}.*?"
    r"(?:=|(?=\s*LPPC\s+(?:SIGMET|AIRMET|GAMET)\s)|\s*$))", re.DOTALL)


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
            texto = m.group(1).strip()
            tipo = "AIRMET" if " AIRMET " in f" {texto} " else "SIGMET"
            num = re.search(r"(?:SIGMET|AIRMET)\s+(\S+)", texto).group(1)
            d = _guardar(pasta, f"{tipo}{num}_", texto, agora)
        else:
            d = _guardar(pasta / "desconhecidos", "", texto, agora)
        if d:
            print("Novo boletim:", d)


# ---------------------------------------------------------------------
# Índice do arquivo — lido pela app (secção "Arquivo" e recurso quando o
# IPMA não tem GAMET publicado). Fica em dados/indice.json e é reconstruído
# a partir das pastas em cada volta, por isso nunca fica dessincronizado.
# A app lê-o por raw.githubusercontent.com, sem passar pela API do GitHub
# (que tem limite de pedidos).
# ---------------------------------------------------------------------
import json

_NOME_RE = re.compile(r"^(\d{8}T\d{4})Z_(?:(?:SIGMET|AIRMET)\S*?_)?(\d{6})-(\d{6})_")


def _data_validade(ddhhmm, ref):
    """dia/hora/minuto do GAMET → datetime UTC, no mês mais próximo de ref."""
    d, h, mi = int(ddhhmm[:2]), int(ddhhmm[2:4]), int(ddhhmm[4:])
    melhores = []
    for dm in (-1, 0, 1):
        ano, mes = ref.year, ref.month + dm
        if mes < 1:
            ano, mes = ano - 1, 12
        if mes > 12:
            ano, mes = ano + 1, 1
        try:
            melhores.append(datetime(ano, mes, d, h, mi, tzinfo=timezone.utc))
        except ValueError:
            continue
    return min(melhores, key=lambda c: abs((c - ref).total_seconds())) if melhores else None


def _entrada(f, base):
    m = _NOME_RE.match(f.name)
    if not m:
        return None
    rec = datetime.strptime(m.group(1), "%Y%m%dT%H%M").replace(tzinfo=timezone.utc)
    ini = _data_validade(m.group(2), rec)
    fim = _data_validade(m.group(3), ini or rec)
    if ini and fim and fim <= ini:
        fim += timedelta(days=1)
    fmt = "%Y-%m-%dT%H:%MZ"
    return {
        "ficheiro": f.relative_to(base).as_posix(),
        "recolhido": rec.strftime(fmt),
        "inicio": ini.strftime(fmt) if ini else None,
        "fim": fim.strftime(fmt) if fim else None,
    }


def construir_indice(base):
    """Reconstrói base/indice.json; devolve True se mudou."""
    gam, sig = [], []
    for f in sorted((base / "gamets").rglob("*.txt")):
        e = _entrada(f, base)
        if e:
            txt = f.read_text(encoding="utf-8")
            e["tipo"] = "AMD" if " GAMET AMD " in f" {txt} " else ("COR" if " GAMET COR " in f" {txt} " else "GAMET")
            gam.append(e)
    pasta_sig = base / "sigmets"
    if pasta_sig.exists():
        for f in sorted(pasta_sig.rglob("*.txt")):
            if "desconhecidos" in f.parts:
                continue
            e = _entrada(f, base)
            if e:
                e["texto"] = f.read_text(encoding="utf-8").strip()
                sig.append(e)
    gam.sort(key=lambda e: e["recolhido"])
    sig.sort(key=lambda e: e["recolhido"])
    novo = json.dumps({"gamets": gam, "sigmets": sig}, ensure_ascii=False, indent=1)
    alvo = base / "indice.json"
    if alvo.exists() and alvo.read_text(encoding="utf-8") == novo:
        return False
    alvo.write_text(novo, encoding="utf-8")
    return True


def main() -> int:
    try:
        return _recolher()
    finally:
        try:
            if construir_indice(DESTINO.parent):
                print("Índice actualizado.")
        except Exception as exc:  # noqa: BLE001
            print("Falha ao construir o índice:", exc)


def _recolher() -> int:
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
            # Primeira linha + o diagnóstico por endpoint (HTTP xxx, erro de
            # ligação…) — só a primeira linha não dizia porque falhou
            detalhe = " | ".join(l.strip("• ").strip() for l in texto.splitlines()[1:] if l.strip())
            f.write(f"{agora:%Y-%m-%dT%H:%MZ} {texto.splitlines()[0]}"
                    + (f" [{detalhe}]" if detalhe else "") + "\n")
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
