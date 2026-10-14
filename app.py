import streamlit as st
import requests
import json
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    RunRealtimeReportRequest,
    OrderBy,
)
from google.oauth2 import service_account

# --- FUNKCJE POMOCNICZE ---
def calc_delta(curr, prev):
    if prev is None or prev == 0:
        return ""
    pct = ((curr - prev) / prev) * 100
    return f"{pct:+.1f}%"

def format_ga_datetime(d_str):
    if not d_str:
        return ""
    d_str = str(d_str).strip()
    if len(d_str) == 12:  # YYYYMMDDHHMM
        return f"{d_str[6:8]}.{d_str[4:6]}.{d_str[0:4]} {d_str[8:10]}:{d_str[10:12]}"
    elif len(d_str) == 10:  # YYYYMMDDHH
        return f"{d_str[6:8]}.{d_str[4:6]}.{d_str[0:4]} {d_str[8:10]}:00"
    elif len(d_str) == 8:  # YYYYMMDD
        return f"{d_str[6:8]}.{d_str[4:6]}.{d_str[0:4]}"
    return d_str

# Słownik flag i tłumaczeń państw
COUNTRY_FLAGS = {
    "poland": ("Polska", "🇵🇱"), "polska": ("Polska", "🇵🇱"),
    "germany": ("Niemcy", "🇩🇪"), "niemcy": ("Niemcy", "🇩🇪"),
    "united kingdom": ("Wielka Brytania", "🇬🇧"),
    "united states": ("Stany Zjednoczone", "🇺🇸"), "usa": ("Stany Zjednoczone", "🇺🇸"),
    "ukraine": ("Ukraina", "🇺🇦"), "ukraina": ("Ukraina", "🇺🇦"),
    "france": ("Francja", "🇫🇷"), "francja": ("Francja", "🇫🇷"),
    "netherlands": ("Holandia", "🇳🇱"), "holandia": ("Holandia", "🇳🇱"),
    "norway": ("Norwegia", "🇳🇴"), "norwegia": ("Norwegia", "🇳🇴"),
    "czechia": ("Czechy", "🇨🇿"), "czech republic": ("Czechy", "🇨🇿"),
    "sweden": ("Szwecja", "🇸🇪"), "spain": ("Hiszpania", "🇪🇸"),
    "italy": ("Włochy", "🇮🇹"), "denmark": ("Dania", "🇩🇰"),
    "ireland": ("Irlandia", "🇮🇪"), "belgium": ("Belgia", "🇧🇪"),
    "austria": ("Austria", "🇦🇹"), "switzerland": ("Szwajcaria", "🇨🇭"),
    "slovakia": ("Słowacja", "🇸🇰"), "lithuania": ("Litwa", "🇱🇹"),
    "finland": ("Finlandia", "🇫🇮"), "canada": ("Kanada", "🇨🇦"),
}

def get_country_info(raw_country):
    if not raw_country or raw_country == "(not set)":
        return "Polska", "🇵🇱"
    c_low = raw_country.lower().strip()
    if c_low in COUNTRY_FLAGS:
        return COUNTRY_FLAGS[c_low]
    return raw_country, "🌐"

COUNTRY_DEFAULT_COORDS = {
    "poland": (52.2297, 21.0122), "germany": (52.5200, 13.4050),
    "united kingdom": (51.5074, -0.1278), "united states": (38.8951, -77.0364),
    "ukraine": (50.4501, 30.5234), "france": (48.8566, 2.3522),
    "netherlands": (52.3676, 4.9041), "norway": (59.9139, 10.7522),
    "czechia": (50.0755, 14.4378), "sweden": (59.3293, 18.0686),
}

