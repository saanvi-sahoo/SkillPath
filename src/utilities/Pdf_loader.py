import fitz

def extract_text_from_pdf(file_path):
    doc = fitz.open(file_path)
    text = ""

    for page in doc:
        text += page.get_text()

    doc.close()
    return text


def extract_pagewise(file_path):
    doc = fitz.open(file_path)
    data = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()

        data.append({
            "page": page_num + 1,
            "content": text
        })

    doc.close()
    return data