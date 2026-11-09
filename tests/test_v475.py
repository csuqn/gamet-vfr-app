"""
4.7.5 — `SFC WIND:` na Secção I do GAMET é o mesmo campo que `SFC WSPD:`.

GAMETs reais de 8-nov-2026 (primeiros do arquivo com este nome de campo, o do
Anexo 3):
- dados/gamets/2026/11/20261108T1451Z_081500-082100_73bc1f4fc4.txt
  `SECN I SFC WIND:N OF N3900 AND W OF W00935 150/30KT SFC VIS:…`
- dados/gamets/2026/11/20261108T2053Z_082100-090300_aba6b1c60d.txt
  `SECN I SFC WIND:N OF N4000 AND W OF W00930 160/30KT SFC VIS:…`

Até à 4.7.4 só `SFC WSPD` abria campo: `SFC WIND:` logo a seguir a `SECN I`
era ignorado em silêncio (sem bloco WSPD nem aviso "Campo não interpretado") e,
depois de outro campo, ficava colado a ele como continuação (com a área do
vento a recortar esse campo). Nestes GAMETs não mudava nada (tudo já NO-GO),
mas um vento ≥ 30 kt sozinho dava GO.
"""
import json
import re
import sys
import types
from datetime import timedelta
from pathlib import Path

import pytest

import conftest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import analisar  # noqa: E402

REF474 = Path(__file__).resolve().parent / "referencia" / "app_4_7_4.py"
DADOS = Path(__file__).resolve().parent.parent / "dados"
RANK = {"GO": 0, "MARGINAL": 1, "NO-GO": 2}

G081500 = (
    "LPPC GAMET VALID 081500/082100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I "
    "SFC WIND:N OF N3900 AND W OF W00935 150/30KT SFC VIS:LCA 2000-5000M BR/DZ/RA "
    "SIGWX:17/21 MAR AND COT ISOL/EMBD TS SIG CLD:LCA BKN 006-008/012HFT AGL MAR AND "
    "COT ISOL/EMBD TCU/CB 020-035/XXXHFT AGL ICE:LAN LCA MOD/SEV ABV FL100 TURB:LCA "
    "MOD/SEV SFC/FL150 SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN II PSYS:18 N4340 "
    "W02320 L 976HPA STNR NC CLD:SCT/BKN SC/CU 015-030/040HFT AGL SCT/BKN AS/AC "
    "060-090/100-130HFT AMSL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 "
    "N4045 W00750 1000FT AGL 130/015KT PS12 130/028KT PS17 140/019KT PS14 2000FT AGL "
    "160/024KT PS10 150/036KT PS15 170/030KT PS12 5000FT AGL 180/041KT PS06 190/054KT "
    "PS10 200/049KT PS08 FL100 200/046KT PS01 210/038KT PS05 210/045KT PS03 FL150 "
    "220/043KT MS06 200/033KT MS06 210/036KT MS06 FZLVL: 10500FT AMSL 12200FT AMSL "
    "11600FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 W00752 N3700 W00800 1000FT AGL "
    "170/034KT PS17 160/033KT PS16 160/032KT PS18 2000FT AGL 180/043KT PS15 170/040KT "
    "PS14 170/034KT PS17 5000FT AGL 210/040KT PS11 210/037KT PS10 210/036KT PS12 FL100 "
    "200/047KT PS05 220/036KT PS04 220/040KT PS04 FL150 200/040KT MS05 210/040KT MS05 "
    "210/040KT MS05 FZLVL: 12100FT AMSL 11800FT AMSL 12100FT AMSL MNM QNH:1003HPA="
)
G082100 = (
    "LPPC GAMET VALID 082100/090300 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I "
    "SFC WIND:N OF N4000 AND W OF W00930 160/30KT SFC VIS:LCA 2000-5000M BR/DZ/RA "
    "SIGWX:ISOL/EMBD TS SIG CLD:LCA BKN 006-008/012HFT AGL ISOL/EMBD TCU/CB "
    "020-035/XXXHFT AGL TURB:LCA MOD/SEV SFC/FL070 SIGMET APPLICABLE: AT TIME OF ISSUE "
    "NIL SECN II PSYS:00 N4340 W02140 L 972HPA STNR NC CLD:SCT/BKN SC/CU "
    "015-030/040HFT AGL SCT/BKN AS/AC 060-090/100-130HFT AMSL WIND/T: BRAGANCA PORTO "
    "VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL 150/017KT PS11 150/031KT "
    "PS18 150/018KT PS14 2000FT AGL 170/030KT PS09 160/041KT PS16 170/034KT PS13 5000FT "
    "AGL 210/029KT PS06 190/041KT PS11 200/044KT PS08 FL100 200/032KT PS02 190/052KT "
    "PS03 200/050KT PS03 FL150 200/042KT MS06 190/058KT MS06 200/054KT MS06 FZLVL: "
    "11100FT AMSL 11400FT AMSL 10800FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 W00752 "
    "N3700 W00800 1000FT AGL 190/032KT PS16 180/031KT PS16 190/033KT PS18 2000FT AGL "
    "200/044KT PS15 190/039KT PS15 200/035KT PS17 5000FT AGL 210/047KT PS11 200/046KT "
    "PS10 210/033KT PS13 FL100 210/052KT PS03 210/050KT PS03 210/045KT PS02 FL150 "
    "200/058KT MS06 210/055KT MS06 210/052KT MS06 FZLVL: 11300FT AMSL 11800FT AMSL "
    "11300FT AMSL MNM QNH:999HPA="
)
REAIS = {
    "081500": (G081500, "N OF N3900 AND W OF W00935", 30),
    "082100": (G082100, "N OF N4000 AND W OF W00930", 30),
}
CAB = ("LPPC GAMET VALID 081500/082100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 "
       "SECN I ")
