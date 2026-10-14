import streamlit as st
import requests
import json
import plotly.express as px
import pandas as pd
from datetime import datetime
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2 import service_account

# --- KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="RUSTEC™ Analytics",
    page_icon="https://rustec.pl/assets/logo-sygnet.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Stylizacja
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    div[data-testid="metric-container"] {
        background-color: #0f172a;
        border: 1px solid #1e293b;
        padding: 1rem;
        border-radius: 0.75rem;
    }
</style>
""", unsafe_allow_html=True)

# --- SYSTEM LOGOWANIA Z LOGO RUSTEC ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if st.session_state["authenticated"]:
        return True

    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; margin-bottom: 1.5rem;">
        <img src="https://rustec.pl/assets/logo-black.png" alt="RUSTEC" style="max-width: 280px; width: 85%; height: auto; border-radius: 10px;">
        <p style="color: #94a3b8; font-size: 0.95rem; margin-top: 10px; font-weight: 500;">Prywatny Panel Analityczny</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pin = st.text_input("Wprowadź PIN dostępu:", type="password")
        if st.button("Zaloguj się", use_container_width=True):
            correct_pin = st.secrets.get("APP_PIN", "1234")
            if pin == correct_pin:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Nieprawidłowy kod PIN.")
    return False

if not check_password():
    st.stop()

# --- POBIERANIE DANYCH Z CLOUDFLARE ---
@st.cache_data(ttl=300)
def fetch_cloudflare_data(since_minutes=10080):
    if "CF_API_TOKEN" not in st.secrets or "CF_ZONE_ID" not in st.secrets:
        return None, "Brak klucza CF_API_TOKEN lub CF_ZONE_ID w Streamlit Secrets"
    
    token = st.secrets["CF_API_TOKEN"].strip()
    zone_id = st.secrets["CF_ZONE_ID"].strip()
    
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/analytics/dashboard?since=-{since_minutes}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        if not res.get("success"):
            errors = res.get("errors", [])
            err_msg = ", ".join([f"{e.get('code')}: {e.get('message')}" for e in errors]) if errors else "Odrzucono zapytanie"
            return None, f"Cloudflare API: {err_msg}"
        
        totals = res["result"]["totals"]
        return {
            "requests": totals["requests"]["all"],
            "bandwidth_mb": round(totals["bandwidth"]["all"] / (1024 * 1024), 2),
            "uniques": totals["uniques"]["all"],
            "threats": totals["threats"]["all"],
        }, None
    except Exception as e:
        return None, str(e)

# --- POBIERANIE DANYCH Z GOOGLE ANALYTICS 4 ---
@st.cache_data(ttl=300)
def fetch_ga4_data(days=7):
    if "gcp_service_account" not in st.secrets or "GA4_PROPERTY_ID" not in st.secrets:
        return None, None, None, "Brak poświadczeń GA4 w Secrets (podłączymy w kolejnym kroku)"
    
    try:
        sa_info = dict(st.secrets["gcp_service_account"])
        credentials = service_account.Credentials.from_service_account_info(sa_info)
        client = BetaAnalyticsDataClient(credentials=credentials)
        property_id = str(st.secrets["GA4_PROPERTY_ID"]).strip()

        metrics_req = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[],
            metrics=[
                Metric(name="activeUsers"),
                Metric(name="sessions"),
                Metric(name="screenPageViews"),
                Metric(name="engagementRate"),
                Metric(name="averageSessionDuration"),
            ],
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
        )
        metrics_res = client.run_report(metrics_req)
        
        summary = {}
        if metrics_res.rows:
            row = metrics_res.rows[0]
            summary = {
                "active_users": int(row.metric_values[0].value),
                "sessions": int(row.metric_values[1].value),
                "pageviews": int(row.metric_values[2].value),
                "engagement_rate": f"{float(row.metric_values[3].value)*100:.1f}%",
                "avg_duration": f"{int(float(row.metric_values[4].value))}s",
            }

        sources_req = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="sessionDefaultChannelGroup")],
            metrics=[Metric(name="sessions")],
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
        )
        sources_res = client.run_report(sources_req)
        sources = [
            {"Kanał": r.dimension_values[0].value, "Sesje": int(r.metric_values[0].value)}
            for r in sources_res.rows
        ]

        device_req = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="deviceCategory")],
            metrics=[Metric(name="sessions")],
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
        )
        device_res = client.run_report(device_req)
        devices = [
            {"Urządzenie": r.dimension_values[0].value, "Sesje": int(r.metric_values[0].value)}
            for r in device_res.rows
        ]

        return summary, sources, devices, None
    except Exception as e:
        return None, None, None, str(e)

# --- NAGŁÓWEK DASHBOARDU Z LOGO RUSTEC ---
col_head, col_filter = st.columns([3, 1])
with col_head:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 8px;">
        <img src="https://rustec.pl/assets/logo-black.png" alt="RUSTEC" style="height: 44px; border-radius: 6px;">
        <div style="border-left: 2px solid #f97316; padding-left: 12px;">
            <div style="font-weight: 700; font-size: 1.25rem; color: #f8fafc; line-height: 1.2;">Live Analytics</div>
            <div style="font-size: 0.78rem; color: #94a3b8;">Cloudflare & Google Analytics 4</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.caption(f"Synchronizacja: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

with col_filter:
    period = st.selectbox("Zakres czasu", ["Ostatnie 24 godziny", "Ostatnie 7 dni", "Ostatnie 30 dni"], index=1)
    days_map = {"Ostatnie 24 godziny": 1, "Ostatnie 7 dni": 7, "Ostatnie 30 dni": 30}
    days = days_map[period]
    since_minutes = days * 24 * 60

cf_data, cf_err = fetch_cloudflare_data(since_minutes)
ga_summary, ga_sources, ga_devices, ga_err = fetch_ga4_data(days)

# --- SEKCJA CLOUDFLARE ---
st.markdown("### 🛡️ Cloudflare")
if cf_err:
    st.error(f"⚠️ {cf_err}")
elif cf_data:
    cf1, cf2, cf3, cf4 = st.columns(4)
    cf1.metric("Unikalne IP", cf_data["uniques"])
    cf2.metric("Wszystkie żądania", cf_data["requests"])
    cf3.metric("Transfer", f"{cf_data['bandwidth_mb']} MB")
    cf4.metric("Zablokowane ataki", cf_data["threats"], delta_color="inverse")

# --- SEKCJA GOOGLE ANALYTICS 4 ---
st.markdown("### 👥 Google Analytics 4")
if ga_err:
    st.info(f"ℹ️ {ga_err}")
elif ga_summary:
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Użytkownicy", ga_summary["active_users"])
    kpi2.metric("Sesje", ga_summary["sessions"])
    kpi3.metric("Wyświetlenia stron", ga_summary["pageviews"])
    kpi4.metric("Zaangażowanie", ga_summary["engagement_rate"], help=f"Śr. czas: {ga_summary['avg_duration']}")

# --- WYKRESY ---
st.markdown("---")
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("#### 🎯 Główne źródła ruchu")
    if ga_sources:
        df_sources = pd.DataFrame(ga_sources)
        fig1 = px.pie(df_sources, values="Sesje", names="Kanał", hole=0.45, color_discrete_sequence=px.colors.qualitative.Prism)
        fig1.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=True, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.caption("Wykres pojawi się po podłączeniu GA4.")

with chart_col2:
    st.markdown("#### 📱 Urządzenia")
    if ga_devices:
        df_devices = pd.DataFrame(ga_devices)
        fig2 = px.bar(df_devices, x="Urządzenie", y="Sesje", color="Urządzenie", color_discrete_sequence=px.colors.qualitative.Safe)
        fig2.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.caption("Wykres pojawi się po podłączeniu GA4.")

if st.button("Wyloguj"):
    st.session_state["authenticated"] = False
    st.rerun()
