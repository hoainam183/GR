import pandas as pd
df = pd.read_csv("../clean_dataset.csv")

print(df["questions"][0])