FIM = " SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN II MNM QNH:1003HPA="


def _g(secn1):
    return CAB + secn1 + FIM


@pytest.fixture(scope="module")
def eng474(eng):
    mod = types.ModuleType("motor_4_7_4")
    mod.__dict__["__file__"] = str(REF474)
    exec(compile(conftest._extract_engine(REF474.read_text(encoding="utf-8")), str(REF474),
                 "exec"), mod.__dict__)
    return mod


def _icao(nome):
    return nome.split()[0]


def _wspd(blocos):
    return [b for b in blocos if b.phenomenon == "WSPD"]


def _pontos(eng, texto):
    blocos, *_ = eng.parse_gamet(texto)
    regioes = eng.compute_dynamic_regions(blocos)
    return {_icao(n): eng.find_region_for_point(regioes, la, lo)
            for n, (la, lo) in eng.AERODROMES.items()}


def test_referencia_e_a_4_7_4(eng, eng474):
    assert eng474.APP_VERSION == "4.7.4"
    assert tuple(int(x) for x in eng.APP_VERSION.split(".")) >= (4, 7, 5)


def test_textos_iguais_aos_do_arquivo():
    for nome, f in (("081500", "20261108T1451Z_081500-082100_73bc1f4fc4.txt"),
                    ("082100", "20261108T2053Z_082100-090300_aba6b1c60d.txt")):
        p = DADOS / "gamets" / "2026" / "11" / f
        if not p.exists():
            pytest.skip("sem dados/")
        assert p.read_text(encoding="utf-8").strip() == REAIS[nome][0]


# ---------------------------------------------------------------- GAMETs reais

@pytest.mark.parametrize("nome", sorted(REAIS))
def test_gamet_real_gera_bloco_wspd_na_area(eng, nome):
    texto, area, kt = REAIS[nome]
    blocos, *_ = eng.parse_gamet(texto)
    w = _wspd(blocos)
    assert len(w) == 1, [(b.phenomenon, b.parte) for b in blocos]
    assert w[0].value == kt and w[0].qualifier == "" and not w[0].window
    esperado = eng.extract_polygon(area)
    assert esperado is not None
    assert w[0].polygon.symmetric_difference(esperado).area < 1e-9
    # Só sobre o mar a W da costa (no 082100 uma lasca junto ao limite W da
    # área do GAMET): nenhum dos 52 pontos lá dentro
    assert w[0].polygon.area > 0
    assert w[0].polygon.bounds[0] >= eng.FIR_POLYGON.bounds[0] - 1e-9
    assert w[0].polygon.bounds[2] <= -9.5 + 1e-9
    assert w[0].polygon.intersection(eng.LAND_POLYGON).area < 1e-9
    for nome_ad, (la, lo) in eng.AERODROMES.items():
        assert not w[0].polygon.contains(eng.Point(lo, la)), nome_ad
    # Os outros campos não ficam recortados pela área do vento
    vis = [b for b in blocos if b.phenomenon == "VIS"]
    assert vis and vis[0].polygon.symmetric_difference(eng.FIR_POLYGON).area < 1e-6


