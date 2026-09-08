from __future__ import annotations
import pandas as pd
from tr_platform.pmpd_v5.certification import _normalize_vector_columns

def main():
    x = pd.DataFrame({
        "new_close_vector": [1, 10, 11, 100, 111],
        "traded_vector": [1, 10, 11, 100, 111],
    })
    y = _normalize_vector_columns(x)
    assert y["new_close_vector"].tolist() == ["001","010","011","100","111"]
    assert y["traded_vector"].tolist() == ["001","010","011","100","111"]
    assert y["new_close_vector_code"].tolist() == ["V001","V010","V011","V100","V111"]
    assert y["traded_vector_code"].tolist() == ["V001","V010","V011","V100","V111"]
    assert y["pm_retained"].tolist() == [False, False, False, True, True]
    assert y["ah_retained"].tolist() == [False, True, True, False, True]
    assert y["pd_retained"].tolist() == [True, False, True, False, True]
    print("=== PMPD V5 ALPHA 0.2 VECTOR SERIALIZATION TEST PASS ===")

if __name__ == "__main__":
    main()
