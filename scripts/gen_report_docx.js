const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  AlignmentType, LevelFormat, TableOfContents, HeadingLevel, BorderStyle,
  WidthType, ShadingType, VerticalAlign, PageNumber, PageBreak, Footer,
} = require("docx");

const ROOT = process.argv[2], OUT = process.argv[3];
const D = JSON.parse(fs.readFileSync(ROOT + "/runs/final_comparison.json"));        // base médica (todos modelos)
const AI = JSON.parse(fs.readFileSync(ROOT + "/runs/cool_cold_frac0.8.json"));       // base IA (cool/cold)

const AC = "1F4E79", ZEBRA = "EEF3F8", GOOD = "DDEBD8", BAD = "F8D7DA", CW = 9360;
const bd = { style: BorderStyle.SINGLE, size: 1, color: "BBBBBB" };
const borders = { top: bd, bottom: bd, left: bd, right: bd };
const cm = { top: 60, bottom: 60, left: 90, right: 90 };
const txt = (t, o = {}) => new TextRun({ text: t, ...o });
const P = (c, o = {}) => new Paragraph({ children: Array.isArray(c) ? c : [txt(c)], ...o });
const H = (n, t) => new Paragraph({ heading: n, children: [txt(t)] });
const hc = (t, w) => new TableCell({ borders, width: { size: w, type: WidthType.DXA }, margins: cm, shading: { fill: AC, type: ShadingType.CLEAR }, verticalAlign: VerticalAlign.CENTER, children: [P([txt(t, { bold: true, color: "FFFFFF", size: 18 })])] });
const bc = (t, w, o = {}) => new TableCell({ borders, width: { size: w, type: WidthType.DXA }, margins: cm, shading: o.fill ? { fill: o.fill, type: ShadingType.CLEAR } : undefined, verticalAlign: VerticalAlign.CENTER, children: [P([txt(String(t), { bold: !!o.bold, size: 18 })], { alignment: o.align || AlignmentType.LEFT })] });
function table(widths, header, rows) {
  const tr = [new TableRow({ tableHeader: true, children: header.map((h, i) => hc(h, widths[i])) })];
  rows.forEach((r, ri) => tr.push(new TableRow({ children: r.map((c, i) => bc(c.t ?? c, widths[i], { fill: c.fill ?? (ri % 2 ? ZEBRA : undefined), bold: c.bold, align: c.align })) })));
  return new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: widths, rows: tr });
}
const bullets = items => items.map(it => new Paragraph({ numbering: { reference: "b", level: 0 }, children: Array.isArray(it) ? it : [txt(it)] }));
const numbered = items => items.map(it => new Paragraph({ numbering: { reference: "n", level: 0 }, children: Array.isArray(it) ? it : [txt(it)] }));
const img = (file, w, h) => new Paragraph({ alignment: AlignmentType.CENTER, children: [new ImageRun({ type: "png", data: fs.readFileSync(ROOT + "/docs/" + file), transformation: { width: w, height: h }, altText: { title: file, description: file, name: file } })] });

const R = (j, m, scope, mk, k) => (scope === "overall" ? j[m].overall : j[m].by_regime[scope])[k][mk] * 100;
const cnt = D["Topology (Graph Coauthor)"].regime_counts;
const aicnt = AI["Topology (Graph Coauthor)"].regime_counts;

const BASE = "Topology (Graph Coauthor)";
const MM = [["Hybrid (Graph + RandomForest)","Híbrido RF"],["Text (SciBERT)","Texto (SciBERT)"],
            ["GNN-rerank","GNN-rerank"],["Hybrid-cand","Cand. híbridos"],["Sup-Hybrid","Sup-Hybrid"],
            ["Ideal Topology (Oracle)","Oráculo (teto)"]];
