import streamlit as st
import re
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# -------------------------------------------------
# CONFIGURAÇÃO
# -------------------------------------------------
st.set_page_config(page_title="LPPC GAMET – VFR", layout="centered")

col1, col2 = st.columns([0.95, 0.05])

with col1:
    st.title("✈️ LPPC GAMET – Análise VFR")

with col2:
    st.markdown(
        """
        <span title="
        VIS < 3000 m ⇒ NO-GO global
        BKN/OVC < 500 ft ⇒ NO-GO (modo strict)
        Parsing extended é apenas informativo
        Decisão conservadora
        Não substitui julgamento do piloto
        ">
        ℹ️
        </span>
        """,
        unsafe_allow_html=True
    )

# -------------------------------------------------
# INPUT
# -------------------------------------------------
gamet_text = st.text_area(
    "Cole aqui o texto completo do GAMET (LPPC)",
    height=330
)

# -------------------------------------------------
# ZONAS
# -------------------------------------------------
ZONE_BANDS = {
    "NORTE": (39.5, 42.5),
    "CENTRO": (38.5, 39.5),
    "SUL": (36.5, 38.5)
}

# -------------------------------------------------
# PARSING VISIBILIDADE
# -------------------------------------------------
def extract_min_visibility(text):
    values = []
    context = []

    for line in text.splitlines():
        if "VIS" not in line:
            continue

        if "SFC" in line:
            context.append("SFC")
        if "LCA" in line:
            context.append("LCA")

        matches = re.findall(r"(\d{4})-(\d{4})M", line)
        for low, _ in matches:
            values.append(int(low))

    ctx = ", ".join(sorted(set(context))) if context else None
    return (min(values), ctx) if values else (None, None)

# -------------------------------------------------
# CLOUD BASE STRICT (linhas CLD apenas)
# -------------------------------------------------
def extract_min_cloud_base(text):
    bases = []

    for line in text.splitlines():
        if "CLD" in line:
            matches = re.findall(r"(\d{3})-(\d{3})", line)
            for low, _ in matches:
                bases.append(int(low) * 100)

    return min(bases) if bases else None

# -------------------------------------------------
# CLOUD BASE EXTENDED (qualquer BKN/OVC no texto)
# -------------------------------------------------
def extract_cloud_base_extended(text):
    bases = []

    for line in text.splitlines():
        if "BKN" in line or "OVC" in line:
            matches = re.findall(r"(\d{3})-(\d{3})", line)
            for low, _ in matches:
                bases.append(int(low) * 100)

    return min(bases) if bases else None

# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------
if st.button("🔍 Analisar GAMET") and gamet_text.strip():

    text = gamet_text.upper()
    zones = {}

    global_vis, vis_context = extract_min_visibility(text)
    cloud_strict = extract_min_cloud_base(text)
    cloud_extended = extract_cloud_base_extended(text)

    # -------------------------------------------------
    # REGRA VISIBILIDADE
    # -------------------------------------------------
    if global_vis is not None and global_vis < 3000:

        for z in ZONE_BANDS:
            reasons = [
                f"Visibilidade mínima: {global_vis} m" +
                (f" ({vis_context})" if vis_context else "")
            ]

            if cloud_strict:
                reasons.append(f"Base das nuvens (CLD): {cloud_strict} ft")

            zones[z] = ("NO-GO", reasons, ["VIS < 3000 m"])

    # -------------------------------------------------
    # SEM VIS LIMITANTE
    # -------------------------------------------------
    else:
        for z in ZONE_BANDS:
            reasons = []
            limiting = []

            if cloud_strict:
                reasons.append(f"Base das nuvens (CLD): {cloud_strict} ft")

                if cloud_strict < 500:
                    limiting.append("Base das nuvens < 500 ft")

            if limiting:
                zones[z] = ("NO-GO", reasons, limiting)
            else:
                zones[z] = (
                    "VFR POSSÍVEL",
                    reasons if reasons else ["Sem limitações VFR identificadas"],
                    []
                )

    # -------------------------------------------------
    # RESULTADOS
    # -------------------------------------------------
    st.subheader("📋 Resultado VFR por zona")

    for z, (status, reasons, limiting) in zones.items():
        if status == "NO-GO":
            st.error(f"{z}: NO-GO")
        else:
            st.success(f"{z}: VFR POSSÍVEL")

        for r in reasons:
            st.write(f" • {r}")

        if limiting:
            st.write(f" • Critério limitante: {limiting[0]}")

    # -------------------------------------------------
    # AVISO VISUAL (Extended inferior ao Strict)
    # -------------------------------------------------
    if cloud_extended is not None:
        if cloud_strict is None or cloud_extended < cloud_strict:
            st.warning(
                f"⚠️ Base adicional detetada fora das linhas CLD: {cloud_extended} ft."
            )

    # -------------------------------------------------
    # MAPA ESQUEMÁTICO
    # -------------------------------------------------
    st.subheader("🗺️ Mapa VFR – Portugal Continental (esquemático)")

    fig, ax = plt.subplots(figsize=(6, 10))

    ZONE_Y = {
        "NORTE": (9.0, 14.0),
        "CENTRO": (4.0, 9.0),
        "SUL": (-4.5, 4.0)
    }

    for z, (y0, y1) in ZONE_Y.items():
        status = zones[z][0]
        color = "green" if status == "VFR POSSÍVEL" else "red"
        ax.axhspan(y0, y1, color=color, alpha=0.25)

    cities = {
        "Bragança": (0.8, 13.5),
        "Viana do Castelo": (0.2, 12.6),
        "Braga": (0.4, 11.8),
        "Vila Real": (0.6, 11.0),
        "Porto": (0.3, 10.5),
        "Viseu": (0.6, 8.6),
        "Aveiro": (0.3, 8.0),
        "Guarda": (0.8, 7.4),
        "Coimbra": (0.5, 6.6),
        "Leiria": (0.3, 5.6),
        "Castelo Branco": (0.8, 5.9),
        "Santarém": (0.4, 3.0),
        "Portalegre": (0.8, 3.0),
        "Lisboa": (0.3, 2.0),
        "Setúbal": (0.3, 1.2),
        "Évora": (0.6, 0.2),
        "Beja": (0.7, -1.0),
        "Faro": (0.7, -2.2),
    }

    for name, (x, y) in cities.items():
        ax.plot(x, y, "ko", markersize=3)
        ax.text(x + 0.015, y, name, va="center", fontsize=8)

    ax.legend(
        handles=[
            Patch(facecolor="red", alpha=0.25, label="🟥 NO-GO"),
            Patch(facecolor="green", alpha=0.25, label="🟩 VFR POSSÍVEL"),
            Line2D([0], [0], linestyle="--", color="black",
                   label="Limite aproximado GAMET"),
        ],
        loc="lower left",
        fontsize=8
    )

    ax.set_xlim(0, 1)
    ax.set_ylim(-4.5, 14.0)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Mapa esquemático de decisão VFR")

    st.pyplot(fig)

    st.caption("Ferramenta de apoio à decisão. Não substitui o julgamento do piloto.")
