from pathlib import Path
import pyarrow.parquet as pq


ROOT = Path(
    r"data\second1m_alt_entry_research_v1"
)

files = sorted(
    ROOT.rglob(
        "*features_v1.parquet"
    )
)

print(
    f"FEATURE FILES: {len(files)}"
)

for path in files:

    print()
    print(
        f"FILE: {path}"
    )

    try:

        pf = pq.ParquetFile(
            path
        )

        print(
            f"ROWS: {pf.metadata.num_rows}"
        )

        print(
            "COLUMNS:"
        )

        for col in pf.schema_arrow.names:

            print(
                f"  {col}"
            )

    except Exception as exc:

        print(
            f"ERROR: {type(exc).__name__}: {exc}"
        )