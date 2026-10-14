import streamlit as st
import requests
import json
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    OrderBy,
)
from google.oauth2 import service_account

# --- FUNKCJA OBLICZANIA ZMIANY PROCENTOWEJ (DELTA) ---
def calc_delta(curr, prev):
    if prev is None or prev == 0:
        return None
    pct = ((curr - prev) / prev) * 100
    return f"{pct:+.1f}% vs poprz."

# --- BAZA WSPÓŁRZĘDNYCH GŁÓWNYCH MIAST ---
CITY_COORDS = {
    "warszawa": (52.2297, 21.0122), "warsaw": (52.2297, 21.0122),
    "krakow": (50.0647, 19.9450), "kraków": (50.0647, 19.9450),
    "plock": (52.5463, 19.7065), "płock": (52.5463, 19.7065),
    "wroclaw": (51.1079, 17.0385), "wrocław": (51.1079, 17.0385),
    "poznan": (52.4064, 16.9252), "poznań": (52.4064, 16.9252),
    "gdansk": (54.3520, 18.6466), "gdańsk": (54.3520, 18.6466),
    "lodz": (51.7592, 19.4560), "łódź": (51.7592, 19.4560),
    "szczecin": (53.4285, 14.5528), "bydgoszcz": (53.1235, 18.0084),
    "lublin": (51.2465, 22.5684), "bialystok": (53.1325, 23.1688), "białystok": (53.1325, 23.1688),
    "katowice": (50.2649, 19.0238), "gdynia": (54.5189, 18.5305),
    "czestochowa": (50.8118, 19.1203), "częstochowa": (50.8118, 19.1203),
    "radom": (51.4027, 21.1471), "torun": (53.0138, 18.5984), "toruń": (53.0138, 18.5984),
    "sosnowiec": (50.2863, 19.1041), "kielce": (50.8661, 20.6286),
    "rzeszow": (50.0412, 21.9991), "rzeszów": (50.0412, 21.9991),
    "gliwice": (50.2945, 18.6714), "zabrze": (50.3249, 18.7857),
    "olsztyn": (53.7784, 20.4801), "bielsko-biala": (49.8225, 19.0444), "bielsko-biała": (49.8225, 19.0444),
    "bytom": (50.3480, 18.9157), "zielona gora": (51.9356, 15.5062), "zielona góra": (51.9356, 15.5062),
    "rybnik": (50.1022, 18.5463), "ruda slaska": (50.2574, 18.8559), "ruda śląska": (50.2574, 18.8559),
    "opole": (50.6751, 17.9213), "tychy": (50.1264, 18.9866),
    "gorzow wielkopolski": (52.7368, 15.2288), "gorzów wielkopolski": (52.7368, 15.2288),
    "dabrowa gornicza": (50.3204, 19.1912), "dąbrowa górnicza": (50.3204, 19.1912),
    "elblag": (54.1522, 19.4088), "elbląg": (54.1522, 19.4088),
    "walbrzych": (50.7813, 16.2847), "wałbrzych": (50.7813, 16.2847),
    "wloclawek": (52.6483, 19.0678), "włocławek": (52.6483, 19.0678),
    "tarnow": (50.0121, 20.9858), "tarnów": (50.0121, 20.9858),
    "chorzow": (50.2975, 18.9546), "chorzów": (50.2975, 18.9546),
    "koszalin": (54.1944, 16.1722), "kalisz": (51.7673, 18.0853),
    "legnica": (51.2070, 16.1552), "grudziadz": (53.4841, 18.7537), "grudziądz": (53.4841, 18.7537),
    "jaworzno": (50.2052, 19.2748), "slupsk": (54.4641, 17.0285), "słupsk": (54.4641, 17.0285),
    "jastrzebie-zdroj": (49.9535, 18.5833), "jastrzębie-zdrój": (49.9535, 18.5833),
    "nowy sacz": (49.6218, 20.6971), "nowy sącz": (49.6218, 20.6971),
    "jelenia gora": (50.9044, 15.7194), "jelenia góra": (50.9044, 15.7194),
    "siedlce": (52.1677, 22.2901), "konin": (52.2234, 18.2512),
    "piotrkow trybunalski": (51.4052, 19.7032), "piotrków trybunalski": (51.4052, 19.7032),
    "myslowice": (50.2078, 19.1664), "mysłowice": (50.2078, 19.1664),
    "inowroclaw": (52.7938, 18.2612), "inowrocław": (52.7938, 18.2612),
    "lubin": (51.3984, 16.2008), "ostrow wielkopolski": (51.6550, 17.8068), "ostrów wielkopolski": (51.6550, 17.8068),
    "suwalki": (54.1118, 22.9308), "suwałki": (54.1118, 22.9308),
    "gniezno": (52.5348, 17.5826), "stargard": (53.3386, 15.0449),
    "glogow": (51.6635, 16.0845), "głogów": (51.6635, 16.0845),
    "pabianice": (51.6645, 19.3562), "zamosc": (50.7231, 23.2520), "zamość": (50.7231, 23.2520),
    "leszno": (51.8427, 16.5749), "chelm": (51.1307, 23.4716), "chełm": (51.1307, 23.4716),
    "lomza": (53.1781, 22.0594), "łomża": (53.1781, 22.0594),
    "przemysl": (49.7839, 22.7678), "przemyśl": (49.7839, 22.7678),
    "mielec": (50.2871, 21.4239), "tczew": (54.0924, 18.7777),
    "pruszkow": (52.1679, 20.8122), "pruszków": (52.1679, 20.8122),
    "ostroleka": (53.0857, 21.5742), "ostrołęka": (53.0857, 21.5742),
    "piaseczno": (52.0743, 21.0267), "ciechanow": (52.8794, 20.6186), "ciechanów": (52.8794, 20.6186),
    "sierpc": (52.8550, 19.6738), "gostynin": (52.4287, 19.4627),
    "kutno": (52.2327, 19.3644), "lowicz": (52.1069, 19.9469), "łowicz": (52.1069, 19.9469),
    "berlin": (52.5200, 13.4050), "london": (51.5074, -0.1278), "londyn": (51.5074, -0.1278),
    "frankfurt": (50.1109, 8.6821), "vienna": (48.2082, 16.3738), "wiedeń": (48.2082, 16.3738),
    "prague": (50.0755, 14.4378), "praga": (50.0755, 14.4378),
    "kyiv": (50.4501, 30.5234), "kijów": (50.4501, 30.5234),
}

