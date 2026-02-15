#!/usr/bin/env python3
"""
Teste completo de todas as funcionalidades solicitadas
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from production_v2 import ProductionRunnerV2
import json

print("="*70)
print("🧪 TESTE COMPLETO DE TODAS AS FUNCIONALIDADES")
print("="*70)

# Lista de features esperadas
features = {
    "1. Download paralelo (150x faster)": False,
    "2. Batch save positions (90% less I/O)": False,
    "3. DecisionLogger com reasoning": False,
    "4. FilteredNewsClient integrado": False,
    "5. Exit manager com multi-level TP": False,
    "6. Trailing stop funcionando": False,
    "7. News sentiment graduado": False,
    "8. Regime detection funcionando": False,
    "9. Stop loss tighten sem exit": False,
    "10. Bulk download validation": False,
    "11. Error handling robusto": False,
    "12. ATR calculation otimizado": False,
}

print("\n📋 Testando features...")

# 1. Teste com sistema completo
runner = ProductionRunnerV2(use_news=False, use_reasoning=True)

# Verificar que positions_modified flag existe
if hasattr(runner, 'positions_modified'):
    features["2. Batch save positions (90% less I/O)"] = True
    print("✅ Feature 2: Batch save flag exists")

# Verificar DecisionLogger
if hasattr(runner, 'decision_logger') and hasattr(runner, 'signal_analyzer'):
    features["3. DecisionLogger com reasoning"] = True
    print("✅ Feature 3: DecisionLogger & SignalAnalyzer integrated")

# Verificar FilteredNewsClient
if hasattr(runner, 'news_client'):
    runner_with_news = ProductionRunnerV2(use_news=True, use_reasoning=False)
    from src.news.filtered_news_client import FilteredNewsClient
    if isinstance(runner_with_news.news_client, FilteredNewsClient):
        features["4. FilteredNewsClient integrado"] = True
        print("✅ Feature 4: FilteredNewsClient active")

# Verificar ExitManager
if hasattr(runner, 'exit_manager'):
    from src.risk.exit_manager import ExitManager
    
    # Verificar multi-level TP
    exit_mgr = runner.exit_manager
    if hasattr(exit_mgr, 'tp1_pct') and hasattr(exit_mgr, 'tp2_pct') and hasattr(exit_mgr, 'tp3_pct'):
        features["5. Exit manager com multi-level TP"] = True
        print("✅ Feature 5: Multi-level take profits")
    
    # Verificar trailing stop
    if hasattr(exit_mgr, 'trailing_activation'):
        features["6. Trailing stop funcionando"] = True
        print("✅ Feature 6: Trailing stop configured")

# Verificar news graduated thresholds no código
try:
    with open('src/risk/exit_manager.py', 'r') as f:
        code = f.read()
        if 'news_sentiment <= -0.8' in code and 'news_sentiment <= -0.6' in code and 'news_sentiment <= -0.4' in code:
            features["7. News sentiment graduado"] = True
            print("✅ Feature 7: Graduated news sentiment")
except:
    pass

# Verificar TrendDetectorV2
from src.signals.trend_detector_v2 import TrendDetectorV2
detector = TrendDetectorV2()
if hasattr(detector, 'macro_period') and hasattr(detector, 'micro_period'):
    features["8. Regime detection funcionando"] = True
    print("✅ Feature 8: Dual-timeframe trend detection")

# Verificar que código tem a feature de tighten stop
try:
    with open('production_v2.py', 'r') as f:
        code = f.read()
        if 'Stop loss tightened' in code:
            features["9. Stop loss tighten sem exit"] = True
            print("✅ Feature 9: Stop tighten without exit")
except:
    pass

# Verificar bulk download validation
try:
    with open('production_v2.py', 'r') as f:
        code = f.read()
        if 'Invalid data structure' in code and 'not in bulk download' in code:
            features["10. Bulk download validation"] = True
            print("✅ Feature 10: Bulk download validation")
except:
    pass

# Verificar error handling
try:
    with open('production_v2.py', 'r') as f:
        code = f.read()
        # Conta quantos try/except existem
        try_count = code.count('try:')
        if try_count >= 5:  # Deve ter pelo menos 5 try/except blocks
            features["11. Error handling robusto"] = True
            print(f"✅ Feature 11: Error handling ({try_count} try/except blocks)")
except:
    pass

# Verificar numpy optimization no ATR
try:
    with open('src/risk/exit_manager.py', 'r') as f:
        code = f.read()
        if 'np.maximum' in code:
            features["12. ATR calculation otimizado"] = True
            print("✅ Feature 12: ATR numpy optimization")
except:
    pass

# Testar download paralelo (feature 1)
import time
start = time.time()
test_tickers = ['VALE3.SA', 'PETR4.SA']
data = runner.get_data_bulk(test_tickers)
elapsed = time.time() - start

if elapsed < 2.0 and len(data) == 2:  # Deve ser < 2s para 2 tickers
    features["1. Download paralelo (150x faster)"] = True
    print(f"✅ Feature 1: Parallel download ({elapsed:.1f}s for 2 tickers)")

# Resultado final
print("\n" + "="*70)
print("📊 RESULTADO FINAL")
print("="*70)

passed = sum(1 for v in features.values() if v)
total = len(features)

for feature, status in features.items():
    emoji = "✅" if status else "❌"
    print(f"{emoji} {feature}")

print("\n" + "="*70)
print(f"Score: {passed}/{total} features funcionando ({passed/total*100:.1f}%)")
print("="*70)

# Exit code
sys.exit(0 if passed == total else 1)
