# 🧠 ML Bucket Selection Skill (ทักษะโมดูลคัดเลือกหุ้นด้วย ML)

`src/strategies/ml_bucket_selection.py` เป็นระบบคัดเลือกหุ้นด้วย Machine Learning ระดับสถาบัน ที่แบ่งหุ้นเป็น 4 กลุ่มอุตสาหกรรม (Buckets) แล้วเทรนโมเดลแยกกันเพื่อทำนายผลตอบแทน (y_return) ของไตรมาสถัดไป

---

## 1. 🏗️ Architecture (สถาปัตยกรรม)

### Sector → Bucket Mapping
หุ้นถูกจัดกลุ่มจาก GICS Sector เป็น 4 Buckets:

| Bucket | Sectors ที่รวมอยู่ |
|---|---|
| **Growth Tech** | Information Technology, Communication Services |
| **Cyclical** | Consumer Discretionary, Financials, Industrials |
| **Real Assets** | Energy, Materials, Real Estate |
| **Defensive** | Health Care, Consumer Staples, Utilities |

### ML Models (7 โมเดลแข่งขัน)

| โมเดล | ประเภท | หมายเหตุ |
|---|---|---|
| Random Forest | Ensemble (Bagging) | n=200, depth=8 |
| XGBoost | Gradient Boosting | Optional (ต้อง install) |
| LightGBM | Gradient Boosting | Optional (ต้อง install) |
| HistGradientBoosting | Gradient Boosting | Built-in sklearn |
| ExtraTrees | Ensemble (Bagging) | n=200, depth=8 |
| Ridge | Linear Regression | alpha=1.0, baseline |
| **Stacking** | Meta-ensemble | Top 3 โมเดล + Ridge meta-learner |

### Feature Set (33 Features)

| Category | Features | จำนวน |
|---|---|---|
| Valuation | pe, ps, pb, peg, ev_multiple | 5 |
| Profitability | EPS, roe, gross_margin, operating_margin | 4 |
| Cash Flow | fcf_per_share, cash_per_share, capex_per_share, fcf_to_ocf, ocf_ratio | 5 |
| Leverage | debt_ratio, debt_to_equity, debt_to_mktcap | 3 |
| Liquidity | cur_ratio | 1 |
| Efficiency | acc_rec_turnover, asset_turnover, payables_turnover | 3 |
| Coverage | interest_coverage, debt_service_coverage | 2 |
| Dividend | dividend_yield | 1 |
| Solvency | solvency_ratio | 1 |
| Per-Share | BPS | 1 |
| **Momentum** | ret_1q, ret_4q, ret_accel, eps_chg, roe_chg, gm_chg, om_chg | **7** |
| **Sector Dummies** | one-hot encoded gsector (dynamic) | ~10 |

---

## 2. 🔄 Workflow (ขั้นตอนการทำงาน)

```
SQLite DB (fundamental_data)
    │
    ▼
1. Load & Filter ───── Universe filter (SP500/NASDAQ100/CSV)
    │
    ▼
2. Feature Engineering
    ├── Momentum (ret_1q, ret_4q, ret_accel, eps/roe/gm/om changes)
    ├── Fill NULL trade_price → Yahoo Finance (today's price)
    ├── Winsorize (clip at 1st/99th percentile)
    └── Sector one-hot encoding
    │
    ▼
3. Point-in-Time Filter ── ป้องกัน Look-ahead Bias ด้วย Historical Constituents
    │
    ▼
4. Per-Bucket Training
    ├── Train/Val split (val = last N quarters ≤ val_cutoff)
    ├── 7 models compete → select best by Val MSE
    ├── Stacking ensemble (top 3 + Ridge)
    ├── Retrain on train+val → final inference
    └── Inverse-MSE weighted ensemble prediction
    │
    ▼
5. Output
    ├── CSV predictions (ranked per bucket)
    ├── Excel dashboard (Rankings + Models + Features)
    └── Feature importance analysis
```

---

