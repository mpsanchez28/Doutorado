# Auditoria da seleção temporal das sementes, dos alvos e do corpus

Branch `research/t1-t4-robustez`. Referência histórica preservada em `477dcd1`: nenhum
dataset, configuração ou resultado anterior foi alterado. Tudo o que é novo está em
`runs/robustez/` e nos scripts e documentos citados.

**Legenda de estado:**
- **[implementado]**: código existe;
- **[executado]**: rodou nas bases indicadas;
- **[verificado]**: tem checagem independente, como reprodução de resultado gravado ou
  validação de KG;
- **[planejado]**: ainda não implementado.

## 1. Mecanismo completo de seleção (como foi executado)

Fonte: `collect/openalex.py › seeded_collect` e `expand_candidates`,
`scripts/subset_seeds.py`, `scripts/hygiene.py`, `data/hygiene.py`, `configs/bases.yaml`.

| Etapa | O que faz | Parâmetros efetivos |
|---|---|---|
| 1. Quadro de amostragem | trabalhos da área no OpenAlex: campo do *primary topic*, idioma inglês, publicação ≥ 2004, **sem limite superior de ano** | estado do OpenAlex na data da coleta (out/2026) |
| 2. Sorteio de trabalhos | `sample(2000, seed=s)` da API: 2.000 trabalhos uniformes no quadro | as 1.000 sementes usadas vieram todas do sorteio **s = 42** (as 4 bases) |
| 3. Extração de autores | de cada trabalho, os autores **com ORCID no OpenAlex** e ainda não vistos | ORCID: ligação atual autor–ORCID do OpenAlex |
| 4. Um autor por trabalho | se houver mais de um elegível, sorteia 1 (`random.Random(42)`) | evita privilegiar equipes grandes |
| 5. Rejeições | trabalho sem nenhum autor com ORCID ainda não visto → descartado | Economia: 1.152 sementes possíveis dos 2.000 trabalhos do sorteio 42 (848 trabalhos rejeitados); Matemática: 1.415; Medicina e Computação: ≥ 1.000 (a coleta parou antes de esgotar o sorteio) |
| 6. Deduplicação | `seen_cand`: um autor sorteado não volta (entre trabalhos e entre sorteios) | — |
| 7. Embaralhamento e ordem | candidatos a semente embaralhados (`rng.shuffle`) e processados em lotes de 50; `order` = posição | aleatório, sem relação com tempo |
| 8. Parada | `max_seeds = 1000` (Medicina, Computação). Economia e Matemática foram coletadas antes com outro critério (2.930 e 2.765 sementes de 3 e 2 sorteios) e **reduzidas às 1.000 primeiras pela ordem** (`subset_seeds.py`), todas do sorteio 42 | subamostra aleatória da ordem |
| 9. Histórico das sementes | todos os trabalhos da área de cada semente, 2004–2026 | completo |
| 10. Candidatos | `select_candidates`: coautores das sementes em trabalhos **≤ 2021**, dentro do teto de 50 autores; priorizados pelo nº de trabalhos em comum até 2021; desempate aleatório (semente 42); teto de 15 mil | teto atingido nas 4 bases |
| 11. Expansão | histórico de cada candidato na área em **2017–2021** | — |
| 12. Limpeza | idioma, ano ≥ 2004, campos obrigatórios (**inclui resumo**) | metadados atuais |
| 13. Higienização | pessoa canônica = ORCID; níveis A/B/C/X; X (nome incompatível ou conflito) sai do corpus | ORCID atual (cache) |
| 14. Elegibilidade E1–E8 | calculada sobre **todos os anos** (2004–2026) | ver §3 |
| 15. Alvos | semente ∩ elegível; na avaliação, ≥ 1 coautoria nova em T1 | — |

**Amostragem de trabalhos × amostragem de autores.** O sorteio é **uniforme entre
trabalhos** (etapa 2), não entre autores. A probabilidade de um autor *a* virar semente é,
aproximadamente, proporcional a

  Σ sobre os trabalhos *w* de *a* no quadro de 1/kʷ,

em que kʷ é o número de autores de *w* com ORCID ainda não vistos. Consequências:

- **Viés de produtividade:** quem tem mais trabalhos na área no quadro (2004–2026) tem mais
  chances. É uma amostragem **por tamanho**, não uniforme entre pesquisadores.
- **Viés de recência:** o volume de publicações e a adoção do ORCID crescem com o tempo, então
  autores ativos em anos recentes têm mais chances.
- **Viés de ORCID:** só entra quem tem ORCID ligado no OpenAlex **hoje**.
- **Equipes:** o 1/kʷ reduz o peso de equipes grandes, mas não o elimina, porque a
  participação em muitos trabalhos ainda soma.