# --- KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="RUSTEC™ Analytics",
    page_icon="https://rustec.pl/assets/logo-sygnet.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)

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

# --- SYSTEM LOGOWANIA ---
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

# --- CLOUDFLARE Z PORÓWNANIEM POPRZEDNIEGO OKRESU ---
@st.cache_data(ttl=300)
def fetch_cloudflare_data(days=7):
    if "CF_API_TOKEN" not in st.secrets or "CF_ZONE_ID" not in st.secrets:
        return None, None, None, "Brak klucza CF_API_TOKEN lub CF_ZONE_ID"
    
    token = st.secrets["CF_API_TOKEN"].strip()
    zone_id = st.secrets["CF_ZONE_ID"].strip()
    
    now = datetime.utcnow()
    # Pobieramy dwa okresy (bieżący i poprzedni o tej samej długości)
    start_date = (now - timedelta(days=days*2)).strftime("%Y-%m-%d")
    split_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    query = """
    query CloudflareDailyMetrics($zoneTag: String!, $startDate: Date!, $endDate: Date!) {
      viewer {
        zones(filter: { zoneTag: $zoneTag }) {
          httpRequests1dGroups(
            limit: 100
            filter: { date_geq: $startDate, date_lt: $endDate }
            orderBy: [date_ASC]
          ) {
            dimensions {
              date
            }
            sum {
              requests
              pageViews
              threats
              bytes
            }
            uniq {
              uniques
            }
          }
        }
      }
    }
    """
    
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    try:
        response = requests.post(
            "https://api.cloudflare.com/client/v4/graphql",
            json={"query": query, "variables": {"zoneTag": zone_id, "startDate": start_date, "endDate": end_date}},
            headers=headers,
            timeout=10
        )
        res = response.json()
        if res.get("errors"):
            return None, None, None, f"Cloudflare: {res['errors'][0].get('message')}"
        
        groups = res.get("data", {}).get("viewer", {}).get("zones", [{}])[0].get("httpRequests1dGroups", [])
        
        # Podział na okres bieżący i poprzedni
        curr_groups = [g for g in groups if g.get("dimensions", {}).get("date") >= split_date]
        prev_groups = [g for g in groups if g.get("dimensions", {}).get("date") < split_date]
        
        curr = {
            "requests": sum(g.get("sum", {}).get("requests", 0) for g in curr_groups),
            "bandwidth_mb": round(sum(g.get("sum", {}).get("bytes", 0) for g in curr_groups) / (1024 * 1024), 2),
            "uniques": sum(g.get("uniq", {}).get("uniques", 0) for g in curr_groups),
            "threats": sum(g.get("sum", {}).get("threats", 0) for g in curr_groups),
        }
        prev = {
            "requests": sum(g.get("sum", {}).get("requests", 0) for g in prev_groups),
            "bandwidth_mb": round(sum(g.get("sum", {}).get("bytes", 0) for g in prev_groups) / (1024 * 1024), 2),
            "uniques": sum(g.get("uniq", {}).get("uniques", 0) for g in prev_groups),
            "threats": sum(g.get("sum", {}).get("threats", 0) for g in prev_groups),
        }
        
        deltas = {
            "requests": calc_delta(curr["requests"], prev["requests"]),
            "bandwidth": calc_delta(curr["bandwidth_mb"], prev["bandwidth_mb"]),
            "uniques": calc_delta(curr["uniques"], prev["uniques"]),
            "threats": calc_delta(curr["threats"], prev["threats"]),
        }
        
        daily_data = [
            {
                "Data": g.get("dimensions", {}).get("date"),
                "Zapytania": g.get("sum", {}).get("requests", 0),
                "Unikalni goście": g.get("uniq", {}).get("uniques", 0),
            }
            for g in curr_groups
        ]
        
        return curr, deltas, daily_data, None
    except Exception as e:
        return None, None, None, str(e)

