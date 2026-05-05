# 📊 Data Fetcher Skill (ทักษะโมดูลดึงข้อมูล)

`src/data/data_fetcher.py` เป็นหัวใจหลักในการดึงและจัดการข้อมูล (Data Ingestion Layer) ของ FinRL-X โดยทำหน้าที่เป็นสะพานเชื่อมระหว่างแหล่งข้อมูลภายนอกและระบบวิเคราะห์ภายใน

---

## 1. 🌐 Multi-Source Ingestion (การดึงข้อมูลจากหลายแหล่ง)
- **Financial Modeling Prep (FMP) Integration:** รองรับการดึงข้อมูลเชิงลึกระดับสถาบัน ทั้งงบการเงินรายไตรมาส/รายปี, ราคาหุ้นรายวัน และข่าวสาร
- **Yahoo Finance Support:** มีระบบดึงข้อมูลจาก yfinance สำหรับข้อมูลราคาและตัวชี้วัดพื้นฐาน
- **Index Constituents Management:** สามารถดึงรายชื่อหุ้นในดัชนี S&P 500 และ NASDAQ 100 ทั้งแบบปัจจุบันและข้อมูลประวัติย้อนหลัง (Point-in-time)

## 2. 🏛️ Local-First Caching & Data Store (ระบบแคชข้อมูลอัจฉริยะ)
- **Database Centric:** ข้อมูลที่ดึงมาจะถูกเก็บลง SQLite ผ่าน `DataStore` โดยอัตโนมัติ เพื่อลดการเรียก API ซ้ำซ้อนและประหยัดค่าใช้จ่าย
- **Offline Capability:** หากไม่มี API Key หรืออยู่ในโหมด Offline ระบบจะดึงข้อมูลจากฐานข้อมูลท้องถิ่นมาใช้งานแทนได้ทันที (Offline-ready)
- **Incremental Range Fetching:** ระบบฉลาดพอที่จะตรวจสอบว่าช่วงวันที่ต้องการมีอยู่ในฐานข้อมูลหรือไม่ และจะดึงเพิ่มเฉพาะส่วนที่ขาดหายไปเท่านั้น (Gap filling)

## 3. 📑 Fundamental Data Engine (การประมวลผลข้อมูลพื้นฐาน)
- **Comprehensive Factor Calculation:** คำนวณอัตราส่วนทางการเงินกว่า 50 ตัว (Ratios) ครอบคลุมทั้ง Profitability, Liquidity, Solvency, Efficiency และ Valuation (P/E, P/B, P/S)
- **Forward Return Calculation (`y_return`):** มีระบบคำนวณ Log Return ล่วงหน้าของแต่ละไตรมาสเพื่อใช้เป็น Target ในการเทรนโมเดล Machine Learning
- **Point-in-Time Alignment:** จัดการปัญหาความเหลื่อมล้ำของเวลา (Lag) ระหว่างวันปิดงวดบัญชีกับวันประกาศงบจริง เพื่อป้องกันการเกิด Look-ahead Bias
- **Standardized Schema:** แปลงข้อมูลจากแหล่งต่างๆ ให้เป็นฟอร์แมตมาตรฐาน (CRSP/Compustat style) เพื่อความสะดวกในการวิเคราะห์เชิงปริมาณ

## 4. 📰 AI News & Sentiment Analysis (การวิเคราะห์ข่าวด้วย AI)
- **Gemini AI Integration:** เชื่อมต่อกับ Google Gemini API (`google-genai`) เพื่อวิเคราะห์ Sentiment ของข่าวหุ้น (Positive, Neutral, Negative)
- **Configurable Toggle:** มีระบบเปิด/ปิดการใช้งาน AI (`GEMINI_ENABLE_AI`) ผ่าน environment variables เพื่อความยืดหยุ่นในการควบคุมต้นทุน
- **Persistent Sentiment Storage:** บันทึกผลการวิเคราะห์ Sentiment ลงฐานข้อมูลพร้อมชื่อโมเดลและค่าความเชื่อมั่น (Confidence score)

## 5. 🛠️ Robust Engineering (วิศวกรรมข้อมูลที่แข็งแกร่ง)
- **High Performance:** ใช้ `ThreadPoolExecutor` ในการดึงข้อมูลแบบขนาน (Parallelism) ช่วยลดเวลาในการเตรียม Data Universe ขนาดใหญ่
- **Exchange Calendar Integration:** ใช้ `pandas_market_calendars` เพื่อจัดการข้อมูลตามวันเปิด-ปิดจริงของตลาดหุ้น (NYSE/NASDAQ)
- **Automatic Fallback:** มีกลไกการทำงานสำรองในกรณีที่ API ใด API หนึ่งขัดข้องหรือข้อมูลไม่ครบถ้วน

---

# 🗄️ Fetch & Store Fundamentals (สคริปต์ดึงและจัดเก็บข้อมูลพื้นฐาน)

