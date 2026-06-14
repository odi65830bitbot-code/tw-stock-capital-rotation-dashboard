import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from modules.finmind_client import FinMindClient
client = FinMindClient(raw_root=Path("data/raw"), cache_root=Path("data/cache"))
res = client.fetch_dataset("TaiwanStockShareholding", stock_id="2330", start_date="2024-01-01", end_date="2024-02-01")
print(res.dataframe.head() if not res.dataframe.empty else "Empty")
