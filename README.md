# t212-signal-lab

MVP de um sistema de sinais para ações/ETFs compatíveis com Trading 212, focado em swing trading e ETF/sector rotation.

## 🚀 Funcionalidades
- **Análise Técnica:** SMA, RSI, ATR, Performance, Volatilidade.
- **Regime de Mercado:** Classificação dinâmica (RISK_ON, RISK_OFF, NEUTRAL, HIGH_VOLATILITY).
- **Geração de Sinais:** BUY / WATCH / SKIP baseado em regras quantitativas.
- **AI Analyst:** Explicação de sinais usando OpenAI (com fallback local).
- **Risk Management:** Position sizing automático (1% risco por trade).
- **Persistência:** Base SQLite para histórico de sinais e runs.
- **Dashboard:** Visualização em Streamlit.
- **Alertas:** Notificações diárias via Telegram.

## 🛠️ Setup

1. **Instalar dependências:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configurar ambiente:**
   Crie um ficheiro `.env` baseado no `.env.example`:
   ```bash
   cp .env.example .env
   ```
   Edite o `.env` com as suas chaves da OpenAI e Telegram (opcional).

3. **Segurança:**
   O sistema corre em modo `DRY_RUN=True` por defeito. Não coloca ordens reais.

## 📈 Como usar

### 1. Correr análise diária
Gera sinais e guarda na base de dados:
```bash
python main.py run
```

### 2. Ver últimos sinais via CLI
```bash
python main.py signals
```

### 3. Abrir Dashboard Streamlit
```bash
streamlit run dashboard/app.py
```

### 4. Correr Testes
```bash
pytest
```

## 🏗️ Arquitetura
- `data/`: Módulos de data fetching (yfinance).
- `strategy/`: Lógica de indicadores, regime e engine de sinais.
- `ai/`: Integração com LLMs para análise qualitativa.
- `risk/`: Validação de risco e dimensionamento de posição.
- `db/`: Camada de dados SQLAlchemy.
- `alerts/`: Notificações externas.
- `dashboard/`: Frontend Streamlit.

## ⚠️ Aviso Legal
Isto é research automatizado, não aconselhamento financeiro personalizado. O uso deste software é de inteira responsabilidade do utilizador.
