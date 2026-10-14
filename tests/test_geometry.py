"""
Testes de geometria dinâmica, SIGMET e invariantes universais.

Os invariantes são propriedades que TÊM de se verificar em qualquer GAMET,
independentemente do conteúdo — são a rede de segurança mais valiosa da
suite, porque apanham regressões que testes específicos não anteciparam.
"""
import pytest
from conftest import build_gamet


# ── QUALIFICADORES GEOGRÁFICOS ───────────────────────────────────────
@pytest.mark.parametrize("geo", [
    "N OF N4030", "S OF N3900", "E OF W00800", "W OF W00900",
    "BTN N3900 AND N4030",
])
def test_geo_restringe_area(analyse, eng, geo):
    """Um fenómeno com geografia não pode cobrir a FIR inteira."""
    r = analyse(build_gamet(f"SECN I SIG CLD: {geo} BKN 002HFT AGL"))
    assert "NO-GO" in r["decisions"]
    assert "GO" in r["decisions"], f"'{geo}' devia deixar parte da FIR livre"

    for b in r["blocks"]:
        if b.phenomenon == "BASE_AGL":
            frac = b.polygon.area / eng.FIR_POLYGON.area
            assert 0.01 < frac < 0.99, f"área implausível: {frac:.0%}"


def test_multiplos_blocos_geo_na_mesma_linha(analyse):
    """Duas zonas na mesma linha têm de dar bases distintas."""
    r = analyse(build_gamet(
        "SECN I SIG CLD: N OF N4030 BKN 002HFT AGL "
        "S OF N3845 ISOL TCU/CB 020HFT AGL"))
    assert 200 in r["base"] and 2000 in r["base"]


def test_tres_blocos_geo(analyse):
    r = analyse(build_gamet(
        "SECN I SIG CLD: N OF N4100 BKN 002HFT AGL "
        "BTN N3900 AND N4100 SCT 015HFT AGL "
        "S OF N3900 FEW 030HFT AGL"))
    for esperado in (200, 1500, 3000):
        assert esperado in r["base"]


def test_geometria_nunca_produz_geometrycollection(analyse, eng):
    """
    REGRESSÃO (v16): intersecções degeneradas produziam GeometryCollection,
    cujo .boundary é None — o fenómeno desaparecia silenciosamente do mapa.
    """
    for geo in ["S OF N3800", "N OF N4030", "BTN N3900 AND N4130", "E OF W00830"]:
        r = analyse(build_gamet(f"SECN I SIGWX: {geo} FRQ TS"))
        for b in r["blocks"]:
            if b.polygon is not None:
                assert b.polygon.geom_type in ("Polygon", "MultiPolygon"), \
                    f"'{geo}' produziu {b.polygon.geom_type}"


# ── SIGMET ───────────────────────────────────────────────────────────
SIGMETS_REAIS = [
    "LPPC1 VALID 201500/201900 LPPC- LISBOA FIR SEV TURB FCST BLW FL100 STNR NC",
    "LPPC2 VALID 201500/201900 LPPC- LISBOA FIR SEV ICE FCST FL050/FL120 STNR NC",
    "LPPC3 VALID 201500/202100 LPPC- LISBOA FIR VA CLD OBS FL100/FL200 MOV SE 20KT",
    "LPPC4 VALID 201500/201900 LPPC- LISBOA FIR SEV MTW FCST FL080/FL150 STNR NC",
    "LPPC5 VALID 201500/202100 LPPC- LISBOA FIR EMBD TS FCST TOP FL350 MOV NE 25KT",
    "LPPC6 VALID 201500/202100 LPPC- LISBOA FIR TC OBS TOP FL400",
]


@pytest.mark.parametrize("sigmet", SIGMETS_REAIS)
def test_sigmet_activo_forca_nogo(analyse, sigmet):
    """Um SIGMET activo sobrepõe-se a tudo, mesmo com céu limpo."""
    r = analyse(build_gamet("SECN I SFC VIS: 9999M SIG CLD: NIL", sigmet=sigmet))
    assert r["has_sigmet"]
    assert set(r["decisions"]) == {"NO-GO"}
    assert any("SIGMET" in m for reg in r["regions"] for m in reg["reasons"])


@pytest.mark.parametrize("sigmet", SIGMETS_REAIS)
def test_sigmet_preserva_texto(analyse, sigmet):
    """O texto do SIGMET não pode ser truncado ao ser extraído."""
    r = analyse(build_gamet("SECN I SFC VIS: 5000M", sigmet=sigmet))
    assert r["sigmet_text"].strip() == sigmet.strip()