## 3. 🛡️ Anti-Bias Mechanisms (ระบบป้องกัน Bias)

### Point-in-Time Universe Filter
- ใช้ไฟล์ `data/{universe}_historical_constituents.csv` เพื่อกรอง Universe ณ แต่ละ Tradedate
- ป้องกัน **Survivorship Bias**: เทรนเฉพาะหุ้นที่อยู่ในดัชนี ณ เวลานั้นจริงๆ
- ป้องกัน **Look-ahead Bias**: ใช้ `datadate → tradedate` mapping ที่มี lag 2 เดือน (เช่น Q4 Dec-31 → Mar-01 ปีถัดไป) เพื่อจำลองความล่าช้าของการประกาศงบจริง

### Winsorization
- Clip ค่า Feature ทั้งหมดที่ percentile 1st/99th เพื่อลดผลกระทบจาก Outlier
- `ret_accel` คำนวณหลัง winsorize เพื่อรักษาความสอดคล้องทางพีชคณิต

### Validation Strategy
- ใช้ **Temporal Split**: Val = N ไตรมาสสุดท้ายก่อน `val_cutoff` (default: 3Q)
- **ไม่ใช้** Random Split เพราะข้อมูลเป็น Time Series → ป้องกัน Data Leakage

---

## 4. 🔀 Advanced Modes (โหมดขั้นสูง)

### Mixed-Vintage Mode (`--mixed-vintage`)
- สำหรับช่วงเปลี่ยนไตรมาส: หุ้นบางตัวประกาศ Q1 แล้ว บางตัวยังใช้ Q4
- รวมข้อมูลล่าสุดของแต่ละตัว → จัดอันดับร่วมกัน
- Align `trade_price` ทุกตัวด้วยราคาวันนี้จาก Yahoo Finance

### Latest-Snapshot Mode (`--latest-snapshot`)
- ดึงข้อมูลล่าสุดของทุก Ticker ในดัชนี (~500 ตัว)
- คำนวณ Actual Return จาก FMP price data (ref_date → end_date)
- ใช้สำหรับ Production: "วันนี้ควรซื้อหุ้นตัวไหน?"

### Dual Ensemble (`--dual-ensemble`)
- **Stage 1**: Unified Model — เทรนโมเดลเดียวกับหุ้นทุกตัว + sector dummies
- **Stage 2**: Bucket-Split Models — เทรนแยกรายกลุ่ม (จากขั้นตอนปกติ)
- **Stage 3**: Rank-based Combination — `dual_score = α × unified_rank%ile + (1-α) × bucket_rank%ile`
- Alpha Sensitivity analysis: ทดสอบ α = 0.0, 0.3, 0.5, 0.7, 1.0

### Mixed Alpha (`--mixed-alpha`)
- ใช้ค่า α ที่ดีที่สุดสำหรับแต่ละ Bucket (จาก backtest):

| Bucket | α | Strategy |
|---|---|---|
| Growth Tech | 0.0 | Pure Bucket-Split (tech มี features เฉพาะตัว) |
| Cyclical | 0.7 | Heavy Unified (sectors หลากหลาย ต้องการ cross-sector signal) |
| Real Assets | 1.0 | Pure Unified (sample น้อย, bucket model overfit) |
| Defensive | 1.0 | Pure Unified (fundamentals-driven, best Sharpe) |

### Unified-Only Mode (`--unified-only`)
- ข้ามการแบ่ง Bucket ทั้งหมด → เทรนโมเดลเดียว จัดอันดับหุ้นทุกตัวรวมกัน

---

## 5. ⚙️ CLI Arguments (พารามิเตอร์คำสั่ง)

