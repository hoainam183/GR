from unstructured.partition.pdf import partition_pdf

elements = partition_pdf(
    filename="QCDT-2023.pdf",
    strategy="hi_res",
    infer_table_structure=True,
    include_metadata=True,
)

# Lưu lại text đã tách
text = "\n".join([el.text for el in elements if el.text])
with open("qcdt_text.txt", "w", encoding="utf-8") as f:
    f.write(text)
