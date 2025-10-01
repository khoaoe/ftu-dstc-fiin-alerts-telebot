from __future__ import annotations

    import importlib
    import importlib.util
    import sys
    from pathlib import Path
    from types import ModuleType
    from typing import Callable, Iterable

    import numpy as np
    import pandas as pd

    MARKET_TICKER_CANDIDATES: tuple[str, ...] = (
        "VNINDEX",
        "VNINDEX-INDEX",
        "^VNINDEX",
    )


    def _ensure_matplotlib_stub(force: bool = False) -> None:
        if not force and "matplotlib" in sys.modules and "matplotlib.pyplot" in sys.modules:
            return

        import types

        def _noop(*args, **kwargs):
            return None

        class _Axes(types.SimpleNamespace):
            def plot(self, *args, **kwargs):
                return None

            def fill_between(self, *args, **kwargs):
                return None

            def bar(self, *args, **kwargs):
                return None

            def hist(self, *args, **kwargs):
                return None

            def set_title(self, *args, **kwargs):
                return None

            def set_ylabel(self, *args, **kwargs):
                return None

            def set_xlabel(self, *args, **kwargs):
                return None

            def legend(self, *args, **kwargs):
                return None

            def grid(self, *args, **kwargs):
                return None

        def _subplots(*args, **kwargs):
            axes = [_Axes() for _ in range(kwargs.get("nrows", args[0] if args else 1) * kwargs.get("ncols", args[1] if len(args) > 1 else 1))]
            if len(axes) == 1:
                axes = axes[0]
            return None, axes

        matplotlib_module = types.ModuleType("matplotlib")
        pyplot_module = types.ModuleType("pyplot")
        pyplot_module.plot = _noop
        pyplot_module.figure = _noop
        pyplot_module.subplots = _subplots
        pyplot_module.show = _noop
        pyplot_module.close = _noop
        pyplot_module.style = types.SimpleNamespace(use=_noop)
        pyplot_module.fill_between = _noop
        pyplot_module.bar = _noop
        pyplot_module.hist = _noop
        pyplot_module.title = _noop
        pyplot_module.ylabel = _noop
        pyplot_module.xlabel = _noop

        matplotlib_module.pyplot = pyplot_module
        sys.modules.setdefault("matplotlib", matplotlib_module)
        sys.modules.setdefault("matplotlib.pyplot", pyplot_module)


    def _load_v12_from_spec(spec: importlib.machinery.ModuleSpec) -> ModuleType | None:
        if not spec or not spec.loader:
            return None

        module = ModuleType(spec.name or "v12_user")
        module.__file__ = spec.origin
        module.__package__ = spec.name.rpartition(".")[0]

        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            return module
        except ModuleNotFoundError as exc:
            if exc.name == "matplotlib":
                _ensure_matplotlib_stub(force=True)
                try:
                    spec.loader.exec_module(module)  # type: ignore[union-attr]
                    return module
                except Exception:
                    return None
            return None
        except Exception:
            return None


    def _load_v12_from_file(file_path: Path) -> ModuleType | None:
        if not file_path.exists():
            return None

        try:
            code = file_path.read_text(encoding="utf-8")
        except OSError:
            return None

        for marker in ("
# 4.", "
## 4."):
            idx = code.find(marker)
            if idx != -1:
                code = code[:idx]
                break

        module = ModuleType("v12_user")
        module.__file__ = str(file_path)
        module.__package__ = ""

        _ensure_matplotlib_stub()

        try:
            exec(compile(code, str(file_path), "exec"), module.__dict__)
            return module
        except ModuleNotFoundError as exc:
            if exc.name == "matplotlib":
                _ensure_matplotlib_stub(force=True)
                try:
                    exec(compile(code, str(file_path), "exec"), module.__dict__)
                    return module
                except Exception:
                    return None
            return None
        except Exception:
            return None


    def _load_v12() -> ModuleType | None:
        candidate_modules = (
            "v12",
            "strategies.v12",
            "round_2.v12",
        )

        for name in candidate_modules:
            try:
                return importlib.import_module(name)
            except ModuleNotFoundException:
                continue
            except ModuleNotFoundError as exc:
                if exc.name == "matplotlib":
                    _ensure_matplotlib_stub(force=True)
                    try:
                        return importlib.import_module(name)
                    except Exception:
                        continue
                continue
            except Exception:
                continue

        base_dir = Path(__file__).resolve().parent.parent
        candidate_files = (
            base_dir / "v12.py",
            base_dir / "round_2" / "v12.py",
        )

        for file_path in candidate_files:
            module = _load_v12_from_file(file_path)
            if module:
                return module

        return None


    class ModuleNotFoundException(Exception):
        pass


    _v12 = _load_v12()


    def _ema(series: pd.Series, span: int) -> pd.Series:
        return series.ewm(span=span, adjust=False).mean()


    def _calc_rsi(series: pd.Series, window: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / window, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / window, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))


    def _calc_atr(group: pd.DataFrame, window: int = 14) -> pd.Series:
        close = group["close_adj"]
        high = group["high"]
        low = group["low"]
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        return tr.rolling(window, min_periods=window).mean()


    def _prepare_for_v12(raw: pd.DataFrame) -> pd.DataFrame:
        if raw.empty:
            return raw

        df = raw.copy()

        time_col = None
        for col_candidate in ("timestamp", "time", "date"):
            if col_candidate in df.columns:
                time_col = col_candidate
                break

        if time_col is None:
            raise ValueError("Input dataframe must contain a timestamp/time column")

        df["time"] = pd.to_datetime(df[time_col])
        if "ticker" not in df.columns:
            raise ValueError("Input dataframe must contain a ticker column")

        df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
        df.sort_values(["time", "ticker"], inplace=True)

        if "adj_factor" not in df.columns:
            df["adj_factor"] = 1.0

        df["close_adj"] = df["close"] * df["adj_factor"].astype(float)

        grouped = df.groupby("ticker", group_keys=False)

        df["volume_ma20"] = grouped["volume"].transform(lambda s: s.rolling(20, min_periods=20).mean())
        df["volume_spike"] = df["volume"] / df["volume_ma20"].replace(0, np.nan)

        df["sma_5"] = grouped["close_adj"].transform(lambda s: s.rolling(5, min_periods=5).mean())
        df["sma_50"] = grouped["close_adj"].transform(lambda s: s.rolling(50, min_periods=50).mean())
        df["sma_200"] = grouped["close_adj"].transform(lambda s: s.rolling(200, min_periods=200).mean())

        df["rsi_14"] = grouped["close_adj"].transform(_calc_rsi)

        ema12 = grouped["close_adj"].transform(lambda s: _ema(s, 12))
        ema26 = grouped["close_adj"].transform(lambda s: _ema(s, 26))
        df["macd"] = ema12 - ema26
        df["macd_signal"] = grouped["macd"].transform(lambda s: _ema(s, 9))

        ma20 = grouped["close_adj"].transform(lambda s: s.rolling(20, min_periods=20).mean())
        std20 = grouped["close_adj"].transform(lambda s: s.rolling(20, min_periods=20).std())
        df["boll_upper"] = ma20 + 2 * std20
        df["boll_lower"] = ma20 - 2 * std20
        df["boll_width"] = (df["boll_upper"] - df["boll_lower"]) / ma20.replace(0, np.nan)

        df["atr_14"] = grouped.apply(_calc_atr).reset_index(level=0, drop=True)

        market_mask = df["ticker"].isin(MARKET_TICKER_CANDIDATES)
        if market_mask.any():
            market = df[market_mask].copy()
            market = market.loc[:, ["time", "close_adj", "high", "low"]]
            market.rename(columns={"close_adj": "market_close"}, inplace=True)
            market.set_index("time", inplace=True)

            market_features = pd.DataFrame(index=market.index)
            market_features["market_close"] = market["market_close"]
            market_features["market_MA50"] = market["market_close"].rolling(50, min_periods=50).mean()
            market_features["market_MA200"] = market["market_close"].rolling(200, min_periods=200).mean()
            market_features["market_rsi"] = _calc_rsi(market["market_close"])

            sma = market["market_close"].rolling(20, min_periods=20).mean()
            std = market["market_close"].rolling(20, min_periods=20).std()
            boll_upper = sma + 2 * std
            boll_lower = sma - 2 * std
            market_features["market_boll_width"] = (boll_upper - boll_lower) / sma.replace(0, np.nan)

            if _v12 and hasattr(_v12, "calculate_adx"):
                market_df = pd.DataFrame({
                    "high": market["high"],
                    "low": market["low"],
                    "close": market_features["market_close"],
                })
                market_features["market_adx"] = _v12.calculate_adx(market_df, n=14)
            else:
                market_features["market_adx"] = np.nan

            df = df.merge(market_features.reset_index(), on="time", how="left")
            df = df[~market_mask]
        else:
            df["market_close"] = np.nan
            df["market_MA50"] = np.nan
            df["market_MA200"] = np.nan
            df["market_rsi"] = np.nan
            df["market_boll_width"] = np.nan
            df["market_adx"] = np.nan

        df.set_index("time", inplace=True)
        return df.sort_index()


    def compute_picks_from_daily_df(df_history: pd.DataFrame) -> list[str]:
        """Return tickers picked by V12 strategy (or fallback) for the latest session."""
        if df_history is None or df_history.empty:
            return []

        if _v12 and hasattr(_v12, "precompute_technical_indicators_vectorized"):
            try:
                prepared = _prepare_for_v12(df_history)
                if prepared.empty:
                    raise ValueError("Prepared dataframe is empty")

                enriched = _v12.precompute_technical_indicators_vectorized(prepared)
                latest_index = enriched.index.max()
                df_day = enriched.loc[enriched.index == latest_index].copy()

                for candidate in ("apply_enhanced_screener_v12", "apply_enhanced_screener_v12_sideway_soft"):
                    screener: Callable | None = getattr(_v12, candidate, None)
                    if screener:
                        picks = list(dict.fromkeys(screener(df_day)))  # preserve order & uniqueness
                        if picks:
                            return picks
                return []
            except Exception:
                pass

        import numpy as np  # local import for fallback

        df_latest = df_history.copy()
        if "timestamp" in df_latest.columns:
            max_ts = df_latest["timestamp"].max()
            df_latest = df_latest[df_latest["timestamp"] == max_ts]

        picks: list[str] = []
        grouped = df_latest.groupby("ticker")
        for tk, g in grouped:
            if len(g) < 50:
                continue
            closes = g["close"].to_numpy(dtype=float)
            ma20 = closes[-20:].mean()
            ma50 = closes[-50:].mean()
            if closes[-1] > ma20 > ma50:
                picks.append(tk)
        return picks


    def early_signal_from_15m_bar(prev_bar_row: dict) -> bool:
        """Intraday early condition (demo). Replace by your real V12 intraday premises."""
        vol = float(prev_bar_row.get("volume", 0))
        bu = float(prev_bar_row.get("bu", 0))
        sd = float(prev_bar_row.get("sd", 0))
        return vol > 0 and (bu - sd) > 0 and (bu / max(sd, 1)) > 1.2
