# HerdSignal

**[한국어](README.ko.md)** | English

> A data-driven timing tool for long-term US equity investors

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Spring Boot](https://img.shields.io/badge/Spring_Boot-3.x-6DB33F?logo=springboot&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![MariaDB](https://img.shields.io/badge/MariaDB-10.x-003545?logo=mariadb&logoColor=white)

---

## Why

HerdSignal helps long-term US equity investors decide when to add, hold, or trim positions using data instead of intuition.

It combines each stock's HERD Index with portfolio context and translates the score into actionable guidance.
It is positioned as a decision engine for add/hold/trim actions, not a general-purpose portfolio tracker.

---

## What Is the HERD Index?

The HERD Index is a 0-100 crowd-sentiment score for individual stocks. It is normalized against each stock's own historical behavior, so high-growth stocks and defensive stocks can be evaluated with the same formula.

The production calculation uses a 5-year default price window. HERD v4 starts from the v3 weighted technical score, then applies EPS surprise and sector relative-strength multipliers.

### Five Stages

| Score | Stage | Meaning | Action |
| --- | --- | --- | --- |
| 0-15 | Flee | Crowd exit | Consider aggressive buying |
| 15-40 | Scatter | Crowd dispersion | Consider scaling in |
| 40-60 | Calm | Crowd balance | Hold current position |
| 60-75 | Drift | Crowd tilt | Consider partial trim |
| 75-100 | Rush | Crowd concentration | Consider aggressive trim |

The `Herd Flow` animation visualizes these stages as particle distribution. Flee appears sparse across the whole canvas, while Rush appears tightly concentrated in a narrow area.

---

## Core Features

- **Dashboard**: S&P 500 Herd Flow banner, portfolio valuation, core rebalance check, and holding-level HERD action cards
- **Watchlist**: opportunity queue and HERD cards sorted by long-term add/trim timing priority
- **Search**: ticker/company search, HERD preview, recent searches, and portfolio/watchlist add actions
- **Stock Detail**: HERD v4 score, HERD_v5 Action Layer guidance, signal reliability board, HERD Index history, Fundamental Guard, and indicator breakdown
- **HERD Lab**: model version, backtest summary, action matrix, and validation data for the HERD methodology

---

## Tech Stack

| Layer | Technology | Role |
| --- | --- | --- |
| data | Python 3.12, yfinance, pandas-ta, APScheduler, Finnhub | Collect, calculate, store |
| backend | Spring Boot 3.x, JPA, MariaDB, Gradle | DB reads, REST API, Python on-demand execution |
| frontend | React 18, Vite 5, Recharts, Axios | Dashboard UI |
| database | MariaDB | HERD, portfolio, watchlist, asset history |

---

## Architecture

```text
yfinance / Finnhub
        |
        v
Python data engine
        |
        v
MariaDB
        |
        v
Spring Boot REST API
        |
        v
React frontend
```

Python calculates and stores data. Spring Boot serves database-backed APIs. React renders the product experience.

---

## Main APIs

- `GET /api/stocks/{ticker}/herd`
- `POST /api/stocks/{ticker}/herd/refresh`
- `GET /api/stocks/search?q=apple`
- `GET /api/stocks/{ticker}/financials`
- `GET /api/stocks/{ticker}/herd/history?period=1m|3m|1y|3y`
- `GET /api/stocks/{ticker}/herd/reliability?years=3`
- `GET /api/portfolio`
- `GET /api/portfolio/herd`
- `POST /api/portfolio/herd/refresh`
- `GET /api/portfolio/summary`
- `GET /api/portfolio/history?period=month|year`
- `GET /api/portfolio/realtime`
- `GET /api/watchlist`
- `GET /api/watchlist/herd`

The current MVP intentionally exposes HERD, search, financials, portfolio, and watchlist APIs only.

---

## HERD Algorithm

The base score is a weighted sum of percentile-normalized indicators.

| Indicator | Weight | Description |
| --- | ---: | --- |
| Monthly RSI | 24% | Long-term momentum |
| 200-week MA position | 20% | Long-term trend position |
| Weekly RSI | 19% | Mid-term momentum |
| 52-week position | 19% | Position in annual price range |
| MA200 deviation | 18% | Distance from 200-day trend |
| Volume strength | 0% | Computed but inactive in production score |

HERD v4 applies two multipliers to the base score:

- EPS surprise: recent four-quarter beat/miss pattern
- Sector relative strength: stock 90-day return vs sector ETF 90-day return

The final score is stored in `herd_scores.herd_score`. The API also exposes `herdV4`, `herdBase`, `epsMultiplier`, and `sectorMultiplier`.

Signal reliability is calculated separately from data quality. It compares saved HERD history with later price movement and reports Flee hit rate, Rush hit rate, MDD improvement, return preservation, and annual action count.

---

## Getting Started

### Prerequisites

- Python 3.12
- Java 17+
- MariaDB
- Node.js 18+

### 1. Database

```bash
mysql -u root -p
CREATE DATABASE herdsignal CHARACTER SET utf8mb4;
CREATE USER 'herdsignal'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON herdsignal.* TO 'herdsignal'@'localhost';
```

### 2. Data Engine

```bash
cp .env.example .env
cd data
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd ..
./scripts/run-data.sh init_db.py
./scripts/run-data.sh setup_default_tickers.py
./scripts/run-data.sh scheduler/herd_scheduler.py --run-now
./scripts/run-data.sh scheduler/herd_scheduler.py
```

### 3. Backend

```bash
./scripts/run-backend.sh
```

The API runs at `http://localhost:8080`.

### 4. Frontend

```bash
cd frontend
npm install
cd ..
./scripts/run-frontend.sh
```

The frontend usually runs at `http://localhost:5173`.

---

## Current Limitations

- The MVP is intentionally focused on HERD-based add/hold/trim timing, not full portfolio management.
- The Rebalance Plan, History page, and Herd Flow Preview routes exist, but they are hidden from the main sidebar.
- Target weights are stored in localStorage, not in the database.
- Authentication, multi-user support, brokerage integration, and deployment are not implemented yet.
- Portfolio entry is currently manual. Official brokerage APIs or low-friction import flows can be evaluated later.
- The v5 volatility layer is a backtest candidate and is not part of the production HERD score.

---

## Roadmap

Product direction and priorities are maintained in [ROADMAP.md](./ROADMAP.md).

---

## License

MIT
