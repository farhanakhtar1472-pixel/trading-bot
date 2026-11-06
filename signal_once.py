import os
import requests
import pandas as pd
from datetime import datetime, timedelta

TOPIC = os.environ["NTFY_TOPIC"]
SYMBOL = "BTCUSDT"
SL_PCT = 0.01
TP_PCT = 0.02
URL = "https://data-api.binance.vision/api/v3/klines"
WINDOW_MIN = 90


def notify(title, msg):
    requests.post(f"https://ntfy.sh/{TOPIC}", data=msg.encode("utf-8"),
                  headers={"Title": title}, timeout=15)


params = {"symbol": SYMBOL, "interval": "15m", "limit": 200}
data = requests.get(URL, params=params, timeout=15).json()
df = pd.DataFrame(data, columns=[
    "time", "open", "high", "low", "close", "volume",
    "close_time", "qav", "trades", "tbb", "tbq", "ignore"])
df["close"] = df["close"].astype(float)
df["time"] = pd.to_datetime(df["time"], unit="ms")
df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
delta = df["close"].diff()
gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
df["rsi"] = 100 - (100 / (1 + gain / loss))

# pehle bheje gaye alerts (pichle 6 ghante) taake dobara na jayen
try:
    recent = requests.get(f"https://ntfy.sh/{TOPIC}/json?poll=1&since=6h",
                          timeout=15).text
except Exception:
    recent = ""

now_price = df.iloc[-1]["close"]
sent = 0
for i in range(7, 1, -1):          # purani se nayi candle ki taraf
    prev, last = df.iloc[-i - 1], df.iloc[-i]
    closed_at = last["time"] + timedelta(minutes=15)
    if datetime.utcnow() - closed_at > timedelta(minutes=WINDOW_MIN):
        continue
    up = prev["ema20"] <= prev["ema50"] and last["ema20"] > last["ema50"] and last["rsi"] > 50
    down = prev["ema20"] >= prev["ema50"] and last["ema20"] < last["ema50"] and last["rsi"] < 50
    if not (up or down):
        continue
    tag = f"Candle: {last['time']}"
    if tag in recent:
        continue
    side = "BUY" if up else "SELL"
    price = last["close"]
    sl = price * (1 - SL_PCT) if up else price * (1 + SL_PCT)
    tp = price * (1 + TP_PCT) if up else price * (1 - TP_PCT)
    notify(f"{side} Signal",
           f"{SYMBOL} {side}\nEntry: {price:.2f}\nStop Loss: {sl:.2f}\n"
           f"Target: {tp:.2f}\nRSI: {last['rsi']:.1f}\n"
           f"Abhi ka price: {now_price:.2f}\n{tag} (UTC)")
    sent += 1
    print("signal bheja:", side, last["time"])

if sent == 0:
    print("koi naya signal nahi | RSI:", round(df.iloc[-2]["rsi"], 1))
