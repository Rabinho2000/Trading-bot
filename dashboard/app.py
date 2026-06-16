import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import sys
import os

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import config
from db.database import get_session, Signal, Run, SignalReview

st.set_page_config(page_title="t212-signal-lab Dashboard", layout="wide")

st.title("📈 t212-signal-lab")

session = get_session()

# Sidebar
st.sidebar.header("Filters")
action_filter = st.sidebar.multiselect("Action", ["BUY", "WATCH", "SKIP", "SELL"], default=["BUY", "WATCH"])
risk_filter = st.sidebar.multiselect("Risk Rating", ["LOW", "MEDIUM", "HIGH"], default=["LOW", "MEDIUM", "HIGH"])

# Latest Run
latest_run = session.query(Run).order_by(Run.timestamp.desc()).first()
if latest_run:
    st.metric("Latest Market Regime", latest_run.market_regime)
    st.write(f"Last updated: {latest_run.timestamp}")

# Signals Table
st.header("Latest Signals")
query = session.query(Signal).join(Run).filter(Signal.run_id == latest_run.id if latest_run else True)

if action_filter:
    query = query.filter(Signal.action.in_(action_filter))
if risk_filter:
    query = query.filter(Signal.risk_rating.in_(risk_filter))

signals = query.order_by(Signal.final_score.desc()).all()

if signals:
    data = []
    for s in signals:
        data.append({
            "Ticker": s.ticker,
            "Action": s.action,
            "Score": s.final_score,
            "Risk": s.risk_rating,
            "Entry": f"{s.entry_min} - {s.entry_max}",
            "Invalidation": s.invalidation,
            "Target 1": s.target_1,
            "Reason": s.reason
        })
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)
    
    # Detail view
    st.header("Signal Details & AI Analysis")
    selected_ticker = st.selectbox("Select ticker for details", [s.ticker for s in signals])
    
    if selected_ticker:
        sig = next(s for s in signals if s.ticker == selected_ticker)
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Technical Specs")
            st.write(f"**Technical Score:** {sig.technical_score}")
            st.write(f"**Regime Score:** {sig.regime_score}")
            st.write(f"**Final Score:** {sig.final_score}")
            st.write(f"**Time Horizon:** 2-6 weeks")
            
        with col2:
            review = sig.review
            if review:
                st.subheader("AI Analysis")
                st.info(review.summary)
                st.write("**Bullish Thesis:**")
                st.write(review.bullish_thesis)
                st.write("**Bearish Thesis:**")
                st.write(review.bearish_thesis)
                st.write("**Risks:**")
                st.write(review.risks)
                st.write(f"**Confidence:** {review.confidence_score}")
else:
    st.warning("No signals found. Run analysis first.")

session.close()