@pytest.mark.parametrize("nome", sorted(REAIS))
def test_gamet_real_na_4_7_4_o_vento_era_ignorado(eng474, nome):
    """O erro que a 4.7.5 corrige (o teste acima falha com este motor)."""
    blocos, *_ = eng474.parse_gamet(REAIS[nome][0])
    assert _wspd(blocos) == []
    assert eng474.campos_nao_interpretados(REAIS[nome][0]) == []


@pytest.mark.parametrize("nome", sorted(REAIS))
def test_gamet_real_sem_campo_nao_interpretado(eng, nome):
    texto = REAIS[nome][0]
    assert eng.campos_nao_interpretados(texto) == []
    r = eng.analisar_gamet(texto, "manual")
    assert not any("não interpretado" in m for _, m in r["avisos"])


@pytest.mark.parametrize("nome", sorted(REAIS))
def test_gamet_real_52_pontos_iguais_a_4_7_4(eng, eng474, nome):
    texto = REAIS[nome][0]
    novo, velho = _pontos(eng, texto), _pontos(eng474, texto)
    for icao in novo:
        assert novo[icao]["decision"] == velho[icao]["decision"] == "NO-GO", icao


@pytest.mark.parametrize("nome", sorted(REAIS))
def test_gamet_real_regiao_do_mar_diz_vento(eng, nome):
    texto = REAIS[nome][0]
    blocos, *_ = eng.parse_gamet(texto)
    regioes = eng.compute_dynamic_regions(blocos)
    p = _wspd(blocos)[0].polygon.representative_point()
    reg = eng.find_region_for_point(regioes, p.y, p.x)
    assert reg["decision"] == "NO-GO"
    # Pleno ou, numa lasca absorvida pela vizinha (4.7.3), "parte da zona: …"
    assert any(m.endswith("SFC WSPD 30KT ≥ 30KT (vento à superfície)")
               for m in reg["reasons"]), reg["reasons"]


@pytest.mark.parametrize("nome", sorted(REAIS))
def test_analisar_py_sem_palavras_desconhecidas(eng, nome):
    r = analisar.analisar(eng, REAIS[nome][0])
    assert r["excepcao"] is None
    assert not [a for a in r["alertas"] if a.startswith("Palavras desconhecidas")], r["alertas"]
    assert not [a for a in r["alertas"] if "sem fenómeno" in a], r["alertas"]


def test_analisar_py_continua_a_assinalar_palavra_desconhecida(eng):
    r = analisar.analisar(eng, _g("SFC WIND:N OF N4000 160/30KT XYZZY"))
    assert any(a.startswith("Palavras desconhecidas") and "XYZZY" in a for a in r["alertas"])


# ---------------------------------------------------------------- vento em terra

def test_sfc_wind_sozinho_em_terra_no_go_na_area_go_fora(eng, eng474):
    texto = _g("SFC WIND:N OF N4000 AND E OF W00800 250/35KT")
    pontos = _pontos(eng, texto)
    n_nogo = 0
    for nome, (la, lo) in eng.AERODROMES.items():
        if abs(la - 40.0) < 0.05 or abs(lo + 8.0) < 0.05:
            continue
        dec = pontos[_icao(nome)]["decision"]
        if la > 40.0 and lo > -8.0:
            assert dec == "NO-GO", nome
            assert any("SFC WSPD 35KT" in m for m in pontos[_icao(nome)]["reasons"])
            n_nogo += 1
        else:
            assert dec == "GO", nome
    assert n_nogo >= 3
    # Na 4.7.4: GO em todo o lado (o erro optimista)
    assert {r["decision"] for r in _pontos(eng474, texto).values()} == {"GO"}


