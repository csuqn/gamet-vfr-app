"""
Analisa GAMETs reais recolhidos e produz um relatório em Markdown.

Sem saber o tempo real, o que se pode detectar automaticamente é o tipo
de erro que mais vezes apareceu neste projecto — o parser não perceber
parte do texto e a app dar GO em silêncio:

  1. excepções ao processar o GAMET;
  2. GAMET considerado ilegível (looks_unparseable);
  3. campos (subentradas) da Secção I com conteúdo que não geraram nenhum
     fenómeno (foi assim que "BKN 002/010HFT AGL" passou 31 versões
     despercebido) — a mesma verificação do aviso do briefing (3.9);
  4. palavras da Secção I fora do vocabulário conhecido (formatos novos);
  5. subentradas com área geográfica não reconhecida, aplicadas a toda a
     FIR (3.4), e com cardinal solto antes de BTN, lidas de forma alargada
     (3.5);
  6. regiões cuja decisão não bate com o cálculo directo ponto a ponto
     nos 52 aeródromos (o "oráculo" dos testes).

Uso:
    python scripts/analisar.py gamets/2026/10/*.txt > relatorio.md
    python scripts/analisar.py --desde 24        # últimas 24 h (pela data
                                                 # do nome do ficheiro)
"""
import argparse
import re
import sys
import types
from datetime import datetime, timezone, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tests"))
import conftest  # noqa: E402  (reutiliza a extracção do motor dos testes)


def carregar_motor():
    app = RAIZ / "app.py"
    mod = types.ModuleType("motor")
    exec(compile(conftest._extract_engine(app.read_text(encoding="utf-8")),
                 str(app), "exec"), mod.__dict__)
    return mod


# ---------------------------------------------------------------------
# Vocabulário da Secção I. Os campos com conteúdo que não geraram fenómeno
# são do motor (campos_nao_interpretados, 3.9) — o mesmo aviso do briefing.
# ---------------------------------------------------------------------
# Vocabulário conhecido da Secção I (palavras isoladas ou padrões)
_VOCAB = set("""
SECN I SFC VIS SIG CLD SIGWX TURB ICE MT OBSC VA NIL AND OF N S E W BTN TS
LCA ISOL OCNL FRQ EMBD GEN MOD SEV HVY ABV BLW TOP TOPS MAR LAN COT
FEW SCT BKN OVC CB TCU AS AC NS ST SC CU CI FG BR RA DZ SN HZ FU DU SA
SHRA SHSN TSRA TSGR GR GS FZRA FZDZ FZFG BCFG MIFG PRFG VCFG BLSN DS SS
INTSF WKN NC STNR MOV KT AGL AMSL HFT FT M KM FL INC IN CLD OBS FCST
WSPD MTW SQL FC TC MPS -
""".split())
_PADROES = [
    r"N\d{4}", r"W\d{5}", r"FL\d{3}", r"\d{2}/\d{2}", r"\d{3,4}M",
    r"\d{3,4}-\d{3,4}M", r"\d{3,5}(?:-\d{3,5})?(?:/(?:\d{3,5}|XXX))?(?:HFT|HTF|FT)",
    r"SFC/(?:FL\d{3}|\d{3,5}(?:HFT|HTF|FT))", r"FL\d{3}/FL\d{3}", r"\d{3}/\d{3}",
    r"[A-Z]{2,4}/[A-Z]{2,4}", r"SFC/\d{3}(?:HFT)?", r"\d+", r"MOD/SEV", r"MOD/HVY",
    r"\d{2,3}(?:-\d{2,3})?(?:KT|MPS)",
]
_PADROES_RE = [re.compile(p + r"$") for p in _PADROES]


def palavras_desconhecidas(secn1):
    desconhecidas = set()
    for tok in re.split(r"[\s,:]+", secn1):
        tok = tok.strip(":=.")
        if not tok or tok in _VOCAB:
            continue
        if any(p.match(tok) for p in _PADROES_RE):
            continue
        desconhecidas.add(tok)
    return sorted(desconhecidas)


def oraculo(eng, blocos, tem_sigmet, lon, lat):
    if tem_sigmet:
        return "NO-GO"
    p = eng.Point(lon, lat)
    ev = []
    for b in blocos:
        if not b.polygon.buffer(0.01).contains(p):
            continue
        if not b.polygon.buffer(-0.01).contains(p):
            return None
        if b.phenomenon == "BASE_AMSL":
            ev.append(("BASE", max(0, round(b.value - eng._terrain_elevation_ft(lon, lat))),
                       b.qualifier, b.layer))
        elif b.phenomenon == "BASE_AGL":
            ev.append(("BASE", b.value, b.qualifier, b.layer))
        else:
            ev.append((b.phenomenon, b.value, b.qualifier, b.layer))
    return eng.decision(ev)[0]