CHANNEL_TRANSLATION = {
    "Organic Search": "Google (Wyszukiwarka)",
    "Direct": "Bezpośrednio (wpisany URL)",
    "Organic Social": "Social Media (FB / IG)",
    "Referral": "Link z innej witryny",
    "Paid Search": "Płatne reklamy Google",
    "Unassigned": "Inne źródło",
}

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
    "sierpc": (52.8550, 19.6738), "gostynin": (52.4287, 19.4627), "kutno": (52.2327, 19.3644),
    "lowicz": (52.1069, 19.9469), "łowicz": (52.1069, 19.9469),
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
<link rel="apple-touch-icon" sizes="180x180" href="https://rustec.pl/assets/logo-sygnet.png">
<link rel="icon" type="image/png" href="https://rustec.pl/assets/logo-sygnet.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="RUSTEC">
<meta name="mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#0f172a">
<style>
    /* Bezpieczny odstęp od góry, aby pasek Streamlit nigdy nie obcinał logo ani napisów */
    .block-container {
        padding-top: 4.8rem !important;
        padding-bottom: 2.5rem !important;
    }
    @media (max-width: 768px) {
        .block-container {
            padding-top: 5.2rem !important;
        }
    }
    header[data-testid="stHeader"] {
        background: transparent !important;
    }
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

# --- POBIERANIE DANYCH NA ŻYWO (REAL-TIME - OSTATNIE 30 MIN) ---
@st.cache_data(ttl=15)
def fetch_ga4_realtime():
    if "gcp_service_account" not in st.secrets or "GA4_PROPERTY_ID" not in st.secrets:
        return 0, [], {}, None
    try:
        sa_info = dict(st.secrets["gcp_service_account"])
        credentials = service_account.Credentials.from_service_account_info(sa_info)
        client = BetaAnalyticsDataClient(credentials=credentials)
        property_id = str(st.secrets["GA4_PROPERTY_ID"]).strip()

        # 1. Raport ogólny: aktualnie aktywni oraz miasta
        req_total = RunRealtimeReportRequest(
            property=f"properties/{property_id}",
            metrics=[Metric(name="activeUsers")],
            dimensions=[Dimension(name="city"), Dimension(name="country")],
        )
        res_total = client.run_realtime_report(req_total)

        total_users = sum(int(r.metric_values[0].value) for r in res_total.rows) if res_total.rows else 0
        active_cities = []
        for r in res_total.rows:
            cname = r.dimension_values[0].value
            c_country = r.dimension_values[1].value
            users_count = int(r.metric_values[0].value)
            if cname and cname != "(not set)":
                _, flag = get_country_info(c_country)
                active_cities.append(f"{cname} {flag} ({users_count})")

        # 2. Raport minutowy: szczegółowy rozkład co do minuty z miastem i urządzeniem
        minutes_data = {m: [] for m in range(30)}
        try:
            req_min = RunRealtimeReportRequest(
                property=f"properties/{property_id}",
                metrics=[Metric(name="activeUsers")],
                dimensions=[
                    Dimension(name="minutesAgo"),
                    Dimension(name="city"),
                    Dimension(name="country"),
                    Dimension(name="deviceCategory"),
                ],
            )
            res_min = client.run_realtime_report(req_min)
            for r in res_min.rows:
                try:
                    m_ago = int(r.dimension_values[0].value)
                except (ValueError, TypeError):
                    continue
                cname = r.dimension_values[1].value
                ccountry = r.dimension_values[2].value
                device = r.dimension_values[3].value if len(r.dimension_values) > 3 else ""
                u_cnt = int(r.metric_values[0].value) if r.metric_values else 0

                dev_lower = device.lower()
                if "mobile" in dev_lower:
                    dev_label = "📱 Smartfon"
                elif "desktop" in dev_lower:
                    dev_label = "💻 Komputer"
                elif "tablet" in dev_lower:
                    dev_label = "📟 Tablet"
                elif device:
                    dev_label = f"🖥️ {device}"
                else:
                    dev_label = ""

                c_trans, flag = get_country_info(ccountry)
                loc_label = f"{cname} {flag}" if (cname and cname != "(not set)") else f"{c_trans} {flag}"

                if 0 <= m_ago < 30:
                    minutes_data[m_ago].append({
                        "location": loc_label,
                        "device": dev_label,
                        "users": u_cnt,
                    })
        except Exception:
            # Fallback bez wymiaru deviceCategory
            try:
                req_min = RunRealtimeReportRequest(
                    property=f"properties/{property_id}",
                    metrics=[Metric(name="activeUsers")],
                    dimensions=[
                        Dimension(name="minutesAgo"),
                        Dimension(name="city"),
                        Dimension(name="country"),
                    ],
                )
                res_min = client.run_realtime_report(req_min)
                for r in res_min.rows:
                    try:
                        m_ago = int(r.dimension_values[0].value)
                    except (ValueError, TypeError):
                        continue
                    cname = r.dimension_values[1].value
                    ccountry = r.dimension_values[2].value
                    u_cnt = int(r.metric_values[0].value) if r.metric_values else 0

                    c_trans, flag = get_country_info(ccountry)
                    loc_label = f"{cname} {flag}" if (cname and cname != "(not set)") else f"{c_trans} {flag}"

                    if 0 <= m_ago < 30:
                        minutes_data[m_ago].append({
                            "location": loc_label,
                            "device": "",
                            "users": u_cnt,
                        })
            except Exception:
                pass

        return total_users, active_cities, minutes_data, None
    except Exception as e:
        return 0, [], {}, str(e)