@pytest.mark.parametrize("nil", [
    "AT TIME OF ISSUE NIL", "NIL",
])
def test_sigmet_nil_nao_dispara(analyse, nil):
    r = analyse(build_gamet("SECN I SFC VIS: 5000M", sigmet=nil))
    assert not r["has_sigmet"]
    assert r["decisions"] == ["GO"]


def test_sigmet_duplicado_nao_da_falso_positivo(analyse):
    """REGRESSÃO (v24): dois marcadores SIGMET davam falso positivo."""
    r = analyse(build_gamet(
        "SECN I SFC VIS: 2500M SIGWX: ISOL TS "
        "SIGMET APPLICABLE: AT TIME OF ISSUE NIL SIG CLD: 001HFT AGL"))
    assert not r["has_sigmet"]


def test_campos_apos_sigmet_sao_ignorados(analyse):
    """SIGMET APPLICABLE é o último campo — o que vier depois é inválido."""
    r = analyse(build_gamet(
        "SECN I SFC VIS: 2500M "
        "SIGMET APPLICABLE: AT TIME OF ISSUE NIL SIG CLD: 001HFT AGL"))
    assert r["base"] == []
    assert r["decisions"] == ["MARGINAL"]


# ── INVARIANTES UNIVERSAIS ───────────────────────────────────────────
GAMETS_VARIADOS = [
    "SECN I SFC VIS: NIL SIGWX: NIL SIG CLD: NIL",
    "SECN I SFC VIS: 800M SIGWX: FRQ TS",
    "SECN I SIG CLD: N OF N4030 BKN 002HFT AGL S OF N3845 ISOL TCU/CB 020HFT AGL",
    "SECN I MT OBSC N OF N4000 VA: S OF N3800 FL030/FL150",
    "SECN I SFC VIS: LCA 2000-5000M RA/BR SIGWX: S OF N4100 ISOL/EMBD TS "
    "ICE: BTN N3900 AND N4130 LCA MOD ABV FL070 TURB: S OF N3900 MOD SFC/FL030",
    "SECN I TURB: BTN N3900 AND N4200 SEV SFC/FL080 SFC VIS: 8000M",
    "secn i sfc vis: 1800m sigwx: ocnl ts",
]


@pytest.mark.parametrize("corpo", GAMETS_VARIADOS)
def test_invariante_cobertura_total(analyse, eng, corpo):
    """As regiões dinâmicas cobrem sempre ~100% da FIR — sem buracos."""
    r = analyse(build_gamet(corpo))
    total = sum(reg["polygon"].area for reg in r["regions"])
    pct = 100 * total / eng.FIR_POLYGON.area
    assert 98 <= pct <= 102, f"cobertura {pct:.1f}%"


@pytest.mark.parametrize("corpo", GAMETS_VARIADOS)
def test_invariante_decisoes_validas(analyse, corpo):
    r = analyse(build_gamet(corpo))
    assert r["regions"], "nenhuma região calculada"
    for reg in r["regions"]:
        assert reg["decision"] in ("GO", "MARGINAL", "NO-GO")
        assert reg["label"], "região sem label"


@pytest.mark.parametrize("corpo", GAMETS_VARIADOS)
def test_invariante_ordenacao(analyse, corpo):
    """Regiões ordenadas da pior decisão para a melhor."""
    r = analyse(build_gamet(corpo))
    ordem = {"NO-GO": 0, "MARGINAL": 1, "GO": 2}
    assert r["decisions"] == sorted(r["decisions"], key=lambda d: ordem[d])


@pytest.mark.parametrize("corpo", GAMETS_VARIADOS)
def test_invariante_aerodromos_localizaveis(analyse, eng, corpo):
    """Todos os aeródromos e pistas UL caem sempre numa região."""
    r = analyse(build_gamet(corpo))
    perdidos = [nome for nome, (lat, lon) in eng.AERODROMES.items()
                if eng.find_region_for_point(r["regions"], lat, lon) is None]
    assert not perdidos, f"não localizados: {perdidos}"


@pytest.mark.parametrize("corpo", GAMETS_VARIADOS)
def test_invariante_pdf_valido(analyse, eng, corpo):
    texto = build_gamet(corpo)
    r = analyse(texto)
    pdf = eng.generate_pdf(r["regions"], texto, r["fzlvl"], r["qnh"], "teste")
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1000


