"""MODELO DE APRENDIZAJE (parte de RAZONAMIENTO, componente IBM 4): P(retraso>=15 min) y duracion esperada."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from .perception import FEATURES
from .simulator import AIRLINES, AIRPORTS

CATS = ["origin", "dest", "airline"]
VOCAB = {"origin": AIRPORTS, "dest": AIRPORTS, "airline": AIRLINES}


def encode(df: pd.DataFrame) -> pd.DataFrame:
    X = df[FEATURES].copy()
    for c in CATS:
        X[c] = X[c].map({v: i for i, v in enumerate(VOCAB[c])}).astype(float)
    return X.astype(float)


class DelayModel:
    def __init__(self, seed=0):
        cat_idx = [FEATURES.index(c) for c in CATS]
        self.clf = HistGradientBoostingClassifier(max_iter=150, learning_rate=0.08, max_leaf_nodes=24,
                                                  categorical_features=cat_idx, random_state=seed)
        self.reg = HistGradientBoostingRegressor(max_iter=100, learning_rate=0.08, max_leaf_nodes=16,
                                                 categorical_features=cat_idx, random_state=seed)
        self.fitted = False

    def fit(self, feats: pd.DataFrame, delayed: np.ndarray, dep_delay: np.ndarray, weight: np.ndarray | None = None):
        X = encode(feats)
        w = np.ones(len(X)) if weight is None else weight
        self.clf.fit(X, delayed.astype(int), sample_weight=w)
        m = delayed.astype(bool)
        self.reg.fit(X[m], dep_delay[m], sample_weight=w[m])
        self.fitted = True
        return self

    def predict(self, feats: pd.DataFrame):
        X = encode(feats)
        p = self.clf.predict_proba(X)[:, 1]
        d = np.clip(self.reg.predict(X), 15, 240)
        return p, d
