"""
4.7.3 — os motivos de uma região fundida só afirmam o que vale em toda ela.

GAMET real 061500/062100 (recolhido a 6-nov-2026 14:42Z), SIG CLD:
"N OF N3800 LCA BKN 004-008/010HFT AGL BTN N4030 - N3800 MAR AND COT ISOL
TCU/CB 018-035/XXXHFT AGL". O CB só cobre MAR∪COT entre N3800 e N4030 (dos 52
pontos, só LPCS, LPSC, LP49, LP63). Mas uma fatia de 1,2% da FIR com o CB
(Atouguia da Baleia) era absorvida por `_merge_slivers` na região MARGINAL do
interior norte (37,5%): a 1.ª escolha (`_assinatura`) compara decisão, VIS,
base, TS, TURB, ICE, MT OBSC e VA, mas não o CB (nem WSPD, MTW, SIGWX, SIGMET,
AIRMET), e `_absorb_values` unia os motivos. A região de 38,8% ("Casarão,
Seia, Viseu +29", com LPPR/LPBG/LPCH/LPVR/LPSO) dizia "CB ISOL (cumulonimbos)".

Desde a 4.7.3 a fusão fica igual (mesmos polígonos, decisões e valores) e um
motivo que só vale numa das partes passa a "parte da zona: <motivo>" — nenhum
motivo desaparece. As decisões não mudam (só texto).
"""
import json
import re
import types
from datetime import timedelta
from pathlib import Path

import pytest

import conftest

REF472 = Path(__file__).resolve().parent / "referencia" / "app_4_7_2.py"
DADOS = Path(__file__).resolve().parent.parent / "dados"
PARCIAL = "parte da zona: "

G061500 = (
    "LPPC GAMET VALID 061500/062100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I "
    "SFC VIS:N OF N3800 LCA 1200-5000M DZ/BR/RA SIG CLD:N OF N3800 LCA BKN "
    "004-008/010HFT AGL BTN N4030 - N3800 MAR AND COT ISOL TCU/CB 018-035/XXXHFT AGL "
    "ICE:N OF N3900 LAN LCA MOD ABV FL090 TURB:N OF N3820 AND W OF W00735 LCA MOD "
    "SFC/FL090 SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN II PSYS:18 N3840 W01000 - "
    "N4000 W00900 - N4130 W01000 COLD FRONT MOV NE NC CLD:SCT/BKN SC/CU "
    "012-025/030-050HFT AGL SCT/BKN AS/AC 060-090/100-130HFT AMSL WIND/T: BRAGANCA "
    "PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL 190/008KT PS08 "
    "160/020KT PS13 160/008KT PS10 2000FT AGL 190/010KT PS06 180/025KT PS12 190/013KT "
    "PS09 5000FT AGL 240/015KT PS03 210/018KT PS08 230/018KT PS05 FL100 240/015KT MS01 "
    "260/025KT MS00 250/025KT MS00 FL150 250/018KT MS08 260/023KT MS09 260/028KT MS09 "
    "FZLVL: 9400FT AMSL 9900FT AMSL 9600FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 "
    "W00752 N3700 W00800 1000FT AGL 180/015KT PS14 220/011KT PS17 130/005KT PS16 2000FT "
    "AGL 200/024KT PS13 210/010KT PS15 200/005KT PS16 5000FT AGL 250/025KT PS10 "
    "210/017KT PS07 230/014KT PS11 FL100 250/018KT PS01 250/021KT PS01 250/015KT PS01 "
    "FL150 270/019KT MS09 250/021KT MS08 250/023KT MS09 FZLVL: 10500FT AMSL 10300FT "
    "AMSL 10500FT AMSL MNM QNH:1017HPA="
)

CB_RE = re.compile(r"^(?:AIRMET \S+ — )?CB\b")
COM_CB = {"LPCS", "LPSC", "LP49", "LP63"}
INTERIOR_NORTE = {"LPBG", "LPCH", "LPPR", "LPVR", "LPSO", "LPVZ", "LPSE"}


def _icao(nome):
    return nome.rsplit("(", 1)[1].rstrip(")")


def _sem_prefixo(m):
    return m[len(PARCIAL):] if m.startswith(PARCIAL) else m


def _plenos(regiao):
    return [m for m in regiao["reasons"] if not m.startswith(PARCIAL)]


