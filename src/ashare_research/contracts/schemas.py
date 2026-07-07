from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchemaField:
    name: str
    dtype: str
    required: bool
    description: str


@dataclass(frozen=True)
class DatasetSchema:
    name: str
    description: str
    fields: tuple[SchemaField, ...]
    primary_keys: tuple[str, ...] = ()
    producer_modules: tuple[str, ...] = ()
    consumer_modules: tuple[str, ...] = ()

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields)

    @property
    def required_fields(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields if field.required)

    @property
    def optional_fields(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields if not field.required)

    @property
    def required_field_set(self) -> set[str]:
        return set(self.required_fields)

    @property
    def optional_field_set(self) -> set[str]:
        return set(self.optional_fields)


def _field(name: str, dtype: str, required: bool, description: str) -> SchemaField:
    return SchemaField(
        name=name,
        dtype=dtype,
        required=required,
        description=description,
    )


DAILY_BARS_SOURCE_SCHEMA = DatasetSchema(
    name="daily_bars_csv",
    description="Normalized A-share daily OHLCV source data loaded from CSV.",
    primary_keys=("date", "symbol"),
    producer_modules=("external_vendor", "scripts/create_sample_data.py", "scripts/download_guidebee_data.py"),
    consumer_modules=("ashare_research.data.daily_bars", "ashare_research.pipeline.run"),
    fields=(
        _field("date", "datetime64[ns]", True, "Trading date for the symbol row."),
        _field("symbol", "string", True, "Normalized A-share ticker such as 600000.SH."),
        _field("open", "float", True, "Session open price."),
        _field("high", "float", True, "Session high price."),
        _field("low", "float", True, "Session low price."),
        _field("close", "float", True, "Session close price used by the daily backtest."),
        _field("volume", "float", True, "Daily traded volume."),
        _field("amount", "float", False, "Daily traded amount used for liquidity filtering."),
        _field("adj_factor", "float", False, "Corporate-action adjustment factor for price adjustment."),
        _field("is_suspended", "bool", False, "Whether the symbol is suspended on the date."),
        _field("limit_up", "bool", False, "Whether the symbol is at limit-up and blocks new buys."),
        _field("limit_down", "bool", False, "Whether the symbol is at limit-down and blocks sells."),
        _field("tradable", "bool", False, "Explicit tradability flag when provided by the data source."),
        _field("st_status", "string", False, "ST or special treatment state used for filtering."),
        _field("industry", "string", False, "Industry classification label."),
        _field("sector", "string", False, "Sector or board classification label."),
    ),
)

BENCHMARK_SOURCE_SCHEMA = DatasetSchema(
    name="benchmark_csv",
    description="Benchmark close series used to derive close-to-close benchmark returns.",
    primary_keys=("date",),
    producer_modules=("external_vendor", "scripts/create_sample_data.py"),
    consumer_modules=("ashare_research.data.benchmarks", "ashare_research.pipeline.run"),
    fields=(
        _field("date", "datetime64[ns]", True, "Benchmark trading date."),
        _field("close", "float", True, "Benchmark close used to derive next-day return."),
        _field("symbol", "string", False, "Optional benchmark symbol such as 000300.SH."),
    ),
)

TRADING_CALENDAR_SOURCE_SCHEMA = DatasetSchema(
    name="trading_calendar_csv",
    description="Explicit list of valid trading dates.",
    primary_keys=("date",),
    producer_modules=("external_vendor", "scripts/download_guidebee_data.py"),
    consumer_modules=("ashare_research.data.calendar", "ashare_research.pipeline.run"),
    fields=(
        _field("date", "datetime64[ns]", True, "Trading session date."),
    ),
)

UNIVERSE_SOURCE_SCHEMA = DatasetSchema(
    name="universe_csv",
    description="Date-aware research universe membership snapshot.",
    primary_keys=("date", "symbol"),
    producer_modules=("external_vendor", "scripts/download_guidebee_data.py"),
    consumer_modules=("ashare_research.data.universe", "ashare_research.pipeline.run"),
    fields=(
        _field("date", "datetime64[ns]", True, "Trading date."),
        _field("symbol", "string", True, "Eligible symbol on the date."),
    ),
)

