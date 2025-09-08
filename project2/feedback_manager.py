import pandas as pd
import joblib
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np

LOG_DIR = Path("logs")
BUFF_DIR = Path("buffers")
MODELS_DIR = Path("models")
LOG_DIR.mkdir(exist_ok=True)
BUFF_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)

INFERENCE_LOG = LOG_DIR / "inference_logs.parquet"
USER_FEEDBACK = LOG_DIR / "user_feedback.parquet"
MODERATOR_QUEUE = BUFF_DIR / "moderator_queue.parquet"
REVIEWED_LABELS = BUFF_DIR / "reviewed_labels.parquet"
PSEUDO_LABELS = BUFF_DIR / "pseudo_labels.parquet"
REPLAY_SAMPLE = MODELS_DIR / "replay_sample.parquet"

AUTO_ACCEPT_CONF = 0.95
AGREE_COUNT = 3
USER_WEIGHT = 0.3
MODERATOR_WEIGHT = 1.0

def _append_parquet(path: Path, df: pd.DataFrame):
    if df.empty:
        return
    if path.exists():
        existing = pd.read_parquet(path)
        df = pd.concat([existing, df], ignore_index=True)
    df.to_parquet(path, index=False)

def log_inference(text: str, pred_label: str, pred_conf: float, model_version: str, meta: Optional[Dict]=None):
    row = {
        "text": text,
        "pred_label": pred_label,
        "pred_conf": float(pred_conf),
        "model_version": model_version,
        "timestamp": datetime.utcnow().isoformat()
    }
    if meta:
        row.update(meta)
    _append_parquet(INFERENCE_LOG, pd.DataFrame([row]))
    return row

def log_user_feedback(text: str, user_id: Optional[str], user_label: str, model_label: str, model_conf: float, meta: Optional[Dict]=None):
    row = {
        "text": text,
        "user_id_hash": user_id,
        "user_label": user_label,
        "model_label": model_label,
        "model_conf": float(model_conf),
        "timestamp": datetime.utcnow().isoformat()
    }
    if meta:
        row.update(meta)
    _append_parquet(USER_FEEDBACK, pd.DataFrame([row]))
    _try_aggregate_for_text(text)
    return row

