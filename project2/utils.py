import pandas as pd
import re
import hashlib
from urllib.parse import urlparse
from typing import List, Optional
import nltk
try:
    from nltk.corpus import stopwords
    _ = stopwords.words("english")
except LookupError:
    nltk.download("stopwords")
    from nltk.corpus import stopwords

STOP_WORDS = set(stopwords.words("english"))
SALT = "change-me-demo-salt"

URL_REGEX = re.compile(r"(https?://\S+)")

def load_data(f):
    return pd.read_csv(f)

def clean_text(text: str) -> str:
    if text is None:
        return ""
    text = re.sub(r"http\S+", " ", str(text))
    text = re.sub(r"@\w+", " ", text)
    text = re.sub(r"#", " ", text)
    text = re.sub(r"[^A-Za-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = " ".join(w for w in text.split() if w not in STOP_WORDS)
    return text

def anonymize_id(author_id: Optional[str]) -> Optional[str]:
    if not author_id:
        return None
    h = hashlib.sha256((SALT + str(author_id)).encode("utf-8")).hexdigest()
    return h[:16]

def extract_domains(text: str) -> List[str]:
    domains = []
    for match in URL_REGEX.findall(text or ""):
        try:
            d = urlparse(match).netloc.lower()
            if d:
                domains.append(d)
        except Exception:
            pass
    return sorted(set(domains))
