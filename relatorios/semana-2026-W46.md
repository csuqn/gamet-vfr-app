# Relatório semanal — 2026-W46 (9 a 15 de Novembro de 2026)

Quarta semana completa do processo com agentes. Para comparar, uso a W45.

**Fontes:**
- os relatórios diários de 10-nov a 15-nov, que cobrem as 24 h anteriores e portanto os dias 9 a 14, com as adendas de 10, 12 e 15-nov;
- o resumo do diário de 16-nov (cobre o dia 15), que ainda não está escrito no ramo `dados`;
- os PRs #44 a #49 e os comentários do revisor;
- as execuções do workflow "Testes" (todas verdes);
- o histórico de `main` e de `dados` (clone raso);
- o arquivo `gamets/`, `sigmets/` e `falhas.log`;
- o relatório W45 e o `CLAUDE.md` (4.8 a 5.0).

## a. Resumo executivo

- **Nenhum erro optimista do parser chegou ao main nesta semana.** Em 28 GAMETs e 1456 comparações, o parser e o piloto concordaram em 96,7% (W45: 100%). Os 48 desacordos têm só 2 causas: uma pessimista (`D OF LINE`, 10 pontos) e uma ambígua (CB colado à nuvem baixa, 38 pontos). Não houve nenhum erro do piloto.
- **A app passou da 4.7.6 à 5.0 em seis PRs, todos com merge feito por ti ou com o teu OK; não houve nenhum merge automático.** Entraram duas leituras novas (`D OF LINE` no GAMET, 4.8; CB sem localização própria em toda a FIR, 4.9), uma correcção pessimista dos SIGMETs (4.8.1), manutenção de testes e os limiares do AIP (5.0).
- **O maior efeito na segurança veio de mudanças de regra, não de erros:** a 4.9 põe 207 decisões do arquivo de GO em MARGINAL e a 5.0 torna 494 decisões mais severas. Nenhuma das duas tem decisões mais permissivas.
- **O processo funcionou onde mais importa.** O revisor travou dois caminhos optimistas antes de chegarem ao main: o `EXC` com `LINE` no #45 e o contra-exemplo do AMD no #46. O piloto, ao ler o CB às cegas de forma conservadora, levou à 4.9.
- **O ponto fraco são os testes do arquivo:** 3 vezes nesta semana falharam localmente com `dados/` e o CI ficou verde, porque não tem `dados/`. Hoje (5.0, com `dados/`) falham 4 testes, todos sentinelas do arquivo: 3 do `test_v49` (GAMET 151500) e 1 do `test_v48` (GAMET 160300, `LINE` na Secção II); o `test_v43` já passa.
- **Recomendação principal:** manter o merge automático tal como está. Prioridades: decidir os níveis dos SIGMET (o exemplo mais forte até agora: 37 pontos GO → NO-GO no 141500) e fazer o CI correr os testes do arquivo.

## b. Recolha

### Por dia (data de recolha)

| Dia | GAMETs | AMD/COR | SIGMET/AIRMET | Linhas em `falhas.log` | Anormais |
|---|---|---|---|---|---|
| 09 | 4 | 0 | 8 SIGMET (inclui o T07 082300/090300 de 8-nov, gravado às 02:26Z) | 16 | 9 `ConnectTimeout` (00:04–02:24Z, fim do episódio de 8-nov já contado na W45) |
| 10 | 4 | 0 | 5 SIGMET | 12 | 0 |
| 11 | 4 | 0 | 10 SIGMET | 12 | 0 |
| 12 | 4 | 0 | 0 | 16 | 0 |
| 13 | 4 | 0 | 0 | 9 | 0 |
| 14 | 4 | 0 | 3 SIGMET | 12 | 0 |
| 15 | 4 | 0 | 4 SIGMET | 12 | 0 |
| **Total** | **28** | **0** | **30 SIGMET, 0 AIRMET** | **89** | **9 (herdados de 8-nov)** |

