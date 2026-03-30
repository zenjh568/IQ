# IQ Option Professional Trading Bot

A fully automated trading system for the IQ Option platform with multiple AI-style agents, advanced money-management strategies, and a professional live terminal dashboard.

---

## Features

| Category | Details |
|---|---|
| **Agents** | RSI, MACD, Bollinger Bands, Stochastic, Multi-Confirmation |
| **Money management** | Flat, Martingale, Anti-Martingale, Soros, Fibonacci |
| **Risk management** | Daily loss limit, consecutive-loss gate, daily trade limit |
| **Signal filtering** | Majority vote, Weighted, Unanimous, Best |
| **Dashboard** | Rich live terminal UI with real-time updates |
| **Logging** | Full trade log written to `bot.log` |

---

## Project layout

```
bot/
├── main.py                      ← Entry point
├── config.py                    ← Configuration loader
├── agents/
│   ├── base_agent.py            ← Abstract base class
│   ├── rsi_agent.py             ← RSI oscillator agent
│   ├── macd_agent.py            ← MACD crossover agent
│   ├── bollinger_agent.py       ← Bollinger Bands mean-reversion agent
│   ├── stochastic_agent.py      ← Stochastic %K/%D agent
│   └── multi_confirmation_agent.py  ← Consensus agent (RSI+MACD+BB+Stoch+WR)
├── strategies/
│   ├── risk_manager.py          ← Daily limits, consecutive-loss gate
│   ├── money_manager.py         ← Bet-size strategies
│   └── signal_filter.py        ← Agent signal aggregator
├── ui/
│   └── dashboard.py             ← Rich terminal dashboard
└── utils/
    └── indicators.py            ← RSI, MACD, BB, Stochastic, ATR, Williams %R, EMA
iqoptionapi-master/              ← IQ Option Python API (from zip)
requirements.txt
config.json                      ← Created on first run (see below)
bot.log                          ← Auto-generated trade log
```

---

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

The IQ Option API requires no additional installation – it is loaded from `iqoptionapi-master/` automatically.

### 2. Create `config.json`

```bash
python -m bot.config
```

Edit the generated `config.json` and fill in your IQ Option credentials.

Alternatively, set environment variables:

```bash
export IQ_EMAIL="your@email.com"
export IQ_PASSWORD="yourpassword"
export IQ_ACCOUNT_TYPE="PRACTICE"   # or REAL
```

### 3. Run the bot

```bash
python -m bot.main
# or with a custom config:
python -m bot.main --config my_settings.json
```

---

## Configuration reference

```jsonc
{
  // IQ Option credentials
  "email": "you@example.com",
  "password": "secret",
  "account_type": "PRACTICE",       // PRACTICE | REAL

  // Assets to rotate through
  "assets": ["EURUSD", "GBPUSD", "USDJPY"],
  "duration": 1,                    // option expiry in minutes
  "candle_size": 60,                // candle granularity in seconds
  "candle_count": 100,              // historical candles per analysis

  "signal_filter": {
    "mode": "majority",             // majority | unanimous | weighted | best
    "confidence_threshold": 0.62
  },

  "agents": {
    "rsi":       { "enabled": true, "period": 14, "oversold": 30, "overbought": 70 },
    "macd":      { "enabled": true, "fast": 12, "slow": 26, "signal": 9 },
    "bollinger": { "enabled": true, "period": 20, "std_dev": 2.0 },
    "stochastic":{ "enabled": true, "k_period": 14, "d_period": 3 },
    "multi_confirmation": { "enabled": true, "min_confirmations": 3 }
  },

  "money_management": {
    "strategy": "flat",             // flat | martingale | anti_martingale | soros | fibonacci
    "base_bet": 1.0,
    "martingale_max": 4,
    "soros_cycles": 3,
    "max_bet": 50.0
  },

  "risk_management": {
    "max_daily_loss": 30.0,         // stop trading after losing $30 in a day
    "max_consecutive_losses": 5,    // stop after 5 losses in a row
    "daily_trade_limit": 40         // max trades per day
  },

  "loop_interval": 5                // seconds between analysis cycles
}
```

---

## Trading Agents

### RSI Agent
Generates **CALL** when RSI < 30 (oversold) and **PUT** when RSI > 70 (overbought).
Optionally filtered by EMA trend direction.

### MACD Agent
Signals on MACD / signal-line crossovers.  Filters out crosses that go against
extreme RSI readings to avoid chasing exhausted moves.

### Bollinger Bands Agent
Mean-reversion strategy.  Buys when price touches or breaks the lower band
(CALL) and sells at the upper band (PUT).  ATR filter skips low-volatility markets.

### Stochastic Agent
Signals %K / %D crossovers inside the oversold (< 20) or overbought (> 80) zone.

### Multi-Confirmation Agent
Aggregates RSI, MACD, Bollinger Bands, Stochastic, Williams %R and EMA trend.
Only fires when a configurable number of indicators agree – the highest-quality
signal but the rarest.

---

## Money-Management Strategies

| Strategy | Description |
|---|---|
| **Flat** | Fixed bet every trade |
| **Martingale** | Double bet after each loss; reset after win |
| **Anti-Martingale** | Double bet after each win; reset after loss |
| **Soros** | Reinvest accumulated winnings for N cycles, then bank profits |
| **Fibonacci** | Follow Fibonacci sequence on losses; step back 2 on wins |

> ⚠️ Martingale-type strategies amplify losses.  Always test on **PRACTICE** first.

---

## Risk Management

The `RiskManager` blocks new trades when any of the following conditions is met:

- Daily loss exceeds `max_daily_loss`
- Consecutive losses reach `max_consecutive_losses`
- Daily trade count reaches `daily_trade_limit`

---

## Disclaimer

This software is provided for **educational purposes only**.
Trading binary options involves significant financial risk.
**Never trade with money you cannot afford to lose.**
Past performance of any strategy does not guarantee future results.
