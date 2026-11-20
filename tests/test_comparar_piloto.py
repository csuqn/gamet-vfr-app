"""
scripts/comparar_piloto.py — comparação ponto a ponto app × piloto
(relatório W46, recomendação g.4).

O script lê a tabela do agente `piloto` e a decisão da app (só o texto do
GAMET, modo manual) e lista os pontos em que diferem. Verifica-se:
- que as diferenças saem no sentido certo (app mais permissiva / mais
  severa) e que a decisão da app é a do briefing (`analisar_gamet` manual);
- que uma tabela incompleta ou ilegível falha em voz alta (código 2) — os
  lapsos de contagem dos pilotos da W46 eram assim;
- as formas de escrever o ponto e a decisão que um piloto usa.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import comparar_piloto as cp  # noqa: E402
from test_v49 import G141500  # noqa: E402  (GAMET real 141500/142100)

DADOS = Path(__file__).resolve().parent.parent / "dados"
NOME_G = "20261114T1449Z_141500-142100_0b0ae4c2af.txt"
AGORA = cp._agora_do_ficheiro(NOME_G)


@pytest.fixture(scope="module")
def app(eng):
    """Decisão da app por ponto, calculada à parte pelo briefing."""
    r = eng.analisar_gamet(G141500, "manual", agora=AGORA)
    return {n: eng.find_region_for_point(r["regioes"], la, lo)["decision"]
            for n, (la, lo) in eng.AERODROMES.items()}


@pytest.fixture
def gamet(tmp_path):
    f = tmp_path / NOME_G
    f.write_text(G141500, encoding="utf-8")
    return f


def _tabela(decs, forma=lambda n: n, dec=lambda d: d):
    linhas = ["GAMET: 141500/142100", "", "| Aeródromo | Decisão | Motivo |", "|---|---|---|"]
    linhas += [f"| {forma(n)} | {dec(d)} | motivo de {n} |" for n, d in decs.items()]
    return "\n".join(linhas) + "\n\nDúvidas: nenhuma\n"


def _correr(gamet, tmp_path, texto, capsys):
    p = tmp_path / "piloto.md"
    p.write_text(texto, encoding="utf-8")
    codigo = cp.main([str(gamet), str(p)])
    return codigo, capsys.readouterr().out


def _codigo(n):
    return n.rsplit("(", 1)[1].rstrip(")")


def test_app_e_o_briefing_manual(eng, app):
    d = cp.decisoes_app(eng, G141500, AGORA)
    assert {n: v[0] for n, v in d.items()} == app
    # GAMET real 141500 (6.0.1): 14 NO-GO, o resto MARGINAL (CB em toda a FIR)
    assert sum(v == "NO-GO" for v in app.values()) == 14
    assert set(app.values()) == {"NO-GO", "MARGINAL"}


def test_concordam(gamet, tmp_path, capsys, app):
    c, out = _correr(gamet, tmp_path, _tabela(app), capsys)
    assert c == 0
    assert "**Concordam: 52/52**" in out
    assert "MAIS PERMISSIVA do que o piloto: 0" in out
    assert "mais severa do que o piloto: 0" in out
    assert "problemas" not in out


def test_diferencas_nos_dois_sentidos(gamet, tmp_path, capsys, app):
    piloto = dict(app)
    marg = [n for n, d in app.items() if d == "MARGINAL"]
    nogo = [n for n, d in app.items() if d == "NO-GO"]
    piloto[marg[0]] = "NO-GO"   # a app é mais permissiva
    piloto[marg[1]] = "GO"      # a app é mais severa
    piloto[nogo[0]] = "MARGINAL"  # a app é mais severa
    c, out = _correr(gamet, tmp_path, _tabela(piloto), capsys)
    assert c == 1
    assert "**Concordam: 49/52**" in out
    perm, sev = out.split("### App mais severa")
    assert "MAIS PERMISSIVA do que o piloto: 1" in perm
    assert f"| {marg[0]} | MARGINAL | NO-GO | motivo de {marg[0]} |" in perm
    assert marg[1] not in perm and nogo[0] not in perm
    assert "do que o piloto: 2" in sev
    assert f"| {marg[1]} | MARGINAL | GO |" in sev
    assert f"| {nogo[0]} | NO-GO | MARGINAL |" in sev
    # os motivos da app vão para o comparador
    assert "CB ISOL" in perm


def test_funcao_comparar_independente(app):
    piloto = {n: ("GO", "") for n in app}
    perm, sev = cp.comparar({n: (d, []) for n, d in app.items()}, piloto)
    assert perm == [] and len(sev) == 52


@pytest.mark.parametrize("forma", [
    lambda n: n,                              # "Lisboa (LPPT)"
    _codigo,                                  # "LPPT"
    lambda n: f"**{_codigo(n)}**",            # negrito
    lambda n: f"`{_codigo(n)}` — {n.rsplit(' (', 1)[0]}",
    lambda n: n.rsplit(" (", 1)[0],           # só o nome
    lambda n: cp._sem_acentos(n.rsplit(" (", 1)[0]).upper(),  # sem acentos, maiúsculas
], ids=["nome-app", "codigo", "negrito", "codigo-e-nome", "so-nome", "sem-acentos"])
def test_formas_do_ponto(gamet, tmp_path, capsys, app, forma):
    c, out = _correr(gamet, tmp_path, _tabela(app, forma=forma), capsys)
    assert c == 0, out
    assert "**Concordam: 52/52**" in out


@pytest.mark.parametrize("dec,esperada", [
    ("**NO-GO**", "NO-GO"), ("NO GO", "NO-GO"), ("No-Go", "NO-GO"), ("NO–GO", "NO-GO"),
    ("NOGO", "NO-GO"), ("marginal", "MARGINAL"), ("MARGINAL (LCA)", "MARGINAL"),
    ("GO", "GO"), ("✅ GO", "GO"),
    ("GO / MARGINAL", None), ("MARGINAL→NO-GO", None), ("", None), ("?", None),
    ("GOOD", None),
])
def test_ler_decisao(dec, esperada):
    assert cp.ler_decisao(dec) == esperada


def test_duas_tabelas_e_texto_a_volta(gamet, tmp_path, capsys, app):
    icao = {n: d for n, d in app.items() if not _codigo(n)[2:].isdigit()}
    ul = {n: d for n, d in app.items() if _codigo(n)[2:].isdigit()}
    texto = ("Fenómenos:\n- SIG CLD | N OF N4000 | BKN 008\n\n" + _tabela(icao)
             + "\nPistas de ultraleves:\n\n" + _tabela(ul, forma=_codigo))
    c, out = _correr(gamet, tmp_path, texto, capsys)
    assert c == 0, out
    assert "**Concordam: 52/52**" in out


def test_pontos_em_falta(gamet, tmp_path, capsys, app):
    parcial = dict(list(app.items())[:-3])
    c, out = _correr(gamet, tmp_path, _tabela(parcial), capsys)
    assert c == 2
    assert "3 ponto(s) em falta" in out
    for n in list(app)[-3:]:
        assert n in out
    assert "**Concordam: 49/49**" in out
    assert "não a dês por boa" in out


def test_ponto_repetido_desconhecido_e_decisao_ilegivel(gamet, tmp_path, capsys, app):
    nomes = list(app)
    tab = _tabela(app).split("\n\nDúvidas")[0]
    tab += f"\n| {_codigo(nomes[0])} | {app[nomes[0]]} | outra vez |"
    outra = "GO" if app[nomes[1]] != "GO" else "NO-GO"
    tab += f"\n| {_codigo(nomes[1])} | {outra} | outra decisão |"
    tab += "\n| LPXX Inventado | GO | — |"
    tab = tab.replace(f"| {nomes[2]} | {app[nomes[2]]} |", f"| {nomes[2]} | GO / MARGINAL |")
    c, out = _correr(gamet, tmp_path, tab, capsys)
    assert c == 2
    assert f"{nomes[0]} repetido (já na linha" in out
    assert f"{nomes[1]} repetido com outra decisão ({app[nomes[1]]}" in out
    assert "ponto desconhecido → `LPXX Inventado`" in out
    assert f"decisão ilegível para {nomes[2]}" in out
    assert "1 ponto(s) em falta" in out  # o da decisão ilegível


def test_sem_tabela(gamet, tmp_path, capsys):
    c, out = _correr(gamet, tmp_path, "Todos GO.\n", capsys)
    assert c == 2
    assert "nenhuma tabela" in out


def test_stdin_e_varios_pares(gamet, tmp_path, capsys, app, monkeypatch):
    import io
    p_ok = tmp_path / "ok.md"
    p_ok.write_text(_tabela(app), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", io.StringIO(_tabela(dict(list(app.items())[:10]))))
    c = cp.main([str(gamet), str(p_ok), str(gamet), "-"])
    out = capsys.readouterr().out
    assert c == 2  # o pior dos pares
    assert "(2 GAMET(s))" in out
    assert out.count("**Concordam: 52/52**") == 1
    assert "× stdin" in out and "42 ponto(s) em falta" in out


def test_gamet_ilegivel_no_disco(tmp_path, capsys):
    c = cp.main([str(tmp_path / "nao_existe.txt"), str(tmp_path / "nem_este.md")])
    assert c == 2
    assert "❌ FileNotFoundError" in capsys.readouterr().out


@pytest.mark.skipif(not (DADOS / "gamets").exists(), reason="sem dados/")
def test_arquivo_tabela_da_app_concorda(eng, tmp_path, capsys):
    """Nos 10 GAMETs mais recentes do arquivo, a tabela feita com a decisão
    da app concorda nos 52 pontos (o script lê a app como o briefing)."""
    fich = sorted((DADOS / "gamets").rglob("*.txt"))[-10:]
    for g in fich:
        texto = g.read_text(encoding="utf-8").strip()
        r = eng.analisar_gamet(texto, "manual", agora=cp._agora_do_ficheiro(g))
        decs = {n: eng.find_region_for_point(r["regioes"], la, lo)["decision"]
                for n, (la, lo) in eng.AERODROMES.items()}
        p = tmp_path / "p.md"
        p.write_text(_tabela(decs, forma=_codigo), encoding="utf-8")
        assert cp.main([str(g), str(p)]) == 0, g.name
        assert "**Concordam: 52/52**" in capsys.readouterr().out
