from app.services.web_loader import load_webpage
from app.core.web_processor import ingest_web


url = "https://en.wikipedia.org/wiki/Retrieval-augmented_generation"


try:

    document = ingest_web(url,"123")

    print("\n" + "=" * 80)
    print("WEB LOADER TEST RESULT")
    print("=" * 80)

    print("\nTITLE:")
    print(document['title'])

    print("\nSOURCE:")
    print(document["source"])

    print("\nTYPE:")
    print(document["type"])

    print("\n Vectorstore:")
    print(document["vectorstore_path"])

    print("\nDoc id :")
    print(document["doc_id"])
    print("\nContent Hash:")
    print(document["content_hash"])

    print("\nCONTENT LENGTH:")
    print(len(document["content"]))

    print("\nFIRST al CHARACTERS:")
    print(document["content"])

except Exception as e:

    print("\nERROR:")
    print(str(e))