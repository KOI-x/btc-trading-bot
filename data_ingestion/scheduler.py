import schedule
import time
from fetcher import guardar_precio


def job():
    try:
        guardar_precio()
    except Exception as e:
        print(f"Error al guardar el precio: {e}")


if __name__ == "__main__":
    schedule.every(10).minutes.do(job)
    job()
    while True:
        schedule.run_pending()
        time.sleep(1)