@pytest.fixture(scope="module")
def eng472(eng):
    mod = types.ModuleType("motor_4_7_2")
    mod.__dict__["__file__"] = str(REF472)
    exec(compile(conftest._extract_engine(REF472.read_text(encoding="utf-8")), str(REF472),
                 "exec"), mod.__dict__)
    return mod


def test_referencia_e_a_4_7_2(eng, eng472):
    assert eng472.APP_VERSION == "4.7.2"
    assert tuple(int(x) for x in eng.APP_VERSION.split(".")) >= (4, 7, 3)


# ---------------------------------------------------------------- GAMET real

def test_gamet_real_061500_cb_nao_e_motivo_do_interior(eng):
    blocos, *_ = eng.parse_gamet(G061500)
    regioes = eng.compute_dynamic_regions(blocos)
    pontos = {_icao(n): eng.find_region_for_point(regioes, la, lo)
              for n, (la, lo) in eng.AERODROMES.items()}
    for icao in INTERIOR_NORTE:
        assert not any(CB_RE.match(m) for m in _plenos(pontos[icao])), (icao, pontos[icao]["reasons"])
    # A região de Cascais/Tojeira tem CB em toda ela: motivo pleno
    assert any(CB_RE.match(m) for m in _plenos(pontos["LPCS"])), pontos["LPCS"]["reasons"]
    # Nos pontos com CB, o motivo continua lá (pleno ou "parte da zona")
    for icao in COM_CB:
        assert any(CB_RE.match(_sem_prefixo(m)) for m in pontos[icao]["reasons"]), icao
    # A fatia com CB absorvida na região grande não perde o motivo
    grande = pontos["LPBG"]
    assert PARCIAL + "CB ISOL (cumulonimbos)" in grande["reasons"]
    # Decisão de todos os pontos: MARGINAL a N de N3800, GO a sul
    for nome, (la, lo) in eng.AERODROMES.items():
        esperado = "MARGINAL" if la > 38.0 else "GO"
        assert pontos[_icao(nome)]["decision"] == esperado, nome


def test_gamet_real_061500_igual_a_4_7_2_excepto_texto(eng, eng472):
    _comparar(eng, eng472, G061500, "061500")


def test_analisar_gamet_061500(eng):
    r = eng.analisar_gamet(G061500, "manual")
    reg = eng.find_region_for_point(r["regioes"], 41.8, -6.73)    # perto de Bragança
    assert not any(CB_RE.match(m) for m in _plenos(reg))
    # Os componentes de UI e o PDF não rebentam com motivos parciais
    html = eng.html_regiao(reg, 38.8)
    assert "parte da zona: CB ISOL" in html
    assert "CB (parte da zona)" in html                            # coluna CB/TS
    pdf = eng.generate_pdf(r["regioes"], G061500, r["fz"], r["qnh"], "")
    assert pdf[:4] == b"%PDF"


# ---------------------------------------------------------------- _absorb_values

def _reg(reasons, **kw):
    d = dict(vis=None, base=None, ts=[], turb=[], turb_layers=[], ice=[],
             ice_layers=[], mt_obsc=[], va=[], reasons=list(reasons), notas=[])
    d.update(kw)
    return d


def test_absorb_motivo_comum_fica_pleno(eng):
    a = _reg(["BASE 400ft < 500ft", "CB ISOL (cumulonimbos)"])
    b = _reg(["BASE 300ft < 500ft", "CB ISOL (cumulonimbos)"])
    eng._absorb_values(a, b)
    assert a["reasons"] == ["BASE 300ft < 500ft", "CB ISOL (cumulonimbos)"]


def test_absorb_motivo_so_de_uma_parte_fica_parcial(eng):
    a = _reg(["BASE 400ft < 500ft", "VIS LCA 1200m < 1500m (local)"])
    b = _reg(["BASE 400ft < 500ft", "CB ISOL (cumulonimbos)", "VIS LCA 1200m < 1500m (local)"])
    eng._absorb_values(a, b)
    assert a["reasons"] == ["BASE 400ft < 500ft", "VIS LCA 1200m < 1500m (local)",
                            PARCIAL + "CB ISOL (cumulonimbos)"]
    # E nos dois sentidos
    a = _reg(["SIGMET T01", "TS OCNL (risco alto)"])
    b = _reg(["TS OCNL (risco alto)"])
    eng._absorb_values(a, b)
    assert a["reasons"] == ["TS OCNL (risco alto)", PARCIAL + "SIGMET T01"]


