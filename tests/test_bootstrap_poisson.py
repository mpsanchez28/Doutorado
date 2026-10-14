"""Bootstrap de Poisson por pessoa: mesmo peso para a mesma identidade em todas as áreas e cortes."""
import numpy as np
import pandas as pd

from coauthor_rec.eval.bootstrap import person_weights, poisson_bootstrap


def test_same_identity_same_weight_across_calls_and_orders():
    a = person_weights(["p1", "p2", "p3"], 50, seed=7)
    b = person_weights(["p3", "p1"], 50, seed=7)                 # outra chamada, outra ordem
    assert (a.loc["p1"].to_numpy() == b.loc["p1"].to_numpy()).all()
    assert (a.loc["p3"].to_numpy() == b.loc["p3"].to_numpy()).all()
    assert not (a.loc["p1"].to_numpy() == a.loc["p2"].to_numpy()).all()
    assert not (a.loc["p1"].to_numpy() == person_weights(["p1"], 50, seed=8).loc["p1"].to_numpy()).all()


def test_weights_are_poisson_one():
    w = person_weights([f"p{i}" for i in range(400)], 200, seed=0).to_numpy()
    assert abs(w.mean() - 1) < 0.02 and abs(w.var() - 1) < 0.05


def test_person_repeated_in_two_areas_moves_together():
    """A mesma pessoa em duas áreas/cortes: suas observações recebem o mesmo peso em cada réplica."""
    df = pd.DataFrame({"pessoa": ["p1", "p1", "p2", "p3"], "area": ["eco", "mat", "eco", "mat"],
                       "corte": [2021, 2019, 2021, 2021], "delta": [1.0, 1.0, 0.0, 0.0]})
    W = person_weights(df["pessoa"], 300, seed=1).loc[df["pessoa"]].to_numpy()
    assert (W[0] == W[1]).all()
    r = poisson_bootstrap(df, "delta", n_rep=300, seed=1)
    assert r["pessoas_em_mais_de_um_grupo"] == 1
    assert r["grupos"]["eco"]["estimativa"] == 0.5 and r["agregado"]["estimativa"] == 0.5


def test_ci_covers_mean_and_aggregate_uses_fixed_weights():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"pessoa": [f"p{i}" for i in range(600)],
                       "area": np.repeat(["a", "b", "c", "d"], 150), "delta": rng.normal(0.01, 0.02, 600)})
    r = poisson_bootstrap(df, "delta", n_rep=500, seed=3)
    for g, v in r["grupos"].items():
        assert v["ic_inf"] < v["estimativa"] < v["ic_sup"]
    means = df.groupby("area")["delta"].mean()
    assert np.isclose(r["agregado"]["estimativa"], means.mean())
    assert r["agregado"]["pesos"] == {g: 0.25 for g in "abcd"}
    assert r["replicas"] + r["replicas_descartadas"] == 500