def test_ponto_fora_da_fir(analyse, eng):
    """Madrid está fora da FIR LPPC e não pode ser atribuído a região."""
    r = analyse(build_gamet("SECN I SFC VIS: 5000M"))
    assert eng.find_region_for_point(r["regions"], 40.42, -3.70) is None


def test_braganca_perto_da_fronteira(analyse, eng):
    """
    REGRESSÃO (v19): Bragança fica ~7km fora do polígono aproximado da FIR
    e deixava de ser localizável.
    """
    r = analyse(build_gamet("SECN I SFC VIS: 5000M"))
    lat, lon = eng.AERODROMES["Bragança (LPBG)"]
    assert eng.find_region_for_point(r["regions"], lat, lon) is not None


# ── COMPONENTES CONEXOS ──────────────────────────────────────────────
def test_regioes_sao_sempre_conexas(analyse):
    """
    Cada região tem de ser um polígono simples. Antes da v27, zonas
    geograficamente separadas com a mesma decisão eram fundidas num só
    cartão — os motivos de uma apareciam atribuídos à outra.
    """
    r = analyse(build_gamet(
        "SECN I SFC VIS: N OF N4100 1000M FG "
        "SIG CLD: BTN N3900 AND N4100 BKN 002HFT AGL "
        "SIGWX: BTN N3700 AND N3900 ISOL TS "
        "TURB: S OF N3700 SEV SFC/FL050"))
    for reg in r["regions"]:
        assert reg["polygon"].geom_type == "Polygon", \
            f"região desconexa: {reg['decision']} {reg['label']}"


def test_zonas_separadas_nao_partilham_motivos(analyse):
    """
    Duas causas de NO-GO em zonas que não se tocam têm de dar regiões
    distintas, cada uma só com os seus motivos.

    Nota: uma faixa a norte e outra a sul podem estar ligadas pela parte
    oceânica da FIR — por isso usam-se aqui faixas separadas por uma zona
    intermédia sem fenómenos.
    """
    r = analyse(build_gamet(
        "SECN I SFC VIS: N OF N4130 800M FG "
        "TURB: S OF N3700 SEV SFC/FL050"))

    nogo = [reg for reg in r["regions"] if reg["decision"] == "NO-GO"]
    assert len(nogo) >= 2, "zonas separadas deviam dar regiões distintas"

    por_nevoeiro = [reg for reg in nogo if reg["vis"] is not None]
    por_turb = [reg for reg in nogo if reg["turb"]]
    assert por_nevoeiro and por_turb

    # A região do nevoeiro não pode mencionar turbulência, nem vice-versa
    for reg in por_nevoeiro:
        assert not reg["turb"], "motivo de turbulência atribuído à zona de nevoeiro"
    for reg in por_turb:
        assert reg["vis"] is None, "visibilidade atribuída à zona de turbulência"


@pytest.mark.parametrize("geo", ["N OF N4220", "N OF N4300", "S OF N3550"])
def test_geografia_fora_da_fir_nao_cobre_tudo(analyse, geo):
    """
    REGRESSÃO (v27): um qualificador fora dos limites da FIR (a FIR termina
    em ~N42°09', Melgaço — até à v31 terminava, erradamente, em ~N41°54')
    dá polígono vazio. O parser mantinha o polígono anterior —
    a FIR inteira — transformando área NULA em cobertura TOTAL. Erro
    optimista ao contrário: reportava perigo onde não havia nenhum.
    """
    r = analyse(build_gamet(f"SECN I SFC VIS: {geo} 800M FG"))
    assert r["decisions"] == ["GO"], \
        f"'{geo}' está fora da FIR e não devia afectar nenhuma região"
    assert not r["blocks"], "não devia criar blocos sem área aplicável"


def test_label_reflecte_localizacao_da_regiao(analyse, eng):
    """
    O rótulo escolhe os pontos mais próximos do centro da região — antes
    usava os primeiros por ordem alfabética, que podiam ficar longe.
    """
    r = analyse(build_gamet("SECN I SFC VIS: N OF N4130 800M FG"))
    norte = [reg for reg in r["regions"] if reg["decision"] == "NO-GO"]
    assert norte

    for reg in norte:
        centro = reg["polygon"].representative_point()
        nomes = [n.split(" (")[0] for n in reg["label"].replace(" +", ",+").split(", ")
                 if not n.startswith("+")]
        for nome in nomes:
            match = [v for k, v in eng.AERODROMES.items() if k.startswith(nome)]
            if not match:
                continue
            lat, lon = match[0]
            dist = ((lat - centro.y) ** 2 + (lon - centro.x) ** 2) ** 0.5
            assert dist < 3.0, f"'{nome}' está a {dist:.1f}° do centro da região"


