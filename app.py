from shapely.ops import unary_union
import matplotlib.pyplot as plt

st.subheader("🗺️ Validação Visual – Detecção de Gaps")

# União dos sectores
union_sectors = unary_union([
    SECTOR_NORTE_LOWER,
    SECTOR_CENTRO_LOWER,
    SECTOR_SUL_LOWER
])

# Envelope geral
FIR_BOUND = union_sectors.envelope

# Gaps = envelope - união
gaps = FIR_BOUND.difference(union_sectors)

fig, ax = plt.subplots(figsize=(7, 10))

def plot_polygon(poly, color, label, alpha=0.3):
    if poly.is_empty:
        return
    if poly.geom_type == "Polygon":
        x, y = poly.exterior.xy
        ax.fill(x, y, alpha=alpha, label=label)
        ax.plot(x, y)
    elif poly.geom_type == "MultiPolygon":
        for p in poly.geoms:
            x, y = p.exterior.xy
            ax.fill(x, y, alpha=alpha, label=label)
            ax.plot(x, y)

# Plot sectores
plot_polygon(SECTOR_NORTE_LOWER, "blue", "Sector Norte")
plot_polygon(SECTOR_CENTRO_LOWER, "orange", "Sector Centro")
plot_polygon(SECTOR_SUL_LOWER, "green", "Sector Sul")

# Plot gaps a vermelho
if not gaps.is_empty:
    plot_polygon(gaps, "red", "GAPS", alpha=0.6)
    st.error("⚠ Foram detectadas lacunas entre sectores.")
else:
    st.success("✔ Sem lacunas detectadas.")

ax.set_xlim(-11, -6)
ax.set_ylim(35.5, 42.5)

ax.set_xlabel("Longitude (°W)")
ax.set_ylabel("Latitude (°N)")
ax.set_title("FIR Lisboa – Sectores LOWER (Gaps em Vermelho)")
ax.legend()
ax.grid(True, linestyle="--", alpha=0.4)

st.pyplot(fig)
