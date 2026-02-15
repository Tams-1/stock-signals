#!/usr/bin/env python3
"""
Add AI-powered reasoning to trading signals using Claude Haiku

Reads decisions_log.json and adds human-readable explanations
"""

import json
import subprocess
import sys

def call_haiku(prompt):
    """Call Claude Haiku via OpenClaw's oracle CLI"""
    try:
        result = subprocess.run(
            ['oracle', '-m', 'haiku', '--'],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"[Erro ao gerar explicação: {result.stderr}]"
    except Exception as e:
        return f"[Erro: {str(e)}]"

def generate_reasoning_prompt(signal_data):
    """Generate prompt for Haiku"""
    components = signal_data['components']
    
    prompt = f"""Você é um analista quantitativo. Explique EM PORTUGUÊS e de forma CONCISA (2-3 linhas) por que o sistema recomenda:

Ticker: {signal_data['ticker']}
Sinal: {signal_data['signal']}
Tamanho posição: {signal_data.get('position_size', 0):.0%}
Confiança: {signal_data.get('confidence', 0):.1%}

Componentes:
- Preço: R$ {components.get('price', {}).get('current', 0):.2f} ({components.get('price', {}).get('change_pct', 0):+.1f}% dia)
- vs MA20: {components.get('price', {}).get('vs_ma20', 0):+.1f}%
- Tendência: {components.get('trend', {}).get('consensus', 'unknown')} (conf {components.get('trend', {}).get('confidence', 0):.1%})
- RSI: {components.get('momentum', {}).get('rsi', 50):.0f} ({components.get('momentum', {}).get('rsi_signal', 'neutral')})
- Volume: {components.get('volume', {}).get('signal', 'normal')}

Fator principal: {signal_data.get('key_factor', 'unknown')}

Responda em 2-3 linhas: PORQUÊ da recomendação e SINAL MAIS IMPORTANTE."""

    return prompt

def main():
    # Load decision log
    try:
        with open('decisions_log.json', 'r') as f:
            decisions = json.load(f)
    except FileNotFoundError:
        print("❌ decisions_log.json não encontrado. Rode production_explainable.py primeiro.")
        sys.exit(1)
    
    print(f"📖 Carregando {len(decisions)} decisões...")
    print("🤖 Gerando explicações com Claude Haiku...\n")
    
    # Add reasoning to each decision
    for i, decision in enumerate(decisions, 1):
        ticker = decision['ticker']
        signal = decision['signal']
        
        # Skip HOLD signals (not interesting)
        if signal == 'HOLD':
            decision['reasoning'] = "Mercado neutro, sem sinal claro de entrada."
            continue
        
        print(f"[{i}/{len(decisions)}] {ticker} ({signal})...", end=" ")
        
        prompt = generate_reasoning_prompt(decision)
        reasoning = call_haiku(prompt)
        
        decision['reasoning'] = reasoning
        print("✓")
    
    # Save enriched log
    with open('decisions_log_explained.json', 'w') as f:
        json.dump(decisions, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Explicações geradas!")
    print("💾 Salvo em: decisions_log_explained.json\n")
    
    # Print summary
    print("="*80)
    print("📋 RESUMO DAS RECOMENDAÇÕES")
    print("="*80)
    
    for decision in decisions:
        if decision['signal'] == 'HOLD':
            continue
        
        emoji = "🟢" if decision['signal'] == "BUY" else "🔴"
        print(f"\n{emoji} {decision['ticker']} - {decision['signal']}")
        print(f"   Posição: {decision.get('position_size', 0):.0%} | Confiança: {decision.get('confidence', 0):.1%}")
        print(f"   Fator: {decision.get('key_factor', 'unknown')}")
        print(f"   Razão: {decision.get('reasoning', 'N/A')}")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
