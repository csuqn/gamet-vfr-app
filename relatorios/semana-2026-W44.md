# Relatório semanal — 2026-W44 (26 de Outubro a 1 de Novembro de 2026)

Segunda semana completa do processo com agentes. A W43 serve de termo de comparação.

**Fontes:**
- relatórios diários de 27-out a 02-nov (cada um cobre as 24 h anteriores, por isso cobrem os dias 26-out a 01-nov) e a adenda do relatório de 26-out sobre o PR #26;
- PRs #26 a #34 e os comentários do revisor;
- as 22 execuções do workflow "Testes" (todas verdes);
- o histórico de `main` e de `dados`;
- o arquivo `gamets/` e `sigmets/`;
- o relatório semanal W43.

## a. Resumo executivo

- **A app ficou bastante mais completa, mas houve um erro optimista real.**
  - Entraram 7 versões (3.10 → 4.5), mais a 4.5.1 hoje.
  - Os AIRMETs passaram a entrar na decisão (4.0), o pendente principal da W43.
  - O GAMET real 270900 deu **GO a 37 pontos do interior com VIS 200 m e base de 100 ft** (`… 11/15 MAR AND COT`). Foi corrigido no dia seguinte (4.1) e a seguir generalizado (4.3).
- **O piloto às cegas justificou-se esta semana.** Foi ele que apanhou o erro do 270900, e o `analisar.py` tinha dado 0 alertas, porque o oráculo usa os mesmos blocos do parser. Na W43 o piloto não tinha acrescentado nada.
- **Os SIGMETs oceânicos foram o problema da semana**, mas do lado pessimista:
  - os `OF LINE` de 31-out e 01-nov deram 7 h de NO-GO falso em todo o continente (corrigido na 4.5);
  - o `S OF N33`/`N34` de 01-nov deu mais 8 h (PR #33, contigo).
  - Ao mexer aqui, o revisor descobriu um erro **optimista** latente na margem de 10 NM, corrigido hoje (4.5.1).
- **Merge automático:** 2 merges automáticos (#27 pela excepção crítica, #34). Ambos correctos, 0 reversões, `main` sempre verde (22/22). Tudo o que era regra ou funcionalidade foi decidido por ti.
- **Recomendação principal:** manter o merge automático. Pôr como prioridade um teste de propriedade "SIGMET + 10 NM" e uma revisão sistemática dos formatos de SIGMET da série T/U, que nesta semana foi a principal fonte de erros.

## b. Recolha

### Por dia (data de arquivo)

| Dia | GAMETs | AMD/COR | SIGMET/AIRMET | Linhas em `falhas.log` | Anormais |
|---|---|---|---|---|---|
| 26 | 4 | 0 | 0 | 28 | 20 (`ConnectTimeout` 11:17–16:47Z) |
| 27 | 4 | 0 | 0 | 12 | 0 |
| 28 | 4 | 0 | 0 | 8 | 0 |
| 29 | 4 | 0 | 1 (SIGMET U01 291700/292100) | 12 | 0 |
| 30 | 4 | 0 | 0 | 28 | 20 (`ConnectTimeout` 03:37–09:08Z) |
| 31 | 4 | 0 | 2 (SIGMET T01 311035, T02 311330) | 10 | 0 |
| 01 | 4 | 0 | 6 (SIGMET T01–T06) | 11 | 0 |
| **Total** | **28** | **0** | **9 SIGMET, 0 AIRMET** | **109** | **40** |

A W43 teve 27 GAMETs, 5 SIGMET/AIRMET (3 + 2) e cerca de 22 linhas anormais.

### Buracos e falhas

1. **Falhas de ligação ao IPMA**, só informação: são do lado do IPMA e não há nada a fazer do nosso lado.
   - **26-out, 11:17–16:47Z (~5 h 30):** 20 `ConnectTimeout` em todos os endpoints. O GAMET 261500 foi arquivado ~2 h atrasado (16:50Z), mas não se perdeu.
   - **30-out, 03:37–09:08Z (~5 h 30):** 20 `ConnectTimeout`, mais 4 contados no dia 31. O 300300 e o 300900 foram arquivados. Se o IPMA emitiu algum SIGMET/AIRMET nesse intervalo e o cancelou antes das 09:08Z, falta no arquivo. Não há indício de que isso tenha acontecido.
2. Fora disso, só houve as janelas normais de ~30 min antes de cada emissão.
3. Os 28 GAMETs seguem-se sem buracos de validade. Nenhum boletim foi parar a `sigmets/desconhecidos/`.

### Workflows

- **"Recolha GAMET LPPC":** activo. A cadeia de `workflow_dispatch` funcionou toda a semana, e as `schedule` foram canceladas pelo grupo de concorrência, como previsto.
- **"Testes":** 22 execuções, 22 verdes.
- **"Publicar protótipo NiceGUI":** activo.

## c. Qualidade da app

### Erros encontrados, por gravidade

| # | Gravidade | Erro | Boletim real | Quem apanhou | Estado |
|---|---|---|---|---|---|
| E1 | **CRÍTICO (real)** | `HH/HH MAR AND COT` a meio do campo não abria subentrada. A superfície recortava a subentrada anterior e 37 pontos do interior ficavam GO, sem aviso | GAMET 270900/271500 (`09/11 W OF W00715 … BKN 001-004 … 11/15 MAR AND COT LCA 0400-5000M`) | piloto | Corrigido na 4.1 (#27, excepção crítica, 28-out 08:43Z) e generalizado na 4.3 (#30, contigo) |
| E2 | CRÍTICO latente | `… AGL 11/15 MAR` no fim da linha, ou antes de um qualificador, recortava a 1.ª subentrada pelo MAR | nenhum (variante do E1) | análise do E1 e o revisor | Corrigido na 4.3 |
| E3 | CRÍTICO latente | "Resto do período" optimista sem aviso quando uma parte da linha não tinha fenómeno; janela fora da validade ignorada | nenhum | revisor do #30 (4 rondas) | Corrigido na 4.3 |
| E4 | **CRÍTICO latente** | Margem de 10 NM dos SIGMET com qualificadores medida depois do recorte à FIR: pontos a 0,4–8 NM ficavam GO | nenhum (existia desde a 3.0) | revisor do #33 | Corrigido na 4.5.1 (#34, automático, 02-nov) |
| E5 | MENOR (pessimista, real) | SIGMET `D OF LINE …` dava toda a área: NO-GO no continente 31-out 10:35–13:30Z e 01-nov 04:50–08:50Z | T01 311035, T01 010450 | relatório (a app avisava) | Corrigido na 4.5 (#32, contigo) |
| E6 | MENOR (pessimista, real) | SIGMET `S OF N33`/`N34` (graus sem minutos) dava toda a área: NO-GO no continente 01-nov 08:50–16:50Z | T02 010850, T03 011250 | comparador, ao correr o GAMET com o arquivo | PR #33, "[Precisa do Duarte]" |
| E7 | MENOR (apresentação) | Nota "Nuvens baixas na Secção II" com base AMSL falava em "aeródromos abrangidos" | GAMET 301500 (AS/AC 6000 ft AMSL) | tu | Corrigido na 4.4 (#31) |
| E8 | Latente (optimista) | `BTN N3945 AND N3945` num SIGMET dá área vazia, sem aviso | nenhum | editor do #34 | Pendente (pergunta) |
| E9 | Latente (optimista, ligeiro) | Buffer do COT em graus: ~7,7 km em longitude em vez de 10 km | nenhum ponto afectado | comparador | Pendente (pergunta) |

**Funcionalidades novas** (todas decididas por ti):
- 4.0: AIRMETs na decisão (caso real de 25-out);
- 4.2: "Resto do período";
- 4.5: `D OF LINE`.

### Formatos novos vistos na semana

- SIGMET com `D OF LINE p1 - p2 [- …]`, com e sem AND, incluindo uma linha degenerada (`N3430 W01728 - N3430 W01728`), que parece gralha do IPMA.
- SIGMET com o qualificador só em graus: `S OF N33`, `S OF N34`.
- GAMET com a janela seguida de superfície a meio do campo (`… 11/15 MAR AND COT …`), no 270900.
- Secção II do 011500 com o WIND/T igual ao do 010900. É cópia do IPMA e não entra na decisão.

### Fenómenos ou campos ainda não cobertos

- Níveis dos SIGMET/AIRMET (`TOP FL400`, `SFC/FL080`): continuam a não restringir a decisão. Com a série T de TS a FL400 sobre o oceano, isto não pesa, porque a área já não toca o continente.
- `ENTIRE FIR` a meio da linha (#24, em pausa).
- `BTN` degenerado em SIGMET (E8).

### Padrões repetidos

- **A série T/U de SIGMETs oceânicos (Madeira e sul) apareceu em 4 dos 7 dias.** O IPMA escreve-a com formatos variados: `WI`, `OF LINE`, `S OF Nnn` e `S OF Nnnnn`. Cada formato novo caía em "toda a área". É conservador, mas tira credibilidade ao alerta.
- **Janelas `HH/HH` a meio da linha:** foram o E1 a E3. Desde a 4.3 a linha parte sempre que encontra uma, e há uma garantia contra a 4.2.

## d. Avaliação do processo com agentes

| Medida | W44 | W43 |
|---|---|---|
| GAMETs comparados | 28 | 27 |
| Aeródromos comparados | 1456 | 1404 |
| Em desacordo parser × piloto | 39 | 19 |
| Concordância | **97,3%** | 98,6% |
| Parser optimista | 37 (1 causa: E1) | 0 |
| Parser pessimista | 0 | 0 |
| Erro do piloto | 2 (1 causa: largura do COT) | 19 |
| Ambíguo | 0 | 0 |
| Falsos alarmes (erros do piloto ÷ diferenças) | **5%** (2/39), 1 de 2 causas | 100% |
| Erros do parser apanhados pelo piloto e não pelo `analisar.py` | **1 (E1, crítico)** | 0 |
| Agentes lançados | ~70 (28 piloto, ~26 comparador, 4 editor, ~12 revisor, contando as rondas) | ~60 |
| Agentes falhados ou com resposta incompleta | 0 | 0 |
| Tempo da tarefa diária | 12–50 min nos dias normais; ~2 h 15 hoje (2 PRs e o semanal) | 15–60 min |

**Leitura dos números:**
- **A concordância desce, mas por boa razão.** As 37 diferenças são o erro real do 270900, e os falsos alarmes do piloto caíram de 19 para 2. As instruções do piloto ficaram mais certeiras.
- **O que fica:** o piloto continua a não conhecer a largura do COT da app (10 km). Hoje usou ~25 km. Ou se diz isso ao piloto, ou se aceita como ruído. Prefiro **não** lhe dizer: a independência dele é o valor que traz.
- **O revisor continua a ser o agente mais produtivo.** Nesta semana encontrou o E3 e o E4 e travou 4 versões incompletas: duas rondas no #26, três no #30 e duas no #32. Hoje encontrou o erro optimista mais importante da semana, o E4, ao rever um PR do lado pessimista.
- **O comparador ultrapassou o que lhe foi pedido**, e foi útil. Hoje correu os GAMETs com os SIGMETs do arquivo e foi assim que apareceu o E6.
- **Às cegas:** os pilotos receberam só o texto do GAMET e o caminho do repositório. Vários disseram explicitamente que não leram saídas da app. Um leu o ficheiro do GAMET completo em vez do resumo, o que é aceitável: é o boletim, não o resultado.

## e. Merge automático, PR a PR

| PR | Versão | Como entrou | Porquê | Revisor | Comparação |
|---|---|---|---|---|---|
| #26 | 4.0 AIRMETs | contigo (26-out 19:08Z) | funcionalidade nova | DÚVIDA → REJEITADO → APROVADO | 0 mais permissivas, 25 mais severas |
| #27 | 4.1 | **automático** (excepção crítica, "[Entrou — escolha a confirmar]") | E1, escolha entre leituras, variante mais conservadora | APROVADO | 0 mais permissivas, 37 mais severas |
| #28 | (doc) | contigo | leitura A confirmada | — | — |
| #29 | 4.2 Resto do período | contigo | funcionalidade nova | DÚVIDA (só por ser nova) | 0/0 |
| #30 | 4.3 | contigo | pedido teu, com escolhas | DÚVIDA ×3 → APROVADO | 0/0 contra a 4.2 |
| #31 | 4.4 | contigo | texto pedido por ti | — | — |
| #32 | 4.5 `D OF LINE` | contigo | funcionalidade nova | REJEITADO ×2 → APROVADO | 96 mais permissivas, todas provadas (≥ 88 NM) |
| #33 | 4.6 graus | **aberto, "[Precisa do Duarte]"** | DÚVIDA do revisor (E4) | DÚVIDA | 153 mais permissivas, todas provadas |
| #34 | 4.5.1 margem | **automático** (02-nov 09:59Z) | correcção, só mais severa | APROVADO | 0/0 |

- **Reversões:** 0. O `main` ficou verde depois de cada merge.
- **Qualidade dos veredictos do revisor:** não houve nenhum APROVADO que depois se revelasse errado. Os REJEITADOS foram justos: no #26 o topo era lido como base, no #32 perdia-se a 2.ª posição e o MOV na diagonal encurtava a margem. A DÚVIDA de hoje no #33 era justa.
- **Decisões mais permissivas na semana:** 96 (#32) e 153 (#33). Estão todas provadas: vêm só dos SIGMETs oceânicos, a 88–178 NM da área do GAMET. Em ambos os casos a 4.x com o índice completo dá exactamente o mesmo que a versão anterior sem esses boletins.

## f. Riscos e incidentes

1. **E1: GAMET 270900/271500, 27-out 09–15Z.**
   - **Exposição real:** quem abriu a app viu **GO em 37 pontos do interior**, entre eles LPPT, LPEV, LPCO, LPCB, LPCH e LPBJ. Para as 11–15Z o GAMET dava VIS 200 m e base de 100 ft em MAR e COT de toda a FIR. Além disso, a leitura da 4.0 fazia cair a subentrada 09/11 W OF W00715 com base de 100 ft.
   - **Correcção:** entrou a 28-out às 08:43Z, quase 18 h depois do fim da validade.
   - **Lição:** o oráculo do `analisar.py` não apanha erros de partição de linhas. Só um leitor independente os apanha.
2. **E4, latente desde a 3.0 (17-out):** em teoria, até hoje a app podia mostrar GO a menos de 10 NM de um SIGMET definido por qualificadores, junto à fronteira. No arquivo nenhum boletim real tocava essa faixa, e a comparação da 4.5.1 deu 0 decisões alteradas.
3. **E2 e E3, latentes de 28-out:** não houve casos reais. Ficaram fechados no mesmo dia.
4. **Do lado pessimista** (não é risco de segurança, é risco de credibilidade): 15 h de NO-GO falso em todo o continente em 3 dias, por causa de SIGMETs oceânicos (E5 e E6).

## g. Recomendações

1. **Manter o merge automático tal como está.** Os dois merges automáticos estavam certos e tudo o que era regra passou por ti. Não vejo razão para o alargar nem para o apertar.
2. **Teste de propriedade "SIGMET + 10 NM"** para todos os formatos de área (WI, círculo, qualificadores, BTN, `OF LINE`, MOV), a correr na suite. O E4 sobreviveu duas semanas porque cada PR testava só o seu formato. O teste novo do #34 cobre os qualificadores; falta juntar WI e `LINE` ao mesmo verificador independente.
3. **Fechar a série dos SIGMETs oceânicos:**
   - decidir o #33;
   - decidir o E8 (`BTN` degenerado → toda a área com aviso);
   - rever a faixa "SIGMET ACTIVO" para SIGMETs a mais de 100 NM, que é o pendente 5 da W43.
4. **Instruções dos agentes:**
   - **piloto:** sem alterações. A largura do COT fica como ruído conhecido.
   - **comparador:** pôr no ficheiro do agente o que ele fez hoje por iniciativa própria, ou seja, correr também com `arquivo_hist` quando houver SIGMET/AIRMET no período.
   - **editor:** está a assinalar bem os erros fora do âmbito. Manter.
5. **Prioridade da semana:** o pendente 2 (níveis de SIGMET acima de FL150), que passou a ser a próxima causa provável de NO-GO falso com SIGMETs de TS sobre terra.

## h. Decisões do Duarte

**Nesta semana**

- **26-out:** AIRMETs na decisão com as regras normais, sem NO-GO automático (4.0, #26). Resolve o pendente 1 da W43.
- **28-out:**
  - **leitura A** da 4.1 (`HH/HH SUP` em toda a FIR), a revisitar se aparecer um caso real;
  - **4.2 "Resto do período"**, opção 2, com margem de 1 h;
  - **4.3**: a janela a meio da linha abre sempre subentrada. Uma parte só com valores herda a superfície; um `HH/HH SUP` + área deixa a subentrada anterior ambígua.
- **30-out:** as falhas de ligação ao IPMA ficam só como informação, sem propostas.
- **31-out:** nota de nuvens baixas AMSL fala do relevo (MEF) (4.4, #31).
- **01-nov:** `D OF LINE` como semiplano (4.5, #32).

**Pendentes**

1. **#33 (4.6):** com a 4.5.1 no main, a dúvida do revisor deixou de existir. Avanço com a actualização do ramo, nova revisão e merge?
2. `BTN` degenerado em SIGMET (E8) e buffer do COT em km (E9).
3. Níveis dos SIGMET acima de FL150 (W42/W43).
4. `ENTIRE FIR` a meio da linha (#24 em pausa).
5. Confirmar "LCA não suaviza a base" no `CLAUDE.md`.
6. Faixa "SIGMET ACTIVO" para SIGMETs fora da área.
7. 4.1, caso com superfície também na 1.ª parte (`09/11 MAR … 11/15 LAN …`): hoje é mais severo do que a leitura literal. Fica a confirmar se aparecer.
8. Seguimentos antigos: o do revisor do #12 e o alerta de recolha (W42 g.4).
