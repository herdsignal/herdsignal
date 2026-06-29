# HerdSignal

> A data-driven timing tool for long-term US equity investors

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Spring Boot](https://img.shields.io/badge/Spring_Boot-3.x-6DB33F?logo=springboot&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![MariaDB](https://img.shields.io/badge/MariaDB-10.x-003545?logo=mariadb&logoColor=white)

---

## Why I Built This

I've held NVDA since 2021 and watched it swing from +600% to -50% and back — multiple times. Every dip felt like a test of conviction, every peak a temptation to cash out too early or too late. The problem wasn't my thesis; it was having no systematic signal to act on. HerdSignal quantifies that gut feeling — translating crowd psychology into a 0–100 score so I know when the herd is rushing in (time to trim) and when it's fleeing (time to buy more).

---

## What Is the HERD Index?

The HERD Index measures crowd sentiment for an individual stock on a **0–100 scale**, updated daily after market close. It combines five technical indicators, normalized against each stock's own 10-year history — so an NVDA score of 80 and a KO score of 80 carry the same relative meaning.

### Five Stages

| Score | Stage | Color | Action |
|-------|-------|-------|--------|
| 0 – 15 | **Flee** | 🔵 Blue | Aggressive buy (30% add) |
| 15 – 40 | **Scatter** | 🩵 Light blue | Start scaling in (10% add) |
| 40 – 60 | **Calm** | ⚫ Gray | Hold current position |
| 60 – 75 | **Drift** | 🟠 Orange | Partial trim (5% reduce) |
| 75 – 100 | **Rush** | 🔴 Red | Significant trim (30% reduce) |

> Signal cooldown: signals within 20 days of the same type are suppressed to prevent overtrading.

---

## Core Features

- **Portfolio Dashboard** — S&P 500 HERD banner + per-stock scores with live particle animation
- **Stock Detail** — Full indicator breakdown (5 metrics), timing signal, analyst targets (Phase 2)
- **Ticker Search** — Debounced live search with HERD preview, popular stocks grid, recent history
- **Watchlist** — Separate tracked list with instant remove
- **Daily Scheduler** — Auto-calculates HERD for all tracked tickers at 16:30 ET after market close
- **AI Rebalancing** *(Phase 2)* — Claude API-powered portfolio analysis with specific $ action suggestions

---

## Tech Stack

| Layer | Technology | Role |
|-------|-----------|------|
| Data Engine | Python 3.12 + yfinance + pandas-ta | Collect → Calculate → Store |
| REST API | Spring Boot 3.x + JPA + Lombok | Serve DB data to frontend |
| Database | MariaDB 10.x | Single source of truth |
| Frontend | React 18 + Vite 5 + react-router-dom | Dashboard & UI |
| Scheduler | APScheduler (BlockingScheduler) | Daily HERD update at 16:30 ET |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Data Engine  (Python)                                       │
│                                                             │
│  yfinance ──► collectors/ ──► indicators/ ──► herd/         │
│                                              calculator.py  │
│                                                   │         │
│                                              saver.py       │
└───────────────────────────────────────────────────┼─────────┘
                                                    │ INSERT
                                                    ▼
                                              ┌──────────┐
                                              │  MariaDB  │
                                              │           │
                                              │ herd_scores│
                                              │ herd_ind.. │
                                              │ daily_prices│
                                              │ user_port. │
                                              │ user_watch.│
                                              └─────┬──────┘
                                                    │ SELECT
                                                    ▼
┌─────────────────────────────────────────────────────────────┐
│  REST API  (Spring Boot)                                     │
│                                                             │
│  GET /api/stocks/{ticker}/herd                              │
│  GET /api/portfolio/herd                                    │
│  GET /api/watchlist/herd                                    │
│  POST|DELETE /api/portfolio                                 │
│  POST|DELETE /api/watchlist                                 │
└───────────────────────────────────────────────────┬─────────┘
                                                    │ JSON
                                                    ▼
┌─────────────────────────────────────────────────────────────┐
│  Dashboard  (React 18)                                       │
│                                                             │
│  /            Portfolio Dashboard + S&P500 banner           │
│  /stock/:id   HERD card + indicator breakdown               │
│  /search      Live ticker search + watchlist add            │
│  /watchlist   Watched stocks + remove                       │
└─────────────────────────────────────────────────────────────┘
```

---

## HERD Algorithm

Five indicators are each normalized to 0–100 using **percentile rank against 10 years of the same stock's history**, then weighted-summed:

| Indicator | Weight | What It Captures |
|-----------|--------|-----------------|
| Monthly RSI | 20% | Long-term momentum extremes |
| Weekly RSI | 20% | Mid-term momentum extremes |
| 52-Week Position | 20% | Where price sits in its annual range |
| MA200 Deviation | 20% | Distance from the 200-day trend |
| Volume Strength | 20% | Recent volume vs. 20-day average |

Percentile normalization means the same formula works for every ticker — a Rush in NVDA and a Rush in KO represent equivalent crowd-psychology extremes relative to their own histories.

---

## Backtesting Results

Backtested on 5 years of daily data. Strategy: hold normally during Calm/Scatter, trim 30% at Rush, add 30% at Flee.

| Ticker | B&H Return | HERD Return | Return Preserved | MDD Improvement |
|--------|-----------|-------------|-----------------|-----------------|
| NVDA | +17,242% | +6,634% | 38.5% | **−10.3%p** |
| AAPL | +186% | +143% | 76.9% | **−7.8%p** |
| TSLA | +812% | +521% | 64.2% | **−9.4%p** |
| META | +623% | +401% | 64.4% | **−8.1%p** |
| **Average** | — | — | **59.3%** | **−8.9%p** |

> **Key insight:** The strategy significantly reduces maximum drawdown at the cost of some upside — the right trade-off for long-term investors who want to hold through volatility without panic-selling or FOMO-buying.
>
> Flee signal frequency: 6–10% of trading days (ideal).
> Rush signal frequency: 3–9% of trading days (varies by ticker volatility).

---

## Getting Started

### Prerequisites

- Python 3.12 with `data/.venv/`
- Java 17+, Gradle
- MariaDB running locally
- Node.js 18+

### 1. Database Setup

```bash
# Create database and user
mysql -u root -p
CREATE DATABASE herdsignal CHARACTER SET utf8mb4;
CREATE USER 'herdsignal'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON herdsignal.* TO 'herdsignal'@'localhost';
```

### 2. Data Engine

```bash
cd data/

# Create .env from template
cp .env.example .env   # fill in DB credentials

# Install dependencies
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Initialize DB schema
.venv/bin/python3.12 init_db.py

# Seed default tickers (SPY benchmark + starter portfolio)
.venv/bin/python3.12 setup_default_tickers.py

# Run HERD calculation immediately (skip scheduler wait)
.venv/bin/python3.12 scheduler/herd_scheduler.py --run-now

# Start daily scheduler daemon (runs at 16:30 ET every market day)
.venv/bin/python3.12 scheduler/herd_scheduler.py
```

### 3. Backend

```bash
cd backend/
./gradlew bootRun
# API available at http://localhost:8080
```

### 4. Frontend

```bash
cd frontend/
npm install
npm run dev
# Dashboard at http://localhost:5173 (or 5174 if port is taken)
```

### Quick API Check

```bash
curl http://localhost:8080/api/stocks/NVDA/herd
curl http://localhost:8080/api/portfolio/herd
curl http://localhost:8080/api/stocks/SPY/herd
```

---

## Development Roadmap

### Phase 1 — Technical Indicators (Current) ✅

- [x] HERD Index algorithm (5 indicators, percentile normalization)
- [x] Daily scheduler with APScheduler
- [x] Spring Boot REST API (portfolio + watchlist + per-stock HERD)
- [x] React dashboard (portfolio, detail, search, watchlist pages)
- [x] S&P 500 benchmark (SPY) as market-wide HERD signal

### Phase 2 — Leading Indicators

- [ ] Options Put/Call ratio integration
- [ ] Short interest ratio
- [ ] Cross-ticker correlation weighting
- [ ] **AI Rebalancing** — Claude API analyzes portfolio and suggests specific $ amounts to buy/sell

### Phase 3 — Macro Overlay

- [ ] VIX integration
- [ ] DXY (dollar index)
- [ ] 10-year Treasury yield

### Phase 4 — ML Optimization

- [ ] Auto-tune weights per ticker category (growth vs. value vs. ETF)
- [ ] Reinforcement learning for signal timing

---

## Known Limitations (v1)

These are understood trade-offs, not bugs:

| Limitation | Impact | Planned Fix |
|------------|--------|-------------|
| All lagging indicators | Signal fires after price already moved | Phase 2: leading indicators |
| No macro awareness | Misses rate hike / geopolitical shocks | Phase 3: VIX, DXY, yields |
| Can't catch V-shaped recoveries | Short sharp crashes not flagged | Phase 2: Put/Call ratio |
| No cross-ticker correlation | Treats each stock independently | Phase 2: correlation matrix |

---

## License

MIT