def test_absorb_parcial_continua_parcial(eng):
    a = _reg(["CB ISOL (cumulonimbos)", PARCIAL + "SFC WSPD 35KT ≥ 30KT (vento à superfície)"])
    b = _reg(["CB ISOL (cumulonimbos)", "SFC WSPD 35KT ≥ 30KT (vento à superfície)"])
    eng._absorb_values(a, b)
    assert a["reasons"] == ["CB ISOL (cumulonimbos)",
                            PARCIAL + "SFC WSPD 35KT ≥ 30KT (vento à superfície)"]
    # Base: limiar só numa parte → parcial, com a base mais baixa
    a = _reg(["BASE 400ft < 500ft", PARCIAL + "BASE 250ft < 300ft"])
    b = _reg(["BASE 450ft < 500ft", "BASE 200ft < 300ft"])
    eng._absorb_values(a, b)
    assert a["reasons"] == ["BASE 400ft < 500ft", PARCIAL + "BASE 200ft < 300ft"]
    # Origem AIRMET: o prefixo vem antes da origem
    a = _reg(["AIRMET 2 — VIS 200m < 1500m"])
    b = _reg([])
    eng._absorb_values(a, b)
    assert a["reasons"] == [PARCIAL + "AIRMET 2 — VIS 200m < 1500m"]


def test_html_cb_ts_parcial(eng):
    assert eng._cb_ts(_reg(["CB ISOL (cumulonimbos)"])) == "CB"
    assert eng._cb_ts(_reg([PARCIAL + "CB ISOL (cumulonimbos)"])) == "CB (parte da zona)"
    assert eng._cb_ts(_reg([PARCIAL + "AIRMET 1 — CB OCNL (cumulonimbos, risco alto)"])) == \
        "CB (parte da zona)"
    assert eng._cb_ts(_reg(["VIS 800m < 1500m"])) == "—"


# ---------------------------------------------------------------- contra a 4.7.2
# tests/referencia/app_4_7_2.py é cópia fixa do app.py do main d30a657
# (`git show d30a657:app.py`; não editar).

GRELHA = [(la / 10, lo / 10) for la in range(368, 422, 3) for lo in range(-96, -61, 3)]


def _comparar(eng, eng472, texto, nome, fonte="manual", **kw):
    rn = eng.analisar_gamet(texto, fonte, **kw)
    rv = eng472.analisar_gamet(texto, fonte, **kw)
    _comparar_regioes(eng, eng472, rn["regioes"], rv["regioes"], nome)
    for campo in ("por_dec", "avisos", "faixa_sig"):
        assert rn.get(campo) == rv.get(campo), (nome, campo)
    rr_n, rr_v = rn.get("resto"), rv.get("resto")
    assert (rr_n is None) == (rr_v is None), nome
    if rr_n:
        assert rr_n["decisao"] == rr_v["decisao"], nome
        _comparar_regioes(eng, eng472, rr_n["regioes"], rr_v["regioes"], nome + " resto")
    return rn


def _comparar_regioes(eng, eng472, regs_n, regs_v, nome):
    assert len(regs_n) == len(regs_v), nome
    area_n = sum(r["polygon"].area for r in regs_n)
    area_v = sum(r["polygon"].area for r in regs_v)
    assert abs(area_n - area_v) < 1e-9, nome
    for a, b in zip(regs_n, regs_v):
        assert a["polygon"].symmetric_difference(b["polygon"]).area < 1e-12, nome
        for k in b:
            if k == "reasons":
                continue
            if k == "polygon":
                continue
            if k == "notas":
                # 4.7.4: notas de alcance parciais ganham o prefixo (test_v474)
                assert conftest.notas_sem_parcial_474(a[k]) == b[k], (nome, k)
                continue
            assert a[k] == b[k], (nome, k)
        # Nenhum motivo desaparece nem aparece: só passa a "parte da zona"
        assert sorted(_sem_prefixo(m) for m in a["reasons"]) == sorted(b["reasons"]), \
            (nome, a["reasons"], b["reasons"])
    for la, lo in list(eng.AERODROMES.values()) + GRELHA:
        rn = eng.find_region_for_point(regs_n, la, lo)
        rv = eng472.find_region_for_point(regs_v, la, lo)
        assert (rn is None) == (rv is None), (nome, la, lo)
        if rn is not None:
            assert rn["decision"] == rv["decision"], (nome, la, lo)


