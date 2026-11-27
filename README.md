# Dados do teste com GAMETs reais

Ramo separado do `main` para que cada recolha não reinicie a app publicada.

- `gamets/AAAA/MM/` — GAMETs recolhidos de hora a hora pelo GitHub Actions
- `gamets/*_historico.txt` — GAMETs reais anteriores (reconstruídos dos briefings em PDF)
- `gamets/AAAA/MM/*_manual.txt` — GAMETs reais **inseridos à mão**, não recolhidos pelo GitHub Actions. O texto foi copiado da página do IPMA e normalizado como na recolha (espaços). No nome do ficheiro, a hora é a da inserção e não a da emissão.
  - `20261126T1233Z_260900-261500_manual.txt` — GAMET 260900/261500 COR. Colado pelo Duarte a partir do site do IPMA durante a falha do certificado de `brief-ng.ipma.pt` (14:13Z de 25-nov a 14:25Z de 26-nov), em que a recolha não conseguiu ligar-se. Ver `relatorios/2026-11-26.md`.
- `relatorios/` — relatório diário
