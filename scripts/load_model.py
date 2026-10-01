import os
import joblib

model_path = os.path.join("app", "ml", "models", "isolation_forest.joblib")
bundle = joblib.load(model_path)
print(f"Successfully loaded model bundle.")
print(f"Threshold: {bundle['threshold']}")
print(f"Features: {bundle['features']}")
