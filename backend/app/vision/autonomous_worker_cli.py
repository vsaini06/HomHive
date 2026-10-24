"""Opt-in autonomous queue worker: python -m app.vision.autonomous_worker_cli"""
import logging
import os
import time

def main():
    if os.environ.get('HOMHIVE_ENABLE_AUTONOMOUS_QUEUE','').lower() != 'true' or os.environ.get('HOMHIVE_ENABLE_AUTONOMOUS_SCAN','').lower() != 'true':
        raise SystemExit('Both autonomous feature flags must be true')
    from app.api.app import app
    fn = getattr(app.state, 'autonomous_process_one', None)
    if fn is None:
        raise SystemExit('Autonomous AI pipeline not configured')
    logging.basicConfig(level=logging.INFO)
    logging.info('Autonomous scan worker started')
    while True:
        try:
            result=fn()
            if result is None:
                time.sleep(5)
            else:
                logging.info('Autonomous job finished with state %s', result)
        except KeyboardInterrupt:
            break
        except Exception:
            logging.exception('Worker error; scan jobs remain durable')
            time.sleep(10)

if __name__ == '__main__':
    main()
