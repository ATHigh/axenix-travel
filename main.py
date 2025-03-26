import streamlit as st
import json
import requests
import networkx as nx
from datetime import datetime, date, timedelta
from dateutil import parser as date_parser
import folium
import random
from streamlit_folium import folium_static
import pandas as pd

# API ключ (замените на свой)
API_KEY = ""
BASE_URL = "https://api.rasp.yandex.net/v3.0"
ALL_TRANSPORT_TYPES = "plane,train,bus"

st.set_page_config(page_title="Планировщик маршрутов", layout="wide")

st.markdown(
    """
    <style>
        div.stButton > button {
            background-color: #E57A4E;
            color: white;
            font-size: 14px;
            font-weight: bold;
            border-radius: 5px;
            padding: 8px 16px;
            border: none;
        }
        div.stButton > button:hover {
            background-color: #E57A4E;
            color: white;
        }
        .big-text {
            font-size: 24px !important;
            font-weight: bold;
            text-align: center;
            margin-top: 20px;
            margin-bottom: 20px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title(":orange[Axenix] travel")
st.markdown(
    "<p class='big-text'>Простые решения для сложных маршрутов</p>",
    unsafe_allow_html=True,
)

MAX_ROUTES = 5
if "num_routes" not in st.session_state:
    st.session_state.num_routes = 1
if "routes" not in st.session_state:
    st.session_state.routes = [{} for _ in range(MAX_ROUTES)]


def get_route_segments(
    from_code, to_code, date_str, transport_types=ALL_TRANSPORT_TYPES
):
    url = (
        f"{BASE_URL}/search/"
        f"?apikey={API_KEY}"
        f"&format=json"
        f"&from={from_code}"
        f"&to={to_code}"
        f"&date={date_str}"
        f"&transfers=true"
        f"&transport_types={transport_types}"
    )
    try:
        response = requests.get(url)
        response.raise_for_status()
    except Exception as e:
        st.error(f"Ошибка при получении маршрутов: {e}")
        return []
    return response.json().get("segments", [])


def process_routes(routes):
    route_list = []
    for route in routes:
        try:
            price = route.get("tickets", [{}])[0].get("price", {}).get("whole", None)
            if price is None:
                # Здесь заменяем None значение цены на случайное число, как временный способ, чтобы показать работу алгоритма
                price = random.randint(750, 25000)
            route_list.append(
                {
                    "Тип": route["thread"]["transport_type"],
                    "Отправление": date_parser.parse(route["departure"]),
                    "Прибытие": date_parser.parse(route["arrival"]),
                    "Время в пути": date_parser.parse(route["arrival"])
                    - date_parser.parse(route["departure"]),
                    "Цена": price,
                }
            )
        except Exception as e:
            print(f"Ошибка обработки маршрута: {e}")
    df = pd.DataFrame(route_list)
    df = df.sort_values(
        by=["Отправление", "Цена", "Время в пути"], ascending=[True, True, True]
    )
    return df


def find_best_routes(all_routes):
    combined_routes = pd.concat(all_routes)
    cheapest_path = (
        combined_routes.groupby("Тип")
        .apply(lambda x: x.nsmallest(1, "Цена"))
        .sort_values(by="Отправление")
    )
    fastest_path = (
        combined_routes.groupby("Тип")
        .apply(lambda x: x.nsmallest(1, "Время в пути"))
        .sort_values(by="Отправление")
    )
    return cheapest_path, fastest_path


def route_form(index):
    cols = st.columns([1.5, 1.5, 0.9, 0.9, 0.8, 1, 1])
    with cols[0]:
        from_city = st.selectbox(
            "Откуда",
            ["Москва", "Санкт-Петербург", "Калининград", "Казань", "Екатеринбург"],
            index=0,
            key=f"from_city_{index}",
        )
    with cols[1]:
        to_city = st.selectbox(
            "Куда",
            ["Санкт-Петербург", "Москва", "Калининград", "Казань", "Екатеринбург"],
            index=1,
            key=f"to_city_{index}",
        )
    with cols[2]:
        departure_date = st.date_input(
            "Туда", min_value=date.today(), value=None, key=f"departure_date_{index}"
        )
    with cols[3]:
        return_date = st.date_input(
            "Обратно",
            min_value=departure_date if departure_date else date.today(),
            value=None,
            key=f"return_date_{index}",
        )
    if index > 0:
        st.session_state.routes[index - 1]["return_date"] = None
    with cols[4]:
        num_passengers = st.number_input(
            "Пассажиры",
            min_value=1,
            max_value=10,
            value=1,
            step=1,
            format="%d",
            key=f"num_passengers_{index}",
        )
    with cols[5]:
        transport_type = st.selectbox(
            "Транспорт",
            ["Самолет", "Поезд", "Автобус"],
            index=0,
            key=f"transport_type_{index}",
        )
    with cols[6]:
        class_type = (
            st.selectbox(
                "Тип класса", ["Эконом", "Бизнес"], index=0, key=f"class_type_{index}"
            )
            if transport_type == "Самолет"
            else None
        )
    return (
        from_city,
        to_city,
        departure_date,
        return_date,
        num_passengers,
        transport_type,
        class_type,
    )


route_data = []
for i in range(st.session_state.num_routes):
    st.markdown(f"**Маршрут {i+1}**")
    route_data.append(route_form(i))
    if i > 0:
        if st.button(f"Удалить маршрут {i+1}", key=f"remove_route_{i}"):
            st.session_state.num_routes -= 1
            st.rerun()

if st.session_state.num_routes < MAX_ROUTES:
    if st.button("Добавить маршрут"):
        st.session_state.num_routes += 1
        st.rerun()

if st.session_state.num_routes > 1:
    if st.button("Вернуться к простому маршруту"):
        st.session_state.num_routes = 1
        st.rerun()

if st.button("Найти"):
    all_routes = []
    for route in route_data:
        from_code, to_code = "c213", "c2"  # Заглушки
        raw_routes = get_route_segments(
            from_code, to_code, route[2].strftime("%Y-%m-%d")
        )
        df = process_routes(raw_routes)
        all_routes.append(df)

    if all_routes:
        cheapest_route, fastest_route = find_best_routes(all_routes)

        st.markdown(
            f"### Самый дешевый вариант: {route_data[0][0]} - {route_data[-1][1]}"
        )
        st.dataframe(cheapest_route, use_container_width=True)

        st.markdown(
            f"### Самый быстрый вариант: {route_data[0][0]} - {route_data[-1][1]}"
        )
        st.dataframe(fastest_route, use_container_width=True)

        for i, df in enumerate(all_routes):
            st.markdown(
                f"### {route_data[i][0]} - {route_data[i][1]} ({route_data[i][2]})"
            )
            st.dataframe(df, use_container_width=True)
