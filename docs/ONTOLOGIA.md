# Ontologia do grafo de conhecimento

Resposta à crítica da banca de que o grafo era uma **rede heterogênea**, e não um **grafo de
conhecimento**. Arquivos: TBox em `configs/ontology/coauthor-rec.ttl`; exportação e validação
em `src/coauthor_rec/graph/ontology.py`; amostras por base em
`data/processed/enrich_<base>/kg_sample.ttl` (geradas por `scripts/enrich_base.py`).

## 1. Por que uma ontologia

Uma rede heterogênea tem nós e arestas de vários tipos, mas os tipos são só rótulos. Um grafo
de conhecimento exige, além disso, (i) entidades e relações com **significado definido num
esquema formal**, (ii) **identificadores** que permitam ligar o grafo a outras fontes e (iii)
**proveniência** — saber de onde vem cada fato (Hogan et al., 2021). A ontologia mínima aqui
definida dá esses três elementos ao grafo da tese, sem alterar o que os modelos aprendem: é a
camada semântica que documenta, valida e permite consultar e explicar o grafo.

## 2. Princípios de modelagem

1. **Reusar vocabulários estabelecidos** em vez de inventar termos. Cada classe e propriedade
   própria (`cr:`) é declarada como especialização (`rdfs:subClassOf` / `rdfs:subPropertyOf`)
   de um termo consolidado: FOAF e Schema.org (pessoas e organizações), SPAR FaBiO e CiTO
   (obras e citações; Peroni; Shotton, 2012), SKOS (hierarquia temática), W3C ORG (vínculos
   com período) e PROV-O (proveniência). Usa-se especialização, e não equivalência, por
   prudência: os termos próprios são mais restritos que os externos.
2. **Relações n-árias como nós.** Autoria, coautoria, atribuição de tópico e vínculo
   profissional carregam atributos próprios (instituição, nível de evidência, score, período).
   Seguindo o padrão do W3C para relações n-árias, cada uma vira um nó (`cr:Authorship`,
   `cr:CoAuthorship`, `cr:TopicAssignment`, `cr:Employment`).
3. **A qualidade dos dados é parte do grafo.** Os níveis de evidência da higienização (A/B/C de
   identidade; I1/I2/I3 de vínculo institucional) são propriedades da autoria — o grafo registra
   o quanto cada fato é confiável.
4. **Identificadores persistentes e `owl:sameAs`** para ORCID, DOI, ROR, Wikidata e OpenAlex,
   ligando o grafo à nuvem de dados abertos.

## 3. Classes

| Classe | Especializa | Significado | Fonte |
|---|---|---|---|
| `cr:Author` | `foaf:Person`, `schema:Person`, `prov:Agent` | Pessoa canônica (ORCID quando houver) | OpenAlex + ORCID |
| `cr:Work` | `fabio:Expression`, `schema:CreativeWork` | Trabalho científico | OpenAlex |
| `cr:Authorship` | `prov:Attribution` | Autor × trabalho × instituição, com posição e nível de evidência | OpenAlex + higienização |
| `cr:CoAuthorship` | — | Aresta de coautoria reificada: peso, primeiro ano, menor nível de evidência | derivada |
| `cr:Institution` | `foaf:Organization`, `schema:Organization`, `org:FormalOrganization` | Instituição (com ROR) | OpenAlex Institutions |
| `cr:Venue` | `schema:CreativeWorkSeries` | Veículo de publicação | OpenAlex Sources |
| `cr:Country` | `schema:Country` | País | OpenAlex |
| `cr:Topic`, `cr:Subfield`, `cr:Field`, `cr:Domain` | `skos:Concept` | Hierarquia OpenAlex Topics (`cr:TopicScheme`) | OpenAlex Topics |
| `cr:TopicAssignment` | — | Trabalho × tópico, com score | OpenAlex Topics |
| `cr:Employment` | `org:Membership` | Vínculo profissional com período | ORCID |
| `cr:Education` | — | Formação com período | ORCID |

## 4. Propriedades

| Propriedade | Domínio → contradomínio | Especializa / característica | Uso |
|---|---|---|---|
| `cr:wrote` | Author → Work | inversa de `dcterms:creator` | autoria |
| `cr:hasAuthorship`, `cr:agent`, `cr:atInstitution` | Work → Authorship → Author / Institution | `prov:agent` | autoria n-ária |
| `cr:coAuthorWith` | Author ↔ Author | `foaf:knows`; **simétrica** | rede de coautoria (alvo da predição) |
| `cr:between` | CoAuthorship → Author | — | aresta reificada |
| `cr:cites` | Work → Work | `cito:cites` | citação |
| `cr:publishedIn` | Work → Venue | `schema:isPartOf` | veículo |
| `cr:hasTopic`, `cr:topicAssignment`, `cr:topic` | Work → Topic | `dcterms:subject` | semântica temática |
| `cr:broader` | Topic → Subfield → Field → Domain | `skos:broader` | hierarquia |
| `cr:affiliatedWith` | Author → Institution | `schema:affiliation` | vínculo (das autorias) |
| `cr:partOf` | Institution → Institution | `schema:parentOrganization`; **transitiva** | hierarquia institucional |
| `cr:relatedInstitution` | Institution ↔ Institution | **simétrica** | associação declarada |
| `cr:locatedIn` | Institution → Country | `schema:location` | geografia |
| `cr:hasEmployment`, `cr:hasEducation`, `cr:organization` | Author → Employment/Education → organização | `org:organization` | trajetória (ORCID) |
| `cr:exColleagueOf` | Author ↔ Author | **simétrica**; derivada até o ano de corte | ex-colegas |

