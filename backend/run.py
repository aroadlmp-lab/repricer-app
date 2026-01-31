from app import create_app
from apscheduler.schedulers.background import BackgroundScheduler
from services.repricer import run_repricer

app = create_app()

scheduler = BackgroundScheduler()
scheduler.add_job(func=run_repricer, trigger='interval', minutes=15, args=[app], id='repricer_job')
scheduler.start()

if __name__ == '__main__':
    try:
        app.run(debug=True, port=5000, use_reloader=False)
    finally:
        scheduler.shutdown()