SOURCE_DATASET_SCHEMAS: dict[str, DatasetSchema] = {
    schema.name: schema
    for schema in (
        DAILY_BARS_SOURCE_SCHEMA,
        BENCHMARK_SOURCE_SCHEMA,
        TRADING_CALENDAR_SOURCE_SCHEMA,
        UNIVERSE_SOURCE_SCHEMA,
    )
}

BARS_SCHEMA = DatasetSchema(
    name="bars",
    description="Validated and optionally adjusted daily bar frame used by the research pipeline.",
    primary_keys=("date", "symbol"),
    producer_modules=("ashare_research.data.daily_bars",),
    consumer_modules=(
        "ashare_research.strategies",
        "ashare_research.backtest",
        "ashare_research.analysis",
        "ashare_research.pipeline.run",
    ),
    fields=DAILY_BARS_SOURCE_SCHEMA.fields
    + (
        _field("raw_open", "float", False, "Original open price preserved when price adjustment is enabled."),
        _field("raw_high", "float", False, "Original high price preserved when price adjustment is enabled."),
        _field("raw_low", "float", False, "Original low price preserved when price adjustment is enabled."),
        _field("raw_close", "float", False, "Original close price preserved when price adjustment is enabled."),
    ),
)

BENCHMARK_RETURNS_SCHEMA = DatasetSchema(
    name="benchmark_returns",
    description="Derived close-to-next-close benchmark return series aligned by date.",
    primary_keys=("date",),
    producer_modules=("ashare_research.data.benchmarks",),
    consumer_modules=("ashare_research.pipeline.run", "ashare_research.backtest", "ashare_research.analysis"),
    fields=(
        _field("date", "datetime64[ns]", True, "Benchmark return date aligned to strategy return timing."),
        _field("benchmark_return", "float", True, "Close-to-next-close benchmark return."),
    ),
)

SIGNALS_SCHEMA = DatasetSchema(
    name="signals",
    description="Daily strategy signal frame keyed by date and symbol.",
    primary_keys=("date", "symbol"),
    producer_modules=("ashare_research.strategies",),
    consumer_modules=("ashare_research.risk.position_sizing", "ashare_research.backtest.engine"),
    fields=(
        _field("date", "datetime64[ns]", True, "Signal date."),
        _field("symbol", "string", True, "Symbol receiving the signal."),
        _field("signal", "float", True, "Primary selection signal; positive values mean long eligibility."),
        _field(
            "signal_strength",
            "float",
            False,
            "Optional strength used to rank or size positions when available.",
        ),
    ),
)

POSITIONS_SCHEMA = DatasetSchema(
    name="positions",
    description="Daily target portfolio weights after scheduling and trade constraints.",
    primary_keys=("date", "symbol"),
    producer_modules=("ashare_research.backtest.engine", "ashare_research.risk.tradeability"),
    consumer_modules=("ashare_research.backtest.accounting", "ashare_research.analysis"),
    fields=(
        _field("date", "datetime64[ns]", True, "Holding date."),
        _field("symbol", "string", True, "Held symbol."),
        _field("weight", "float", True, "End-of-day target portfolio weight for the symbol."),
    ),
)

EQUITY_CURVE_SCHEMA = DatasetSchema(
    name="equity_curve",
    description="Daily portfolio return and equity path generated by the backtest engine.",
    primary_keys=("date",),
    producer_modules=("ashare_research.backtest.accounting", "ashare_research.analysis.reports"),
    consumer_modules=("ashare_research.analysis.metrics", "ashare_research.analysis.reports", "dashboard.py"),
    fields=(
        _field("date", "datetime64[ns]", True, "Trading date."),
        _field("gross_return", "float", True, "Pre-cost portfolio return for the date."),
        _field("turnover", "float", True, "Total one-day turnover implied by weight changes."),
        _field("sell_turnover", "float", True, "One-day sell turnover used to compute stamp tax."),
        _field("gross_exposure", "float", True, "Sum of positive portfolio weights on the date."),
        _field("cash_weight", "float", True, "Residual cash weight after constrained portfolio sizing."),
        _field("commission", "float", True, "Commission cost deducted from return."),
        _field("slippage", "float", True, "Slippage cost deducted from return."),
        _field("cost", "float", True, "Total trading cost excluding tax, including commission and slippage."),
        _field("tax", "float", True, "Stamp tax deducted from return."),
        _field("net_return", "float", True, "Post-cost close-to-close daily portfolio return."),
        _field("equity", "float", True, "Portfolio equity after compounding net returns."),
        _field("is_rebalance_day", "float", True, "1.0 when weights changed from prior day, else 0.0."),
        _field("benchmark_return", "float", False, "Optional benchmark return merged into report exports."),
    ),
)

