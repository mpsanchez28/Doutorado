# Enriquecimento da base — camadas 1–3 e ontologia (passo a passo)

Escopo aprovado em 09/10/2026 (`docs/PLANO_ENRIQUECIMENTO.md`): **camada 1** (semântica temática),
**camada 2** (instituições), **camada 3** (trajetórias de carreira) e **ontologia**. Este documento
registra, etapa por etapa, o que foi feito, por quê, como e com que resultado, além de um diário
de execução com os incidentes e suas correções. Números por base: `docs/RESULTADOS_BASES.md` §7.

## 0. Princípios

1. **Relações tipadas e com significado** — o objetivo é um grafo de conhecimento, não apenas
   mais colunas (`docs/ONTOLOGIA.md`).
2. **Toda camada precisa justificar sua presença** — por ganho mensurável no ranqueamento (T6),
   como fonte de candidatos (T7) ou na explicação. Antes dos testes formais, um **diagnóstico de
   sinal** (passo 5) indica se vale a pena testá-la.
3. **Sem vazamento temporal** — relações usadas como atributo em T0 só usam informação disponível
   até o fim de T0. Isso é crítico na camada 3: o ORCID descreve o presente.
4. **Proveniência e reprodutibilidade** — cada fato guarda a fonte; respostas das APIs ficam em
   cache em disco (retomável); parâmetros em `configs/enrich.yaml`.
5. **Separação de etapas** — a coleta cuida de identidade e estrutura; o enriquecimento, de
   semântica e atributos. O enriquecimento parte do corpus higienizado.

## 1. Arquitetura

```
corpus higienizado ─┬─► (1) Topics por trabalho ──────────► work_topics · taxonomy · author_subfields
                    ├─► (2) Instituições das autorias ────► institutions · lineage · associated
                    │                                        · author_institution_years
cache ORCID ────────┴─► (3) Vínculos e formação ──────────► author_affiliations_orcid · author_careers
                                       │
                                       ▼
            (4) diagnóstico de sinal (lift, só T0)   (5) amostra RDF validada + SPARQL
                                       ▼
          data/processed/enrich_<base>/  ·  runs/<base>/enrich.json
```

Código: `src/coauthor_rec/enrich/` (`openalex_cache.py`, `topics.py`, `institutions.py`,
`careers.py`), `src/coauthor_rec/graph/ontology.py`; orquestração em `scripts/enrich_base.py`.
Testes: `tests/test_enrich.py`.

## Passo 1 — Infraestrutura: busca por identificador, com cache e orçamento

**O quê.** Um cliente que busca entidades do OpenAlex pelo identificador, 50 por requisição
(filtro `openalex:ID1|ID2|…`), em paralelo sob um limite global de taxa.
**Por quê.** Os trabalhos e as instituições já são conhecidos (vêm da coleta); buscar por ID é
o modo mais barato e reprodutível de obter os metadados adicionais.
**Como.** Cada entidade tem um arquivo `data/cache/openalex/<entidade>.jsonl`, uma linha por
registro: IDs em cache não são consultados de novo; IDs que a API não devolve (removidos ou
fundidos) são gravados como ausentes. A resposta inteira fica guardada — as camadas futuras
(ODS, financiadores) não exigirão nova consulta.
**Por que a busca usa o bruto, e não o corpus higienizado.** O conjunto bruto contém todos os
trabalhos que podem sobreviver à higienização; buscá-lo uma vez evita refazer consultas se os
critérios mudarem.
**Orçamento.** Desde fevereiro de 2026 o OpenAlex mede o uso em créditos diários (1 por consulta
de lista/filtro; renovação à meia-noite UTC): 1.000 por dia sem chave, 10× com chave gratuita.
Uma base custa ~2 mil créditos de enriquecimento (≈100 mil trabalhos ÷ 50) — **exige a chave**.

## Passo 2 — Camada 1: semântica temática (OpenAlex Topics)

**O quê.** Para cada trabalho, os tópicos atribuídos (em média ~3), cada um com score e com a
hierarquia fixa tópico → subcampo → campo → domínio; e as palavras-chave.
**Por quê.** É a semântica explícita que faltava ao grafo e substitui os *Concepts*, cuja marcação
se mostrou ruidosa (`docs/SELECAO_BASES.md` §3.2). Usos: perfil temático dos autores, terceira
fonte de candidatos (T7), atributo "mesmo subcampo" (T6) e explicações tipadas.
**Como.**
- `work_topics`: trabalho × tópico com score, posição e indicação do tópico principal.
- `taxonomy`: tópicos únicos com seus ancestrais (base da hierarquia SKOS da ontologia).
- **Perfil do autor por subcampo:** para o autor *a* e o subcampo *s*,
  `peso(a, s) = Σ score(w, t) / Σ score(w, ·)`, somando sobre os trabalhos *w* de *a* e os tópicos
  *t* de *w* que pertencem a *s*; os pesos somam 1 por autor. Para atributos de T0, o perfil é
  calculado só com trabalhos de T0.
