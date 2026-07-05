import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ----------------------------------------------------
# 1. 지표 계산 함수 (SMA, MACD, RSI)
# ----------------------------------------------------
def calc_sma(df, window):
    return df['Close'].rolling(window=window).mean()

def calc_macd(df):
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - signal
    return macd, signal, macd_hist

def calc_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    ema_gain = gain.ewm(com=period-1, adjust=False).mean()
    ema_loss = loss.ewm(com=period-1, adjust=False).mean()
    rs = ema_gain / ema_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calc_bollinger(df, window=20, k=2):
    mid = df['Close'].rolling(window=window).mean()
    std = df['Close'].rolling(window=window).std()
    upper = mid + k * std
    lower = mid - k * std
    return mid, upper, lower

def calc_ichimoku(df):
    # 일목균형표(一目均衡表): 전환선/기준선/선행스팬1,2/후행스팬
    high, low, close = df['High'], df['Low'], df['Close']
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2      # 전환선
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2     # 기준선
    span_a = ((tenkan + kijun) / 2).shift(26)                        # 선행스팬1
    span_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)  # 선행스팬2
    chikou = close.shift(-26)                                        # 후행스팬
    return tenkan, kijun, span_a, span_b, chikou

# ----------------------------------------------------
# 2. 데이터 로드 및 표시용 헬퍼
# ----------------------------------------------------
# 봉 주기(일/주/월) 별 조회 기간·간격 설정
# 스크롤로 과거 데이터를 더 볼 수 있도록 넉넉한 기간을 로드한다.
TIMEFRAMES = {
    "일봉": ("3y", "1d"),
    "주봉": ("max", "1wk"),
    "월봉": ("max", "1mo"),
}

@st.cache_data(ttl=300)
def load_data(ticker, period="1y", interval="1d"):
    # yfinance의 최신 버전 호환성 문제(MultiIndex)를 피하기 위해 Ticker.history()를 사용합니다.
    stock = yf.Ticker(ticker)
    data = stock.history(period=period, interval=interval)
    return data

