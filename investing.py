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
# 2. 기본 UI 및 종목 관리 설정
# ----------------------------------------------------
st.set_page_config(layout="wide") # 화면을 넓게 쓰기 위한 설정
st.title("📈 나의 첫 주식 대시보드 (Pro 버전)")

if 'tickers' not in st.session_state:
    st.session_state.tickers = {
        "엔비디아 (NVIDIA)": "NVDA",
        "애플 (Apple)": "AAPL",
        "SOXX (반도체 ETF)": "SOXX"
    }

# ----------------------------------------------------
# 3. 사이드바(Sidebar): 종목 검색 및 지표 옵션 선택
# ----------------------------------------------------
with st.sidebar:
    st.header("🔍 설정 패널")
    
    # 종목 추가
    new_ticker = st.text_input("새로운 종목 티커 추가 (예: TSLA)")
    if st.button("목록에 추가") and new_ticker:
        new_ticker = new_ticker.upper()
        st.session_state.tickers[f"새 종목 ({new_ticker})"] = new_ticker
        st.success(f"{new_ticker} 추가 완료!")
    
    st.divider()
    
    # 종목 선택
    selected_name = st.selectbox("차트를 볼 종목을 선택하세요", list(st.session_state.tickers.keys()))
    selected_ticker = st.session_state.tickers[selected_name]
    
    st.divider()
    
    # 차트 옵션 선택 (체크박스)
    st.subheader("📊 차트 옵션")
    show_sma20 = st.checkbox("20일 이동평균선", value=True)
    show_sma60 = st.checkbox("60일 이동평균선", value=False)
    show_sma120 = st.checkbox("120일 이동평균선", value=False)
    show_rsi = st.checkbox("RSI (상대강도지수)", value=True)
    show_macd = st.checkbox("MACD", value=True)

# ----------------------------------------------------
# 4. 데이터 로드 및 지표 계산
# ----------------------------------------------------
st.write(f"### **{selected_name} ({selected_ticker})** 차트 분석")

@st.cache_data
def load_data(ticker):
    # yfinance의 최신 버전 호환성 문제(MultiIndex)를 피하기 위해 Ticker.history()를 사용합니다.
    stock = yf.Ticker(ticker)
    data = stock.history(period="1y")
    return data

df = load_data(selected_ticker)

if not df.empty:
    # 지표 데이터 추가 계산
    df['SMA20'] = calc_sma(df, 20)
    df['SMA60'] = calc_sma(df, 60)
    df['SMA120'] = calc_sma(df, 120)
    df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = calc_macd(df)
    df['RSI'] = calc_rsi(df)

    # 최근 6개월 데이터만 잘라서 차트에 표시 (너무 길면 캔들이 안 보임)
    df_chart = df.tail(120) 

    # ----------------------------------------------------
    # 5. Plotly를 이용한 인터랙티브 차트 그리기
    # ----------------------------------------------------
    # 보조지표 선택 여부에 따라 차트의 층(Row) 개수 계산
    rows = 1
    if show_rsi: rows += 1
    if show_macd: rows += 1
    
    # 패널(Subplots) 비율 설정
    row_heights = [0.6]
    if show_rsi and show_macd: row_heights = [0.6, 0.2, 0.2]
    elif show_rsi or show_macd: row_heights = [0.7, 0.3]

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=row_heights)

    # 메인 차트: 캔들스틱 추가
    fig.add_trace(go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], 
                                 low=df_chart['Low'], close=df_chart['Close'], name='Candle'), row=1, col=1)

    # 메인 차트: 이동평균선 추가
    if show_sma20:
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['SMA20'], line=dict(color='orange', width=1.5), name='SMA 20'), row=1, col=1)
    if show_sma60:
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['SMA60'], line=dict(color='blue', width=1.5), name='SMA 60'), row=1, col=1)
    if show_sma120:
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['SMA120'], line=dict(color='purple', width=1.5), name='SMA 120'), row=1, col=1)

    # 보조지표 차트 그리기 시작할 위치(층)
    current_row = 2

    # RSI 차트 추가
    if show_rsi:
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['RSI'], line=dict(color='purple', width=1.5), name='RSI'), row=current_row, col=1)
        # RSI 30, 70 기준선 긋기
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=current_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=current_row, col=1)
        current_row += 1

    # MACD 차트 추가
    if show_macd:
        # MACD 막대그래프(히스토그램) 색상 지정 (양수는 초록, 음수는 빨강)
        colors = ['green' if val >= 0 else 'red' for val in df_chart['MACD_Hist']]
        fig.add_trace(go.Bar(x=df_chart.index, y=df_chart['MACD_Hist'], marker_color=colors, name='MACD Hist'), row=current_row, col=1)
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MACD'], line=dict(color='blue', width=1.5), name='MACD Line'), row=current_row, col=1)
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MACD_Signal'], line=dict(color='orange', width=1.5), name='Signal Line'), row=current_row, col=1)

    # 차트 전체 레이아웃 다듬기
    fig.update_layout(height=800, xaxis_rangeslider_visible=False, margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("데이터를 불러오지 못했습니다. 올바른 티커인지 확인해 주세요.")