Esses vieses são **descritos** aqui, mas **não quantificados** contra a população. Isso
exigiria o quadro completo de autores da área. Uma quantificação parcial é possível
**[planejado]**: reproduzir os sorteios (`sample` com semente é reprodutível; ~10 consultas
por sorteio por base) e registrar os trabalhos rejeitados e o kʷ de cada um.

## 2. Quais etapas usam informação posterior a um corte c

| Etapa | Usa informação posterior a c? | Como |
|---|---|---|
| 1–2 Quadro e sorteio | **sim** | trabalhos de (c, 2026] estão no quadro. ~30% das sementes vieram de trabalhos de 2022–2026 (corte 2021) |
| 3 ORCID na extração | **sim** (metadado atual) | ligação autor–ORCID de hoje; a pessoa pode ter criado o ORCID depois de c |
| 4–8 Um por trabalho, deduplicação, ordem, parada | não, por si mesmos | mas operam sobre o quadro da etapa 1 |
| 9 Histórico das sementes | não, desde que cortado em c | os fatos ≤ c são usados no KG; os de (c, c+H] viram rótulos |
| 10 Candidatos | **não para c = 2021; sim para c < 2021** | laços contados até 2021. A priorização pelo teto também |
| 11 Expansão | **sim para c < 2021** (janela inclui anos > c); **incompleta para c > 2021** | janela fixa 2017–2021 |
| 12 Limpeza | **sim** (metadado atual) | exigência de resumo, idioma e campo com os metadados de hoje |
| 13 Higienização | **sim** (metadado atual) | ORCID de hoje: reivindicações e nomes; desambiguação atual do OpenAlex |
| 14 Elegibilidade | **sim** | E5/E6/E8 contam trabalhos > c; E3 usa reivindicações feitas até hoje (inclusive de trabalhos > c); E4 e E7 idem |
| 15 Alvos | rótulos em T1 (correto) | — |
| Atributos do modelo | não para fatos (KG ≤ c validado); **sim para metadados** | tópicos (classificador de 2024), instituições e hierarquia ROR atuais, referências completadas depois, TF-IDF ajustado só em textos ≤ c |
| M9 | usa nomes de T0 e T1 (correto: limpa o gabarito) | — |

## 3. Elegibilidade recalculada com publicações até 31/12/2021

**[implementado] [executado nas 4 bases] [verificado]** `scripts/auditoria_elegibilidade_2021.py`.
O script refaz a higienização dos trabalhos das sementes a partir do bruto e do cache do
ORCID, sem chamadas.

**Verificação:** com todos os anos, o recálculo reproduz a elegibilidade gravada em 100%
(Economia, Matemática), 99,9% (Computação) e 99,7% (Medicina). As poucas divergências vêm de
fragmentos de ORCID que só aparecem nos trabalhos dos candidatos, fora do recorte do
recálculo.

**Classificação das 1.000 sementes no corte de 2021:**
- **mantida**: elegível só com autorias ≤ 2021. *Condicional*: E1 e E3 ainda dependem do
  retrato atual do ORCID.
- **excluída**: reprova algum critério com dados ≤ 2021.
- **indeterminada**: sem registro ORCID no cache (E3 e a confirmação de nome pelo ORCID não
  são avaliáveis).

| | Medicina | Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Elegíveis (gravado, todos os anos) | 487 | 507 | 535 | 465 |
| Mantidas (elegíveis ≤ 2021) | 419 | 405 | 443 | 370 |
| Excluídas | 569 | 581 | 527 | 577 |
| Indeterminadas | 12 | 14 | 30 | 53 |
| **Elegíveis gravadas que saem em 2021** | **99** | **112** | **95** | **97** |
| Inelegíveis gravadas que entram em 2021 | 31 | 10 | 3 | 2 |
| Mantidas **e** sorteadas por trabalho ≤ 2021 | 310 | 297 | 344 | 313 |

Valores em `runs/robustez/auditoria/elegibilidade.json`.

**Motivos de exclusão no corte de 2021** (uma semente pode ter vários; inclui as que já eram
inelegíveis):

| Motivo | Medicina | Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| E3: nenhum trabalho ≤ 2021 reivindicado no ORCID | 412 | 429 | 404 | 439 |
| E6: plausibilidade | 96 | 62 | 10 | 10 |
| E5: < 2 trabalhos ≤ 2021 | 50 | 59 | 82 | 117 |
| Sem nenhuma publicação até 2021 | 47 | 88 | 66 | 95 |
| E7: nome | 45 | 21 | 50 | 23 |
| E4: instituição | 22 | 36 | 53 | 99 |
| E8: equipe | 4 | 5 | 4 | 8 |

