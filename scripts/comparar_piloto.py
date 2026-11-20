"""
Compara, ponto a ponto, a decisão da app com a tabela do agente `piloto`
(relatório diário; recomendação g.4 do relatório W46).

O agente `comparador` deixa de contar diferenças: recebe a saída deste
script, com os pontos em que as duas leituras diferem, e só classifica cada
diferença (erro do parser optimista/pessimista, erro do piloto, ambíguo).
Assim nenhum lapso de contagem passa e o comparador recebe sempre a tabela
integral, lida por código, não um resumo.

A app é lida como o piloto a lê: só o texto do GAMET, sem SIGMET/AIRMET da
página do IPMA nem do arquivo — `analisar_gamet(texto, "manual")`, o mesmo
que um GAMET colado à mão no briefing (conta o `SIGMET APPLICABLE` do texto).
A decisão comparada é a principal (pior caso do período).

A tabela do piloto (formato do `.claude/agents/piloto.md`) é a primeira
coluna com o ponto e uma coluna "Decisão"; pode vir partida em várias
tabelas com o mesmo cabeçalho. Cada ponto é reconhecido pelo indicativo
(`LPPT`, `LP48`), em qualquer forma (`Lisboa (LPPT)`, `**LPPT**`), ou pelo
nome exacto da app. **Falhar em voz alta**: um ponto em falta, repetido ou
desconhecido, ou uma decisão que não é exactamente uma de GO / MARGINAL /
NO-GO, é um problema da tabela — sai com código 2 e não se dá a comparação
por boa.

Uso:
    python scripts/comparar_piloto.py GAMET.txt PILOTO.md [GAMET2.txt PILOTO2.md …]
    python scripts/comparar_piloto.py GAMET.txt - < piloto.md

Saída: Markdown. Código de saída: 0 se as leituras concordam nos 52 pontos,
1 se há diferenças, 2 se alguma tabela do piloto tem problemas (ou um
ficheiro não se lê, ou a análise rebenta).
"""
import argparse
import re
import sys
import types
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tests"))
import conftest  # noqa: E402  (reutiliza a extracção do motor dos testes)

GRAVIDADE = {"GO": 0, "MARGINAL": 1, "NO-GO": 2}
_CODIGO_RE = re.compile(r"\bLP(?:[A-Z]{2}|\d{2})\b")
_DECISAO_RE = re.compile(r"NO[\s\-‐‑–—]*GO|MARGINAL|\bGO\b")


def carregar_motor(app=RAIZ / "app.py"):
    mod = types.ModuleType("motor_comparar_piloto")
    exec(compile(conftest._extract_engine(Path(app).read_text(encoding="utf-8")),
                 str(app), "exec"), mod.__dict__)
    return mod


def _sem_acentos(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).casefold().strip()


def _celulas(linha):
    linha = linha.strip()
    if linha.startswith("|"):
        linha = linha[1:]
    if linha.endswith("|"):
        linha = linha[:-1]
    return [c.strip() for c in linha.split("|")]


def _limpa(c):
    return re.sub(r"[*_`]", "", c).strip()


def _e_separador(cels):
    return all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) for c in cels if c) and any(cels)


def ler_decisao(celula):
    """'GO' / 'MARGINAL' / 'NO-GO', ou None se a célula não tem exactamente
    uma decisão (vazia, outra palavra, ou duas — 'GO / MARGINAL')."""
    achadas = {("NO-GO" if t.upper().startswith("NO") else t.upper())
               for t in _DECISAO_RE.findall(_limpa(celula).upper())}
    return achadas.pop() if len(achadas) == 1 else None


