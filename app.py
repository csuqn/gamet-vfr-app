import streamlit as st
import re
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# -------------------------------------------------
# CONFIGURAÇÃO BASE
# -------------------------------------------------
st.set_page_config(page_title="LPPC GAMET – VFR Analysis", layout="centered")

LANG = st.radio("Language / Idioma", ["PT", "EN"], horizontal=True)

def t(pt, en):
    return pt if LANG == "PT" else en

st.title(t("✈️ LPPC GAMET – Análise VFR", "✈️ LPPC GAMET – VFR Analysis"))

# -------------------------------------------------
# INPUT
# -------------------------------------------------
gamet_text = st.text_area(
    t("Cole aqui o texto completo do GAMET (LPPC)",
      "Paste the full GAMET text here (LPPC)"),
    height=330
)

# -------------------------------------------------
# DEFINIÇÃO DAS ZONAS (FAIXAS DE LATITUDE)
# -------------------------------------------------
ZONE_BANDS = {
    "NORTE": (39.5, 42.5),
    "CENTRO": (38.5, 39.5),
    "SUL": (36.5, 38.5)
}

# -------------------------------------------------
# REGISTO DE CORTES PARCIAIS (reset por análise)
# -------------------------------------------------
PARTIAL_CUTS = {
    "NORTE": [],
    "CENTRO": [],
    "SUL": []
}

# -------------------------------------------------
# FUNÇÕES AUXILIARES
# -------------------------------------------------
def extract_latitudes(text):
    lats = re.findall(r'N(\d{2})(\d{2})', text)
    return sorted({int(d) + int(m)/60 for d, m in lats}, reverse=True)

def line_applies_to_zone(line, zone):
    zmin, zmax = ZONE_BANDS[zone]

    north_of = re.search(r'N OF N(\d{2})(\d{2})', line)
    south_of = re.search(r'S OF N(\d{2})(\d{2})', line)

    if north_of:
        lat = int(north_of.group(1)) + int(north_of.group(2)) / 60

        if zmax < lat:
            return False

        if zmin < lat < zmax:
            PARTIAL_CUTS[zone].append(("NORTH", lat))

        return True

    if south_of:
        lat = int(south_of.group(1)) + int(south_of.group(2)) / 60

        if zmin > lat:
            return False

        if zmin < lat < zmax:
            PARTIAL_CUTS[zone].append(("SOUTH", lat))

        return True

    return True

def filter_text_for_zone(text, zone):
    relevant = []
    for line in text.splitlines():
        if line_applies_to_zone(line, zone):
            relevant.append(line)
    return " ".join(relevant)

# -------------------------------------------------
# EXTRAÇÃO DE DETALHES (INFORMATIVO)
# -------------------------------------------------
def extract_details(text):
    details = {}

    vr = re.search(r'(\d{4})-(\d{4})M', text)
    if vr:
        details["VIS"] = f"{vr.group(1)}–{vr.group(2)} m"
    else:
        vs = re.search(r'VIS.*?(\d{4})M', text)
        if vs:
            details["VIS"] = f"{vs.group(1)} m"

    cld = re.search(r'(SCT|BKN|OVC)\s*(\d{3})-(\d{3})', text)
    if cld:
        details["CLD"] = f"{cld.group(1)} {cld.group(2)}–{cld.group(3)} ft AGL"

    ice = re.search(r'ICE.*?(FL\d{2,3}(?:/FL\d{2,3})?|ABV FL\d{2,3})', text)
    if ice:
        details["ICE"] = ice.group(1)

    return details

# -------------------------------------------------
# LÓGICA METEO (PRIORIDADE + WORST CASE)
# -------------------------------------------------
def analyze_zone(text):
    no_go_abs = []
    no_go_cond = []
    marginal = []

    # VIS
    vr = re.search(r'(\d{4})-(\d{4})M', text)
    if vr:
        vis_min = int(vr.group(1))
    else:
        vs = re.search(r'VIS.*?(\d{4})M', text)
        vis_min = int(vs.group(1)) if vs else None

    if vis_min is not None:
        if vis_min < 3000:
            no_go_abs.append("VERY LOW VIS")
        elif vis_min <= 5000:
            marginal.append("REDUCED VIS")

    # TETO
    if re.search(r'BKN 0{2,3}', text) or "OVC" in text:
        no_go_abs.append("LOW CEILING")

    # ICE
    ice = re.search(r'ICE.*FL(\d{2,3})', text)
    if ice:
        fl = int(ice.group(1))
        if fl <= 60:
            no_go_cond.append("ICE (LOW LEVEL)")
        else:
            marginal.append("ICE ALOFT")

    # CB / TCU
    if "CB" in text or "TCU" in text:
        if "ISOL" in text:
            marginal.append("ISOL CB/TCU")
        else:
            no_go_cond.append("CB/TCU")

    # MT OBSC
    if "MT OBSC" in text:
        no_go_abs.append("MT OBSC")

    # DECISÃO FINAL
    if no_go_abs:
        return "NO-GO ABSOLUTO", no_go_abs + no_go_cond
    if no_go_cond:
        return "NO-GO (CONDICIONADO)", no_go_cond
    if marginal:
        return "MARGINAL", marginal
    return "POSSIBLE", []

# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------
if st.button(t("🔍 Analisar GAMET", "🔍 Analyze GAMET")) and gamet_text.strip():

    # reset cortes
    for z in PARTIAL_CUTS:
        PARTIAL_CUTS[z].clear()

    text = gamet_text.upper()
    zones = {}
    details = {}

    for z in ["NORTE", "CENTRO", "SUL"]:
        ztext = filter_text_for_zone(text, z)
        zones[z] = analyze_zone(ztext)
        details[z] = extract_details(ztext)

    st.subheader(t("📋 Resultado VFR por zona", "📋 VFR result by zone"))

    for z, (status, reasons) in zones.items():
        if status.startswith("NO-GO"):
            if PARTIAL_CUTS[z]:
                cut_dir, lat = PARTIAL_CUTS[z][0]
                lat_txt = f"{lat:.1f}N"

                st.error(f"{z}: NO-GO PARCIAL — {', '.join(reasons)}")
                if cut_dir == "NORTH":
                    st.write(f" • NO-GO a norte de {lat_txt}")
                    st.write(f" • VFR possível a sul de {lat_txt}")
                else:
                    st.write(f" • NO-GO a sul de {lat_txt}")
                    st.write(f" • VFR possível a norte de {lat_txt}")
            else:
                st.error(f"{z}: {status} — {', '.join(reasons)}")

        elif status == "MARGINAL":
            st.warning(f"{z}: VFR marginal — {', '.join(reasons)}")

        else:
            st.success(f"{z}: VFR possível")

        for k, v in details[z].items():
            st.write(f"   • {k}: {v}")

    st.caption(t(
        "Ferramenta de apoio à decisão. Não substitui o julgamento do piloto.",
        "Decision-support tool. Does not replace pilot judgment."
    ))
