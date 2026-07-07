# A-share Research

Research-first Python scaffold for validating A-share daily quantitative strategy logic.

This project intentionally starts with a small and auditable workflow: load daily bars, generate signals, apply simple portfolio construction, run a close-to-close backtest, compare against a benchmark, and export research reports.

## Scope

- Market: China A-shares.
- Frequency: daily bars.
- Purpose: research and strategy validation, not live trading.
- First strategy family: long-only moving-average crossover and relative-strength selection.
- First portfolio model: equal-weight selected names with simple transaction costs.
- First benchmark model: close-to-close benchmark returns from a daily index CSV.

## Project Layout

```text
ashare-research/
├── configs/                 # YAML configuration files
├── data/                    # Local data, ignored by Git except .gitkeep files
│   ├── raw/                 # Source CSV files
│   └── processed/           # Cleaned or derived datasets
├── notebooks/               # Research notebooks
├── scripts/                 # One-off utility scripts
├── reports/                 # Local generated reports, ignored by Git
├── src/ashare_research/
│   ├── analysis/            # Performance metrics
│   ├── backtest/            # Research backtest engine
│   ├── data/                # Data loading and validation
│   ├── factors/             # Factor calculations
│   ├── risk/                # Position sizing and risk controls
│   └── strategies/          # Strategy signal definitions
└── tests/                   # Regression and smoke tests
```

## Quick Start

```powershell
cd E:\Code\ashare-research
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,dashboard,notebook]"
python scripts/create_sample_data.py
ashare-validate-data --config configs/backtest.yaml
ashare-run-backtest --config configs/backtest.yaml
```

## Dashboard

```powershell
cd E:\Code\ashare-research
streamlit run dashboard.py
```

The dashboard can also run the example backtest from the sidebar and then render the generated reports.

If a report directory also contains `symbol_technical_analysis.csv`, the dashboard will render a dedicated single-stock technical analysis tab.

## Strategy Templates

Two strategy config templates are included:

- `configs/backtest.yaml`: moving-average crossover.
- `configs/relative_strength.yaml`: cross-sectional relative strength with signal-weight sizing.

Example:

```powershell
ashare-run-backtest --config configs/relative_strength.yaml
```

## Validate Data Inputs

Before running a backtest on downloaded or vendor-supplied data, validate the normalized research inputs first:

```powershell
cd E:\Code\ashare-research
ashare-validate-data --config configs/backtest.yaml
```

Expected success output includes:

```text
validation_status: ok
bar_rows: 3912
symbol_count: 12
start_date: 2024-01-02
end_date: 2024-12-31
benchmark_rows: 243
trading_calendar_days: 244
universe_rows: 3912
```

This command reuses the same loader and contracts validation path as the research pipeline, so it is the preferred preflight check before `ashare-run-backtest`.

## Analyze Specific Symbols

You can run the formal single-stock technical analysis workflow with the same unified data loader and report directory conventions:

```powershell
cd E:\Code\ashare-research
ashare-analyze-symbols --config configs/symbol_analysis.yaml
```

Override symbols from the command line when needed:

```powershell
ashare-analyze-symbols --config configs/symbol_analysis.yaml --symbols 300059.SZ,603986.SH,002714.SZ
```

This command writes `symbol_technical_analysis.csv` to the configured report directory. The current decision uses Chinese labels such as `偏买入 / 偏持有 / 偏卖出`, and is a score-based technical view built from trend, volume confirmation, relative strength, and pullback risk; it is a research aid, not investment advice.

## Download Real Data

You can download public A-share daily CSV files from Guidebee and convert them into the project format:

```powershell
cd E:\Code\ashare-research
python scripts/download_guidebee_data.py --start-date 2024-01-01 --end-date 2024-12-31
```

The script writes `data/raw/daily_bars.csv` with this normalized schema:

```text
date,symbol,open,high,low,close,volume,amount
```

Guidebee symbols such as `sh600000` and `sz000001` are converted to the project format `600000.SH` and `000001.SZ`.

The downloader also writes inferred support files used by the backtest:

- `data/raw/trading_calendar.csv`: trading dates observed in the downloaded rows.
- `data/raw/universe.csv`: daily date/symbol membership inferred from available rows.

