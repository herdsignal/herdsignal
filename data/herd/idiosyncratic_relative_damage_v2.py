"""시장·섹터를 제거한 종목 고유 상대강도 훼손을 월별 측정한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.rush_damage_profit_take_v1 import load_frames


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")
FEATURES = ["residual_return_21d", "residual_volatility_expansion_21_63", "relative_strength_gap_21_126"]


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_MEASUREMENT_OUTPUT":
        raise ValueError("idiosyncratic relative damage protocol must be locked")
    if "RELATIVE_DAMAGE_ALONE_CREATES_SELL" not in protocol.get("forbidden", []):
        raise ValueError("relative damage action boundary weakened")
    return protocol


def _log_returns(frame: pd.DataFrame, name: str) -> pd.Series:
    close = frame.drop_duplicates("Date").set_index("Date")["Adj Close"].astype(float).sort_index()
    return np.log(close).diff().rename(name)


def features_as_of(stock: pd.DataFrame, spy: pd.DataFrame, sector: pd.DataFrame, as_of: pd.Timestamp, protocol: dict) -> dict:
    aligned = pd.concat([_log_returns(stock, "stock"), _log_returns(spy, "spy"), _log_returns(sector, "sector")], axis=1, join="inner").dropna()
    aligned = aligned.loc[:as_of].tail(protocol["regression"]["lookback_sessions"])
    minimum = protocol["regression"]["minimum_observations"]
    if len(aligned) < minimum:
        return {feature: np.nan for feature in FEATURES}
    design = np.column_stack([np.ones(len(aligned)), aligned.spy.to_numpy(), (aligned.sector - aligned.spy).to_numpy()])
    coefficients = np.linalg.lstsq(design, aligned.stock.to_numpy(), rcond=None)[0]
    residual = pd.Series(aligned.stock.to_numpy() - design @ coefficients, index=aligned.index)
    recent_sessions = protocol["regression"]["recent_sessions"]
    prior_sessions = protocol["regression"]["prior_volatility_sessions"]
    recent, prior = residual.iloc[-recent_sessions:], residual.iloc[-recent_sessions-prior_sessions:-recent_sessions]
    prior_vol = prior.std(ddof=1)
    relative = aligned.stock - aligned.sector
    short = float(relative.iloc[-recent_sessions:].sum())
    long = float(relative.sum()) * recent_sessions / len(relative)
    return {
        "residual_return_21d": float(recent.sum()),
        "residual_volatility_expansion_21_63": float(recent.std(ddof=1) / prior_vol) if prior_vol > 0 else np.nan,
        "relative_strength_gap_21_126": short - long,
    }


def build(panel: pd.DataFrame, protocol: dict) -> tuple[pd.DataFrame, dict]:
    frame = panel.copy()
    frame["month_end"] = pd.to_datetime(frame["month_end"])
    sectors = pd.read_csv(ROOT / protocol["sector_map"]).drop_duplicates("ticker").set_index("ticker")["sector_etf"].to_dict()
    required = set(frame.ticker) | {"SPY"} | {sectors[ticker] for ticker in frame.ticker.unique() if sectors.get(ticker)}
    manifest = json.loads((ROOT / protocol["snapshot"] / "manifest.json").read_text(encoding="utf-8"))
    available = required & set(manifest["files"])
    price_frames = load_frames(ROOT / protocol["snapshot"], available)
    rows = []
    for row in frame.itertuples(index=False):
        values = row._asdict()
        sector = sectors.get(row.ticker)
        if row.ticker not in price_frames or sector not in price_frames:
            values.update({feature: np.nan for feature in FEATURES})
        else:
            values.update(features_as_of(price_frames[row.ticker], price_frames["SPY"], price_frames[sector], pd.Timestamp(row.month_end), protocol))
        rows.append(values)
    output = pd.DataFrame(rows).sort_values(["ticker", "month_end"]).reset_index(drop=True)
    output["relative_strength_gap_change_1m"] = output.groupby("ticker")["relative_strength_gap_21_126"].diff()
    measured = [*FEATURES, "relative_strength_gap_change_1m"]
    report = {
        "report_version": "HERD_IDIOSYNCRATIC_RELATIVE_DAMAGE_V2", "status": "MEASUREMENTS_READY",
        "rows": len(output), "tickers": int(output.ticker.nunique()),
        "coverage": {feature: float(output[feature].notna().mean()) for feature in measured},
        "measurements": measured, "sell_authority": False, "operational_action_ratio": 0.0,
        "survivorship_safe": False, "claim_boundary": "CURRENT_FIXED_UNIVERSE_CONFIRMATION_RESEARCH_ONLY",
    }
    return output, report


def run(protocol_path: Path = PROTOCOL_PATH) -> tuple[pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path)
    return build(pd.read_csv(ROOT / protocol["input_measurements"]), protocol)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measurements", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    frame, report = run()
    frame.to_csv(args.measurements, index=False)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
