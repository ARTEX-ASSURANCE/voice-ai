# backend/build_knowledge_base.py
import os
import pickle
import pandas as pd
from io import StringIO # Nécessaire pour la nouvelle version de pandas
from unstructured.partition.pdf import partition_pdf
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

def process_document_elements_final(docs_path):
    """
    Analyse les documents PDF en extrayant les tableaux de manière robuste.
    S'il ne peut pas parser la structure d'un tableau, il utilise son contenu textuel comme repli.
    """
    all_texts = []
    print(f"Début de l'analyse structurelle des documents (mode final) dans : {docs_path}")

    for root, _, files in os.walk(docs_path):
        for filename in files:
            if not filename.lower().endswith('.pdf'):
                continue

            file_path = os.path.join(root, filename)
            print(f"  -> Traitement du PDF : {file_path}")
            
            try:
                elements = partition_pdf(filename=file_path, strategy="hi_res", infer_table_structure=True)

                for element in elements:
                    is_table = "unstructured.documents.elements.Table" in str(type(element))
                    
                    if is_table:
                        table_html = getattr(element.metadata, 'text_as_html', None)
                        table_parsed = False
                        
                        if table_html:
                            try:
                                # Correction pour le FutureWarning de pandas
                                df_list = pd.read_html(StringIO(table_html), header=0)
                                if df_list:
                                    df = df_list[0]
                                    if not df.empty:
                                        print("    -> Tableau détecté, conversion via HTML réussie.")
                                        for _, row in df.iterrows():
                                            row_text = ", ".join([f"{col}: {val}" for col, val in row.dropna().items()])
                                            all_texts.append(f"Information d'un tableau : {row_text}.")
                                        table_parsed = True
                            except Exception:
                                # L'analyse HTML a échoué, on passera au texte brut
                                pass
                        
                        # Stratégie de repli : si le tableau n'a pas pu être parsé, on prend son texte brut.
                        if not table_parsed:
                            print("    -> Avertissement : Impossible de parser la structure du tableau. Utilisation du texte brut de l'élément.")
                            if element.text:
                                all_texts.append(f"Texte brut d'un tableau : {element.text}")
                    else:
                        all_texts.append(element.text)
            
            except Exception as e:
                print(f"    /!\\ Erreur majeure lors du traitement du fichier {filename}: {e}")

    return "\n\n".join(all_texts)

def main():
    print("Construction de la base de connaissances (Mode Final et Robuste)...")
    docs_path = os.path.join(os.path.dirname(__file__), 'knowledge_documents')
    
    if not os.path.exists(docs_path):
        print(f"ERREUR : Le dossier '{docs_path}' n'existe pas.")
        return

    structured_text = process_document_elements_final(docs_path)
    if not structured_text:
        print("Aucun contenu n'a pu être extrait. Arrêt.")
        return
    
    # Le reste du script est inchangé
    print(f"\nExtraction terminée. Total de {len(structured_text)} caractères structurés.")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200, length_function=len)
    chunks = text_splitter.split_text(text=structured_text)
    print(f"Texte global découpé en {len(chunks)} morceaux.")
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vector_store_path = os.path.join(os.path.dirname(__file__), 'vector_store.pkl')
    print("Création de la base de données vectorielle...")
    vector_store = FAISS.from_texts(chunks, embedding=embeddings)
    with open(vector_store_path, "wb") as f:
        pickle.dump(vector_store, f)
    print(f"\nSuccès ! La base de connaissances avancée a été sauvegardée dans '{vector_store_path}'.")

if __name__ == "__main__":
    main()