# Relatório semanal — 2026-W47 (16 a 22 de Novembro de 2026)

Quinta semana completa do processo com agentes. Comparo com a W46.

Este relatório devia ter saído na segunda-feira, 23-nov, mas só foi escrito a 24-nov, juntamente com os diários de 22 e 23-nov, que também ficaram por fazer porque o plano esgotou.

**Fontes:**
- os relatórios diários de 17 a 23-nov (cobrem os dias 16 a 22) e as respectivas "Métricas";
- os PRs #50 a #66 e os comentários do revisor;
- o histórico de `main` e de `dados`;
- `gamets/`, `sigmets/` e `falhas.log`;
- o relatório da W46.

## a. Resumo executivo

- **A app esteve fiável na leitura.** Em 28 GAMETs e 1456 comparações ponto a ponto, o parser e o piloto às cegas concordaram em **100%** (W46: 96,7%). Não houve nenhum erro do parser, optimista ou pessimista, nem nenhum erro do piloto.
- **Foi a semana com mais mudanças de regra até agora.** A app passou da 5.0 à **7.0**:
  - 5.1 a 5.1.5: novo briefing, só apresentação;
  - 6.0: SIGMETs acima do FL195 passam a informativos;
  - 6.0.1: o CB colado com janela própria fica só nessa janela;
  - 6.0.2: o SIGMET da véspera expirado deixa de contar;
  - 6.1: aviso "Campo desconhecido";
  - 7.0: **GO COND.** para fenómenos severos só a partir do FL100.

  Todas foram decisões tuas e entraram contigo ou a teu pedido, com o revisor no PR.