Em Economia, das 97 elegíveis que saem:
- 50 só tinham reivindicado trabalhos posteriores a 2021;
- 30 não tinham nenhuma publicação até 2021;
- 23 tinham menos de 2 trabalhos;
- 13 não tinham instituição identificada até 2021.

**Leitura.** Filtrar só os **alvos finais** não basta. A elegibilidade muda para cerca de 20%
das elegíveis, e, como mostra §2, candidatos, expansão, limpeza e metadados também
dependem de informação posterior. O conjunto "corrigido" (mantidas e sorteadas por trabalho
≤ 2021) tem de 297 a 344 sementes por base. Os alvos avaliáveis (com coautoria nova em T1)
são menos: 202 a 265 (§4).

## 4. Componentes que precisam ser reconstruídos para uma avaliação corrigida em 2021

| Componente | Situação no protocolo original | Necessário para a versão corrigida | Pode ser feito localmente? |
|---|---|---|---|
| Sementes | 1.000 do sorteio 42, ~30% via trabalho > 2021 | só as sorteadas por trabalho ≤ 2021 | **sim** (ano de sorteio conhecido) |
| Elegibilidade | todos os anos | E1–E8 com autorias ≤ 2021 | **sim** (feito, §3); E1/E3 seguem com o ORCID atual |
| Candidatos | escolhidos a partir das 1.000 sementes | `select_candidates` só com as sementes corrigidas | **sim** (a função reproduz exatamente o original) |
| Expansão | histórico 2017–2021 dos 15 mil atuais | histórico dos candidatos do conjunto corrigido que não estão entre os 15 mil | **parcial**: os que faltam exigem coleta |
| Limpeza e higienização | sobre o corpus inteiro | refeitas sobre o corpus corrigido | sim, depois da coleta |
| Enriquecimento | trabalhos do corpus atual (cache) | trabalhos novos da expansão | parcial: os novos exigem consulta |
| KG e atributos | KG ≤ 2021 | refeitos sobre o corpus corrigido | sim |
| Treino temporal (KG 2018 → 2019–2021) | consultas = sementes + candidatos | mesmas regras sobre o corpus corrigido | sim |
| Metadados (tópicos, ORCID, instituições) | atuais | não reconstruíveis com as APIs atuais | **não**: limitação declarada |

## 5. Diagnóstico comparativo por subconjunto (descritivo)

**[implementado] [executado nas 4 bases]** `scripts/diagnostico_subconjuntos_2021.py`;
tabelas completas em [RESULTADOS_AUDITORIA_2021.md](RESULTADOS_AUDITORIA_2021.md).

Usa os rankings **já existentes** do protocolo original. Ninguém foi retreinado. Compara o
LambdaMART + KG com os controles (LTR só coautoria, União RRF, Adamic-Adar, vizinhos comuns)
em cinco subconjuntos de alvos: todos, sorteados até 2021, elegíveis até 2021, **corrigido**
(os dois) e fora do corrigido. Reporta a média com IC 95% (bootstrap sobre alvos) e as
diferenças pareadas por alvo com IC 95% e p de Wilcoxon, sem correção.

**Classificação: descritiva.** Os modelos foram treinados no protocolo original, então isto
não estima o desempenho de um protocolo corrigido nem determina a direção do viés. O que o
diagnóstico mostra, nas 4 bases e nas duas avaliações:
- o nível absoluto difere entre subconjuntos. Por exemplo, R@50 estrito em Computação: 7,9
  no corrigido contra 4,3 fora dele. Isso se confunde com a quantidade de histórico dos
  alvos;
- as diferenças pareadas do LambdaMART + KG sobre Adamic-Adar e vizinhos comuns têm IC 95%
  acima de zero **dentro** do subconjunto corrigido em todas as bases;
- contra o LTR só coautoria e a União RRF, os intervalos ficam mais largos no corrigido, por
  ter menos alvos. Alguns tocam zero: Computação estrita contra só coautoria, [−0,01; +1,04];
  Matemática contra RRF, como já ocorria no conjunto todo.

## 6. O que fica em aberto

1. A reconstrução histórica (§4) é **retrospectiva pela data dos fatos, com metadados
   atuais**. Ela elimina as dependências de seleção e de fatos, mas não as de metadados (§2).
   O efeito residual dos metadados sobre a predição **não foi medido** e não pode ser
   presumido pequeno.
2. Os vieses de produtividade, recência e ORCID (§1) estão descritos, não quantificados.
3. A subamostra "sorteadas por trabalho ≤ c" é uniforme **entre os trabalhos do quadro
   atual** publicados até c. O quadro atual, porém, não é o quadro como existia em c: o
   OpenAlex de hoje inclui trabalhos indexados depois e classifica a área com tópicos atuais.
   Ela **não** é, portanto, garantidamente a amostra que se teria obtido em c.
