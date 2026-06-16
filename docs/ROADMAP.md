# Roadmap da Tese × Progresso

Mapa das 10 atividades do Plano de Trabalho (Cap. 6 da qualificação) com status e
resultado de cada passo. Resultados sob o protocolo atual (teto coautores/artigo = 50;
população T0-ativa warm+cool; Recall@200 salvo exceto onde indicado).

| # | Passo | Cronograma | Status | Resultado |
|---|---|---|---|---|
| 1 | Protocolo experimental + verdade fundamental | 3T/26 | ✅ | Split temporal T0→T1, `C_new = C_future \ C_past`, regimes warm/cool/cold **+newcomer**, métricas, stats. Teste anti-vazamento. |
| 2 | Coleta/limpeza/versionamento OpenAlex | 3–4T/26 | ✅ | 3 modos (snowball/thematic/hybrid). Corpus real **5.878 works / 19.120 autores**, gate **APROVADO**. |
| 3 | Grafo heterogêneo | 4T/26 | ✅ | KG Tabela 8 (5 entidades/6 relações), teto anti-consórcio = 50. **14.283 autores / 4.702 papers / 172k arestas coautoria**; densidade 0,0008, clustering 0,88. |
| 4 | Baselines de referência | 4T/26 | ✅ | Reproduziu o estudo inicial. **RF > baseline** (sig). RF R@200: warm **14,36**, cool **22,41**. Oráculo (teto): 16,55 / 23,83. |
| 1b | **Enriquecimento GenAI do KG** (§4.3.3) | 4T/26 | ⚠️ feito, não ajudou | Extração OpenAI+Claude (paper_type/contribution/style/methods/topic); concordância writing_style 90%, type/contrib 66%. Integrado como nós do KG → **ablação neutra/negativa** (cool 22,65→20,98). Texto livre (topic/methods) ainda não usado. |
| 5 | Módulo textual (CNN/BERT) | 1S/27 | ⚠️ parcial | Comparei encoders **TF‑IDF/BERT/SciBERT/SPECTER** (text-only). Em cool, texto **> RF no topo** (R@10 +6pp, sig); SciBERT≈SPECTER. **CNN 1D entra na fusão end-to-end (passo 7).** |
| 6 | Módulo relacional (GNN) | 1S/27 | ✅ | GNN heterogênea + reranker 2-hop. **Competitiva**: overall ≈ RF (14,33 vs 14,80); **melhor em cool@200 (22,65)**. Não domina warm. |
| 7 | **Fusão CNN+GNN (Eq. 10)** | 2S/27 | ⚠️ 1º corte | End-to-end CNN textual ⊕ GNN → Dense, treino por link prediction. **Empata a GNN-rerank, não supera o RF** (overall 14,25). Diagnóstico: gargalo é o espaço de candidatos (2-hop anula a força do texto), não a fusão. Ver COMPARATIVO_MODELOS.md. |
| 8 | Experimentos comparativos + ablação | 2S/27 | 🟡 parcial | Comparação por componente pronta (topologia × texto × GNN); falta ablação formal do modelo de fusão. |
| 9 | Análise estatística | 2S/27 | 🟡 parcial | Infra pronta e aplicada (Wilcoxon/Bonferroni/bootstrap) a baselines/texto; aplicar à fusão. |
| 10 | Redação da tese | contínuo | 🟡 em curso | Relatório Ciclo 1 (.md/.docx) + comparativo crítico de modelos. |

## Onde estamos
Fundação (1–4) e módulos isolados (5 parcial, 6) concluídos. No **passo 7 — fusão**, onde a
**hipótese central** ("texto+estrutura > cada um isolado") é testada.

## Ressalvas metodológicas
1. **A CNN 1D** (proposta §4.4.1) é uma cabeça treinável; seu lugar é a **fusão end-to-end**
   (passo 7), treinada com o sinal de link prediction sobre tokens do BERT/SciBERT.
2. **Nenhum modelo "venceu" isolado** — o quadro é de **complementaridade** (RF forte em warm;
   texto forte no topo em cool; GNN-rerank forte em recall de cool). A fusão precisa bater o RF
   em warm **e** o texto/GNN em cool simultaneamente.
3. **`cold` é inconclusivo (n=3)** e *newcomers* (82% dos alvos) são inatendíveis por perfil-T0;
   a avaliação significativa recai sobre os **1.054 autores T0-ativos** (warm+cool).

## Estado dos modelos (R@200) — corrigido por teste de significância
| Modelo | overall | warm | cool | vs RF (Wilcoxon) |
|---|--:|--:|--:|---|
| Híbrido RF | 14,80 | 14,36 | 22,41 | — (referência) |
| Hybrid-cand (rank=text) | 14,84 | 14,39 | 24,95 | **empate** (RF melhor em R@50/NDCG@10) |
| GNN-rerank | 14,33 | 11,49 | 22,65 | Hybrid-cand vence (sig) |
| Texto-only | 2,22 | 11,73 | 20,77 | Hybrid-cand vence em R@200 (sig) |

**Achado-chave (corrigido):** o gargalo era a **geração de candidatos** (2-hop). Unir
candidatos estruturais + textuais bate a GNN e o texto-only, e **empata** com o Híbrido RF —
mas **não o supera** (RF segue melhor em R@50/NDCG@10). O número "14,84>14,80" é ruído (p=0,21).

**Ranqueador supervisionado sobre o pool híbrido (RF + features textual/GNN): FALHOU** — recall@200
sobe (cool 25,42) mas precisão no topo desaba (warm R@5 0,45 vs 2,82); significativamente PIOR
que o RF em R@10/R@50/NDCG@10. Adicionar candidatos textuais a um ranqueador forte polui o topo.

**Síntese honesta:** o **Híbrido RF segue o melhor modelo geral**; nenhuma abordagem multimodal
o supera em warm/topo. O ganho robusto do texto é **localizado em cool** (R@10 +5pp vs RF, sig)
— furando o teto do oráculo topológico. A fusão que funciona é de **fontes de candidatos**, não
de representações nem de ranqueador. Caveat: fixar `PYTHONHASHSEED` (comparações finas oscilam).
