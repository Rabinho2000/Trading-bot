import config
from openai import OpenAI

def get_ai_analysis(signal):
    """
    Generate AI analysis for a signal.
    """
    if not config.OPENAI_API_KEY:
        return get_fallback_analysis(signal)
    
    try:
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        
        prompt = f"""
        Analyze the following trading signal for {signal['ticker']}:
        Action: {signal['action']}
        Technical Score: {signal['technical_score']}
        Regime Score: {signal['regime_score']}
        Final Score: {signal['final_score']}
        Risk Rating: {signal['risk_rating']}
        Entry: {signal['entry_zone']}
        Invalidation: {signal['invalidation']}
        Targets: {signal['target_1']}, {signal['target_2']}
        Reason: {signal['reason']}
        
        Provide:
        1. Summary (max 2 sentences)
        2. Bullish Thesis
        3. Bearish Thesis
        4. Main Risks
        5. Confidence Score (0.0 to 1.0)
        
        Format as JSON.
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        
        import json
        return json.loads(response.choices[0].message.content)
        
    except Exception as e:
        print(f"AI Analysis error: {e}")
        return get_fallback_analysis(signal)

def get_fallback_analysis(signal):
    """
    Rule-based fallback for AI analysis.
    """
    return {
        "summary": f"Technical setup for {signal['ticker']} indicates a {signal['action']} action.",
        "bullish_thesis": f"Momentum and trend are supportive. Technical score is {signal['technical_score']}.",
        "bearish_thesis": f"Potential reversal if invalidation at {signal['invalidation']} is hit.",
        "risks": f"Market regime impact and {signal['risk_rating']} volatility risk.",
        "confidence_score": signal['final_score']
    }
