"""
MongoDB Atlas connectivity + vector index check.

    python -m src.rag.check_atlas            # ping, create index if missing, show counts
    python -m src.rag.check_atlas --query "data analyst interview tips"

Run this once after putting MONGODB_URI in .env, then:
    python -m src.rag.ingest --sources all --backend mongo
"""
import argparse

from src.rag import config


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--query", default=None)
    args = p.parse_args()

    from src.rag.vector_store import get_vector_store

    first = True
    for source, (coll, index) in config.COLLECTIONS.items():
        store = get_vector_store(source, backend="mongo")
        if first:
            store.client.admin.command("ping")
            print(f"[ok] connected - db={config.MONGODB_DB}")
            first = False
        store.ensure_index(wait=True)
        for ix in store.coll.list_search_indexes():
            print(f"[index] {coll}.{ix['name']} status={ix.get('status')} queryable={ix.get('queryable')}")
        sample = store.coll.find_one({}, {"embedding_model": 1})
        print(f"[counts] {coll}: {store.count()}  model={sample and sample.get('embedding_model')}")
    if args.query:
        from src.rag.retriever import retrieve_careers

        for h in retrieve_careers(args.query):
            print(f"  {h['score']:.3f} {h['career_id']} {h['career_name']} [{h['domain']}]")


if __name__ == "__main__":
    main()
