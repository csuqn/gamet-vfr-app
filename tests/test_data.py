"""
Testes de validade temporal, parsing de vento, ligação ao IPMA e robustez.
"""
from datetime import datetime, timezone

import pytest
from conftest import build_gamet


# ── VALIDADE TEMPORAL ────────────────────────────────────────────────
@pytest.mark.parametrize("dia,hora,minuto,ref,mes_esperado", [
    # REGRESSÃO (v25): replace(day=31) rebentava quando o mês actual não
    # tinha dia 31 — um GAMET válido era dado como expirado.
    (31, 21, 0, datetime(2026, 4, 1, 1, 0, tzinfo=timezone.utc), 3),
    (1, 3, 0, datetime(2026, 3, 31, 22, 0, tzinfo=timezone.utc), 4),
    (31, 21, 0, datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc), 12),
    (15, 12, 0, datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc), 3),
])
def test_construcao_de_data_atravessa_meses(eng, dia, hora, minuto, ref, mes_esperado):
    d = eng._build_utc_date(dia, hora, minuto, ref)
    assert d is not None, "não conseguiu construir a data"
    assert d.day == dia
    assert d.month == mes_esperado


def test_validade_periodo_de_seis_horas(eng):
    inicio, fim, _ = eng.parse_validity("LPPC GAMET VALID 151500/152100 LPPT")
    assert inicio and fim
    assert (fim - inicio).total_seconds() == 6 * 3600


def test_validade_atravessa_meia_noite(eng):
    inicio, fim, _ = eng.parse_validity("LPPC GAMET VALID 312100/010300 LPPT")
    assert inicio and fim
    assert fim > inicio
    assert (fim - inicio).total_seconds() == 6 * 3600


def test_validade_sem_campo(eng):
    assert eng.parse_validity("LPPC GAMET 201500/202100") == (None, None, False)


# ── VENTO ────────────────────────────────────────────────────────────
VENTO_REAL = (
    "WIND/T: BRAGANCA PORTO VISEU "
    "N4145 W00645 N4115 W00840 N4045 W00750 "
    "1000FT AGL 260/011KT PS14 330/010KT PS15 310/004KT PS15 "
    "2000FT AGL 270/011KT PS11 340/008KT PS14 350/004KT PS12 "
    "FZLVL: 8800FT AMSL 9200FT AMSL 8900FT AMSL LISBOA EVORA FARO "
    "N3845 W00908 N3830 W00752 N3700 W00800 "
    "1000FT AGL 360/011KT PS15 030/005KT PS14 120/008KT PS14 "
    "MNM QNH:1010HPA="
)


def test_vento_seis_estacoes(eng):
    estacoes = eng.parse_wind(VENTO_REAL)
    assert len(estacoes) == 6
    assert [e["station"] for e in estacoes] == [
        "BRAGANCA", "PORTO", "VISEU", "LISBOA", "EVORA", "FARO"]


def test_vento_alinhamento_correcto(eng):
    estacoes = eng.parse_wind(VENTO_REAL)
    assert estacoes[0]["levels"]["1000FT AGL"] == {"dir": 260, "spd": 11, "temp": 14}
    assert estacoes[3]["levels"]["1000FT AGL"] == {"dir": 360, "spd": 11, "temp": 15}


def test_vento_nome_com_espaco(eng):
    """
    REGRESSÃO (v25): nomes multi-palavra desalinhavam nomes e coordenadas,
    porque o número de estações vinha de .split() e não das coordenadas.
    """
    estacoes = eng.parse_wind(
        "WIND/T: VILA REAL PORTO VISEU "
        "N4116 W00743 N4114 W00840 N4043 W00753 "
        "1000FT AGL 100/010KT PS10 200/020KT PS11 300/030KT PS12 "
        "MNM QNH:1013HPA=")
    assert len(estacoes) == 3
    assert estacoes[0]["station"] == "VILA REAL"
    assert estacoes[0]["levels"]["1000FT AGL"]["dir"] == 100
    assert estacoes[1]["station"] == "PORTO"


def test_vento_nome_com_acento(eng):
    estacoes = eng.parse_wind(
        "WIND/T: BRAGANÇA PORTO VISEU "
        "N4145 W00645 N4115 W00840 N4045 W00750 "
        "1000FT AGL 260/011KT PS14 330/010KT PS15 310/004KT PS15 "
        "MNM QNH:1013HPA=")
    assert len(estacoes) == 3
    assert estacoes[0]["station"] == "BRAGANÇA"


def test_temperatura_negativa(eng):
    estacoes = eng.parse_wind(
        "WIND/T: PORTO N4115 W00840 FL150 070/021KT MS13 MNM QNH:1013HPA=")
    assert estacoes[0]["levels"]["FL150"]["temp"] == -13


@pytest.mark.parametrize("dados", [
    [], [{"station": "X", "levels": {}}], [{"station": "Y"}],
])
def test_aviso_de_vento_tolera_dados_em_falta(eng, dados):
    assert eng.check_strong_wind(dados) == []


def test_aviso_de_vento_forte(eng):
    dados = [
        {"station": "PORTO", "levels": {"1000FT AGL": {"dir": 250, "spd": 25, "temp": 10}}},
        {"station": "LISBOA", "levels": {"1000FT AGL": {"dir": 180, "spd": 8, "temp": 15}}},
    ]
    avisos = eng.check_strong_wind(dados)
    assert len(avisos) == 1 and "PORTO" in avisos[0]


