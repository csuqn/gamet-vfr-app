"""
2.6 — analisar_gamet: a análise completa (validade, regiões, SIGMETs,
avisos) passou para o motor e é partilhada pelas duas interfaces
(Streamlit e NiceGUI). Testa-se a função directamente.
"""
from datetime import datetime, timezone, timedelta

from conftest import build_gamet

AGORA = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
G = build_gamet("SECN I SFC VIS: N OF N4100 2000M BR", validity="170900/171500")


def _sig(n, ini, fim, tipo="SIGMET"):
    return f"LPPC {tipo} {n} VALID {ini:%d%H%M}/{fim:%d%H%M} LPPT- LPPC LISBOA FIR SEV TURB FCST="


def _tipos(r):
    return [t for t, _ in r["avisos"]]


def test_manual_sigmets_nao_verificados(eng):
    r = eng.analisar_gamet(G, "manual", agora=AGORA)
    assert r["faixa_sig"] == ("N/VERIF.", None)
    assert "info" in _tipos(r)
    assert r["faixa_val"] == "17 09–15Z" and r["faixa_exp"] == "3h00m"


def test_ipma_sem_sigmet_diz_nil(eng):
    r = eng.analisar_gamet(G, "ipma", boletins=[], boletins_at=AGORA, agora=AGORA)
    assert r["faixa_sig"] == ("NIL", "GO")
    assert any(t == "ok" and "verificado às 12:00Z" in m for t, m in r["avisos"])


def test_sigmet_do_ipma_forca_no_go(eng):
    s = _sig(4, AGORA - timedelta(hours=1), AGORA + timedelta(hours=2))
    r = eng.analisar_gamet(G, "ipma", boletins=[s], boletins_at=AGORA, agora=AGORA)
    assert {g["decision"] for g in r["regioes"]} == {"NO-GO"}
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")
    assert any(t == "erro" and "SIGMET 4" in m and "não referido" in m for t, m in r["avisos"])


def test_gamet_do_arquivo_usa_so_os_sigmets_da_sua_validade(eng):
    ini = AGORA - timedelta(days=2)
    fim = ini + timedelta(hours=6)
    antigo = _sig(1, ini + timedelta(hours=1), ini + timedelta(hours=2))
    actual = _sig(9, AGORA - timedelta(hours=1), AGORA + timedelta(hours=2))
    fmt = "%Y-%m-%dT%H:%MZ"
    indice = {"sigmets": [{"texto": antigo, "inicio": (ini + timedelta(hours=1)).strftime(fmt),
                           "fim": (ini + timedelta(hours=2)).strftime(fmt)}]}
    entrada = {"inicio": ini.strftime(fmt), "fim": fim.strftime(fmt)}
    r = eng.analisar_gamet(G, "arquivo_hist", boletins=[actual], boletins_at=AGORA,
                           indice=indice, entrada=entrada, agora=AGORA)
    texto = " ".join(m for _, m in r["avisos"])
    assert "SIGMET 1" in texto and "SIGMET 9" not in texto
    assert "GAMET DO ARQUIVO" in texto


def test_gamet_fora_de_validade_avisa(eng):
    r = eng.analisar_gamet(G, "manual", agora=AGORA + timedelta(hours=6))
    assert r["faixa_exp"] == "EXPIRADO"
    assert any("FORA DO PERÍODO" in m for _, m in r["avisos"])


def test_mesmas_regioes_que_o_pipeline(eng, analyse):
    r = eng.analisar_gamet(G, "manual", agora=AGORA)
    assert [g["decision"] for g in r["regioes"]] == analyse(G)["decisions"]
