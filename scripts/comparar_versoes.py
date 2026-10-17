"""
Compara as decisões de duas versões do motor sobre os GAMETs reais do
arquivo, aeródromo a aeródromo. Serve ao revisor para saber, antes de um
merge, se alguma decisão ficou MAIS PERMISSIVA (o erro optimista).

Uso:
    python scripts/comparar_versoes.py --base /tmp/main/app.py \
        --nova app.py --dir dados/gamets [--desde 720]

Saída: Markdown. Código de saída 0 sempre — quem decide é quem lê.
"""
import argparse
import re
import sys
import types
from datetime import datetime, timezone, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tests"))
import conftest  # noqa: E402

GRAVIDADE = {"GO": 0, "MARGINAL": 1, "NO-GO": 2}


def motor(app):
    mod = types.ModuleType(f"motor_{abs(hash(str(app)))}")
    exec(compile(conftest._extract_engine(Path(app).read_text(encoding="utf-8")),
                 str(app), "exec"), mod.__dict__)
    return mod


def decisoes(eng, texto):
    blocos, *_ = eng.parse_gamet(texto)
    regioes = eng.compute_dynamic_regions(blocos)
    tem, sig = eng.extract_sigmet_applicable(texto)
    if tem:
        regioes = eng.apply_sigmet_override(regioes, sig)
    out = {}
    for nome, (la, lo) in eng.AERODROMES.items():
        reg = eng.find_region_for_point(regioes, la, lo)
        out[nome] = reg["decision"] if reg else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--nova", required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--desde", type=float, default=None, help="horas para trás")
    a = ap.parse_args()
    base, nova = motor(a.base), motor(a.nova)
    fich = sorted(Path(a.dir).rglob("*.txt"))
    if a.desde:
        lim = datetime.now(timezone.utc) - timedelta(hours=a.desde)
        def data(p):
            m = re.match(r"(\d{8}T\d{4})Z", p.name)
            return datetime.strptime(m.group(1), "%Y%m%dT%H%M").replace(tzinfo=timezone.utc) if m else lim
        fich = [p for p in fich if data(p) >= lim]
    mais_perm, mais_sev, erros = [], [], []
    for p in fich:
        t = p.read_text(encoding="utf-8").strip()
        try:
            d0, d1 = decisoes(base, t), decisoes(nova, t)
        except Exception as exc:  # noqa: BLE001
            erros.append(f"{p.name}: {type(exc).__name__}: {exc}")
            continue
        for ad in d0:
            x, y = d0[ad], d1.get(ad)
            if x == y or x is None or y is None:
                continue
            linha = f"| {p.name} | {ad} | {x} → {y} |"
            (mais_perm if GRAVIDADE[y] < GRAVIDADE[x] else mais_sev).append(linha)
    print(f"# Comparação de versões — {len(fich)} GAMET(s) reais\n")
    print(f"Base `{base.APP_VERSION}` → nova `{nova.APP_VERSION}`\n")
    cab = "| GAMET | Aeródromo | Decisão |\n|---|---|---|"
    print(f"## ⚠️ Decisões MAIS PERMISSIVAS: {len(mais_perm)}\n")
    if mais_perm:
        print(cab); print("\n".join(mais_perm)); print()
    print(f"## Decisões mais severas: {len(mais_sev)}\n")
    if mais_sev:
        print(cab); print("\n".join(mais_sev)); print()
    if erros:
        print(f"## ❌ Excepções na versão nova ou base: {len(erros)}\n")
        print("\n".join(f"- {e}" for e in erros))
    return 0


if __name__ == "__main__":
    sys.exit(main())