`src/data/fetch_and_store_fundamentals.py` เป็นสคริปต์ CLI (Command-Line Interface) ที่ทำหน้าที่เป็น **"ประตูหน้า"** ของระบบข้อมูลทั้งหมด ใช้สำหรับดึงข้อมูลปัจจัยพื้นฐาน (Fundamental Data) ของหุ้นจำนวนมากและบันทึกลงฐานข้อมูล SQLite — รองรับ **batch processing**, **resumable progress** และ **FMP rate limit handling** อัตโนมัติ

---

## 1. 🔄 Workflow (ขั้นตอนการทำงาน)

สคริปต์ทำงานตามขั้นตอน:

1. **Ticker Identification** — ระบุ Universe ของหุ้น (S&P 500, NASDAQ 100 หรือ Survivorship-free) พร้อม fallback สำหรับกรณี FMP rate limited
2. **DB Cache Check** — ตรวจสอบ ticker ที่มี ≥ 4 quarters ในฐานข้อมูลแล้ว → ข้ามไม่ต้องดึงซ้ำ
3. **Resume Check** — โหลด progress file (`data/.progress/fund_fetch_*.json`) เพื่อข้าม ticker ที่สำเร็จแล้วจากรอบก่อน
4. **Batch Processing** — แบ่ง ticker เป็น batch ละ N ตัว (default 50 = ~200 FMP calls ต่อ batch)
5. **Fundamental Fetching** — เรียก `fetch_fundamental_data()` จาก `data_fetcher.py` ต่อ batch
6. **Incremental Save** — บันทึกผลลง SQLite ทันทีหลังจบแต่ละ batch (ไม่ต้องรอครบทุก ticker)
7. **Progress Persistence** — อัพเดต progress file หลังจบแต่ละ batch เพื่อรองรับ resume
8. **Summary Report** — แสดงสรุปรวมจาก DB

## 2. ⚙️ CLI Arguments (พารามิเตอร์คำสั่ง)

| Argument | คำอธิบาย | ค่าเริ่มต้น |
|---|---|---|
| `--universe` | เลือกดัชนีเป้าหมาย (`sp500` หรือ `nasdaq100`) | `sp500` |
| `--start-date` | วันที่เริ่มต้นดึงข้อมูล (YYYY-MM-DD) | `2021-01-01` |
| `--end-date` | วันที่สิ้นสุดดึงข้อมูล (YYYY-MM-DD) | `2026-04-01` |
| `--limit` | จำกัดจำนวน Ticker สูงสุด | `10000` |
| `--preferred-source` | แหล่งข้อมูลที่ต้องการ | `FMP` |
| `--output-csv` | Path สำหรับบันทึก CSV (ถ้าต้องการ) | `None` |
| `--survivorship-free` | เปิดโหมด Survivorship-free | `False` |
| `--batch-size` | จำนวน ticker ต่อ batch (ปรับตาม FMP plan) | `50` |
| `--force-refresh` | ข้าม DB cache — ดึงใหม่ทั้งหมด | `False` |
| `--reset-progress` | ล้าง progress file แล้วเริ่มจากศูนย์ | `False` |

## 3. 🚦 Rate Limit & Batch Management (การจัดการ Rate Limit)

ระบบรองรับ FMP Free Plan (250 API calls/day) อัตโนมัติ:

- **Batch Sizing:** Ticker 1 ตัวใช้ ~4 API calls (income, balance, cashflow, ratios) — batch 50 ตัว = ~200 calls ภายใน quota
- **Retry with Backoff:** เมื่อ FMP ตอบ 429 (Too Many Requests) ระบบจะ retry ด้วย exponential backoff (5s → 10s → 20s) สูงสุด 3 ครั้ง
- **FMPRateLimitError:** Exception class เฉพาะ — เมื่อ retry หมดหรือเจอ 402 (Payment Required) จะ raise error ขึ้นไปให้ script จัดการ
- **Graceful Stop:** เมื่อโดน rate limit, script จะ:
  1. บันทึก progress file ทันที
  2. แสดงข้อความบอกให้ re-run
  3. Exit ด้วย code 0 (ไม่ crash)
- **Cross-Day Resume:** Re-run script วันถัดไป → โหลด progress file → ข้ามที่เสร็จแล้ว → เริ่มจาก batch ถัดไป

## 4. 💾 DB Cache Intelligence (ระบบแคชฐานข้อมูลอัจฉริยะ)

- **Automatic Skip:** ก่อน fetch ทุกรอบ สคริปต์จะ query DB เพื่อหา ticker ที่มี ≥ 4 quarterly records ในช่วงวันที่ร้องขอ → ข้ามเลย
- **Incremental Save:** ข้อมูลถูก save ลง DB ทีละ batch (ไม่ต้องรอ fetch ครบทั้ง universe)
- **Idempotent:** รันซ้ำกี่ครั้งก็ปลอดภัย — ไม่ duplicate data (ใช้ `INSERT OR REPLACE`)
- **Force Refresh:** ใช้ `--force-refresh` เพื่อบังคับดึงใหม่แม้มี cache อยู่แล้ว

