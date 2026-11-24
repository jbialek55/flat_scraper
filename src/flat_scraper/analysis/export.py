"""
export.py
---------
Exports listings from SQLite to pandas and applies one-hot encoding
to multi-label columns (e.g. extras_types, equipment_types).
"""

import json
import sqlite3
import pandas as pd
from sklearn.preprocessing import MultiLabelBinarizer

from flat_scraper.config import DB_PATH

LIST_COLUMNS = ["equipment_types", "extras_types", "security_types", "media_types"]


def load_listings_df(only_active: bool = True) -> pd.DataFrame:
    """Load listings from the SQLite database into a pandas DataFrame."""
    conn = sqlite3.connect(DB_PATH)
    try:
        query = "SELECT * FROM listings"
        if only_active:
            query += " WHERE is_active = 1"
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    for col in LIST_COLUMNS + ["location_path"]:
        df[col] = df[col].apply(lambda x: json.loads(x) if isinstance(x, str) and x else [])

    return df


def one_hot_encode_features(df: pd.DataFrame) -> pd.DataFrame:
    """Expand multi-label list columns into binary 0/1 columns."""
    df = df.copy()

    for col in LIST_COLUMNS:
        mlb = MultiLabelBinarizer()
        encoded = mlb.fit_transform(df[col])
        encoded_df = pd.DataFrame(
            encoded,
            columns=[f"{col}_{c}" for c in mlb.classes_],
            index=df.index,
        )
        df = pd.concat([df, encoded_df], axis=1)

    return df.drop(columns=LIST_COLUMNS)


if __name__ == "__main__":
    df = load_listings_df(only_active=True)
    print(f"Loaded {len(df)} active listings from database.")

    df_encoded = one_hot_encode_features(df)
    print(f"After one-hot encoding: {df_encoded.shape[1]} columns.")

    output_path = "data/listings_encoded.csv"
    df_encoded.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"Saved to {output_path}")
