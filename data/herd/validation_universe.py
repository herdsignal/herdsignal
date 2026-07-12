"""HERD v6.1 섹터·스타일 분산 검증 유니버스.

운영 종목 선정 목록이 아니라 모델 편향을 확인하기 위한 고정 표본이다.
티커 추가/삭제 시 결과 리포트에 유니버스 버전을 함께 남긴다.
"""

UNIVERSE_VERSION = "2026.07"

SECTOR_UNIVERSE: dict[str, list[str]] = {
    "benchmark": ["SPY", "QQQ", "IWM", "DIA"],
    "technology": ["AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM"],
    "communication": ["GOOGL", "META", "NFLX", "DIS", "TMUS"],
    "consumer_discretionary": ["AMZN", "TSLA", "HD", "MCD", "NKE"],
    "consumer_staples": ["WMT", "COST", "PG", "KO", "PEP"],
    "financials": ["JPM", "BAC", "GS", "V", "MA"],
    "healthcare": ["LLY", "UNH", "JNJ", "ABBV", "MRK"],
    "industrials": ["GE", "CAT", "HON", "UNP", "BA"],
    "energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
    "utilities_real_estate": ["NEE", "DUK", "SO", "AMT", "PLD"],
    "materials": ["LIN", "APD", "SHW", "FCX", "NEM"],
}

TICKERS = list(dict.fromkeys(ticker for rows in SECTOR_UNIVERSE.values() for ticker in rows))

GROUP_ETF = {
    "benchmark": "SPY", "technology": "XLK", "communication": "XLC",
    "consumer_discretionary": "XLY", "consumer_staples": "XLP",
    "financials": "XLF", "healthcare": "XLV", "industrials": "XLI",
    "energy": "XLE", "utilities_real_estate": "XLU", "materials": "XLB",
}
TICKER_SECTOR_ETF = {
    ticker: GROUP_ETF[group]
    for group, tickers in SECTOR_UNIVERSE.items()
    for ticker in tickers
}
