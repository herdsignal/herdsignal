# HerdSignal

**[한국어](README.ko.md)** | English

> A data-driven timing tool for long-term US equity investors

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Spring Boot](https://img.shields.io/badge/Spring_Boot-3.x-6DB33F?logo=springboot&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![MariaDB](https://img.shields.io/badge/MariaDB-10.x-003545?logo=mariadb&logoColor=white)

---

## Why I Built This

I started long-term investing in US stocks in 2024. I believed in the long-term upward trend, but came to understand that bull and bear markets cycle repeatedly along the way.

The problem was that I had no way — beyond gut feeling — to determine whether the stocks I held were relatively expensive or cheap at any given moment.

I thought: if there were objective signals, I could trim partially at peaks to build cash reserves, and add more during downturns to capture greater gains. HerdSignal is the project built to create those signals.

---

## What Is the HERD Index?

The HERD Index measures crowd sentiment for an individual stock on a **0–100 scale**, updated daily after market close. It combines five technical indicators, normalized against each stock's own 10-year history — so an NVDA score of 80 and a KO score of 80 carry the same relative meaning.

### Five Stages

| Score    | Stage       | Color         | Action                        |
| -------- | ----------- | ------------- | ----------------------------- |
| 0 – 15   | **Flee**    | 🔵 Blue       | Aggressive buy (30% add)      |
| 15 – 40  | **Scatter** | 🩵 Light blue | Start scaling in (10% add)    |
| 40 – 60  | **Calm**    | ⚫ Gray       | Hold current position         |
| 60 – 75  | **Drift**   | 🟠 Orange     | Partial trim (5% reduce)      |
| 75 – 100 | **Rush**    | 🔴 Red        | Significant trim (30% reduce) |

> Signal cooldown: signals within 20 days of the same type are suppressed to prevent overtrading.

---

## Core Features

- **Portfolio Dashboard** — S&P 500 HERD banner + per-stock scores with live particle animation
- **Stock Detail** — Full indicator breakdown (5 metrics), timing signal, analyst targets (Phase 2)
- **Ticker Search** — Debounced live search with HERD preview, popular stocks grid, recent history
- **Watchlist** — Separate tracked list with instant remove
- **Daily Scheduler** — Auto-calculates HERD for all tracked tickers at 16:30 ET after market close
- **AI Rebalancing** _(Phase 2)_ — Claude API-powered portfolio analysis with specific $ action suggestions

---

## Tech Stack

| Layer       | Technology                           | Role                          |
| ----------- | ------------------------------------ | ----------------------------- |
| Data Engine | Python 3.12 + yfinance + pandas-ta   | Collect → Calculate → Store   |
| REST API    | Spring Boot 3.x + JPA + Lombok       | Serve DB data to frontend     |
| Database    | MariaDB 10.x                         | Single source of truth        |
| Frontend    | React 18 + Vite 5 + react-router-dom | Dashboard & UI                |
| Scheduler   | APScheduler (BlockingScheduler)      | Daily HERD update at 16:30 ET |

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

| Indicator        | Weight | What It Captures                     |
| ---------------- | ------ | ------------------------------------ |
| Monthly RSI      | 20%    | Long-term momentum extremes          |
| Weekly RSI       | 20%    | Mid-term momentum extremes           |
| 52-Week Position | 20%    | Where price sits in its annual range |
| MA200 Deviation  | 20%    | Distance from the 200-day trend      |
| Volume Strength  | 20%    | Recent volume vs. 20-day average     |

Percentile normalization means the same formula works for every ticker — a Rush in NVDA and a Rush in KO represent equivalent crowd-psychology extremes relative to their own histories.

---

## Backtesting Results

The core question: "Why use it if returns are lower than just holding?"

HerdSignal's goal isn't to maximize returns. It's to reduce the psychological shock of riding peak valuations into a major crash, and to create opportunities to buy more during downturns.

Looking at MDD (Maximum Drawdown):

| Ticker | B&H MDD | HERD MDD | Improvement | Worst-case loss on $10K invested |
|--------|---------|----------|-------------|----------------------------------|
| NVDA   | -66.3%  | -46.5%   | 19.8%p      | $3,370 → $5,350 ($1,980 protected) |
| TSLA   | -73.6%  | -47.2%   | 26.4%p      | $2,640 → $5,280 ($2,640 protected) |
| SPY    | -33.7%  | -15.9%   | 17.8%p      | $6,630 → $8,410 ($1,780 protected) |

Some upside is sacrificed, but actual loss amounts during major crashes are significantly reduced. The difference between holding through a 50% drawdown and giving up is what determines real long-term returns.

v1 limitation: All current indicators are lagging. Adding leading indicators in Phase 2 is expected to improve signal accuracy.

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

| Limitation                      | Impact                                 | Planned Fix                 |
| ------------------------------- | -------------------------------------- | --------------------------- |
| All lagging indicators          | Signal fires after price already moved | Phase 2: leading indicators |
| No macro awareness              | Misses rate hike / geopolitical shocks | Phase 3: VIX, DXY, yields   |
| Can't catch V-shaped recoveries | Short sharp crashes not flagged        | Phase 2: Put/Call ratio     |
| No cross-ticker correlation     | Treats each stock independently        | Phase 2: correlation matrix |

---

## License

MIT
