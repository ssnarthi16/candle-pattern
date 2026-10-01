import streamlit as st
import pandas as pd
import io
from datetime import datetime, date, time, timedelta

try:
    from SmartApi import SmartConnect
    import pyotp
    ANGEL_AVAILABLE = True
except Exception:
    SmartConnect = None
    pyotp = None
    ANGEL_AVAILABLE = False

st.set_page_config(
    page_title="Candles Pattern Backtest",
    page_icon="🕯️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================
# SESSION STATE
# ============================================================
defaults = {
    "connected": False,
    "smart_api": None,
    "auth_token": None,
    "feed_token": None,
    "client_id": "",
    "profile": None,
    "symbol_master": None,
    "ohlc_df": None,
    "raw_ohlc_df": None,
    "selected_timeframe": "",
    "ohlc_source": None,
    "ohlc_diagnostics": [],
    "results": None,
    "summary": None,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# CSS
# ============================================================
st.markdown(
    """
    <style>
    .block-container {
        max-width: 1200px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    .center-wrap {
        max-width: 720px;
        margin: 35px auto 0 auto;
    }

    .login-title {
        text-align: center;
        font-size: 30px;
        font-weight: 800;
        margin-bottom: 5px;
    }

    .login-subtitle {
        text-align: center;
        color: #6b7280;
        margin-bottom: 25px;
    }

    .app-header {
        text-align: center;
        margin-bottom: 25px;
    }

    .app-title {
        font-size: 38px;
        font-weight: 850;
        margin-bottom: 5px;
    }

    .app-subtitle {
        color: #6b7280;
        font-size: 15px;
    }

    .section-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 18px;
        box-shadow: 0 3px 15px rgba(0,0,0,.04);
    }

    .section-title {
        font-size: 21px;
        font-weight: 800;
        margin-bottom: 12px;
    }

    .stButton > button {
        width: 100%;
        min-height: 44px;
        border-radius: 9px;
        font-weight: 700;
    }

    .connected-box {
        padding: 12px 16px;
        border-radius: 10px;
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
        margin-bottom: 18px;
    }

    .info-box {
        padding: 12px 16px;
        border-radius: 10px;
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        margin-bottom: 18px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 10 CANDLE PATTERNS
# Existing Candle_pattern_final.py pattern logic kept.
# ============================================================
PATTERNS = [
    "BULLISH ENGULFING",
    "BULLISH HARAMI",
    "BULLISH MARUBOZU",
    "HAMMER",
    "INVERTED HAMMER",
    "MORNING STAR",
    "PIERCING",
    "RISING THREE METHODS",
    "THREE WHITE SOLDIERS",
    "TWEEZER BOTTOM",
]


def detect_patterns(df):
    n = len(df)
    r = {p: [""] * n for p in PATTERNS}

    for i in range(n):
        o, h, l, c = df.loc[i, ["Open", "High", "Low", "Close"]]
        body = abs(c - o)

        if i >= 1:
            po, pc = df.loc[i - 1, ["Open", "Close"]]

            if po > pc and c > o and o <= pc and c >= po:
                r["BULLISH ENGULFING"][i] = "BULLISH ENGULFING"

            if po > pc and c > o and o > pc and c < po:
                r["BULLISH HARAMI"][i] = "BULLISH HARAMI"

        if body > 0 and c > o:
            if o - l <= 0.05 * body and h - c <= 0.05 * body:
                r["BULLISH MARUBOZU"][i] = "BULLISH MARUBOZU"

        if body > 0:
            lower = min(o, c) - l
            upper = h - max(o, c)

            if lower >= 2 * body and upper <= 0.10 * body:
                r["HAMMER"][i] = "HAMMER"

            if upper >= 2 * body and lower <= 0.10 * body:
                r["INVERTED HAMMER"][i] = "INVERTED HAMMER"

        if i >= 2:
            o1, c1 = df.loc[i - 2, ["Open", "Close"]]
            o2, c2 = df.loc[i - 1, ["Open", "Close"]]
            o3, c3 = df.loc[i, ["Open", "Close"]]

            if (
                c1 < o1
                and abs(c2 - o2) <= 0.5 * abs(c1 - o1)
                and c3 > o3
                and c3 >= o1 - 0.5 * (o1 - c1)
            ):
                r["MORNING STAR"][i] = "MORNING STAR"

            if (
                c1 > o1
                and c2 > o2
                and c3 > o3
                and c2 > c1
                and c3 > c2
                and o2 >= o1
                and o2 <= c1
                and o3 >= o2
                and o3 <= c2
            ):
                r["THREE WHITE SOLDIERS"][i] = "THREE WHITE SOLDIERS"

        if i >= 1:
            o1, c1 = df.loc[i - 1, ["Open", "Close"]]

            if (
                c1 < o1
                and c > o
                and c > o1 - (o1 - c1) / 2
                and c < o1
            ):
                r["PIERCING"][i] = "PIERCING"

            o1, c1, l1 = df.loc[i - 1, ["Open", "Close", "Low"]]

            if c1 < o1 and c > o and abs(l - l1) <= 0.001 * abs(l1):
                r["TWEEZER BOTTOM"][i] = "TWEEZER BOTTOM"

        if i >= 4:
            o1, c1 = df.loc[i - 4, ["Open", "Close"]]

            small = all(
                abs(df.loc[j, "Close"] - df.loc[j, "Open"])
                <= 0.5 * abs(c1 - o1)
                for j in range(i - 3, i)
            )

            inside = all(
                df.loc[j, "High"] <= df.loc[i - 4, "High"]
                and df.loc[j, "Low"] >= df.loc[i - 4, "Low"]
                for j in range(i - 3, i)
            )

            if c1 > o1 and small and inside and c > o and c > c1:
                r["RISING THREE METHODS"][i] = "RISING THREE METHODS"

    return r


# ============================================================
# BACKTEST
# ============================================================
def make_result(df, pattern, hold, target_percent, flags):
    rows = []

    for i in range(len(df)):
        if flags[pattern][i] != pattern:
            continue

        entry = float(df.loc[i, "Close"])
        target_price = entry * (1 + target_percent)
        last_index = min(i + hold, len(df) - 1)

        exit_index = None
        exit_reason = ""

        # Exit at the first candle that reaches the exact target.
        for j in range(i + 1, last_index + 1):
            current_close = float(df.loc[j, "Close"])

            if current_close >= target_price:
                exit_index = j
                exit_reason = "TARGET"
                break

        # If target is not reached, use the selected holding period.
        if exit_index is None:
            exit_index = last_index
            exit_reason = "HOLDING PERIOD"

        exit_price = float(df.loc[exit_index, "Close"])
        pnl = exit_price - entry
        pct = (pnl / entry) if entry else None

        rows.append(
            {
                "Entry Date": df.loc[i, "Date"],
                "Pattern": pattern,
                "Entry Price": entry,
                "Holding Candles": exit_index - i,
                "Target %": target_percent * 100,
                "Target Price": target_price,
                "Exit Date": df.loc[exit_index, "Date"],
                "Exit": "EXIT",
                "Exit Reason": exit_reason,
                "Exit Price": exit_price,
                "PnL": pnl,
                "PnL %": (pct * 100) if pct is not None else None,
                "_entry_index": i,
                "_exit_index": exit_index,
            }
        )

    if not rows:
        return pd.DataFrame()

    # Do not allow another entry while a previous trade is open.
    accepted = []
    last_exit = -1

    for row in rows:
        if row["_entry_index"] > last_exit:
            accepted.append(row)
            last_exit = row["_exit_index"]

    result = pd.DataFrame(accepted)

    return result.drop(
        columns=["_entry_index", "_exit_index"],
        errors="ignore",
    )


# ============================================================
# EXCEL EXPORT
# ============================================================
def _excel_safe_df(frame):
    """Return a copy that Excel/openpyxl can write safely.

    Angel One OHLC timestamps can contain an IST timezone (+05:30).
    Excel does not support timezone-aware datetime values, so remove
    timezone information while preserving the actual date/time.
    """
    if frame is None:
        return pd.DataFrame()

    safe = frame.copy()

    for col in safe.columns:
        series = safe[col]

        # Datetime columns, including timezone-aware datetimes.
        if isinstance(series.dtype, pd.DatetimeTZDtype):
            safe[col] = series.dt.tz_localize(None)
        elif pd.api.types.is_datetime64_any_dtype(series):
            # Keep normal naive datetimes unchanged.
            safe[col] = series
        elif series.dtype == object:
            # Handle object columns containing Python datetime/Timestamp values.
            try:
                converted = pd.to_datetime(series, errors="coerce")
                if converted.notna().any():
                    if isinstance(converted.dtype, pd.DatetimeTZDtype):
                        converted = converted.dt.tz_localize(None)
                    safe[col] = converted.where(converted.notna(), series)
            except (TypeError, ValueError):
                pass

    return safe


def excel_bytes(df, results, hold, target_percent):
    out = io.BytesIO()

    safe_df = _excel_safe_df(df)

    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "Parameter": ["Holding Candles", "Target %"],
                "Value": [hold, target_percent * 100],
            }
        ).to_excel(
            writer,
            sheet_name="PARAMETERS",
            index=False,
        )

        summary = []

        for p in PATTERNS:
            x = results.get(p, pd.DataFrame())
            done = x.dropna(subset=["PnL"]) if not x.empty else x

            summary.append(
                {
                    "Pattern": p,
                    "Entries": len(x),
                    "Completed Exits": len(done),
                    "Winning Trades": (
                        int((done["PnL"] > 0).sum())
                        if len(done) else 0
                    ),
                    "Losing Trades": (
                        int((done["PnL"] < 0).sum())
                        if len(done) else 0
                    ),
                    "Total PnL": (
                        float(done["PnL"].sum())
                        if len(done) else 0
                    ),
                    "Average PnL %": (
                        float(done["PnL %"].mean())
                        if len(done) else 0
                    ),
                }
            )

            _excel_safe_df(x).to_excel(
                writer,
                sheet_name=p[:31],
                index=False,
            )

        pd.DataFrame(summary).to_excel(
            writer,
            sheet_name="SUMMARY",
            index=False,
        )

        safe_df.to_excel(
            writer,
            sheet_name="OHLC_DATA",
            index=False,
        )

    out.seek(0)
    return out


# ============================================================
# ANGEL ONE
# ============================================================
SYMBOL_MASTER_URL = (
    "https://margincalculator.angelbroking.com/"
    "OpenAPI_File/files/OpenAPIScripMaster.json"
)


@st.cache_data(ttl=3600, show_spinner=False)
def load_symbol_master():
    import requests

    response = requests.get(
        SYMBOL_MASTER_URL,
        timeout=30,
    )
    response.raise_for_status()
    return pd.DataFrame(response.json())


def connect_angel_one(api_key, client_id, mpin, totp_secret):
    if not ANGEL_AVAILABLE:
        raise RuntimeError(
            "SmartAPI packages are missing. Install them first."
        )

    api = SmartConnect(api_key=api_key)

    totp = pyotp.TOTP(
        totp_secret.replace(" ", "")
    ).now()

    response = api.generateSession(
        client_id,
        mpin,
        totp,
    )

    if not response or response.get("status") is False:
        raise RuntimeError(
            str(response)
            if response
            else "Angel One login failed."
        )

    auth_token = response["data"]["jwtToken"]
    feed_token = api.getfeedToken()

    profile = None
    refresh_token = response["data"].get("refreshToken")

    if refresh_token:
        try:
            profile_response = api.getProfile(refresh_token)

            if profile_response.get("status"):
                profile = profile_response.get("data")
        except Exception:
            profile = None

    return api, auth_token, feed_token, profile


def search_symbols(master, query, exchange):
    if master is None or master.empty or not query:
        return pd.DataFrame()

    d = master.copy()

    for col in d.columns:
        d[col] = d[col].astype(str)

    if "exch_seg" not in d.columns or "symbol" not in d.columns:
        return pd.DataFrame()

    d = d[
        d["exch_seg"].str.upper().eq(exchange.upper())
    ].copy()

    q = query.strip().upper()

    name_series = (
        d["name"]
        if "name" in d.columns
        else pd.Series("", index=d.index)
    )

    result = d[
        d["symbol"].str.upper().str.contains(
            q,
            regex=False,
            na=False,
        )
        |
        name_series.str.upper().str.contains(
            q,
            regex=False,
            na=False,
        )
    ].copy()

    # For derivatives/commodities, show contract metadata and prefer the
    # latest expiry rows. This helps avoid accidentally selecting an old
    # generic token such as an outdated MCX SILVERM token.
    if exchange.upper() in {"NFO", "MCX"} and "expiry" in result.columns:
        result["_expiry_sort"] = pd.to_datetime(
            result["expiry"],
            errors="coerce",
            dayfirst=True,
        )
        result = result.sort_values(
            ["_expiry_sort", "symbol"],
            ascending=[False, True],
            na_position="last",
        ).drop(columns=["_expiry_sort"], errors="ignore")

    columns = [
        c for c in [
            "symbol",
            "name",
            "expiry",
            "strike",
            "instrumenttype",
            "token",
            "exch_seg",
            "lotsize",
        ]
        if c in result.columns
    ]

    return result[columns].drop_duplicates().head(100)



# Angel One Historical API limits documented by SmartAPI:
# ONE_MINUTE=30 days, THREE_MINUTE=60, FIVE_MINUTE=100,
# TEN/FIFTEEN=100/200, THIRTY=200, ONE_HOUR=400, ONE_DAY=2000.
# The endpoint is also rate-limited, so requests are deliberately serialized.
HISTORICAL_MAX_DAYS = {
    "ONE_MINUTE": 30,
    "THREE_MINUTE": 60,
    "FIVE_MINUTE": 100,
    "TEN_MINUTE": 100,
    "FIFTEEN_MINUTE": 200,
    "THIRTY_MINUTE": 200,
    "ONE_HOUR": 400,
    "ONE_DAY": 2000,
}


class HistoricalDataError(RuntimeError):
    """Detailed Angel One historical-data error for the UI."""

    def __init__(self, message, diagnostics=None):
        super().__init__(message)
        self.diagnostics = diagnostics or []


# ONE_MINUTE requests can also hit the documented 8,000-record response
# restriction. A smaller chunk keeps long minute-range requests reliable.
SAFE_CHUNK_DAYS = {
    "ONE_MINUTE": 7,
}


def _historical_chunks(from_dt, to_dt, interval):
    max_days = HISTORICAL_MAX_DAYS.get(interval, 30)
    safe_days = min(max_days, SAFE_CHUNK_DAYS.get(interval, max_days))
    chunk_size = timedelta(days=safe_days)
    current = from_dt

    while current < to_dt:
        chunk_end = min(current + chunk_size, to_dt)
        yield current, chunk_end
        if chunk_end >= to_dt:
            break
        # Avoid requesting the exact same boundary candle twice.
        current = chunk_end + timedelta(minutes=1)


def _is_rate_limit_error(response_or_exception):
    text = str(response_or_exception).lower()
    return (
        "exceeding access rate" in text
        or "access denied" in text
        or "rate limit" in text
        or "too many" in text
        or "429" in text
    )


def _get_one_candle_chunk(api, exchange, symbol_token, interval, from_dt, to_dt, retries=3):
    import time as _time

    params = {
        "exchange": str(exchange).upper(),
        "symboltoken": str(symbol_token),
        "interval": str(interval),
        "fromdate": from_dt.strftime("%Y-%m-%d %H:%M"),
        "todate": to_dt.strftime("%Y-%m-%d %H:%M"),
    }

    last_response = None
    last_error = None

    for attempt in range(retries + 1):
        try:
            response = api.getCandleData(params)
            last_response = response

            if not response:
                raise RuntimeError("Angel One returned an empty response object.")

            if response.get("status") is False:
                message = response.get("message") or "Historical API returned status=false."
                errorcode = response.get("errorcode") or ""
                raise RuntimeError(
                    f"{message}" + (f" (errorcode: {errorcode})" if errorcode else "")
                )

            return response.get("data") or [], response

        except Exception as exc:
            last_error = exc
            if not _is_rate_limit_error(exc) or attempt >= retries:
                raise
            _time.sleep(2.0 * (attempt + 1))

    raise RuntimeError(str(last_error))


def fetch_candle_data(
    api,
    exchange,
    symbol_token,
    interval,
    from_dt,
    to_dt,
):
    import time as _time

    all_data = []
    diagnostics = []
    chunks = list(_historical_chunks(from_dt, to_dt, interval))

    for chunk_number, (chunk_from, chunk_to) in enumerate(chunks, start=1):
        if chunk_number > 1:
            # Conservative pacing between historical calls.
            _time.sleep(1.0)

        params_text = {
            "exchange": str(exchange).upper(),
            "symboltoken": str(symbol_token),
            "interval": str(interval),
            "fromdate": chunk_from.strftime("%Y-%m-%d %H:%M"),
            "todate": chunk_to.strftime("%Y-%m-%d %H:%M"),
        }

        try:
            data, response = _get_one_candle_chunk(
                api,
                exchange,
                symbol_token,
                interval,
                chunk_from,
                chunk_to,
            )

            diagnostics.append({
                "chunk": chunk_number,
                "request": params_text,
                "status": response.get("status") if isinstance(response, dict) else None,
                "message": response.get("message", "") if isinstance(response, dict) else "",
                "errorcode": response.get("errorcode", "") if isinstance(response, dict) else "",
                "rows": len(data),
            })

            all_data.extend(data)

        except Exception as exc:
            diagnostics.append({
                "chunk": chunk_number,
                "request": params_text,
                "status": False,
                "message": str(exc),
                "errorcode": "",
                "rows": 0,
            })

            # Continue other chunks; a weekend/holiday/expired contract can
            # legitimately produce no candles for one requested period.
            continue

    if not all_data:
        raise HistoricalDataError(
            "Angel One returned no OHLC candles for this selection.",
            diagnostics=diagnostics,
        )

    df = pd.DataFrame(
        all_data,
        columns=[
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ],
    )

    # Keep the exact Angel One timestamp text for the original-data download.
    df["Angel One Timestamp"] = df["Date"].astype(str)

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce",
    )

    for c in ["Open", "High", "Low", "Close", "Volume"]:
        df[c] = pd.to_numeric(
            df[c],
            errors="coerce",
        )

    df = df.dropna(
        subset=["Date", "Open", "High", "Low", "Close"]
    ).copy()

    df = (
        df.sort_values("Date")
        .drop_duplicates(subset=["Date"], keep="first")
        .reset_index(drop=True)
    )

    return df, diagnostics


def resolve_timeframe(timeframe_value, timeframe_unit):
    """Convert the user's timeframe into an Angel One base interval.

    Angel One's Historical API accepts fixed intervals.  The app therefore
    uses a native interval when possible and aggregates native candles when
    the user enters a custom duration.
    """
    value = int(timeframe_value)
    unit = str(timeframe_unit).strip().lower()

    if value <= 0:
        raise ValueError("Timeframe must be greater than 0.")

    if unit == "minutes":
        if value > 240:
            raise ValueError("Minute timeframe must be between 1 and 240.")

        native = {
            1: "ONE_MINUTE",
            3: "THREE_MINUTE",
            5: "FIVE_MINUTE",
            10: "TEN_MINUTE",
            15: "FIFTEEN_MINUTE",
            30: "THIRTY_MINUTE",
        }

        if value in native:
            return {
                "requested": f"{value} Minute",
                "value": value,
                "unit": "Minutes",
                "base_interval": native[value],
                "resample": False,
                "rule": None,
            }

        # 60 minutes or more can be built more efficiently from ONE_HOUR.
        if value % 60 == 0:
            hours = value // 60
            return {
                "requested": f"{value} Minute ({hours} Hour)",
                "value": value,
                "unit": "Minutes",
                "base_interval": "ONE_HOUR",
                "resample": hours != 1,
                "rule": f"{hours}h",
            }

        return {
            "requested": f"{value} Minute",
            "value": value,
            "unit": "Minutes",
            "base_interval": "ONE_MINUTE",
            "resample": True,
            "rule": f"{value}min",
        }

    if unit == "hours":
        if value > 24:
            raise ValueError("Hour timeframe must be between 1 and 24.")

        return {
            "requested": f"{value} Hour",
            "value": value,
            "unit": "Hours",
            "base_interval": "ONE_HOUR",
            "resample": value != 1,
            "rule": f"{value}h",
        }

    raise ValueError("Timeframe unit must be Minutes or Hours.")


def resample_ohlc(raw_df, timeframe_info, exchange):
    """Build a user-requested timeframe from Angel One base candles."""
    if not timeframe_info.get("resample"):
        return raw_df.copy()

    if raw_df is None or raw_df.empty:
        return raw_df.copy()

    work = raw_df.copy()
    work["Date"] = pd.to_datetime(work["Date"], errors="coerce")
    work = work.dropna(subset=["Date"]).sort_values("Date")

    # Anchor Indian equity/derivative sessions at 09:15 and MCX at 09:00.
    # This makes custom 2/4/20/45-minute or multi-hour candles align to the
    # market session rather than midnight.
    offset = "9h" if str(exchange).upper() == "MCX" else "9h15min"

    indexed = work.set_index("Date")
    agg = (
        indexed[["Open", "High", "Low", "Close", "Volume"]]
        .resample(
            timeframe_info["rule"],
            origin="start_day",
            offset=offset,
            label="left",
            closed="left",
        )
        .agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        })
        .dropna(subset=["Open", "High", "Low", "Close"])
        .reset_index()
    )

    agg["Angel One Timestamp"] = agg["Date"].astype(str)
    return agg


def build_candle_data(df):
    """Create the downloadable candle-data table.

    Keeps the original OHLC columns and adds one column for each of the
    10 candle patterns plus a combined Pattern column.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    candle_df = df.copy()

    # Do not expose the internal helper timestamp column in the candle-data
    # sheet unless it is useful to the user. Keep the original OHLC timestamp
    # as a readable string when available.
    if "Angel One Timestamp" in candle_df.columns:
        candle_df["Date"] = candle_df["Angel One Timestamp"].astype(str)
        candle_df = candle_df.drop(
            columns=["Angel One Timestamp"],
            errors="ignore",
        )

    flags = detect_patterns(
        df.reset_index(drop=True)
    )

    for pattern in PATTERNS:
        candle_df[pattern] = flags[pattern]

    # One combined pattern column is convenient for filtering in Excel.
    candle_df["Pattern"] = ""

    for pattern in PATTERNS:
        mask = candle_df[pattern].astype(str).str.strip() != ""
        candle_df.loc[mask, "Pattern"] = pattern

    # Put the main OHLC fields first, followed by pattern columns.
    preferred = [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "Pattern",
    ]

    pattern_columns = [
        p for p in PATTERNS
        if p in candle_df.columns
    ]

    ordered = [
        c for c in preferred
        if c in candle_df.columns
    ] + pattern_columns

    remaining = [
        c for c in candle_df.columns
        if c not in ordered
    ]

    return candle_df[ordered + remaining]


def original_ohlc_excel_bytes(df, source_name="Angel One"):
    """Download only the original Angel One OHLC data."""
    out = io.BytesIO()

    raw = df.copy()

    if "Angel One Timestamp" in raw.columns:
        date_column = raw["Angel One Timestamp"].astype(str)
    else:
        safe = _excel_safe_df(raw)
        date_column = safe["Date"].astype(str)

    export = pd.DataFrame(
        {
            "Date": date_column,
            "Open": pd.to_numeric(raw["Open"], errors="coerce"),
            "High": pd.to_numeric(raw["High"], errors="coerce"),
            "Low": pd.to_numeric(raw["Low"], errors="coerce"),
            "Close": pd.to_numeric(raw["Close"], errors="coerce"),
            "Volume": (
                pd.to_numeric(raw["Volume"], errors="coerce")
                if "Volume" in raw.columns
                else None
            ),
        }
    )

    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        export.to_excel(
            writer,
            sheet_name="RAW_ANGEL_ONE",
            index=False,
        )

        pd.DataFrame(
            {
                "Field": ["Source", "Rows"],
                "Value": [source_name, len(export)],
            }
        ).to_excel(
            writer,
            sheet_name="INFO",
            index=False,
        )

    out.seek(0)
    return out


def candle_data_excel_bytes(df, source_name="Angel One"):
    """Download OHLC plus all 10 detected candle-pattern columns."""
    out = io.BytesIO()

    candle_df = build_candle_data(df)

    # Pattern detection uses the original numeric/date dataframe, but the
    # downloadable Date can safely be text so +05:30 is preserved.
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        candle_df.to_excel(
            writer,
            sheet_name="CANDLE_DATA",
            index=False,
        )

        pd.DataFrame(
            {
                "Field": ["Source", "Rows", "Patterns"],
                "Value": [
                    source_name,
                    len(candle_df),
                    ", ".join(PATTERNS),
                ],
            }
        ).to_excel(
            writer,
            sheet_name="INFO",
            index=False,
        )

    out.seek(0)
    return out


def complete_excel_bytes(
    df,
    results,
    hold,
    target_percent,
    source_name="Angel One",
    raw_df=None,
):
    """One complete workbook containing raw OHLC, candle data and backtest.

    Sheets:
      1. PARAMETERS
      2. RAW_ANGEL_ONE
      3. CANDLE_DATA
      4. SUMMARY
      5-14. One sheet for each pattern
    """
    out = io.BytesIO()

    raw = (raw_df if raw_df is not None else df).copy()

    if "Angel One Timestamp" in raw.columns:
        raw_date = raw["Angel One Timestamp"].astype(str)
    else:
        raw_date = _excel_safe_df(raw)["Date"].astype(str)

    raw_export = pd.DataFrame(
        {
            "Date": raw_date,
            "Open": pd.to_numeric(raw["Open"], errors="coerce"),
            "High": pd.to_numeric(raw["High"], errors="coerce"),
            "Low": pd.to_numeric(raw["Low"], errors="coerce"),
            "Close": pd.to_numeric(raw["Close"], errors="coerce"),
            "Volume": (
                pd.to_numeric(raw["Volume"], errors="coerce")
                if "Volume" in raw.columns
                else None
            ),
        }
    )

    candle_df = build_candle_data(df)

    summary = []

    for p in PATTERNS:
        x = results.get(p, pd.DataFrame())
        done = x.dropna(subset=["PnL"]) if not x.empty else x

        summary.append(
            {
                "Pattern": p,
                "Entries": len(x),
                "Completed Exits": len(done),
                "Winning Trades": (
                    int((done["PnL"] > 0).sum())
                    if len(done) else 0
                ),
                "Losing Trades": (
                    int((done["PnL"] < 0).sum())
                    if len(done) else 0
                ),
                "Total PnL": (
                    float(done["PnL"].sum())
                    if len(done) else 0
                ),
                "Average PnL %": (
                    float(done["PnL %"].mean())
                    if len(done) else 0
                ),
            }
        )

    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "Parameter": [
                    "Source",
                    "Holding Candles",
                    "Target %",
                    "OHLC Rows",
                ],
                "Value": [
                    source_name,
                    hold,
                    target_percent * 100,
                    len(df),
                ],
            }
        ).to_excel(
            writer,
            sheet_name="PARAMETERS",
            index=False,
        )

        raw_export.to_excel(
            writer,
            sheet_name="RAW_ANGEL_ONE",
            index=False,
        )

        candle_df.to_excel(
            writer,
            sheet_name="CANDLE_DATA",
            index=False,
        )

        pd.DataFrame(summary).to_excel(
            writer,
            sheet_name="SUMMARY",
            index=False,
        )

        for p in PATTERNS:
            _excel_safe_df(
                results.get(p, pd.DataFrame())
            ).to_excel(
                writer,
                sheet_name=p[:31],
                index=False,
            )

    out.seek(0)
    return out


# ============================================================
# SCREEN 1 — CENTERED ANGEL ONE LOGIN
# ============================================================
if not st.session_state.connected:

    st.markdown(
        '<div class="center-wrap">',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="login-title">
            🔐 Angel One Connection
        </div>
        <div class="login-subtitle">
            Connect first, then the Candle Pattern screen will open
        </div>
        """,
        unsafe_allow_html=True,
    )

    api_key = st.text_input(
        "API Key",
        type="password",
    )

    client_id = st.text_input(
        "Client ID",
        value=st.session_state.client_id,
    )

    mpin = st.text_input(
        "MPIN",
        type="password",
    )

    totp_secret = st.text_input(
        "TOTP Secret",
        type="password",
    )

    if not ANGEL_AVAILABLE:
        st.warning(
            "SmartAPI is not installed."
        )
        st.code(
            "pip install smartapi-python pyotp logzero websocket-client openpyxl requests",
            language="bash",
        )

    if st.button(
        "🔐 Connect to Angel One",
        type="primary",
        disabled=not ANGEL_AVAILABLE,
    ):
        if not all(
            [
                api_key.strip(),
                client_id.strip(),
                mpin.strip(),
                totp_secret.strip(),
            ]
        ):
            st.error(
                "Enter API Key, Client ID, MPIN and TOTP Secret."
            )
        else:
            with st.spinner(
                "Connecting to Angel One..."
            ):
                try:
                    api, auth_token, feed_token, profile = (
                        connect_angel_one(
                            api_key.strip(),
                            client_id.strip(),
                            mpin.strip(),
                            totp_secret.strip(),
                        )
                    )

                    st.session_state.smart_api = api
                    st.session_state.auth_token = auth_token
                    st.session_state.feed_token = feed_token
                    st.session_state.client_id = client_id.strip()
                    st.session_state.profile = profile
                    st.session_state.connected = True

                    st.rerun()

                except Exception as e:
                    st.error(
                        f"Angel One connection failed: {e}"
                    )

    st.markdown(
        """
        <div class="info-box">
            🔒 Credentials are kept in the current Streamlit session.
            Do not hard-code API credentials into your GitHub repository.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '</div>',
        unsafe_allow_html=True,
    )

    st.stop()


# ============================================================
# SCREEN 2 — CANDLE PATTERN
# ============================================================
st.markdown(
    """
    <div class="app-header">
        <div class="app-title">
            🕯️ Candles Pattern Backtest
        </div>
        <div class="app-subtitle">
            Angel One → Stock → Timeframe → OHLC → 10 Patterns → Entry → Target → Exit → PnL
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="connected-box">
        🟢 <b>Angel One Connected</b>
    </div>
    """,
    unsafe_allow_html=True,
)

_, disconnect_col = st.columns([5, 1])

with disconnect_col:
    if st.button("Disconnect"):
        st.session_state.connected = False
        st.session_state.smart_api = None
        st.session_state.auth_token = None
        st.session_state.feed_token = None
        st.session_state.ohlc_df = None
        st.session_state.raw_ohlc_df = None
        st.session_state.ohlc_diagnostics = []
        st.session_state.results = None
        st.rerun()


# ============================================================
# MARKET DATA
# ============================================================
st.markdown(
    '<div class="section-card">',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="section-title">📡 Get OHLC Data</div>',
    unsafe_allow_html=True,
)


c1, c2, c3 = st.columns([2, 1, 1])

with c1:
    symbol_query = st.text_input(
        "Search Stock",
        placeholder="SBIN / RELIANCE / TCS",
    )

# Load only after the user starts searching.
if symbol_query.strip() and st.session_state.symbol_master is None:
    try:
        with st.spinner("Loading stock list..."):
            st.session_state.symbol_master = load_symbol_master()
    except Exception as e:
        st.error(f"Stock list could not be loaded: {e}")

with c2:
    exchange = st.selectbox(
        "Exchange",
        ["NSE", "BSE", "NFO", "MCX"],
    )

with c3:
    st.empty()

# ------------------------------------------------------------
# USER-ENTERED TIMEFRAME
# ------------------------------------------------------------
tf_col1, tf_col2 = st.columns([1, 1])

with tf_col2:
    timeframe_unit = st.selectbox(
        "Timeframe Unit",
        ["Minutes", "Hours"],
        index=0,
        key="user_timeframe_unit",
    )

with tf_col1:
    if timeframe_unit == "Minutes":
        timeframe_value = st.number_input(
            "Timeframe",
            min_value=1,
            max_value=240,
            value=5,
            step=1,
            key="user_timeframe_minutes",
            help="Enter any minute timeframe from 1 to 240. Example: 1, 7, 20, 45, 60, 120.",
        )
    else:
        timeframe_value = st.number_input(
            "Timeframe",
            min_value=1,
            max_value=24,
            value=1,
            step=1,
            key="user_timeframe_hours",
            help="Enter any hour timeframe from 1 to 24. Example: 1, 2, 4, 8.",
        )

if timeframe_unit == "Hours" and timeframe_value > 24:
    st.error("Hour timeframe must be between 1 and 24.")
elif timeframe_unit == "Minutes" and timeframe_value > 240:
    st.error("Minute timeframe must be between 1 and 240.")

try:
    timeframe_info = resolve_timeframe(timeframe_value, timeframe_unit)
    st.caption(
        f"Selected timeframe: **{timeframe_info['requested']}** | "
        f"Angel One base interval: **{timeframe_info['base_interval']}**"
        + (" | Custom aggregation enabled." if timeframe_info["resample"] else "")
    )
except ValueError as e:
    timeframe_info = None
    st.error(str(e))

search_results = search_symbols(
    st.session_state.symbol_master,
    symbol_query,
    exchange,
)

selected_symbol = None

if not search_results.empty:
    options = []

    for _, row in search_results.iterrows():
        extra = []

        expiry = str(row.get("expiry", "") or "")
        strike = str(row.get("strike", "") or "")
        instrument_type = str(row.get("instrumenttype", "") or "")

        if expiry and expiry.lower() != "nan":
            extra.append(f"Expiry: {expiry}")
        if strike and strike.lower() != "nan":
            extra.append(f"Strike: {strike}")
        if instrument_type and instrument_type.lower() != "nan":
            extra.append(f"Type: {instrument_type}")

        suffix = (" | " + " | ".join(extra)) if extra else ""

        options.append(
            f"{row.get('symbol', '')} | "
            f"{row.get('name', '')}{suffix} | "
            f"Token: {row.get('token', '')}"
        )

    selected_display = st.selectbox(
        "Select Stock",
        options,
    )

    selected_row = search_results.iloc[
        options.index(selected_display)
    ]

    selected_symbol = {
        "symbol": str(selected_row.get("symbol", "")),
        "token": str(selected_row.get("token", "")),
        "exchange": str(
            selected_row.get(
                "exch_seg",
                exchange,
            )
        ),
    }

    st.caption(
        f"Selected instrument: {selected_symbol['symbol']} | "
        f"Exchange: {selected_symbol['exchange']} | "
        f"Token: {selected_symbol['token']}"
    )

elif symbol_query:
    st.info("No matching stock found.")


d1, d2 = st.columns(2)

with d1:
    from_date = st.date_input(
        "From Date",
        value=date.today() - timedelta(days=5),
    )

with d2:
    to_date = st.date_input(
        "To Date",
        value=date.today(),
    )

t1, t2 = st.columns(2)

with t1:
    from_time = st.time_input(
        "From Time",
        value=time(9, 15),
    )

with t2:
    to_time = st.time_input(
        "To Time",
        value=time(15, 30),
    )

if st.button(
    "📥 Get OHLC Data",
    type="primary",
    disabled=(selected_symbol is None or timeframe_info is None),
):
    if from_date > to_date:
        st.error("From Date cannot be after To Date.")
    else:
        start_dt = datetime.combine(from_date, from_time)
        end_dt = datetime.combine(to_date, to_time)

        if end_dt <= start_dt:
            st.error("To Date/Time must be later than From Date/Time.")
            st.stop()

        with st.spinner(
            f"Getting {selected_symbol['symbol']} {timeframe_info['requested']} OHLC..."
        ):
            try:
                raw_df, diagnostics = fetch_candle_data(
                    st.session_state.smart_api,
                    selected_symbol["exchange"],
                    selected_symbol["token"],
                    timeframe_info["base_interval"],
                    start_dt,
                    end_dt,
                )

                processed_df = resample_ohlc(
                    raw_df,
                    timeframe_info,
                    selected_symbol["exchange"],
                )

                st.session_state.raw_ohlc_df = raw_df.copy()
                st.session_state.ohlc_df = processed_df.copy()
                st.session_state.ohlc_diagnostics = diagnostics
                st.session_state.selected_timeframe = timeframe_info["requested"]
                st.session_state.ohlc_source = (
                    f"{selected_symbol['symbol']} "
                    f"({selected_symbol['exchange']}) | "
                    f"{timeframe_info['requested']}"
                )

                st.success(
                    f"Loaded {len(raw_df):,} Angel One base candles → "
                    f"{len(processed_df):,} candles at {timeframe_info['requested']}."
                )

                if timeframe_info["resample"]:
                    st.info(
                        f"Custom {timeframe_info['requested']} candles were aggregated "
                        f"from {timeframe_info['base_interval']} Angel One data. "
                        "The Original OHLC download contains the raw Angel One base candles."
                    )

                if diagnostics:
                    empty_chunks = [
                        x for x in diagnostics
                        if int(x.get("rows", 0) or 0) == 0
                    ]
                    if empty_chunks:
                        st.info(
                            f"{len(empty_chunks)} historical request chunk(s) returned no candles; "
                            "other chunks were still processed."
                        )

            except HistoricalDataError as e:
                st.error(f"Could not get OHLC data: {e}")
                st.warning(
                    "The login is working, but Angel One returned no usable candles. "
                    "Check the selected contract/token, exchange, date/time range and timeframe."
                )
                with st.expander("🔎 Angel One API Debug Details", expanded=True):
                    st.write({
                            "exchange": selected_symbol["exchange"],
                            "symbol": selected_symbol["symbol"],
                            "symboltoken": selected_symbol["token"],
                            "requested_timeframe": timeframe_info["requested"],
                            "angel_one_base_interval": timeframe_info["base_interval"],
                            "fromdate": start_dt.strftime("%Y-%m-%d %H:%M"),
                            "todate": end_dt.strftime("%Y-%m-%d %H:%M"),
                        })
                    if e.diagnostics:
                        st.dataframe(
                            pd.DataFrame(e.diagnostics),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.info("No chunk-level response was recorded.")
            except Exception as e:
                st.error(f"Could not get OHLC data: {e}")

st.markdown(
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# ORIGINAL ANGEL ONE OHLC DOWNLOAD
# ============================================================
if st.session_state.ohlc_df is not None:
    st.markdown(
        '<div class="section-card">',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="section-title">📥 Original Angel One OHLC</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "This is the raw OHLC returned by Angel One. The timestamp is preserved as text so the IST +05:30 value can be stored in Excel safely."
    )
    raw_col, candle_col = st.columns(2)

    with raw_col:
        st.download_button(
            "⬇️ Download Original OHLC Excel",
            data=original_ohlc_excel_bytes(
                st.session_state.raw_ohlc_df if st.session_state.raw_ohlc_df is not None else st.session_state.ohlc_df,
                st.session_state.ohlc_source or "Angel One",
            ),
            file_name="AngelOne_Original_OHLC.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            key="download_original_ohlc",
            help="Only the original OHLC candles returned by Angel One.",
        )

    with candle_col:
        st.download_button(
            "🕯️ Download Candle Data Excel",
            data=candle_data_excel_bytes(
                st.session_state.ohlc_df,
                st.session_state.ohlc_source or "Angel One",
            ),
            file_name="Candle_Data.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            key="download_candle_data",
            help="OHLC plus all 10 candle-pattern columns for every candle.",
        )

    st.info(
        "You can download the raw Angel One OHLC separately, "
        "or download Candle Data containing every candle plus all 10 "
        "pattern detections."
    )

    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# OPTIONAL EXCEL
# ============================================================
with st.expander("📁 Or upload OHLC Excel instead"):

    excel_file = st.file_uploader(
        "Upload OHLC Excel",
        type=["xlsx", "xls"],
        key="excel_ohlc",
    )

    if excel_file is not None:
        try:
            raw = pd.read_excel(
                excel_file
            )

            lookup = {
                str(c).strip().lower(): c
                for c in raw.columns
            }

            required = [
                "date",
                "open",
                "high",
                "low",
                "close",
            ]

            missing = [
                x for x in required
                if x not in lookup
            ]

            if missing:
                st.error(
                    "Missing columns: "
                    + ", ".join(missing)
                )
            else:
                df = raw[
                    [lookup[x] for x in required]
                ].copy()

                df.columns = [
                    "Date",
                    "Open",
                    "High",
                    "Low",
                    "Close",
                ]

                for c in [
                    "Open",
                    "High",
                    "Low",
                    "Close",
                ]:
                    df[c] = pd.to_numeric(
                        df[c],
                        errors="coerce",
                    )

                df = df.dropna(
                    subset=[
                        "Open",
                        "High",
                        "Low",
                        "Close",
                    ]
                ).reset_index(drop=True)

                st.session_state.raw_ohlc_df = df.copy()
                st.session_state.ohlc_df = df.copy()
                st.session_state.ohlc_source = (
                    f"Excel: {excel_file.name}"
                )

                st.success(
                    f"Loaded {len(df):,} candles."
                )

        except Exception as e:
            st.error(
                f"Could not read Excel: {e}"
            )


# ============================================================
# BACKTEST PARAMETERS
# ============================================================
if st.session_state.ohlc_df is not None:

    st.markdown(
        '<div class="section-card">',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="section-title">⚙️ Backtest Parameters</div>',
        unsafe_allow_html=True,
    )

    p1, p2 = st.columns(2)

    with p1:
        hold = st.selectbox(
            "Exit after how many candles?",
            list(range(1, 31)),
            index=9,
        )

    with p2:
        target_percent_input = st.selectbox(
            "Target %",
            [5, 7, 10],
            index=0,
        )

    target_percent = target_percent_input / 100

    if st.button(
        "▶️ Run Candle Pattern Backtest",
        type="primary",
    ):
        df = st.session_state.ohlc_df.copy()

        flags = detect_patterns(df)

        results = {}

        for pattern in PATTERNS:
            results[pattern] = make_result(
                df,
                pattern,
                int(hold),
                target_percent,
                flags,
            )

        summary = []

        for pattern in PATTERNS:
            x = results[pattern]
            done = (
                x.dropna(subset=["PnL"])
                if not x.empty
                else x
            )

            summary.append(
                {
                    "Pattern": pattern,
                    "Entries": len(x),
                    "Completed Exits": len(done),
                    "Winning Trades": (
                        int((done["PnL"] > 0).sum())
                        if len(done) else 0
                    ),
                    "Losing Trades": (
                        int((done["PnL"] < 0).sum())
                        if len(done) else 0
                    ),
                    "Total PnL": (
                        float(done["PnL"].sum())
                        if len(done) else 0
                    ),
                    "Average PnL %": (
                        float(done["PnL %"].mean())
                        if len(done) else 0
                    ),
                }
            )

        st.session_state.results = results
        st.session_state.summary = pd.DataFrame(
            summary
        )

    st.markdown(
        '</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# RESULTS
# ============================================================
if (
    st.session_state.results is not None
    and st.session_state.summary is not None
):

    results = st.session_state.results
    summary_df = st.session_state.summary
    df = st.session_state.ohlc_df

    st.success(
        f"Loaded {len(df):,} candles | "
        f"Source: {st.session_state.ohlc_source}"
    )

    total_entries = int(
        summary_df["Entries"].sum()
    )

    total_exits = int(
        summary_df["Completed Exits"].sum()
    )

    total_pnl = float(
        summary_df["Total PnL"].sum()
    )

    a, b, c = st.columns(3)

    a.metric(
        "Pattern Entries",
        total_entries,
    )

    b.metric(
        "Completed Exits",
        total_exits,
    )

    c.metric(
        "Total PnL",
        f"{total_pnl:,.4f}",
    )

    st.subheader("📊 Summary")

    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("🕯️ Pattern Results")

    tabs = st.tabs(PATTERNS)

    for tab, pattern in zip(
        tabs,
        PATTERNS,
    ):
        with tab:
            result_df = results[pattern]

            if result_df.empty:
                st.warning(
                    "No occurrences of this pattern were found."
                )
            else:
                st.dataframe(
                    result_df,
                    use_container_width=True,
                    hide_index=True,
                )

    with st.expander("📈 Original Angel One OHLC Data"):
        raw_display = (
            st.session_state.raw_ohlc_df
            if st.session_state.raw_ohlc_df is not None
            else df
        )
        st.dataframe(
            raw_display,
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("🕯️ Candle Timeframe Data Used For Backtest"):
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("📥 Downloads")

    # --------------------------------------------------------
    # 1. RAW ANGEL ONE OHLC
    # --------------------------------------------------------
    st.markdown("### 1️⃣ Original Angel One OHLC")

    st.caption(
        "Downloads the exact raw OHLC candles received from Angel One. "
        "For custom timeframes, this file contains the base candles returned by Angel One."
    )

    st.download_button(
        "⬇️ Download Original Angel One OHLC",
        data=original_ohlc_excel_bytes(
            st.session_state.raw_ohlc_df if st.session_state.raw_ohlc_df is not None else df,
            st.session_state.ohlc_source or "Angel One",
        ),
        file_name="AngelOne_Original_OHLC.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        key="download_original_ohlc_results",
        help="Only the original OHLC data returned by Angel One.",
    )

    st.divider()

    # --------------------------------------------------------
    # 2. FULL CANDLE DATA
    # --------------------------------------------------------
    st.markdown("### 2️⃣ Full Candle Data")

    st.caption(
        "Downloads every OHLC candle plus all 10 candle-pattern "
        "columns and the combined Pattern column."
    )

    st.download_button(
        "🕯️ Download Full Candle Data",
        data=candle_data_excel_bytes(
            df,
            st.session_state.ohlc_source or "Angel One",
        ),
        file_name="Candle_Data_Full.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        key="download_full_candle_data",
        help="All candles with the 10 pattern calculations.",
    )

    st.divider()

    # --------------------------------------------------------
    # 3. BACKTEST RESULT
    # --------------------------------------------------------
    st.markdown("### 3️⃣ Candle Backtest Result")

    st.caption(
        "Contains PARAMETERS, SUMMARY and one result sheet for each "
        "of the 10 candle patterns."
    )

    dl1, dl2 = st.columns(2)

    with dl1:
        st.download_button(
            "⬇️ Download Candle Backtest Excel",
            data=excel_bytes(
                df,
                results,
                int(hold),
                target_percent,
            ),
            file_name="Candle_Backtest_Result.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            key="download_backtest_results",
            help="Backtest parameters, summary and one sheet per pattern.",
        )

    with dl2:
        st.download_button(
            "📦 Download Complete Excel",
            data=complete_excel_bytes(
                df,
                results,
                int(hold),
                target_percent,
                st.session_state.ohlc_source or "Angel One",
                raw_df=st.session_state.raw_ohlc_df,
            ),
            file_name="Complete_AngelOne_Candle_Backtest.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            key="download_complete_workbook",
            help=(
                "One workbook containing RAW_ANGEL_ONE, CANDLE_DATA, "
                "SUMMARY and all 10 pattern result sheets."
            ),
        )

    st.info(
        "The Complete Excel contains all important data in one workbook: "
        "RAW_ANGEL_ONE → CANDLE_DATA → SUMMARY → 10 Pattern Result sheets."
    )

    st.caption(
        "Complete Excel contains RAW_ANGEL_ONE + CANDLE_DATA + SUMMARY "
        "+ all 10 pattern result sheets."
    )