def test_sfc_wind_toda_a_fir_igual_a_sfc_wspd(eng):
    for corpo in ("250/35KT", "N OF N3900 160/30KT", "10/14 S OF N3800 LAN 30KT",
                  "N OF N4000 AND W OF W00930 160/30KT"):
        bw, *_ = eng.parse_gamet(_g("SFC WIND:" + corpo))
        bs, *_ = eng.parse_gamet(_g("SFC WSPD:" + corpo))
        assert len(_wspd(bw)) == len(_wspd(bs)) == 1, corpo
        a, b = _wspd(bw)[0], _wspd(bs)[0]
        assert (a.value, a.qualifier, a.surface, a.window) == \
               (b.value, b.qualifier, b.surface, b.window), corpo
        assert a.polygon.symmetric_difference(b.polygon).area < 1e-12, corpo


@pytest.mark.parametrize("corpo,kt,dec", [
    ("150/30KT", 30, "NO-GO"),
    ("160/30KT", 30, "NO-GO"),
    ("250/35KT", 35, "NO-GO"),
    ("30KT", 30, "NO-GO"),
    ("250/35G45KT", 45, "NO-GO"),      # rajada: fica o valor mais alto (conservador)
    ("250/25KT", 25, "GO"),            # limiar inalterado (≥ 30 kt)
])
def test_valores_do_vento(eng, corpo, kt, dec):
    texto = _g("SFC WIND: " + corpo)
    blocos, *_ = eng.parse_gamet(texto)
    w = _wspd(blocos)
    assert [b.value for b in w] == [kt]
    assert w[0].polygon.symmetric_difference(eng.FIR_POLYGON).area < 1e-6
    assert {r["decision"] for r in _pontos(eng, texto).values()} == {dec}


def test_sfc_wind_ilegivel_avisa(eng):
    assert eng.campos_nao_interpretados(_g("SFC WIND:N OF N4000 XYZ")) != []


def test_sfc_wind_nil_nao_avisa(eng):
    assert eng.campos_nao_interpretados(_g("SFC WIND:NIL SFC VIS:LCA 2000M BR")) == []


# ---------------------------------------------------------------- depois de outro campo

@pytest.mark.parametrize("antes,fenomeno", [
    ("SFC VIS:LCA 2000-5000M BR", "VIS"),
    ("SIG CLD:LCA BKN 006-008/012HFT AGL", "BASE_AGL"),
    ("TURB:LCA MOD/SEV SFC/FL070", "TURB"),
    ("SIGWX:ISOL TS", "TS"),
])
def test_sfc_wind_depois_de_outro_campo(eng, eng474, antes, fenomeno):
    texto = _g(antes + " SFC WIND:N OF N3900 160/30KT")
    blocos, *_ = eng.parse_gamet(texto)
    w = _wspd(blocos)
    assert len(w) == 1 and w[0].value == 30
    assert w[0].polygon.symmetric_difference(eng.extract_polygon("N OF N3900")).area < 1e-9
    # O campo anterior fica com toda a FIR e sem o texto do vento
    outro = [b for b in blocos if b.phenomenon == fenomeno]
    assert outro
    for b in outro:
        assert b.polygon.symmetric_difference(eng.FIR_POLYGON).area < 1e-6, b.parte
        assert "WIND" not in b.parte
    assert eng.campos_nao_interpretados(texto) == []
    # Na 4.7.4 o vento ficava colado ao campo anterior e não gerava bloco
    b474, *_ = eng474.parse_gamet(texto)
    assert _wspd(b474) == []
    # Nos 52 pontos nunca mais permissivo do que a 4.7.4
    novo, velho = _pontos(eng, texto), _pontos(eng474, texto)
    for icao in novo:
        assert RANK[novo[icao]["decision"]] >= RANK[velho[icao]["decision"]], icao


def test_sfc_wind_entre_campos_com_janela(eng):
    texto = _g("SFC VIS:LCA 2000M BR SFC WIND:10/14 N OF N4000 160/35KT SIG CLD:"
               "LCA BKN 004/010HFT AGL")
    blocos, *_ = eng.parse_gamet(texto)
    w = _wspd(blocos)
    assert len(w) == 1 and w[0].value == 35 and w[0].window
    for b in blocos:
        if b.phenomenon != "WSPD":
            assert b.polygon.symmetric_difference(eng.FIR_POLYGON).area < 1e-6, b.parte


# ---------------------------------------------------------------- Secção II

