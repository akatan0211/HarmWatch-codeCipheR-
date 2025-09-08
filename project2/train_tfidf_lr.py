import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import argparse

def load_data(path):
    df = pd.read_csv(path)
    df = df.dropna(subset=['text', 'label'])
    return df

def train(input_csv, out_model="models/tfidf_lr_pipeline.joblib"):
    df = load_data(input_csv)
    X = df['text'].astype(str).values
    y = df['label'].astype(str).values
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1,2), max_features=50000)),
        ("clf", LogisticRegression(max_iter=2000, class_weight="balanced", solver="saga"))
    ])
    param_grid = {
        "tfidf__max_features": [20000, 50000],
        "tfidf__ngram_range": [(1,1),(1,2)],
        "clf__C": [0.5, 1.0, 2.0]
    }
    gs = GridSearchCV(pipeline, param_grid, cv=3, n_jobs=-1, verbose=1)
    gs.fit(X_train, y_train)
    print("Best params:", gs.best_params_)
    best = gs.best_estimator_
    preds = best.predict(X_val)
    print(classification_report(y_val, preds))
    print("Confusion matrix:\n", confusion_matrix(y_val, preds))
    joblib.dump(best, out_model)
    print("Saved model to", out_model)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Labeled CSV with text,label")
    parser.add_argument("--out", default="models/tfidf_lr_pipeline.joblib")
    args = parser.parse_args()
    train(args.input, args.out)
