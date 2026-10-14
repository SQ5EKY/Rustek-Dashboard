import streamlit as st
import requests
import json
import plotly.express as px
import pandas as pd
import pydeck as pdk
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

def format_ga_date(d_str):
    if len(d_str) == 8:
        return f"{d_str[6:8]}.{d_str[4:6]}.{d_str[0:4]}"
    return d_str

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
    "nowy sacz": (49.6218, 20.6971), "nowy sącz": (