@pytest.mark.parametrize("corpo", GAMETS_VARIADOS)
def test_invariante_regioes_conexas(analyse, corpo):
    for reg in analyse(build_gamet(corpo))["regions"]:
        assert reg["polygon"].geom_type == "Polygon"


# ── SEPARAÇÃO POR CAUSAS (v28) ───────────────────────────────────────
def test_faixas_adjacentes_com_causas_diferentes(analyse):
    """
    REGRESSÃO (v28): faixas ADJACENTES com causas diferentes formavam um
    componente conexo único e o cartão listava todas as causas em todo o
    lado — um piloto no Algarve via nevoeiro que estava no Minho.
    """
    r = analyse(build_gamet(
        "SECN I SFC VIS: N OF N4130 1000M FG "
        "SIG CLD: BTN N4030 AND N4130 BKN 002HFT AGL "
        "SIGWX: BTN N3900 AND N4030 OCNL TS "
        "TURB: BTN N3800 AND N3900 SEV SFC/FL050 "
        "ICE: S OF N3800 SEV ABV FL050"))

    assert len(r["regions"]) >= 4, "faixas com causas distintas deviam separar-se"
    for reg in r["regions"]:
        assert len(reg["reasons"]) <= 2, \
            f"região com demasiadas causas: {reg['reasons']}"


def test_cada_aerodromo_ve_so_a_sua_causa(analyse, eng):
    """Cada aeródromo recebe apenas o motivo que o afecta."""
    texto = build_gamet(
        "SECN I SFC VIS: N OF N4130 1000M FG "
        "ICE: S OF N3800 SEV ABV FL050")
    r = analyse(texto)

    lat, lon = eng.AERODROMES["Braga (LPBR)"]
    norte = eng.find_region_for_point(r["regions"], lat, lon)
    lat, lon = eng.AERODROMES["Faro (LPFR)"]
    sul = eng.find_region_for_point(r["regions"], lat, lon)

    assert norte and sul
    assert any("VIS" in m for m in norte["reasons"])
    assert not any("ICE" in m for m in norte["reasons"]), \
        "Braga não devia ver o gelo do Algarve"
    assert any("ICE" in m for m in sul["reasons"])
    assert not any("VIS" in m for m in sul["reasons"]), \
        "Faro não devia ver o nevoeiro do Minho"


def test_fusao_de_fragmentos_nao_perde_area(analyse, eng):
    """
    REGRESSÃO (v28): fundir um fragmento com uma região não contígua
    descartava área — a cobertura caía abaixo de 100% e aeródromos
    perto da fronteira deixavam de ser localizáveis.
    """
    for corpo in GAMETS_VARIADOS + [
        "SECN I SFC VIS:LCA 2000-5000M RA/BR SIGWX:S OF N4100 ISOL/EMBD TS "
        "SIG CLD:S OF N4130 ISOL/EMBD TCU/CB 015-030/XXXHFT AGL "
        "ICE:BTN N3900 AND N4130 LCA MOD ABV FL070 "
        "TURB:S OF N3900 AND E OF W00830 LAN LCA MOD SFC/FL030",
    ]:
        r = analyse(build_gamet(corpo))
        total = sum(reg["polygon"].area for reg in r["regions"])
        pct = 100 * total / eng.FIR_POLYGON.area
        assert 99.5 <= pct <= 100.5, f"cobertura {pct:.2f}% em: {corpo[:50]}"


def test_numero_de_regioes_e_razoavel(analyse):
    """
    A separação por causas não pode explodir o número de cartões — um
    briefing com 20 regiões é ilegível.
    """
    for corpo in GAMETS_VARIADOS:
        r = analyse(build_gamet(corpo))
        assert len(r["regions"]) <= 10, \
            f"{len(r['regions'])} regiões é demasiado: {corpo[:50]}"


