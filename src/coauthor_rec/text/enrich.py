"""Enriquecimento do KG com IA Generativa (§4.3.3).

Extrai atributos de alto nível dos abstracts via LLM: tipo de artigo, tipo de contribuição,
estilo de escrita, métodos e tópico proposto (ProposedSubject / WritingStyle). Suporta dois
provedores (OpenAI e Anthropic/Claude) com o MESMO esquema, permitindo comparar a concordância.

As chaves vêm de variáveis de ambiente / .env (gitignored) — nunca hardcoded.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# Vocabulários fixos (facilitam virar nós categóricos no KG e comparar provedores).
PAPER_TYPES = ["empirical", "theoretical", "methodological", "review", "application", "other"]
CONTRIBUTIONS = ["new_method", "new_dataset", "benchmark", "theory", "application", "survey", "tool", "other"]
STYLES = ["formal_technical", "mathematical", "descriptive", "accessible"]

SYSTEM = (
    "You analyze scientific paper abstracts and extract structured attributes. "
    "Respond with ONLY a JSON object, no prose."
)
PROMPT = """Given the paper title and abstract, return a JSON object with exactly these keys:
- "paper_type": one of {paper_types}
- "contribution": one of {contributions}
- "writing_style": one of {styles}
- "methods": array of up to 3 short lowercase technique keywords
- "topic": a short noun phrase (the proposed subject)

TITLE + ABSTRACT:
{text}
"""


def _load_env():
    """Carrega .env do projeto (sem dependência forte de python-dotenv)."""
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    except Exception:
        pass


def _build_prompt(text: str) -> str:
    return PROMPT.format(paper_types=PAPER_TYPES, contributions=CONTRIBUTIONS,
                         styles=STYLES, text=text[:4000])


def _coerce(d: dict) -> dict:
    """Normaliza para os vocabulários fixos (rótulos fora do conjunto -> 'other')."""
    def pick(v, allowed):
        v = (v or "").strip().lower().replace(" ", "_")
        return v if v in allowed else allowed[-1]
    methods = d.get("methods") or []
    if isinstance(methods, str):
        methods = [methods]
    return {
        "paper_type": pick(d.get("paper_type"), PAPER_TYPES),
        "contribution": pick(d.get("contribution"), CONTRIBUTIONS),
        "writing_style": pick(d.get("writing_style"), STYLES),
        "methods": [str(m).strip().lower() for m in methods[:3]],
        "topic": str(d.get("topic", "")).strip()[:120],
    }


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].lstrip("json").strip()
    start, end = raw.find("{"), raw.rfind("}")
    return json.loads(raw[start:end + 1]) if start >= 0 else {}


def extract_openai(text: str, model: str = "gpt-4o-mini") -> dict:
    _load_env()
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], max_retries=8)  # backoff em 429 (TPM)
    resp = client.chat.completions.create(
        model=model, temperature=0, response_format={"type": "json_object"},
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": _build_prompt(text)}],
    )
    return _coerce(_parse_json(resp.choices[0].message.content))


def extract_anthropic(text: str, model: str = "claude-haiku-4-5-20251001") -> dict:
    _load_env()
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=model, max_tokens=300, temperature=0, system=SYSTEM,
        messages=[{"role": "user", "content": _build_prompt(text)}],
    )
    return _coerce(_parse_json(resp.content[0].text))


EXTRACTORS = {"openai": extract_openai, "anthropic": extract_anthropic}


def enrich_papers(texts: list[str], work_ids: list[str], provider: str,
                  model: str | None = None, workers: int = 12, log=print) -> list[dict]:
    """Extrai atributos para (work_id, texto) com concorrência. Mantém a ordem de entrada."""
    from concurrent.futures import ThreadPoolExecutor

    fn = EXTRACTORS[provider]
    kwargs = {"model": model} if model else {}
    results: list[dict | None] = [None] * len(texts)
    done = [0]

    def work(i):
        try:
            attrs = fn(texts[i], **kwargs)
        except Exception as exc:  # robustez a falhas pontuais de API
            log(f"  [aviso] {provider} falhou em {work_ids[i]}: {exc}")
            attrs = _coerce({})
        results[i] = {"work_id": work_ids[i], "provider": provider, **attrs}
        done[0] += 1
        if done[0] % 200 == 0:
            log(f"  {provider}: {done[0]}/{len(texts)}")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(work, range(len(texts))))
    return results
