import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pandas as pd
import json
import joblib
from src.config.settings import get_settings
from src.ml.train import evaluate_leakage_safe_spatial_cv, get_primary_feature_names
from src.ml.evaluate import analyze_threshold_tradeoffs
from src.ml.predict import predict_susceptibility_single

settings = get_settings()
parquet_path = settings.DATA_PROCESSED_DIR / "spatial_susceptibility_dataset.parquet"
df_full = pd.read_parquet(parquet_path)

rf_agg, rf_folds, rf_oof_y, rf_oof_p = evaluate_leakage_safe_spatial_cv(df_full, model_type="random_forest", n_splits=5, random_seed=42)
gb_agg, gb_folds, gb_oof_y, gb_oof_p = evaluate_leakage_safe_spatial_cv(df_full, model_type="gradient_boosting", n_splits=5, random_seed=42)

th_df = analyze_threshold_tradeoffs(rf_oof_y, rf_oof_p, thresholds=[0.30, 0.40, 0.50, 0.60, 0.70])

feature_cols = get_primary_feature_names(df_full)
sample_dict = {col: float(df_full[col].iloc[0]) for col in feature_cols}

model_path = BASE_DIR / "models" / "trained" / "static_susceptibility_model.joblib"
model_obj = joblib.load(model_path)
pred_res = predict_susceptibility_single(model_obj, feature_cols, sample_dict)

out_data = {
    "rf_folds": rf_folds,
    "gb_folds": gb_folds,
    "threshold_analysis": th_df.to_dict(orient="records"),
    "sample_prediction": pred_res,
}

with open(BASE_DIR / "scratch" / "fold_details.json", "w") as f:
    json.dump(out_data, f, indent=2)

print("SUCCESSFULLY WRITTEN FOLD DETAILS JSON!", flush=True)
