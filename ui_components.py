import streamlit as st

def render_card(content, footer=None):
    """
    Wraps content in a professional SaaS-style card.
    """
    footer_html = f'<div style="border-top: 1px solid var(--border-color); padding-top: 10px; margin-top: 10px; font-size: 0.85rem; color: var(--text-muted);">{footer}</div>' if footer else ""

    return f"""
    <div class="st-card">
        {content}
    </div>
    """

def render_badge(text, stage):
    """
    Returns a color-coded badge based on the application stage.
    """
    stage = stage.lower()
    # Map stages to colors
    color_map = {
        "applied": "#2ecc71",
        "active": "#2ecc71",
        "interview": "#3498db",
        "call": "#3498db",
        "oa": "#f1c40f",
        "assessment": "#f1c40f",
        "challenge": "#f1c40f",
        "offer": "#9b59b6",
        "rejected": "#e74c3c",
        "saved": "#95a5a6",
    }

    # Determine color based on map or default
    bg_color = "var(--border-color)"
    text_color = "var(--text-main)"

    for key, color in color_map.items():
        if key in stage:
            bg_color = color
            text_color = "white" if key not in ["oa", "assessment", "challenge"] else "#2c3e50"
            break

    return f'<span class="status-badge" style="background-color: {bg_color}; color: {text_color};">{text}</span>'

def render_kpi_card(label, value, delta=None):
    """
    A specialized card for dashboard metrics.
    """
    delta_html = f'<div style="font-size: 0.8rem; color: {"#2ecc71" if delta and delta > 0 else "#e74c3c"};">{delta}% vs last month</div>' if delta is not None else ""

    return f"""
    <div class="kpi-card">
        <div style="color: var(--text-muted); font-size: 0.9rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">{label}</div>
        <div style="font-size: 1.8rem; font-weight: 700; color: var(--text-main); margin: 5px 0;">{value}</div>
        {delta_html}
    </div>
    """

def render_section_header(title, subtitle=None):
    """
    Standardized header for sections.
    """
    subtitle_html = f'<div style="color: var(--text-muted); font-size: 0.95rem; margin-bottom: 1.5rem;">{subtitle}</div>' if subtitle else ""
    return f"""
    <div style="margin-bottom: 1.5rem;">
        <h2 style="color: var(--text-main); font-weight: 700; margin-bottom: 0.2rem;">{title}</h2>
        {subtitle_html}
    </div>
    """
