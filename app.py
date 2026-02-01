import streamlit as st
import re
import matplotlib.pyplot as plt

# -------------------------------------------------
# CONFIGURAÇÃO
# -------------------------------------------------
st.set_page_config(page_title="LPPC GAMET – VFR", layout="centered")
st.title("✈️ LPPC GAMET – Análise VFR")

# -------------------------------------------------
# INPUT
# -------------------------------------------------
gamet_text = st.text_area(
    "Cole aqui o texto completo do GAMET (LPPC)",
    height=330
)

# -------------------------------------------------
# ZONAS (LATITUDES APROXIMADAS)
# -------------------------------------------------
ZONE_BANDS = {
    "NORTE": (39.5, 42.5),
    "CENTRO": (38.5, 39.5),
    "SUL": (36.5, 38.5)
}

PARTIAL_CUTS = {z: [] for z in ZONE_BANDS}

# -------------------------------------------------
# FUNÇÕES ESPACIAIS (INALTERADAS)
# -------------------------------------------------
def line_applies_to_zone(line, zone):
    zmin, zmax = ZONE_BANDS[zone]

    north_of = re.search(r"N OF N(\d{2})(\d{2})", line)
    south_of = re.search(r"S OF N(\d{2})(\d{2})", line)

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
    return " ".join(
        line for line in text.splitlines()
        if line_applies_to_zone(line, zone)
    )

# -------------------------------------------------
# PARSING ROBUSTO (NOVO)
# -------------------------------------------------
def extract_min_visibility(text):
    """
    Devolve a visibilidade mínima encontrada (em metros),
    suportando vários formatos GAMET.
    """
    values = []

    # 0800-5000M → usa o mínimo
    for m in re.findall(r"(\d{4})-(\d{4})M", text):
        values.append(int(m[0]))

    # VIS 3000M
    for m in re.findall(r"VIS\s*(\d{4})M", text):
        values.append(int(m))

    # LOC 1500M
    for m in re.findall(r"LOC\s*(\d{4})M", text):
        values.append(int(m))

    return min(values) if values else None


def extract_min_ceiling(text):
    """
    Devolve o ceiling mais baixo (ft AGL),
    considerando BKN e OVC.
    """
    bases = []

    for m in re.findall(r"(BKN|OVC)\s*(\d{3})", text):
        bases.append(int(m[1]) * 100)

    return min(bases) if bases else None

# -------------------------------------------------
# LÓGICA VFR (RESULTADO FINAL IGUAL AO BASE)
# -------------------------------------------------
def analyze_zone(text):
    reasons = []
    no_go = False

    vis = extract_min_visibility(text)
    cld = extract_min_ceiling(text)

    if vis is not None:
        reasons.append(f"VIS mínima: {vis} m")
        if vis < 3000:
            no_go = True

    if cld is not None:
        reasons.append(f"Ceiling: {cld} ft")
        if cld < 500:
            no_go = True

    if no_go:
        return "NO-GO", reasons

    if not reasons:
        reasons.append("Sem limitações significativas")

    return "VFR POSSÍVEL", reasons

# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------
if st.button("🔍 Analisar GAMET") and gamet_text.strip():

    for z in PARTIAL_CUTS:
        PARTIAL_CUTS[z].clear()

    text = gamet_text.upper()
    zones = {}
    details = {}

    for z in ZONE_BANDS:
        ztext = filter_text_for_zone(text, z)
        zones[z] = analyze_zone(ztext)

    # -------------------------------------------------
    # RESULTADOS TEXTO (MELHORADOS, MESMOS RÓTULOS)
    # -------------------------------------------------
    st.subheader("📋 Resultado VFR por zona")

    for z, (status, reasons) in zones.items():
        if status == "NO-GO":
            st.error(f"{z}: {status}")
        else:
            st.success(f"{z}: {status}")

        for r in reasons:
            st.write(f" • {r}")

    # -------------------------------------------------
    # MAPA ESQUEMÁTICO (INALTERADO)
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

        if status == "VFR POSSÍVEL":
            ax.axhspan(y0, y1, color="green", alpha=0.25)
        elif PARTIAL_CUTS[z]:
            mid = (y0 + y1) / 2
            ax.axhspan(mid, y1, color="red", alpha=0.25)
            ax.axhspan(y0, mid, color="green", alpha=0.25)
            ax.axhline(mid, linestyle="--", color="black")
            ax.text(
                0.5,
                mid + 0.15,
                "Limite VFR / VFR boundary",
                ha="center",
                va="bottom",
                fontsize=8,
                style="italic"
            )
        else:
            ax.axhspan(y0, y1, color="red", alpha=0.25)

    # -------------------------------------------------
    # CIDADES (INALTERADAS)
    # -------------------------------------------------
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
        "Castelo Branco": (0.8, 4.8),
        "Santarém": (0.4, 3.6),
        "Portalegre": (0.8, 2.8),
        "Lisboa": (0.3, 2.0),
        "Setúbal": (0.3, 1.2),
        "Évora": (0.6, 0.2),
        "Beja": (0.7, -1.0),
        "Faro": (0.7, -2.2),
    }

    for name, (x, y) in cities.items():
        ax.plot(x, y, "ko", markersize=3)
        ax.text(x + 0.015, y, name, va="center", fontsize=8)

    ax.set_xlim(0, 1)
    ax.set_ylim(-4.5, 14.0)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Mapa esquemático de orientação (topológico)")

    st.pyplot(fig)

    st.caption("Ferramenta de apoio à decisão. Não substitui o julgamento do piloto.")
