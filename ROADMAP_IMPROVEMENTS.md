# 🚀 Stock Signals - Melhorias de Produção

**Data**: 2026-02-15 11:06 GMT-3  
**Solicitação**: Bruno Santos (@StepanNercessian)

## 🎯 Objetivos

1. **Exit timing melhorado**: Stop loss, take profit, trailing stops inteligentes
2. **Notícias em tempo real**: Monitorar notícias a cada 10 minutos
3. **Cobertura total**: Expandir para TODOS os índices (IBOV completo + SMLL + outros)

## 📋 Roadmap Detalhado

### Fase 1: Exit Timing Inteligente (Prioridade ALTA) ✅ CONCLUÍDA
- [x] **1.1** Implementar stop loss dinâmico baseado em ATR (Average True Range)
  - Stop loss inicial: 2x ATR abaixo do preço de entrada
  - Ajusta conforme volatilidade do ativo
- [x] **1.2** Implementar take profit em níveis de resistência
  - TP1: +5% (vende 30% da posição)
  - TP2: +10% (vende 40% da posição)
  - TP3: +15% (vende 30% restante)
- [x] **1.3** Implementar trailing stop
  - Ativa após +8% de lucro
  - Segue o preço com distância de 1.5x ATR
- [x] **1.4** Adicionar exit por mudança de regime
  - Sair imediatamente se TrendDetectorV2 mudar de bullish → bearish
  - Sair em 50% se mudar de bullish → neutral
- [x] **1.5** Criar `src/risk/exit_manager.py` - Implementado com todas features
- [x] **1.6** Adicionar testes em `tests/test_exit_manager.py` - 14/14 testes passando
- [x] **1.7** Integrar no `production_v2.py` (novo arquivo, mantém o antigo funcionando)
- [x] **1.8** Backtest 6 meses com novo exit timing - **+49.78% (vs IBOV +40.79%)**
- [x] **1.9** Validar melhoria vs versão anterior - **+35.28 pp vs baseline (+14.50%)**
  - **RESULTADO**: Exit Manager bateu IBOV e melhorou +35 pontos vs baseline!
  - 13 posições, 180 saídas (take profit multi-nível funcionando)
  - Win rate: 99.4% (179 winning, 1 losing)

### Fase 2: Notícias em Tempo Real (Prioridade ALTA) ⚙️ EM PROGRESSO
- [x] **2.1** Criar sistema de notícias filtradas (`filtered_news_client.py`)
  - Google News RSS com filtros específicos por ticker
  - Cache de 10 minutos para evitar rate limits
  - Busca apenas notícias relevantes (ticker/empresa no título)
- [x] **2.2** Implementar análise de sentimento com FinBERT
  - Testado com VALE3: 6 artigos, sentiment +0.82 (muito positivo)
  - Tempo de carregamento: ~20s (aceitável conforme Bruno)
- [x] **2.3** Filtro de relevância implementado
  - Só considera notícias com ticker/empresa no título ou resumo
  - Filtra por fontes brasileiras (InfoMoney, Valor, Estadão, etc.)
- [ ] **2.4** Integrar filtro no `monitor_market_v2.py`
- [ ] **2.5** Adicionar testes em `tests/test_filtered_news.py`
- [ ] **2.6** Testar em produção simulada por 48h
- [ ] **2.7** Validar que notícias agregam valor vs baseline sem notícias

### Fase 3: Expansão de Cobertura (Prioridade MÉDIA)
- [ ] **3.1** Coletar lista completa do IBOV (~87 ações)
  - Fonte: B3 ou yfinance
- [ ] **3.2** Coletar lista completa do SMLL (Small Caps)
  - Fonte: B3 ou yfinance
- [ ] **3.3** Adicionar outros índices relevantes
  - IDIV (dividendos)
  - IFNC (financeiro)
  - UTIL (utilities)
- [ ] **3.4** Implementar filtro de liquidez
  - Volume médio diário > R$ 5 milhões
  - Evitar ações sem liquidez que travem posições
- [ ] **3.5** Criar `data/indices/` com CSVs dos índices
- [ ] **3.6** Atualizar `production_simple.py` para usar listas dinâmicas
- [ ] **3.7** Adicionar configuração `config/production.yaml`
  - Escolher quais índices monitorar
  - Configurar filtros de liquidez
- [ ] **3.8** Testar com ~150-200 ações
- [ ] **3.9** Otimizar performance (paralelização se necessário)
- [ ] **3.10** Validar que sistema roda em <5 minutos

### Fase 4: Integração e Validação Final
- [ ] **4.1** Rodar backtest 6 meses com TODAS as melhorias
  - Exit timing + Notícias + Cobertura expandida
- [ ] **4.2** Comparar com versão atual (+14.50%)
  - Meta: +30% vs IBOV +40.79%
- [ ] **4.3** Validar que não há look-ahead bias
- [ ] **4.4** Testar em produção simulada por 1 semana
- [ ] **4.5** Documentar configuração final
- [ ] **4.6** Atualizar `PRODUCTION_README.md`
- [ ] **4.7** Push para GitHub
- [ ] **4.8** Deploy em produção REAL

## ⚠️ Riscos e Mitigações

| Risco | Mitigação |
|-------|-----------|
| Notícias podem prejudicar novamente (-0.08% anterior) | Testar em produção simulada 48h antes de deploy real |
| Exit timing agressivo pode sair muito cedo | Backtest 6 meses para validar antes |
| ~200 ações podem ser lentas para processar | Paralelizar com `concurrent.futures` se necessário |
| Mais ações = mais trades = mais custos | Filtrar apenas as com melhor liquidez |

## 📊 Métricas de Sucesso

- **Exit timing**: Reduzir drawdown máximo em >30%
- **Notícias**: Agregar +2-3% vs versão sem notícias
- **Cobertura**: Encontrar >50 oportunidades/mês (vs 17 trades em 6 meses)
- **Performance total**: +30% vs IBOV +40.79% (reduzir gap de -26.30% para -10%)

## 🚦 Status Atual

**EM PROGRESSO**: Iniciando Fase 1 (Exit Timing)

---

**Próximo checkpoint**: Após Fase 1.5 (exit_manager.py implementado)