def test_secn2_cld_termina_em_sfc_wind(eng):
    base = ("LPPC GAMET VALID 081500/082100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 "
            "SECN I SFC VIS:LCA 2000M BR SECN II CLD:N OF N4000 SCT ST 004/008HFT AGL ")
    for campo in ("SFC WIND:", "SFC WSPD:"):
        notas = eng.nuvens_baixas_secn2(base + campo + " S OF N3800 250/30KT MNM QNH:1003HPA=")
        assert notas, campo
        assert all("WIND" not in str(n) and "250/30" not in str(n) for n in notas), notas


def test_secn2_wind_t_inalterado(eng, eng474):
    for nome in sorted(REAIS):
        texto = REAIS[nome][0]
        assert eng.parse_wind(eng.normalize(texto).split("SECN II", 1)[1]) == \
               eng474.parse_wind(eng474.normalize(texto).split("SECN II", 1)[1])
        assert eng.nuvens_baixas_secn2(texto) == eng474.nuvens_baixas_secn2(texto)


# ---------------------------------------------------------------- AIRMET

def test_airmet_sfc_wind_inalterado(eng, eng474):
    for corpo in ("SFC WIND 250/35KT", "SFC WIND 250/25KT", "MOD TURB AND SFC WIND 250/35KT"):
        txt = (f"LPPC AIRMET 5 VALID 201700/202100 LPPT- LPPC LISBOA FIR/MAINLAND AREA "
               f"{corpo} OBS N OF N4000 STNR NC")
        a, b = eng.ler_airmet(txt), eng474.ler_airmet(txt)
        assert a["descr"] == b["descr"] and a["lido"] == b["lido"], corpo
        assert [(x.phenomenon, x.value) for x in a["blocos"]] == \
               [(x.phenomenon, x.value) for x in b["blocos"]], corpo
        assert any(x.phenomenon == "WSPD" for x in a["blocos"]), corpo


# ---------------------------------------------------------------- contra a 4.7.4
# tests/referencia/app_4_7_4.py é cópia fixa do app.py do main 9e46f66
# (`git show 9e46f66:app.py`; não editar).

GRELHA = [(la / 10, lo / 10) for la in range(368, 422, 3) for lo in range(-96, -61, 3)]
_SFC_WIND_RE = re.compile(r"\bSFC\s+WIND\b")


def _tem_sfc_wind(texto):
    secn1 = re.split(r"SECN\s+II", eng_norm(texto), maxsplit=1)[0]
    return bool(_SFC_WIND_RE.search(secn1))


def eng_norm(texto):
    return texto.upper()


def _comparar(eng, eng474, texto, nome, fonte="manual", **kw):
    rn = eng.analisar_gamet(texto, fonte, **kw)
    rv = eng474.analisar_gamet(texto, fonte, **kw)
    muda = _tem_sfc_wind(texto)
    if not muda:
        _iguais(eng, eng474, rn["regioes"], rv["regioes"], nome)
        for campo in ("por_dec", "avisos", "faixa_sig"):
            assert rn.get(campo) == rv.get(campo), (nome, campo)
    _nunca_mais_permissivo(eng, eng474, rn["regioes"], rv["regioes"], nome)
    rr_n, rr_v = rn.get("resto"), rv.get("resto")
    if not muda:
        assert (rr_n is None) == (rr_v is None), nome
        if rr_n:
            assert rr_n["decisao"] == rr_v["decisao"], nome
            _iguais(eng, eng474, rr_n["regioes"], rr_v["regioes"], nome + " resto")
    elif rr_n and rr_v:
        assert RANK[rr_n["decisao"]] >= RANK[rr_v["decisao"]], nome
        _nunca_mais_permissivo(eng, eng474, rr_n["regioes"], rr_v["regioes"], nome + " resto")
    return muda


def _iguais(eng, eng474, regs_n, regs_v, nome):
    assert len(regs_n) == len(regs_v), nome
    for a, b in zip(regs_n, regs_v):
        assert set(a) == set(b), nome
        assert a["polygon"].symmetric_difference(b["polygon"]).area < 1e-12, nome
        for k in b:
            if k != "polygon":
                assert a[k] == b[k], (nome, k)


def _nunca_mais_permissivo(eng, eng474, regs_n, regs_v, nome):
    for la, lo in list(eng.AERODROMES.values()) + GRELHA:
        rn = eng.find_region_for_point(regs_n, la, lo)
        rv = eng474.find_region_for_point(regs_v, la, lo)
        if rv is None:
            continue
        assert rn is not None, (nome, la, lo)
        assert RANK[rn["decision"]] >= RANK[rv["decision"]], (nome, la, lo)