Propriedades de dados: `cr:evidenceLevel` (A/B/C), `cr:institutionLevel` (I1/I2/I3),
`cr:authorPosition`, `cr:score`, `cr:weight`, `cr:year`, `cr:firstYear`, `cr:startYear`,
`cr:endYear`, `cr:institutionType` e os identificadores `cr:orcid`, `cr:doi`, `cr:ror`,
`cr:openalexId` (especializações de `schema:identifier`).

## 5. Exemplo (dados ilustrativos)

```turtle
kg:work/W1  a cr:Work ;  cr:doi "10.1/w1" ;  owl:sameAs <https://doi.org/10.1/w1> ;
            cr:hasAuthorship kg:authorship/W1_orcid_0000-0001 ;  cr:hasTopic kg:topic/T1 .
kg:authorship/W1_orcid_0000-0001  a cr:Authorship ;
            cr:agent kg:author/orcid_0000-0001 ;  cr:atInstitution kg:institution/I1 ;
            cr:evidenceLevel "A" ;  cr:institutionLevel "I1" ;  prov:wasDerivedFrom <https://orcid.org> .
kg:author/orcid_0000-0001  a cr:Author ;  foaf:name "Ana Souza" ;
            owl:sameAs <https://orcid.org/0000-0001> ;  cr:coAuthorWith kg:author/orcid_0000-0002 ;
            cr:exColleagueOf kg:author/orcid_0000-0002 .
kg:institution/I1  a cr:Institution ;  cr:ror "036rp1748" ;  cr:institutionType "education" ;
            owl:sameAs <https://ror.org/036rp1748> , <http://www.wikidata.org/entity/Q835960> ;
            cr:locatedIn kg:country/BR .
kg:topic/T1  a cr:Topic ;  skos:prefLabel "Macroeconomia" ;  cr:broader kg:subfield/2002 .
```

## 6. Ontologia × grafo de aprendizado

O grafo de aprendizado (PyTorch Geometric) é uma **projeção** do grafo de conhecimento: usa as
relações que alimentam os modelos e descarta reificações e metadados. Tornar a correspondência
explícita responde à pergunta da banca sobre quais relações o modelo de fato usa.

| No grafo de conhecimento | No grafo de aprendizado | Uso atual |
|---|---|---|
| `cr:coAuthorWith` (+ `cr:CoAuthorship.weight`) | aresta `co_author` com peso | estrutura (2-hop, RF, GNN) — **sinal principal** |
| `cr:wrote` | `writes` | GNN; agregação texto→autor |
| `cr:hasTopic` (Topics) | `has_topic` | a substituir os Concepts antigos (KG v2) |
| `cr:affiliatedWith`, `cr:partOf`, `cr:locatedIn` | `affiliated_with` (+ novas) | features do ranqueador (T6) |
| `cr:exColleagueOf` | feature de par | ranqueador (T6) |
| `cr:cites`, `cr:publishedIn` | `cites`, `published_in` | GNN (ablação: sem ganho) |
| níveis de evidência, proveniência, `owl:sameAs` | — | explicação, auditoria, ligação externa |

## 7. Validação
1. **TBox:** analisada com rdflib — 184 triplas, 14 classes, 20 propriedades de objeto, 14 de dados.
2. **ABox (amostra por base):** toda classe e propriedade `cr:` usada precisa estar declarada na
   TBox (`ontology.validate`); a serialização Turtle é relida para garantir que o arquivo é
   válido; consultas SPARQL de demonstração rodam sobre a amostra (resultados em
   `runs/<base>/enrich.json` e em `docs/ENRIQUECIMENTO.md`).
3. **Testes automatizados:** `tests/test_enrich.py` gera um grafo sintético, valida-o contra a
   TBox, executa as consultas e confere, por exemplo, que um par de coautores ex-colegas é
   recuperado pela consulta correspondente.

## 8. Limitações e extensões
- A validação verifica declarações, não restrições lógicas: não há raciocinador OWL nem regras
  de forma. Extensão natural: formas SHACL (cardinalidade, tipos de valor) e um raciocinador.
- O alinhamento é por especialização (conservador); equivalências exigiriam análise termo a termo.
- A exportação completa (milhões de triplas) é viável, mas desnecessária para os experimentos;
  publica-se uma amostra por base. Extensões previstas: veículos (`cr:Venue` populado), citações
  (`cr:cites`) e publicação como Linked Data.

## Referências
- HOGAN, A. et al. Knowledge graphs. *ACM Computing Surveys*, v. 54, n. 4, art. 71, 2021.
- PERONI, S.; SHOTTON, D. FaBiO and CiTO: ontologies for describing bibliographic resources and
  citations. *Journal of Web Semantics*, v. 17, p. 33–43, 2012.
- W3C. *Defining N-ary Relations on the Semantic Web*. W3C Working Group Note, 2006.
- W3C. *The Organization Ontology*. W3C Recommendation, 2014.
- W3C. *PROV-O: The PROV Ontology*. W3C Recommendation, 2013.
