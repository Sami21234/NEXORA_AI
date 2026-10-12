"""
Trains the intent classifier used by the chatbot to decide whether a message
is small talk (greeting, thanks, joke request, etc.) that can be answered
instantly from a template, or a general / open-ended query that should be
routed to the Gemini LLM.

This is a real, small, labeled dataset (data/intents.csv) with a held-out
test split -- not a hardcoded if/else keyword list. Accuracy is reported
honestly from that held-out split, whatever the number turns out to be.

Run from the project root:
    venv\\Scripts\\activate
    python models/train_intent_classifier.py
"""

import json     
import os       
import pandas as pd     
import joblib       # used to save and load the trained model and vectorizer to/from disk
from sklearn.feature_extraction.text import TfidfVectorizer     # used to convert text to a matrix of TF-IDF features(here TF-IDF is used to convert the text data into numerical features that can be used by machine learning algorithms)
from sklearn.linear_model import LogisticRegression     # used to train a logistic regression model for intent classification
from sklearn.metrics import accuracy_score, classification_report     # used to evaluate the performance of the trained model
from sklearn.model_selection import train_test_split     # used to split the dataset into training and testing sets
from sklearn.pipeline import Pipeline     # used to create a pipeline that combines the vectorizer and the classifier into a single object

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # get the base directory of the project
DATA_PATH = os.path.join(BASE_DIR, "data", "intents.csv")       # path to the intents dataset
MODEL_PATH = os.path.join(BASE_DIR, "models", "intent_classifier.pkl")     # path to save the trained model
METRICS_PATH = os.path.join(BASE_DIR, "models", "intent_classifier_metrics.json")       # path to save the evaluation metrics of the trained model

def main():
    # Load the dataset
    df = pd.read_csv(DATA_PATH)     # read the intents dataset into a pandas DataFrame
    print(f"Loaded {len(df)} labeled examples across {df['intent'].nunique()} intents.")
    print(df["intent"].value_counts(), "\n")

    # Stratified split so every intent is represented in both train and test,
    # even on this small dataset.
    X_train, X_test, y_train, y_test = train_test_split(
        df["text"], df["intent"], test_size=0.25, random_state=42, stratify=df["intent"]        # here, test_size=0.25 means 25% of the data will be used for testing, random_state=42 ensures reproducibility, and stratify=df["intent"] ensures that the split maintains the same proportion of each intent in both training and testing sets
    )

    # Create a pipeline that combines the vectorizer and the classifier
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(ngram_range=(1,2), min_df=1)),        # here, TfidfVectorizer is used to convert the text data into numerical features using TF-IDF, with ngram_range=(1,2) meaning that both unigrams and bigrams will be considered, and min_df=1 means that terms must appear in at least one document to be included
        ('clf', LogisticRegression(max_iter=1000, C=10.0))      # here, LogisticRegression is used as the classifier, with max_iter=1000 meaning that the maximum number of iterations for the solver to converge is 1000, and C=10.0 meaning that the inverse of regularization strength is set to 10.0 (higher values mean less regularization)
    ])

    pipeline.fit(X_train, y_train)     # fit the pipeline to the training data
    y_pred = pipeline.predict(X_test)     # predict the intents for the test data
    acc = accuracy_score(y_test, y_pred)     # calculate the accuracy of the predictions
    report = classification_report(y_test, y_pred, zero_division=0)     # generate a classification report with precision, recall, f1-score, and support for each class

    print(f"Held-out test accuracy: {acc:.3f}\n")
    print("Classification report:\n", report)

    # Save the trained model and evaluation metrics to disk
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)     # create the directory for the model if it doesn't exist
    joblib.dump(pipeline, MODEL_PATH)     # save the trained pipeline (vectorizer + classifier) to disk

    with open(METRICS_PATH, "w") as f:     # open the metrics file for writing
        json.dump(      # save the evaluation metrics as a JSON object to the metrics file
            {
                "test_accuracy": round(acc, 4),
                "n_train": len(X_train),
                "n_test": len(X_test),
                "intents": sorted(df["intent"].unique().tolist()),
                "classification_report": report,
            },
            f,
            indent=2,
        )

    print(f"Saved model to {MODEL_PATH}")
    print(f"Saved metrics to {METRICS_PATH}")

if __name__ == "__main__":
    main()