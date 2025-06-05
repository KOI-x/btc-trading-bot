import os
import sys
import subprocess
from pathlib import Path


def run(cmd):
    """Run a command and stream its output."""
    print(f"Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, text=True)
    if proc.returncode != 0:
        sys.exit(proc.returncode)


def main():
    venv_dir = Path('.venv')
    if not venv_dir.exists():
        print('Creating virtual environment...')
        subprocess.check_call([sys.executable, '-m', 'venv', str(venv_dir)])

    python = venv_dir / ('Scripts' if os.name == 'nt' else 'bin') / ('python.exe' if os.name == 'nt' else 'python')

    run([str(python), '-m', 'pip', 'install', '--upgrade', 'pip'])
    run([str(python), '-m', 'pip', 'install', '-r', 'requirements.txt'])
    run([str(python), '-m', 'pip', 'install', '-e', '.'])

    run([str(python), 'data_ingestion/historic_fetcher.py'])

    run([str(python), 'backtests/ema_s2f_backtest.py', '--save', 'equity_curve.png'])


if __name__ == '__main__':
    main()
