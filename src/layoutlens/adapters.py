"""Optional adapters. No automatic downloads or cloud writes during extraction."""

import json
from pathlib import Path

from .core import normalized_box


def layoutlm_features(page, checkpoint):
    """Run a locally supplied Hugging Face LayoutLM checkpoint; return word vectors.

    These are contextual embeddings, NOT trained table or legal labels.
    """
    import torch
    from transformers import AutoTokenizer, LayoutLMModel

    tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
    model = LayoutLMModel.from_pretrained(checkpoint, local_files_only=True).eval()
    words = page["words"]
    if not words:
        return {"word_vectors": [], "checkpoint": str(checkpoint)}
    tokens = tokenizer(
        [w["text"] for w in words],
        is_split_into_words=True,
        return_tensors="pt",
        truncation=False,
    )
    if tokens["input_ids"].shape[1] > model.config.max_position_embeddings:
        raise ValueError("Page exceeds model token capacity; chunk it explicitly")
    ids = tokens.word_ids()
    boxes = [
        normalized_box(words[i]["box"], page["width"], page["height"])
        if i is not None
        else [0, 0, 0, 0]
        for i in ids
    ]
    with torch.no_grad():
        hidden = model(**tokens, bbox=torch.tensor([boxes])).last_hidden_state[0]
    vectors = [
        hidden[[j for j, wi in enumerate(ids) if wi == i]].mean(0).tolist()
        for i in range(len(words))
    ]
    return {
        "word_vectors": vectors,
        "checkpoint": str(checkpoint),
        "purpose": "features-only; no fine-tuned task head",
    }


def upload_json(path, bucket, key):
    """Explicit AWS S3 upload using the standard credential chain and SSE-S3."""
    import boto3

    payload = Path(path).read_bytes()
    json.loads(payload)
    if not bucket or not key or key.startswith("/"):
        raise ValueError("Provide a bucket and relative object key")
    boto3.client("s3").put_object(
        Bucket=bucket,
        Key=key,
        Body=payload,
        ContentType="application/json",
        ServerSideEncryption="AES256",
    )
    return f"s3://{bucket}/{key}"
