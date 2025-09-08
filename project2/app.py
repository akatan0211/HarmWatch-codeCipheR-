import streamlit as st
from utils import load_data, anonymize_id, clean_text, extract_domains
from feedback_manager import log_inference, log_user_feedback, get_moderator_queue, moderator_review, prepare_incremental_batch, incremental_update_tfidf
import joblib, os

st.set_page_config(page_title="HarmWatch Demo", layout="wide")
st.title("HarmWatch — Demo Dashboard")

st.sidebar.header("Upload & Controls")
uploaded = st.sidebar.file_uploader("Upload CSV with text column", type=["csv"])
model_version = st.sidebar.text_input("Model version label", value="tfidf_v1")

if uploaded:
    df = load_data(uploaded)
    st.subheader("Data preview")
    st.dataframe(df.head(10))

    st.subheader("Select a row to predict / give feedback")
    if 'text' in df.columns:
        i = st.number_input("row index", min_value=0, max_value=len(df)-1, value=0)
        text = str(df.loc[int(i),'text'])
        st.write("Text:", text)
        # naive prediction stub: if keywords -> label else Neutral
        pred = "Neutral"
        if "verify" in text.lower() or "bit.ly" in text.lower():
            pred = "Scam/Phishing"
        elif "kill yourself" in text.lower() or "i want to die" in text.lower():
            pred = "Mental Health"
        st.write("Model predicted:", pred)
        conf = 0.75
        # log inference
        log_inference(text=text, pred_label=pred, pred_conf=conf, model_version=model_version)
        st.write("Give feedback (optional)")
        options = ["Neutral","Scam/Phishing","Hate Speech","Cyberbullying","Misinformation","Mental Health","Other"]
        sel = st.selectbox("Correct label", options)
        if st.button("Submit feedback"):
            user_id = st.session_state.get("user_id", None)
            uid = anonymize_id(user_id)
            log_user_feedback(text=text, user_id=uid, user_label=sel, model_label=pred, model_conf=conf)
            st.success("Feedback recorded for review.")
    else:
        st.info("Uploaded CSV must have a 'text' column.")

st.sidebar.markdown('---')
if st.sidebar.button("View moderator queue"):
    q = get_moderator_queue(200)
    if q.empty:
        st.sidebar.info("No items in moderator queue.")
    else:
        st.sidebar.write(q)

st.sidebar.markdown('---')
if st.sidebar.button("Run incremental update (TF-IDF)"):
    # expects models at models/
    vecp = "models/tfidf_vec.joblib"
    clfp = "models/tfidf_sgd.joblib"
    lep = "models/label_encoder.joblib"
    res = incremental_update_tfidf(vecp, clfp, lep)
    st.sidebar.write(res)