EXECUTION_DIAGNOSTICS_SCHEMA = DatasetSchema(
    name="execution_diagnostics",
    description="Per-date per-symbol execution diagnostics capturing requested and executed weights.",
    primary_keys=("date", "symbol"),
    producer_modules=("ashare_research.risk.tradeability", "ashare_research.backtest.engine"),
    consumer_modules=("ashare_research.analysis.reports", "dashboard.py"),
    fields=(
        _field("date", "datetime64[ns]", True, "Trading date."),
        _field("symbol", "string", True, "Symbol evaluated for execution."),
        _field("previous_weight", "float", True, "Portfolio weight before the date's execution step."),
        _field("target_weight", "float", True, "Desired target weight before execution constraints."),
        _field("executed_weight", "float", True, "Final executed weight after execution constraints."),
        _field("desired_trade_weight", "float", True, "Requested weight change before constraints."),
        _field("executed_trade_weight", "float", True, "Actual weight change after constraints."),
        _field("available", "bool", True, "Whether a bar exists for the symbol/date pair."),
        _field("tradable", "bool", True, "Whether the symbol was tradable after base eligibility checks."),
        _field("limit_up", "bool", True, "Whether the symbol was marked limit-up on the date."),
        _field("limit_down", "bool", True, "Whether the symbol was marked limit-down on the date."),
        _field("liquidity_amount", "float", True, "Liquidity notional used for participation checks."),
        _field("max_trade_weight", "float", True, "Maximum trade weight allowed by participation constraints."),
        _field("blocked_reason", "string", True, "Pipe-delimited execution reason diagnostics."),
        _field("is_blocked", "bool", True, "Whether any execution constraint altered or blocked the request."),
    ),
)

TRADE_LEDGER_SCHEMA = DatasetSchema(
    name="trade_ledger",
    description="Daily executed trade ledger derived from execution diagnostics and portfolio equity.",
    primary_keys=("date", "symbol"),
    producer_modules=("ashare_research.backtest.accounting", "ashare_research.backtest.engine"),
    consumer_modules=("ashare_research.analysis.reports", "dashboard.py"),
    fields=(
        _field("date", "datetime64[ns]", True, "Trading date."),
        _field("symbol", "string", True, "Executed symbol."),
        _field("side", "string", True, "Trade side: buy or sell."),
        _field("previous_weight", "float", True, "Portfolio weight before execution."),
        _field("target_weight", "float", True, "Requested target weight before constraints."),
        _field("executed_weight", "float", True, "Executed ending weight."),
        _field("weight_delta", "float", True, "Executed weight change for the trade."),
        _field("reference_equity", "float", True, "Equity reference used to approximate trade notional."),
        _field("trade_notional", "float", True, "Approximate executed trade notional."),
        _field("blocked_reason", "string", True, "Execution reason context carried from diagnostics."),
    ),
)

POSITION_CONTRIBUTION_SCHEMA = DatasetSchema(
    name="position_contribution",
    description="Daily per-position contribution report using close-to-next-close returns.",
    primary_keys=("date", "symbol"),
    producer_modules=("ashare_research.analysis.reports",),
    consumer_modules=("dashboard.py",),
    fields=(
        _field("date", "datetime64[ns]", True, "Trading date."),
        _field("symbol", "string", True, "Held symbol."),
        _field("weight", "float", True, "Position weight used for the date."),
        _field("return", "float", True, "Close-to-next-close symbol return."),
        _field("contribution", "float", True, "Weight multiplied by symbol return."),
        _field("group_name", "string", True, "Industry or sector grouping for the symbol."),
    ),
)