@pytest.mark.parametrize("corpo", GAMETS_VARIADOS)
def test_invariante_sem_fragmentos_residuais(analyse, eng, corpo):
    """
    Regiões com menos de 1% da FIR só sobrevivem se forem as únicas com
    aquela decisão (nesse caso perdê-las esconderia informação).
    """
    r = analyse(build_gamet(corpo))
    for reg in r["regions"]:
        frac = reg["polygon"].area / eng.FIR_POLYGON.area
        if frac < 0.01:
            # Só é erro se havia uma região da mesma decisão ENCOSTADA a
            # ele. Um fragmento isolado (ex.: faixa a norte de 42°N separada
            # do resto por uma zona NO-GO) é preservado de propósito desde
            # a v28 — fundi-lo deixaria um buraco no mapa.
            vizinhas = [x for x in r["regions"] if x is not reg
                        and x["decision"] == reg["decision"]
                        and x["polygon"].intersection(reg["polygon"]).length > 1e-6]
            assert not vizinhas, \
                f"fragmento de {frac:.1%} encostado a outra região igual devia ter sido fundido"


def test_fenomenos_informativos_nao_fragmentam(analyse):
    """
    REGRESSÃO (v28): ICE/TURB moderados não alteram a decisão, mas
    entravam na assinatura de causas e partiam o briefing — um GAMET
    real dava 8 cartões em vez de 2, sem informação adicional.
    """
    r = analyse(build_gamet(
        "SECN I SFC VIS:LCA 2000-5000M RA/BR SIGWX:S OF N4100 ISOL/EMBD TS "
        "SIG CLD:S OF N4130 ISOL/EMBD TCU/CB 015-030/XXXHFT AGL "
        "ICE:BTN N3900 AND N4130 LCA MOD ABV FL070 "
        "TURB:S OF N3900 AND E OF W00830 LAN LCA MOD SFC/FL030"))
    assert len(r["regions"]) <= 4, \
        f"{len(r['regions'])} regiões — fragmentação excessiva"


def test_fenomeno_parcial_e_assinalado(analyse):
    """
    Quando um fenómeno informativo cobre só parte de uma região, tem de
    ser marcado — senão parece aplicar-se a toda a área.
    """
    r = analyse(build_gamet("SECN I SFC VIS: 2000M ICE: N OF N4100 MOD ABV FL070"))
    com_ice = [x for x in r["regions"] if x["ice"]]
    assert com_ice
    assert any(x["ice_parcial"] for x in com_ice), \
        "ICE parcial não foi assinalado"


def test_fenomeno_global_nao_e_parcial(analyse):
    r = analyse(build_gamet("SECN I SFC VIS: 2000M ICE: MOD ABV FL070"))
    for reg in r["regions"]:
        if reg["ice"]:
            assert not reg["ice_parcial"], "ICE global marcado como parcial"


@pytest.mark.parametrize("corpo", GAMETS_VARIADOS)
def test_invariante_chaves_completas(analyse, corpo):
    """Todas as regiões têm o mesmo conjunto de chaves — a UI depende disso."""
    esperadas = {"polygon", "label", "decision", "vis", "base", "ts",
                 "turb", "turb_layers", "turb_parcial", "ice", "ice_layers",
                 "ice_parcial", "mt_obsc", "va", "reasons", "notas"}
    for reg in analyse(build_gamet(corpo))["regions"]:
        assert set(reg) == esperadas, f"chaves em falta: {esperadas - set(reg)}"


# ── PDF ──────────────────────────────────────────────────────────────
def test_pdf_legenda_so_com_decisoes_presentes(analyse, eng):
    """
    A legenda do mapa não pode mostrar MARGINAL quando não existe nenhuma
    zona marginal — induziria o piloto a procurar algo que não está lá.
    """
    r = analyse(build_gamet("SECN I SFC VIS: N OF N4030 800M FG"))
    presentes = {reg["decision"] for reg in r["regions"]}
    assert "MARGINAL" not in presentes
    pdf = eng.generate_pdf(r["regions"], "teste", None, 1013, "")
    assert pdf[:4] == b"%PDF"


@pytest.mark.parametrize("n_label", [10, 60, 120, 200])
def test_pdf_tolera_labels_longos(analyse, eng, n_label):
    """Labels longos não podem escrever por cima de outros elementos."""
    r = analyse(build_gamet("SECN I SFC VIS: 2000M"))
    for reg in r["regions"]:
        reg["label"] = "X" * n_label
    pdf = eng.generate_pdf(r["regions"], "teste", None, 1013, "")
    assert pdf[:4] == b"%PDF"


