# 🚀 Sistema de Trading em Produção

Sistema de sinais de compra/venda em tempo real com conviction scoring (technical + news + regime).

## 📊 Performance Validada

**Backtest (Fev 2025 - Fev 2026)**:
- Sistema SEM news: **+51.09%**
- IBOV: **+48.02%**
- **Ganho vs IBOV: +3.07%**

Sistema bate IBOV mesmo sem notícias. Com notícias em tempo real, a performance tende a melhorar.

---

## 🏃 Como Usar

### 1. Análise de Todos os Tickers (Recomendado)

```bash
cd ~/stock-signals
python3 production_runner.py
```

**Output**:
- Análise de 18 tickers do IBOV
- Sinais: 🟢 BUY / 🔴 SELL / ⚪ HOLD
- Conviction score (0.0 - 1.0)
- Tamanho de posição recomendado

**Tempo de execução**: ~5-10 minutos (busca notícias em tempo real)

---

### 2. Análise de Ticker Específico

```bash
python3 production_runner.py --ticker PETR4.SA
```

**Use quando**: Quer verificar rapidamente um ativo específico.

---

### 3. Ajustar Janela de Notícias

```bash
python3 production_runner.py --days 3
```

**Janela de notícias**:
- `--days 3`: Últimos 3 dias (mais rápido, foco em eventos recentes)
- `--days 7`: Últimos 7 dias (default, balanceado)
- `--days 14`: Últimos 14 dias (mais contexto, mais lento)

---

## 📊 Interpretando os Sinais

### Conviction Score

O sistema calcula um **conviction score** de -1.0 a +1.0:

| Score | Nível | Ação |
|-------|-------|------|
| ≥ 0.80 | High | 🟢 BUY (70% do capital) |
| 0.60 - 0.80 | Medium | 🟢 BUY (50% do capital) |
| 0.40 - 0.60 | Low | 🟢 BUY (25% do capital) |
| -0.40 a +0.40 | Neutral | ⚪ HOLD (não fazer nada) |
| ≤ -0.40 | Bearish | 🔴 SELL (fechar posição) |

### Componentes do Conviction

O score é calculado a partir de 3 componentes:

1. **Technical (40%)**: Trend + Momentum
   - TrendDetectorV2 (dual timeframe: 50-day macro + 20-day micro)
   - MomentumDetector (RSI, MACD, volume)

2. **News (30%)**: Sentiment de notícias recentes
   - Google News RSS (últimos N dias)
   - FinBERT sentiment analysis (local, sem API)

3. **Regime (30%)**: Contexto de mercado
   - Detecta uptrend/downtrend/neutral
   - Usado como tie-breaker

---

## 🔄 Uso Diário Recomendado

### Rotina Matinal (antes do mercado abrir)

```bash
# 1. Executar análise completa
cd ~/stock-signals
python3 production_runner.py > daily_signals_$(date +%Y-%m-%d).txt

# 2. Revisar sinais
cat daily_signals_$(date +%Y-%m-%d).txt
```

**O que fazer com os sinais**:

1. **🟢 BUY signals**:
   - Verificar conviction score
   - High conviction (≥0.80)? → Alocar 70% do capital
   - Medium (0.60-0.80)? → Alocar 50%
   - Low (0.40-0.60)? → Alocar 25%

2. **🔴 SELL signals**:
   - Fechar posições existentes
   - Não entrar em novas posições

3. **⚪ HOLD signals**:
   - Manter posições existentes
   - Não fazer nada

---

## 🤖 Automação (Opcional)

### Opção 1: Cron Job (Executar todo dia útil às 8:00)

```bash
# Adicionar ao crontab
crontab -e

# Adicionar linha (substitua /path/to/ pelo caminho real):
0 8 * * 1-5 cd /path/to/stock-signals && python3 production_runner.py > ~/daily_signals_$(date +\%Y-\%m-\%d).txt 2>&1
```

### Opção 2: OpenClaw Cron (Enviar sinais via Telegram)

```python
# Usar OpenClaw para enviar sinais automaticamente
# (já configurado para Bruno via TARS)
```

---

## ⚠️ Avisos Importantes

### 1. **Notícias em Tempo Real**

