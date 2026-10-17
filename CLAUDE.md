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
- Qualificadores seguidos, com ou sem AND (`BTN N3840 AND N4100 E OF W00800`),
  são uma só área (2.3). A janela `HH/HH` pertence à subentrada que vem a
  seguir; uma subentrada sem janela vale para todo o período.

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
| SIGMET activo (no GAMET **ou** na página do IPMA) | NO-GO em toda a área |

TURB e ICE severos forçam NO-GO desde a v23: a maioria dos ultraleves não
tem sistemas de degelo nem margem estrutural para turbulência severa.

O SIGMET aplica-se a toda a FIR porque o campo `SIGMET APPLICABLE` do
GAMET não descreve geometria — restringi-lo a parte da área seria inventar
precisão que não temos.

Desde a 1.4 a app também lê os SIGMET/AIRMET da página do IPMA (a mesma
que traz o GAMET; `extract_bulletins_from_html`, `active_bulletins`), para
apanhar SIGMETs emitidos depois do GAMET. Só se aplicam ao GAMET carregado
do IPMA nessa sessão. AIRMETs são mostrados mas não interpretados.

Campos do modelo OACI (Anexo 3) suportados desde a 1.4: `SFC WSPD`, `MTW`
e, em `SIGWX`, os fenómenos de `_SIGWX_SEVEROS` além da trovoada.

Desde a 2.0 um CB em `SIG CLD` gera um fenómeno próprio (`CB`, com a escala
de `TS_RISK`), mesmo sem TS em `SIGWX`. Até à 1.6 era só o tipo de nuvem, e o
GAMET real 160300/160900 (`ISOL/EMBD TCU/CB` no NE, sem TS) dava GO em
Trás-os-Montes. Não é lido como TS: os motivos dizem "CB …".

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

446 testes. Devem passar a 100%.

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
- `tests/test_v23.py` — qualificadores seguidos sem AND (`BTN … AND … E OF …`)
  e janela horária de cada subentrada (GAMETs reais 160900, 162100, 170300)
- `tests/test_v25.py` — VIS sem unidade (`LCA 5000 RA`, GAMET real 161500)
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
   arquivo, que lista as decisões que ficam MAIS PERMISSIVAS).
5. Relatório e mensagem ao Duarte.

**Merge automático (decisão do Duarte, 17-out-2026):** um PR entra no
`main` sem intervenção quando o check "Testes" está verde **e** o revisor
diz APROVADO. **Na dúvida, não entra**: fica aberto com "[Precisa do
Duarte]" no título e a dúvida explicada na mensagem. É dúvida, sempre:
mudança de limiares/regras de decisão; decisão mais permissiva que o
revisor não consiga provar; leitura ambígua do GAMET; piloto e parser
discordarem sem se saber quem tem razão; qualquer funcionalidade nova
(não correcção).
