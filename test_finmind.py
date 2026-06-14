import sys
from pathlib import Path
from modules.finmind_client import FinMindClient
client = FinMindClient(raw_root=Path("data/raw"), cache_root=Path("data/cache"))
res = client.fetch_dataset("TaiwanStockHoldingSharesPer", stock_id="2330", start_date="2024-01-01", end_date="2024-02-01")
print('HoldingSharesPer:', res.dataframe.columns.tolist() if not res.dataframe.empty else "Empty")
print(res.dataframe.head() if not res.dataframe.empty else "")