const baselineCmp = () => {
  const b200 = R(D, BASE, "overall", "R", "200");
  const rows = [[{t:"Baseline (Common Neighbors)"},{t:b200.toFixed(2),align:AlignmentType.RIGHT},{t:"—",align:AlignmentType.RIGHT},{t:R(D,BASE,"overall","MRR","10").toFixed(2),align:AlignmentType.RIGHT},{t:R(D,BASE,"overall","NDCG","10").toFixed(2),align:AlignmentType.RIGHT}]];
  MM.forEach(([m,l])=>{ const r=R(D,m,"overall","R","200"); const dl=r-b200;
    rows.push([{t:l},{t:r.toFixed(2),align:AlignmentType.RIGHT},
      {t:(dl>=0?"+":"")+dl.toFixed(2),align:AlignmentType.RIGHT,fill:(m!=="Ideal Topology (Oracle)"&&dl>0)?GOOD:(dl<0?BAD:undefined),bold:true},
      {t:R(D,m,"overall","MRR","10").toFixed(2),align:AlignmentType.RIGHT},
      {t:R(D,m,"overall","NDCG","10").toFixed(2),align:AlignmentType.RIGHT}]); });
  return table([3200,1500,1500,1580,1580],["Modelo","Recall@200","Δ vs Baseline","MRR@10","NDCG@10"],rows);
};
const aiTable = () => {
  const MA=[["Topology (Graph Coauthor)","Baseline (CN)"],["Hybrid (Graph + RandomForest)","Híbrido RF"],["Text (SciBERT)","Texto"],["Hybrid-cand","Cand. híbridos"]];
  const rows=MA.map(([m,l])=>{ const co=R(AI,m,"cool","R","200"), cd=R(AI,m,"cold","R","200");
    return [{t:l},{t:co.toFixed(1),align:AlignmentType.RIGHT,fill:co>=7?GOOD:undefined},
            {t:cd.toFixed(1),align:AlignmentType.RIGHT,fill:cd>=4?GOOD:(cd<0.1?BAD:undefined),bold:true}]; });
  return table([4000,2680,2680],["Modelo",`cool R@200 (n=${aicnt.cool})`,`cold R@200 (n=${aicnt.cold})`],rows);
};

