"""
LPPC GAMET — protótipo da interface em NiceGUI.

Corre em paralelo com a app Streamlit (app.py), que continua a ser a app
publicada. O motor é o MESMO (ver motor.py); aqui só muda a interface.

    pip install -r nicegui_app/requirements.txt
    python nicegui_app/main.py          # http://localhost:8080
"""
import json
import os
import re
from datetime import datetime, timezone

from nicegui import app, run, ui

from motor import M, APP

_SRC = APP.read_text(encoding="utf-8")
# O mesmo CSS e a mesma legenda da app Streamlit (uma só fonte)
_CSS = re.search(r'_CSS = """\n<style>\n(.*?)</style>\n"""', _SRC, re.S).group(1)
_LEGENDA = re.search(r'st\.markdown\("""\n(### 📐 Referência técnica.*?)"""\)', _SRC, re.S).group(1)

_EXTRA_CSS = """
body { background:#0E151C; color:#E6EDF3; }
.nicegui-content { max-width: 1100px; margin: 0 auto; padding: 12px 16px 48px; gap: 10px; }
.gv-alerta { border-radius:12px; padding:12px 14px; font-size:14px; line-height:1.5; border:1px solid; }
.gv-alerta code { white-space: pre-wrap; word-break: break-word; font-size:12px; }
.gv-erro  { background:#3A1414; border-color:#7A2A26; color:#FBD5D1; }
.gv-aviso { background:#3D3110; border-color:#7A6420; color:#F8E4B0; }
.gv-info  { background:#16314A; border-color:#2C5A82; color:#D3E8FA; }
.gv-sec { font-family:'IBM Plex Mono',monospace; font-size:12px; letter-spacing:.1em; color:#8FA3B5;
          font-weight:600; margin-top:8px; }
.q-tab { min-height: 44px; }
.q-tabs { border-bottom: 1px solid #22303C; }
.gv-txt { font-family:'IBM Plex Mono',monospace; font-size:12.5px; white-space:pre-wrap;
          word-break:break-word; background:#15202A; border:1px solid #22303C; border-radius:12px; padding:12px; }
.q-field__native, .q-field__input { color:#E6EDF3 !important; }
.leaflet-tooltip.gv-lbl { background: rgba(14,21,28,.85); color:#E6EDF3; border:0; box-shadow:none;
  font-family:'IBM Plex Mono',monospace; font-size:10px; padding:0 4px; border-radius:3px; }
.leaflet-tooltip.gv-lbl::before { display:none; }
.gv-zoom-lo .leaflet-tooltip.gv-lbl { display:none; }
"""


def _md(txt):
    """**negrito** e `código` → HTML (o resto escapado)."""
    t = M._e(txt)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t.replace("\n", "<br>")


