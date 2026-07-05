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

# ----------------------------------------------------
# 2. 데이터 로드 (종목별로 캐싱, 5분마다 갱신)
# ----------------------------------------------------
@st.cache_data(ttl=300)
def load_data(ticker):
    # yfinance의 최신 버전 호환성 문제(MultiIndex)를 피하기 위해 Ticker.history()를 사용합니다.
    stock = yf.Ticker(ticker)
    data = stock.history(period="1y")
    return data

# ----------------------------------------------------
# 3. 기본 UI 및 상태(세션) 초기화
# ----------------------------------------------------
st.set_page_config(layout="wide", page_title="나의 주식 대시보드")

if 'tickers' not in st.session_state:
    st.session_state.tickers = {
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
    }
if 'view' not in st.session_state:
    st.session_state.view = 'home'          # 'home' or 'detail'
if 'active_name' not in st.session_state:
    st.session_state.active_name = None
if 'active_ticker' not in st.session_state:
    st.session_state.active_ticker = None

def open_detail(name, ticker):
    st.session_state.view = 'detail'
    st.session_state.active_name = name
    st.session_state.active_ticker = ticker

def back_to_home():
    st.session_state.view = 'home'

def remove_ticker(name):
    st.session_state.tickers.pop(name, None)
    if st.session_state.active_name == name:
        st.session_state.view = 'home'

# ----------------------------------------------------
# 4. 사이드바: 종목 추가 + (상세 화면일 때) 차트 옵션
# ----------------------------------------------------
show_sma20 = show_sma60 = show_sma120 = show_rsi = show_macd = False

with st.sidebar:
    st.header("🔍 설정 패널")

    new_ticker = st.text_input("새로운 종목 티커 추가 (예: TSLA)")
    if st.button("목록에 추가") and new_ticker:
        new_ticker = new_ticker.upper()
        st.session_state.tickers[f"새 종목 ({new_ticker})"] = new_ticker
        st.success(f"{new_ticker} 추가 완료!")

    st.divider()

    if st.session_state.view == 'detail':
        st.button("← 종목 리스트로 돌아가기", on_click=back_to_home, width='stretch')
        st.divider()
        st.subheader("📊 차트 옵션")
        show_sma20 = st.checkbox("20일 이동평균선", value=True)
        show_sma60 = st.checkbox("60일 이동평균선", value=False)
        show_sma120 = st.checkbox("120일 이동평균선", value=False)
        show_rsi = st.checkbox("RSI (상대강도지수)", value=True)
        show_macd = st.checkbox("MACD", value=True)
    else:
        st.caption("아래 관심종목 리스트에서 종목을 클릭하면 상세 차트로 이동합니다.")

