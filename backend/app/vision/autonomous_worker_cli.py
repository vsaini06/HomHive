"""Opt-in autonomous queue worker: python -m app.vision.autonomous_worker_cli"""
import logging
import os
import time

def main():
    from app.config import load_local_environment
    load_local_environment()
    if os.environ.get('HOMHIVE_ENABLE_AUTONOMOUS_QUEUE','').lower() != 'true' or os.environ.get('HOMHIVE_ENABLE_AUTONOMOUS_SCAN','').lower() != 'true':
        raise SystemExit('Both autonomous feature flags must be true')
    from app.api.app import app
    fn = getattr(app.state, 'autonomous_process_one', None)
    if fn is None:
        raise SystemExit('Autonomous AI pipeline not configured')
    logging.basicConfig(level=logging.INFO)
    logging.info('Autonomous scan worker started; automatic research and planning: %s', 'enabled' if os.environ.get('HOMHIVE_AUTO_ORCHESTRATION','false').lower() == 'true' else 'DISABLED')
    next_pulse = 0.0
    while True:
        try:
            if time.monotonic() >= next_pulse:
                pulse = getattr(app.state, "autonomous_pulse", None)
                if pulse is not None:
                    try:
                        n = pulse()
                        if n:
                            logging.info("Generated %s proactive work-window reminders", n)
                    except Exception as exc:
                        logging.warning("Scheduling pulse unavailable: %s", type(exc).__name__)
                next_pulse = time.monotonic() + 300
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