const doc = new Document({
  styles: { default:{document:{run:{font:"Arial",size:21}}}, paragraphStyles:[
    {id:"Heading1",name:"Heading 1",basedOn:"Normal",next:"Normal",quickFormat:true,run:{size:28,bold:true,color:AC,font:"Arial"},paragraph:{spacing:{before:300,after:140},outlineLevel:0}},
    {id:"Heading2",name:"Heading 2",basedOn:"Normal",next:"Normal",quickFormat:true,run:{size:23,bold:true,color:AC,font:"Arial"},paragraph:{spacing:{before:200,after:100},outlineLevel:1}}]},
  numbering:{config:[
    {reference:"b",levels:[{level:0,format:LevelFormat.BULLET,text:"•",alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:540,hanging:280}}}}]},
    {reference:"n",levels:[{level:0,format:LevelFormat.DECIMAL,text:"%1.",alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:540,hanging:280}}}}]}]},
  sections:[{
    properties:{page:{size:{width:12240,height:15840},margin:{top:1440,right:1440,bottom:1440,left:1440}}},
    footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.CENTER,border:{top:{style:BorderStyle.SINGLE,size:4,color:AC,space:6}},children:[txt("coauthor-rec · Relatório de Avaliação · pág. ",{size:16,color:"666666"}),new TextRun({children:[PageNumber.CURRENT],size:16,color:"666666"})]})]})},
    children:[
      ...Array(4).fill(0).map(()=>P("")),
      P([txt("Predição de Coautorias com CNN e GNN",{size:40,bold:true,color:AC})],{alignment:AlignmentType.CENTER}),
      P(""), P([txt("Relatório de Avaliação — Desenvolvimento, Avanços e Comparação",{size:23,color:"333333"})],{alignment:AlignmentType.CENTER}),
      ...Array(5).fill(0).map(()=>P("")),
      table([3000,6360],["Campo","Valor"],[
        ["Doutorando","Marcos Paulo Sanchez"],["Orientador","Prof. Dr. Luciano A. Digiampietri"],
        ["Programa","PPgSI — EACH/USP"],
        ["Bases","Médica (snowball, 19.120 autores) e IA temática (45.732 autores)"],
        ["Protocolo","Split temporal T0→T1; IC95% bootstrap; Wilcoxon+Bonferroni; PYTHONHASHSEED=0"],
      ]),
      new Paragraph({children:[new PageBreak()]}),
      P([txt("Sumário",{size:26,bold:true,color:AC})]),
      new TableOfContents("Sumário",{hyperlink:true,headingStyleRange:"1-2"}),
      new Paragraph({children:[new PageBreak()]}),

      H(HeadingLevel.HEADING_1,"1. Objetivo"),
      P("Desenvolver e avaliar um sistema híbrido de recomendação de coautores que combina representações textuais (CNN/SciBERT) e estruturais (GNN heterogênea) sobre um Grafo de Conhecimento do OpenAlex, tratando a recomendação como predição de links futuros (T0→T1). Este relatório descreve, passo a passo, o que foi feito, os avanços encontrados e a comparação com o modelo de referência (baseline)."),

      H(HeadingLevel.HEADING_1,"2. Passo a passo do desenvolvimento"),
      P("Cada etapa foi construída de forma incremental, testada e avaliada sob o mesmo protocolo. Resumo do que foi feito e o achado de cada etapa:"),
      ...numbered([
        [txt("Coleta e preparação (OpenAlex): ",{bold:true}),txt("pipeline de coleta (snowball e temática), limpeza (inglês, ano≥2004, deduplicação) e gate de qualidade. Resultado: bases reprodutíveis e versionadas.")],
        [txt("Grafo de Conhecimento heterogêneo: ",{bold:true}),txt("5 entidades (autor, artigo, instituição, venue, conceito) e 6 relações; teto anti-consórcio de 50 coautores/artigo. Resultado: KG materializado em PyTorch Geometric.")],
        [txt("Baselines de referência: ",{bold:true}),txt("Common Neighbors (baseline), oráculo topológico (teto) e Random Forest sobre features topológicas. Achado: o RF melhora o recall sobre o baseline.")],
        [txt("Módulo textual (CNN/BERT): ",{bold:true}),txt("comparação de encoders (TF-IDF, BERT, SciBERT, SPECTER). Achado: SciBERT≈SPECTER > BERT > TF-IDF; texto forte na baixa conectividade.")],
        [txt("GNN heterogênea: ",{bold:true}),txt("reranker sobre candidatos de 2 saltos com features textuais nos nós. Achado: competitiva, mas não supera o RF; ranqueador da GNN é fraco.")],
        [txt("Fusão end-to-end CNN+GNN (Eq. 10): ",{bold:true}),txt("treino conjunto. Achado: empatou com a GNN; fundir representações não bastou.")],
        [txt("Enriquecimento GenAI (OpenAI + Claude): ",{bold:true}),txt("extração de atributos de alto nível dos abstracts (estilo, tipo de contribuição) como nós do KG. Achado: neutro/negativo — categorias ruidosas e de baixa variância.")],
        [txt("Candidatos híbridos (estrutura ∪ texto): ",{bold:true}),txt("ampliar o pool com vizinhos textuais. Achado: empata o RF no geral e o supera em cobertura; o gargalo era a geração de candidatos, não a representação.")],
        [txt("Base de IA temática + cold-start: ",{bold:true}),txt("coleta focada em IA (45.732 autores) que populou os regimes cool/cold. Achado central: ver Seção 5.")],
      ]),

      H(HeadingLevel.HEADING_1,"3. Comparação com o baseline (base médica, geral)"),
      P([txt("Δ vs Baseline = ganho/perda em Recall@200 sobre o Common Neighbors. ",{}),txt("Verde = ganho; vermelho = perda. Oráculo é o teto (não é modelo operacional).",{italics:true})]),
      baselineCmp(),
      P([txt("Leitura: ",{bold:true}),txt("o Híbrido RF e os Candidatos híbridos melhoram o recall sobre o baseline (~+1,6pp em R@200); a GNN fica abaixo. Porém, no topo do ranking (MRR@10/NDCG@10), o próprio Baseline é o melhor entre os modelos realistas — a heurística simples ordena bem as primeiras posições. Testes pareados (Wilcoxon+Bonferroni) confirmam: RF > Baseline em recall é significativo; nenhuma abordagem multimodal supera o RF no topo, na base médica.")],{spacing:{before:120}}),

      H(HeadingLevel.HEADING_1,"4. Gráficos (base médica)"),
      P([txt(`Métricas × K, regime geral (n=${Object.values(cnt).reduce((a,b)=>a+b,0)}; barras = IC95%):`,{bold:true})]),
      img("metricas_overall.png",600,337),

      H(HeadingLevel.HEADING_1,"5. Avanço principal: cold-start na base de IA"),
      P("Na base médica (snowball denso), os regimes de baixa conectividade eram pequenos demais (cool n=78, cold n=3) para conclusões. Coletamos uma base temática de IA e correlatas (45.732 autores), que por ser menos densa populou esses regimes: cool n=783, cold n=53. Com poder estatístico real, o avanço fica claro:"),
      aiTable(),
      P([txt("Cold-start (autores sem coautoria em T0): os modelos topológicos ZERAM ",{bold:true}),txt("— a vizinhança de 2 saltos é vazia, não há candidatos. Apenas o texto recomenda corretamente (Texto vs RF: +6,2pp em R@200, p=0,0009). Em cool, texto/candidatos híbridos superam o RF de forma altamente significativa (+4,0pp, p=1,2×10⁻²³).")],{spacing:{before:120}}),
      img("ai_cool_cold.png",620,238),

      H(HeadingLevel.HEADING_1,"6. Avanços encontrados (síntese)"),
      ...bullets([
        [txt("RF > Baseline em recall: ",{bold:true}),txt("o re-ranqueamento supervisionado recupera mais coautores futuros (significativo).")],
        [txt("O gargalo é a geração de candidatos: ",{bold:true}),txt("fundir FONTES de candidatos (estrutura ∪ texto) empata/melhora o RF; fundir representações (GNN, end-to-end) ou enriquecer com categorias GenAI, não.")],
        [txt("Cold-start resolvido pelo texto (avanço central): ",{bold:true}),txt("onde a topologia falha por construção (0% de recall), a semântica textual é a única fonte de sinal — confirmando a hipótese da tese exatamente onde é decisiva.")],
        [txt("Complementaridade caracterizada: ",{bold:true}),txt("topologia domina autores bem conectados (warm) e o topo do ranking; texto domina baixa/nenhuma conectividade (cool/cold).")],
      ]),

      H(HeadingLevel.HEADING_1,"7. Conclusão e próximos passos"),
      P([txt("Conclusão: ",{bold:true}),txt("o baseline topológico e o Híbrido RF são fortes para pesquisadores bem conectados, mas insuficientes (cool) ou nulos (cold) no cold-start; é aí que o multimodal/textual é essencial e estatisticamente comprovado. A contribuição da tese é caracterizar onde cada fonte de informação importa e mostrar que a fusão útil é de fontes de candidatos.")]),
      ...bullets([
        "Rodar o pipeline completo (GNN + fusão) na base de IA para confirmar o quadro com todos os modelos.",
        "Ranqueador que preserve a precisão do RF no topo sobre o pool de candidatos ampliado.",
        "Recalibrar o gate de qualidade para coletas temáticas (mean_coauthor_weight menor).",
      ]),
    ],
  }],
});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync(OUT,b);console.log("escrito",OUT,(b.length/1024|0)+"KB");});
