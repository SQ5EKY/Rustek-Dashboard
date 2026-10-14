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

def format_ga_date(d_str):
    if len(d_str) == 8:
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
    "sosnowiec": (50.2v