def _try_aggregate_for_text(text: str):
    if not USER_FEEDBACK.exists():
        return
    fb = pd.read_parquet(USER_FEEDBACK)
    subs = fb[fb["text"] == text]
    if subs.empty:
        return
    votes = subs.groupby("user_label")["user_id_hash"].nunique().sort_values(ascending=False)
    top_label = votes.index[0]
    top_count = int(votes.iloc[0])
    model_confs = subs["model_conf"].dropna()
    model_conf_med = float(model_confs.median()) if len(model_confs) else 0.0
    if model_conf_med >= AUTO_ACCEPT_CONF and top_count >= max(1, AGREE_COUNT//2):
        pseudo = pd.DataFrame([{
            "text": text,
            "label": top_label,
            "source": "pseudo_auto",
            "confidence": model_conf_med,
            "collected_at": datetime.utcnow().isoformat(),
            "votes": int(votes.sum())
        }])
        _append_parquet(PSEUDO_LABELS, pseudo)
        return
    if top_count >= AGREE_COUNT:
        qrow = {
            "text": text,
            "suggested_label": top_label,
            "votes": int(votes.sum()),
            "label_counts": votes.to_dict(),
            "queued_at": datetime.utcnow().isoformat()
        }
        _append_parquet(MODERATOR_QUEUE, pd.DataFrame([qrow]))
        return

def get_moderator_queue(limit: int = 200) -> pd.DataFrame:
    if not MODERATOR_QUEUE.exists():
        return pd.DataFrame()
    df = pd.read_parquet(MODERATOR_QUEUE)
    return df.sort_values("queued_at", ascending=False).head(limit)

def moderator_review(text: str, approved: bool, final_label: Optional[str], moderator_id: Optional[str], notes: Optional[str]=None):
    if not final_label:
        final_label = "REJECTED" if not approved else None
    row = {
        "text": text,
        "approved": bool(approved),
        "final_label": final_label,
        "moderator_id": moderator_id,
        "notes": notes or "",
        "reviewed_at": datetime.utcnow().isoformat()
    }
    if approved:
        _append_parquet(REVIEWED_LABELS, pd.DataFrame([{
            "text": text,
            "label": final_label,
            "source": "moderator",
            "weight": MODERATOR_WEIGHT,
            "reviewed_at": row["reviewed_at"]
        }]))
    if MODERATOR_QUEUE.exists():
        q = pd.read_parquet(MODERATOR_QUEUE)
        q = q[q["text"] != text]
        q.to_parquet(MODERATOR_QUEUE, index=False)
    _append_parquet(USER_FEEDBACK, pd.DataFrame([{
        "text": text,
        "user_id_hash": moderator_id,
        "user_label": final_label,
        "model_label": None,
        "model_conf": None,
        "timestamp": row["reviewed_at"],
        "moderator_action": True,
        "notes": notes or ""
    }]))
    return row

def prepare_incremental_batch(max_new: int = 2000, replay_fraction: float = 0.3):
    pieces = []
    if REVIEWED_LABELS.exists():
        rev = pd.read_parquet(REVIEWED_LABELS)
        pieces.append(rev)
    if PSEUDO_LABELS.exists():
        pseudo = pd.read_parquet(PSEUDO_LABELS)
        pseudo = pseudo.rename(columns={"label":"label"})
        pseudo["weight"] = USER_WEIGHT
        pseudo["source"] = pseudo.get("source","pseudo")
        pieces.append(pseudo[["text","label","weight","source"]])
    if not pieces:
        return pd.DataFrame(columns=["text","label","weight","source"])
    new_df = pd.concat(pieces, ignore_index=True)
    new_df["text"] = new_df["text"].astype(str)
    new_df["label"] = new_df["label"].astype(str)
    if REPLAY_SAMPLE.exists() and replay_fraction > 0:
        replay = pd.read_parquet(REPLAY_SAMPLE)
        n_replay = int(len(new_df) * replay_fraction)
        n_replay = min(n_replay, len(replay))
        if n_replay > 0:
            replay_samp = replay.sample(n_replay, random_state=42)
            replay_samp["weight"] = 1.0
            replay_samp["source"] = "replay"
            new_df = pd.concat([new_df, replay_samp[["text","label","weight","source"]]], ignore_index=True)
    new_df = new_df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    return new_df

def incremental_update_tfidf(vec_path: str, clf_path: str, label_encoder_path: str):
    from pathlib import Path
    if not Path(vec_path).exists() or not Path(clf_path).exists() or not Path(label_encoder_path).exists():
        raise FileNotFoundError("Required model artifacts not found.")
    batch = prepare_incremental_batch()
    if batch.empty:
        return {"status":"no_new_data"}
    vec = joblib.load(vec_path)
    clf = joblib.load(clf_path)
    le = joblib.load(label_encoder_path)
    new_labels = set(batch["label"].unique()) - set(le.classes_)
    if new_labels:
        return {"status":"new_labels_present", "new_labels": list(new_labels)}
    X = vec.transform(batch["text"].tolist())
    y = le.transform(batch["label"].tolist())
    sample_weights = batch.get("weight", pd.Series(1.0, index=batch.index)).astype(float).tolist()
    try:
        clf.partial_fit(X, y, classes=np.arange(len(le.classes_)), sample_weight=sample_weights)
    except Exception as e:
        return {"status":"partial_fit_failed", "error": str(e)}
    joblib.dump(vec, vec_path)
    joblib.dump(clf, clf_path)
    if PSEUDO_LABELS.exists():
        PSEUDO_LABELS.unlink()
    if REVIEWED_LABELS.exists():
        REVIEWED_LABELS.unlink()
    return {"status":"updated", "n": len(batch)}