# --- GOOGLE ANALYTICS 4 Z PORÓWNANIEM POPRZEDNIEGO OKRESU ---
@st.cache_data(ttl=300)
def fetch_ga4_data(days=7):
    if "gcp_service_account" not in st.secrets or "GA4_PROPERTY_ID" not in st.secrets:
        return None, None, None, None, None, "Brak poświadczeń GA4"
    
    try:
        sa_info = dict(st.secrets["gcp_service_account"])
        credentials = service_account.Credentials.from_service_account_info(sa_info)
        client = BetaAnalyticsDataClient(credentials=credentials)
        property_id = str(st.secrets["GA4_PROPERTY_ID"]).strip()

        # 1. Bieżący okres
        curr_res = client.run_report(RunReportRequest(
            property=f"properties/{property_id}",
            metrics=[
                Metric(name="activeUsers"),
                Metric(name="sessions"),
                Metric(name="screenPageViews"),
                Metric(name="engagementRate"),
            ],
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
        ))

        # 2. Poprzedni okres (porównanie)
        prev_res = client.run_report(RunReportRequest(
            property=f"properties/{property_id}",
            metrics=[
                Metric(name="activeUsers"),
                Metric(name="sessions"),
                Metric(name="screenPageViews"),
                Metric(name="engagementRate"),
            ],
            date_ranges=[DateRange(start_date=f"{days*2}daysAgo", end_date=f"{days+1}daysAgo")],
        ))
        
        curr_vals = [int(curr_res.rows[0].metric_values[0].value), int(curr_res.rows[0].metric_values[1].value), int(curr_res.rows[0].metric_values[2].value), float(curr_res.rows[0].metric_values[3].value)] if curr_res.rows else [0,0,0,0]
        prev_vals = [int(prev_res.rows[0].metric_values[0].value), int(prev_res.rows[0].metric_values[1].value), int(prev_res.rows[0].metric_values[2].value), float(prev_res.rows[0].metric_values[3].value)] if prev_res.rows else [0,0,0,0]

        summary = {
            "active_users": curr_vals[0],
            "sessions": curr_vals[1],
            "pageviews": curr_vals[2],
            "engagement_rate": f"{curr_vals[3]*100:.1f}%",
        }
        
        deltas = {
            "active_users": calc_delta(curr_vals[0], prev_vals[0]),
            "sessions": calc_delta(curr_vals[1], prev_vals[1]),
            "pageviews": calc_delta(curr_vals[2], prev_vals[2]),
            "engagement_rate": f"{(curr_vals[3] - prev_vals[3])*100:+.1f} p.p." if prev_vals[3] else None,
        }

        # 3. MIASTA
        cities_res = client.run_report(RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="city")],
            metrics=[Metric(name="activeUsers"), Metric(name="sessions")],
            order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="activeUsers"), desc=True)],
            limit=40,
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
        ))
        
        cities = []
        for r in cities_res.rows:
            city_name = r.dimension_values[0].value
            if city_name and city_name != "(not set)":
                users = int(r.metric_values[0].value)
                sess = int(r.metric_values[1].value)
                coords = CITY_COORDS.get(city_name.lower())
                lat = coords[0] if coords else None
                lon = coords[1] if coords else None
                cities.append({
                    "Miasto": city_name,
                    "Użytkownicy": users,
                    "Sesje": sess,
                    "latitude": lat,
                    "longitude": lon
                })

        # 4. Źródła
        sources_res = client.run_report(RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="sessionDefaultChannelGroup")],
            metrics=[Metric(name="sessions")],
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
        ))
        sources = [{"Kanał": r.dimension_values[0].value, "Sesje": int(r.metric_values[0].value)} for r in sources_res.rows]

        # 5. Urządzenia
        devices_res = client.run_report(RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="deviceCategory")],
            metrics=[Metric(name="sessions")],
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
        ))
        devices = [{"Urządzenie": r.dimension_values[0].value, "Sesje": int(r.metric_values[0].value)} for r in devices_res.rows]

        return summary, deltas, cities, sources, devices, None
    except Exception as e:
        return None, None, None, None, None, str(e)

