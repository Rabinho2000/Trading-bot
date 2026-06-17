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
  - `RELATIVE_STRENGTH_STOCK_ENGINE`
- Parameter sweep e walk-forward.
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

## Limitacoes

- Survivorship bias: a watchlist atual contem tickers atuais; resultados historicos podem estar inflacionados. Usa `ETF_ONLY` para reduzir, mas nao eliminar, este problema.
- Yahoo Finance: dados podem ter erros, ajustes retroativos, missing bars e diferencas entre `Close` e `Adj Close`.
- Dividend handling: `--use-adjusted-data` aproxima retorno total via dados ajustados, mas nao e um benchmark total-return institucional.
- Costs: custos sao modelos simples por lado; nao incluem market impact, borrow, taxas especificas ou impostos.
- Slippage intradiario: OHLC nao revela sequencia real entre stop e target; o backtester usa abordagem conservadora.
- No financial advice: isto e research automatizado, nao aconselhamento financeiro personalizado.

## Testes

```bash
python -m pytest -q
```
