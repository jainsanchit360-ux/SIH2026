# ResQtech (SIH26001) — Judge Q&A & Technical Defense Guide

### 1. What is actually "AI" in ResQtech?
> **Answer**: ResQtech uses a `RandomForestClassifier` trained on SRTM DEM elevation, slope, and GSI historical landslide spatial density features. It models spatial terrain susceptibility to produce baseline susceptibility scores $S \in [0, 100]$.

### 2. How did you prevent spatial data leakage during ML model evaluation?
> **Answer**: We implemented spatial block cross-validation (`GroupKFold` on 25km spatial blocks) rather than standard random train-test splitting. Random splitting suffers from spatial autocorrelation leakage, giving artificially inflated ~92% accuracy scores. Our spatial cross-validation yields a realistic, scientifically sound spatial ROC-AUC of `0.736`.

### 3. Why isn't rainfall fed directly into the Random Forest model?
> **Answer**: GSI historical landslide records lack reliable exact occurrence timestamps required for supervised temporal rainfall training. Feeding static rainfall averages into an ML model causes spatial overfitting. Instead, we use a two-layer architecture: Layer 1 ML static susceptibility + Layer 2 physical hydrometeorological trigger engine (NASA IMERG/SMAP), fused dynamically.

### 4. Is this system operating live in real-time?
> **Answer**: ResQtech operates on offline historical cached prototype datasets (`is_live = false`, latest valid observation date `2025-09-23`). The architecture is fully near-real-time ready and can consume live satellite feeds once operational API credentials are integrated.

### 5. How are negative control samples generated?
> **Answer**: Negative samples are pseudo-absence controls generated from non-landslide spatial locations at least 2km away from known GSI landslide points, constrained to valid NER elevation boundaries. They are labeled as background controls, not "confirmed safe areas".

### 6. Can ResQtech predict the exact minute a landslide will occur?
> **Answer**: No. Landslide slope failure depends on micro-geotechnical factors (pore pressure, shear strength) unavailable from satellite observations. ResQtech provides operational regional risk advisories (`PROTOTYPE OPERATIONAL WARNING — REQUIRES REGIONAL CALIBRATION`) to guide authority monitoring and response dispatch.

### 7. How does the system operate if internet connection fails?
> **Answer**: The dashboard is designed for offline resilience. If basemap tiles fail to fetch, all site lists, location panels, risk fusion metrics, charts, Command Center feeds, and SQLite workflow logging remain fully functional.

### 8. What happens during demo scenario simulation?
> **Answer**: The What-If simulator allows operators to inject custom rainfall/soil moisture parameters into the dynamic trigger engine. It evaluates the resulting fused risk and generates a `SIMULATED_DEMO` alert. It does not overwrite or mutate scientific Parquet datasets.
