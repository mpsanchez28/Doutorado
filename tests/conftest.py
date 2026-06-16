"""Fixtures de teste: corpus sintético com estrutura temporal de coautoria."""
import random

import pandas as pd
import pytest


@pytest.fixture
def synthetic_corpus():
    """Gera um merged_df sintético (work_id, author_id, publication_date, title,
    abstract, language) com grupos de coautores e novas colaborações ao longo do tempo,
    de modo que o split temporal produza ground truth não-vazio e candidatos a 2 saltos.
    """
    rng = random.Random(7)
    rows = []
    n_authors = 60
    authors = [f"A{i}" for i in range(n_authors)]
    work_counter = 0

    def add_work(coauthors, year):
        nonlocal work_counter
        wid = f"W{work_counter}"
        work_counter += 1
        for a in coauthors:
            rows.append({
                "work_id": wid,
                "author_id": a,
                "publication_date": f"{year}-06-01",
                "title": f"Estudo {wid}",
                "abstract": f"Resumo do trabalho {wid} sobre redes academicas.",
                "language": "en",
            })

    # Passado (T0): grupos estáveis de 3-4 autores.
    for year in range(2005, 2018):
        for _ in range(20):
            base = rng.randrange(0, n_authors - 4)
            group = authors[base:base + rng.randint(3, 4)]
            add_work(group, year)

    # Futuro (T1): pontes entre grupos vizinhos -> novas coautorias (2 saltos).
    for year in range(2018, 2024):
        for _ in range(15):
            base = rng.randrange(0, n_authors - 6)
            group = [authors[base], authors[base + 2], authors[base + 5]]
            add_work(group, year)

    return pd.DataFrame(rows)
