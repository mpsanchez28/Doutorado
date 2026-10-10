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