def build_sparkline(series, color):
    fig = go.Figure(go.Scatter(y=series.values, mode='lines', line=dict(color=color, width=1.5)))
    fig.update_layout(height=50, margin=dict(l=0, r=0, t=0, b=0),
                       xaxis=dict(visible=False), yaxis=dict(visible=False),
                       showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig

def format_volume(v):
    if v is None or pd.isna(v):
        return "-"
    v = float(v)
    if v >= 1_000_000_000: return f"{v/1_000_000_000:.2f}B"
    if v >= 1_000_000: return f"{v/1_000_000:.2f}M"
    if v >= 1_000: return f"{v/1_000:.2f}K"
    return f"{v:.0f}"

def format_price(price, currency):
    if price is None or pd.isna(price):
        return "N/A"
    if currency == "₩":
        return f"₩{price:,.0f}"      # 원화는 소수점 없이 표시
    return f"${price:,.2f}"

# 메인 화면에 표시할 주요 지수
INDEXES = [
    ("나스닥", "^IXIC"),
    ("S&P 500", "^GSPC"),
    ("다우존스", "^DJI"),
    ("비트코인", "BTC-USD"),
    ("달러환율 (USD/KRW)", "KRW=X"),
    ("달러인덱스 (DXY)", "DX-Y.NYB"),
]

# 시장(마켓) 구분과 통화 기호
MARKETS = {
    "미국주식": "$",
    "국내주식": "₩",
}

# 관심종목 리스트의 정렬 가능한 컬럼 (표시 라벨, 정렬 키, 컬럼 너비)
LIST_COLUMNS = [
    ("종목", "ticker", 2.0),
    ("이름", "name", 2.6),
    ("현재가", "price", 1.4),
    ("등락률", "change", 1.4),
    ("거래량", "volume", 1.6),
    ("최근 추이", None, 1.8),
    ("", None, 0.7),
]

# ----------------------------------------------------
# 3. 기본 UI 및 상태(세션) 초기화
# ----------------------------------------------------
st.set_page_config(layout="wide", page_title="StockPulse")

DEFAULT_TICKERS = {
    "미국주식": {
        "엔비디아 (NVIDIA)": "NVDA",
        "애플 (Apple)": "AAPL",
        "SOXX (반도체 ETF)": "SOXX",
        "테슬라 (Tesla)": "TSLA",
        "팔란티어 (Palantir)": "PLTR",
        "메타 (Meta)": "META",
        "아이온큐 (IonQ)": "IONQ",
        "서클 (Circle)": "CRCL",
        "알파벳 (Google)": "GOOGL",
        "뉴스케일파워 (NuScale Power)": "SMR",
        "마이크로스트래티지 (MicroStrategy)": "MSTR",
        "마이크론 (Micron)": "MU",
        "샌디스크 (SanDisk)": "SNDK",
        "마이크로소프트 (Microsoft)": "MSFT",
        "스페이스X (Space Exploration Technologies)": "SPCX",
        "로켓랩 (Rocket Lab)": "RKLB",
        "블룸에너지 (Bloom Energy)": "BE",
        "SCHD (배당 ETF)": "SCHD",
        "JEPQ (프리미엄 인컴 ETF)": "JEPQ",
        "오라클 (Oracle)": "ORCL",
        "TQQQ (나스닥 3배 레버리지 ETF)": "TQQQ",
        "옥시덴탈 페트롤리엄 (Occidental Petroleum)": "OXY",
        "아마존 (Amazon)": "AMZN",
        "어도비 (Adobe)": "ADBE",
        "넷플릭스 (Netflix)": "NFLX",
        "퀄컴 (Qualcomm)": "QCOM",
        "AMD (에이엠디)": "AMD",
        "TSMC (대만반도체)": "TSM",
        "엑슨모빌 (ExxonMobil)": "XOM",
        "스타벅스 (Starbucks)": "SBUX",
        "록히드마틴 (Lockheed Martin)": "LMT",
    },
    "국내주식": {
        "삼성전자": "005930.KS",
        "SK하이닉스": "000660.KS",
        "현대차": "005380.KS",
        "대덕전자": "353200.KS",
        "HD현대일렉트릭": "267260.KS",
        "현대로템": "064350.KS",
        "두산에너빌리티": "034020.KS",
        "삼성전기": "009150.KS",
        "이수페타시스": "007660.KS",
        "원익IPS": "240810.KQ",
        "한화에어로스페이스": "012450.KS",
        "동진쎄미켐": "005290.KQ",
        "제주반도체": "080220.KQ",
        "엘앤에프": "066970.KS",
        "LG이노텍": "011070.KS",
        "한미반도체": "042700.KS",
        "효성중공업": "298040.KS",
        "HD현대중공업": "329180.KS",
        "심텍": "222800.KQ",
        "SK스퀘어": "402340.KS",
        "SK텔레콤": "017670.KS",
        "하이브": "352820.KS",
        "JYP Ent.": "035900.KQ",
    },
}

# 세션에 없거나 옛 형식(평면 dict)이면 새 형식(시장별 중첩 dict)으로 초기화
if 'tickers' not in st.session_state or not all(
        isinstance(v, dict) for v in st.session_state.get('tickers', {}).values()):
    st.session_state.tickers = {m: dict(DEFAULT_TICKERS.get(m, {})) for m in MARKETS}

if 'view' not in st.session_state:
    st.session_state.view = 'home'          # 'home'(주요 지수) / 'list'(관심종목) / 'detail'(차트)
if 'active_name' not in st.session_state:
    st.session_state.active_name = None
if 'active_ticker' not in st.session_state:
    st.session_state.active_ticker = None
if 'active_currency' not in st.session_state:
    st.session_state.active_currency = "$"
if 'sort_by' not in st.session_state:
    st.session_state.sort_by = None          # None이면 추가한 순서 그대로
if 'sort_dir' not in st.session_state:
    st.session_state.sort_dir = 'desc'
if 'active_market' not in st.session_state:
    st.session_state.active_market = list(MARKETS.keys())[0]

def show_market():
    st.session_state.view = 'home'

def show_list():
    st.session_state.view = 'list'

def show_list_market(market):
    # 특정 시장(국내/미국)을 바로 선택해서 리스트 화면으로 이동
    st.session_state.active_market = market
    st.session_state.view = 'list'

def open_detail(name, ticker, currency):
    st.session_state.view = 'detail'
    st.session_state.active_name = name
    st.session_state.active_ticker = ticker
    st.session_state.active_currency = currency

def remove_ticker(market, name):
    st.session_state.tickers.get(market, {}).pop(name, None)

def set_sort(key):
    if st.session_state.sort_by == key:
        st.session_state.sort_dir = 'asc' if st.session_state.sort_dir == 'desc' else 'desc'
    else:
        st.session_state.sort_by = key
        st.session_state.sort_dir = 'desc'

# ----------------------------------------------------
# 4. 사이드바: 종목 추가 + 화면별 옵션
# ----------------------------------------------------
with st.sidebar:
    st.header("🔍 설정 패널")

    add_market = st.selectbox("시장 구분", list(MARKETS.keys()))
    if add_market == "국내주식":
        st.caption("국내주식은 뒤에 .KS(코스피)/.KQ(코스닥)를 붙여주세요. 예: 005930.KS")
    new_ticker = st.text_input("새로운 종목 티커 추가 (예: TSLA)")
    new_label = st.text_input("표시할 이름 (선택)")
    if st.button("목록에 추가") and new_ticker:
        new_ticker = new_ticker.upper()
        label = new_label.strip() or f"새 종목 ({new_ticker})"
        st.session_state.tickers.setdefault(add_market, {})[label] = new_ticker
        st.success(f"[{add_market}] {new_ticker} 추가 완료!")

    st.divider()

    if st.session_state.view == 'detail':
        st.button("← 목록으로 돌아가기", on_click=show_list, width='stretch')
        st.caption("차트 위 '지표 옵션'에서 보고 싶은 지표만 켜고 끌 수 있어요.")
    elif st.session_state.view == 'list':
        st.button("← 메인 화면으로", on_click=show_market, width='stretch')
        st.caption("열 제목을 클릭하면 오름차순/내림차순 정렬이 전환됩니다.")
    else:
        st.caption("상단 버튼으로 국내/미국 관심종목을 바로 볼 수 있어요.")

# ----------------------------------------------------
# 5-A. 메인 화면: 주요 지수 현황
# ----------------------------------------------------
def render_market():
    st.title("StockPulse")

    # 최상단: 관심종목 바로가기 (국내/미국 시장 직접 선택)
    st.subheader("📋 관심종목 바로보기")
    market_names = list(MARKETS.keys())
    btn_cols = st.columns(len(market_names))
    for col, market in zip(btn_cols, market_names):
        count = len(st.session_state.tickers.get(market, {}))
        icon = "🇰🇷" if market == "국내주식" else "🇺🇸"
        col.button(f"{icon} {market} ({count})", key=f"go_{market}",
                   on_click=show_list_market, args=(market,), width='stretch')

    st.divider()
    st.caption("주요 지수 현황")

    # 한 줄에 3개씩 배치 (지수 6개 → 2줄)
    per_row = 3
    for start in range(0, len(INDEXES), per_row):
        cols = st.columns(per_row)
        for col, (name, ticker) in zip(cols, INDEXES[start:start + per_row]):
            data = load_data(ticker)
            with col, st.container(border=True):
                st.markdown(f"**{name}**")
                if data.empty or len(data) < 2:
                    st.write("N/A")
                    continue
                last_close = data['Close'].iloc[-1]
                prev_close = data['Close'].iloc[-2]
                change = last_close - prev_close
                change_pct = (change / prev_close) * 100
                color = "green" if change >= 0 else "red"
                st.metric(label=ticker, value=f"{last_close:,.2f}", delta=f"{change_pct:+.2f}%")
                spark = build_sparkline(data['Close'].tail(30), color)
                st.plotly_chart(spark, width='stretch', config={'displayModeBar': False}, key=f"idx_spark_{ticker}")
                st.button("차트 보기 →", key=f"idx_open_{ticker}", on_click=open_detail,
                          args=(name, ticker, ""), width='stretch')

# ----------------------------------------------------
# 5-B. 리스트 화면: 시장(국내/미국)별 관심종목 (정렬 가능)
# ----------------------------------------------------
def render_market_table(market, currency):
    watch = st.session_state.tickers.get(market, {})
    if not watch:
        st.info("사이드바에서 종목을 추가해주세요.")
        return

    col_widths = [c[2] for c in LIST_COLUMNS]

    # 정렬에 필요한 데이터 먼저 수집
    rows_data = []
    for name, ticker in watch.items():
        data = load_data(ticker)
        if data.empty or len(data) < 2:
            rows_data.append({"name": name, "ticker": ticker, "price": None,
                               "change": None, "volume": None, "closes": None, "color": None})
            continue
        last_close = data['Close'].iloc[-1]
        prev_close = data['Close'].iloc[-2]
        change_pct = ((last_close - prev_close) / prev_close) * 100
        rows_data.append({
            "name": name, "ticker": ticker, "price": last_close, "change": change_pct,
            "volume": data['Volume'].iloc[-1], "closes": data['Close'].tail(30),
            "color": "green" if change_pct >= 0 else "red",
        })

    sort_by = st.session_state.sort_by
    if sort_by:
        valid = [r for r in rows_data if r.get(sort_by) is not None]
        invalid = [r for r in rows_data if r.get(sort_by) is None]
        valid.sort(key=lambda r: r[sort_by], reverse=(st.session_state.sort_dir == 'desc'))
        rows_data = valid + invalid

    # 헤더 (정렬 버튼) — 시장별로 key가 겹치지 않도록 market을 접두어로 사용
    header = st.columns(col_widths)
    for col, (label, key, _) in zip(header, LIST_COLUMNS):
        if key:
            arrow = ""
            if st.session_state.sort_by == key:
                arrow = " ▲" if st.session_state.sort_dir == 'asc' else " ▼"
            col.button(f"{label}{arrow}", key=f"sort_{market}_{key}", on_click=set_sort, args=(key,), width='stretch')
        elif label:
            col.markdown(f"**{label}**")
    st.divider()

    for r in rows_data:
        row = st.columns(col_widths)
        row[0].button(r['ticker'], key=f"open_{market}_{r['name']}", on_click=open_detail,
                      args=(r['name'], r['ticker'], currency), width='stretch')
        row[1].write(r['name'])

        if r['price'] is None:
            row[2].write("N/A")
            row[3].write("-")
            row[4].write("-")
        else:
            arrow = "▲" if r['color'] == "green" else "▼"
            row[2].write(format_price(r['price'], currency))
            row[3].markdown(f":{r['color']}[{arrow} {abs(r['change']):.2f}%]")
            row[4].write(format_volume(r['volume']))

        if r['closes'] is not None:
            spark = build_sparkline(r['closes'], r['color'])
            row[5].plotly_chart(spark, width='stretch', config={'displayModeBar': False}, key=f"spark_{market}_{r['name']}")

        row[6].button("🗑", key=f"del_{market}_{r['name']}", on_click=remove_ticker, args=(market, r['name']))

def render_list():
    st.title("📋 관심종목 리스트")
    st.caption("종목을 클릭하면 상세 차트로 이동합니다. 열 제목을 클릭하면 정렬됩니다.")

    # 국내/미국 시장 직접 선택 (active_market 키로 상단 바로가기 버튼과 연동)
    market = st.radio("시장 선택", list(MARKETS.keys()), horizontal=True,
                      key="active_market", label_visibility="collapsed")
    render_market_table(market, MARKETS[market])

# ----------------------------------------------------
# 5-C. 상세 화면: 캔들스틱 + 보조지표
# ----------------------------------------------------
def render_detail():
    name = st.session_state.active_name
    ticker = st.session_state.active_ticker
    st.write(f"### **{name} ({ticker})** 차트 분석")

    # 차트 바로 위 툴바: 봉 주기 + 보고 싶은 지표만 체크박스로 선택
    tf_col, opt_col = st.columns([1, 3])
    with tf_col:
        timeframe = st.radio("봉 주기", list(TIMEFRAMES.keys()), horizontal=True, key="tf_radio")
    with opt_col:
        st.caption("지표 옵션 (원하는 것만 체크)")
        c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
        show_ichimoku = c1.checkbox("일목구름", value=True, key="opt_ichimoku")
        show_bb = c2.checkbox("볼린저밴드", value=True, key="opt_bb")
        show_rsi = c3.checkbox("RSI", value=True, key="opt_rsi")
        show_macd = c4.checkbox("MACD", value=True, key="opt_macd")
        show_sma20 = c5.checkbox("SMA20", value=False, key="opt_sma20")
        show_sma60 = c6.checkbox("SMA60", value=False, key="opt_sma60")
        show_sma120 = c7.checkbox("SMA120", value=False, key="opt_sma120")
    st.divider()

    period, interval = TIMEFRAMES[timeframe]
    df = load_data(ticker, period=period, interval=interval)

    if df.empty:
        st.error("데이터를 불러오지 못했습니다. 올바른 티커인지 확인해 주세요.")
        return

    df['SMA20'] = calc_sma(df, 20)
    df['SMA60'] = calc_sma(df, 60)
    df['SMA120'] = calc_sma(df, 120)
    df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = calc_macd(df)
    df['RSI'] = calc_rsi(df)
    df['BB_MID'], df['BB_UP'], df['BB_LOW'] = calc_bollinger(df)
    df['ICH_TENKAN'], df['ICH_KIJUN'], df['ICH_A'], df['ICH_B'], df['ICH_CHIKOU'] = calc_ichimoku(df)

    # 넉넉히 그려두고(스크롤 시 과거 데이터가 나타나도록) 처음엔 최근 구간만 보이게 한다.
    plot_cap = {"일봉": 750, "주봉": 500, "월봉": 360}.get(timeframe, 500)
    visible_n = 120                      # 처음 화면에 보이는 봉 개수
    df_chart = df.tail(plot_cap)
    x = df_chart.index

    rows = 1
    if show_rsi: rows += 1
    if show_macd: rows += 1

    row_heights = [0.6]
    if show_rsi and show_macd: row_heights = [0.6, 0.2, 0.2]
    elif show_rsi or show_macd: row_heights = [0.7, 0.3]

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.09, row_heights=row_heights)

    # 일목구름: 캔들 뒤에 먼저 그림 (선행스팬1 >= 선행스팬2 → 초록 구름, 아니면 빨강 구름)
    if show_ichimoku:
        span_a, span_b = df_chart['ICH_A'], df_chart['ICH_B']
        # 초록 구름
        fig.add_trace(go.Scatter(x=x, y=span_b, line=dict(width=0), showlegend=False, hoverinfo='skip'), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=span_a.where(span_a >= span_b), fill='tonexty',
                                 fillcolor='rgba(38,166,154,0.18)', line=dict(width=0),
                                 showlegend=False, hoverinfo='skip'), row=1, col=1)
        # 빨강 구름
        fig.add_trace(go.Scatter(x=x, y=span_b, line=dict(width=0), showlegend=False, hoverinfo='skip'), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=span_a.where(span_a < span_b), fill='tonexty',
                                 fillcolor='rgba(239,83,80,0.18)', line=dict(width=0),
                                 showlegend=False, hoverinfo='skip'), row=1, col=1)
        # 구름 경계선
        fig.add_trace(go.Scatter(x=x, y=span_a, line=dict(color='rgba(38,166,154,0.7)', width=1), name='선행스팬1'), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=span_b, line=dict(color='rgba(239,83,80,0.7)', width=1), name='선행스팬2'), row=1, col=1)

    # 캔들스틱
    fig.add_trace(go.Candlestick(x=x, open=df_chart['Open'], high=df_chart['High'],
                                 low=df_chart['Low'], close=df_chart['Close'], name='Candle'), row=1, col=1)

    # 일목균형표 전환선/기준선/후행스팬
    if show_ichimoku:
        fig.add_trace(go.Scatter(x=x, y=df_chart['ICH_TENKAN'], line=dict(color='#2962FF', width=1.2), name='전환선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=df_chart['ICH_KIJUN'], line=dict(color='#B71C1C', width=1.2), name='기준선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=df_chart['ICH_CHIKOU'], line=dict(color='#9E9E9E', width=1, dash='dot'), name='후행스팬'), row=1, col=1)

    # 볼린저밴드
    if show_bb:
        fig.add_trace(go.Scatter(x=x, y=df_chart['BB_UP'], line=dict(color='rgba(120,120,255,0.6)', width=1), name='BB 상단'), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=df_chart['BB_LOW'], fill='tonexty', fillcolor='rgba(120,120,255,0.10)',
                                 line=dict(color='rgba(120,120,255,0.6)', width=1), name='BB 하단'), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=df_chart['BB_MID'], line=dict(color='rgba(120,120,255,0.9)', width=1, dash='dash'), name='BB 중심'), row=1, col=1)

    # 이동평균선
    if show_sma20:
        fig.add_trace(go.Scatter(x=x, y=df_chart['SMA20'], line=dict(color='orange', width=1.5), name='SMA 20'), row=1, col=1)
    if show_sma60:
        fig.add_trace(go.Scatter(x=x, y=df_chart['SMA60'], line=dict(color='blue', width=1.5), name='SMA 60'), row=1, col=1)
    if show_sma120:
        fig.add_trace(go.Scatter(x=x, y=df_chart['SMA120'], line=dict(color='purple', width=1.5), name='SMA 120'), row=1, col=1)

    current_row = 2
    if show_rsi:
        fig.add_trace(go.Scatter(x=x, y=df_chart['RSI'], line=dict(color='purple', width=1.5), name='RSI'), row=current_row, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=current_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=current_row, col=1)
        current_row += 1

    if show_macd:
        colors = ['green' if val >= 0 else 'red' for val in df_chart['MACD_Hist']]
        fig.add_trace(go.Bar(x=x, y=df_chart['MACD_Hist'], marker_color=colors, name='MACD Hist'), row=current_row, col=1)
        fig.add_trace(go.Scatter(x=x, y=df_chart['MACD'], line=dict(color='blue', width=1.5), name='MACD Line'), row=current_row, col=1)
        fig.add_trace(go.Scatter(x=x, y=df_chart['MACD_Signal'], line=dict(color='orange', width=1.5), name='Signal Line'), row=current_row, col=1)

    # 봉 주기별 날짜 표시 형식
    date_fmt = {"일봉": "%Y-%m-%d", "주봉": "%Y-%m-%d", "월봉": "%Y-%m"}.get(timeframe, "%Y-%m-%d")

    fig.update_layout(
        height=800,
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=10, t=30, b=24),
        hovermode='x unified',        # 커서 x위치의 모든 값을 날짜와 함께 한 번에 표시
        hoverdistance=100,
        spikedistance=-1,             # 항상 크로스헤어(십자선) 표시
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
    )
    # X축: 하단 날짜 눈금을 촘촘하게 + 커서 따라다니는 세로 십자선
    fig.update_xaxes(
        showspikes=True, spikemode='across', spikesnap='cursor',
        spikecolor='rgba(160,160,160,0.9)', spikethickness=1, spikedash='dot',
        showgrid=True, gridcolor='rgba(150,150,150,0.12)',
        nticks=15, tickformat=date_fmt, hoverformat=date_fmt,
    )
    # Y축: 커서 따라다니는 가로 십자선 + 가격 표시
    fig.update_yaxes(
        showspikes=True, spikemode='across', spikesnap='cursor',
        spikecolor='rgba(160,160,160,0.9)', spikethickness=1, spikedash='dot',
        showgrid=True, gridcolor='rgba(150,150,150,0.12)',
    )
    # 일봉은 주말 공백을 제거해 캔들이 끊기지 않게 (트레이딩뷰처럼)
    if interval == "1d":
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])

    # 날짜 눈금을 캔들차트(맨 위) 바로 아래에 표시하고, 아래 보조지표엔 숨김
    fig.update_xaxes(showticklabels=True, row=1, col=1)
    for r in range(2, rows + 1):
        fig.update_xaxes(showticklabels=False, row=r, col=1)

    # 처음엔 최근 visible_n개 봉만 보이게 설정 → 스크롤/드래그로 과거·현재 데이터 탐색
    if len(df_chart) > visible_n:
        fig.update_xaxes(range=[df_chart.index[-visible_n], df_chart.index[-1]])
        vis = df_chart.tail(visible_n)
        y_lo, y_hi = float(vis['Low'].min()), float(vis['High'].max())
        pad = (y_hi - y_lo) * 0.08 or 1
        fig.update_yaxes(range=[y_lo - pad, y_hi + pad], row=1, col=1)

    st.caption("💡 차트 위에서 마우스 휠로 확대/축소, 드래그로 이동하며 과거 데이터를 볼 수 있어요. 더블클릭하면 원래대로 돌아갑니다.")
    st.plotly_chart(fig, width='stretch', config={'scrollZoom': True})

# ----------------------------------------------------
# 6. 라우팅
# ----------------------------------------------------
if st.session_state.view == 'detail' and st.session_state.active_ticker:
    render_detail()
elif st.session_state.view == 'list':
    render_list()
else:
    render_market()