- **Sem buracos de GAMET:** todos os períodos de 6 h, de 090300 a 160300, têm o seu GAMET. Não houve AMD nem COR.
- **`falhas.log`:** fora das 9 linhas de 9-nov, todas são "IPMA respondeu, mas sem GAMET do LPPC", nos ~45 min antes de cada emissão. Na W45 houve 11 anormais, mais 9 no dia 9; nesta semana não começou nenhum episódio novo de falha de ligação.
- **Nota sobre 12-nov:** as linhas "sem GAMET" começaram às 07:08Z e o 120900 só foi gravado às 08:54Z, uma janela de ~1 h 45 em vez dos ~45 min habituais. É só informação. Não faltou nada no arquivo.
- **SIGMET T06 de 8-nov:** continua sem aparecer no arquivo. O T07 de 8-nov foi gravado logo a seguir ao fim da falha de ligação. Também não se viu nenhum T06 a 9-nov (do T05 passou-se ao T07); a recolha esteve sempre a correr.
- `sigmets/desconhecidos/`: não existe. Não houve nenhum formato inesperado.
- **Workflows:** "Recolha GAMET LPPC", "Testes" e "Publicar protótipo NiceGUI (Hugging Face)" estão activos. A cadeia de recolha não parou. As 18 execuções do "Testes" desde 9-nov 09:06Z (PRs e main) estão todas verdes.
- **SIGMETs da semana (30):**
  - 9–11 nov: EMBD TS (série T) e SEV TURB (série U). Vários cruzaram o continente: T04/T05/T07 de 9-nov, T01/T03/T04 de 10-nov, T01/U02 de 11-nov e U06/U08/U09 de 11-nov (até 37 pontos na área).
  - 14–15 nov: só SEV TURB a FL240–420.
  - Todos foram lidos com área e MOV e ficaram em NO-GO só na sua área. O U08 (`S OF N3940 AND E OF W010`) foi o **primeiro boletim misto real** (minutos + só graus) e foi lido como a 4.6 prevê.
  - Não houve NO-GO falso em toda a FIR por área ilegível. Houve um em toda a área por SIGMET referido e já expirado (T01 de 11-nov, ver f.3).

## c. Qualidade da app

### Erros e mudanças (9–15 nov)

