import streamlit as st
import tempfile
from PIL import Image
import hashlib

from deta import Deta
import torch
from dataclasses import dataclass

from model import LayoutLMForQuestionAnswering


import document
from ext.reg import AutoModelForDocumentQuestionAnswering
from ext.document_qa import DocumentQuestionAnsweringPipeline

from transformers import AutoConfig, AutoTokenizer
from transformers import pipeline as transformers_pipeline
from transformers.pipelines import PIPELINE_REGISTRY

st.set_page_config(page_title='Mukham')

nlp=None
blocksize=65536

deta = Deta("d039yor3_NEChbz6ZyakvfAAtVzbKsKbEpLNcgi1a")
db = deta.Base("invoice_data")
drive = deta.Drive("files")

def hash_file(path):
    afile = open(path, 'rb')
    hasher = hashlib.md5()
    buf = afile.read(blocksize)
    while len(buf) > 0:
        hasher.update(buf)
        buf = afile.read(blocksize)
    afile.close()
    return(hasher.hexdigest())

def load_model():

    PIPELINE_REGISTRY.register_pipeline(
    "document-question-answering",
    pipeline_class=DocumentQuestionAnsweringPipeline,
    pt_model=AutoModelForDocumentQuestionAnswering, 
    )

    config = AutoConfig.from_pretrained("impira/layoutlm-document-qa", 
    revision="ff904df")

    tokenizer = AutoTokenizer.from_pretrained(
            "impira/layoutlm-document-qa",
            revision="ff904df",
            config=config)

    model = LayoutLMForQuestionAnswering.from_pretrained('impira/layoutlm-document-qa', config=config, revision='ff904df')

    device = 0 if torch.cuda.is_available() else -1

    return transformers_pipeline(
        "document-question-answering",
        revision="ff904df",
        model=model,
        tokenizer=tokenizer,
        device=device)

st.image("header.png", use_column_width=True)
# st.header("`Problem Statement 4 by Mukham`")

file = st.file_uploader(label="Upload your invoice.",
                        type=['jpg', 'jpeg', 'png'])
if not file:
    st.warning("Please upload the file.")
    st.stop()
else:
    submit = st.button("Submit")

if submit:
    f = file.read()
    tfile = tempfile.NamedTemporaryFile(delete=False)
    tfile.write(f)

    hash = hash_file(tfile.name)

    if db.get(hash_file(tfile.name)) is not None:
        st.error("File Already Exists in the Database.")
    else:
        nlp = nlp if nlp!=None else load_model()
    
        image = Image.open(tfile.name)
        # st.image(f, use_column_width=True)

        words, boxes = document.apply_ocr(image=image)
        doc = document._generate_document_output(image, [words], [boxes])

        inv_num = nlp(question="What is the invoice number?", **doc)[0]

        if db.fetch({"invoice_number":str(inv_num['answer'])}).count != 0:
            st.error("A file with same Invoice Number already exists in the Database.")
        else:
            inv_date = nlp(question="What is the invoice date?", **doc)[0]
            seller_name = nlp(question="What is the seller name?", **doc)[0]
            db.put({"key":hash, 
                    "invoice_number": str(inv_num['answer']),
                    "invoice_date":str(inv_date['answer']), 
                    "seller_name":str(seller_name['answer'])})
            st.success("File info added to the database.")
            drive.put(f"{hash}.jpg", f)





        