def ler_tabela_piloto(texto, pontos):
    """
    Lê a(s) tabela(s) `| Aeródromo | Decisão | Motivo |` do piloto.

    `pontos`: os nomes dos pontos da app (`AERODROMES`). Devolve
    (decisões {nome: (decisão, motivo)}, problemas [str]).
    """
    por_codigo = {}
    por_nome = {}
    for nome in pontos:
        for cod in _CODIGO_RE.findall(nome):
            por_codigo[cod] = nome
        por_nome[_sem_acentos(nome)] = nome
        por_nome[_sem_acentos(re.sub(r"\s*\([^)]*\)\s*$", "", nome))] = nome

    decisoes, problemas, linhas_ponto = {}, [], {}
    col_dec = col_mot = None
    tabelas = 0
    for n, linha in enumerate(texto.splitlines(), 1):
        if not linha.strip().startswith("|"):
            col_dec = None  # fim da tabela
            continue
        cels = _celulas(linha)
        cab = [_sem_acentos(_limpa(c)) for c in cels]
        if any(c.startswith("decis") for c in cab) and not _e_separador(cels):
            # cabeçalho: a 1.ª coluna é o ponto
            col_dec = next(i for i, c in enumerate(cab) if c.startswith("decis"))
            col_mot = next((i for i, c in enumerate(cab) if c.startswith("motiv")), None)
            tabelas += 1
            continue
        if col_dec is None or _e_separador(cels):
            continue
        if len(cels) <= col_dec:
            problemas.append(f"linha {n}: tem menos colunas do que o cabeçalho → `{linha.strip()}`")
            continue
        ponto_txt = _limpa(cels[0])
        cods = {por_codigo[c] for c in _CODIGO_RE.findall(ponto_txt.upper()) if c in por_codigo}
        if len(cods) == 1:
            nome = cods.pop()
        elif len(cods) > 1:
            problemas.append(f"linha {n}: mais de um ponto na mesma linha → `{ponto_txt}`")
            continue
        elif _sem_acentos(ponto_txt) in por_nome:
            nome = por_nome[_sem_acentos(ponto_txt)]
        else:
            problemas.append(f"linha {n}: ponto desconhecido → `{ponto_txt}`")
            continue
        dec = ler_decisao(cels[col_dec])
        if dec is None:
            problemas.append(f"linha {n}: decisão ilegível para {nome} → `{cels[col_dec]}` "
                             "(tem de ser exactamente uma de GO / MARGINAL / NO-GO)")
            continue
        if nome in decisoes:
            if decisoes[nome][0] != dec:
                problemas.append(f"linha {n}: {nome} repetido com outra decisão "
                                 f"({decisoes[nome][0]} na linha {linhas_ponto[nome]}, {dec} aqui)")
            else:
                problemas.append(f"linha {n}: {nome} repetido (já na linha {linhas_ponto[nome]})")
            continue
        motivo = cels[col_mot].strip() if col_mot is not None and len(cels) > col_mot else ""
        decisoes[nome] = (dec, motivo)
        linhas_ponto[nome] = n
    if not tabelas:
        problemas.append("nenhuma tabela com uma coluna \"Decisão\"")
    em_falta = [p for p in pontos if p not in decisoes]
    if tabelas and em_falta:
        problemas.append(f"{len(em_falta)} ponto(s) em falta: " + ", ".join(em_falta))
    return decisoes, problemas


def _agora_do_ficheiro(caminho):
    m = re.match(r"(\d{8}T\d{4})Z", Path(caminho).name)
    if m:
        return datetime.strptime(m.group(1), "%Y%m%dT%H%M").replace(tzinfo=timezone.utc)
    return None


def decisoes_app(eng, texto, agora=None):
    """{nome: (decisão, [motivos])} da app, só com o texto do GAMET."""
    r = eng.analisar_gamet(texto, "manual", agora=agora)
    out = {}
    for nome, (la, lo) in eng.AERODROMES.items():
        reg = eng.find_region_for_point(r["regioes"], la, lo) or {}
        out[nome] = (reg.get("decision"), list(reg.get("reasons", [])))
    return out


