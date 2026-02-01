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
# ZONAS
# -------------------------------------------------
ZONE_BANDS = {
    "NORTE": (39.5, 42.5),
    "CENTRO": (38.5, 39.5),
    "SUL": (36.5, 38.5)
}

PARTIAL_CUTS = {z: [] for z in ZONE_BANDS}

# -------------------------------------------------
# FUNÇÕES ESPACIAIS
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
# PARSING
# -------------------------------------------------
def extract_min_visibility(text):
    values = []

    for m in re.findall(r"(\d{4})-(\d{4})M", text):
        values.append(int(m[0]))

    for m in re.findall(r"VIS\s*(\d{4})M", text):
        values.append(int(m))

    for m in re.findall(r"LOC\s*(\d{4})M", text):
        values.append(int(m))

    return min(values) if values else None


def extract_min_cloud_base(text):
    """
    Devolve a base de nuvens mais baixa como:
    (tipo_nuvem, base_em_ft)
    """
    clouds = []

    for m in re.findall(r"(BKN|OVC)\s*(\d{3})", text):
        cloud_type = m[0]
        base_ft = int(m[1]) * 100
        clouds.append((cloud_type, base_ft))

    if not clouds:
        return None

    return min(clouds, key=lambda x: x[1])

# -------------------------------------------------
# LÓGICA VFR
# -------------------------------------------------
def analyze_zone(text):
    reasons = []
    limiting = []
    no_go = False

    vis = extract_min_visibility(text)
    cloud_base = extract_min_cloud_base(text)

    if vis is not None:
        reasons.append(f"VIS: {vis} m")
        if vis < 3000:
            limiting.append("VIS < 3000 m")
            no_go = True

    if cloud_base is not None:
        cloud_type, base_ft = cloud_base
        reasons.append(f"BASE DAS NUVENS: {cloud_type} {base_ft} ft")
        if base_ft < 500:
            limiting.append("Base das nuvens < 500 ft")
            no_go = True

    if no_go:
        return "NO-GO", reasons, limiting

    if not reasons:
        reasons.append("Sem limitações significativas")

    return "VFR POSSÍVEL", reasons, []

# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------
if st.button("🔍 Analisar GAMET") and gamet_text.strip():

    for z in PARTIAL_CUTS:
        PARTIAL_CUTS[z].clear()

    text = gamet_text.upper()
    zones = {}

    for z in ZONE_BANDS:
        ztext = filter_text_for_zone(text, z)
        zones[z] = analyze_zone(ztext)

    # -------------------------------------------------
    # RESULTADOS TEXTO
    # -------------------------------------------------
    st.subheader("📋 Resultado VFR por zona")

    for z, (status, reasons, limiting) in zones.items():

        if status == "NO-GO" and PARTIAL_CUTS[z]:
            cut_dir, lat = PARTIAL_CUTS[z][0]
            st.error(f"{z}: NO-GO PARCIAL")

            st.write(f" • NO-GO a {'norte' if cut_dir=='NORTH' else 'sul'} de {lat:.1f}N")
            for r in reasons:
                st.write(f"    – {r}")
            if limiting:
                st.write(f"   Critério limitante: {limiting[0]}")
            st.write(f" • VFR possível a {'sul' if cut_dir=='NORTH' else 'norte'} de {lat:.1f}N")

        elif status == "NO-GO":
            st.error(f"{z}: NO-GO")
            for r in reasons:
                st.write(f" • {r}")
            if limiting:
                st.write(f" • Critério limitante: {limiting[0]}")

        else:
            st.success(f"{z}: VFR POSSÍVEL")
            for r in reasons:
                st.write(f" • {r}")

    # -------------------------------------------------
    # RESUMO GLOBAL
    # -------------------------------------------------
    st.subheader("🧭 Resumo global")

    for z, (status, *_ ) in zones.items():
        label = status
        if status == "NO-GO" and PARTIAL_CUTS[z]:
            label = "NO-GO PARCIAL"
        st.write(f" • {z}: {label}")

    # -------------------------------------------------
    # MAPA (INALTERADO)
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
                0.5, mid + 0.15,
                "Limite VFR / VFR boundary",
                ha="center", va="bottom", fontsize=8, style="italic"
            )
        else:
            ax.axhspan(y0, y1, color="red", alpha=0.25)

    # CIDADES (baseline)
    cities = {
        "Bragança":         (0.8, 13.5),
        "Viana do Castelo": (0.2, 12.6),
        "Braga":            (0.4, 11.8),
        "Vila Real":        (0.6, 11.0),
        "Porto":            (0.3, 10.5),
        "Viseu":            (0.6, 8.6),
        "Aveiro":           (0.3, 8.0),
        "Guarda":           (0.8, 7.4),
        "Coimbra":          (0.5, 6.6),
        "Leiria":           (0.3, 5.6),
        "Castelo Branco":   (0.8, 4.8),
        "Santarém":         (0.4, 3.6),
        "Portalegre":       (0.8, 2.8),
        "Lisboa":           (0.3, 2.0),
        "Setúbal":          (0.3, 1.2),
        "Évora":            (0.6, 0.2),
        "Beja":             (0.7, -1.0),
        "Faro":             (0.7, -2.2),
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

