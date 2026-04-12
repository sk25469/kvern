"""
Streamlit dashboard for KVern cache performance visualization.

Provides real-time insights into cache hit rates, prefix patterns,
and optimization opportunities.
"""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import asyncio
import time
from datetime import datetime, timedelta
import yaml

from ..analytics.store import AnalyticsStore
from ..analytics.queries import AnalyticsQueryEngine

# Page config
st.set_page_config(
    page_title="KVern Cache Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .stMetric > label {
        font-size: 0.9rem !important;
    }
</style>
""", unsafe_allow_html=True)

# Load configuration
@st.cache_data
def load_config():
    """Load KVern configuration."""
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {
            "analytics": {"db_path": "./data/cache_analytics.db"},
            "dashboard": {"port": 8501}
        }

def init_dashboard():
    """Initialize dashboard components."""
    config = load_config()
    db_path = config["analytics"]["db_path"]
    
    # Initialize analytics components
    analytics_store = AnalyticsStore(db_path)
    query_engine = AnalyticsQueryEngine(db_path)
    
    return analytics_store, query_engine

@st.cache_data(ttl=60)  # Cache for 1 minute
def get_summary_stats(query_engine, hours=24):
    """Get cached summary statistics."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Get basic stats
        summary = loop.run_until_complete(
            query_engine.get_summary_stats(hours)
        )
        
        # Get model comparison
        model_stats = loop.run_until_complete(
            query_engine.get_model_comparison(hours)
        )
        
        return summary, model_stats
    finally:
        loop.close()

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_timeline_data(query_engine, hours=24):
    """Get cached timeline data."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        timeline = loop.run_until_complete(
            query_engine.get_hit_rate_timeline(hours, bucket_minutes=60)
        )
        return timeline
    finally:
        loop.close()

def main():
    """Main dashboard application."""
    
    # Header
    st.title("⚡ KVern Cache Dashboard")
    st.markdown("Real-time LLM cache performance monitoring")
    
    # Initialize
    try:
        analytics_store, query_engine = init_dashboard()
    except Exception as e:
        st.error(f"Failed to connect to analytics database: {e}")
        st.info("Make sure KVern is running and has processed some requests.")
        return
    
    # Sidebar controls
    st.sidebar.header("⚙️ Controls")
    
    # Time window selector
    time_window = st.sidebar.selectbox(
        "Time Window",
        options=[1, 6, 24, 72, 168],  # hours
        index=2,  # default to 24h
        format_func=lambda x: f"{x}h" if x < 24 else f"{x//24}d"
    )
    
    # Auto-refresh toggle
    auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", value=True)
    if auto_refresh:
        time.sleep(30)
        st.rerun()
    
    # Manual refresh button
    if st.sidebar.button("🔄 Refresh Now"):
        st.cache_data.clear()
        st.rerun()
    
    # Main content
    try:
        # Get data
        summary_stats, model_stats = get_summary_stats(query_engine, time_window)
        
        # Overview metrics
        st.header("📊 Overview")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Hit Rate",
                f"{summary_stats['hit_rate'] * 100:.1f}%",
                delta=None
            )
        
        with col2:
            st.metric(
                "Total Requests",
                f"{summary_stats['total_requests']:,}",
                delta=None
            )
        
        with col3:
            st.metric(
                "Token Reuse",
                f"{summary_stats['token_reuse_ratio'] * 100:.1f}%",
                delta=None
            )
        
        with col4:
            st.metric(
                "Compute Savings",
                f"{summary_stats['theoretical_compute_savings_pct']:.1f}%",
                delta=None
            )
        
        # Timeline chart
        st.header("📈 Hit Rate Timeline")
        
        if timeline_data := get_timeline_data(query_engine, time_window):
            timeline_df = pd.DataFrame(timeline_data)
            timeline_df['datetime'] = pd.to_datetime(timeline_df['timestamp'], unit='s')
            
            fig = px.line(
                timeline_df, 
                x='datetime', 
                y='hit_rate',
                title=f"Cache Hit Rate Over Time ({time_window}h window)",
                labels={'hit_rate': 'Hit Rate', 'datetime': 'Time'}
            )
            fig.update_traces(line_color='#1f77b4')
            fig.update_layout(yaxis=dict(tickformat='.1%'))
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No timeline data available yet.")
        
        # Model comparison
        if model_stats:
            st.header("🔍 Model Performance")
            
            # Convert to DataFrame for easier plotting
            models_df = pd.DataFrame.from_dict(model_stats, orient='index')
            models_df['model'] = models_df.index
            
            # Model performance table
            display_df = models_df[[
                'model', 'total_requests', 'hit_rate', 'token_reuse_ratio', 
                'avg_latency_ms', 'compute_savings_pct'
            ]].copy()
            
            display_df['hit_rate'] = (display_df['hit_rate'] * 100).round(1)
            display_df['token_reuse_ratio'] = (display_df['token_reuse_ratio'] * 100).round(1)
            display_df['compute_savings_pct'] = display_df['compute_savings_pct'].round(1)
            display_df['avg_latency_ms'] = display_df['avg_latency_ms'].round(1)
            
            display_df.columns = [
                'Model', 'Requests', 'Hit Rate (%)', 'Token Reuse (%)',
                'Avg Latency (ms)', 'Compute Savings (%)'
            ]
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # Model comparison charts
            col1, col2 = st.columns(2)
            
            with col1:
                fig = px.bar(
                    models_df,
                    x='model',
                    y='hit_rate',
                    title="Hit Rate by Model",
                    labels={'hit_rate': 'Hit Rate', 'model': 'Model'}
                )
                fig.update_layout(yaxis=dict(tickformat='.1%'))
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.bar(
                    models_df,
                    x='model', 
                    y='token_reuse_ratio',
                    title="Token Reuse by Model",
                    labels={'token_reuse_ratio': 'Token Reuse Ratio', 'model': 'Model'}
                )
                fig.update_layout(yaxis=dict(tickformat='.1%'))
                st.plotly_chart(fig, use_container_width=True)
        
        # Cache pressure analysis
        st.header("🔍 Cache Analysis")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Get cache pressure metrics
            pressure_metrics = loop.run_until_complete(
                query_engine.get_cache_pressure_metrics(time_window)
            )
            
            # Get optimization opportunities
            opportunities = loop.run_until_complete(
                query_engine.identify_optimization_opportunities(time_window)
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Cache Pressure")
                st.metric("Requests/Hour", f"{pressure_metrics['requests_per_hour']:.1f}")
                st.metric("Unique Models", pressure_metrics['unique_models'])
                st.metric("Avg Prompt Length", f"{pressure_metrics['avg_prompt_length']:.0f} tokens")
            
            with col2:
                st.subheader("Optimization Opportunities")
                if opportunities:
                    for opp in opportunities:
                        if opp['type'] == 'low_hit_rate':
                            st.warning(f"⚠️ {opp['suggestion']}")
                        elif opp['type'] == 'repeated_miss_pattern':
                            st.info(f"💡 {opp['suggestion']}")
                else:
                    st.success("✅ No major optimization opportunities detected")
                    
        finally:
            loop.close()
        
        # Hot prefixes (if available)
        st.header("🔥 Hot Prefixes")
        
        if model_stats:
            selected_model = st.selectbox("Select Model", options=list(model_stats.keys()))
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                hot_prefixes = loop.run_until_complete(
                    analytics_store.get_hot_prefixes(selected_model, limit=10)
                )
                
                if hot_prefixes:
                    hot_df = pd.DataFrame([
                        {
                            'Prefix Hash': hp.prefix_hash,
                            'Depth': hp.token_depth,
                            'Count': hp.count,
                            'Last Seen': datetime.fromtimestamp(hp.last_seen).strftime('%Y-%m-%d %H:%M'),
                            'Age': f"{(time.time() - hp.first_seen) / 3600:.1f}h"
                        }
                        for hp in hot_prefixes
                    ])
                    
                    st.dataframe(hot_df, use_container_width=True, hide_index=True)
                else:
                    st.info(f"No hot prefixes found for {selected_model}")
            finally:
                loop.close()
        
        # Footer
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.caption(f"⏰ Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        with col2:
            st.caption(f"📊 Showing data from last {time_window}h")
        
        with col3:
            if summary_stats['total_requests'] > 0:
                st.caption(f"📈 Processing {summary_stats['total_requests']} requests")
            else:
                st.caption("⏳ Waiting for requests...")
                
    except Exception as e:
        st.error(f"Dashboard error: {e}")
        st.info("Check that the analytics database is accessible and contains data.")


if __name__ == "__main__":
    main()