SYMBOL_TECHNICAL_ANALYSIS_SCHEMA = DatasetSchema(
    name="symbol_technical_analysis",
    description="Latest single-stock technical analysis snapshot with score-based Chinese decision labels.",
    primary_keys=("symbol",),
    producer_modules=("ashare_research.analysis.technical", "ashare_research.analysis.reports"),
    consumer_modules=("ashare_research.cli", "dashboard.py"),
    fields=(
        _field("date", "string", True, "Latest analysis date in YYYY-MM-DD format."),
        _field("symbol", "string", True, "Normalized project symbol such as 603986.SH."),
        _field("latest_close", "float", True, "Latest close used by the analysis snapshot."),
        _field("return_20d", "float", False, "Trailing short-window return."),
        _field("return_60d", "float", False, "Trailing medium-window return."),
        _field("return_120d", "float", False, "Trailing long-window return."),
        _field("return_250d", "float", False, "Trailing trend-window return."),
        _field("max_drawdown", "float", False, "Max drawdown over the loaded history range."),
        _field("close_vs_ma20", "float", False, "Latest close relative to short moving average."),
        _field("close_vs_ma60", "float", False, "Latest close relative to medium moving average."),
        _field("close_vs_ma120", "float", False, "Latest close relative to long moving average."),
        _field("close_vs_ma250", "float", False, "Latest close relative to trend moving average."),
        _field("vol20_vs_120", "float", False, "Recent average volume relative to baseline volume."),
        _field("amt20_vs_120", "float", False, "Recent average turnover amount relative to baseline amount."),
        _field("relative_strength_250d", "float", False, "Trailing relative strength versus benchmark over the trend window."),
        _field("latest_from_peak_20d", "float", False, "Latest close relative to recent peak over the peak lookback window."),
        _field("trend_score", "int", True, "Trend sub-score from moving averages and trailing returns."),
        _field("volume_score", "int", True, "Volume confirmation sub-score."),
        _field("relative_strength_score", "int", True, "Relative strength confirmation sub-score."),
        _field("risk_penalty", "int", True, "Risk deductions from pullback and drawdown conditions."),
        _field("total_score", "int", True, "Aggregate score used for final decision."),
        _field("decision", "string", True, "Final score-based decision: 偏买入, 偏持有, or 偏卖出."),
        _field("decision_reason", "string", True, "Chinese semicolon-delimited explanation for the decision."),
    ),
)

TURNOVER_BREAKDOWN_SCHEMA = DatasetSchema(
    name="turnover_breakdown",
    description="Daily turnover and cost breakdown derived from the equity curve.",
    primary_keys=("date",),
    producer_modules=("ashare_research.analysis.reports",),
    consumer_modules=("dashboard.py",),
    fields=(
        _field("date", "datetime64[ns]", True, "Trading date."),
        _field("turnover", "float", True, "Total one-day turnover."),
        _field("buy_turnover", "float", True, "One-day buy turnover."),
        _field("sell_turnover", "float", True, "One-day sell turnover."),
        _field("commission", "float", True, "Commission cost for the date."),
        _field("slippage", "float", True, "Slippage cost for the date."),
        _field("tax", "float", True, "Stamp tax for the date."),
        _field("total_cost", "float", True, "Total execution cost for the date."),
    ),
)

DRAWDOWNS_SCHEMA = DatasetSchema(
    name="drawdowns",
    description="Daily drawdown diagnostics derived from the equity curve.",
    primary_keys=("date",),
    producer_modules=("ashare_research.analysis.reports",),
    consumer_modules=("dashboard.py",),
    fields=(
        _field("date", "datetime64[ns]", True, "Trading date."),
        _field("equity", "float", True, "Portfolio equity."),
        _field("peak_equity", "float", True, "Running peak equity up to the date."),
        _field("drawdown", "float", True, "Current drawdown relative to running peak."),
        _field("is_new_high", "bool", True, "Whether the date establishes a new peak."),
        _field("underwater_days", "int", True, "Consecutive days spent below the running peak."),
    ),
)