- **Merge automático:** 3 PRs, todos só de testes (#60, #62, #65), todos com o revisor APROVADO e o CI verde. Não houve reversões.
- **O processo com agentes funcionou, mas com pouco valor acrescentado nesta semana.** Sem erros do parser, o piloto não apanhou nada que o `analisar.py` não apanhasse. O script `comparar_piloto.py` (#61, recomendação g.4 da W46) passou a fazer a contagem de forma determinística, e isso tirou trabalho e erros de contagem ao comparador.
- **O ponto fraco continua a ser o mesmo da W46: os testes do arquivo.** Os GAMETs novos partem testes que comparam o arquivo inteiro e o CI não o vê, porque corre sem `dados/`. Foram 4 PRs só de testes em 9 dias (#50, #60, #62, #65), mais o #67 a 24-nov.
- **Falha do processo nesta semana:** três tarefas diárias não correram (22, 23 e 24-nov de manhã) por falta de plano. A app e a recolha continuaram a funcionar, mas ninguém esteve de vigia durante esse tempo.
- **Recomendação principal:** manter o merge automático e tratar os testes do arquivo (ver g.1). As regras da 7.0 são novas e a próxima semana deve olhar para elas com atenção.

## b. Recolha

| Dia | GAMETs | AMD/COR | SIGMET | AIRMET | Linhas em `falhas.log` | Anormais |
|---|---|---|---|---|---|---|
| 16 | 4 | 0 | 3 (U02, U04, U05) | 0 | 8 | 0 |
| 17 | 4 | 0 | 1 (I01) | 0 | 12 | 0 |
| 18 | 4 | 0 | 4 (I01, I02, U01, U02) | 0 | 13 | 0 |
| 19 | 4 | 0 | 3 (U01, U02, U03) | 0 | 8 | 0 |
| 20 | 4 | 0 | 2 (U01, I01) | 0 | 11 | 0 |
| 21 | 4 | 0 | 5 (U02 202355, U01, T01, U02 211130, U03) | 0 | 12 | 0 |
| 22 | 4 | 0 | 0 | 0 | 8 | 0 |
| **Total** | **28** | **0** | **18** | **0** | **72** | **0** |

- **Sem buracos de GAMET.** Todos os períodos de 6 h entre 160300 e 222100 têm o seu GAMET.
- **`falhas.log`.** Todas as linhas são "O IPMA respondeu, mas sem GAMET do LPPC", nos ~30–45 min antes de cada emissão. Não houve falhas de ligação ao IPMA (na W46 houve 9, herdadas de 8-nov).
- **`sigmets/desconhecidos/`:** não existe.
- **Workflows.**
  - "Recolha GAMET LPPC": activo; a cadeia de execuções não parou.
  - "Testes": verde no main em todos os merges.
  - "Publicar NiceGUI": activo.

## c. Qualidade da app

### Erros encontrados

| Gravidade | Erro | Boletim real | Estado |
|---|---|---|---|
| — | Nenhum erro do parser confirmado | — | — |
| MENOR (pessimista, regra) | SIGMET da véspera referido no GAMET, já expirado, forçava NO-GO em toda a área durante 5 h | GAMET 210300 de 21-nov com o U02 202355/210355 de 20-nov | Corrigido na 6.0.2 (#63), a teu pedido |
| MENOR (apresentação) | `SCF/FL060` (gralha de `SFC`) deixava a TURB sem camada no motivo | GAMETs 162100, 170300 e 170900 | Decidiste não corrigir (17-nov) |
| MENOR (gralha) | `AGLL` numa base de CB | 201500 | Base lida, sem efeito |
| MENOR (só testes) | Conjuntos fixos do arquivo desactualizados | 15/16-nov, U03 192100, 202100, 210900 | #50, #60, #62 e #65 |

### Formatos novos

- `AGLL` (21-nov).
- SIGMET TURB com limite inferior entre FL160 e FL180 (U02 211130), já lido pela 7.0 como GO COND.
- Já fora da semana (23-nov): `SFC WIND:` com conteúdo de VIS e `N OF N2300`.

### Fenómenos ainda não cobertos

- Uma VIS escrita no campo `SFC WIND` (23-nov): a app avisa, mas não a usa na decisão.
- Nomes de campo desconhecidos sem `:`. Continuam em silêncio desde a 6.1; não há nenhum caso no arquivo.

### Padrões repetidos

- As bases LCA < 500 ft aparecem em quase todos os GAMETs com nuvem baixa. Em quase todos os dias os pilotos perguntam se o LCA devia atenuar a base. A app e os pilotos aplicam a regra escrita (NO-GO), por isso não há desacordo, mas a pergunta repete-se.
- `MOD/SEV` aparece em quase todos os dias e é sempre lido como SEV.

## d. Avaliação do processo com agentes

| Métrica | W47 | W46 |
|---|---|---|
| GAMETs analisados | 28 | 28 |
| Comparações ponto a ponto | 1456 | 1456 |
| Concordância parser × piloto | **100%** (0 desacordos) | 96,7% (48) |
| Parser optimista / pessimista / piloto / ambíguo | 0 / 0 / 0 / 0 | 0 / 10 / 0 / 38 |
| Taxa de falsos alarmes (erros do piloto ÷ diferenças) | n/a (0 diferenças) | 0% |
| Erros do parser apanhados só pelo piloto | 0 | 2 causas (`D OF LINE`, CB colado) |
| Agentes lançados (diários) | ~46: 28 piloto, ~10 comparador, ~8 revisor, 0 editor | — |
| Agentes que falharam ou com resposta incompleta | 0 | 0 |
| Tempo por tarefa diária | 25–55 min | 25–35 min |

- **Os pilotos ficaram às cegas.** Cada piloto recebeu só o texto do GAMET e o caminho do repositório, e todos disseram que não leram resultados da app nem a memória.
- **Contagens.** Três pilotos erraram a contagem no resumo (20-nov), mas as tabelas estavam certas. Desde 20-nov a contagem vem do `comparar_piloto.py` e esse risco desapareceu.
- **Valor acrescentado.** Nesta semana foi zero em erros apanhados. Continua a ter valor como verificação independente de que as regras novas não mudaram a leitura: a 7.0 foi comparada com pilotos a 22 e 24-nov e deu 0 diferenças.
- **Custo.** Os GAMETs `HAZARDOUS WX NIL` (3 a 22/23-nov) gastam um piloto cada sem quase nenhum valor (ver g.3).

## e. Merge automático, PR a PR

| PR | O quê | Entrou como | Revisor | Comparação de versões |
|---|---|---|---|---|
| #50 | Testes do arquivo: conjuntos fixos de 15/16-nov | Fora do diário, por ti | — | motor igual |
| #51 | CLAUDE.md: revisor obrigatório no PR em mudanças de regra | Por ti | — | — |
| #52–#57 | 5.1 a 5.1.5: briefing novo, origem da base, mapa clicável, motivo SIGMET legível | Por ti (funcionalidades) | no PR | 0/0 (só apresentação) |
| #58 | 6.0: SIGMETs TURB/ICE/MTW SEV acima do FL195 informativos | Por ti (regra) | APROVADO depois de 4 revisões (lista branca, cabeçalho ancorado) | mais permissivas só nos 17 SIGMETs altos, provadas |
| #59 | 6.0.1: CB colado com janela própria | Por ti (decisão h.2) | APROVADO | 0/0 na decisão principal |
| #60 | test_v60: U03 192100 no conjunto fixo | **Automático** | APROVADO | motor igual |
| #61 | `scripts/comparar_piloto.py` (g.4 da W46) | Por ti (funcionalidade) | — | motor igual |
| #62 | test_v49: 202100 no `CB_SOLTO` | **Automático** | APROVADO | 0/0 |
| #63 | 6.0.2: SIGMET da véspera expirado | A teu pedido (regra) | APROVADO | 110 mais permissivas (fonte `ipma`), todas provadas e todas no 210300 |
| #64 | 6.1: aviso "Campo desconhecido" | Por ti (funcionalidade) | APROVADO | 0/0 (só aviso) |
| #65 | conftest: motivos repetidos sem camada | **Automático** | APROVADO | motor igual |
| #66 | 7.0: GO COND. a partir do FL100 | Por ti (regra) | APROVADO (revisor do PR + agente `parser`) | mais permissivas só onde há motivo condicional; nunca abaixo de GO COND. |

- **Reversões:** 0. O main ficou verde depois de cada merge.
- **Qualidade do revisor.** Nesta semana não aprovou nada que não devesse. No #58 rejeitou três versões com caminhos optimistas: o corte do cabeçalho apagava `EMBD TS`, `SFC/FL100` e `TSRA`. É o exemplo mais claro do valor do revisor desde a W45.
- **Decisões mais permissivas.** As da 6.0, da 6.0.2 e da 7.0 vêm de regras pedidas por ti e foram todas provadas no PR. Não há nenhuma por provar.

## f. Riscos e incidentes

- **Não conheço nenhum caso em que a app tenha estado mais permissiva do que devia.**
- **Regras novas em que a app ficou mais permissiva de propósito:** 6.0, 6.0.2 e 7.0. A 7.0 é a de maior alcance: um SIGMET de ICE/TURB a partir do FL100 deixa de dar NO-GO e passa a GO COND. com tecto.
  - O agente `parser` testou 25 caminhos optimistas e todos ficam como na 6.1. Ainda assim, só há uma semana de boletins reais com ela.
  - Nos dias 22 e 24-nov a 7.0 leu bem 3 SIGMETs condicionais reais (U02 211130, U01 240330, U02 240730) e manteve NO-GO nos de limite abaixo do FL100 (U03 SFC/FL080, I01 FL080/200).
- **Pessimista:** o 210300 de 21-nov ficou 5 h em NO-GO em toda a área (U02 da véspera). Corrigido na 6.0.2.
- **Processo:** entre 22-nov às 08:00 e 24-nov às 17:30 não houve tarefa diária. Se houvesse um erro do parser nesse intervalo, só seria detectado com dois dias de atraso. A verificação a posteriori deu 0 diferenças em 12 GAMETs.

## g. Recomendações

1. **Testes do arquivo no CI.** É a mesma recomendação da W46, e o problema agravou-se: 5 PRs só de testes em 9 dias. Há duas saídas:
   - (a) o workflow "Testes" passa a fazer checkout do ramo `dados` e corre os testes do arquivo, para as falhas aparecerem no próprio dia;
   - (b) o diário passa a actualizar os conjuntos fixos sozinho, com o revisor, como já faz.

   A (a) é a mais segura.
2. **Manter o merge automático tal como está.** Só entraram PRs de testes, todos aprovados, e nenhum foi revertido.
3. **Reduzir o custo do diário**, já que o plano esgotou. Quando a Secção I é `HAZARDOUS WX NIL`, não lançar o piloto: o resultado é trivialmente GO e o `comparar_piloto.py` pode comparar com uma tabela gerada. Isto é uma mudança às instruções da tarefa, por isso decides tu.
4. **Prioridades para a W48:**
   - vigiar se a VIS dentro de `SFC WIND` (230900 de 23-nov) volta a aparecer (decidiste a 24-nov não alterar por agora);
   - acompanhar os primeiros GO COND. reais da 7.0 nos briefings;
   - rever se a pergunta repetida dos pilotos sobre a base LCA merece uma regra ou só uma nota no CLAUDE.md.

## h. Decisões do Duarte

**Tomadas nesta semana:**
- 16-nov: o revisor é obrigatório no próprio PR em mudanças de regra ou limiares (#51).
- 17-nov: não corrigir a gralha `SCF/FL060`; briefing novo 5.1 (maqueta, 2.ª proposta).
- 18 e 19-nov: base com AGL e de onde vem (5.1.1/5.1.2); tocar numa zona escolhe-a (5.1.3); trocar de zona sem recarregar (5.1.4); o motivo SIGMET diz o que avisa (5.1.5).
- 19-nov: níveis dos SIGMET — acima do FL195 informativo (6.0).
- 20-nov: h.2 "como for mais lógico e real" (6.0.1); script de comparação ponto a ponto (g.4); aviso "Campo desconhecido" (6.1).
- 21-nov: SIGMET da véspera em vigor no início do GAMET serve de prova (6.0.2); GO COND. com margem de 1000 ft, só a partir do FL100, entre GO e MARGINAL, também no GAMET e não no AIRMET (7.0).

**Decidida já depois da semana:**
- 24-nov: VIS escrita em `SFC WIND` (230900) — não alterar; corrigir só se voltar a aparecer.

- 24-nov: testes do arquivo no CI (g.1) e GAMETs NIL sem piloto (g.3) — **não alterar o processo**, fica como está (PR #68 fechado sem merge).

**Pendentes:** nenhuma.