def comparar(app, piloto):
    """Pontos em que diferem: (mais_permissiva, mais_severa) — da app em
    relação ao piloto —, cada um [(nome, dec_app, dec_piloto)]."""
    perm, sev = [], []
    for nome, (da, _) in app.items():
        if nome not in piloto or da is None:
            continue
        dp = piloto[nome][0]
        if da != dp:
            (perm if GRAVIDADE[da] < GRAVIDADE[dp] else sev).append((nome, da, dp))
    return perm, sev


def _md(s):
    return s.replace("|", "\\|").replace("\n", " ")


def relatorio(nome_gamet, nome_piloto, versao, app, piloto, problemas):
    linhas = [f"## {nome_gamet} × {nome_piloto}", "",
              f"App `{versao}`, só o texto do GAMET (modo manual, decisão principal)."]
    perm, sev = comparar(app, piloto)
    sem_app = [n for n, (d, _) in app.items() if d is None]
    if problemas:
        linhas += ["", f"### ❌ Tabela do piloto com problemas: {len(problemas)}", ""]
        linhas += [f"- {p}" for p in problemas]
        linhas += ["", "A comparação abaixo cobre só os pontos lidos — **não a dês por boa** "
                       "sem corrigir a tabela."]
    if sem_app:
        linhas += ["", "### ❌ Pontos sem decisão na app: " + ", ".join(sem_app)]
    comparados = sum(1 for n in app if n in piloto and app[n][0] is not None)
    linhas += ["", f"**Concordam: {comparados - len(perm) - len(sev)}/{comparados}** pontos "
                   f"comparados (de {len(app)})."]
    cab = ["| Ponto | App | Piloto | Motivo do piloto | Motivos da app |",
           "|---|---|---|---|---|"]

    def _tab(lst):
        return cab + [f"| {n} | {da} | {dp} | {_md(piloto[n][1])} | "
                      f"{_md('; '.join(app[n][1]) or '—')} |" for n, da, dp in lst]

    linhas += ["", f"### ⚠️ App MAIS PERMISSIVA do que o piloto: {len(perm)}", ""]
    if perm:
        linhas += ["Se a app estiver errada aqui, é um erro OPTIMISTA (crítico).", ""] + _tab(perm)
    linhas += ["", f"### App mais severa do que o piloto: {len(sev)}", ""]
    if sev:
        linhas += _tab(sev)
    return "\n".join(linhas) + "\n", (2 if problemas or sem_app else (1 if perm or sev else 0))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("pares", nargs="+", metavar="GAMET PILOTO",
                    help="pares ficheiro do GAMET / ficheiro com a resposta do piloto ('-' = stdin)")
    ap.add_argument("--app", default=str(RAIZ / "app.py"))
    ap.add_argument("--agora", default=None,
                    help="instante da análise (AAAA-MM-DDTHH:MMZ); por omissão o do nome "
                         "do ficheiro do GAMET, ou o actual")
    a = ap.parse_args(argv)
    if len(a.pares) % 2:
        ap.error("os ficheiros vêm aos pares: GAMET PILOTO")
    eng = carregar_motor(a.app)
    codigo = 0
    print(f"# Comparação ponto a ponto — app × piloto ({len(a.pares) // 2} GAMET(s))\n")
    for g, p in zip(a.pares[::2], a.pares[1::2]):
        try:
            texto = Path(g).read_text(encoding="utf-8").strip()
            resp = sys.stdin.read() if p == "-" else Path(p).read_text(encoding="utf-8")
            agora = (datetime.strptime(a.agora, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
                     if a.agora else _agora_do_ficheiro(g))
            app = decisoes_app(eng, texto, agora)
        except Exception as exc:  # noqa: BLE001
            print(f"## {Path(g).name} × {p}\n\n### ❌ {type(exc).__name__}: {exc}\n")
            codigo = 2
            continue
        piloto, problemas = ler_tabela_piloto(resp, list(eng.AERODROMES))
        txt, c = relatorio(Path(g).name, "stdin" if p == "-" else Path(p).name,
                           eng.APP_VERSION, app, piloto, problemas)
        print(txt)
        codigo = max(codigo, c)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
