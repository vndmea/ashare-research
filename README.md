# A-share Research

Research-first Python scaffold for validating A-share daily quantitative strategy logic.

This project intentionally starts with a small and auditable workflow: load daily bars, generate signals, apply simple portfolio construction, run a close-to-close backtest, compare against a benchmark, and export research reports.

## Scope

- Market: China A-shares.
- Frequency: daily bars.
- Purpose: research and strategy validation, not live trading.
- First strategy: long-only moving-average crossover.
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
ashare-run-backtest --config configs/backtest.yaml
```

## Dashboard

```powershell
cd E:\Code\ashare-research
streamlit run dashboard.py
```

The dashboard can also run the example backtest from the sidebar and then render the generated reports.

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

The source is useful for research, but you should still verify adjusted-price handling and corporate-action treatment before trusting any live strategy work.

## Data Contract

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
- `positions.csv`: daily target weights selected by the strategy.

The equity curve also includes `gross_exposure` and `cash_weight` so blocked trades and uninvested capital are visible.

## Backtest Controls

`configs/backtest.yaml` supports these execution controls:

- `exclude_suspended`: remove suspended stocks from selection and execution.
- `exclude_st`: remove ST stocks when `st_status` is present.
- `block_limit_up_buys`: prevent buying stocks marked `limit_up`.
- `block_limit_down_sells`: prevent selling stocks marked `limit_down`.
- `min_amount`: require minimum daily turnover when `amount` is present.
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
- Costs include commission on turnover and stamp tax on sell turnover.
- Benchmark returns are aligned to the same close-to-next-close date convention.
- The scaffold can filter suspensions, ST rows, limit-up buys, limit-down sells, and date-aware universe membership when those fields are available.
- It still does not solve adjusted prices, corporate actions, or official historical index constituents by itself.

## Next Milestones

- Replace sample data with real A-share adjusted daily bars.
- Add official China trading calendar and historical index constituents.
- Add richer factor attribution and sector exposure reports.
- Add corporate-action adjusted price pipelines.
