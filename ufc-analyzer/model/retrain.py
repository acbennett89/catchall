"""Refit the win model on all history, with no third-party packages.

    python -m model.retrain

The app already folds new fights into every fighter's state automatically; this only refreshes the
win model's coefficients (same features, same regularization as the shipped model) so they reflect
the latest results.  The method model, round mix, blend weights and the evaluation report are kept.
Takes a minute or two in pure Python.
"""
import json, math, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from model import dataset, learn, scrape  # noqa: E402
from model.predict import MODEL_PATH  # noqa: E402


def main():
    t = time.time()
    with open(MODEL_PATH, encoding="utf-8") as f:
        model = json.load(f)
    feats = model["win"]["feats"]
    C = (model.get("evaluation") or {}).get("C") or 0.1
    ev, fi, fr = scrape.load_dataset()
    rows, eng, _ = dataset.build_rows(ev, fi, fr, engine_params=model.get("engine"))
    rows = [r for r in rows if r["year"] >= 2001 and r["y"] is not None]
    X = [[r["x"][k] for k in feats] for r in rows]
    scale = [math.sqrt(sum(x[j] ** 2 for x in X) / len(X)) or 1.0 for j in range(len(feats))]
    Xs = [[v / s for v, s in zip(x, scale)] for x in X]
    Xa = Xs + [[-v for v in x] for x in Xs]
    ya = [r["y"] for r in rows] + [1 - r["y"] for r in rows]
    coef, _ = learn.fit_logistic(Xa, ya, l2=1.0 / C)
    model["win"]["coef"] = [c / s for c, s in zip(coef, scale)]
    model["win"]["scale"] = scale
    model["trained_through"] = max(r["date"] for r in rows)
    model["retrained"] = time.strftime("%Y-%m-%d")
    tmp = MODEL_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(model, f, indent=1)
    os.replace(tmp, MODEL_PATH)
    print(f"refit on {len(rows)} fights through {model['trained_through']} in {time.time() - t:.0f}s")


if __name__ == "__main__":
    main()
