import streamlit as st
import re
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# -------------------------------------------------
# Configuração base
# -------------------------------------------------
st.set_page_config(page_title="LPPC GAMET – VFR Analysis", layout="centered")

LANG = st.radio("Language / Idioma", ["PT", "EN"], horizontal=True)

def t(pt, en):
    return pt if LANG == "PT" else en

st.title(t("✈️ LPPC GAMET – Análise VFR", "✈️ LPPC GAMET – VFR Analysis"))

# -------------------------------------------------
# Input
# -------------------------------------------------
gamet_text = st.text_area(
    t("Cole aqui o texto completo do GAMET (LPPC)",
      "Paste the full GAMET text here (LPPC)"),
    height=320
)

# -------------------------------------------------
# Funções auxiliares
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

def analyze_zone(text):
    reasons = []

    # --- NO-GO ---
    ice_match = re.search(r'ICE.*FL(\d{2,3})', text)
if ice_match:
    fl = int(ice_match.group(1))
    if fl <= 80:
        reasons.append("ICE (LOW LEVEL)")
    else:
        return "MARGINAL", ["ICE ALOFT"]

    if "BKN 000" in text or "BKN 00" in text or "OVC" in text:
        reasons.append("LOW CEILING")
    if re.search(r'VIS.*0[0-4]\d{2}', text):
        reasons.append("LOW VIS")
    if "CB" in text or "TCU" in text:
        reasons.append("CB/TCU")
    if "MT OBSC" in text:
        reasons.append("MT OBSC")

    if reasons:
        return "NO-GO", reasons

    # --- MARGINAL ---
    if re.search(r'VIS.*[5-8]\d{3}', text) or "TURB MOD" in text:
        return "MARGINAL", ["LIMITING CONDITIONS"]

    return "POSSIBLE", []

# -------------------------------------------------
# Botão principal
# -------------------------------------------------
if st.button(t("🔍 Analisar GAMET", "🔍 Analyze GAMET")) and gamet_text.strip():

    text = gamet_text.upper()

    zones = {}
    for zone in ["NORTE", "CENTRO", "SUL"]:
        zone_text = filter_text_for_zone(text, zone)
        zones[zone] = analyze_zone(zone_text)

    # -------------------------------------------------
    # Resultado textual por zona
    # -------------------------------------------------
    st.subheader(t("📋 Resultado VFR por zona", "📋 VFR result by zone"))

    for zone, (status, reasons) in zones.items():
        if status == "NO-GO":
            st.error(f"{zone}: NO-GO VFR — {', '.join(reasons)}")
        elif status == "MARGINAL":
            st.warning(f"{zone}: VFR marginal")
        else:
            st.success(f"{zone}: VFR possível")

    # -------------------------------------------------
    # Conclusão tipo exame
    # -------------------------------------------------
    st.subheader(t("🧠 Conclusão operacional", "🧠 Operational conclusion"))

    def exam_sentence(zone, status):
        zl = zone.lower()
        if status == "NO-GO":
            return t(
                f"No {zl}, as condições são incompatíveis com voo VFR.",
                f"In the {zl}, conditions are incompatible with VFR flight."
            )
        if status == "MARGINAL":
            return t(
                f"O {zl} apresenta condições marginais para VFR.",
                f"The {zl} presents marginal VFR conditions."
            )
        return t(
            f"No {zl}, o voo VFR pode ser considerado.",
            f"In the {zl}, VFR flight may be considered."
        )

    for zone, (status, _) in zones.items():
        st.write("• " + exam_sentence(zone, status))

    # -------------------------------------------------
    # MAPA
    # -------------------------------------------------
    st.subheader(t("🗺️ Mapa VFR – LPPC", "🗺️ VFR Map – LPPC"))

    fig, ax = plt.subplots(figsize=(5.5, 8.5))

    # Retângulo FIR
    ax.plot([-10, -6, -6, -10, -10],
            [36.5, 36.5, 42.5, 42.5, 36.5],
            linewidth=1.5)

    # Faixas fixas
    ax.axhspan(39.5, 42.5, alpha=0.3, color="red")
    ax.axhspan(38.3, 39.5, alpha=0.3, color="orange")
    ax.axhspan(36.5, 38.3, alpha=0.3, color="green")

    # Linhas de latitude do GAMET
    for lat in extract_latitudes(text):
        ax.axhline(lat, linestyle="--", linewidth=1, color="black")

    # Cidades
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
        ax.plot(x, y, 'ko', markersize=3)
        ax.text(x + 0.1, y + 0.05, name, fontsize=8)

    # Legenda
    legend_patches = [
        mpatches.Patch(color='red', alpha=0.3, label='NO-GO VFR'),
        mpatches.Patch(color='orange', alpha=0.3, label='VFR Marginal'),
        mpatches.Patch(color='green', alpha=0.3, label='VFR Possível')
    ]
    ax.legend(handles=legend_patches, loc="lower right")

    ax.set_xlim(-10.2, -5.8)
    ax.set_ylim(36.3, 42.7)
    ax.set_xticks([])
    ax.set_yticks([])

    st.pyplot(fig)

    # Rodapé
    st.caption(t(
        "Ferramenta de apoio à decisão. Não substitui o julgamento do piloto.",
        "Decision-support tool. Does not replace pilot judgment."
    ))