ROLLING_METRICS_SCHEMA = DatasetSchema(
    name="rolling_metrics",
    description="Rolling strategy diagnostics emitted by the default report writer.",
    primary_keys=("date",),
    producer_modules=("ashare_research.analysis.reports",),
    consumer_modules=("dashboard.py",),
    fields=(
        _field("date", "datetime64[ns]", True, "Trading date."),
        _field("rolling_20d_return", "float", False, "20-day compounded strategy return."),
        _field("rolling_20d_volatility", "float", False, "20-day annualized volatility."),
        _field("rolling_20d_sharpe", "float", False, "20-day rolling Sharpe ratio."),
        _field("rolling_20d_excess_return", "float", False, "20-day strategy return minus benchmark return."),
        _field("rolling_60d_return", "float", False, "60-day compounded strategy return."),
        _field("rolling_60d_volatility", "float", False, "60-day annualized volatility."),
        _field("rolling_60d_sharpe", "float", False, "60-day rolling Sharpe ratio."),
        _field("rolling_60d_excess_return", "float", False, "60-day strategy return minus benchmark return."),
    ),
)

MONTHLY_RETURNS_SCHEMA = DatasetSchema(
    name="monthly_returns",
    description="Monthly aggregated strategy and benchmark return table.",
    primary_keys=("month",),
    producer_modules=("ashare_research.analysis.reports",),
    consumer_modules=("dashboard.py",),
    fields=(
        _field("month", "string", True, "Calendar month in YYYY-MM format."),
        _field("strategy_return", "float", True, "Compounded strategy return for the month."),
        _field("benchmark_return", "float", False, "Compounded benchmark return for the month."),
        _field("excess_return", "float", False, "Monthly strategy excess return versus the benchmark."),
    ),
)

INDUSTRY_EXPOSURE_SCHEMA = DatasetSchema(
    name="industry_exposure",
    description="Daily grouped exposure by industry or sector label.",
    primary_keys=("date", "group_name"),
    producer_modules=("ashare_research.analysis.reports",),
    consumer_modules=("dashboard.py",),
    fields=(
        _field("date", "datetime64[ns]", True, "Trading date."),
        _field("group_name", "string", True, "Industry or sector label; Unclassified when missing."),
        _field("exposure", "float", True, "Total portfolio weight assigned to the group."),
    ),
)

STRATEGY_ATTRIBUTION_SCHEMA = DatasetSchema(
    name="strategy_attribution",
    description=(
        "Daily attribution-style diagnostic keyed by source. "
        "Current contribution values are weight-based exposure proxies, not realized PnL attribution."
    ),
    primary_keys=("date", "source"),
    producer_modules=("ashare_research.analysis.attribution",),
    consumer_modules=("dashboard.py",),
    fields=(
        _field("date", "datetime64[ns]", True, "Trading date."),
        _field("source", "string", True, "Industry, sector, or cash bucket source label."),
        _field(
            "contribution",
            "float",
            True,
            "Current weight-based contribution proxy for the source; not realized return contribution.",
        ),
    ),
)

RUNTIME_DATASET_SCHEMAS: dict[str, DatasetSchema] = {
    schema.name: schema
    for schema in (
        BARS_SCHEMA,
        BENCHMARK_RETURNS_SCHEMA,
        SIGNALS_SCHEMA,
        POSITIONS_SCHEMA,
        EQUITY_CURVE_SCHEMA,
        DRAWDOWNS_SCHEMA,
        ROLLING_METRICS_SCHEMA,
        MONTHLY_RETURNS_SCHEMA,
        INDUSTRY_EXPOSURE_SCHEMA,
        STRATEGY_ATTRIBUTION_SCHEMA,
        EXECUTION_DIAGNOSTICS_SCHEMA,
        TRADE_LEDGER_SCHEMA,
        POSITION_CONTRIBUTION_SCHEMA,
        SYMBOL_TECHNICAL_ANALYSIS_SCHEMA,
        TURNOVER_BREAKDOWN_SCHEMA,
    )
}

ALL_DATASET_SCHEMAS: dict[str, DatasetSchema] = {
    **SOURCE_DATASET_SCHEMAS,
    **RUNTIME_DATASET_SCHEMAS,
}


def get_dataset_schema(name: str) -> DatasetSchema:
    if name not in ALL_DATASET_SCHEMAS:
        raise KeyError(f"Unknown dataset schema: {name}")
    return ALL_DATASET_SCHEMAS[name]