- **Verificação de consistência:** fração de trabalhos cujo tópico principal está no campo da
  base — esperado 100%, porque a área foi definida exatamente por esse campo.
**Decisão.** Todos os tópicos são guardados com o score (sem limiar na coleta); os limiares são
decididos na modelagem.

## Passo 3 — Camada 2: instituições

**O quê.** Para cada instituição das autorias: ROR, tipo (*education*, *healthcare*, *company*,
*government*, *facility*, *nonprofit*…), país, cidade e coordenadas, Wikidata, **hierarquia**
(`lineage`: a instituição e suas ancestrais) e **associações** declaradas (mãe, filha,
relacionada). Do corpus vem o vínculo datado autor × instituição × ano.
**Por quê.** Proximidade institucional e geográfica é um dos determinantes clássicos de
colaboração científica (Katz; Martin, 1997). Tipadas, essas relações viram atributos
(`mesma_instituicao`, `mesma_org_mae`, `mesmo_pais`, par de tipos) e explicações.
**Como.** As instituições ancestrais que não aparecem nas autorias também são buscadas, para
fechar a hierarquia. A "organização-mãe" de uma instituição é o último ancestral do `lineage`
(ex.: o hospital universitário → a universidade).
**Por que OpenAlex e não a API do ROR.** O OpenAlex já incorpora os metadados do ROR (tipo,
país, hierarquia) e o identificador Wikidata; uma fonte a menos para manter.

## Passo 4 — Camada 3: trajetórias de carreira (ORCID)

**O quê.** Vínculos profissionais e formação declarados no ORCID, com organização, país e período
— lidos do **cache da higienização** (nenhuma consulta nova).
**Por quê.** Ter trabalhado na mesma organização ao mesmo tempo é um preditor clássico de
colaboração que **a rede de coautoria não enxerga** (colegas que ainda não publicaram juntos).
**Como.**
- **Identidade da organização** (`org_key`), por ordem de preferência: ROR; identificador
  desambiguado do próprio ORCID (RINGGOLD/GRID — consistente entre registros, o que permite
  casar colegas mesmo sem ROR); nome normalizado + país.
- **Ex-colegas:** duas pessoas com vínculo na mesma `org_key` em períodos sobrepostos.
  Períodos sem início nem fim são descartados (desconhecidos).
- **Resumo de carreira:** nº de empregadores, nº de países, primeiro emprego e ano da última
  formação concluída (aproximação do início da carreira independente).
- **Controle de vazamento:** toda consulta recebe o ano de corte de T0; vínculos iniciados depois
  dele são ignorados e períodos em aberto são truncados no corte. Coberto por teste automatizado.
**Limitações.** Registros autodeclarados, muitas vezes incompletos; datas com granularidade de
ano; o tipo de formação (ex.: doutorado) não é usado.

## Passo 5 — Diagnóstico de sinal (antes dos testes formais)

**Pergunta.** Cada relação nova é mais frequente entre pares que **vieram a colaborar** do que
entre pares aleatórios?
**Método.**
1. Split temporal do corpus (80% mais antigos = T0), como na avaliação.
2. **Positivos:** para cada autor-alvo, os coautores **novos** em T1.
3. **Negativos:** para cada positivo, uma pessoa sorteada do catálogo de T0 que não é coautora
   do alvo, nem em T0 nem em T1 (semente fixa).
4. Relações calculadas **só com T0**: mesmo subcampo principal; similaridade de perfis de
   subcampo > 0,5 (cosseno); mesma instituição; mesma organização-mãe; mesmo país; ex-colegas
   (ORCID, até o corte).
5. **Lift** = P(relação | coautoria nova) ÷ P(relação | par aleatório), mais a cobertura (fração
   de pares em que a relação é calculável).
**Leitura.** Lift ≫ 1 indica sinal que vale testar formalmente. **Não é avaliação de modelo**:
negativos aleatórios são mais fáceis de distinguir que os candidatos reais do 2-hop; o teste
decisivo é o T6, com os candidatos do modelo.

