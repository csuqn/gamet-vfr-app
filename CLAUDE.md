# LPPC GAMET Decoder

App Streamlit que descodifica GAMETs da FIR LPPC (Portugal Continental) e
produz um briefing VFR com decisões **GO / MARGINAL / NO-GO** por região
geográfica.

Público-alvo: pilotos VFR e de ultraleves. **É uma ferramenta de apoio à
decisão de voo** — um erro pode levar alguém a voar em condições inseguras.
Isso condiciona todas as escolhas técnicas abaixo.

## Estrutura

Ficheiro único `app.py` (~2700 linhas) — é o ficheiro que o Streamlit Cloud publica a partir do ramo `main`. Não está dividido em
módulos porque o Streamlit corre um script de cima a baixo e a divisão
traria pouco benefício face ao custo. As secções estão marcadas por
comentários (`# PARSER`, `# DECISION`, `# PDF EXPORT`, `# EXECUÇÃO`).

Versão numa constante única, `APP_VERSION`, usada no título, no User-Agent
e nos metadados do PDF. Desde a **1.0** (estável) o ficheiro tem nome fixo (`app.py` no repositório) —
ao criar uma versão nova muda só a constante (1.1, 1.2… para correcções e
melhorias; 2.0 para mudanças de regras de decisão). Até à 1.0 a numeração
era v11…v31 no nome do ficheiro.

## Pipeline

```
texto → normalize → injecção de quebras por campo → máquina de estados
      → MetBlock(fenómeno, polígono, valor) → compute_dynamic_regions
      → decision() por célula → regiões fundidas por decisão
```

`compute_dynamic_regions` usa `polygonize` para partir a FIR nas células
atómicas definidas pela intersecção de todos os fenómenos, calcula a
decisão em cada uma e funde as que têm a mesma decisão. As regiões cobrem
sempre ~100% da FIR.

Três pormenores que já causaram erros reais:

- **Pertença por área, nunca por ponto.** Um fenómeno aplica-se a uma
  célula se cobrir mais de metade dela. Até à v31 usava-se
  `representative_point()`, que numa célula degenerada devolveu um vértice
  da fronteira e pôs 12% da FIR em GO com TS EMBD por todo o lado.
- **`_refine_cells`** parte explicitamente qualquer célula que um fenómeno
  cubra só em parte. O `polygonize` descarta segmentos cujas pontas não
  coincidem exactamente e deixa células por partir.
- Com bases AMSL as células são também partidas pela grelha de relevo, e
  se o briefing passar de 8 regiões juntam-se as bolsas com as mesmas
  causas (`_consolidate_groups`).
- Uma bolsa residual (< 1,5% da FIR) junta-se à região com as mesmas causas
  e notas se estiver a menos de `_BOLSA_MAX_KM` (25 km), mesmo sem ser
  contígua (2.0). Mais longe continua a ser um cartão próprio.
- Uma base de SIG CLD sem AGL nem AMSL (`BKN 002-008/010HFT`) é lida como
  **AGL** (3.3, decisão do Duarte a 18-out-2026: em SIG CLD o IPMA dá as
  bases em AGL e a falta da referência é tida por gralha). Só `AMSL`
  explícito é convertido contra o MEF. Até à 3.2 era descartada em silêncio.
- `HTF` numa base de nuvem (`BKN 008/010HTF AGL`, GAMET real 201500/202100)
  é gralha do IPMA e vale como `HFT` (3.7) — só em `_CLD_BASE_RE`, colado ao
  número; até à 3.6 a base desaparecia em silêncio (SIG CLD e Secção II).
- Topo de nuvem em intervalo (`050-090/100-130HTF AMSL`, GAMET real
  201500/202100, Secção II) é aceite em `_CLD_BASE_RE` (3.8); a base continua a
  ser o primeiro número e o topo é ignorado. Até à 3.7 a base desaparecia em
  silêncio. Na Secção II, AS/AC a 5000–6000 ft AMSL contra o MEF passa a dar a
  nota "Nuvens baixas" em muitos GAMETs (18/28 do arquivo a 21-out-2026).
