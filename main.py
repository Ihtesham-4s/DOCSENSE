"""
main.py
-------
Query side of the RAG system.

Builds an LCEL (LangChain Expression Language) chain out of Runnables:

    retriever -> format context -> prompt -> llm -> output parser

This is the idiomatic LangChain pattern (as opposed to manually calling
.invoke() on each piece in a while-loop) and is what most real LangChain
codebases and interviewers expect to see.
"""

import os
import sys
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import Chroma

load_dotenv()

PERSIST_DIR = os.getenv("CHROMA_DIR", "chroma-db")
CHAT_MODEL = os.getenv("CHAT_MODEL", "mistral-small-2506")
EMBED_MODEL = "mistral-embed"  # must match database_create.py exactly


def load_retriever():
    if not os.path.exists(PERSIST_DIR):
        sys.exit(
            f"ERROR: No vector store found at '{PERSIST_DIR}'. "
            "Run database_create.py first to build it."
        )

    # IMPORTANT: this embedding model must be the SAME one used when the
    # vector store was created, otherwise retrieval will be broken/garbage.
    embedding_model = MistralAIEmbeddings(model=EMBED_MODEL)

    vectorstore = Chroma(
        persist_directory=PERSIST_DIR,
        embedding_function=embedding_model,
    )

    return vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 4, "fetch_k": 10, "lambda_mult": 0.5},
    )


def format_docs(docs) -> str:
    return "\n\n".join(doc.page_content for doc in docs)


def build_chain():
    if not os.getenv("MISTRAL_API_KEY"):
        sys.exit(
            "ERROR: MISTRAL_API_KEY not found. "
            "Add it to a .env file in this folder (see .env.example)."
        )

    retriever = load_retriever()

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful AI assistant.\n\n"
                "Use ONLY the provided context to answer the question.\n\n"
                'If the answer is not present in the context, say: '
                '"I could not find the answer in the document."',
            ),
            ("human", "Context:\n{context}\n\nQuestion:\n{question}"),
        ]
    )

    llm = ChatMistralAI(model=CHAT_MODEL)

    # LCEL chain: each step is a Runnable, piped together with |
    #   1. RunnablePassthrough keeps the original question flowing through
    #   2. retriever | format_docs turns the question into a context string
    #   3. prompt formats context + question into messages
    #   4. llm generates a response
    #   5. StrOutputParser extracts plain text from the response
    chain = (
        {
            "context": retriever | RunnableLambda(format_docs),
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain


def main():
    chain = build_chain()
    print("RAG system ready. Type your question, or 0 to exit.\n")

    while True:
        query = input("You: ").strip()
        if query == "0":
            print("Goodbye.")
            break
        if not query:
            continue

        try:
            answer = chain.invoke(query)
            print(f"\nAI: {answer}\n")
        except Exception as e:
            print(f"\n[Error while answering] {e}\n")


if __name__ == "__main__":
    main()
