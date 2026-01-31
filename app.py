import streamlit as st
import re
import matplotlib.pyplot as plt

# ----------------------------
# Configuração básica
# ----------------------------
st.set_page_config(page_title="LPPC GAMET – VFR Analysis", layout="centered")

LANG = st.radio("Language / Idioma", ["PT", "EN"], horizontal=True)

def t(pt, en):
    return pt if LANG == "PT" else en

st.title(t("✈️ LPPC GAMET – Análise VFR", "✈️ LPPC GAMET – VFR Analysis"))

# ----------------------------
# Input
# ----------------------------
gamet_text = st.text_area(
    t("Cole aqui o texto completo do GAMET (LPPC)",
      "Paste the full GAMET text here (LPPC)"),
    height=300
)

# ----------------------------
# Funções de lógica
# ----------------------------
def extract_latitudes(text):
    lats = re.findall(r'N(\d{2})(\d{2})', text)
    return sorted({int(d) + int(m)/60 for d, m in lats}, reverse=True)

def analyze_zone(text):
    reasons = []

    # NO-GO
    if "ICE" in text:
        reasons.append("ICE")
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

    # MARGINAL
    if re.search(r'VIS.*[5-8]\d{3}', text) or "TURB MOD" in text:
        return "MARGINAL", ["LIMITING CONDITIONS"]

    return "POSSIBLE", []

# ----------------------------
# Botão principal
# ----------------------------
if st.button(t("🔍 Analisar GAMET", "🔍 Analyze GAMET")) and gamet_text.strip():

    text = gamet_text.upper()

    zones = {
        "NORTE": analyze_zone(text),
        "CENTRO": analyze_zone(text),
        "SUL": analyze_zone(text)
    }

    st.subheader(t("📋 Resultado VFR", "📋 VFR Summary"))

    for zone, (status, reasons) in zones.items():
        if status == "NO-GO":
            st.error(f"{zone}: NO-GO VFR — {', '.join(reasons)}")
        elif status == "MARGINAL":
            st.warning(f"{zone}: VFR marginal")
        else:
            st.success(f"{zone}: VFR possível")

    # ----------------------------
    # MAPA
    # ----------------------------
    fig, ax = plt.subplots(figsize=(5,8))

    # Retângulo FIR
    ax.plot([-10, -6, -6, -10, -10], [36.5, 36.5, 42.5, 42.5, 36.5])

    # Faixas fixas
    ax.axhspan(39.5, 42.5, alpha=0.3)
    ax.axhspan(38.3, 39.5, alpha=0.2)
    ax.axhspan(36.5, 38.3, alpha=0.1)

    # Linhas de latitude do GAMET
    for lat in extract_latitudes(text):
        ax.axhline(lat, linestyle="--", linewidth=1)

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
        ax.plot(x, y, 'o')
        ax.text(x+0.1, y+0.05, name, fontsize=8)

    ax.set_title(t("Mapa VFR – LPPC", "VFR Map – LPPC"))
    ax.set_xlim(-10.2, -5.8)
    ax.set_ylim(36.3, 42.7)

    st.pyplot(fig)

    st.caption(t(
        "Ferramenta de apoio à decisão. Não substitui o julgamento do piloto.",
        "Decision-support tool. Does not replace pilot judgment."
    ))