| Argument | คำอธิบาย | ค่าเริ่มต้น |
|---|---|---|
| `--db` | Path ไปยัง SQLite database | `data/finrl_trading.db` |
| `--universe` | Filter Universe (sp500, nasdaq100, หรือ CSV path) | `None` (ใช้ทั้งหมดใน DB) |
| `--val-cutoff` | วันสุดท้ายของ Validation | `2025-12-31` |
| `--val-quarters` | จำนวนไตรมาสสำหรับ Validation | `3` |
| `--output-dir` | โฟลเดอร์สำหรับบันทึกผลลัพธ์ | `data/` |
| `--latest-snapshot` | เปิดโหมด Latest Snapshot | `False` |
| `--mixed-vintage` | เปิดโหมด Mixed Vintage | `False` |
| `--dual-ensemble` | เปิด Dual Model Ensemble | `False` |
| `--ensemble-alpha` | ค่า α สำหรับ Dual Ensemble | `0.5` |
| `--mixed-alpha` | เปิด Per-bucket optimal α | `False` |
| `--unified-only` | โหมด Unified model เดียว | `False` |
| `--infer-date` | ระบุ datadate เฉพาะสำหรับ inference | `None` |
| `--ref-date` | วันอ้างอิงสำหรับคำนวณ return (latest-snapshot) | `None` |
| `--end-date` | วันสิ้นสุดสำหรับคำนวณ return | `None` (วันนี้) |

---

## 6. 📋 Usage Examples (ตัวอย่างการใช้งาน)

```bash
# Standard: Per-bucket ML selection (S&P 500)
python3 src/strategies/ml_bucket_selection.py --universe sp500

# Mixed-vintage: ใช้ข้อมูลล่าสุดของแต่ละตัว (สำหรับช่วงเปลี่ยนไตรมาส)
python3 src/strategies/ml_bucket_selection.py --universe sp500 --mixed-vintage

# Dual Ensemble: รวม Unified + Bucket models
python3 src/strategies/ml_bucket_selection.py --universe sp500 --dual-ensemble --ensemble-alpha 0.5

# Mixed Alpha: ใช้ α ที่เหมาะสมแต่ละ Bucket
python3 src/strategies/ml_bucket_selection.py --universe sp500 --mixed-alpha

# Latest Snapshot: วิเคราะห์หุ้นทั้งดัชนีด้วยข้อมูลล่าสุด
python3 src/strategies/ml_bucket_selection.py --universe sp500 \
    --latest-snapshot --ref-date 2026-03-31 --end-date 2026-05-01

# Unified-only: โมเดลเดียวจัดอันดับรวม
python3 src/strategies/ml_bucket_selection.py --universe sp500 --unified-only
```

---

## 7. 📁 Output Files (ไฟล์ผลลัพธ์)

| ไฟล์ | เนื้อหา |
|---|---|
| `{prefix}_ml_bucket_predictions_{date}.csv` | Prediction + ranking ของทุกหุ้น |
| `{prefix}_ml_bucket_model_results_{date}.csv` | Val MSE ของทุกโมเดลทุก Bucket |
| `{prefix}_ml_feature_importance_{date}.csv` | Feature Importance แยกรายโมเดล/Bucket |
| `{prefix}_ml_dashboard_{date}.xlsx` | Excel dashboard (Rankings + Models + Features) |
| `{prefix}_ml_dual_ensemble_{date}.csv` | ผลลัพธ์ Dual Ensemble (ถ้าเปิดใช้) |
| `{prefix}_ml_mixed_alpha_{date}.csv` | ผลลัพธ์ Mixed Alpha (ถ้าเปิดใช้) |

---

## 8. 🔗 System Integration (ความเชื่อมโยงในระบบ)

```
data/cache/finrl_trading.db (fundamental_data table)
    │
    ▼
ml_bucket_selection.py  ← ML training & inference
    │
    ├── data_fetcher.py     ← Universe lookup (SP500/NASDAQ100)
    ├── yfinance            ← Fill today's price for momentum
    └── FMP API             ← Actual return calculation (latest-snapshot)
    │
    ▼
data/*.csv, data/*.xlsx    ← Predictions, Rankings, Dashboard
    │
    ▼
Adaptive Rotation Strategy / Execution Engine ← ใช้ผลลัพธ์ในการเทรดจริง
```