# ----------------------------------------------------
# 5-A. 홈 화면: 관심종목 리스트 (트레이딩뷰 워치리스트 스타일)
# ----------------------------------------------------
def render_home():
    st.title("📈 나의 주식 대시보드")
    st.caption("관심종목 리스트")

    if not st.session_state.tickers:
        st.info("사이드바에서 종목을 추가해주세요.")
        return

    header = st.columns([2.8, 3, 1.6, 1.6, 2, 0.8])
    for col, label in zip(header, ["종목", "이름", "현재가", "등락률", "최근 추이", ""]):
        col.markdown(f"**{label}**")
    st.divider()

    for name, ticker in list(st.session_state.tickers.items()):
        data = load_data(ticker)
        row = st.columns([2.8, 3, 1.6, 1.6, 2, 0.8])

        if data.empty or len(data) < 2:
            row[0].button(ticker, key=f"open_{name}", on_click=open_detail, args=(name, ticker), width='stretch')
            row[1].write(name)
            row[2].write("N/A")
            row[3].write("-")
            row[5].button("🗑", key=f"del_{name}", on_click=remove_ticker, args=(name,))
            continue

        last_close = data['Close'].iloc[-1]
        prev_close = data['Close'].iloc[-2]
        change = last_close - prev_close
        change_pct = (change / prev_close) * 100
        color = "green" if change >= 0 else "red"
        arrow = "▲" if change >= 0 else "▼"

        row[0].button(ticker, key=f"open_{name}", on_click=open_detail, args=(name, ticker), width='stretch')
        row[1].write(name)
        row[2].write(f"${last_close:,.2f}")
        row[3].markdown(f":{color}[{arrow} {abs(change_pct):.2f}%]")

        spark = go.Figure(go.Scatter(y=data['Close'].tail(30).values, mode='lines',
                                      line=dict(color=color, width=1.5)))
        spark.update_layout(height=50, margin=dict(l=0, r=0, t=0, b=0),
                             xaxis=dict(visible=False), yaxis=dict(visible=False),
                             showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        row[4].plotly_chart(spark, width='stretch', config={'displayModeBar': False}, key=f"spark_{name}")

        row[5].button("🗑", key=f"del_{name}", on_click=remove_ticker, args=(name,))

# ----------------------------------------------------
# 5-B. 상세 화면: 캔들스틱 + 보조지표
# ----------------------------------------------------
def render_detail(show_sma20, show_sma60, show_sma120, show_rsi, show_macd):
    name = st.session_state.active_name
    ticker = st.session_state.active_ticker
    st.write(f"### **{name} ({ticker})** 차트 분석")

    df = load_data(ticker)

    if df.empty:
        st.error("데이터를 불러오지 못했습니다. 올바른 티커인지 확인해 주세요.")
        return

    df['SMA20'] = calc_sma(df, 20)
    df['SMA60'] = calc_sma(df, 60)
    df['SMA120'] = calc_sma(df, 120)
    df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = calc_macd(df)
    df['RSI'] = calc_rsi(df)

    # 최근 6개월 데이터만 잘라서 차트에 표시 (너무 길면 캔들이 안 보임)
    df_chart = df.tail(120)

    # 보조지표 선택 여부에 따라 차트의 층(Row) 개수 계산
    rows = 1
    if show_rsi: rows += 1
    if show_macd: rows += 1

    row_heights = [0.6]
    if show_rsi and show_macd: row_heights = [0.6, 0.2, 0.2]
    elif show_rsi or show_macd: row_heights = [0.7, 0.3]

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=row_heights)

    fig.add_trace(go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'],
                                 low=df_chart['Low'], close=df_chart['Close'], name='Candle'), row=1, col=1)

    if show_sma20:
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['SMA20'], line=dict(color='orange', width=1.5), name='SMA 20'), row=1, col=1)
    if show_sma60:
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['SMA60'], line=dict(color='blue', width=1.5), name='SMA 60'), row=1, col=1)
    if show_sma120:
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['SMA120'], line=dict(color='purple', width=1.5), name='SMA 120'), row=1, col=1)

    current_row = 2
    if show_rsi:
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['RSI'], line=dict(color='purple', width=1.5), name='RSI'), row=current_row, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=current_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=current_row, col=1)
        current_row += 1

    if show_macd:
        colors = ['green' if val >= 0 else 'red' for val in df_chart['MACD_Hist']]
        fig.add_trace(go.Bar(x=df_chart.index, y=df_chart['MACD_Hist'], marker_color=colors, name='MACD Hist'), row=current_row, col=1)
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MACD'], line=dict(color='blue', width=1.5), name='MACD Line'), row=current_row, col=1)
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MACD_Signal'], line=dict(color='orange', width=1.5), name='Signal Line'), row=current_row, col=1)

    fig.update_layout(height=800, xaxis_rangeslider_visible=False, margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig, width='stretch')

# ----------------------------------------------------
# 6. 라우팅
# ----------------------------------------------------
if st.session_state.view == 'detail' and st.session_state.active_ticker:
    render_detail(show_sma20, show_sma60, show_sma120, show_rsi, show_macd)
else:
    render_home()