O sistema usa **Google News RSS** (gratuito, sem limite):
- ✅ Notícias dos últimos 30 dias
- ✅ Sem custo de API
- ✅ Sentiment local via FinBERT
- ⚠️ Requer internet

### 2. **Dados de Mercado**

O sistema usa **yfinance** (gratuito):
- ✅ Preços em tempo real (delay ~15 min)
- ✅ Sem custo de API
- ⚠️ Requer internet

### 3. **Decisão Final é Sua**

Este sistema é uma **ferramenta de apoio**, não um robô autônomo:
- ❌ Não executa trades automaticamente
- ✅ Fornece sinais + conviction + posição recomendada
- ✅ Você decide se segue ou não

### 4. **Gestão de Risco**

**NUNCA aloque 100% do capital em uma única operação**:
- Diversifique entre múltiplos sinais BUY
- Respeite o tamanho de posição recomendado
- Mantenha sempre uma reserva de caixa

---

## 📈 Exemplo de Output

```
================================================================================
📊 RESUMO FINAL - 18 tickers analisados
================================================================================

Ticker     Preço    Signal Conv  Pos%  Trend      News 
--------------------------------------------------------------------------------
VALE3.SA   R$ 65.23 🟢 BUY  0.85  70%   uptrend    +0.42
PETR4.SA   R$ 38.91 🟢 BUY  0.72  50%   uptrend    +0.31
ITUB4.SA   R$ 29.45 🟢 BUY  0.55  25%   neutral    +0.15
BBDC4.SA   R$ 15.67 ⚪ HOLD 0.22  -     neutral    +0.08
ABEV3.SA   R$ 11.23 ⚪ HOLD 0.05  -     downtrend  -0.12
MGLU3.SA   R$  2.85 🔴 SELL -0.51  -    downtrend  -0.38

────────────────────────────────────────────────────────────────────────────────
  🟢 BUY: 3 | 🔴 SELL: 1 | ⚪ HOLD: 14
================================================================================
```

---

## 🔧 Troubleshooting

### Erro: "Failed to download data"

**Causa**: yfinance não conseguiu baixar dados do ticker.

**Solução**:
```bash
# Testar ticker manualmente
python3 -c "import yfinance as yf; print(yf.download('PETR4.SA', period='1mo'))"
```

### Erro: "No articles found"

**Causa**: Google News não tem notícias recentes para o ticker.

**Comportamento**: Sistema usa sentiment = 0.0 (neutro) e continua.

### Performance lenta

**Causa**: Buscando notícias para muitos tickers.

**Solução**:
```bash
# Reduzir janela de notícias
python3 production_runner.py --days 3

# Ou analisar apenas alguns tickers
python3 production_runner.py --ticker PETR4.SA
```

---

## 📝 Logs e Histórico

### Salvar sinais diários

```bash
# Criar pasta de logs
mkdir -p ~/trading_logs

# Executar e salvar
python3 production_runner.py > ~/trading_logs/signals_$(date +%Y-%m-%d).txt
```

### Analisar histórico

```bash
# Ver sinais dos últimos 7 dias
ls -lt ~/trading_logs/ | head -8

# Comparar sinais de hoje vs ontem
diff ~/trading_logs/signals_2026-02-14.txt ~/trading_logs/signals_2026-02-15.txt
```

---

## 🎯 Próximos Passos

1. **Testar com capital pequeno** (2-5% do total)
2. **Acompanhar performance** por 2-4 semanas
3. **Ajustar thresholds** se necessário
4. **Escalar gradualmente** conforme confiança aumenta

---

## 💡 Dicas

### 1. **Combine com análise fundamental**
- Sinais técnicos + notícias são úteis, mas não substituem análise de balanço
- Use o sistema como filtro inicial

### 2. **Respeite stop-loss**
- Se uma posição cair >10%, considere sair independente do sinal
- Conviction alto não garante sucesso 100%

### 3. **Revise semanalmente**
- Compare performance real vs sinais
- Ajuste estratégia se necessário

---

## ❓ Suporte

Problemas? Melhorias? Entre em contato com TARS via Telegram.

**Última atualização**: 2026-02-15
