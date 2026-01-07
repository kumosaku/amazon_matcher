import pandas as pd
from utils import get_default_index
import io

# Mock DataFrame for Amazon
df_amazon = pd.DataFrame({
    '注文日': ['2023/01/01'],
    '支払金額': [1000],
    '商品名': ['Test Item']
})

# Mock DataFrame for Card with shifted columns
# Simulating a case where 'Col_10' is text and 'Col_11' is the actual price
df_card = pd.DataFrame({
    '利用日': ['2023/01/01'],
    'Col_10': ['Not Price'],
    'Col_11': ['1,000'],
    '利用店名': ['AMAZON']
})

print("Testing get_default_index...")
# Test 1: Finding by name
idx_date = get_default_index(df_amazon.columns, ['注文日'])
print(f"Date index (expected 0): {idx_date}")

# Test 2: Finding by numeric heuristic
# Should ignore 'Col_10' because it's not numeric, and pick 'Col_11' if we only looked for 'Col_11' or if we iterate.
# But my implementation iterates through columns.
# Let's see how I implemented it:
# It iterates `for i, col in enumerate(columns): if col.startswith("Col_"): ...`
# So it will check Col_10 (fail) then Col_11 (pass).
idx_price = get_default_index(df_card.columns, ['NonExistent'], check_numeric=True, df=df_card)
print(f"Price index (expected 2 for Col_11): {idx_price}")

print("Verification complete.")