# --- NAGŁÓWEK DASHBOARDU ---
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

cf_data, cf_deltas, cf_daily, cf_err = fetch_cloudflare_data(days)
ga_summary, ga_deltas, ga_cities, ga_sources, ga_devices, ga_err = fetch_ga4_data(days)

# --- SEKCJA GOOGLE ANALYTICS 4 (Z PORÓWNANIEM) ---
st.markdown("### 👥 Użytkownicy i zachowanie (Google Analytics 4)")
if ga_err:
    st.info(f"ℹ️ {ga_err}")
elif ga_summary:
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Użytkownicy", ga_summary["active_users"], delta=ga_deltas.get("active_users"))
    kpi2.metric("Sesje", ga_summary["sessions"], delta=ga_deltas.get("sessions"))
    kpi3.metric("Odsłony stron", ga_summary["pageviews"], delta=ga_deltas.get("pageviews"))
    kpi4.metric("Zaangażowanie", ga_summary["engagement_rate"], delta=ga_deltas.get("engagement_rate"))

# --- SEKCJA CLOUDFLARE (Z PORÓWNANIEM) ---
st.markdown("### 🛡️ Ruch sieciowy (Cloudflare)")
if cf_err:
    st.error(f"⚠️ {cf_err}")
elif cf_data:
    cf1, cf2, cf3, cf4 = st.columns(4)
    cf1.metric("Unikalne IP", cf_data["uniques"], delta=cf_deltas.get("uniques"))
    cf2.metric("Wszystkie żądania", cf_data["requests"], delta=cf_deltas.get("requests"))
    cf3.metric("Transfer", f"{cf_data['bandwidth_mb']} MB", delta=cf_deltas.get("bandwidth"))
    cf4.metric("Zablokowane ataki", cf_data["threats"], delta=cf_deltas.get("threats"), delta_color="inverse")
    
    if cf_daily and len(cf_daily) > 1:
        df_cf = pd.DataFrame(cf_daily)
        fig_cf = px.bar(df_cf, x="Data", y="Zapytania", hover_data=["Unikalni goście"], color_discrete_sequence=["#f97316"])
        fig_cf.update_layout(
            margin=dict(t=20, b=10, l=10, r=10),
            height=230,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False),
            yaxis=dict(gridcolor="#1e293b")
        )
        st.plotly_chart(fig_cf, use_container_width=True)

# --- MAPA I RANKING MIAST ---
st.markdown("---")
st.markdown("### 🗺️ Skąd wchodzą goście? (Mapa miast)")

if ga_cities:
    df_all_cities = pd.DataFrame(ga_cities)
    df_map = df_all_cities.dropna(subset=["latitude", "longitude"])
    
    if not df_map.empty:
        st.map(
            df_map,
            latitude="latitude",
            longitude="longitude",
            size="Użytkownicy",
            color="#f97316",
            zoom=5.2
        )
    
    col_t1, col_t2 = st.columns([1, 1])
    with col_t1:
        st.markdown("#### 🏆 Ranking miast (Top)")
        st.dataframe(df_all_cities[["Miasto", "Użytkownicy", "Sesje"]], hide_index=True, use_container_width=True)
    with col_t2:
        top_cities = df_all_cities.head(8)
        fig_city = px.bar(
            top_cities,
            x="Użytkownicy",
            y="Miasto",
            orientation="h",
            color_discrete_sequence=["#f97316"],
        )
        fig_city.update_layout(
            yaxis=dict(autorange="reversed"),
            margin=dict(t=10, b=10, l=10, r=10),
            height=260,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False),
            yaxis_title=None
        )
        st.plotly_chart(fig_city, use_container_width=True)

# --- ŹRÓDŁA I URZĄDZENIA ---
st.markdown("---")
col_channels, col_devices = st.columns(2)

with col_channels:
    st.markdown("#### 🎯 Główne źródła ruchu")
    if ga_sources:
        df_sources = pd.DataFrame(ga_sources)
        fig1 = px.pie(df_sources, values="Sesje", names="Kanał", hole=0.45, color_discrete_sequence=px.colors.qualitative.Prism)
        fig1.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=260, showlegend=True, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig1, use_container_width=True)

with col_devices:
    st.markdown("#### 📱 Urządzenia (Smartfon vs Komputer)")
    if ga_devices:
        df_devices = pd.DataFrame(ga_devices)
        fig2 = px.bar(df_devices, x="Urządzenie", y="Sesje", color="Urządzenie", color_discrete_sequence=px.colors.qualitative.Safe)
        fig2.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=260, showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig2, use_container_width=True)

if st.button("Wyloguj"):
    st.session_state["authenticated"] = False
    st.rerun()