# ---------------------------------------------------------------------
# Análise — mesma lógica da secção # EXECUÇÃO da app Streamlit, sem UI.
# (Numa migração a sério esta função passaria para o motor, e as duas
# interfaces usavam-na; no protótipo fica aqui.)
# ---------------------------------------------------------------------
def analisar(texto, fonte, boletins=None, boletins_at=None, boletins_fonte="",
             indice=None, entrada=None):
    agora = datetime.now(timezone.utc)
    r = {"alertas": [], "texto": texto}
    ini, fim, activo = M.parse_validity(texto)
    r["validity_label"] = ""
    r["faixa_val"], r["faixa_exp"] = "—", "—"
    if ini and fim:
        r["validity_label"] = f"Válido: {ini:%d/%H%MZ} – {fim:%d/%H%MZ}"
        r["faixa_val"] = f"{ini:%d} {ini:%H}–{fim:%H}Z"
        if activo:
            mins = max(0, int((fim - agora).total_seconds() // 60))
            h, m = divmod(mins, 60)
            r["faixa_exp"] = f"{h}h{m:02d}m" if h else f"{m} min"
            if mins <= 30:
                r["alertas"].append(("aviso", f"⏳ O GAMET expira em **{r['faixa_exp']}** — o próximo está prestes a ser emitido."))
        else:
            r["faixa_exp"] = "EXPIRADO" if fim <= agora else "AINDA NÃO"
            r["alertas"].append(("aviso", f"⏱️ {r['validity_label']} — **FORA DO PERÍODO DE VALIDADE**."))
    blocks, fz, qnh, wind = M.parse_gamet(texto)
    regioes = M.compute_dynamic_regions(blocks)
    has_sig, sig_txt = M.extract_sigmet_applicable(texto)

    if fonte == "arquivo_hist":
        r["alertas"].append(("aviso", "📚 **GAMET DO ARQUIVO — não é o GAMET actual.** Serve para rever uma situação passada; não o uses para planear um voo."))
    elif fonte == "arquivo_recurso":
        r["alertas"].append(("aviso", "🕓 **O IPMA ainda não publicou o novo GAMET** (o anterior é retirado cerca de 45 min antes da emissão). A mostrar o **último GAMET arquivado, ainda em vigor**."))

    sig, air, verificado, onde = [], [], False, ""
    if fonte in ("ipma", "arquivo_recurso") and boletins is not None:
        sig, air = M.active_bulletins(boletins)
        verificado, onde = True, ("em vigor no IPMA" if fonte == "ipma" else f"em vigor ({boletins_fonte})")
    elif fonte == "arquivo_hist" and indice:
        sig, air = M.boletins_do_periodo(indice, M._iso_utc(entrada.get("inicio")), M._iso_utc(entrada.get("fim")))
        verificado, onde = True, "durante a validade deste GAMET (arquivo)"
    if sig:
        regioes = M.apply_sigmet_override(regioes, " | ".join(b[:80] for b in sig))
        r["alertas"].append(("erro", f"🚨 **{len(sig)} SIGMET {onde}**"
                             + ("" if has_sig else " — **não referido no GAMET**")
                             + ". Decisão forçada a NO-GO em toda a área. Lê o SIGMET completo:\n"
                             + "\n".join(f"`{b}`" for b in sig)))
    if air:
        r["alertas"].append(("aviso", f"⚠️ **{len(air)} AIRMET {onde}** (mostrado, não interpretado):\n"
                             + "\n".join(f"`{b}`" for b in air)))
    if not verificado:
        r["alertas"].append(("info", "ℹ️ SIGMETs do IPMA **não verificados**: só conta o campo \"SIGMET APPLICABLE\" do próprio GAMET."))
    if has_sig:
        regioes = M.apply_sigmet_override(regioes, sig_txt)
        r["alertas"].append(("erro", f"🚨 **SIGMET ACTIVO APLICÁVEL A ESTE GAMET.** Decisão forçada a NO-GO em toda a área.\nTexto reportado: {sig_txt}"))
    if M.looks_unparseable(texto):
        r["alertas"].append(("erro", "⚠️ **Nenhum campo meteorológico reconhecido no texto** — isto **não** quer dizer que está calmo. Confirma o GAMET."))
    ww = M.check_strong_wind(wind)
    if ww:
        r["alertas"].append(("aviso", "💨 **Vento forte a 1000ft AGL** (aviso geral, não altera a decisão):\n" + "\n".join(ww)))

    if has_sig or sig:
        r["faixa_sig"] = ("ACTIVO", "NO-GO")
    elif verificado:
        r["faixa_sig"] = ("NIL", "GO")
    else:
        r["faixa_sig"] = ("N/VERIF.", None)

    area = M.FIR_POLYGON.area
    por_dec = {}
    for g in regioes:
        por_dec[g["decision"]] = por_dec.get(g["decision"], 0) + g["polygon"].area
    r.update(regioes=regioes, por_dec=por_dec, area=area, fz=fz, qnh=qnh, wind=wind,
             ini=ini)
    return r


def obter_gamet_actual():
    """IPMA; se não houver GAMET publicado, o último em vigor do arquivo."""
    ok, res = M.fetch_gamet_ipma("")
    if ok:
        return dict(texto=res, fonte="ipma",
                    boletins=M.extract_bulletins_from_html(M._IPMA_LAST["raw"]),
                    boletins_at=M._IPMA_LAST["at"], boletins_fonte="página do IPMA", erro=None)
    pagina = M.extract_bulletins_from_html(M._IPMA_LAST["sem_gamet"])
    txt, info, arq = M.gamet_de_recurso(M.fetch_arquivo_indice, M.fetch_arquivo)
    if txt:
        return dict(texto=txt, fonte="arquivo_recurso", boletins=arq + [b for b in pagina if b not in arq],
                    boletins_at=datetime.now(timezone.utc),
                    boletins_fonte="página do IPMA + arquivo" if pagina else "arquivo", erro=res)
    return dict(texto="", fonte=None, boletins=None, boletins_at=None, boletins_fonte="",
                erro=f"{res}\n\nArquivo: {info}.")


# ---------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------
@ui.page("/")
async def pagina():
    ui.add_head_html('<meta name="theme-color" content="#0E151C">'
                     f"<style>{_CSS}{_EXTRA_CSS}</style>")
    ui.dark_mode(True)
    ui.colors(primary="#7CC4FF", dark="#0E151C", dark_page="#0E151C")

    estado = {"aerodromo": app.storage.user.get("aerodromo") if _STORAGE else None}

    ui.html('<div class="gv-head"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" '
            'stroke="#7CC4FF" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
            'aria-hidden="true"><path d="M2 16l20-6-20-6 4 6-4 6z"></path><path d="M6 10h8"></path></svg>'
            f'<div><b>LPPC GAMET</b><small>BRIEFING VFR · v{M.APP_VERSION} · NICEGUI (PROTÓTIPO)</small></div></div>'
            ).classes("w-full")

    briefing = ui.column().classes("w-full gap-3")
    with briefing:
        ui.spinner(size="lg", color="primary")
        ui.label("A carregar o GAMET…").classes("gv-k")

    def desenhar(r):
        briefing.clear()
        with briefing:
            ui.html(M.html_faixa(r["faixa_val"], r["faixa_exp"], *r["faixa_sig"])).classes("w-full")
            for tipo, txt in r["alertas"]:
                ui.html(f'<div class="gv-alerta gv-{tipo}">{_md(txt)}</div>').classes("w-full")
            ui.html(M.html_veredicto(r["por_dec"], r["area"])).classes("w-full")

            opcoes = sorted(M.AERODROMES.keys())
            res_ad = ui.html("").classes("w-full")

            def mostrar_ad(nome):
                estado["aerodromo"] = nome
                if _STORAGE:
                    app.storage.user["aerodromo"] = nome
                if nome:
                    la, lo = M.AERODROMES[nome]
                    res_ad.set_content(M.html_aerodromo(nome, M.find_region_for_point(r["regioes"], la, lo)))
                else:
                    res_ad.set_content("")

            ui.select(opcoes, label="O meu aeródromo", with_input=True, clearable=True,
                      value=estado["aerodromo"] if estado["aerodromo"] in opcoes else None,
                      on_change=lambda e: mostrar_ad(e.value)).classes("w-full").props("dark outlined")
            res_ad.move(target_index=-1)
            mostrar_ad(estado["aerodromo"] if estado["aerodromo"] in opcoes else None)

            ui.label(f"BRIEFING POR REGIÕES · {len(r['regioes'])}").classes("gv-sec")
            cartoes = "".join(
                M.html_regiao(g, 100 * g["polygon"].area / r["area"],
                              M.annotate_window_notes(g.get("notas"), r["ini"]))
                for g in r["regioes"])
            ui.html(f'<div class="gv-regioes">{cartoes}</div>').classes("w-full")

            with ui.tabs().classes("w-full").props("dense align=left active-color=primary indicator-color=primary no-caps") as tabs:
                t_mapa = ui.tab("Mapa")
                t_vento = ui.tab("Vento/Temp")
                t_s2 = ui.tab("Secção II")
                t_txt = ui.tab("Texto GAMET")
                t_leg = ui.tab("Legenda")
            with ui.tab_panels(tabs, value=t_mapa).classes("w-full").style("background:transparent"):
                with ui.tab_panel(t_mapa).classes("p-0"):
                    m = ui.leaflet(center=(39.6, -8.2), zoom=6).classes("w-full").style(
                        "height:460px;border-radius:14px;border:1px solid #22303C")
                    for g in r["regioes"]:
                        cor = M._DEC_BARRA.get(g["decision"], "#888")
                        geoms = g["polygon"].geoms if hasattr(g["polygon"], "geoms") else [g["polygon"]]
                        dica = f"{g['label']}: {g['decision']}" + (f" — {'; '.join(g['reasons'])}" if g["reasons"] else "")
                        for p in geoms:
                            if p.is_empty or getattr(p, "exterior", None) is None:
                                continue
                            camada = m.generic_layer(name="polygon", args=[
                                [[la, lo] for lo, la in p.exterior.coords],
                                {"color": cor, "fillColor": cor, "fillOpacity": 0.35, "weight": 2}])
                            camada.run_method("bindTooltip", dica)
                    # Aeródromos (círculo escuro) e pistas de ultraleves (círculo
                    # branco), com nome e designador sempre visíveis a partir do
                    # zoom 9 (mais longe sobrepunham-se). Criados de uma vez em
                    # JavaScript — os tooltips permanentes não passavam pelo
                    # run_method da camada genérica.
                    pontos = [[la, lo, nome, nome in M.ULTRALIGHT_STRIPS]
                              for nome, (la, lo) in M.AERODROMES.items()]
                    m.run_map_method("fitBounds", [[36.9, -9.9], [42.2, -6.1]])
                    ui.run_javascript(f"""
                        const pts = {json.dumps(pontos)};
                        const go = () => {{
                          const el = getElement({m.id});
                          if (!el || !el.map || !window.L) return setTimeout(go, 200);
                          const map = el.map;
                          for (const [la, lo, nome, ul] of pts) {{
                            L.circleMarker([la, lo], {{radius: ul ? 3 : 4, weight: 1.5, color: '#0E151C',
                              fillColor: ul ? '#FFFFFF' : '#0E151C', fillOpacity: 1}})
                             .bindTooltip(nome, {{permanent: true, direction: 'right', offset: [6, 0],
                              className: 'gv-lbl'}})
                             .addTo(map);
                          }}
                          const upd = () => map.getContainer().classList.toggle('gv-zoom-lo', map.getZoom() < 9);
                          map.on('zoomend', upd); upd();
                        }};
                        go();""")
                with ui.tab_panel(t_vento).classes("p-0"):
                    if r["wind"]:
                        cols = [{"name": "n", "label": "Nível", "field": "n", "align": "left"}] + [
                            {"name": s["station"], "label": s["station"], "field": s["station"], "align": "left"}
                            for s in r["wind"]]
                        linhas = []
                        for lvl in M._WIND_LEVELS:
                            lin = {"n": lvl}
                            for s in r["wind"]:
                                e = s["levels"].get(lvl)
                                lin[s["station"]] = (f"{e['dir']:03d}°/{e['spd']:03d}kt "
                                                     f"{'+' if e['temp'] >= 0 else ''}{e['temp']}°C") if e else "—"
                            linhas.append(lin)
                        ui.table(columns=cols, rows=linhas).classes("w-full").props("dark flat dense")
                    else:
                        ui.label("Este GAMET não traz vento e temperatura por níveis.").classes("gv-k")
                with ui.tab_panel(t_s2).classes("p-0"):
                    q = f"{r['qnh']} hPa" if r["qnh"] else "—"
                    z = f"{r['fz']} ft AMSL" if r["fz"] else "—"
                    ui.html('<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px">'
                            f'<div class="gv-tile"><span class="gv-k">QNH MÍN.</span><br><span class="gv-v">{M._e(q)}</span></div>'
                            f'<div class="gv-tile"><span class="gv-k">ISO 0 °C MÍN. (FZLVL)</span><br><span class="gv-v">{M._e(z)}</span></div>'
                            '</div>').classes("w-full")
                with ui.tab_panel(t_txt).classes("p-0"):
                    ui.html(f'<div class="gv-txt">{M._e(r["texto"])}</div>').classes("w-full")
                with ui.tab_panel(t_leg).classes("p-0"):
                    ui.markdown(_LEGENDA)

            async def pdf():
                dados = await run.cpu_bound(_gerar_pdf, r["regioes"], r["texto"], r["fz"], r["qnh"], r["validity_label"])
                ui.download(dados, f"briefing_lppc_{datetime.now(timezone.utc):%Y%m%d_%H%MZ}.pdf")
            ui.button("Descarregar briefing (PDF)", icon="download", on_click=pdf).classes("w-full").props(
                "unelevated color=primary text-color=dark size=lg no-caps")
            ui.html('<p class="gv-nota">Ferramenta de apoio à decisão. Não substitui o briefing '
                    'oficial nem o juízo do piloto.</p>')

    def erro(msg):
        briefing.clear()
        with briefing:
            ui.html(f'<div class="gv-alerta gv-erro">{_md(msg)}</div>').classes("w-full")

    # ---- Controlos (fim da página) ----
    ui.label("GAMET E ARQUIVO").classes("gv-sec")
    with ui.expansion("Texto do GAMET (colar ou editar)", icon="edit_note").classes("w-full gv-card"):
        caixa = ui.textarea(placeholder="LPPC GAMET VALID …").classes("w-full").props("dark outlined autogrow")

        async def analisar_colado():
            if caixa.value.strip():
                desenhar(await run.cpu_bound(analisar, caixa.value.strip(), "manual"))
        ui.button("Analisar este texto", icon="search", on_click=analisar_colado).classes("w-full").props("outline no-caps")

    with ui.expansion("Arquivo de GAMETs", icon="inventory_2").classes("w-full gv-card"):
        ui.label("GAMETs recolhidos do IPMA desde 14/10/2026. Para rever situações "
                 "passadas — não para planear um voo.").classes("gv-k")
        zona_arq = ui.column().classes("w-full")

        async def abrir_arquivo():
            zona_arq.clear()
            ok, idx = await run.io_bound(M.fetch_arquivo_indice)
            with zona_arq:
                if not ok:
                    ui.label(f"Não foi possível ler o arquivo: {idx}").classes("gv-k")
                    return
                lista = sorted(idx["gamets"], key=lambda e: (e.get("inicio") or "", e["recolhido"]), reverse=True)
                opc = {i: f"{(e.get('inicio') or '')[8:10]}/{(e.get('inicio') or '')[5:7]} "
                          f"{(e.get('inicio') or '')[11:13]}–{(e.get('fim') or '')[11:13]}Z"
                          + ("" if e.get("tipo", "GAMET") == "GAMET" else f" {e['tipo']}")
                       for i, e in enumerate(lista)}
                sel = ui.select(opc, value=0 if opc else None, label="GAMET").classes("w-full").props("dark outlined")

                async def carregar():
                    e = lista[sel.value]
                    ok2, txt = await run.io_bound(M.fetch_arquivo, e["ficheiro"])
                    if not ok2:
                        ui.notify(f"Não foi possível ler o GAMET: {txt}", type="negative")
                        return
                    txt = re.sub(r"\s+", " ", txt).strip()
                    caixa.value = txt
                    desenhar(await run.cpu_bound(analisar, txt, "arquivo_hist", None, None, "", idx, e))
                    ui.run_javascript("window.scrollTo({top:0,behavior:'smooth'})")
                ui.button("Carregar e analisar", on_click=carregar).classes("w-full").props("outline no-caps")
        ui.button("Abrir arquivo", icon="folder_open", on_click=abrir_arquivo).props("flat no-caps")

    async def carregar_actual():
        g = await run.io_bound(obter_gamet_actual)
        if not g["texto"]:
            erro("**Não foi possível obter o GAMET.** Cola o texto em baixo.\n\n" + g["erro"])
            return
        caixa.value = g["texto"]
        desenhar(await run.cpu_bound(analisar, g["texto"], g["fonte"], g["boletins"],
                                     g["boletins_at"], g["boletins_fonte"]))

    ui.button("Recarregar GAMET", icon="refresh", on_click=carregar_actual).classes("w-full").props("flat no-caps")
    await ui.context.client.connected()
    await carregar_actual()


def _gerar_pdf(*a):
    return M.generate_pdf(*a)


_STORAGE = bool(os.environ.get("STORAGE_SECRET"))

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="LPPC GAMET – VFR", port=int(os.environ.get("PORT", 8080)), dark=True,
           reload=False, show=False, favicon="✈️",
           storage_secret=os.environ.get("STORAGE_SECRET"))