def _arquivo():
    if not (DADOS / "indice.json").exists():
        pytest.skip("sem dados/")
    return json.loads((DADOS / "indice.json").read_text(encoding="utf-8"))


def test_arquivo_manual_contra_4_7_4(eng, eng474):
    indice = _arquivo()
    n = mudam = 0
    for entrada in indice.get("gamets", []):
        f = DADOS / entrada["ficheiro"]
        if not f.exists():
            continue
        ini = eng._iso_utc(entrada.get("inicio"))
        kw = {"agora": ini + timedelta(hours=3, minutes=30)} if ini else {}
        mudam += _comparar(eng, eng474, f.read_text(encoding="utf-8"), f.name, **kw)
        n += 1
    assert n > 50
    assert mudam >= 2


def test_arquivo_hist_contra_4_7_4(eng, eng474):
    indice = _arquivo()
    n = 0
    for entrada in indice.get("gamets", []):
        f = DADOS / entrada["ficheiro"]
        if not f.exists():
            continue
        ini, fim = eng._iso_utc(entrada.get("inicio")), eng._iso_utc(entrada.get("fim"))
        if not ini or not fim:
            continue
        for agora in (ini + timedelta(minutes=30), fim - timedelta(minutes=15)):
            _comparar(eng, eng474, f.read_text(encoding="utf-8"), f.name, "arquivo_hist",
                      indice=indice, entrada=entrada, agora=agora)
            n += 1
    assert n > 100


def test_arquivo_so_mudam_blocos_wspd(eng, eng474):
    """Em todo o arquivo, a 4.7.5 só acrescenta blocos WSPD aos GAMETs com
    SFC WIND; os outros blocos ficam iguais."""
    indice = _arquivo()
    for entrada in indice.get("gamets", []):
        f = DADOS / entrada["ficheiro"]
        if not f.exists():
            continue
        texto = f.read_text(encoding="utf-8")
        bn, *_ = eng.parse_gamet(texto)
        bv, *_ = eng474.parse_gamet(texto)
        resto_n = [b for b in bn if b.phenomenon != "WSPD"]
        resto_v = [b for b in bv if b.phenomenon != "WSPD"]
        assert len(resto_n) == len(resto_v), f.name
        for a, b in zip(resto_n, resto_v):
            assert (a.phenomenon, a.value, a.qualifier, a.window) == \
                   (b.phenomenon, b.value, b.qualifier, b.window), f.name
            assert a.polygon.symmetric_difference(b.polygon).area < 1e-12, f.name
        if not _tem_sfc_wind(texto):
            assert len(_wspd(bn)) == len(_wspd(bv)), f.name
        else:
            assert len(_wspd(bn)) > len(_wspd(bv)), f.name


def test_arquivo_sfc_wind_igual_a_sfc_wspd(eng):
    """Justifica `conftest.sfc_wind_475` (usado nos testes do arquivo contra a
    4.1/4.2/4.7.2/4.7.3): na 4.7.5 o GAMET com `SFC WIND` e o mesmo texto com
    `SFC WSPD` dão a mesma análise (regiões, decisões, motivos, avisos)."""
    indice = _arquivo()
    n = 0
    for entrada in indice.get("gamets", []):
        f = DADOS / entrada["ficheiro"]
        if not f.exists():
            continue
        texto = f.read_text(encoding="utf-8")
        trocado = conftest.sfc_wind_475(texto)
        if trocado == texto:
            assert not _tem_sfc_wind(texto), f.name
            continue
        assert "SFC WSPD" in trocado and not _tem_sfc_wind(trocado), f.name
        ini = eng._iso_utc(entrada.get("inicio"))
        kw = {"agora": ini + timedelta(hours=3, minutes=30)} if ini else {}
        ra = eng.analisar_gamet(texto, "manual", **kw)
        rb = eng.analisar_gamet(trocado, "manual", **kw)
        _iguais(eng, eng, ra["regioes"], rb["regioes"], f.name)
        for campo in ("por_dec", "avisos", "faixa_sig"):
            assert ra.get(campo) == rb.get(campo), (f.name, campo)
        n += 1
    assert n >= 2
