import streamlit as st
import re
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
st.set_page_config(page_title="LPPC GAMET – VFR", layout="centered")
st.title("✈️ LPPC GAMET – Análise VFR (v2.0 Profissional)")

gamet_text = st.text_area(
    "Cole aqui o texto completo do GAMET (LPPC)",
    height=350
)

# -------------------------------------------------
# FASE 2 – PARSER ROBUSTO
# -------------------------------------------------
def parse_gamet(text):

    data = {
        "visibility": {"min": None},
        "clouds": {"extended_min_base": None},
        "hazards": {"ts": False, "embedded_ts": False, "turbulence": None},
        "freezing_level": {"min": None}
    }

    lines = text.splitlines()
    text_upper = text.upper()

    # ---------------- VISIBILITY (GLOBAL) ----------------
    vis_values = []

    # Ranges tipo 0400-5000M
    ranges = re.findall(r"(\d{4})-(\d{4})M", text_upper)
    for low, _ in ranges:
        vis_values.append(int(low))

    # Valores isolados tipo 3000M
    singles = re.findall(r"\b(\d{4})M\b", text_upper)
    for val in singles:
        vis_values.append(int(val))

    if vis_values:
        data["visibility"]["min"] = min(vis_values)

    # ---------------- CLOUD BASE (BKN / OVC) ----------------
    cloud_bases = []

    for line in lines:
        if "BKN" in line or "OVC" in line:
            # BKN005 ou BKN 005
            matches = re.findall(r"(BKN|OVC)\s?(\d{3})", line)
            for _, base in matches:
                cloud_bases.append(int(base) * 100)

            # ranges 000-006
            ranges = re.findall(r"(\d{3})-(\d{3})", line)
            for low, _ in ranges:
                cloud_bases.append(int(low) * 100)

    if cloud_bases:
        data["clouds"]["extended_min_base"] = min(cloud_bases)

    # ---------------- TS ----------------
    if "TS" in text_upper:
        data["hazards"]["ts"] = True

    if "EMBD TS" in text_upper or "EMBEDDED TS" in text_upper:
        data["hazards"]["embedded_ts"] = True

    # ---------------- TURB ----------------
    for line in lines:
        if "TURB" in line:
            if "SEV" in line:
                data["hazards"]["turbulence"] = "SEV"
            elif "MOD" in line:
                data["hazards"]["turbulence"] = "MOD"

    # ---------------- FREEZING LEVEL ----------------
    fzl = re.findall(r"FZLVL:\s*(\d+)FT", text_upper)
    if fzl:
        data["freezing_level"]["min"] = min([int(x) for x in fzl])

    return data


# -------------------------------------------------
# FASE 3 – MOTOR PROFISSIONAL
# -------------------------------------------------
def vfr_decision(data):

    vis = data["visibility"]["min"]
    base = data["clouds"]["extended_min_base"]
    turb = data["hazards"]["turbulence"]
    ts = data["hazards"]["ts"]
    embd_ts = data["hazards"]["embedded_ts"]
    fzl = data["freezing_level"]["min"]

    # =============================
    # 🔴 HARD LIMITS
    # =============================

    if vis is not None and vis < 3000:
        return "NO-GO", "HARD LIMIT", ["Visibilidade < 3000m"]

    if base is not None and base < 500:
        return "NO-GO", "HARD LIMIT", ["Base de nuvens < 500ft"]

    if embd_ts:
        return "NO-GO", "HARD LIMIT", ["Trovoadas embebidas"]

    # =============================
    # 🟡 SOFT SCORING
    # =============================

    score = 0
    reasons = []

    if vis is not None and 3000 <= vis < 5000:
        score += 40
        reasons.append("Visibilidade 3000–5000m")

    if base is not None and 500 <= base < 1500:
        score += 50
        reasons.append("Base 500–1500ft")

    if ts:
        score += 60
        reasons.append("Trovoadas isoladas")

    if turb == "SEV":
        score += 60
        reasons.append("Turbulência severa")
    elif turb == "MOD":
        score += 35
        reasons.append("Turbulência moderada")

    if fzl is not None and fzl < 4000:
        score += 25
        reasons.append("Freezing level < 4000ft")

    # =============================
    # CLASSIFICAÇÃO FINAL
    # =============================

    if score >= 100:
        decision = "NO-GO"
    elif score >= 50:
        decision = "MARGINAL"
    else:
        decision = "GO"

    return decision, score, reasons


# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------
if st.button("🔍 Analisar GAMET") and gamet_text.strip():

    text = gamet_text.upper()
    parsed = parse_gamet(text)
    decision, score, reasons = vfr_decision(parsed)

    # ---------------- RESULTADO ----------------
    st.subheader("📋 Resultado Global")

    if decision == "NO-GO":
        st.error(f"❌ {decision}")
    elif decision == "MARGINAL":
        st.warning(f"⚠️ {decision} | Score: {score}")
    else:
        st.success(f"✅ {decision} | Score: {score}")

    for r in reasons:
        st.write(f"• {r}")

    st.divider()

    # ---------------- MAPA ----------------
    st.subheader("🗺️ Mapa VFR – Portugal Continental")

    fig, ax = plt.subplots(figsize=(6, 10))

    color_map = {
        "GO": "green",
        "MARGINAL": "orange",
        "NO-GO": "red"
    }

    ZONE_Y = {
        "NORTE": (9.0, 14.0),
        "CENTRO": (4.0, 9.0),
        "SUL": (-4.5, 4.0)
    }

    for z, (y0, y1) in ZONE_Y.items():
        ax.axhspan(y0, y1, color=color_map[decision], alpha=0.18)

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
            Patch(facecolor="green", alpha=0.25, label="GO"),
            Patch(facecolor="orange", alpha=0.25, label="MARGINAL"),
            Patch(facecolor="red", alpha=0.25, label="NO-GO"),
            Line2D([0], [0], marker="o", color="black",
                   linestyle="None", markersize=4, label="Cidade")
        ],
        loc="lower left",
        fontsize=8
    )

    ax.set_xlim(0, 1)
    ax.set_ylim(-4.5, 14.0)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Decisão VFR Profissional")

    st.pyplot(fig)

    st.caption("Ferramenta de apoio à decisão. Não substitui julgamento do piloto.")
