import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from components.ui_components import render_kpi, view_error_details
import logging

# --- Theme Helpers ---
def get_plotly_template():
    """Returns the appropriate plotly template based on current theme."""
    mode = st.session_state.get("theme_mode", "Light")
    if mode == "Dark":
        return "plotly_dark"
    return "plotly_white"

# --- Metrics Helpers ---
def calculate_metrics(data_df):
    if data_df.empty: return 0, 0, 0, 0
    total = len(data_df)
    errs = len(data_df[data_df['log_level'] == 'ERROR']) if 'log_level' in data_df.columns else 0
    warns = len(data_df[data_df['log_level'] == 'WARN']) if 'log_level' in data_df.columns else 0
    rate = (errs / total * 100) if total > 0 else 0
    return total, errs, warns, rate

def format_trend(curr, prev, has_trend, is_rate=False):
    if not has_trend or prev == 0:
        return "", ""
    
    diff = curr - prev
    # For rate, diff is percentage points
    
    pct = (diff / prev * 100)
    arrow = "↗" if diff > 0 else "↘" if diff < 0 else "−"
    sign = "+" if diff > 0 else ""
    return arrow, f"{sign}{pct:.0f}%"

# --- Main Render Function ---
def render_dashboard(filtered_df: pd.DataFrame, prev_df: pd.DataFrame = None, container=st):
    """
    Renders the main dashboard view (KPIs, Charts, Top Errors).
    """
    
    # Calculate Metrics
    curr_total, curr_err, curr_warn, curr_rate = calculate_metrics(filtered_df)
    
    prev_total, prev_err, prev_warn, prev_rate = 0, 0, 0, 0
    has_trend = False
    if prev_df is not None and not prev_df.empty:
        prev_total, prev_err, prev_warn, prev_rate = calculate_metrics(prev_df)
        has_trend = True
        
    # Calculate trends
    t1_arrow, t1_val = format_trend(curr_total, prev_total, has_trend)
    t2_arrow, t2_val = format_trend(curr_err, prev_err, has_trend)
    t3_arrow, t3_val = format_trend(curr_warn, prev_warn, has_trend)
    t4_arrow, t4_val = format_trend(curr_rate, prev_rate, has_trend, is_rate=True)

    with container:
        # KPI Row
        k1, k2, k3, k4 = st.columns(4)
        with k1: render_kpi("Total Logs", f"{curr_total:,}", "logs", "#0D9488", "📝", t1_arrow, t1_val) # Primary Teal
        with k2: render_kpi("Total Errors", f"{curr_err:,}", "errs", "#EF4444", "🚨", t2_arrow, t2_val) # Red
        with k3: render_kpi("Warnings", f"{curr_warn:,}", "warns", "#EAB308", "⚠️", t3_arrow, t3_val) # Amber
        with k4: render_kpi("Error Rate", f"{curr_rate:.2f}%", "rate", "#6366F1", "📉", t4_arrow, t4_val) # Indigo

        st.markdown("<br>", unsafe_allow_html=True)

        # Charts Row
        c1, c2 = st.columns([2, 1])
        
        with c1:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            # Header with controls
            h_col1, h_col2 = st.columns([3, 1])
            with h_col1:
                st.markdown("""
<div class="chart-header" style="margin-bottom: 0;">
<div class="chart-title">Error Trends</div>
</div>
""", unsafe_allow_html=True)
            with h_col2:
                # Granularity selector
                default_index = 1
                if not filtered_df.empty and 'timestamp' in filtered_df.columns:
                     try:
                         days_diff = (filtered_df['timestamp'].max() - filtered_df['timestamp'].min()).days
                         if days_diff > 30:
                             default_index = 2
                     except: pass
                
                granularity = st.selectbox(
                    "Granularity", 
                    ["Minute", "Hour", "Day", "Week", "Month"], 
                    index=default_index,
                    label_visibility="collapsed"
                )
            
            # Map friendly names to pandas offsets (Fixing 'M' deprecation usually requires 'ME' in pandas 2.2+, using 'M' for safety unless known)
            offset_map = { "Minute": "T", "Hour": "h", "Day": "D", "Week": "W", "Month": "ME" }
            resample_rule = offset_map.get(granularity, "h")

            # Trend Chart
            if not filtered_df.empty and 'timestamp' in filtered_df.columns:
                # Prepare Data
                error_data = pd.DataFrame()
                warning_data = pd.DataFrame()
                
                # Errors
                err_df = filtered_df[filtered_df['log_level'] == 'ERROR'].copy()
                err_df = err_df.dropna(subset=['timestamp']) # Ensure valid time for chart
                if not err_df.empty:
                    error_data = err_df.set_index('timestamp').resample(resample_rule).size().reset_index(name='count')
                    error_data = error_data[error_data['count'] > 0]
                
                # Warnings
                warn_df = filtered_df[filtered_df['log_level'] == 'WARN'].copy()
                warn_df = warn_df.dropna(subset=['timestamp']) # Ensure valid time for chart
                if not warn_df.empty:
                    warning_data = warn_df.set_index('timestamp').resample(resample_rule).size().reset_index(name='count')
                    # Filter out zero values
                    warning_data = warning_data[warning_data['count'] > 0]

                if not error_data.empty or not warning_data.empty:
                    fig = go.Figure()

                    # Theme Colors for Charts
                    is_dark = st.session_state.get("theme_mode", "Light") == "Dark"
                    chart_text_color = '#ECFEFF' if is_dark else '#000000'
                    chart_muted_color = '#94A3B8' if is_dark else '#64748B'
                    chart_grid_color = '#20353B' if is_dark else '#F1F5F9'

                    # Add Warnings Trace (Amber)
                    if not warning_data.empty:
                        fig.add_trace(go.Scatter(
                            x=warning_data['timestamp'], 
                            y=warning_data['count'],
                            name='Warnings',
                            mode='lines+markers',
                            line=dict(color='#F59E0B', width=2, shape='linear'), # Linear prevents negative interpolation overshoot
                            marker=dict(size=8, color='#F59E0B', symbol='circle'),
                            fill='tozeroy',
                            fillcolor='rgba(245, 158, 11, 0.1)',
                            hovertemplate='<b>%{x}</b><br>Warnings: %{y}<extra></extra>'
                        ))

                    # Add Errors Trace (Red) - On top
                    if not error_data.empty:
                        fig.add_trace(go.Scatter(
                            x=error_data['timestamp'], 
                            y=error_data['count'],
                            name='Errors',
                            mode='lines+markers',
                            line=dict(color='#EF4444', width=3, shape='linear'), # Linear prevents negative interpolation overshoot
                            marker=dict(size=8, color='#EF4444', symbol='circle'),
                            fill='tozeroy',
                            fillcolor='rgba(239, 68, 68, 0.15)',
                            hovertemplate='<b>%{x}</b><br>Errors: %{y}<extra></extra>'
                        ))

                    fig.update_layout(
                        title=dict(
                            text="Error & Warning Trends",
                            font=dict(size=14, color=chart_text_color),
                            x=0
                        ),
                        legend=dict(
                            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                            font=dict(color=chart_text_color)
                        ),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        margin=dict(l=0, r=0, t=40, b=0),
                        xaxis=dict(
                            showgrid=True, 
                            gridcolor=chart_grid_color, 
                            title=None, 
                            tickfont=dict(color=chart_muted_color)
                        ),
                        yaxis=dict(
                            showgrid=True, 
                            gridcolor=chart_grid_color, 
                            title=None, 
                            tickfont=dict(color=chart_muted_color)
                        ),
                        height=320,
                        hovermode="x unified",
                        template=get_plotly_template(),
                        font=dict(color=chart_text_color),
                        hoverlabel=dict(
                            bgcolor="#162226" if is_dark else "#FFFFFF",
                            font=dict(color="#ECFEFF" if is_dark else "#334155")
                        )
                    )
                    st.plotly_chart(fig, config={'displayModeBar': False}, width="stretch", theme=None)
                else:
                    st.info("No data for selected period")
            else:
                    # Empty state instead of mock data
                    st.markdown('<div style="height:280px; display:flex; align-items:center; justify-content:center; color:#94A3B8;">No Data Available</div>', unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)
            
        with c2:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            st.markdown('<div class="chart-title" style="margin-bottom:20px;">Distribution</div>', unsafe_allow_html=True)
            
            # Donut Chart for Levels
            levels_data = pd.DataFrame({
                'Level': ['INFO', 'WARN', 'ERROR'],
                'Count': [curr_total - curr_err - curr_warn, curr_warn, curr_err]
            })
            colors = ['#0D9488', '#EAB308', '#EF4444'] # Teal, Amber, Red
            
            if curr_total > 0:
                is_dark = st.session_state.get("theme_mode", "Light") == "Dark"
                chart_text_color = '#ECFEFF' if is_dark else '#000000'

                fig_donut = go.Figure(data=[go.Pie(
                    labels=levels_data['Level'],
                    values=levels_data['Count'],
                    hole=.6,
                    marker=dict(colors=colors),
                    textinfo='none' # Hide text on chart, rely on hover or legend
                )])
                fig_donut.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(l=0, r=0, t=0, b=0),
                    showlegend=True,
                    legend=dict(
                        orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5,
                        font=dict(color=chart_text_color)
                    ),
                    height=280,
                    template=get_plotly_template(),
                    font=dict(color=chart_text_color),
                    hoverlabel=dict(
                        bgcolor="#162226" if is_dark else "#FFFFFF",
                        font=dict(color="#ECFEFF" if is_dark else "#334155")
                    )
                )
                st.plotly_chart(fig_donut, config={'displayModeBar': False}, width="stretch", theme=None)
            else:
                    st.markdown('<div style="height:280px; display:flex; align-items:center; justify-content:center; color:#94A3B8;">No Data</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)

        # Bottom Section: Top Errors
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown('<div class="chart-title" style="margin-bottom:20px;">Top Frequent Errors</div>', unsafe_allow_html=True)
        
        if not filtered_df.empty and 'message' in filtered_df.columns:
            # Calculate top errors dynamically
            error_data = filtered_df[filtered_df['log_level'] == 'ERROR']
            if not error_data.empty:
                    error_counts = error_data['message'].value_counts().head(5)
                    max_val = error_counts.max()
                    
                    for idx, (message, count) in enumerate(error_counts.items()):
                        # Grid Layout for Custom Card
                        # Use columns to mimic the card structure since we can't put arbitrary HTML containers around streamlit widgets easily
                        
                        with st.container():
                            c1, c2, c3 = st.columns([0.8, 4, 1])
                            
                            with c1:
                                # Badge
                                st.markdown('<div class="sev-badge error">CRITICAL</div>', unsafe_allow_html=True)
                                
                            with c2:
                                # Message & Progress
                                pct = (count / max_val * 100) if max_val > 0 else 0
                                st.markdown(f'''
                                    <div class="err-msg-box" title="{message}">{message}</div>
                                    <div class="err-meta">Last seen: Just now &bull; Service: Auth</div>
                                    <div class="err-bar-bg"><div class="err-bar-fill" style="width: {pct}%; background-color: #EF4444;"></div></div>
                                ''', unsafe_allow_html=True)
                                
                            with c3:
                                # Count & Action
                                st.markdown(f'<div style="text-align:right; font-weight:700; font-size:1.1rem; color:var(--text-title);">{count}</div>', unsafe_allow_html=True)
                                if st.button("View", key=f"btn_err_{idx}", type="secondary", use_container_width=True):
                                    # Get examples for this error
                                    examples = error_data[error_data['message'] == message]
                                    view_error_details(message, count, examples)
                            
                            st.markdown('<div style="height: 12px;"></div>', unsafe_allow_html=True) # Spacer

            else:
                st.info("No errors found in the current selection.")
        else:
                st.markdown('<div style="color:#94A3B8; padding: 20px 0;">No data to analyze.</div>', unsafe_allow_html=True)
            
        st.markdown('</div>', unsafe_allow_html=True)