- **Topo com `ABV` ou com espaços à volta da barra** (`BKN 002/ABV 030HFT AGL`,
  `002/ABV030HFT`, `002 / 030HFT`; 4.0, revisor do PR #26): até à 4.0 a base
  não casava em `_CLD_BASE_RE` e o **topo era lido como base** (3000 ft → GO em
  silêncio), no GAMET e no AIRMET. A base é sempre o primeiro número; o topo
  aceita `/ABV n`, `/ABVn` e ` / `; um número precedido de `-`/`/` (com ou sem
  espaços e `ABV`) nunca é base. Base de 1–2 algarismos só antes de uma barra
  (`OVC CLD 0/1000FT`, Anexo 3). Nenhum GAMET do arquivo tinha estes formatos
  (comparação a 26-out-2026: nada muda).
- **MT OBSC e VA: um bloco por subentrada** (3.10). Até à 3.9 só a linha que
  abre o campo gerava bloco: em `MT OBSC:N OF N4100 LAN S OF N3800 LAN` o S de
  N3800 ficava fora da decisão. Cada subentrada gera agora o seu, com a sua
  janela; a linha de abertura vazia (`MT OBSC:` antes de `17/19 N OF …`, ou
  `MT OBSC S OF …`) continua a dar toda a FIR. VA dentro de SIGWX abre o campo
  VA (quebra antes de `VA`) e fica em toda a FIR, como antes.
- **Vírgula decimal nos KM** (3.10): `LCA 1,5KM BR` → 1500 m (até à 3.9, 5000 m:
  apanhava o `5KM`). Só `\d{1,2},\d+` colado (`0800M BR, 5KM`, `1200M,5KM`,
  `2500,5KM` continuam a ser dois valores). Só a VIS lê KM.
- Qualificadores seguidos, com ou sem AND (`BTN N3840 AND N4100 E OF W00800`),
  são uma só área (2.3). A janela `HH/HH` pertence à subentrada que vem a
  seguir; uma subentrada sem janela vale para todo o período.
- Uma fatia pequena (< 1,5%) só se funde numa vizinha da mesma decisão se os
  motivos dela já estiverem na vizinha (3.2); senão fica cartão próprio. Antes,
  os motivos da fatia passavam para a região inteira.
- `BTN` aceita `AND` ou hífen entre os limites (`BTN N4050 - N3840`, 3.1).
- Uma subentrada que começa (depois da janela `HH/HH`) por algo com ar de
  qualificador geográfico (`N/NW… OF`, `BTN`, `WI`, `ALONG`, `N PART`,
  coordenada) mas de que `extract_polygon` não tira área vale para **toda a
  FIR** e gera um aviso "Área não reconhecida" (`subentradas_sem_area`; também
  no `scripts/analisar.py`) — até à 3.3 herdava em silêncio a área da anterior
  (pedido do Duarte, 3.4). `ENTIRE FIR` também dá toda a FIR, sem aviso.
  Linhas sem qualificador continuam a usar a área da subentrada; um
  qualificador fora da FIR continua a descartar o fenómeno; MAR/LAN/COT
  sozinhos não são área. Só conta o que já é início de linha (quebra injectada
  antes de `N OF N…`/`BTN N…` etc., ou quebra do texto) — não se injectam
  quebras novas.
- **Cardinal solto antes de BTN** (`S BTN N3720 - N3800`, GAMET real
  182100/190300; 3.5, opção (b) do Duarte a 19-out-2026): cardinal simples
  (N/S/E/W, sem `OF`/`PART`) imediatamente antes de `BTN` dá a **união** da
  faixa com o semiplano nessa direcção, a partir do limite mais extremo nessa
  direcção — `S BTN N3720 - N3800` → `S OF N3800`; `N BTN` → `N OF` a menor
  latitude; com longitudes, `E BTN` → `E OF` a mais a oeste, `W BTN` → `W OF`
  a mais a leste. Mantém as intersecções com LAN/MAR/COT e os outros
  qualificadores da linha. Gera sempre o aviso "Área alargada"
  (`subentradas_alargadas`; alerta no `scripts/analisar.py`). Eixo trocado
  (`E BTN N…`, `N BTN W…`) ou limites ilegíveis → a linha fica sem área (toda
  a FIR + aviso "Área não reconhecida"). A quebra injectada antes de `BTN N…`
  passa para antes do cardinal (que leva a janela consigo); um cardinal que
  já abre a linha/campo (`CLD:S BTN`) não é separado. O cardinal solto
  **nunca se junta por AND** a um qualificador anterior (`E OF W00800 S BTN …`
  fica em duas linhas, como na 3.4 — juntá-los dava `E OF ∩ S OF`, menor do
  que a faixa da 3.4; rejeitado pelo revisor no d043ce1). Na mesma linha, a
  área é sempre unida com a leitura da 3.4 (a linha sem os cardinais), porque
  a intersecção vazia → união podia dar mais área na 3.4. Até à 3.4 o
  cardinal era ignorado em silêncio e a janela `23/03` perdia-se. A área nova
  contém sempre a da 3.4 — testado contra o motor da 3.4
  (`tests/referencia/app_3_4.py`, `test_v35_contra_34.py`).
- **Diagonais** (`NE/NW/SE/SW OF …`, `_DIAGONAL_RE`) não são interpretadas: a
  linha onde aparecem, em qualquer posição, fica sem área legível → toda a FIR
  + aviso; num SIGMET sem `WI`, toda a área. Os cardinais `N/S/E/W OF` exigem
  fronteira de palavra (em `extract_polygon`). A junção por AND aceita
  diagonais (`[NSEW]{1,3} OF`), para a quebra antes do cardinal seguinte não
  separar a diagonal do resto da área. Até à 3.3
  `NW OF W00800` era lido como `W OF W00800`. Toda a FIR contém qualquer
  meia-FIR, por isso nunca é mais permissivo.

Não há sectores fixos. A app teve 3 sectores (Norte/Centro/Sul) até à v17;
foram substituídos por geometria dinâmica porque marcavam um sector
inteiro como NO-GO quando só uma fatia estava afectada — Bragança e Porto
estão ambos no "Norte" mas podem ter condições muito diferentes.
`ZONES` e `SECTOR_*` (sectores inferiores oficiais) servem apenas para
definir `FIR_POLYGON` — não entram na decisão.

## Regras de decisão

| Condição | Decisão |
|---|---|
| VIS < 1500 m (geral) | NO-GO |
| VIS < 1500 m (LCA) | MARGINAL — é local |
| VIS < 3000 m | MARGINAL |
| Base < 300 ft AGL | NO-GO |
| Base < 500 ft AGL | MARGINAL |
| TS ISOL | MARGINAL |
| TS OCNL / FRQ / EMBD / ISOL_EMBD / GEN | NO-GO |
| CB em SIG CLD, ISOL | MARGINAL (desde a 2.0) |
| CB em SIG CLD, EMBD / OCNL / FRQ / sem qualificador | NO-GO (desde a 2.0; TCU sozinho não conta) |
| TURB ou ICE **SEV** (ou HVY) | NO-GO |
| TURB ou ICE MOD | informativo, não altera decisão |
| MTW (onda de montanha) SEV | NO-GO |
| MTW MOD | MARGINAL (≠ TURB MOD: descendentes junto ao relevo) |
| SFC WSPD ≥ 30 kt | NO-GO |
| SIGWX SQL / FZRA / FZDZ / DS / SS / GR / FC | NO-GO |
| MT OBSC | NO-GO |
| VA (cinzas vulcânicas) | NO-GO |
| SIGMET activo com área legível (página do IPMA / arquivo) | NO-GO na área + 10 NM, estendida pelo MOV (desde a 3.0) |
| SIGMET sem área legível, ENTIRE FIR, ou só o identificador no GAMET | NO-GO em toda a área |
| SIGMET referido no GAMET que se sabe terminado (expirou / CNL) | não conta; aviso (desde a 3.2). Estado desconhecido → toda a área |
| AIRMET em vigor (página do IPMA / arquivo) | as regras acima, na área do AIRMET, **sem margem**, estendida pelo MOV (desde a 4.0). Área/MOV ilegível → toda a FIR + aviso |
| AIRMET em vigor com fenómeno ilegível | MARGINAL na área do AIRMET + aviso "AIRMET não interpretado" (desde a 4.0) |

TURB e ICE severos forçam NO-GO desde a v23: a maioria dos ultraleves não
tem sistemas de degelo nem margem estrutural para turbulência severa.

**SIGMET (3.0, decisão do Duarte a 17-out-2026).** Até à 2.7 qualquer
SIGMET punha NO-GO em toda a FIR, porque a app só tinha o campo
`SIGMET APPLICABLE` do GAMET, que não traz geometria. Desde que lê o SIGMET
completo (página do IPMA e arquivo), usa a área dele: `area_sigmet()` lê
`WI <polígono>`, `WI nnNM OF <ponto>` e os qualificadores do GAMET
(`N OF …`, `BTN …`) — coordenadas `Nnn[nn] Wnnn[nn]` (os minutos podem faltar
e valem 00', Anexo 3; 3.5, decisão do Duarte a 19-out-2026 — o SIGMET real U02
de 18-out com `N3347 W018` punha NO-GO em toda a FIR) —, junta `_SIGMET_MARGEM_NM` (10 NM) e, com `MOV dir nnKT`,
estende a área na direcção do movimento desde a hora da observação
(`OBS AT`, se anterior) até ao fim da validade.
`blocos_sigmet()` transforma cada SIGMET num `MetBlock("SIGMET")`, que entra
em `compute_dynamic_regions` como qualquer fenómeno (decisão NO-GO).
Continua a ser **toda a área** quando: a área não é legível, há `ENTIRE FIR`
ou `LINE`, o `MOV` não tem direcção/velocidade legível, ou o GAMET refere um
SIGMET cujo texto completo não está disponível (ex.: GAMET colado à mão).
Os níveis (`TOP FL340`, `SFC/FL080`) ainda não restringem a decisão.
Desde a 3.2 (decisão do Duarte), um SIGMET referido em `SIGMET APPLICABLE`
que se **sabe** terminado — validade acabada ou `CNL SIGMET <id>` na página do
IPMA ou nos boletins arquivados das últimas 24 h (`sigmets_terminados`) —
deixa de contar, com aviso. Se o estado não se souber, conta em toda a área.
A numeração dos SIGMET recomeça todos os dias: só contam os boletins com
esse id que começam no mesmo dia UTC do GAMET e se sobrepõem à sua validade,
com cabeçalho legível, e todos têm de estar
terminados. Um CNL só cancela o boletim concreto (mesmo id **e** validade;
sem validade, o que estava em vigor no início do CNL — `_boletins_cancelados`,
também usado por `active_bulletins`).

Desde a 1.4 a app também lê os SIGMET/AIRMET da página do IPMA (a mesma
que traz o GAMET; `extract_bulletins_from_html`, `active_bulletins`), para
apanhar SIGMETs emitidos depois do GAMET. Só se aplicam ao GAMET carregado
do IPMA nessa sessão. Até à 3.10 os AIRMETs eram só mostrados; desde a 4.0
entram na decisão (ver abaixo).

**AIRMET na decisão (4.0, decisão do Duarte a 26-out-2026).** Caso real de
25-out-2026: o GAMET 251500/252100 só tinha BKN 006 a N de N4100 e W de W00800
(GO em todo o lado) e o IPMA emitiu `AIRMET 1 … BKN CLD OBS N OF N3930 COT
002HFT AGL` (18:10Z) e `AIRMET 2 … SFC VIS 0200-5000M FG/BR OBS N OF N3930 COT
AND LAN` (18:40Z); a 3.10 dava 100% GO e só "AIRMET … não o interpreta". Desde
a 4.0 `ler_airmet()` / `blocos_airmet()` lêem cada AIRMET em vigor com **as
regras normais, não NO-GO automático**: o valor (o corpo sem área, movimento e
tendência — `_AIRMET_NAO_VALOR`) vai para uma Secção I sintética com o campo
do GAMET correspondente (`_AIRMET_CAMPOS`: SFC VIS, BKN/OVC CLD → SIG CLD,
ISOL/OCNL TS/TSGR → SIGWX, ISOL/OCNL/FRQ CB → SIG CLD, TURB, ICE, MTW, MT OBSC,
SFC WIND/WSPD) e é lido por `parse_gamet`. Cada fenómeno vai do seu início ao
do seguinte, por isso dois fenómenos ligados por AND (`SFC VIS 4000M BR AND BKN
CLD 002/010HFT AGL`) são lidos os dois, com a mesma área. TS com precipitação
(`OCNL TSRA`, `ISOL TSGR`) é TS. Palavras que sobram sem significado
(`_resto_ilegivel_airmet`, ex.: `ISOL TCU … XYZ`) → "lido em parte" → MARGINAL
+ aviso; os blocos entram em
`compute_dynamic_regions` com a área do AIRMET e são avaliados pela mesma
`decision()` — **os limiares não mudaram**. LCA no texto → LCA; base sem
AGL/AMSL → AGL; `BKN CLD 120/900M` (metros, Anexo 3) → pés por defeito; TCU
sozinho não conta; MOD TURB/ICE são informativos (nota na região). Área:
`_area_boletim()` (partilhada com `area_sigmet`, que só junta a margem) — WI
polígono/círculo ou qualificadores do GAMET, estendida pelo MOV — **sem** os
10 NM do SIGMET, recortada por COT/LAN/MAR. MOV ilegível, `LINE`, área
ilegível ou ausente, ou restos de área não lidos (`OF`/`BTN`/`PART`/`WI` no
valor) → toda a FIR + aviso "Área do AIRMET não reconhecida"; `ENTIRE FIR` →
toda a FIR sem esse aviso. Fenómeno ilegível (nenhum campo reconhecido, ou um
campo reconhecido sem valor legível) → bloco `AIRMET` (tipo novo em
`decision`, o único: MARGINAL) na área + aviso "AIRMET não interpretado". Os
blocos levam `MetBlock.origem` ("AIRMET 2"); `_motivos_por_origem` mantém a
decisão de `decision(todos os eventos)` e separa os motivos por origem
("AIRMET 2 — VIS 200m < 1500m"). Fontes: as dos SIGMETs (`ipma`/
`arquivo_recurso` com `active_bulletins`, que já tira os `CNL AIRMET`;
`arquivo_hist` com `boletins_do_periodo`); colado à mão não há AIRMETs. O aviso
dos AIRMETs lista, para cada um, o que leu, o efeito e a área. A faixa SIGMET
não muda. Os blocos só se acrescentam: nunca mais permissivo do que a 3.10
(`test_v40.py`; `comparar_versoes.py` no arquivo a 26-out-2026: 0 mais
permissivas, 25 mais severas, todas no GAMET 251500). Os níveis (`FL015`) não
restringem a decisão, como no SIGMET.

Campos do modelo OACI (Anexo 3) suportados desde a 1.4: `SFC WSPD`, `MTW`
e, em `SIGWX`, os fenómenos de `_SIGWX_SEVEROS` além da trovoada.

Desde a 2.0 um CB em `SIG CLD` gera um fenómeno próprio (`CB`, com a escala
de `TS_RISK`), mesmo sem TS em `SIGWX`. Até à 1.6 era só o tipo de nuvem, e o
GAMET real 160300/160900 (`ISOL/EMBD TCU/CB` no NE, sem TS) dava GO em
Trás-os-Montes. Não é lido como TS: os motivos dizem "CB …".

**Nuvens baixas na Secção II (3.6, pedido do Duarte a 20-out-2026).** O `CLD`
da Secção II é a nuvem que não cumpre os critérios de SIG CLD e **não entra na
decisão**. Desde a 3.6, `nuvens_baixas_secn2()` lê esse campo com a mesma
máquina do SIG CLD (áreas, janelas, AGL/AMSL; sem referência = AGL) e, se
alguma base ficar < 500 ft AGL (AMSL contra o MEF), `analisar_gamet` junta um
aviso `info` "Nuvens baixas na Secção II" com a base, janela, superfície e os
aeródromos abrangidos. Nunca vai a `compute_dynamic_regions`. Caso real:
GAMET 192100/200300 (`SCT ST 004-008/012HFT` a N de N4000, 00–03Z).

**Campo não interpretado (3.9, pedido do Duarte a 21-out-2026).**
`campos_nao_interpretados()` devolve as subentradas da Secção I com conteúdo
(não NIL) que não geraram nenhum fenómeno, e `analisar_gamet` junta um aviso
`aviso` "Campo não interpretado" (o texto NÃO entra na decisão; não muda
decisões). A verificação é **por subentrada**, dentro de `parse_gamet`
(parâmetro `sem_fenomeno`): uma subentrada é a linha que abre o campo ou traz
qualificador geográfico, mais as linhas sem qualificador que se lhe seguem —
uma subentrada ilegível num campo com outra legível também avisa. Não conta a
que tem área lida fora da FIR/superfície (descartada de propósito), nem só
janela/NIL/pontuação. O `scripts/analisar.py` ("Campo sem fenómeno gerado") usa
a mesma função; até à 3.8 verificava por campo, com lógica própria. Dentro de
uma só subentrada basta um fenómeno lido para não avisar (ex.: duas bases na
mesma linha, uma ilegível). Caso real: GAMET 201500/202100 até à 3.6
(`008/010HTF`). 0 avisos no arquivo a 21-out-2026 (28 GAMETs). Em `MT OBSC` e
`VA`, até à 3.9 só a linha que abre o campo gerava bloco e a 2.ª subentrada
(`MT OBSC: N OF N4100 LAN S OF N3800 LAN`) só avisava; desde a 3.10 gera bloco
(ver abaixo) e deixa de avisar.

## Princípios que orientam o código

**O erro optimista é inaceitável.** Reportar pior do que a realidade é
chato; reportar melhor é perigoso. Na dúvida entre duas leituras, escolhe
a conservadora. É por isso que valores de visibilidade e base usam sempre
`min()`.

**Falhar em voz alta.** Um GAMET que não é interpretado não pode resultar
em "GO" silencioso — `looks_unparseable()` existe para distinguir "está
calmo" de "não percebi o texto". Um fetch que falha mostra diagnóstico, não
uma caixa vazia.

**Determinismo.** O parser é regex e máquina de estados, sem LLM. Um erro
é localizável e corrigível; um LLM erraria de forma silenciosa e não
reproduzível, o que num contexto go/no-go é bastante pior. A app também
funciona sem rede, com o GAMET colado à mão.

**Testar comportamento.** Verificar que uma string existe no ficheiro não
prova nada. Todos os bugs reais deste projecto apareceram ao executar
lógica com dados concretos.

## Testes

```bash
python3 -m pytest
```

1379 testes (com a NiceGUI instalada; sem ela, os do `test_nicegui.py` saltam). Devem passar a 100%.

- `tests/test_parser.py` — VIS, base, TS, TURB/ICE, MT OBSC, VA
- `tests/test_geometry.py` — geometria, SIGMET, **invariantes**
- `tests/test_data.py` — validade temporal, vento, IPMA, robustez
- `tests/test_v1.py` — regressões da 1.0, oráculo, fronteira, relevo,
  janela horária e **a app completa** (via `streamlit.testing`)
- `tests/test_v14.py` — campos OACI novos e SIGMETs do IPMA
- `tests/test_v15.py` — qualificadores geográficos ligados por AND
- `tests/test_v16.py` — índice do arquivo, recurso ao arquivo e SIGMETs
  históricos (inclui a app completa com a rede simulada)
- `tests/test_v20.py` — CB em SIG CLD (GAMET real 160300) e bolsas residuais
- `tests/test_v22.py` — componentes HTML do briefing (2.2), faixa do SIGMET e
  análise automática ao abrir
- `tests/test_v26.py` — `analisar_gamet` (análise completa partilhada)
- `tests/test_nicegui.py` — a interface NiceGUI dá as mesmas decisões (salta
  sem NiceGUI instalado)
- `tests/test_v23.py` — qualificadores seguidos sem AND (`BTN … AND … E OF …`)
  e janela horária de cada subentrada (GAMETs reais 160900, 162100, 170300)
- `tests/test_v25.py` — VIS sem unidade (`LCA 5000 RA`, GAMET real 161500)
- `tests/test_v27.py` — SIGMET/AIRMET sem "=" final (boletins reais de
  17-out-2026: SIGMET T01, AIRMET 1)
- `tests/test_v30.py` — SIGMET só na sua área + 10 NM (SIGMET T02 real),
  movimento, círculo, ENTIRE FIR, área ilegível, referência do GAMET
- `tests/test_v31.py` — base de SIG CLD sem AGL/AMSL (GAMETs reais 172100 e
  180300: `LCA BKN 002-008/010HFT`)
- `tests/test_v32.py` — `BTN … - …` com hífen (GAMET real 171500/172100)
- `tests/test_v33.py` — SIGMET referido já terminado (T02 real após 18Z) e
  motivos de fatias que não passam para a vizinha
- `tests/test_v34.py` — subentrada com área ilegível → toda a FIR + aviso
  (GAMET real 171500 com `BTN N4050 ~ N3840`), casos que não mudam, `SW OF`
  colado na mesma linha (OCNL TS continua NO-GO no NE), diagonais `NE/NW/SE/SW OF`
  (toda a FIR + aviso; SIGMET → toda a área)
- `tests/test_v35.py` — cardinal solto antes de BTN (GAMET real 182100:
  `S BTN N3720 - N3800` → `S OF N3800`, aviso; N/E/W, eixo trocado → toda a
  FIR, área nova ⊇ antiga) e coordenadas de SIGMET só com graus (SIGMET real
  U02 com `W018`; U01, T01, T02 inalterados)
- `tests/test_v36.py` — nota informativa de nuvens baixas na Secção II (GAMET
  real 192100: 18 aeródromos, decisão inalterada)
- `tests/test_v37.py` — `HTF` como gralha de `HFT` nas bases (GAMET real
  201500: base 800 ft a N de N4100, GO inalterado; 004/002HTF → MARGINAL/NO-GO;
  nota da Secção II; `analisar.py` sem "Campo sem fenómeno gerado")
- `tests/test_v38.py` — topo em intervalo (GAMET real 201500: AS/AC
  `050-090/100-130HTF AMSL` lida, nota AMSL contra o MEF; SIG CLD
  `002-004/010-015HFT` → NO-GO, `004/010-015HFT` → MARGINAL, igual a topo
  simples; o topo nunca é lido como base)
- `tests/test_v39.py` — aviso "Campo não interpretado" (GAMET real 201500 com
  a gralha nova `HTX`; campo ilegível; subentrada ilegível ao lado de uma
  legível; NIL, `HAZARDOUS WX NIL`, área fora da FIR e todo o arquivo não
  avisam; Streamlit e NiceGUI mostram o aviso; decisão inalterada; 2.ª
  subentrada de MT OBSC/VA nunca em silêncio — desde a 3.10 gera bloco)
- `tests/test_v310.py` — MT OBSC/VA com 2 e 3 subentradas (GAMET real 201500
  com a Secção I trocada: LAN/MAR, janelas, fora da FIR, ENTIRE FIR, área
  ilegível, VA em SIGWX) e vírgula decimal nos KM (`1,5KM` → 1500,
  `0,8KM` → 800, `LCA 1,5KM` → MARGINAL; `1.5KM` e vírgulas que separam
  valores inalterados)
- `tests/test_v40.py` — AIRMETs na decisão (AIRMET 1 e 2 reais de 25-out com o
  GAMET 251500 às 18:00/18:30/19:00/21:05Z; AIRMET MOD TURB real de 17-out sem
  mudança; cada fenómeno, LCA, AMSL, metros, WI polígono/círculo sem margem,
  MOV/STNR, área ilegível → toda a FIR + aviso, fenómeno ilegível → MARGINAL
  + aviso, CNL, arquivo_hist/recurso, colado à mão; nunca mais permissivo nos
  aeródromos e numa grelha; oráculo; Streamlit e NiceGUI). Revisão do PR #26:
  topo `/ABV`/` / ` nunca é base (GAMET e AIRMET; formas antigas
  inalteradas), formatos do Anexo 3 (`200/ABV3000FT`, `0/1000FT`, `0/300M`,
  `TSRA`), dois fenómenos com AND, resto ilegível → MARGINAL + aviso
- `tests/test_v35_contra_34.py` — 400 subentradas geradas (qualificadores
  antes/depois do cardinal, AND/espaço, MAR/LAN/COT, janela, diagonais):
  nos 52 aeródromos e numa grelha de 0,2°, a decisão nunca é mais permissiva
  do que a do motor da **3.4**, carregado de `tests/referencia/app_3_4.py`
  (cópia fixa do `app.py` do main 46e8d8e; o checkout do CI não tem
  histórico). Não editar a cópia.
- `tests/conftest.py` — extrai o motor da app sem executar a UI. Os imports
  vêm da própria app (nunca de uma lista fixa — escondia imports em falta)

`test_regioes_concordam_com_oraculo` é o teste mais importante: compara a
decisão de cada região com a decisão calculada directamente sobre os
fenómenos que contêm cada aeródromo, em 150 GAMETs aleatórios.

Os invariantes em `test_geometry.py` correm sobre uma lista de GAMETs
representativos e verificam propriedades que têm de se manter sempre.
Acrescentar um GAMET a `GAMETS_VARIADOS` fá-lo passar por todos.

**Nunca ajustes um teste ao output para o fazer passar.**

## Subagentes

- `testes` — escrever e correr testes após alterações
- `parser` — rever regex e lógica de extracção
- `dados-aero` — adicionar ou validar aeródromos e pistas UL

Usados pelo relatório diário (ver "Relatório diário com agentes"):

- `piloto` — lê um GAMET às cegas, como um piloto, e dá a decisão por aeródromo
- `comparador` — compara parser × piloto e classifica cada diferença
- `editor` — corrige um erro confirmado, com teste do GAMET real
- `revisor` — revê a correcção de forma independente (testes + comparação
  de versões); APROVADO / REJEITADO / DÚVIDA

## Geografia

- **Área do GAMET** — os três sectores **inferiores** da FIR (ENR 2.1.3,
  SFC–FL245): NORTH LOWER 3.1, CENTRE LOWER 6.1, SOUTH LOWER 8.1, com as
  coordenadas oficiais do eAIP (ENR 2.1, 27-NOV-2025, fornecido pelo
  utilizador). Nunca usar vértices dos sectores superiores — incluem espaço
  aéreo delegado sobre Espanha.
- **Fronteira** — o ENR 2.1 só diz "along Portuguese/Spanish border". Traçado
  base da Natural Earth 1:10m (domínio público), forçado a passar pelos 14
  pontos do ENR 2.1 que iniciam/terminam "along border" (antes do ajuste
  desviava-se deles 0,04–3,3 km) e pelas fozes do Minho e do Guadiana.
- **Costa** — 67 pontos da NAV Portugal, fornecidos pelo utilizador. Os estuários do Tejo e
  do Minho contam como terra.
- **Relevo** — `_TERRAIN_MAX_FT`: MEF (Maximum Elevation Figure) do
  SkyDemon por quadrícula de **1° de longitude × 30' de latitude**, lidos
  das capturas de ecrã do utilizador (out-2026). O SkyDemon usa dados
  aeronáuticos oficiais; os MEF incluem obstáculos e margem. Quadrículas só de mar sem valor
  legível ficam a 600 ft. A app recusa arrancar se alguma quadrícula que
  toque a área não tiver valor.

## Dados aeronáuticos

52 pontos: 28 aeródromos ICAO + 24 pistas de ultraleves, todos com
coordenadas oficiais do eVFR da NAV Portugal (AD 2.2 e AD 4.2).
Nunca inventar coordenadas — se falta uma, dizer que falta.

## Ligação ao IPMA

Endpoint actual: `https://brief-ng.ipma.pt/pages/actuals/sigmet.php`

O IPMA já mudou o caminho (era `/showsigmet.php` na raiz até à migração
para single-page app). O fetch tenta 7 endpoints em sequência, aceita HTML
e JSON, e a app tem um campo de URL alternativo para o utilizador corrigir
sem editar código.

## Duas interfaces, um motor (2.6)

- **NiceGUI** (`nicegui_app/`) — a interface **principal**, publicada no Render
  (https://gamet-vfr-app.onrender.com/, plano gratuito: adormece após 15 min
  sem uso, ~1 min a acordar) a partir do ramo `main`.
- **Streamlit** (`app.py`) — reserva, no Streamlit Cloud.
- O motor vive no `app.py`. `nicegui_app/motor.py` executa as mesmas secções
  que os testes extraem (`tests/conftest.py`) e a secção de rede. **Não há
  cópia do motor** — uma correcção no `app.py` vale para as duas.
- `analisar_gamet()` (secção `# ANÁLISE COMPLETA`) faz tudo o que vai do
  texto ao briefing: validade, regiões, SIGMETs (GAMET / IPMA / arquivo),
  faixa e avisos `(tipo, markdown)`. As duas interfaces só desenham.
- A recolha e o relatório diário correm no GitHub Actions e testam o motor —
  não dependem de nenhuma das interfaces.

## Interface (2.2)

Tema escuro "aeronáutico" em `.streamlit/config.toml`; o resto do aspecto
está em `_CSS` (início da app). Pensada primeiro para o telemóvel.

- Ordem no ecrã: briefing (`_c_brief`) no topo, controlos (`_c_ctrl`: texto,
  arquivo, ligação ao IPMA) no fim. Os contentores são criados no início e
  preenchidos depois — o Streamlit mostra-os pela ordem de criação.
- O GAMET do IPMA (ou do recurso ao arquivo) é analisado logo ao abrir.
- Faixa, veredicto, cartões e aeródromo são HTML gerado por funções puras
  (`html_faixa`, `html_veredicto`, `html_regiao`, `html_aerodromo`, secção
  `# UI — COMPONENTES HTML`), com `html.escape` em todo o texto. Os testes da
  app lêem o veredicto com `conftest.veredicto(at)`.
- A faixa nunca diz `NIL` se os SIGMETs não foram verificados (`N/VERIF.`).
- Alertas (SIGMET, AIRMET, validade, texto ilegível, vento) continuam a ser
  `st.error`/`st.warning` nativos.

## Armadilhas conhecidas

**Streamlit e `st.button`** — devolve `True` só no ciclo imediatamente a
seguir ao clique. Widgets dentro de um `if st.button(...)` desaparecem
quando o utilizador interage com eles. Guarda o estado em
`st.session_state` (ver `_active_gamet_text`).

**Tiles do mapa** — usar `tiles="OpenStreetMap"`. Os alias de CartoDB do
Folium levam a serviços que passaram a exigir API key e o mapa aparece com
marca de água "API KEY REQUIRED".

**Intersecções degeneradas** — podem produzir `GeometryCollection`, cujo
`.boundary` é `None`, fazendo o fenómeno desaparecer do `polygonize`.
`_clean_poly()` existe para isso e é chamada após cada intersecção.

**Dia sem mês** — o GAMET indica o dia mas não o mês. `_build_utc_date()`
procura o mês certo à volta da data actual; `replace(day=31)` rebentava
quando o mês corrente não tinha dia 31.

## Arquivo de GAMETs (1.6)

A app lê o arquivo do ramo `dados` por `raw.githubusercontent.com`
(`_ARQUIVO_BASE`; nunca pela API do GitHub, que tem limite de pedidos),
através de `dados/indice.json`, que `scripts/recolher_gamet.py`
(`construir_indice`) reconstrói das pastas no fim de cada volta.

- **Recurso:** quando o fetch do IPMA não traz GAMET (o IPMA retira o
  anterior ~45 min antes do novo), `gamet_de_recurso` carrega o último GAMET
  arquivado em vigor — confirmado pela validade lida do próprio texto, não só
  pelo nome do ficheiro. SIGMETs = arquivo ∪ página do IPMA, se respondeu
  (`_IPMA_LAST["sem_gamet"]`). Corre no início de `# EXECUÇÃO`, porque o
  motor só está definido aí (flag `_tentar_recurso` + `st.rerun()`).
- **Consulta:** painel "📚 Arquivo de GAMETs". Um GAMET do arquivo usa os
  SIGMETs arquivados que se **sobrepõem à sua validade**
  (`boletins_do_periodo`; um SIGMET cancelado a meio conta).
- **Origem do GAMET** em `st.session_state["gamet_fonte"]`: `ipma`,
  `arquivo_recurso`, `arquivo_hist`. (O "Histórico de GAMETs analisados" da
  sessão foi retirado na 2.1 — para GAMETs antigos há o arquivo.)
  Só `ipma` e `arquivo_recurso` usam os SIGMETs de agora; texto editado ou
  colado é sempre "manual" (só conta o `SIGMET APPLICABLE` do texto).

## Teste contínuo com GAMETs reais

Ramos: `main` tem o código (é o que o Streamlit Cloud publica); `dados` tem
os GAMETs recolhidos (`gamets/AAAA/MM/`) e os relatórios (`relatorios/`).
Ficam separados para que cada recolha não reinicie a app publicada.

- `.github/workflows/recolha-gamet.yml` — GitHub Actions, **em cadeia**:
  cada execução fica ligada ~5h30, recolhe de 15 em 15 minutos e, no fim,
  lança a seguinte (`gh workflow run` com o GITHUB_TOKEN). O `schedule`
  (:23 e :53) é só rede de segurança — o agendamento do GitHub não é fiável
  (a 15-out-2026 esteve 7 h sem correr). O grupo de concorrência impede
  recolhas em paralelo. Para testar sem encadear: `encadear=false` e
  `duracao_min` curto. Cada volta corre `scripts/recolher_gamet.py`, que usa o MESMO código de recolha da
  app, e guarda cada GAMET distinto no ramo `dados` (inclui AMD/COR).
  Guarda também os SIGMET/AIRMET LPPC em `sigmets/AAAA/MM/` (blocos com
  formato inesperado vão para `sigmets/desconhecidos/`). Falhas de recolha
  ficam em `gamets/falhas.log`. Correr à mão com "guardar_pagina" guarda a
  página do IPMA tal como vem, em `paginas/`, para diagnóstico.
- `scripts/analisar.py` — passa os GAMETs pela app e assinala: excepções,
  GAMET ilegível, **campos com conteúdo que não geraram fenómeno**,
  palavras fora do vocabulário e discrepâncias com o oráculo. Uso:
  `python scripts/analisar.py --dir dados/gamets --desde 24`.
- Relatórios diários em `relatorios/AAAA-MM-DD.md` e resumo mensal em
  `relatorios/resumo-AAAA-MM.md` (ramo `dados`). Sem data de fim.

## Relatório diário com agentes

Tarefa agendada às 08:00 (Lisboa). Cadeia:

1. `scripts/analisar.py` — leitura pelo parser (determinística, não é agente).
2. `piloto` × N — um por GAMET das últimas 24 h, em paralelo, **às cegas**.
3. `comparador` — parser × piloto, aeródromo a aeródromo.
4. Para cada erro do parser confirmado: `editor` (ramo `proposta/...` com
   teste do GAMET real) → PR → check "Testes" (GitHub Actions) →
   `revisor` (independente; inclui `scripts/comparar_versoes.py` sobre todo o
   arquivo, que lista as decisões que ficam MAIS PERMISSIVAS; com `--indice`
   inclui os SIGMETs arquivados).
5. Relatório e mensagem ao Duarte.

**Merge automático (decisão do Duarte, 17-out-2026):** um PR entra no
`main` sem intervenção quando o check "Testes" está verde **e** o revisor
diz APROVADO. **Na dúvida, não entra**: fica aberto com "[Precisa do
Duarte]" no título e a dúvida explicada na mensagem. É dúvida, sempre:
mudança de limiares/regras de decisão; decisão mais permissiva que o
revisor não consiga provar; leitura ambígua do GAMET; piloto e parser
discordarem sem se saber quem tem razão; qualquer funcionalidade nova
(não correcção).

**Excepção para erros CRÍTICOS (decisão do Duarte, 19-out-2026):** quando
um erro optimista confirmado só se corrige escolhendo entre duas ou mais
leituras (caso do PR #14: base sem referência como AGL ou AMSL), entra
sozinha a variante **mais conservadora**, desde que: check "Testes" verde;
revisor APROVADO para essa variante; a comparação de versões dá **0
decisões mais permissivas** (só mais severas); e não mexe em limiares. O
PR leva "[Entrou — escolha a confirmar]" no título e a escolha vai na
mensagem ao Duarte, que pode trocar de leitura depois. Fora disto, a regra
"na dúvida, não entra" mantém-se.
