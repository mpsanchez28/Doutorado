# Prompt de contexto: estado do projeto (14/10/2026)

> Cole o bloco abaixo no início de uma conversa com qualquer assistente (nova sessão do Claude,
> outro modelo, ou como briefing para o orientador). Troque a última linha pela tarefa desejada.
> Fontes detalhadas: os documentos citados em `docs/` do repositório.

---

```text
Você vai me ajudar no meu doutorado. Leia todo o contexto antes de responder.

QUEM E O QUÊ
Sou Marcos Paulo Sanchez, doutorando no PPgSI/EACH-USP, orientado pelo prof. Luciano
Digiampietri. A tese trata de RECOMENDAÇÃO DE COAUTORIA formulada como predição de links
futuros: dado o que se sabe até 31/12/2021 (T0), recomendar a um pesquisador quem serão seus
coautores NOVOS a partir de 2022 (T1). A fonte é o OpenAlex. Já passei pela qualificação; a
banca pediu, entre outros pontos, baselines fortes, um "KG de verdade" (com ontologia, não só
rede heterogênea), corpus auditável e hipóteses explícitas.
Repositório: github.com/mpsanchez28/Doutorado (pasta coauthor-rec, Python).

HIPÓTESES EM TESTE
- H0-KG: as relações tipadas de um grafo de conhecimento (instituição, tópicos, periódico,
  citação, carreira) melhoram a recomendação além da rede de coautoria.
- H3: o valor de cada sinal depende da densidade de colaboração da área (gradiente: Medicina
  densa > Computação intermediária > Matemática ≈ Economia esparsas).

DADOS (4 bases, uma por campo OpenAlex Topics)
- Medicina, Ciência da Computação, Matemática, Economia. Amostragem aleatória de 1.000
  sementes por base (1 autor com ORCID por artigo sorteado), histórico completo das sementes e
  histórico 2017–2021 de até 15 mil coautores de T0 delas (candidatos).
- Higienização com ORCID: pessoa canônica = ORCID; níveis de evidência de autoria (A/B/C/X) e
  de vínculo institucional (I1/I2/I3); critérios de elegibilidade E1–E8; regra M9 (coautor
  "novo" com o mesmo nome de um coautor antigo sai do gabarito: identidade fragmentada).
- Tamanho: Medicina 393 mil trabalhos / 951 mil pessoas; Computação 221 mil / 252 mil;
  Matemática 102 mil / 69 mil; Economia 61 mil / 62 mil.
- Alvos avaliados (sementes elegíveis com ≥1 coautoria nova): 466 / 449 / 414 / 337.

KG T0 E ONTOLOGIA
- Ontologia própria alinhada a FOAF, Schema.org, FaBiO/CiTO, SKOS, W3C ORG e PROV.
- KG materializado por base com 10 relações (wrote, atInstitution, partOf,
  relatedInstitution, locatedIn, hasTopic, broader, publishedIn, cites, hasEmployment), cada
  fato com ano e corte em 2021 (validado: nenhum fato do futuro).

PROTOCOLO DE AVALIAÇÃO
- Corte por ano civil (T0 ≤ 2021), teto de 50 coautores por artigo, M9 aplicada.
- Avaliação ESTRITA (principal): todas as coautorias novas. Avaliação PADRÃO (literatura):
  só coautorias novas com pessoas que já tinham trabalho no corpus até 2021.
- Métricas: Recall@K, NDCG@10, Hits@K, MRR; regimes warm/cool/cold/newcomer; testes
  pareados por alvo (Shapiro → t ou Wilcoxon) com correção de Bonferroni.

O QUE FOI FEITO E O QUE SE APRENDEU (em ordem)
1. Linha de base + oráculos: 13 meta-caminhos do KG (coautoria por vizinhos comuns,
   Adamic-Adar, RA; PageRank personalizado; mesma instituição; organização-mãe; tópicos;
   periódico; citação; acoplamento bibliográfico; ex-colegas ORCID; texto TF-IDF;
   popularidade) e a União RRF deles. A união supera o melhor baseline de coautoria em R@50
   em todas as bases (+24% a +56%).
2. A maior perda está antes do modelo: 58% a 73% dos coautores novos não têm trabalho no
   corpus até 2021. Diagnóstico no OpenAlex: só ~1/3 deles são estreantes reais; 27% a 32%
   de TODAS as coautorias novas são com quem publicava na área mas ficou fora da coleta
   egocêntrica.
3. Re-ranqueador aprendido (LambdaMART/LightGBM) sobre o top-1000 da União RRF, com
   atributos dos meta-caminhos + atividade. Modelo principal = TREINO TEMPORAL: aprende com
   KG até 2018 e coautorias de 2019–2021 (sementes e candidatos como consultas, 5 mil a 60
   mil positivos), sem usar nenhum rótulo do período de teste. Precisou de regularização
   forte (valores padrão sobreajustavam).
4. Resultados do modelo principal (avaliação estrita; Medicina / Computação / Matemática /
   Economia): R@50 = 3,84 / 6,21 / 11,85 / 7,37; NDCG@10 = 9,30 / 5,41 / 5,96 / 4,25.
   Avaliação padrão: R@50 = 12,1 / 23,8 / 37,2 / 33,6. Supera com significância os
   baselines clássicos (vizinhos comuns: +43% a +91% em R@50 estrita; Adamic-Adar: +36% a
   +67%) em todas as bases e métricas.
5. H0-KG confirmada: o modelo com o KG supera o mesmo modelo só com coautoria em R@50, com
   significância, nas 4 bases. As relações do KG são redundantes entre si: o ganho está no
   conjunto. Relação decisiva por área: instituição em Computação e Economia; conteúdo
   (citação, texto, tópicos) em Matemática.
6. H3 apoiada: no modelo, o peso (|SHAP|) da coautoria cai de 41% (Medicina) para 24%
   (Computação) e 12–13% (Matemática, Economia); o peso do conteúdo sobe de 18% para 29% e
   36–45%.
7. Gargalo de geração: entre as coautorias alcançáveis, 68% (Medicina) e 58% (Computação)
   ficam fora dos 1.000 candidatos. Uma geração seletiva em cascata recuperou +7% a +23%
   delas, mas o top-50/top-200 EMPATOU (resultado negativo): o gargalo do topo da lista é a
   qualidade dos sinais, não a geração.
8. SPECTER2 no lugar do TF-IDF: sozinho é 2 a 12 vezes melhor em NDCG@10, mas no modelo
   completo EMPATA nas 4 bases, nas duas avaliações e em todos os regimes (resultado
   negativo): o conteúdo que ele captura já está no KG (tópicos, citação, acoplamento).
   TF-IDF mantido. Leitura para a tese: relações explícitas e auditáveis do KG entregam o
   mesmo que um encoder neural de 110 milhões de parâmetros, sem GPU e com explicação.

LIMITAÇÕES DECLARADAS
- Coleta egocêntrica limita o teto de recall (item 2).
- Hiperparâmetros do LTR escolhidos em Economia e fixados nas demais (leve viés em Economia).
- Poucos alvos em cool/cold; relação ex-colegas ORCID com cobertura baixa (0,5% a 7%).
- O pré-treino do SPECTER2 pode conter citações posteriores a 2021 (vazamento indireto).
- Números da qualificação não são comparáveis aos atuais (corpus, corte, alvos e gabarito
  mudaram); a comparação válida é o baseline refeito no protocolo novo.

PENDENTE / PRÓXIMOS PASSOS POSSÍVEIS
- Robustez: várias sementes aleatórias (T1) e vários anos de corte (T4), pedidos pela banca.
- Baselines fortes da literatura: NCNC/SEAL ou GNN heterogênea sobre o KG (T5).
- Consolidar os resultados num capítulo da tese.

DOCUMENTOS DE REFERÊNCIA NO REPOSITÓRIO (docs/)
METODOLOGIA_DADOS, HIGIENIZACAO, SELECAO_BASES, ONTOLOGIA, ENRIQUECIMENTO, LINHA_BASE,
ABLACAO_KG (inclui o treino temporal), DIAGNOSTICO_FORA_T0, GERACAO_SELETIVA,
TEXTO_SPECTER2, e os respectivos RESULTADOS_*.md.

COMO QUERO QUE VOCÊ TRABALHE
Português do Brasil, rigor de tese (sem exagerar resultados; diferenças só valem com teste
de significância), explicando os porquês das decisões. Não invente números: se precisar de
um dado que não está aqui, pergunte.

MINHA TAREFA AGORA: [descreva aqui]
```