After downloading and normalizing data, validate it before backtesting:

```powershell
ashare-validate-data --config configs/backtest.yaml
```

The source is useful for research, but you should still verify adjusted-price handling and corporate-action treatment before trusting any live strategy work.

If you prefer a direct A-share data source, you can also use Baostock:

```powershell
cd E:\Code\ashare-research
python scripts/download_baostock_data.py --start-date 2024-01-01 --end-date 2024-12-31
```

This script writes the same normalized project files and manifest:

- `data/raw/daily_bars.csv`
- `data/raw/benchmark.csv`
- `data/raw/trading_calendar.csv`
- `data/raw/universe.csv`
- `data/raw/dataset_manifest.json`

By default, the Baostock workflow also downloads a benchmark close series for `000300.SH`, so relative-strength analysis can work out of the box.

Baostock is a better fit for a quick free research start, while Guidebee remains a lightweight public CSV fallback.

For a one-command path that downloads Baostock data, validates it, and runs a backtest:

```powershell
ashare-bootstrap-baostock --start-date 2024-01-01 --end-date 2024-12-31
```

## Data Contract

Official source and runtime dataset contracts now live in `src/ashare_research/contracts/schemas.py`.

The default loader expects `data/raw/daily_bars.csv` with these columns:

```text
date,symbol,open,high,low,close,volume
2024-01-02,000001.SZ,10.10,10.30,10.00,10.20,1000000
```

Use consistently adjusted prices for the research question. For A-share research, add more fields later when needed, such as `amount`, `adj_factor`, `is_suspended`, `limit_up`, `limit_down`, `st_status`, and industry classification.

Optional columns supported by the backtest:

- `amount`: daily turnover value, used by `min_amount` liquidity filtering.
- `adj_factor`: carried for future adjusted-price workflows.
- `is_suspended`: excludes a stock when `exclude_suspended` is enabled.
- `limit_up`: blocks new buys when `block_limit_up_buys` is enabled.
- `limit_down`: blocks sells when `block_limit_down_sells` is enabled.
- `tradable`: excludes rows marked non-tradable.
- `st_status`: excludes ST rows when `exclude_st` is enabled.
- `industry` or `sector`: optional group labels used for exposure reporting.

## Price Adjustment

The loader supports real price adjustment when `adj_factor` is available in `daily_bars.csv` or supplied through an external factor file.

```yaml
data:
  daily_bar_path: data/raw/daily_bars.csv
  adjustment_factor_path: data/raw/adjustment_factors.csv
  price_adjustment: forward
```

Supported modes:

- `none`: use raw prices.
- `forward`: front-adjusted prices, equivalent to `price * adj_factor / latest_adj_factor` per symbol.
- `backward`: back-adjusted prices, equivalent to `price * adj_factor / first_adj_factor` per symbol.

When adjustment is enabled, original prices are preserved as `raw_open`, `raw_high`, `raw_low`, and `raw_close`.

Guidebee daily CSV files do not include adjustment factors. For adjusted research, supply real `adj_factor` data from a vendor such as Tushare, AKShare-compatible sources, or your own corporate-action pipeline.

The benchmark loader expects `data/raw/benchmark.csv` with at least these columns:

```text
date,symbol,close
2024-01-02,000300.SH,3500.25
```

## Research Workflow

1. Put raw vendor data under `data/raw/`.
2. Validate and normalize it in `src/ashare_research/data/`.
3. Add factors in `src/ashare_research/factors/`.
4. Convert factors into explicit signals in `src/ashare_research/strategies/`.
5. Keep portfolio constraints in `src/ashare_research/risk/`.
6. Use `src/ashare_research/backtest/` to test only assumptions you can explain.
7. Review metrics and CSV reports in `src/ashare_research/analysis/` before adding complexity.

## Report Outputs

The CLI writes CSV files under `reports/example_run/` by default:

- `summary.csv`: total return, annual return, volatility, Sharpe ratio, drawdown, turnover, and benchmark-relative metrics.
- `equity_curve.csv`: daily strategy equity, returns, costs, turnover, and benchmark returns.
  It also includes `is_rebalance_day` so scheduled portfolio updates are visible.