# --- CLOUDFLARE Z OBSŁUGĄ "DZIŚ" ORAZ OKRESÓW WSTECZ ---
@st.cache_data(ttl=300)
def fetch_cloudflare_data(days=7, is_today=False):
    if "CF_API_TOKEN" not in st.secrets or "CF_ZONE_ID" not in st.secrets:
        return None, None, None, "Brak klucza CF_API_TOKEN lub CF_ZONE_ID"
    
    token = st.secrets["CF_API_TOKEN"].strip()
    zone_id = st.secrets["CF_ZONE_ID"].strip()
    
    now = datetime.utcnow()
    if is_today:
        start_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        split_date = now.strftime("%Y-%m-%d")
        end_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
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
            dimensions { date }
            sum { requests pageViews threats bytes }
            uniq { uniques }
          }
        }
      }
    }
    """
    url = "https://api.cloudflare.com/client/v4/graphql"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"query": query, "variables": {"zoneTag": zone_id, "startDate": start_date, "endDate": end_date}}

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=12)
        res = r.json()
        if "errors" in res and res["errors"]:
            return None, None, None, f"Błąd Cloudflare: {res['errors'][0].get('message', 'Nieznany błąd')}"
        
        groups = res.get("data", {}).get("viewer", {}).get("zones", [{}])[0].get("httpRequests1dGroups", [])
        if not groups:
            return None, None, None, "Brak danych w wybranym okresie."
        
        curr_uniques, curr_reqs, curr_threats, curr_bytes = 0, 0, 0, 0
        prev_uniques, prev_reqs, prev_threats, prev_bytes = 0, 0, 0, 0
        
        curr_daily = {}
        prev_daily = {}
        
        for g in groups:
            d = g["dimensions"]["date"]
            u = g["uniq"]["uniques"]
            req = g["sum"]["requests"]
            thr = g["sum"]["threats"]
            byt = g["sum"]["bytes"]
            
            if is_today:
                if d == split_date:
                    curr_uniques += u
                    curr_reqs += req
                    curr_threats += thr
                    curr_bytes += byt
                elif d == start_date:
                    prev_uniques += u
                    prev_reqs += req
                    prev_threats += thr
                    prev_bytes += byt
            else:
                if d >= split_date:
                    curr_uniques += u
                    curr_reqs += req
                    curr_threats += thr
                    curr_bytes += byt
                    curr_daily[d] = req
                else:
                    prev_uniques += u
                    prev_reqs += req
                    prev_threats += thr
                    prev_bytes += byt
                    prev_daily[d] = req

        data = {
            "uniques": curr_uniques,
            "requests": curr_reqs,
            "threats": curr_threats,
            "bandwidth_mb": round(curr_bytes / (1024 * 1024), 2),
        }
        prev_data = {
            "uniques": prev_uniques,
            "requests": prev_reqs,
            "threats": prev_threats,
            "bandwidth_mb": round(prev_bytes / (1024 * 1024), 2),
        }

        deltas = {
            "uniques": f"{calc_delta(data['uniques'], prev_data['uniques'])} (było: {prev_data['uniques']:,})",
            "requests": f"{calc_delta(data['requests'], prev_data['requests'])} (było: {prev_data['requests']:,})",
            "threats": f"{calc_delta(data['threats'], prev_data['threats'])} (było: {prev_data['threats']:,})",
            "bandwidth": f"{calc_delta(data['bandwidth_mb'], prev_data['bandwidth_mb'])} (było: {prev_data['bandwidth_mb']} MB)",
        }
        
        comparison = []
        if not is_today and curr_daily:
            curr_sorted_dates = sorted(curr_daily.keys())
            prev_sorted_dates = sorted(prev_daily.keys())
            for i, c_date in enumerate(curr_sorted_dates):
                p_req = prev_daily.get(prev_sorted_dates[i], 0) if i < len(prev_sorted_dates) else 0
                p_date = prev_sorted_dates[i] if i < len(prev_sorted_dates) else ""
                comparison.append({
                    "Dzień": f"Dzień {i+1} ({c_date[-5:]})",
                    "Bieżący okres": curr_daily[c_date],
                    "Poprzedni okres": p_req,
                    "Data bieżąca": c_date,
                    "Data poprzednia": p_date,
                })

        return data, deltas, comparison, None
    except Exception as e:
        return None, None, None, f"Błąd połączenia z Cloudflare: {str(e)}"

# --- GOOGLE ANALYTICS 4 Z OBSŁUGĄ "DZIŚ" ORAZ PORÓWNANIEM ---
@st.cache_data(ttl=300)
def fetch_ga4_data(days=7, is_today=False):
    if "gcp_service_account" not in st.secrets or "GA4_PROPERTY_ID" not in st.secrets:
        return None, None, None, None, None, "Brak poświadczeń GA4"
    
    try:
        sa_info = dict(st.secrets["gcp_service_account"])
        credentials = service_account.Credentials.from_service_account_info(sa_info)
        client = BetaAnalyticsDataClient(credentials=credentials)
        property_id = str(st.secrets["GA4_PROPERTY_ID"]).strip()

        if is_today:
            curr_range = DateRange(start_date="today", end_date="today")
            prev_range = DateRange(start_date="yesterday", end_date="yesterday")
        else:
            curr_range = DateRange(start_date=f"{days}daysAgo", end_date="today")
            prev_range = DateRange(start_date=f"{days*2}daysAgo", end_date=f"{days+1}daysAgo")

        # 1. Bieżący okres
        curr_res = client.run_report(RunReportRequest(
            property=f"properties/{property_id}",
            metrics=[Metric(name="activeUsers"), Metric(name="sessions"), Metric(name="screenPageViews"), Metric(name="engagementRate")],
            date_ranges=[curr_range],
        ))

        # 2. Poprzedni okres
        prev_res = client.run_report(RunReportRequest(
            property=f"properties/{property_id}",
            metrics=[Metric(name="activeUsers"), Metric(name="sessions"), Metric(name="screenPageViews"), Metric(name="engagementRate")],
            date_ranges=[prev_range],
        ))
        
        curr_vals = [int(curr_res.rows[0].metric_values[0].value), int(curr_res.rows[0].metric_values[1].value), int(curr_res.rows[0].metric_values[2].value), float(curr_res.rows[0].metric_values[3].value)] if curr_res.rows else [0,0,0,0]
        prev_vals = [int(prev_res.rows[0].metric_values[0].value), int(prev_res.rows[0].metric_values[1].value), int(prev_res.rows[0].metric_values[2].value), float(prev_res.rows[0].metric_values[3].value)] if prev_res.rows else [0,0,0,0]

        summary = {"active_users": curr_vals[0], "sessions": curr_vals[1], "pageviews": curr_vals[2], "engagement_rate": f"{curr_vals[3]*100:.1f}%"}
        deltas = {
            "active_users": f"{calc_delta(curr_vals[0], prev_vals[0])} (było: {prev_vals[0]:,})",
            "sessions": f"{calc_delta(curr_vals[1], prev_vals[1])} (było: {prev_vals[1]:,})",
            "pageviews": f"{calc_delta(curr_vals[2], prev_vals[2])} (było: {prev_vals[2]:,})",
            "engagement_rate": f"{(curr_vals[3] - prev_vals[3])*100:+.1f} p.p. (było: {prev_vals[3]*100:.1f}%)" if prev_vals[3] else "",
        }

        # 3. MIASTA + KRAJ + DATA I DOKŁADNA GODZINA + ŹRÓDŁO
        try:
            cities_req = RunReportRequest(
                property=f"properties/{property_id}",
                dimensions=[
                    Dimension(name="city"),
                    Dimension(name="country"),
                    Dimension(name="dateHourMinute"),
                    Dimension(name="sessionDefaultChannelGroup"),
                ],
                metrics=[Metric(name="activeUsers"), Metric(name="sessions")],
                order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="dateHourMinute"), desc=True)],
                limit=1000,
                date_ranges=[curr_range],
            )
            cities_res = client.run_report(cities_req)
        except Exception:
            # Bezpieczny fallback do date w razie problemu z wymiarem
            cities_req = RunReportRequest(
                property=f"properties/{property_id}",
                dimensions=[
                    Dimension(name="city"),
                    Dimension(name="country"),
                    Dimension(name="date"),
                    Dimension(name="sessionDefaultChannelGroup"),
                ],
                metrics=[Metric(name="activeUsers"), Metric(name="sessions")],
                order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="activeUsers"), desc=True)],
                limit=500,
                date_ranges=[curr_range],
            )
            cities_res = client.run_report(cities_req)
        
        city_groups = {}
        for r in cities_res.rows:
            city_name = r.dimension_values[0].value
            country_raw = r.dimension_values[1].value
            if not city_name or city_name == "(not set)":
                continue
            
            date_str = r.dimension_values[2].value
            channel = r.dimension_values[3].value
            users = int(r.metric_values[0].value)
            sess = int(r.metric_values[1].value)
            
            country_name, flag = get_country_info(country_raw)
            city_key = f"{city_name}_{country_name}"
            
            if city_key not in city_groups:
                coords = CITY_COORDS.get(city_name.lower())
                if not coords and country_raw.lower() in COUNTRY_DEFAULT_COORDS:
                    coords = COUNTRY_DEFAULT_COORDS[country_raw.lower()]
                
                city_groups[city_key] = {
                    "Miasto": city_name,
                    "Kraj": country_name,
                    "Flaga": flag,
                    "Użytkownicy": 0,
                    "Sesje": 0,
                    "latest_date": date_str,
                    "channels": {},
                    "latitude": coords[0] if coords else None,
                    "longitude": coords[1] if coords else None,
                }
            
            city_groups[city_key]["Użytkownicy"] += users
            city_groups[city_key]["Sesje"] += sess
            if date_str > city_groups[city_key]["latest_date"]:
                city_groups[city_key]["latest_date"] = date_str
            city_groups[city_key]["channels"][channel] = city_groups[city_key]["channels"].get(channel, 0) + sess

        cities = []
        for ckey, cdata in city_groups.items():
            top_channel_raw = max(cdata["channels"], key=cdata["channels"].get) if cdata["channels"] else "Inne"
            top_channel = CHANNEL_TRANSLATION.get(top_channel_raw, top_channel_raw)
            formatted_date = format_ga_datetime(cdata["latest_date"])
            
            hover_html = (
                f"<b>📍 {cdata['Miasto']}, {cdata['Kraj']} {cdata['Flaga']}</b><br><br>"
                f"👥 <b>Odwiedzający:</b> {cdata['Użytkownicy']} osób<br>"
                f"🔄 <b>Liczba wizyt:</b> {cdata['Sesje']} sesji<br>"
                f"🕒 <b>Ostatnia wizyta:</b> {formatted_date}<br>"
                f"🎯 <b>Główne źródło:</b> {top_channel}"
            )
            
            cities.append({
                "Miasto": cdata["Miasto"],
                "Kraj": f"{cdata['Kraj']} {cdata['Flaga']}",
                "Użytkownicy": cdata["Użytkownicy"],
                "Sesje": cdata["Sesje"],
                "Kiedy": formatted_date,
                "Zrodlo": top_channel,
                "hover_text": hover_html,
                "latitude": cdata["latitude"],
                "longitude": cdata["longitude"],
            })

        cities = sorted(cities, key=lambda x: x["Użytkownicy"], reverse=True)

        # 4. Źródła
        sources_res = client.run_report(RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="sessionDefaultChannelGroup")],
            metrics=[Metric(name="sessions")],
            date_ranges=[curr_range],
        ))
        sources = [{"Kanał": CHANNEL_TRANSLATION.get(r.dimension_values[0].value, r.dimension_values[0].value), "Sesje": int(r.metric_values[0].value)} for r in sources_res.rows]

        # 5. Urządzenia
        devices_res = client.run_report(RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="deviceCategory")],
            metrics=[Metric(name="sessions")],
            date_ranges=[curr_range],
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
    period = st.selectbox(
        "Zakres czasu",
        ["Dzisiaj (vs Wczoraj)", "Ostatnie 24 godziny", "Ostatnie 7 dni", "Ostatnie 30 dni"],
        index=0
    )
    if period == "Dzisiaj (vs Wczoraj)":
        is_today = True
        days = 1
    elif period == "Ostatnie 24 godziny":
        is_today = False
        days = 1
    elif period == "Ostatnie 7 dni":
        is_today = False
        days = 7
    else:
        is_today = False
        days = 30

# --- SEKCJA REAL-TIME (WIZYTY NA ŻYWO) ---
realtime_users, realtime_cities, minutes_data, rt_err = fetch_ga4_realtime()

rt_col1, rt_col2 = st.columns([4, 1])
with rt_col1:
    cities_str = f" • Z miast: {', '.join(realtime_cities)}" if realtime_cities else ""
    st.markdown(f"""
    <div style="background: linear-gradient(90deg, #064e3b 0%, #022c22 100%); border: 1px solid #059669; border-radius: 12px; padding: 12px 18px; margin-bottom: 12px; display: flex; align-items: center; gap: 12px;">
        <span style="display: inline-block; width: 12px; height: 12px; background-color: #10b981; border-radius: 50%; box-shadow: 0 0 10px #10b981;"></span>
        <div>
            <span style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; color: #a7f3d0; font-weight: 700;">NA ŻYWO NA STRONIE (OSTATNIE 30 MIN)</span>
            <div style="font-size: 1.4rem; font-weight: 800; color: #ffffff;">{realtime_users} osób online <span style="font-size: 0.85rem; font-weight: 400; color: #6ee7b7;">{cities_str}</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with rt_col2:
    if st.button("🔄 Odśwież na żywo", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- WYKRES SŁUPKOWY W CZASIE RZECZYWISTYM (OD 0 DO -60 MIN / -30 MIN) ---
if not rt_err:
    rt_hdr1, rt_hdr2 = st.columns([3, 1])
    with rt_hdr1:
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-top: 4px; margin-bottom: 2px;">
            <span style="font-size: 0.95rem; font-weight: 700; color: #f1f5f9;">⏱️ Aktywność w czasie rzeczywistym (minuta po minucie)</span>
        </div>
        """, unsafe_allow_html=True)
    with rt_hdr2:
        rt_view = st.selectbox(
            "Zakres minut",
            ["Ostatnie 30 minut", "Ostatnie 60 minut"],
            index=0,
            label_visibility="collapsed"
        )

    max_mins = 60 if rt_view == "Ostatnie 60 minut" else 30
    range_mins = list(range(max_mins - 1, -1, -1))

    x_labels = []
    y_vals = []
    y_display = []
    tooltips = []
    bar_texts = []
    bar_colors = []
    bar_borders = []
    tick_vals = []
    tick_texts = []

    for m in range_mins:
        lbl = "Teraz" if m == 0 else f"-{m}m"
        x_labels.append(lbl)

        if max_mins == 30:
            if m % 5 == 0 or m == 29:
                tick_vals.append(lbl)
                tick_texts.append(lbl)
        else:
            if m % 10 == 0 or m == 59:
                tick_vals.append(lbl)
                tick_texts.append(lbl)

        m_desc = "Teraz (ta minuta)" if m == 0 else f"-{m} min temu"
        items = minutes_data.get(m, []) if (minutes_data and m < 30) else []
        u_count = sum(it.get("users", 0) for it in items)
        y_vals.append(u_count)

        if u_count > 0:
            y_display.append(u_count)
            bar_texts.append(str(u_count))
            bar_colors.append("#10b981")
            bar_borders.append("#34d399")

            lines = []
            for it in items:
                dev = it.get("device", "")
                dev_str = f" ({dev})" if dev else ""
                lines.append(f"• {it['location']}{dev_str}: <b>{it['users']} os.</b>")
            details = "<br>".join(lines)
            tt = f"<b>⏱️ Czas:</b> {m_desc}<br><b>👥 Aktywni:</b> {u_count} os.<br><b>📍 Kto i skąd:</b><br>{details}"
        else:
            y_display.append(0.04)
            bar_texts.append("")
            bar_colors.append("rgba(255, 255, 255, 0.08)")
            bar_borders.append("rgba(255, 255, 255, 0.12)")
            if m < 30:
                tt = f"<b>⏱️ Czas:</b> {m_desc}<br><b>👥 Brak aktywności (0 os.)</b>"
            else:
                tt = f"<b>⏱️ Czas:</b> {m_desc}<br><i>ℹ️ Bufor API GA4 Realtime obejmuje ostatnie 30 minut.<br>Starszy ruch (30-60 min) trafia do raportów ogólnych.</i>"
        tooltips.append(tt)

    max_y = max(y_vals) if y_vals else 0
    fig_rt = go.Figure()
    fig_rt.add_trace(go.Bar(
        x=x_labels,
        y=y_display,
        customdata=tooltips,
        hovertemplate="%{customdata}<extra></extra>",
        marker=dict(
            color=bar_colors,
            line=dict(color=bar_borders, width=1),
            cornerradius=4
        ),
        text=bar_texts,
        textposition="outside",
        textfont=dict(color="#ffffff", size=11, family="Inter, sans-serif"),
        cliponaxis=False,
    ))

    fig_rt.update_layout(
        height=190,
        margin=dict(l=5, r=5, t=20, b=25),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15, 23, 42, 0.4)",
        hovermode="x",
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            tickfont=dict(color="#94a3b8", size=10),
            tickmode="array",
            tickvals=tick_vals,
            ticktext=tick_texts,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(255,255,255,0.06)",
            zeroline=False,
            tickfont=dict(color="#94a3b8", size=9),
            dtick=1,
            rangemode="nonnegative",
            range=[0, max(max_y + 1.2, 2.5)],
        ),
        showlegend=False,
    )

    st.plotly_chart(fig_rt, use_container_width=True, config={"displayModeBar": False})
    st.markdown(
        "<p style='color: #64748b; font-size: 0.78rem; margin-top: -10px; margin-bottom: 22px;'>"
        "💡 <b>Wskazówka:</b> Najedź kursorem lub dotknij dowolnego słupka, aby zobaczyć dokładne miasto, państwo z flagą oraz urządzenie (komputer/smartfon). Zielone słupki oznaczają wykrytych użytkowników w danej minucie."
        "</p>",
        unsafe_allow_html=True
    )

# Pobieranie danych historycznych
cf_data, cf_deltas, cf_comparison, cf_err = fetch_cloudflare_data(days, is_today)
ga_summary, ga_deltas, ga_cities, ga_sources, ga_devices, ga_err = fetch_ga4_data(days, is_today)

# --- SEKCJA GOOGLE ANALYTICS 4 ---
st.markdown("### 👥 Użytkownicy i zachowanie (Google Analytics 4)")
if ga_err:
    st.info(f"ℹ️ {ga_err}")
elif ga_summary:
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Użytkownicy", ga_summary["active_users"], delta=ga_deltas.get("active_users"))
    kpi2.metric("Sesje", ga_summary["sessions"], delta=ga_deltas.get("sessions"))
    kpi3.metric("Odsłony stron", ga_summary["pageviews"], delta=ga_deltas.get("pageviews"))
    kpi4.metric("Zaangażowanie", ga_summary["engagement_rate"], delta=ga_deltas.get("engagement_rate"))

# --- SEKCJA CLOUDFLARE ---
st.markdown("### 🛡️ Ruch sieciowy (Cloudflare)")
if cf_err:
    st.error(f"⚠️ {cf_err}")
elif cf_data:
    cf1, cf2, cf3, cf4 = st.columns(4)
    cf1.metric("Unikalne IP", cf_data["uniques"], delta=cf_deltas.get("uniques"))
    cf2.metric("Wszystkie żądania", cf_data["requests"], delta=cf_deltas.get("requests"))
    cf3.metric("Transfer", f"{cf_data['bandwidth_mb']} MB", delta=cf_deltas.get("bandwidth"))
    cf4.metric("Zablokowane ataki", cf_data["threats"], delta=cf_deltas.get("threats"), delta_color="inverse")
    
    # --- WYKRES LINIOWY: PORÓWNANIE RUCHU BIEŻĄCY VS POPRZEDNI OKRES ---
    if cf_comparison and len(cf_comparison) > 1 and not is_today:
        st.markdown("#### 📈 Porównanie ruchu dzień po dniu (Bieżący vs Poprzedni okres)")
        fig_line = go.Figure()
        
        fig_line.add_trace(go.Scatter(
            x=[d["Dzień"] for d in cf_comparison],
            y=[d["Bieżący okres"] for d in cf_comparison],
            mode="lines+markers",
            name="Bieżący okres",
            line=dict(color="#f97316", width=3),
            marker=dict(size=7, color="#f97316"),
            customdata=[d["Data bieżąca"] for d in cf_comparison],
            hovertemplate="<b>Bieżący: %{y}</b> (%{customdata})<extra></extra>"
        ))
        
        fig_line.add_trace(go.Scatter(
            x=[d["Dzień"] for d in cf_comparison],
            y=[d["Poprzedni okres"] for d in cf_comparison],
            mode="lines+markers",
            name="Poprzedni okres",
            line=dict(color="#94a3b8", width=2, dash="dash"),
            marker=dict(size=5, color="#94a3b8"),
            customdata=[d["Data poprzednia"] for d in cf_comparison],
            hovertemplate="<b>Poprzedni: %{y}</b> (%{customdata})<extra></extra>"
        ))
        
        fig_line.update_layout(
            margin=dict(t=20, b=10, l=10, r=10),
            height=280,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#cbd5e1")),
            xaxis=dict(showgrid=False, color="#94a3b8"),
            yaxis=dict(gridcolor="#1e293b", color="#94a3b8")
        )
        st.plotly_chart(fig_line, use_container_width=True)

# --- INTERAKTYWNA MAPA Z BŁYSKAWICZNYMI DYMKAMI HOVER (PLOTLY 6) ---
st.markdown("---")
st.markdown("### 🗺️ Skąd wchodzą goście? (Najedź kursorem lub dotknij punktu)")

if ga_cities:
    df_all_cities = pd.DataFrame(ga_cities)
    df_map = df_all_cities.dropna(subset=["latitude", "longitude"])
    
    if not df_map.empty:
        sizes = [max(13, min(int(u * 2.2), 36)) for u in df_map["Użytkownicy"]]
        
        ScatterClass = getattr(go, "Scattermap", getattr(go, "Scattermapbox", None))
        map_key = "map" if hasattr(go, "Scattermap") else "mapbox"
        
        fig_map = go.Figure(ScatterClass(
            lat=df_map["latitude"],
            lon=df_map["longitude"],
            mode="markers",
            marker=dict(
                size=sizes,
                color="#f97316",
                opacity=0.88,
            ),
            text=df_map["hover_text"],
            hoverinfo="text",
            hoverlabel=dict(
                bgcolor="#0f172a",
                bordercolor="#f97316",
                font=dict(color="#f8fafc", size=13, family="sans-serif")
            )
        ))
        
        map_layout_args = {
            map_key: dict(
                style="carto-darkmatter",
                center=dict(lat=52.1, lon=19.4),
                zoom=5.3,
            ),
            "margin": dict(l=0, r=0, t=0, b=0),
            "height": 380,
            "paper_bgcolor": "rgba(0,0,0,0)",
        }
        fig_map.update_layout(**map_layout_args)
        st.plotly_chart(fig_map, use_container_width=True)
    
    st.markdown("#### 🏆 Szczegółowy ranking miast")
    st.dataframe(
        df_all_cities[["Miasto", "Kraj", "Użytkownicy", "Sesje", "Zrodlo", "Kiedy"]].rename(
            columns={"Zrodlo": "Źródło", "Kiedy": "Ostatnia wizyta"}
        ),
        hide_index=True,
        use_container_width=True,
    )

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
