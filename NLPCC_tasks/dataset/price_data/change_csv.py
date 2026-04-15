from pathlib import Path

import pandas as pd

from price_normalizer import reorder_price_columns, standardize_price_dataframe


DATA_DIR = Path(__file__).resolve().parent / "export_data"


def rewrite_price_csvs() -> None:
    csv_files = sorted(DATA_DIR.glob("*.csv"))
    print(f"找到 {len(csv_files)} 个 CSV 文件")

    for csv_file in csv_files:
        try:
            df = standardize_price_dataframe(pd.read_csv(csv_file, encoding="utf-8-sig"))
            df = df[reorder_price_columns(df.columns)]
            df.to_csv(csv_file, index=False, encoding="utf-8-sig")
            print(f"已标准化: {csv_file.name} ({df.iloc[0]['price_mode']})")
        except Exception as exc:
            print(f"处理失败: {csv_file.name} - 错误: {exc}")


if __name__ == "__main__":
    rewrite_price_csvs()