def analisar(eng, texto):
    r = {"texto": texto, "alertas": [], "excepcao": None}
    try:
        norm = eng.normalize(texto)
        secn1 = norm.split("SECN I", 1)[1] if "SECN I" in norm else norm
        secn1 = re.split(r"SIGMET APPLICABLE|SECN II", secn1)[0]
        tem_sig, sig_txt = eng.extract_sigmet_applicable(texto)
        blocos, *_ = eng.parse_gamet(texto)
        regioes = eng.compute_dynamic_regions(blocos)
        if tem_sig:
            regioes = eng.apply_sigmet_override(regioes, sig_txt)
    except Exception as exc:  # noqa: BLE001
        r["excepcao"] = f"{type(exc).__name__}: {exc}"
        return r
    r["regioes"] = regioes
    if eng.looks_unparseable(texto):
        r["alertas"].append("GAMET considerado ilegível pela app")
    for s in eng.subentradas_sem_area(texto):
        r["alertas"].append(f"Área não reconhecida (aplicada a toda a FIR) → {s}")
    for s, leitura in eng.subentradas_alargadas(texto):
        r["alertas"].append(f"Cardinal solto antes de BTN (área alargada a {leitura}) → {s}")
    # Mesma verificação do aviso do briefing (3.9): por subentrada, no motor.
    for p in eng.campos_nao_interpretados(texto):
        r["alertas"].append(f"Campo sem fenómeno gerado → {p}")
    desc = palavras_desconhecidas(secn1)
    if desc:
        r["alertas"].append("Palavras desconhecidas: " + " ".join(desc))
    for nome, (la, lo) in eng.AERODROMES.items():
        esperado = oraculo(eng, blocos, tem_sig, lo, la)
        reg = eng.find_region_for_point(regioes, la, lo)
        if esperado and reg and reg["decision"] != esperado:
            r["alertas"].append(f"Oráculo: {nome} → região {reg['decision']}, esperado {esperado}")
    area = eng.FIR_POLYGON.area
    r["resumo"] = {d: round(100 * sum(x["polygon"].area for x in regioes
                                      if x["decision"] == d) / area)
                   for d in ("NO-GO", "MARGINAL", "GO")}
    return r


def data_do_ficheiro(p):
    m = re.match(r"(\d{8}T\d{4})Z", p.name)
    return datetime.strptime(m.group(1), "%Y%m%dT%H%M").replace(tzinfo=timezone.utc) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ficheiros", nargs="*")
    ap.add_argument("--desde", type=float, help="horas para trás (pelo nome do ficheiro)")
    ap.add_argument("--dir", default=str(RAIZ / "gamets"),
                    help="pasta dos GAMETs (no ramo `dados`: ./dados/gamets)")
    a = ap.parse_args()
    if a.desde:
        limite = datetime.now(timezone.utc) - timedelta(hours=a.desde)
        fich = sorted(p for p in Path(a.dir).rglob("*.txt")
                      if (data_do_ficheiro(p) or limite) >= limite)
    else:
        fich = [Path(f) for f in a.ficheiros]

    eng = carregar_motor()
    print(f"# Relatório GAMET — {datetime.now(timezone.utc):%Y-%m-%d %H:%MZ}\n")
    print(f"App {eng.APP_VERSION} · {len(fich)} GAMET(s) analisado(s)\n")
    total_alertas = 0
    for p in fich:
        r = analisar(eng, p.read_text(encoding="utf-8").strip())
        n = len(r["alertas"]) + bool(r["excepcao"])
        total_alertas += n
        estado = "❌" if r["excepcao"] else ("⚠️" if n else "✅")
        print(f"## {estado} {p.name}\n")
        if r["excepcao"]:
            print(f"**Excepção:** `{r['excepcao']}`\n")
        else:
            s = r["resumo"]
            print(f"NO-GO {s['NO-GO']}% · MARGINAL {s['MARGINAL']}% · GO {s['GO']}% · "
                  f"{len(r['regioes'])} regiões\n")
        for al in r["alertas"]:
            print(f"- {al}")
        print(f"\n<details><summary>Texto</summary>\n\n```\n{r['texto']}\n```\n</details>\n")
    print(f"\n**Total de alertas: {total_alertas}**")
    return 0


if __name__ == "__main__":
    sys.exit(main())