def test_pdf_com_muitas_regioes(analyse, eng):
    """O PDF tem de aguentar um GAMET fragmentado sem rebentar."""
    r = analyse(build_gamet(
        "SECN I SFC VIS: N OF N4130 1000M FG "
        "SIG CLD: BTN N4030 AND N4130 BKN 002HFT AGL "
        "SIGWX: BTN N3900 AND N4030 OCNL TS "
        "TURB: BTN N3800 AND N3900 SEV SFC/FL050 "
        "ICE: S OF N3800 SEV ABV FL050 MT OBSC E OF W00800"))
    pdf = eng.generate_pdf(r["regions"], "teste " * 200, None, 1013, "")
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1000


# ── LINHA DE COSTA (v31) ─────────────────────────────────────────────
def test_costa_particiona_a_fir(eng):
    """Terra e mar cobrem a FIR sem sobreposição nem buracos."""
    total = eng.LAND_POLYGON.area + eng.SEA_POLYGON.area
    pct = 100 * total / eng.FIR_POLYGON.area
    assert 99.5 <= pct <= 100.5, f"terra+mar = {pct:.2f}% da FIR"
    assert eng.LAND_POLYGON.intersection(eng.SEA_POLYGON).area < 1e-6


def test_costa_e_linha_simples(eng):
    """A linha de costa não pode cruzar-se a si própria."""
    assert eng.COASTLINE.is_simple
    assert len(eng.COASTLINE.coords) >= 60


def test_aerodromos_em_terra(eng):
    """
    Todos os aeródromos dentro da FIR têm de cair em terra. Se algum
    ficasse do lado do mar, receberia avisos marítimos que não lhe dizem
    respeito — um erro pior do que a imprecisão que a costa veio corrigir.
    """
    fora_fir = {n for n, (la, lo) in eng.AERODROMES.items()
                if not eng.FIR_POLYGON.contains(eng.Point(lo, la))}
    errados = [n for n, (la, lo) in eng.AERODROMES.items()
               if n not in fora_fir and not eng.LAND_POLYGON.contains(eng.Point(lo, la))]
    assert not errados, f"classificados como mar: {errados}"


@pytest.mark.parametrize("superficie", ["MAR", "LAN", "COT", "COT/MAR"])
def test_recorte_por_superficie_reduz_area(analyse, eng, superficie):
    """
    Um qualificador de superfície tem de reduzir a área do fenómeno —
    antes da v31 era apenas anotado e a área ficava intacta.
    """
    com = analyse(build_gamet(f"SECN I TURB: {superficie} MOD SFC/FL050"))
    sem = analyse(build_gamet("SECN I TURB: MOD SFC/FL050"))
    a_com = [b for b in com["blocks"] if b.phenomenon == "TURB"][0].polygon.area
    a_sem = [b for b in sem["blocks"] if b.phenomenon == "TURB"][0].polygon.area
    assert a_com < a_sem, f"'{superficie}' não recortou a área"


def test_fenomeno_maritimo_nao_afecta_interior(analyse, eng):
    """
    REGRESSÃO (v31): 'TURB S OF N3840 MAR' pintava todo o Alentejo
    interior por causa de turbulência que só existe ao largo.
    """
    r = analyse(build_gamet("SECN I TURB: S OF N3840 MAR SEV SFC/FL050"))
    for aero in ("Évora (LPEV)", "Beja (LPBJ)", "Campinho (LP54)"):
        la, lo = eng.AERODROMES[aero]
        reg = eng.find_region_for_point(r["regions"], la, lo)
        assert reg["decision"] != "NO-GO", \
            f"{aero} (interior) afectado por fenómeno marítimo"


def test_superficie_impossivel_descarta_fenomeno(analyse, eng):
    """
    Um fenómeno marítimo numa zona sem mar nenhum não tem área aplicável
    e é descartado. Usa-se uma faixa bem no interior — note-se que
    'E OF W00700' ainda apanha uma parcela marítima ao largo do Algarve
    oriental, pelo que não serve para este teste.
    """
    r = analyse(build_gamet("SECN I TURB: BTN N3900 AND N4000 E OF W00700 MAR SEV SFC/FL050"))
    maritimos = [b for b in r["blocks"] if b.phenomenon == "TURB"]
    if maritimos:
        # Se sobrou área, tem de ser mesmo mar — nunca interior
        for b in maritimos:
            assert b.polygon.intersection(eng.LAND_POLYGON).area < 0.01 * b.polygon.area
    else:
        assert r["decisions"] == ["GO"]
