# t212-signal-lab

Research lab local para testar sinais e estrategias swing/rotation com dados Yahoo Finance, custos configuraveis e comparacao contra benchmarks.

## Funcionalidades

- Indicadores: SMA, RSI, ATR, momentum, volatilidade, distancia ao 52W high.
- Regime de mercado: `RISK_ON`, `NEUTRAL`, `RISK_OFF`, `HIGH_VOLATILITY`.
- Backtest sem look-ahead: sinais usam dados ate `as_of_date`; entradas so no open seguinte.
- Entry zone enforcement: rejeita entradas fora da zona.
- Position sizing por risco ate ao stop e limites de exposicao.
- Custos configuraveis: spread/slippage e conversao cambial.
- Engines:
  - `SIGNAL_ENGINE`
  - `ETF_ROTATION_ENGINE`
  - `ETF_ROTATION_TOP_N_ENGINE`
  - `INDEX_TREND_BASELINE_ENGINE`
  - `RELATIVE_STRENGTH_STOCK_ENGINE`
  - `RELATIVE_STRENGTH_STOCK_ENGINE_V2`
  - `BREAKOUT_52W_ENGINE`
  - `PULLBACK_TREND_ENGINE`
  - `LOW_VOL_DEFENSIVE_ENGINE`
  - `MEAN_REVERSION_ETF_ENGINE`
  - `PAIR_RELATIVE_RATIO_ENGINE`
- Parameter sweep, optimizer e walk-forward.
- Dashboard Streamlit retro terminal.
- Diagnosticos por ticker, regime, ano, score bucket, exit reason e rejection reason.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

O projeto corre em `DRY_RUN=True` por defeito. Nao coloca ordens reais.

## Dashboard

```bash
python -m streamlit run dashboard\app.py
```

Abrir:

```text
http://localhost:8501
```

No dashboard podes escolher:

- `strategy_engine`
- universo `DEFAULT` ou `ETF_ONLY`
- `min_score`
- risk filter para backtest
- custos
- adjusted data
- benchmark
- sweep
- walk-forward

## CLI

Backtest basico:

```bash
python main.py backtest --start 2015-01-01 --end 2025-12-31
```

Backtest com parametros:

```bash
python main.py backtest --start 2015-01-01 --end 2025-12-31 --strategy-engine ETF_ROTATION_ENGINE --min-score 0.75 --initial-capital 10000 --max-positions-total 5 --max-position-pct 0.20 --max-total-exposure 0.30 --spread-slippage-pct 0.001 --currency-conversion-pct 0 --benchmark-ticker SPY
```

## Backtest Rules

- Se `open_price < entry_min`: rejeita `ENTRY_NOT_REACHED`.
- Se `open_price > entry_max`: rejeita `ENTRY_GAP_ABOVE_ZONE`.
- Se estiver dentro da entry zone: executa com custos.
- Position sizing:
  - `risk_per_share = entry_price - invalidation`
  - `max_risk_amount = equity * MAX_RISK_PER_TRADE`
  - `shares_by_risk = max_risk_amount / risk_per_share`
  - `shares_by_exposure = max_position_value / entry_price`
  - `shares = min(shares_by_risk, shares_by_exposure)`
- Rejeita se `invalidation >= entry_price`.
- Nunca abre nova posicao no mesmo ticker se ja houver uma aberta.
- Respeita `MAX_EXPOSURE_PER_TICKER` e `MAX_TOTAL_EXPOSURE`.
- Se `equity <= 0`, o backtest para.

## Walk-Forward

Segmentos:

- train: 2015-2020
- validation: 2021-2022
- test: 2023-2025

Runs sao guardados separadamente em SQLite e marcados com `overfit_risk` quando ha bom desempenho in-sample e falha fora da amostra.

## Optimizer

No dashboard, usa a seccao `OPTIMIZER` para:

- escolher engine, universo, benchmark, adjusted data e periodo;
- definir intervalos `start/end/step` e listas de valores;
- fazer `PREVIEW COMBINATIONS` antes de correr;
- correr `single_period` ou `walk_forward`;
- filtrar por minimo de trades, drawdown maximo, bate SPY e sem overfit risk;
- exportar resultados para CSV.

Tambem podes chamar por Python:

```python
from strategy.optimizer import run_optimization

result = run_optimization(
    "2015-01-01",
    "2025-12-31",
    {
        "min_score": {"start": 0.70, "end": 0.90, "step": 0.05},
        "max_holding_days": {"values": [10, 30, 60]},
        "top_n": {"values": [1, 2, 3]},
        "rebalance_frequency": {"values": ["weekly", "monthly"]},
    },
    strategy_engine="ETF_ROTATION_TOP_N_ENGINE",
)
```

O optimizer bloqueia grids com mais de 500 combinacoes, salvo `confirm_large_grid=True`.

### Robust score

Formula usada:

```text
robust_score =
  0.30 * normalized_cagr
+ 0.25 * normalized_sharpe
+ 0.20 * normalized_calmar
+ 0.15 * normalized_alpha_vs_spy
- 0.10 * drawdown_penalty
- 0.10 * turnover_penalty
```

Isto nao e uma verdade estatistica universal. E um ranking explicito para evitar escolher apenas o maior retorno bruto.

### Overfit risk

No modo walk-forward, uma combinacao fica marcada como `overfit_risk=True` se:

- train Sharpe > 0.8 e test Sharpe < 0.3;
- ou train CAGR > 10% e test CAGR < 0%;
- ou bate SPY no train mas perde para SPY no test por mais de 20 pontos percentuais;
- ou test max drawdown < -25%;
- ou test tem menos de 20 trades.

## Limitacoes

- Survivorship bias: a watchlist atual contem tickers atuais; resultados historicos podem estar inflacionados. Usa `ETF_ONLY` para reduzir, mas nao eliminar, este problema.
- Yahoo Finance: dados podem ter erros, ajustes retroativos, missing bars e diferencas entre `Close` e `Adj Close`.
- Dividend handling: `--use-adjusted-data` aproxima retorno total via dados ajustados, mas nao e um benchmark total-return institucional.
- Costs: custos sao modelos simples por lado; nao incluem market impact, borrow, taxas especificas ou impostos.
- Slippage intradiario: OHLC nao revela sequencia real entre stop e target; o backtester usa abordagem conservadora.
- No financial advice: isto e research automatizado, nao aconselhamento financeiro personalizado.
- Overfitting: muitas combinacoes aumentam a probabilidade de encontrar parametros bons por acaso. Prefere resultados robustos fora da amostra.

## Testes

```bash
python -m pytest -q
```
