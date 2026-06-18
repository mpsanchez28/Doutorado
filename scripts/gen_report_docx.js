const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  AlignmentType, LevelFormat, TableOfContents, HeadingLevel, BorderStyle,
  WidthType, ShadingType, VerticalAlign, PageNumber, PageBreak, Footer,
} = require("docx");

const ROOT = process.argv[2];          // diretório do projeto
const OUT = process.argv[3];
const D = JSON.parse(fs.readFileSync(ROOT + "/runs/final_comparison.json"));

const AC = "1F4E79", ZEBRA = "EEF3F8", GOOD = "DDEBD8", CW = 9360;
const border = { style: BorderStyle.SINGLE, size: 1, color: "BBBBBB" };
const borders = { top: border, bottom: border, left: border, right: border };
const cm = { top: 60, bottom: 60, left: 90, right: 90 };
const txt = (t, o = {}) => new TextRun({ text: t, ...o });
const P = (c, o = {}) => new Paragraph({ children: Array.isArray(c) ? c : [txt(c)], ...o });
const H = (n, t) => new Paragraph({ heading: n, children: [txt(t)] });

function hc(t, w) { return new TableCell({ borders, width: { size: w, type: WidthType.DXA }, margins: cm, shading: { fill: AC, type: ShadingType.CLEAR }, verticalAlign: VerticalAlign.CENTER, children: [P([txt(t, { bold: true, color: "FFFFFF", size: 18 })])] }); }
function bc(t, w, o = {}) { return new TableCell({ borders, width: { size: w, type: WidthType.DXA }, margins: cm, shading: o.fill ? { fill: o.fill, type: ShadingType.CLEAR } : undefined, verticalAlign: VerticalAlign.CENTER, children: [P([txt(String(t), { bold: !!o.bold, size: 18 })], { alignment: o.align || AlignmentType.LEFT })] }); }
function table(widths, header, rows) {
  const tr = [new TableRow({ tableHeader: true, children: header.map((h, i) => hc(h, widths[i])) })];
  rows.forEach((r, ri) => tr.push(new TableRow({ children: r.map((c, i) => bc(c.t ?? c, widths[i], { fill: c.fill ?? (ri % 2 ? ZEBRA : undefined), bold: c.bold, align: c.align })) })));
  return new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: widths, rows: tr });
}
const bullets = items => items.map(it => new Paragraph({ numbering: { reference: "b", level: 0 }, children: Array.isArray(it) ? it : [txt(it)] }));
const img = (file, w, h) => new Paragraph({ alignment: AlignmentType.CENTER, children: [new ImageRun({ type: "png", data: fs.readFileSync(ROOT + "/docs/" + file), transformation: { width: w, height: h }, altText: { title: file, description: file, name: file } })] });

const M = ["Topology (Graph Coauthor)","Ideal Topology (Oracle)","Hybrid (Graph + RandomForest)","Text (SciBERT)","GNN-rerank","Hybrid-cand","Sup-Hybrid"];
const L = { "Topology (Graph Coauthor)":"Baseline (CN)","Ideal Topology (Oracle)":"Oráculo (teto)","Hybrid (Graph + RandomForest)":"Híbrido RF","Text (SciBERT)":"Texto (SciBERT)","GNN-rerank":"GNN-rerank","Hybrid-cand":"Cand. híbridos","Sup-Hybrid":"Sup-Hybrid" };
const cnt = D[M[0]].regime_counts;
const fmt = (m, scope, mk, k) => {
  const o = scope === "overall" ? D[m].overall : D[m].by_regime[scope];
  const c = scope === "overall" ? D[m].overall_ci : D[m].by_regime_ci[scope];
  return `${(o[k][mk]*100).toFixed(2)} [${(c[k][mk][0]*100).toFixed(1)}–${(c[k][mk][1]*100).toFixed(1)}]`;
};
// melhor realista (exclui oráculo) p/ negrito
function best(scope, mk, k){ let b=null,bv=-1; M.forEach(m=>{ if(m==="Ideal Topology (Oracle)")return; const o=scope==="overall"?D[m].overall:D[m].by_regime[scope]; if(o[k][mk]>bv){bv=o[k][mk];b=m;}}); return b; }
function metricTable(scope, mk, ks){
  const rows = M.map(m => [ {t:L[m]}, ...ks.map(k=>({t:fmt(m,scope,mk,k), bold:(m===best(scope,mk,k)), fill:(m===best(scope,mk,k))?GOOD:undefined, align:AlignmentType.RIGHT})) ]);
  const w0=2400, wk=Math.floor((CW-w0)/ks.length);
  return table([w0, ...ks.map(()=>wk)], ["Modelo", ...ks.map(k=>`@${k}`)], rows);
}

