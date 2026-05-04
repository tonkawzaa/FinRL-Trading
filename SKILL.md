# FinRL-X Skills & Capabilities

ไฟล์นี้รวบรวม "ความสามารถ (Skills)" และฟีเจอร์เชิงลึกของโปรเจค FinRL-Trading (FinRL-X) เพื่อให้เห็นภาพรวมของระบบที่เป็น AI-Native Modular Infrastructure for Quantitative Trading อย่างครบถ้วน

---

## 1. 🤖 AI & Machine Learning Skills (AI และการเรียนรู้ของเครื่อง)

- **Advanced ML-Based Stock Selection (Point-in-Time):** 
  - คัดเลือกหุ้นแบบเจาะลึกโดยแบ่งตาม 4 กลุ่มอุตสาหกรรม (Growth Tech, Cyclical, Real Assets, Defensive) 
  - ใช้โมเดล Machine Learning ถึง 7 ตัวแข่งขันกัน (Random Forest, XGBoost, LightGBM, HistGradientBoosting, ExtraTrees, Ridge, Stacking) เพื่อหาโมเดลที่ให้ค่า Validation MSE ดีที่สุด หรือใช้แบบ Ensemble (Inverse-MSE Weighted)
  - มีระบบ **Point-in-Time SP500 Filter** เพื่อป้องกันปัญหา Data Leakage อย่างเด็ดขาด โดยจะประเมินผลเฉพาะรายชื่อหุ้นที่อยู่ใน SP500 ณ วันที่เทรด (Tradedate) เท่านั้น
- **DRL Portfolio Allocation:** 
  - นำ Deep Reinforcement Learning (อัลกอริทึม PPO และ SAC) มาหาค่าน้ำหนักพอร์ต (Continuous Weight Generation) ทำให้ระบบสามารถเรียนรู้ปรับสัดส่วนการลงทุนตามพลวัตของตลาดได้ลึกซึ้งกว่าวิธีทางสถิติดั้งเดิม (เช่น Mean-Variance)
- **LLM-Ready Sentiment Analysis:** 
  - สถาปัตยกรรมออกแบบมารองรับการวิเคราะห์ Sentiment ของข่าวสารด้วย Large Language Models (LLMs) เพื่อนำมาประมวลผลเป็น Alpha factor เสริมในชั้นข้อมูล

## 2. 📈 Trading & Strategy Skills (กลยุทธ์การลงทุนและการเทรด)

- **Adaptive Multi-Asset Rotation:** 
  - กลยุทธ์สับเปลี่ยนสินทรัพย์ไปมาระหว่างกลุ่ม Growth Tech, Real Assets และ Defensive ตามสภาวะตลาด โดยคำนวณจาก Information Ratio เทียบกับ Benchmark (QQQ) และใช้ค่า Residual Momentum ควบคู่กับ Z-score เพื่อค้นหาสินทรัพย์ที่ Outperform ที่สุด
- **Dynamic Market Regime Detection:**
  - **Slow Regime:** ตรวจจับแนวโน้มตลาดระยะ 26 สัปดาห์ และความผันผวนผ่านดัชนี VIX
  - **Fast Risk-Off:** ระบบเตือนภัยวิกฤตเฉียบพลันภายใน 3 วัน ช่วยให้พอร์ต Rotate หลบเข้ากลุ่ม Defensive หรือถือเงินสด (Cash) ได้ทันท่วงที
- **Signal & Timing Adjustment:** 
  - จับจังหวะการเข้าออกตลาด (Timing Overlay) ด้วยตัวกรองทางเทคนิค เช่น KAMA (Kaufman Adaptive Moving Average) ช่วยลดสัญญาณหลอกในช่วงตลาด Sideway
- **Professional Risk Management:** 
  - **Trailing Stop-Loss & Absolute Stop-Loss:** ระบบตัดขาดทุนอัตโนมัติทั้งแบบรายตัวและระดับพอร์ตโฟลิโอ
  - **Daily Monitoring & Weekly Rebalance:** ปรับโครงสร้างพอร์ตหลักแบบรายสัปดาห์ แต่เฝ้าระวังความเสี่ยง (Stop-Loss / Fast Risk-Off) ทุกวันเพื่อความปลอดภัยสูงสุด