| # | Data | Gravidade | Erro / questão | Causa | Boletim real | Estado |
|---|---|---|---|---|---|---|
| G1 | 9-nov | CRÍTICO latente (vem da W45, F6) | Superfície a meio da linha recortava o valor anterior | `_cortes_janela` só partia em janelas | GAMET 081500 | Corrigido na 4.7.6 (#44, leitura A com o teu OK, 9-nov 23:54Z) |
| G2 | 10-nov | MENOR (pessimista, com aviso) | `D OF LINE` na Secção I → toda a FIR | A geometria das linhas só existia para os boletins (4.5) | GAMET 091500 | 4.8 (#45, funcionalidade pedida por ti; 10 pontos MARGINAL → GO, provados) |
| G3 | 11-nov | MENOR (pessimista) | SIGMET referido e expirado continuava a contar em toda a área se havia um boletim com o mesmo id do dia anterior | `sigmets_terminados` usava o T01 de 10-nov como "estado por provar" | GAMET 110300 + T01 de 10 e 11-nov | 4.8.1 (#46, variante do revisor, OK teu) |
| G4 | 11/12-nov | MENOR (testes) | 5 testes do arquivo falhavam com `dados/` | U01/U03 com a margem da 4.5.1, U08 misto e `SFC WIND` nos motores antigos | U01 110100, U03 110500, U08 111400, GAMETs 110900/111500 | Corrigido no #47 (só testes, pedido teu) |
| G5 | 14/15-nov | AMBÍGUO → mudança de regra | `ISOL TCU/CB` colado à última nuvem baixa herdava a área e a janela dela | Regra da 2.3 (linhas sem qualificador herdam a área) | GAMET 141500 (38 pontos GO) e outros 8 | 4.9 (#48, leitura conservadora decidida por ti; Anexo 3, Tab. A5-3, Nota 3) |
| G6 | 15-nov | MENOR (testes) | `test_v43::test_arquivo_analise_completa_e_resto` falha com `dados/` | A premissa "sem janelas a meio da linha no arquivo" deixou de valer | GAMET 142100 (`… AGL 21/24 N OF N4000 ISOL TCU/CB`) | Na 5.0 já passa (16-nov) |
| G7 | 15-nov | regra | Limiares de VIS e BASE abaixo do AIP | VIS 3000 m, base 300/500 ft | — | 5.0 (#49, pedido teu; merge 16-nov 00:45Z) |
| G8 | 15/16-nov | MENOR (testes) | 3 testes do `test_v49` falham com `dados/` | O conjunto fixo dos 12 GAMETs lidos de outra forma não inclui o 151500, que entrou no arquivo às 14:54Z | GAMET 151500 (`… 15/18 ISOL TCU/CB …`) | Pendente; na 5.0 continua a falhar (16-nov) |
| G8b | 16-nov | MENOR (testes) | `test_v48::test_arquivo_gamets_com_linha` falha com `dados/` | Conjunto fixo dos GAMETs com `LINE` não inclui o 160300 (`N OF LINE N3900 W01000 - N4100 W00600` na Secção II) | GAMET 160300 | Pendente; leitura verificada (nota em LPBG/LPSE/LP66, decisões iguais) |
| G9 | 16-nov | MENOR (só no script) | `analisar.py`: "Palavras desconhecidas" para `0800-5000`, `0300-5000`, `0200-5000` | VIS em intervalo sem `M`, que o vocabulário do script não conhece; o parser lê bem (800/300/200 m) | GAMETs 151500, 152100, 160300 | Pendente |

O G8 é o teste a fazer o que deve: o conjunto fixo existe para falhar quando aparece um GAMET novo lido de outra forma, para se confirmar a leitura. No 151500, o IPMA deu ao CB uma **janela própria** (`15/18`) diferente da do BKN 002 (`18/21`), mas não lhe deu área. Pela 4.9 (a janela não é qualificador próprio), o CB vai para toda a FIR e todo o período. Isto é mais severo do que a janela escrita. Precisa da tua confirmação (h.2).

### Formatos novos

- `D OF LINE` na Secção I (091500; antes só na Secção II e nos boletins).
- Boletim misto `S OF N3940 AND E OF W010` (SIGMET U08).
- Dois boletins com o mesmo id em dias UTC seguidos, ambos no arquivo das 24 h (T01 de 10 e 11-nov).
- VIS em intervalo sem unidade: `LCA 0800-5000 FG/BR` (151500, 152100, 160300).
- `N OF N3030 ISOL TCU/CB` (150300). É provavelmente uma gralha (fica a sul da FIR); a leitura literal dá toda a FIR, que é também a conservadora.
- CB com janela própria e sem área, depois de outra nuvem (`15/18 ISOL TCU/CB`, 151500).

### Fenómenos ainda não cobertos ou por decidir

- **Níveis dos SIGMET** (pendente desde a W42). Nesta semana houve os exemplos mais fortes até agora:
  - no 141500, o U02/U03 (SEV TURB FL310/420) pôs em NO-GO 37 pontos que estavam em GO pelo GAMET;
  - no 151500, com o U03 (FL240–400) às 15:30Z, passa de 10 para 40 NO-GO.
  - É conservador, mas o GAMET é BLW FL150.
- **Texto do aviso** "não referido no GAMET, provavelmente emitido depois dele" (15-nov): é inexacto para SIGMETs acima de FL150, que o GAMET não tem de referir. Só muda o texto.
- **`MT OBSC` sem olhar à altitude** (`ABV 020HFT AMSL`, 13-nov): põe NO-GO também em pistas costeiras baixas (LPIN, LPPR, LP62). É a regra escrita.
- **`EXC`/`OR` sem `LINE`** no GAMET: continuam sem leitura própria (revisor do #45).
- **`MOD/SEV`** continua a ser lido como SEV. Os pilotos fizeram a mesma leitura todos os dias.

### Padrões repetidos

- **O IPMA cola o CB à última linha de nuvem baixa** em quase todos os GAMETs da semana (121500 a 141500, 151500). Era o padrão mais frequente com efeito na decisão e ficou resolvido pela 4.9.
- **A estrutura das linhas continua a ser a área mais delicada:** superfície a meio (4.7.6), `D OF LINE` a abrir subentrada (4.8), CB sem qualificador (4.9) e janela própria sem área (151500).
- **Os testes do arquivo partem quando chegam dados reais novos** (G4, G6, G8). O CI não os corre, por isso só se dá por isso na tarefa diária.

## d. Avaliação do processo com agentes

| Medida | W46 | W45 |
|---|---|---|
| GAMETs comparados | 28 | 28 |
| Aeródromos comparados | 1456 | 1456 |
| Em desacordo parser × piloto | **48** (10 + 38) | 0 |
| Concordância | **96,7%** | 100% |
| Parser optimista (decisão) | 0 | 0 |
| Parser pessimista | 10 (1 causa: `D OF LINE`) | 0 |
| Erro do piloto | 0 | 0 |
| Ambíguo | 38 (1 causa: CB colado) | 0 |
| Falsos alarmes (erros do piloto ÷ diferenças) | **0%** (0/48) | — (0/0) |
| Erros do parser apanhados pelo piloto e não pelo `analisar.py` | 0 erros em sentido estrito. No `D OF LINE`, o `analisar.py` já avisava ("Área não reconhecida", `LINE`); o piloto deu a resposta certa ponto a ponto. O CB colado só o piloto viu, e levou à 4.9 | 0 com efeito; 1 latente (F6) |
| Problemas encontrados fora da comparação | G3 (a minha verificação dos SIGMETs); G4, G6 e G8 (suite local com `dados/`); 2 caminhos optimistas nas correcções (revisor) | F2, F5, F6 |
| Agentes lançados | ~56 registados: 28 piloto, 19 comparador, 3 editor, 4 revisor nos diários, mais pelo menos o editor e o revisor do #48. Para o #49 não há registo | ~55 |
| Agentes falhados ou com resposta incompleta | 0. Houve 3 lapsos de contagem de pilotos, sem efeito (111500: listou 10 em vez de 11; 15-nov: 28 em vez de 27 NO-GO; 16-nov: 24 em vez de 22), todos com a tabela certa | 0 |
| Tempo da tarefa diária | 30–40 min nos dias sem correcção; ~1 h 20 com correcção (11-nov). As adendas (#45, #47, #48) não estão cronometradas. 16-nov: não verificável | 11–20 min; 1 h 25 a 3 h 20 |

**Leitura dos números:**
- **Os 96,7% são melhores do que parecem.** Nenhum dos 48 desacordos foi um erro optimista do parser nem um erro do piloto. Os 10 do `D OF LINE` eram a app pessimista, com aviso. Os 38 do CB eram uma escolha de leitura, que resolveste a favor do piloto.
- **O piloto teve valor real nesta semana.** No 141500 escolheu de propósito a leitura conservadora e disse que a da app era a mais provável. O comparador classificou bem: AMBÍGUO, sem PR, pergunta para ti. É exactamente o caminho que as regras prevêem.
- **Comparadores:** de 13 a 15-nov lancei um só comparador para os 4 GAMETs, ou fiz a comparação ponto a ponto directamente quando os 52 coincidiam. A 16-nov voltei a um por GAMET. A 10-nov os comparadores receberam um resumo das tabelas dos pilotos e não as tabelas integrais. Não deu erro, mas é um risco.
- **Tempo:** a tarefa diária ficou mais longa nos dias sem correcção (30–40 min contra 11–20 min). Grande parte é a suite local com `dados/` (~13 min, 2 vezes a 10-nov). Os editores e revisores das adendas não entram nestas contas.
- **Às cegas:** os pilotos receberam o texto do GAMET e lêem as regras na tabela do `CLAUDE.md` (instrução do `piloto`). Por isso passaram a usar os limiares da 5.0 sem mudar as instruções. Nada indica que tenham visto saídas da app.

## e. Merge automático, PR a PR

| PR | Versão | Entrada | Porquê não foi automático | Revisor | Comparação de versões |
|---|---|---|---|---|---|
| #44 | 4.7.6 | com o teu OK (9-nov 23:54Z) | escolha de leitura (superfície qualifica o que vem a seguir) | DÚVIDA (formal); 2 reparos menores corrigidos em 43b72a5 | 0/0 (105 GAMETs); 1200 gerados sem nada mais permissivo |
| #45 | 4.8 | com o teu OK (10-nov 17:51Z) | funcionalidade nova; decisões mais permissivas | 1.ª DÚVIDA (Secção II perdia LPBG/LPSE/LP66; `ENTIRE FIR EXC N OF LINE` lido sem aviso, **caminho optimista**) → corrigido em 23b364a → 2.ª APROVADO | **10 mais permissivas, provadas** (091500, a 45–105 NM a sul da linha); 0 mais severas |
| #46 | 4.8.1 | teu OK à variante do revisor (12-nov 02:29Z) | revisor DÚVIDA: contra-exemplo **optimista** (AMD depois das 00Z com o T01 de ontem activo) | DÚVIDA → variante df1ec75 com o contra-exemplo como teste | 0/0 (o script não exercita a função); varrimento próprio de 102 casos: 0/0 |
| #47 | — (só testes) | a teu pedido (12-nov 13:10Z) | pedido teu | APROVADO (nenhum teste menos exigente; T02/T03 mais fortes) | n/a (`app.py` igual) |
| #48 | 4.9 | merge teu (15-nov 17:30Z) | mudança de regra | DÚVIDA formal; implementação correcta; 3 leituras-limite para confirmares | 0 mais permissivas; 207 mais severas (165 com `--indice`), todas GO → MARGINAL "CB ISOL" |
| #49 | 5.0 | merge teu (16-nov 00:45Z) | mudança de limiares | **sem veredicto registado no PR** (0 comentários, 0 reviews) | 0 mais permissivas; 494 mais severas em 26 GAMETs (468 MARGINAL → NO-GO, 26 GO → MARGINAL) |

- **Merges automáticos: 0** (W45: 5). Não era para haver nenhum: tudo foi funcionalidade nova, mudança de regra, escolha de leitura ou pedido teu. Nenhum PR ficou à espera indevidamente.
- **Reversões: 0.** O main esteve verde em todas as execuções do "Testes".
- **Qualidade dos veredictos do revisor:**
  - não aprovou nada que tenha falhado depois;
  - apanhou **dois caminhos optimistas** que o editor tinha introduzido: o `EXC` com `LINE` (#45) e o contra-exemplo do #46. Nos dois propôs a correcção que acabou por entrar;
  - no #48 separou bem a verificação técnica (correcta) da razão formal (regra);
  - não vi nenhuma rejeição errada.
- **Decisões mais permissivas na semana:** só as 10 do #45. A prova confirmou-se de forma independente: são exactamente os 10 pontos que o piloto do 091500 tinha posto em GO às cegas, e o comparador verificou a geometria.
- **Lacuna:** o #49 (limiares) entrou sem veredicto do revisor visível no PR. O corpo do PR traz a comparação de versões e diz "[Precisa do Duarte]", mas o título não. Não consigo verificar se houve revisão fora do PR.

## f. Riscos e incidentes

1. **CB colado à nuvem baixa (até 15-nov 17:30Z).** Pela leitura que adoptaste na 4.9, a app esteve mais permissiva do que devia em 9 GAMETs reais, de 12-nov 15Z a 14-nov 21Z. No total são 207 decisões GO que agora são MARGINAL "CB ISOL" (165 com os SIGMETs arquivados). O pior foi o **141500**: 38 dos 52 pontos em GO com `ISOL TCU/CB` previsto sem localização. Não era um erro da regra então escrita (2.3), mas o efeito na prática foi optimista. Com fonte `ipma`, o U02/U03 punha a maior parte desses pontos em NO-GO durante o 141500, por outro motivo (ver 4).
2. **Limiares anteriores à 5.0 (até 16-nov 00:45Z).** Com VIS MARGINAL < 3000 m e base NO-GO < 300 ft / MARGINAL < 500 ft, a app estava abaixo do mínimo VMC do SERA no espaço G (5 km) e da regra dos 500 ft do ENR 1.2. No arquivo (130 GAMETs, desde Outubro) isso dá 494 decisões agora mais severas, em 26 GAMETs. Não sei quantas são desta semana. Nos diários aparecem vários casos com efeito na leitura de então: "VIS 3000 m no limiar → sem efeito" (13, 14 e 15-nov) e bases LCA de 400 ft como MARGINAL.
3. **SIGMET T01 de 11-nov (antes da 4.8.1).** Foi pessimista: das 05Z às 09Z, com fonte `ipma`, o 110300 dava NO-GO em toda a área por um SIGMET já expirado. As decisões não mudaram, porque o GAMET já era NO-GO em todo o lado. A primeira correcção (494a4fc) tinha um caminho **optimista** (AMD com o T01 de ontem activo). O revisor travou-o e nunca chegou ao main.
4. **Níveis dos SIGMET (pessimista, conhecido).** O U02/U03 a FL310–420 pôs em NO-GO 37 pontos GO no 141500; o U03 a FL240–400 passa o 151500 de 10 para 40 NO-GO às 15:30Z.
5. **Superfície a meio da linha (F6)** esteve no main até 9-nov 23:54Z. Só existia o 081500 no arquivo, sem efeito.
6. **`D OF LINE` antes da 4.8** foi pessimista e com aviso (10 pontos MARGINAL a mais no 091500).
7. **Testes do arquivo cegos no CI.** De 11-nov a 12-nov 13:10Z falharam 5 localmente; desde 15-nov falha o `test_v43` e, desde a entrada do 151500, 3 do `test_v49`. O check ficou sempre verde. Nenhuma destas falhas era um erro da app, mas uma regressão real no arquivo também passaria no CI.
8. **Corrida da NiceGUI (F7)** continua latente, na interface de reserva.

## g. Recomendações

1. **Manter o merge automático sem mudanças.** Em 4 semanas houve 9 merges automáticos e 0 reversões. Nesta semana a regra "na dúvida não entra" travou 2 caminhos optimistas (#45, #46). **Ajuste pequeno:** qualquer PR que mexa em regras ou limiares deve ter o veredicto do revisor escrito no próprio PR antes do merge, mesmo que sejas tu a fazê-lo (faltou no #49).
2. **CI com os testes do arquivo.** Proposta: um passo no "Testes", ou um workflow diário, que faça checkout do ramo `dados` e corra os testes do arquivo. Três vezes nesta semana só a tarefa diária deu pelas falhas. É funcionalidade nova, por isso **pergunto-te antes**.
3. **`analisar.py`: aceitar VIS em intervalo sem unidade** (`\d{4}-\d{4}` antes de um tempo presente) no vocabulário. É só no script, o parser já lê bem desde a 2.5, e evita 3 falsos alarmes por dia em dias de nevoeiro.
4. **Comparação ponto a ponto em script.** Um script determinístico que lê a tabela do piloto e a saída da app e lista os pontos diferentes. O comparador (agente) fica só para classificar as diferenças. Justificação:
   - os 3 lapsos de contagem dos pilotos teriam sido apanhados automaticamente;
   - acaba o risco de dar ao comparador um resumo em vez da tabela integral (10-nov);
   - poupa tempo na tarefa diária.
   Mantém-se a independência do piloto.
5. **Manutenção de testes (G6, G8).** Confirmar a leitura do 151500 e do 142100 e actualizar o conjunto fixo e a premissa do `test_v43`. É o mecanismo previsto, não é ajustar ao output.
6. **Prioridades técnicas para a W47:**
   - decidir os níveis dos SIGMET (exemplos fortes nesta semana);
   - texto do aviso dos SIGMETs não referidos acima de FL150;
   - corrida da NiceGUI (F7);
   - aviso "Campo desconhecido" (proposto na W45, ainda sem resposta).

## h. Decisões do Duarte

**Nesta semana**

- **9-nov:** leitura A no #44 (4.7.6): a superfície a meio da linha qualifica o que vem a seguir.
- **10-nov:** "sim" a ler `D OF LINE` no GAMET (4.8). Confirmaste a quebra antes de `D OF LINE` e o AS/AC da Secção II do 091500 (#45).
- **12-nov:** 4.8.1 com a variante do revisor: um boletim de outro dia, sobreposto e activo, continua a bloquear (#46).
- **12-nov:** corrigir as 5 falhas dos testes do arquivo (#47).
- **15-nov:** CB/TCU sem localização própria em SIG CLD vale em toda a FIR e todo o período (4.9, #48, Anexo 3). Fizeste o merge às 17:30Z.
- **15-nov:** limiares pelo AIP: VIS MARGINAL < 5000 m, base NO-GO < 500 ft e MARGINAL < 1000 ft; nota da Secção II a < 1000 ft AGL e AMSL a < 500 ft do MEF (5.0, #49). Fizeste o merge a 16-nov 00:45Z.

**Pendentes**

1. **#48, leituras-limite do revisor** (não encontrei confirmação explícita, só o merge):
   - as bases depois do grupo CB na mesma parte vão com ele;
   - só conta o 1.º grupo CB da linha;
   - uma superfície antes da outra nuvem não protege o CB.
2. **151500:** o CB com janela própria (`15/18`) e sem área vai para toda a FIR **e todo o período**. Confirmas, ou a janela escrita deve contar? A resposta decide o conjunto fixo do `test_v49` (G8).
3. **160300 no conjunto fixo do `test_v48`** (G8b): acrescentar como GAMET com `LINE` só na Secção II? (O `test_v43` com o 142100, G6, já passa na 5.0.)
4. **CI com os testes do arquivo** (g.2): queres?
5. **Níveis dos SIGMET acima de FL150** (desde a W42).
6. **Aviso "Campo desconhecido"** na Secção I (W45).
7. **Corrida da NiceGUI (F7).**
8. **Herdados:**
   - `EXC`/`OR` sem `LINE` no GAMET;
   - `S OF N38` só com graus na Secção I;
   - `MT OBSC` sem olhar à altitude;
   - `ENTIRE FIR` a meio da linha (#24 em pausa);
   - "LCA não suaviza a base" no `CLAUDE.md` (a tabela continua a falar só da VIS);
   - faixa "SIGMET ACTIVO" para SIGMETs fora da área;
   - 4.1 com superfície também na 1.ª parte.

**Teste local com `dados/` na 5.0 (16-nov):** 4 falhas, todas sentinelas do arquivo (3 `test_v49` com o 151500, 1 `test_v48` com o 160300); o resto passa. CI verde.