- `drawdowns.csv`: daily peak equity, drawdown depth, and consecutive underwater days.
- `rolling_metrics.csv`: rolling return, volatility, Sharpe, and benchmark-relative diagnostics.
- `monthly_returns.csv`: strategy, benchmark, and excess monthly returns.
- `industry_exposure.csv`: daily grouped exposure by `industry` or `sector` when those columns are available.
- `strategy_attribution.csv`: daily weight-based attribution proxy by source bucket.
- `positions.csv`: daily target weights selected by the strategy.
- `execution_diagnostics.csv`: per-date per-symbol requested versus executed weights and blocking reasons.
- `trade_ledger.csv`: executed trade ledger with approximate notional and direction.

The equity curve also includes `gross_exposure`, `cash_weight`, `commission`, and `slippage` so blocked trades, uninvested capital, and execution drag are visible.

## Backtest Controls

`configs/backtest.yaml` supports these execution controls:

- `exclude_suspended`: remove suspended stocks from selection and execution.
- `exclude_st`: remove ST stocks when `st_status` is present.
- `block_limit_up_buys`: prevent buying stocks marked `limit_up`.
- `block_limit_down_sells`: prevent selling stocks marked `limit_down`.
- `min_amount`: require minimum daily turnover when `amount` is present.
- `slippage_rate`: add slippage cost on turnover.
- `max_volume_participation`: cap one-day trade size using available `amount` or `close * volume`.
- `position_sizing_method`: choose `equal_weight` or `signal_weight`.
- `rebalance_frequency`: choose `daily`, `weekly`, or `monthly`.
- `min_holding_days`: keep a position for at least this many trading days before reducing it.
- `trading_calendar_path`: optional date list used to align portfolio returns.
- `universe_path`: optional daily date/symbol universe snapshot to reduce survivorship bias.

## Important Backtest Assumptions

- Signals are shifted by one row per symbol to avoid same-close look-ahead bias.
- When `max_names` is binding, the scaffold keeps the strongest positive signals first.
- `signal_weight` sizing uses the strongest selected signals to allocate larger target weights.
- `weekly` and `monthly` rebalancing keep prior target weights between scheduled rebalance days.
- `min_holding_days` can delay exits even on scheduled rebalance days.
- The example engine applies target weights at each close and earns next-day close returns.
- Costs include commission, optional slippage on turnover, and stamp tax on sell turnover.
- Benchmark returns are aligned to the same close-to-next-close date convention.
- The scaffold can filter suspensions, ST rows, limit-up buys, limit-down sells, and date-aware universe membership when those fields are available.
- Execution diagnostics are produced from the same backtest path as positions and equity, so report files and dashboard views share one source of truth.
- It still does not solve adjusted prices, corporate actions, or official historical index constituents by itself.

## Parameter Sweep

Legacy moving-average sweep remains available:

```powershell
ashare-run-backtest --config configs/backtest.yaml --output-dir reports/ma_sweep --sweep-fast 5,10,20 --sweep-slow 30,60,120
```

Generic strategy parameter sweeps are also supported:

```powershell
ashare-run-backtest --config configs/relative_strength.yaml --output-dir reports/rs_sweep --sweep-parameter lookback_window=10,20,40 --sweep-parameter min_positive_return=0.0,0.02
```

The sweep command writes both `parameter_sweep.csv` and `parameter_sweep_manifest.json` so results are traceable back to the input config snapshot.

## Contract Change Process

When adding a new shared field or dataset:

1. Update `src/ashare_research/contracts/schemas.py`.
2. Reuse `src/ashare_research/contracts/validation.py` where input validation applies.
3. Wire the field through the unified pipeline instead of a local one-off path.
4. Add or update tests under `tests/`.
5. Update CLI, report exports, or dashboard only after the shared contract is stable.

## Governance

Project governance notes live in [`governance.md`](E:\Code\ashare-research\governance.md).

## Next Milestones

- Replace sample data with real A-share adjusted daily bars.
- Add official China trading calendar and historical index constituents.
- Add richer factor attribution and sector exposure reports.
- Add corporate-action adjusted price pipelines.