## 3. 🛠️ Engineering & Infrastructure Skills (วิศวกรรมข้อมูลและโครงสร้างพื้นฐาน)

- **Weight-Centric Architecture (Decoupled System):** 
  - สถาปัตยกรรมแบบแยกส่วน (Modular) อย่างแท้จริง โดยเชื่อมต่อทุกกระบวนการผ่าน "น้ำหนักพอร์ต (Target Weights)" ทำให้สามารถสลับหรืออัปเกรดชิ้นส่วน เช่น โมเดลเลือกหุ้น (Stock Selection) หรือกฎความเสี่ยง (Risk Overlay) ได้อิสระ โดยรับประกันว่าพฤติกรรมระหว่าง Backtest และ Live Trade จะตรงกัน 100%
- **Automated & Robust Data Pipeline:** 
  - ดึงข้อมูลอัตโนมัติจาก Financial Modeling Prep (FMP), Yahoo Finance และ WRDS
  - มีระบบแปลง `datadate` เป็น `tradedate` ที่จัดการระยะเวลาหน่วงของการประกาศงบการเงิน (Lag time) อย่างแม่นยำ พร้อมคำนวณ 52 Fundamental factors และแคชลง SQLite Database
- **Professional Backtesting Engine:** 
  - ขับเคลื่อนด้วย `bt` framework รองรับการคำนวณ Transaction Costs และเปรียบเทียบผลตอบแทนกับ Benchmark หลายตัวพร้อมกัน (เช่น QQQ, SPY) แสดงผลเชิงลึกทั้ง Drawdown, Sharpe Ratio และ Calmar Ratio
- **Live / Paper Trading Integration:** 
  - เชื่อมต่อกับ Alpaca API แบบ Multi-account รองรับการส่งคำสั่งซื้อขายจริง (Live) และจำลอง (Paper Trading) พร้อมระบบ Pre-trade Risk Checks ป้องกันการสาดออเดอร์ผิดพลาด

## 4. 💻 Developer & Deployment Skills (ทักษะสำหรับนักพัฒนาและการนำไปใช้)

- **One-Command Deployment (`deploy.sh`):** 
  - จัดการระบบผ่าน Shell script ที่ใช้งานง่าย ครอบคลุมการรัน Backtest แบบกำหนดช่วงเวลา, รันหาสัญญาณรายวัน (Single date) หรือรัน Paper trade แบบ Dry-run โดยไม่ต้องพิมพ์คำสั่ง Python ยาวๆ
- **Pydantic Configuration Management:**
  - รวมการตั้งค่าทั้งหมดไว้ในไฟล์ YAML และจัดการ Environment Variables (เช่น API Keys) ผ่าน `.env` ควบคุมความถูกต้องด้วย Pydantic ทำให้โค้ดสะอาดและตรวจสอบ Config ได้ก่อนรัน
- **Interactive Web Dashboard:** 
  - มี User Interface (UI) แบบ Interactive ที่พัฒนาด้วย Streamlit (`src/web/app.py`) เพื่อให้นักเทรดสามารถมอนิเตอร์พอร์ตโฟลิโอ, สั่งรัน Backtest และดู Analytics ต่างๆ ได้สะดวก
- **Containerization (Docker Ready):** 
  - มีไฟล์ Dockerfile และ docker-compose.yml เตรียมพร้อมสำหรับการ Deploy ขึ้นเซิร์ฟเวอร์แบบ Container เพื่อความเสถียรในระดับ Production

---

*หมายเหตุ: `SKILL.md` นี้ออกแบบมาเพื่อใช้อธิบายขีดความสามารถของโปรเจค FinRL-X และสามารถใช้เป็นคู่มือ (Instruction/Contextual Knowledge) แก่ AI Agent เพื่อให้เข้าใจสถาปัตยกรรมทั้งหมดของโปรเจคได้อย่างถูกต้อง*
