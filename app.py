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
    height=320
)

# -------------------------------------------------
# FUNÇÕES AUXILIARES
# -------------------------------------------------
def extract_latitudes(text):
    lats = re.findall(r'N(\d{2})(\d{2})', text)
    return sorted({int(d) + int(m)/60 for d, m in lats}, reverse=True)

def filter_text_for_zone(text, zone):
    lines = text.splitlines()
    relevant = []

    for line in lines:
        if "N OF" in line or "S OF" in line:
            if zone == "NORTE" and "N OF" in line:
                relevant.append(line)
            elif zone == "SUL" and "S OF" in line:
                relevant.append(line)
            elif zone == "CENTRO":
                relevant.append(line)
        else:
            if zone == "CENTRO":
                relevant.append(line)

    return " ".join(relevant)

# -------------------------------------------------
# EXTRAÇÃO DE DETALHES METEO
# -------------------------------------------------
def extract_details(text):
    details = {}

    # VIS
    vis_range = re.findall(r'(\d{4})-(\d{4})M', text)
    if vis_range:
        details["VIS"] = f"{vis_range[0][0]}–{vis_range[0][1]} m"
    else:
        vis_single = re.findall(r'VIS.*?(\d{4})M', text)
        if vis_single:
            details["VIS"] = f"{vis_single[0]} m"

    # NUVENS (SCT/BKN/OVC)
    cloud = re.findall(r'(SCT|BKN|OVC)\s*(\d{3})-(\d{3})', text)
    if cloud:
        c = cloud[0]
        details["CLD"] = f"{c[0]} {c[1]}–{c[2]} ft AGL"

    # ICE
    ice = re.findall(r'ICE.*?(FL\d{2,3}(?:/FL\d{2,3})?|ABV FL\d{2,3})', text)
    if ice:
        details["ICE"] = ice[0]

    return details

# -------------------------------------------------
# LÓGICA METEO POR ZONA
# -------------------------------------------------
def analyze_zone(text):
    reasons = []

    # ICE por níveis
    ice_match = re.search(r'ICE.*FL(\d{2,3})', text)
    if ice_match:
        fl = int(ice_match.group(1))
        if fl <= 80:
            reasons.append("ICE (LOW LEVEL)")
        else:
            return "MARGINAL", ["ICE ALOFT"]

    # VISIBILIDADE
    vis_match = re.search(r'(\d{4})M', text)
    if vis_match:
        vis = int(vis_match.group(1))
        if vis < 3000:
            reasons.append("VERY LOW VIS")
        elif vis <= 5000:
            return "MARGINAL", ["REDUCED VIS"]

    # CB / TCU
    if "CB" in text or "TCU" in text:
        if "ISOL" in text:
            return "MARGINAL", ["ISOL CB/TCU"]
        else:
            reasons.append("CB/TCU")

    # OUTROS NO-GO
    if "BKN 000" in text or "BKN 00" in text or "OVC" in text:
        reasons.append("LOW CEILING")
    if "MT OBSC" in text:
        reasons.append("MT OBSC")

    if reasons:
        return "NO-GO", reasons

    # TURBULÊNCIA
    if "TURB MOD" in text:
        return "MARGINAL", ["TURB MOD"]

    return "POSSIBLE", []

# -------------------------------------------------
# TEXTO TIPO EXAME
# -------------------------------------------------
def exam_sentence(zone, status):
    zl = zone.lower()
    if status == "NO-GO":
        return t(
            f"O GAMET indica condições adversas no {zl}, incompatíveis com voo VFR.",
            f"The GAMET indicates adverse conditions in the {zl}, incompatible with VFR flight."
        )
    if status == "MARGINAL":
        return t(
            f"O {zl} apresenta condições marginais para voo VFR.",
            f"The {zl} presents marginal conditions for VFR flight."
        )
    return t(
        f"O GAMET indica condições mais favoráveis ao VFR no {zl}.",
        f"The GAMET indicates more favorable VFR conditions in the {zl}."
    )

# -------------------------------------------------
# BOTÃO PRINCIPAL
# -------------------------------------------------
if st.button(t("🔍 Analisar GAMET", "🔍 Analyze GAMET")) and gamet_text.strip():

    text = gamet_text.upper()

    zones = {}
    zone_details = {}

    for zone in ["NORTE", "CENTRO", "SUL"]:
        zone_text = filter_text_for_zone(text, zone)
        zones[zone] = analyze_zone(zone_text)
        zone_details[zone] = extract_details(zone_text)

    # RESULTADO TEXTUAL
    st.subheader(t("📋 Resultado VFR por zona", "📋 VFR result by zone"))

    for zone, (status, reasons) in zones.items():
        if status == "NO-GO":
            st.error(f"{zone}: NO-GO VFR — {', '.join(reasons)}")
        elif status == "MARGINAL":
            st.warning(f"{zone}: VFR marginal")
        else:
            st.success(f"{zone}: VFR possível")

        details = zone_details.get(zone, {})
        for k, v in details.items():
            st.write(f"   • {k}: {v}")

    # CONCLUSÃO
    st.subheader(t("🧠 Conclusão operacional", "🧠 Operational conclusion"))
    for zone, (status, _) in zones.items():
        st.write("• " + exam_sentence(zone, status))

    # -------------------------------------------------
    # MAPA
    # -------------------------------------------------
    st.subheader(t("🗺️ Mapa VFR – LPPC", "🗺️ VFR Map – LPPC"))

    fig, ax = plt.subplots(figsize=(5.5, 8.5))

    ax.plot([-10, -6, -6, -10, -10],
            [36.5, 36.5, 42.5, 42.5, 36.5],
            linewidth=1.5)

    zone_bands = {
        "NORTE": (39.5, 42.5),
        "CENTRO": (38.3, 39.5),
        "SUL": (36.5, 38.3)
    }

    zone_colors = {
        "NO-GO": "red",
        "MARGINAL": "orange",
        "POSSIBLE": "green"
    }

    for zone, (ymin, ymax) in zone_bands.items():
        status, _ = zones[zone]
        ax.axhspan(ymin, ymax, color=zone_colors[status], alpha=0.3)

    for lat in extract_latitudes(text):
        ax.axhline(lat, linestyle="--", color="black", linewidth=1)

    cities = {
        "Porto": (-8.8, 41.1),
        "Bragança": (-7.2, 41.8),
        "Viseu": (-8.0, 40.7),
        "Coimbra": (-8.6, 40.2),
        "Lisboa": (-9.2, 38.8),
        "Évora": (-8.1, 38.6),
        "Faro": (-8.2, 37.1)
    }

    for name, (x, y) in cities.items():
        ax.plot(x, y, "ko", markersize=3)
        ax.text(x + 0.1, y + 0.05, name, fontsize=8)

    legend_patches = [
        mpatches.Patch(color="red", alpha=0.3, label="NO-GO VFR"),
        mpatches.Patch(color="orange", alpha=0.3, label="VFR Marginal"),
        mpatches.Patch(color="green", alpha=0.3, label="VFR Possível")
    ]
    ax.legend(handles=legend_patches, loc="lower right")

    ax.set_xlim(-10.2, -5.8)
    ax.set_ylim(36.3, 42.7)
    ax.set_xticks([])
    ax.set_yticks([])

    st.pyplot(fig)

    st.caption(t(
        "Ferramenta de apoio à decisão. Não substitui o julgamento do piloto.",
        "Decision-support tool. Does not replace pilot judgment."
    ))