## 5. 📈 Price Data Fallback (ระบบสำรองข้อมูลราคา)

เมื่อ FMP endpoint `historical-price-eod/full` ตอบ 402/403 (plan ไม่รองรับ):

- ระบบจะ **fallback ไปใช้ yfinance** อัตโนมัติสำหรับ price data
- เมื่อตรวจพบ 402 ครั้งแรก → ทุก ticker ที่เหลือจะดึงจาก yfinance ทันที (ไม่เสียเวลาลอง FMP อีก)
- ข้อมูลจาก yfinance ถูกแปลงให้อยู่ใน schema เดียวกับ FMP (prccd, prcod, adj_close ฯลฯ)

## 6. 🛡️ Survivorship-Free Mode (โหมดป้องกัน Survivorship Bias)

ฟีเจอร์สำคัญสำหรับการทำ Quantitative Research:

- เมื่อเปิดใช้งาน (`--survivorship-free`) สคริปต์จะดึงรายชื่อหุ้น **ทุกตัวที่เคยอยู่ใน S&P 500** ตั้งแต่วันที่ `--start-date` จนถึงปัจจุบัน ไม่ใช่เฉพาะหุ้นที่ยังอยู่ในดัชนี ณ วันนี้
- ป้องกัน **Survivorship Bias** — ปัญหาที่โมเดลเก่งเกินจริงเพราะทดสอบเฉพาะกับหุ้นที่รอดชีวิตมาได้
- ใช้ข้อมูลจากไฟล์ `data/sp500_historical_constituents.csv` ร่วมกับรายชื่อปัจจุบันจาก FMP API

## 7. 📋 Usage Examples (ตัวอย่างการใช้งาน)

```bash
# ดึงข้อมูล NASDAQ 100 (batch 50, resume อัตโนมัติ)
python3 src/data/fetch_and_store_fundamentals.py --universe nasdaq100

# วันถัดไป — re-run เพื่อ continue จาก batch ที่ค้าง
python3 src/data/fetch_and_store_fundamentals.py --universe nasdaq100

# ปรับ batch size สำหรับ paid plan (เช่น 200 tickers = 800 calls)
python3 src/data/fetch_and_store_fundamentals.py --universe sp500 --batch-size 200

# Force re-fetch ทั้งหมด (ล้าง cache + progress)
python3 src/data/fetch_and_store_fundamentals.py \
    --universe nasdaq100 --force-refresh --reset-progress

# ดึง S&P 500 แบบ Survivorship-free พร้อมส่งออก CSV
python3 src/data/fetch_and_store_fundamentals.py \
    --start-date 2015-01-01 --end-date 2026-04-01 \
    --survivorship-free --output-csv data/fundamentals_full.csv
```

## 8. 🔗 System Integration (ความเชื่อมโยงในระบบ)

```
.env (FMP_API_KEY)
    │
    ▼
fetch_and_store_fundamentals.py  ← CLI entry point (batch + resume)
    │
    ├── data_fetcher.py          ← ดึงข้อมูลจาก FMP API + คำนวณ 50+ Ratios
    │       ├── FMPRateLimitError ← Exception สำหรับ 402/429 rate limit
    │       ├── yfinance fallback ← สำรองข้อมูลราคาเมื่อ FMP plan ไม่รองรับ
    │       └── data_store.py    ← แคชข้อมูลดิบ (Raw Payload) ลง SQLite
    │
    ├── data_store.py            ← บันทึก Fundamental Records ลง SQLite
    │
    ├── data/.progress/*.json    ← Progress files สำหรับ cross-day resume
    │
    ▼
data/finrl_trading.db            ← Output: ฐานข้อมูลพร้อมใช้งาน
    │
    ▼
data_processor/ (ขั้นตอนถัดไป)   ← Data Cleaning → Feature Engineering → ML Training
```

## 9. 💡 Technical Notes (หมายเหตุทางเทคนิค)

- **FMP Free Plan:** 250 API calls/day — batch 50 tickers จะใช้ ~200 calls → เหลือ buffer ~50 calls สำหรับ ticker list + price data
- **Retry Logic:** `_fetch_fmp_data()` retry สูงสุด 3 ครั้งด้วย exponential backoff (5s, 10s, 20s) เฉพาะ HTTP 429
- **NASDAQ Fallback:** `fetch_nasdaq100_tickers()` มี hardcoded ticker list สำรองเมื่อ FMP 429/402 — ทำให้ batch script ยังรันต่อได้แม้ API หมดโควต้า
- **Fault Tolerant:** หากหุ้นตัวใดดึงข้อมูลไม่สำเร็จ (เช่น Delisted) สคริปต์จะข้ามไปรันตัวถัดไปโดยไม่หยุดชะงัก
- **Extensible Design:** สามารถเพิ่ม Universe อื่นๆ (เช่น SET50, Crypto) ได้ง่ายเพียงแค่เพิ่มฟังก์ชันดึง Ticker ใน `data_fetcher.py` และเพิ่ม `choices` ใน argparse
