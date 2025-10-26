import pandas as pd
import re

df = pd.read_csv("../clean_dataset.csv")


def clean_text(question):
    pattern = r"(thưa thầy)"
    pass


for question in df["questions"]:
    clean_text(question)