## Passo 6 — Ontologia e amostra RDF

Detalhada em `docs/ONTOLOGIA.md`. Por base, `scripts/enrich_base.py` sorteia 25 autores-alvo,
exporta a vizinhança deles em RDF/Turtle (`kg_sample.ttl`), valida a amostra contra a TBox (toda
classe e propriedade usada precisa estar declarada) e executa consultas SPARQL de demonstração
(instâncias por classe, coautores que compartilham subcampo, coautores ex-colegas, autorias por
nível de evidência, hierarquia institucional).

## Passo 7 — Testes automatizados

`tests/test_enrich.py`: hierarquia e perfil normalizado (camada 1), hierarquia e vínculo datado
(camada 2), prioridade de `org_key`, resumo com corte e **ex-colegas sem vazamento** (camada 3),
e a ontologia (amostra sintética validada contra a TBox, consultas SPARQL, Turtle relido).
`tests/test_seeding.py`: cota esgotada vira erro explícito e imediato.

---

## Diário de execução e incidentes

| Quando (09/10/2026) | Evento | Diagnóstico | Correção |
|---|---|---|---|
| ~09:50 | Higienização de Economia parada em 17,5 mil de 27,5 mil ORCIDs | A API do ORCID passou a responder 429: o acesso **anônimo** tem cota de **25 mil leituras/dia por IP** (atingida somando pilotos e coleta). Defeito no cliente: após uma falha definitiva, ele aguardava as ~10 mil consultas restantes também falharem, continuando a bater na API | Pausa **global** em 429 (respeita `Retry-After`, espera crescente); **disjuntor** após 15 min de pausas; cancelamento imediato das consultas pendentes; suporte a **token de cliente público** (100 mil leituras/dia); taxa anônima limitada a 6/s |
| ~10:07 | Coleta de Matemática e enriquecimento de Economia parados, sem mensagem | O OpenAlex adotou **orçamento diário de créditos** (fev/2026): 1.000/dia sem chave, esgotados. O `pyalex` repetia o 429 **respeitando `Retry-After` = 38.574 s** — dormiria 10,7 h em silêncio. Pior: o coletor **pulava lotes com falha**, o que podia gerar uma base incompleta com aparência de completa | 429 retirado do *retry* do `pyalex`; cota esgotada vira **erro explícito** com a hora de retorno; lote com falha é **repetido até 3 vezes e, persistindo, aborta** a coleta; suporte a `OPENALEX_API_KEY`; `scripts/check_apis.py` mostra credenciais e saldo |
| ~10:00 | `rdflib` 7.6 incompatível com o `matplotlib` 3.7 do ambiente (via `pyparsing`) | O SPARQL do rdflib ≥ 7.1 exige `pyparsing` ≥ 3.1, que o matplotlib 3.7 rejeita (centenas de avisos por figura) | `rdflib` fixado em 7.0.x com o `pyparsing` original; ambiente sem conflitos (`pip check`) |
| ~10:05 | Corpus limpo de Economia: 99.383 → 58.222 trabalhos | A exigência de abstract em inglês remove ~41% dos trabalhos brutos em Economia | Registrado; entra no funil de filtros (T12) |

**Lição para a tese (reprodutibilidade):** as duas APIs abertas impõem cotas diárias que
dominam o tempo de construção das bases. Com credenciais gratuitas, cada base custa ~1 mil
créditos de coleta + ~2 mil de enriquecimento no OpenAlex e ~30 mil leituras no ORCID — as 4 bases
cabem em 1–2 dias. Sem credenciais, levariam mais de uma semana. Registrar essas condições permite
a terceiros reproduzir o protocolo.

## Estado e próximos passos
- **Feito:** código das camadas 1–3, ontologia (TBox validada), exportação RDF, diagnóstico de sinal,
  testes; cliente robusto a cotas. Bruto de Economia coletado; 7.247 trabalhos já com tópicos em cache.
- **Bloqueado até ter as credenciais:** concluir a higienização de Economia (ORCID), coletar
  Matemática, Computação e Medicina (OpenAlex) e rodar o enriquecimento das 4 bases.
- **Depois:** KG v2 (tópicos e instituições no grafo de aprendizado) e testes T6/T7.

## Referência
- KATZ, J. S.; MARTIN, B. R. What is research collaboration? *Research Policy*, v. 26, n. 1,
  p. 1–18, 1997.
