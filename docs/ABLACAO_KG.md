# Ablação das relações do KG

Segundo passo da fase de modelagem, depois da [linha de base](LINHA_BASE.md): medir quanto
**cada relação do KG** contribui para a recomendação, separando dois papéis que ela pode ter.

- **Geração**: trazer para a lista candidatos que as outras relações não trazem.
- **Ordenação**: ajudar a colocar no topo, entre candidatos já gerados, os que de fato vão
  colaborar.

Números em [RESULTADOS_ABLACAO_KG.md](RESULTADOS_ABLACAO_KG.md), gerado automaticamente.
Código: `models/kg_ltr.py` (pares, atributos, LambdaMART), `scripts/ablation_kg.py`
(execução), `scripts/report_ablacao_kg.py` (relatório).

Responde à hipótese **H0-KG** do plano pós-banca ("relações tipadas do KG melhoram a ordenação
no topo além da coautoria") e ao teste **T6** (features de KG no ranqueador). Atende também ao
pedido de "ver os pesos de uso de cada camada".

## 1. Desenho

```
KG T0 ──► 13 meta-caminhos ──► União RRF ──► top-1000 por alvo (conjunto FIXO)
                                                   │
                       atributos por par (alvo, candidato), em 8 grupos
                                                   │
                     LambdaMART, validação cruzada em 5 dobras de alvos
                                                   │
             completo · só coautoria · sem cada grupo · coautoria + cada grupo
```

**Conjunto fixo de candidatos.** Todas as configurações ordenam o mesmo top-1000 da União RRF.
Assim, a ablação de atributos mede só o ganho de ordenação. O ganho de geração é medido à
parte, pelo Alcance@1000 da União sem a relação.

**Grupos de atributos.** Para cada meta-caminho entram o escore e a posição do candidato na
lista daquele gerador (2.000 se fora do top-1000):

| Grupo | Meta-caminhos |
|---|---|
| Coautoria | vizinhos comuns, Adamic-Adar, Resource Allocation, PageRank personalizado |
| Instituição | mesma instituição, mesma organização-mãe |
| Tópicos | cosseno dos perfis de tópico |
| Periódico | mesmo periódico |
| Citação | citação direta, acoplamento bibliográfico |
| Ex-colegas | vínculos ORCID sobrepostos |
| Texto | TF-IDF dos resumos |
| Atividade | grau, nº de trabalhos e último ano do alvo; grau, nº de trabalhos, primeiro e último ano do candidato |

**Modelo.** LightGBM `lambdarank` (LambdaMART; Burges, 2010), um grupo por alvo. Ele otimiza
diretamente a ordem da lista (NDCG), em vez de classificar pares isolados como o Random Forest
da qualificação.

**Validação.** Os alvos são divididos em 5 dobras (embaralhamento com semente 42). Cada alvo é
avaliado por um modelo que não o viu no treino. Atributos vêm só do KG T0; os rótulos de treino
são as coautorias novas de T1 dos **outros** alvos.

**Configurações** (todas com os mesmos hiperparâmetros):

- União RRF sem aprendizado (referência);
- LTR só coautoria (+ atividade): o recomendador **sem KG**;
- LTR completo: todos os grupos;
- *sem X*: completo menos um grupo (leave-one-out);
- *coautoria + X*: só coautoria mais um grupo do KG (add-one).

**Peso de cada relação.** Medido no modelo completo de duas formas:
- ganho acumulado do LightGBM;
- |SHAP| médio por grupo (`pred_contrib`), nas predições fora da dobra de treino.

O SHAP é a medida principal: diz quanto cada grupo move, em média, o escore de cada
recomendação.

**Testes.** Pareados por alvo: Shapiro-Wilk decide entre t pareado e Wilcoxon (`eval/stats.py`).
Correção de Bonferroni sobre o conjunto de comparações (α = 0,05 / 15). As comparações são:
- completo vs só coautoria;
- completo vs União RRF;
- completo vs cada *sem X*;
- cada *coautoria + X* vs só coautoria.

## 2. Hiperparâmetros: um problema encontrado e corrigido

Positivos são raros: cerca de 0,2% dos pares, ou ~400 por dobra de treino em Economia. Com os
valores padrão do LightGBM (400 árvores de 31 folhas, 20 amostras por folha), o modelo
sobreajustou:

| Economia | R@10 | R@50 | NDCG@10 |
|---|---:|---:|---:|
| União RRF (sem aprendizado) | 3,25 | 6,08 | 3,71 |
| LTR completo, padrão | 2,55 | 6,66 | 3,27 |
| LTR só coautoria, padrão | 1,03 | 4,13 | 1,87 |
| **LTR completo, regularizado** | **3,63** | **6,93** | **4,02** |
| **LTR só coautoria, regularizado** | **2,73** | **6,20** | **3,05** |

Com os valores padrão, o modelo aprendido ficou abaixo da fusão sem aprendizado, e o "só
coautoria" abaixo do próprio Adamic-Adar (NDCG@10 2,31). A configuração adotada usa:
- 200 árvores de 7 folhas;
- ≥200 pares por folha;
- regularização L2 = 5;
- amostragem de 80% das linhas e colunas.

Ela foi **escolhida em Economia** entre 4 variantes: padrão; regularizado `lambdarank`;
regularizado binário; truncamento 1.000. Depois foi **fixada** para todas as bases e
configurações. Por ter sido escolhida olhando as dobras de Economia, os números de Economia
têm um leve viés otimista; as outras três bases não participaram da escolha.

## 3. Limitações

- **Poucos positivos por base.** Diferenças de décimos de ponto podem não ser significativas;
  por isso o relatório marca só o que passa no teste com Bonferroni.
- **Rótulos de T1 no treino.** Os rótulos dos outros alvos vêm do mesmo período de teste
  (validação cruzada por alvo). É o protocolo usual de *learning to rank*, mas um treino
  **temporal** seria mais estrito: rótulos de 2019–2021, atributos até 2018, aplicado a 2021 →
  T1. Ele também daria muito mais positivos, porque os candidatos têm histórico completo
  2017–2021. Fica como verificação de robustez (§4).
- **Texto só TF-IDF.** SPECTER/SciBERT entram quando houver embeddings das bases novas
  (Medicina exige GPU).
- **Ex-colegas** cobre só sementes e candidatos com ORCID, de 0,5% a 7% das pessoas do KG.
  Um efeito nulo aqui reflete cobertura, não ausência de sinal.

## 4. Próximos passos

1. Treino temporal (2018 → 2019–2021) como robustez, com mais positivos.
2. Repetir com 5 sementes de dobra (T1 multi-seed) para a variância do próprio LTR.
3. Embeddings SPECTER2 como grupo "texto" forte.
4. Ampliar a geração onde ela é o gargalo (Medicina: §5 de RESULTADOS_LINHA_BASE).

## 5. Resultados e leitura (10/10/2026)

Tabelas completas em [RESULTADOS_ABLACAO_KG.md](RESULTADOS_ABLACAO_KG.md). Testes pareados com
Bonferroni (α = 0,0031).

**1. As relações do KG melhoram a recomendação além da coautoria (H0-KG) em 3 das 4 bases.**
LTR completo contra LTR só coautoria, R@50: Medicina +0,32 pp (p = 4e-4), Computação +0,59
(p = 1e-3), Matemática +1,94 (p = 5e-5), todos significativos. Em Economia, +0,73, sem
significância (a base com menos positivos). No topo da lista (NDCG@10), o ganho só é
significativo em Computação (+1,38, p = 2e-4); nas demais vai na mesma direção, sem poder
estatístico.

**2. O ganho vem das relações, não do aprendizado.** O LTR completo empata com a União RRF
sem aprendizado em quase tudo: só em Medicina a diferença no R@50 é significativa (+0,46). Com
400 a 4.000 positivos por base, o LambdaMART não consegue extrair muito mais do que a fusão
por posição já entrega. Para a tese, isso é uma boa notícia metodológica: o efeito do KG não
depende de um modelo ajustado. Também indica o próximo passo: mais dados de treino (treino
temporal, §4).

**3. O peso de cada relação acompanha o gradiente de densidade (H3).** Participação no |SHAP|
do modelo completo:

| Grupo | Medicina | Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Coautoria | 31,1 | 33,6 | 20,9 | 16,9 |
| Instituição | 19,9 | 15,9 | 8,1 | 13,1 |
| **Conteúdo** (tópicos + citação + texto) | **23,0** | **25,6** | **49,7** | **43,3** |
| Periódico | 5,2 | 5,8 | 6,9 | 4,7 |
| Atividade | 20,8 | 19,1 | 14,4 | 22,0 |

- Nas áreas densas (Medicina, Computação), a decisão se apoia na rede: coautoria e
  instituição somam cerca de 50%.
- Nas áreas esparsas (Matemática, Economia), o conteúdo vira o principal sinal, com quase
  metade do peso.
- É a mesma direção da qualificação (texto ajuda quando o histórico é fino), agora entre
  áreas e não só entre regimes.

**4. As relações do KG são redundantes entre si.** Retirar uma relação isolada quase nunca muda
o resultado de forma significativa. A única exceção é a instituição em Computação (R@50 −0,56,
p = 3e-3). O ganho do KG está no conjunto: tópicos, citação e texto carregam informação
parecida e se substituem.
- No *add-one*, a citação/acoplamento é a relação que mais acrescenta sozinha à coautoria:
  Matemática +1,87 em R@50 (p = 2e-4); Computação +0,83 em NDCG@10.

**5. Na geração, a coautoria domina.** Sem ela, o Alcance@1000 da união cai de 1,6 a 5,0
pontos. Nenhuma outra relação, retirada sozinha, muda o alcance em mais de 0,8 ponto.
- Tópico e texto chegam a **piorar** levemente o alcance em Medicina (+0,25 ao retirá-los):
  na fusão por posição, listas densas e pouco precisas empurram candidatos bons para fora do
  top-1000.
- O papel das relações do KG nesta arquitetura é **ordenar**, não gerar.
- O gargalo de geração de Medicina (§7 de LINHA_BASE.md) pede outra solução: geradores mais
  seletivos, ou uma fusão ponderada em vez de RRF uniforme.

**6. Ex-colegas ORCID não pesa (|SHAP| ≈ 0).** A cobertura é de 0,5% a 7% das pessoas do KG.
É um resultado de cobertura, não de ausência de sinal: o lift era alto onde a relação existe.

**7. Regimes.** Os maiores ganhos do KG sobre a coautoria estão em cool:

| NDCG@10, cool | Só coautoria | Completo |
|---|---:|---:|
| Matemática | 3,16 | 5,23 |
| Economia | 1,26 | 2,90 |
| Computação | 3,77 | 5,23 |

Em Matemática cold, o modelo só com coautoria zera e o completo chega a 13,4, mas com n = 9.

## 6. Implicações para os próximos passos

1. **Treino temporal** (atributos ≤ 2018, rótulos 2019–2021, incluindo os candidatos como
   consultas): multiplica os positivos e deve permitir que o aprendizado supere a RRF.
2. **Geração em Medicina:** fusão ponderada ou geradores restritos (por exemplo, 2 saltos ∩
   instituição) para tirar do top-1000 o ruído das listas densas.
3. **Conteúdo forte:** SPECTER2 no lugar do TF-IDF, com mais impacto esperado nas áreas
   esparsas, onde o conteúdo já pesa ~45%.
4. **Diagnóstico do "fora de T0"**: separar estreantes reais de histórico não coletado (a maior
   perda: 58% a 73% dos pares).

## 7. Treino temporal (robustez e mais dados)

Script `scripts/temporal_ltr.py`; resultados em
[RESULTADOS_LTR_TEMPORAL.md](RESULTADOS_LTR_TEMPORAL.md) (`scripts/report_ltr_temporal.py`).

**Por quê.** A validação cruzada por alvo (§1) usa, para treinar, rótulos de T1 de outros alvos.
É o protocolo usual, mas tem duas fraquezas:
- o modelo vê padrões do período de teste;
- há poucos positivos, só os coautores novos das sementes elegíveis.

O treino temporal elimina as duas.

**Desenho.**

| | Treino | Teste |
|---|---|---|
| KG | cortado em 31/12/2018 | cortado em 31/12/2021 (o mesmo da linha de base) |
| Rótulos | coautorias novas de 2019–2021 | coautorias novas de 2022+ (T1), com M9 |
| Consultas | sementes **e candidatos** com coautoria nova em 2019–2021 (até 3.000; todas as sementes e o restante sorteado entre candidatos, semente 42) | alvos elegíveis (os mesmos da ablação) |
| Candidatos por consulta | top-1000 da União RRF no KG de 2018 | top-1000 da União RRF no KG de 2021 |

- **Candidatos como consultas.** O histórico deles foi coletado em 2017–2021. Para o período
  de treino, então, ele está completo. Para T1 não está, e por isso eles não podem ser alvos de
  avaliação. É isso que multiplica os positivos.
- **Atributos de ano relativos ao corte.** Por exemplo, "anos desde o último trabalho". Assim, o
  modelo aprendido no KG de 2018 se aplica ao de 2021 sem deslocamento.
- **Mesmas configurações da ablação**, mais duas de sensibilidade:
  - *só sementes como consultas*: quanto os candidatos acrescentam ao treino;
  - *parâmetros padrão do LightGBM*: se, com mais dados, a regularização ainda é necessária.

**Limitação.** Os candidatos têm só 2017–2018 de histórico no KG de 2018, enquanto as sementes
têm o histórico completo. A distribuição dos atributos difere um pouco entre treino e teste. A
configuração "só sementes" mede o efeito disso.

### 7.1 Resultados e leitura (10/10/2026)

O treino temporal teve 5.303 (Matemática) a 60.172 (Medicina) positivos, de 6 a 15 vezes mais
do que a validação cruzada.

**1. Treinar no passado é melhor e mais rigoroso.** O LTR temporal completo supera o da
validação cruzada em todas as bases e métricas principais. NDCG@10:

| | Medicina | Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Validação cruzada | 8,21 | 5,10 | 5,21 | 4,02 |
| Temporal | 9,30 | 5,41 | 5,96 | 4,25 |

Em Medicina a diferença é significativa. Daqui em diante, o **treino temporal passa a ser o
protocolo principal** do re-ranqueador: além de render mais, não usa nenhum rótulo do período
de teste.

**2. O aprendizado agora supera a fusão sem aprendizado.**
- O LTR temporal completo fica acima da União RRF em todas as bases.
- É significativo em Medicina (R@50 e NDCG@10) e em Economia (R@50).
- Na validação cruzada eles empatavam (§5, achado 2). Faltavam dados, não sinal.

**3. H0-KG confirmada nas 4 bases.** O LTR temporal completo supera o LTR temporal só com
coautoria em R@50 com significância em **todas** as bases:

| | Medicina | Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Δ R@50 | +0,37 | +0,66 | +2,46 | +1,31 |

No NDCG@10, o ganho é significativo em Computação e Economia.

**4. Os candidatos como consultas ajudam.** Treinar só com as sementes rende menos em todas as
bases (Medicina, NDCG@10: 8,47 contra 9,30). A diferença de histórico entre candidatos e
sementes (§7, limitação) não atrapalha.

**5. A regularização continua necessária para o topo.** Com os parâmetros padrão, o NDCG@10
cai nas 4 bases. O R@50 sobe um pouco em Matemática e Economia, mas a configuração
regularizada é mantida.

**6. O peso de cada relação segue o gradiente de densidade, agora de forma monótona (H3).**
|SHAP| médio no LTR temporal completo:

| | Medicina | Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Coautoria | 41,3 | 23,6 | 11,9 | 13,3 |
| Conteúdo (tópicos + citação + texto) | 17,6 | 28,7 | 44,7 | 35,6 |

Do polo denso para o esparso, a coautoria perde peso e o conteúdo ganha. Matemática e Economia
formam o polo baixo, onde a ordem interna não é afirmada pela H3.

**7. Cada área tem a sua relação decisiva** (*add-one*, significativos):

| | Relação decisiva | Δ R@50 |
|---|---|---:|
| Computação | instituição | +0,39 |
| Economia | instituição | +1,21 |
| Matemática | citação/acoplamento | +2,36 |
| Matemática | texto | +2,21 |
| Matemática | tópicos | +1,31 |
| Medicina | nenhuma relação isolada | — |

Em Medicina, a coautoria e a atividade dominam (retirar a atividade custa −0,66 de NDCG@10).
O leave-one-out segue mostrando redundância: fora a coautoria, só a instituição (Computação) e
a atividade (Medicina) fazem falta sozinhas.

**8. Regimes.** O KG ajuda mais quem tem pouco histórico. Em cool, NDCG@10 de 2,6 → 4,9
(Matemática), 1,4 → 3,0 (Economia) e 3,4 → 5,2 (Computação). Em cold, o modelo só com
coautoria zera, e o completo chega a 7,9 (Computação) e 12,5 (Matemática), com n pequeno.

### 7.2 Avaliação padrão

Na avaliação padrão (só coautores presentes em T0; [LINHA_BASE.md](LINHA_BASE.md) §9), o LTR
temporal completo supera o só coautoria com significância em R@50 nas 4 bases e em NDCG@10 em
Computação, Matemática e Economia. Supera a União RRF em Medicina (R@50 e NDCG@10) e Economia
(R@50). Valores: R@50 de 12,1 (Medicina) a 37,2 (Matemática); Hits@10 de 36% a 44%.