const doc = new Document({
  styles: { default: { document: { run: { font: "Arial", size: 21 } } }, paragraphStyles: [
    { id:"Heading1", name:"Heading 1", basedOn:"Normal", next:"Normal", quickFormat:true, run:{size:28,bold:true,color:AC,font:"Arial"}, paragraph:{spacing:{before:300,after:140},outlineLevel:0} },
    { id:"Heading2", name:"Heading 2", basedOn:"Normal", next:"Normal", quickFormat:true, run:{size:23,bold:true,color:AC,font:"Arial"}, paragraph:{spacing:{before:200,after:100},outlineLevel:1} } ] },
  numbering: { config: [
    { reference:"b", levels:[{level:0,format:LevelFormat.BULLET,text:"•",alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:540,hanging:280}}}}] },
    { reference:"n", levels:[{level:0,format:LevelFormat.DECIMAL,text:"%1.",alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:540,hanging:280}}}}] } ] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, border:{top:{style:BorderStyle.SINGLE,size:4,color:AC,space:6}}, children: [txt("coauthor-rec · Relatório de Avaliação · pág. ", {size:16,color:"666666"}), new TextRun({children:[PageNumber.CURRENT],size:16,color:"666666"})] })] }) },
    children: [
      ...Array(4).fill(0).map(()=>P("")),
      P([txt("Predição de Coautorias com CNN e GNN", {size:40,bold:true,color:AC})],{alignment:AlignmentType.CENTER}),
      P("",{}),
      P([txt("Relatório de Avaliação — Comparação de Modelos", {size:24,color:"333333"})],{alignment:AlignmentType.CENTER}),
      ...Array(5).fill(0).map(()=>P("")),
      table([3000,6360],["Campo","Valor"],[
        ["Doutorando","Marcos Paulo Sanchez"],["Orientador","Prof. Dr. Luciano A. Digiampietri"],
        ["Programa","PPgSI — EACH/USP"],["Base","OpenAlex (snowball; 5.878 works / 19.120 autores)"],
        ["Protocolo","Split temporal T0→T1; IC95% bootstrap; PYTHONHASHSEED=0"],
      ]),
      new Paragraph({children:[new PageBreak()]}),
      P([txt("Sumário",{size:26,bold:true,color:AC})]),
      new TableOfContents("Sumário",{hyperlink:true,headingStyleRange:"1-2"}),
      new Paragraph({children:[new PageBreak()]}),

      H(HeadingLevel.HEADING_1,"1. Objetivo e arquitetura"),
      P("Sistema híbrido de recomendação de coautores que funde representações textuais (CNN/SciBERT) e estruturais (GNN heterogênea) sobre um Grafo de Conhecimento do OpenAlex, avaliado como predição de links futuros (T0→T1) nos regimes warm/cool/cold. Este relatório consolida a avaliação comparativa dos modelos construídos."),
      P([txt("Cobertura da arquitetura proposta (Figura 1 da qualificação):", {bold:true})]),
      table([4600,4760],["Componente","Estado"],[
        ["OpenAlex → KG heterogêneo (5 entidades/6 relações)","Concluído"],
        ["Enriquecimento GenAI (estilo/assunto via LLM)","Feito; não melhorou a GNN"],
        ["CNN + SciBERT → embedding textual","Concluído"],
        ["GNN heterogênea → embedding estrutural","Concluído (H-GraphSAGE)"],
        ["Fusão multimodal (Eq.10)","Concluído; empatou com a GNN"],
        ["Produção: ranking de candidatos → Top-K","Concluído (gargalo identificado)"],
        ["Avaliação: GT, regimes, métricas, estatística","Concluído (+newcomer, +bootstrap)"],
      ]),

      H(HeadingLevel.HEADING_1,"2. Materiais e método"),
      ...bullets([
        [txt("Corpus: ",{bold:true}), txt("snowball no OpenAlex; após limpeza, 5.878 artigos e 19.120 autores; gate de qualidade aprovado. Teto de 50 coautores/artigo (anti-consórcio).")],
        [txt("Split temporal: ",{bold:true}), txt("80% works mais antigos = T0 (treino); 20% recentes = T1 (teste). Ground truth = novas coautorias C_new = C_future \\ C_past.")],
        [txt("Regimes: ",{bold:true}), txt(`warm (≥5 coautores em T0, n=${cnt.warm}), cool (1–4, n=${cnt.cool}), cold (0 mas ≥1 artigo, n=${cnt.cold}); newcomers sem artigo em T0 (n=${cnt.newcomer}) reportados à parte.`)],
        [txt("Métricas: ",{bold:true}), txt("Precision@K, Recall@K, F1@K, NDCG@K, MRR@K, MAP — K ∈ {5,10,20,50,100,200}.")],
        [txt("Estatística: ",{bold:true}), txt("IC95% por bootstrap (100 reamostragens de autores); testes pareados Wilcoxon com correção de Bonferroni. Execução com PYTHONHASHSEED=0 (reprodutível).")],
      ]),

      H(HeadingLevel.HEADING_1,"3. Resultados"),
      H(HeadingLevel.HEADING_2,"3.1 Métricas gerais (média [IC95%], %)"),
      P([txt("Recall@K — ",{bold:true}), txt("verde = melhor modelo realista (exclui o oráculo, que é o teto).")]),
      metricTable("overall","R",[10,50,200]),
      P("",{}),
      P([txt("Qualidade de ranqueamento no topo (NDCG@10 e MRR@10):",{bold:true})]),
      metricTable("overall","NDCG",[5,10]),
      P("",{}),
      H(HeadingLevel.HEADING_2,"3.2 Gráficos — métricas × K (barras = IC95%)"),
      P([txt("Regime geral (n="+Object.values(cnt).reduce((a,b)=>a+b,0)+"):",{bold:true})]),
      img("metricas_overall.png", 600, 337),
      P([txt("Regime cool (n="+cnt.cool+") — onde o multimodal tem valor:",{bold:true})]),
      img("metricas_cool.png", 600, 337),

      H(HeadingLevel.HEADING_1,"4. Análise crítica (qual venceu, e por quê)"),
      ...bullets([
        [txt("Melhor cobertura (Recall@200): ",{bold:true}), txt("Híbrido RF e Candidatos híbridos empatam (~14,8%; diferença dentro do IC, não significativa).")],
        [txt("Melhor no topo do ranking (MRR/NDCG/MAP): ",{bold:true}), txt("o Baseline (Common Neighbors) — a heurística simples ordena melhor as primeiras posições; modelos que ampliam candidatos ganham recall mas perdem precisão no topo.")],
        [txt("Ganho robusto do texto: ",{bold:true}), txt("apenas no regime cool — candidatos textuais alcançam coautores fora da vizinhança de 2 saltos, furando o teto do oráculo topológico. É onde a hipótese da tese se sustenta.")],
        [txt("Não funcionaram como esperado: ",{bold:true}), txt("GNN-rerank e fusão end-to-end empataram com a topologia; o enriquecimento GenAI (categorias no KG) foi neutro/negativo; o ranqueador supervisionado sobre o pool híbrido piorou o topo. A fusão útil é de FONTES DE CANDIDATOS, não de representações.")],
      ]),
      P([txt("Significância (Wilcoxon + Bonferroni): ",{bold:true}), txt("o Híbrido RF é significativamente melhor que GNN/texto em R@50 e NDCG@10; nenhuma abordagem multimodal o supera de forma robusta. O único ganho significativo do texto/híbrido é em cool (R@10).")]),

      H(HeadingLevel.HEADING_1,"5. Conclusão e próximos passos"),
      P([txt("Conclusão: ",{bold:true}), txt("o Híbrido RF (topológico supervisionado) permanece o melhor modelo geral; o multimodal agrega valor de forma localizada e robusta no regime cool (baixa conectividade), graças ao alcance de candidatos via texto. A contribuição metodológica é caracterizar onde o multimodal ajuda e onde a topologia basta.")]),
      ...bullets([
        [txt("Ressalva estatística: ",{bold:true}), txt("cool tem IC largo (n=78) e cold é inconclusivo (n=3) neste corpus — diferenças nesses regimes são sugestivas, não conclusivas.")],
        "Próximo: aprofundar cool/cold com um corpus com mais autores de baixa conectividade, para fortalecer estatisticamente o ganho do multimodal.",
        "Direção promissora: ranqueador que preserve a precisão do RF no topo sobre o pool de candidatos ampliado (estrutura ∪ texto).",
      ]),
    ],
  }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(OUT, b); console.log("escrito", OUT, (b.length/1024|0)+"KB"); });
