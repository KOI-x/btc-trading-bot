import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import requests


def run(cmd):
    """Run a command and stream its output."""
    print(f"Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, text=True)
    if proc.returncode != 0:
        sys.exit(proc.returncode)


def import_external_strategy(url: str) -> None:
    """Download and backtest a Freqtrade strategy from GitHub or Gist."""
    strategies_dir = Path("strategies")
    strategies_dir.mkdir(exist_ok=True)

    file_name = Path(re.sub(r"\?.*", "", url)).name
    if not file_name.endswith(".py"):
        print("La URL debe apuntar a un archivo .py")
        return

    dest = strategies_dir / file_name

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        dest.write_text(resp.text, encoding="utf-8")
    except requests.RequestException as exc:
        print(f"[ERROR] No se pudo descargar la estrategia: {exc}")
        return

    content = dest.read_text(encoding="utf-8")
    if "class Strategy" not in content:
        print("[ERROR] El archivo no contiene una clase Strategy")
        dest.unlink(missing_ok=True)
        return

    try:
        spec = importlib.util.spec_from_file_location(dest.stem, dest)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
    except Exception as exc:
        print(f"[ERROR] No se pudo importar la estrategia: {exc}")
        dest.unlink(missing_ok=True)
        return

    if importlib.util.find_spec("freqtrade") is None:
        print("Freqtrade no esta instalado. Instala freqtrade para el backtest.")
        return

    cfg_dir = Path("user_data")
    cfg_dir.mkdir(exist_ok=True)
    cfg_file = cfg_dir / "backtest_config.json"

    if not cfg_file.exists():
        cfg = {
            "dry_run": True,
            "strategy": dest.stem,
            "stake_currency": "USDT",
            "stake_amount": 1000,
            "exchange": {"name": "binance"},
            "pair_whitelist": ["BTC/USDT"],
            "timeframe": "1d",
        }
        cfg_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    end = date.today()
    start = end - timedelta(days=365)
    timerange = f"{start:%Y%m%d}-{end:%Y%m%d}"

    cmd = [
        "freqtrade",
        "backtesting",
        "-s",
        dest.stem,
        "--config",
        str(cfg_file),
        f"--timerange={timerange}",
    ]

    try:
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] Backtesting fallo: {exc.output}")
        return

    sharpe = None
    cagr = None
    for line in output.splitlines():
        if "Sharpe Ratio" in line:
            match = re.search(r"(-?\d+\.\d+)", line)
            if match:
                sharpe = match.group(1)
        if "CAGR" in line:
            match = re.search(r"(-?\d+\.\d+)", line)
            if match:
                cagr = match.group(1)

    print(f"Sharpe: {sharpe or 'N/A'} | CAGR: {cagr or 'N/A'}")


def main():
    venv_dir = Path(".venv")
    if not venv_dir.exists():
        print("Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])

    python = (
        venv_dir
        / ("Scripts" if os.name == "nt" else "bin")
        / ("python.exe" if os.name == "nt" else "python")
    )

    run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(python), "-m", "pip", "install", "-r", "requirements.txt"])
    run([str(python), "-m", "pip", "install", "-e", "."])

    run([str(python), "data_ingestion/historic_fetcher.py"])

    run([str(python), "backtests/ema_s2f_backtest.py", "--save", "equity_curve.png"])


if __name__ == "__main__":
    main()
