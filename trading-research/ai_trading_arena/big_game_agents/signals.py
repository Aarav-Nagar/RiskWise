from __future__ import annotations

import numpy as np
import pandas as pd


def ranked_momentum_score(history: pd.DataFrame) -> pd.Series:
    clean = history.dropna(axis=1, thresh=max(20, int(len(history) * 0.5))).ffill()
    returns_3m = clean.pct_change(63).iloc[-1]
    returns_1m = clean.pct_change(21).iloc[-1]
    vol = clean.pct_change().rolling(63).std().iloc[-1]
    score = returns_3m.rank(pct=True) + 0.5 * returns_1m.rank(pct=True) - 0.4 * vol.rank(pct=True)
    return score.replace([np.inf, -np.inf], np.nan).dropna()