# ── SECÇÃO II ────────────────────────────────────────────────────────
def test_fzlvl_usa_o_minimo(analyse):
    r = analyse(build_gamet("SECN I SFC VIS: 5000M").replace(
        "SECN II", "SECN II FZLVL: 8800FT AMSL 7500FT AMSL 9000FT AMSL"))
    assert r["fzlvl"] == 7500


@pytest.mark.parametrize("qnh", ["1013", "998", "1030"])
def test_qnh(analyse, qnh):
    r = analyse(build_gamet("SECN I SFC VIS: 5000M", qnh=qnh))
    assert r["qnh"] == int(qnh)


# ── ROBUSTEZ ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("texto", ["", "   ", "lixo qualquer", "LPPC GAMET", "=" * 50])
def test_texto_invalido_nao_rebenta(analyse, texto):
    """Nunca lançar excepção — a app tem de degradar-se com elegância."""
    r = analyse(texto)
    assert r["regions"], "devia devolver pelo menos uma região"


@pytest.mark.parametrize("texto,suspeito", [
    ("lixo qualquer sem nada", True),
    ("LPPC GAMET VALID 201500/202100 SECN II MNM QNH:1013HPA=", True),
    # Só SIGMET não é campo meteorológico — REGRESSÃO (v25)
    ("LPPC GAMET VALID 201500/202100 SECN I SIGMET APPLICABLE: NIL SECN II MNM QNH:1013HPA=", True),
    # GAMET genuinamente calmo tem campos, ainda que NIL
    ("LPPC GAMET VALID 201500/202100 SECN I SFC VIS: NIL SIGWX: NIL "
     "SIGMET APPLICABLE: NIL SECN II MNM QNH:1013HPA=", False),
])
def test_deteccao_de_texto_nao_interpretavel(eng, texto, suspeito):
    assert eng.looks_unparseable(texto) is suspeito


def test_normalizacao_minusculas_e_travessao(analyse):
    r = analyse(build_gamet("secn i sfc vis: 1800–4500m sigwx: ocnl ts"))
    assert 1800 in r["vis"]
    assert "OCNL" in r["ts"]


# ── LIGAÇÃO AO IPMA ──────────────────────────────────────────────────
class RespostaFalsa:
    def __init__(self, status, texto=""):
        self.status_code, self.text = status, texto


GAMET_HTML = (
    "<pre>LPPC GAMET VALID 201500/202100 LPPT-LPPC LISBOA FIR SECN I "
    "SFC VIS: 5000M SIGMET APPLICABLE: NIL SECN II MNM QNH:1013HPA=</pre>"
)


@pytest.mark.parametrize("carga", [
    GAMET_HTML,
    '{"text": "LPPC GAMET VALID 201500/202100 LPPT SECN I SFC VIS: 5000M SECN II MNM QNH:1013HPA="}',
    '{"data":[{"content":"LPPC GAMET VALID 201500/202100 LPPT SECN I SFC VIS: 5000M SECN II MNM QNH:1013HPA="}]}',
    "LPPC GAMET VALID 201500/202100 LPPT SECN I SFC VIS: 5000M SECN II MNM QNH:1013HPA=",
])
def test_extraccao_html_e_json(net, carga):
    """A API do IPMA pode devolver HTML ou JSON — ambos têm de funcionar."""
    texto = net.extract_gamet_from_html(carga)
    assert texto.startswith("LPPC GAMET") and texto.endswith("=")


def test_extraccao_sem_gamet(net):
    assert net.extract_gamet_from_html('{"data":[]}') == ""


def test_fetch_tenta_varios_endpoints(net, monkeypatch):
    tentados = []

    def falso_get(url, params=None, headers=None, timeout=None):
        tentados.append(url)
        if "pages/actuals/sigmet" in url:
            return RespostaFalsa(200, GAMET_HTML)
        return RespostaFalsa(404)

    monkeypatch.setattr(net.requests, "get", falso_get)
    ok, resultado = net.fetch_gamet_ipma()
    assert ok and resultado.startswith("LPPC GAMET")
    assert "pages/actuals/sigmet.php" in tentados[0], "endpoint actual deve vir primeiro"


def test_fetch_url_personalizado_tem_precedencia(net, monkeypatch):
    tentados = []
    monkeypatch.setattr(net.requests, "get",
                        lambda url, **kw: (tentados.append(url), RespostaFalsa(200, GAMET_HTML))[1])
    ok, _ = net.fetch_gamet_ipma("https://exemplo.pt/meu.php")
    assert ok
    assert tentados == ["https://exemplo.pt/meu.php"]


def test_fetch_distingue_tipos_de_falha(net, monkeypatch):
    """404 em tudo vs. 200 sem GAMET são problemas diferentes."""
    monkeypatch.setattr(net.requests, "get", lambda url, **kw: RespostaFalsa(404))
    ok, msg = net.fetch_gamet_ipma()
    assert not ok and "endpoint" in msg.lower()

    monkeypatch.setattr(net.requests, "get",
                        lambda url, **kw: RespostaFalsa(200, "<html>manutenção</html>"))
    ok, msg = net.fetch_gamet_ipma()
    assert not ok and "respondeu" in msg.lower()


def test_proximo_gamet_e_sempre_futuro(net):
    assert net.next_gamet_time() > datetime.now(timezone.utc)