def _arquivo():
    if not (DADOS / "indice.json").exists():
        pytest.skip("sem dados/")
    return json.loads((DADOS / "indice.json").read_text(encoding="utf-8"))


def test_arquivo_manual_contra_4_7_2(eng, eng472):
    indice = _arquivo()
    n = 0
    for entrada in indice.get("gamets", []):
        f = DADOS / entrada["ficheiro"]
        if not f.exists():
            continue
        texto = conftest.sfc_wind_475(f.read_text(encoding="utf-8"))  # 4.7.5
        if conftest.superficie_476(eng, texto):
            continue  # 4.7.6: verificado em test_v476.py
        ini = eng._iso_utc(entrada.get("inicio"))
        kw = {"agora": ini + timedelta(hours=3, minutes=30)} if ini else {}
        _comparar(eng, eng472, texto, f.name, **kw)
        n += 1
    assert n > 50


def test_arquivo_hist_contra_4_7_2(eng, eng472):
    indice = _arquivo()
    n = 0
    for entrada in indice.get("gamets", []):
        f = DADOS / entrada["ficheiro"]
        if not f.exists():
            continue
        texto = conftest.sfc_wind_475(f.read_text(encoding="utf-8"))  # 4.7.5
        if conftest.superficie_476(eng, texto):
            continue  # 4.7.6: verificado em test_v476.py
        ini = eng._iso_utc(entrada.get("inicio"))
        fim = eng._iso_utc(entrada.get("fim"))
        if not ini or not fim:
            continue
        for agora in (ini + timedelta(minutes=30), fim - timedelta(minutes=15)):
            _comparar(eng, eng472, texto, f.name, "arquivo_hist",
                      indice=indice, entrada=entrada, agora=agora)
            n += 1
    assert n > 100


# ---------------------------------------------------------------- oráculo
# Cada motivo PLENO de uma região tem de valer em cada ponto dela (calculado
# directamente sobre os fenómenos que contêm o ponto). Bases AMSL ficam de
# fora (o limiar depende da quadrícula de relevo).

def _motivos_ponto(eng, blocos, lon, lat):
    p = eng.Point(lon, lat)
    ev = []
    for b in blocos:
        if not b.polygon.buffer(0.01).contains(p):
            continue
        if not b.polygon.buffer(-0.01).contains(p):
            return None          # em cima de uma fronteira — não julgar
        if b.phenomenon == "BASE_AGL":
            ev.append(("BASE", b.value, b.qualifier, b.layer))
        else:
            ev.append((b.phenomenon, b.value, b.qualifier, b.layer))
    return {eng._BASE_REASON_RE.sub(r"\1BASE #ft", m) for m in eng.decision(ev)[-1]}


def _verificar_oraculo(eng, texto, nome):
    blocos, *_ = eng.parse_gamet(texto)
    if any(b.phenomenon == "BASE_AMSL" for b in blocos):
        return 0
    regioes = eng.compute_dynamic_regions(blocos)
    n = 0
    for la, lo in list(eng.AERODROMES.values()) + GRELHA:
        if not eng.FIR_POLYGON.buffer(-0.02).contains(eng.Point(lo, la)):
            continue
        esperado = _motivos_ponto(eng, blocos, lo, la)
        if esperado is None:
            continue
        reg = eng.find_region_for_point(regioes, la, lo)
        if reg is None:
            continue
        for m in _plenos(reg):
            assert eng._BASE_REASON_RE.sub(r"\1BASE #ft", m) in esperado, (nome, la, lo, m)
        n += 1
    return n


def test_motivos_plenos_valem_em_cada_ponto_gamet_real(eng):
    assert _verificar_oraculo(eng, G061500, "061500") > 50


def test_motivos_plenos_valem_em_cada_ponto_arquivo(eng):
    indice = _arquivo()
    n = 0
    for entrada in indice.get("gamets", []):
        f = DADOS / entrada["ficheiro"]
        if f.exists():
            n += _verificar_oraculo(eng, f.read_text(encoding="utf-8"), f.name)
    assert n > 1000
