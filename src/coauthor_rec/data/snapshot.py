"""Cópia congelada (imutável e identificada) das entradas de uma execução (ESPECIFICACAO §2, emenda E2).

Layout de uma cópia ``<dest>/``:
  raw/<base>/...           arquivos do bruto usados pela reconstrução (cópia byte a byte)
  t4/<base>_<c>/...         dados coletados pelo T4 (parquets, estado.json) e lacunas anteriores
  orcid/<orcid>.json        registros ORCID usados (um arquivo por registro, como o cache global)
  openalex/works.jsonl      registros de enriquecimento (subconjunto do cache global, por ID)
  openalex/institutions.jsonl
  configs/*.yaml            configurações vigentes
  MANIFEST.json             origem, tamanho e SHA-256 de cada arquivo; hash combinado por componente

Garantias: cópias físicas (nunca links); cada arquivo copiado é conferido contra a origem
(hash da origem antes e depois da cópia: se a origem mudou durante a cópia, falha); ao final a
árvore fica somente leitura. ``verify_snapshot`` recalcula tudo e falha em divergência ou ausência.
Um registro que não existe na origem é listado como ausente — nunca buscado.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path


class SnapshotError(RuntimeError):
    pass


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def _copy_checked(src: Path, dst: Path) -> dict:
    if src.is_symlink():
        raise SnapshotError(f"origem é link simbólico (não copiado): {src}")
    before = sha256_file(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)                      # cópia física de conteúdo (sem metadados nem links)
    after_src, copied = sha256_file(src), sha256_file(dst)
    if not (before == after_src == copied):
        raise SnapshotError(f"origem alterada durante a cópia ou cópia divergente: {src}")
    return {"origem": str(src), "bytes": dst.stat().st_size, "sha256": copied}


def _combined(entries: dict) -> str:
    h = hashlib.sha256()
    for k in sorted(entries):
        h.update(f"{k}\t{entries[k]['sha256']}\n".encode())
    return h.hexdigest()


def subset_jsonl(src: Path, dst: Path, ids: set) -> dict:
    """Copia de ``src`` (jsonl com campo ``id``) só os registros com id em ``ids``; ordem por id.
    Linhas incompletas (gravação concorrente) causam falha explícita."""
    recs = {}
    with open(src, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            if not line.endswith("\n"):
                raise SnapshotError(f"linha incompleta em {src} (gravação concorrente?)")
            rec = json.loads(line)
            if rec.get("id") in ids:
                recs[rec["id"]] = line if line.endswith("\n") else line + "\n"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", encoding="utf-8") as out:
        for k in sorted(recs):
            out.write(recs[k])
    return {"origem": str(src), "registros": len(recs), "solicitados": len(ids),
            "ausentes_na_origem": len(set(ids) - set(recs)), "bytes": dst.stat().st_size, "sha256": sha256_file(dst)}


def create_snapshot(dest: Path, files: dict[str, Path], orcid_dir: Path | None = None, orcid_ids=(),
                    jsonl_subsets: dict[str, tuple[Path, set]] | None = None, meta: dict | None = None) -> dict:
    """``files``: {caminho relativo na cópia: origem}. ``orcid_ids``: registros a copiar de ``orcid_dir``.
    ``jsonl_subsets``: {caminho relativo: (jsonl de origem, ids)}. Falha se ``dest`` já existir."""
    dest = Path(dest)
    if dest.exists():
        raise SnapshotError(f"{dest} já existe: uma cópia selada não é sobrescrita")
    tmp = dest.with_name(dest.name + ".parcial")
    if tmp.exists():
        shutil.rmtree(tmp)
    man = {"criado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"), "meta": meta or {},
           "arquivos": {}, "orcid": {}, "subconjuntos": {}}
    for rel, src in sorted(files.items()):
        src = Path(src)
        if not src.exists():
            raise SnapshotError(f"entrada obrigatória ausente: {src}")
        man["arquivos"][rel] = _copy_checked(src, tmp / rel)
    if orcid_dir is not None:
        present, absent = {}, []
        for o in sorted(set(orcid_ids)):
            f = Path(orcid_dir) / f"{o}.json"
            if f.exists():
                present[f"orcid/{o}.json"] = _copy_checked(f, tmp / "orcid" / f"{o}.json")
            else:
                absent.append(o)
        (tmp / "orcid").mkdir(parents=True, exist_ok=True)
        (tmp / "orcid_ausentes.txt").write_text("\n".join(absent) + ("\n" if absent else ""))
        man["orcid"] = {"origem": str(orcid_dir), "registros": len(present), "ausentes_na_origem": len(absent),
                        "sha256_combinado": _combined(present),
                        "sha256_lista_ausentes": sha256_file(tmp / "orcid_ausentes.txt")}
        (tmp / "orcid_manifest.json").write_text(json.dumps(present, indent=0, sort_keys=True))
    for rel, (src, ids) in sorted((jsonl_subsets or {}).items()):
        man["subconjuntos"][rel] = subset_jsonl(Path(src), tmp / rel, set(ids))
    man["sha256_combinado"] = {"arquivos": _combined(man["arquivos"]),
                               "subconjuntos": _combined(man["subconjuntos"]),
                               "orcid": man["orcid"].get("sha256_combinado")}
    (tmp / "MANIFEST.json").write_text(json.dumps(man, ensure_ascii=False, indent=1, sort_keys=True))
    os.rename(tmp, dest)
    for root, dirs, fs in os.walk(dest):                 # somente leitura
        for f in fs:
            p = Path(root) / f
            p.chmod(p.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    return man


def verify_snapshot(dest: Path, check_orcid: bool = True) -> dict:
    """Recalcula os hashes; ``SnapshotError`` em arquivo ausente, divergente ou não listado."""
    dest = Path(dest)
    mf = dest / "MANIFEST.json"
    if not mf.exists():
        raise SnapshotError(f"MANIFEST.json ausente em {dest}")
    man = json.loads(mf.read_text())
    bad = []
    for rel, e in {**man["arquivos"], **man["subconjuntos"]}.items():
        p = dest / rel
        if not p.exists():
            bad.append(f"ausente: {rel}")
        elif sha256_file(p) != e["sha256"]:
            bad.append(f"hash divergente: {rel}")
    if check_orcid and man.get("orcid"):
        om = json.loads((dest / "orcid_manifest.json").read_text())
        if _combined(om) != man["orcid"]["sha256_combinado"]:
            bad.append("orcid_manifest.json não confere com o MANIFEST")
        listed = set(om)
        for rel, e in om.items():
            p = dest / rel
            if not p.exists():
                bad.append(f"ausente: {rel}")
            elif sha256_file(p) != e["sha256"]:
                bad.append(f"hash divergente: {rel}")
        extra = {f"orcid/{f}" for f in os.listdir(dest / "orcid")} - listed
        if extra:
            bad.append(f"{len(extra)} registros ORCID não listados no manifesto")
    if bad:
        raise SnapshotError("cópia congelada inválida: " + "; ".join(bad[:10]) + (" …" if len(bad) > 10 else ""))
    return {"ok": True, "sha256_combinado": man["sha256_combinado"], "criado_em": man["criado_em"]}
