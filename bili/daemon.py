import argparse, json, logging, os, signal, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def setup_logging(logfile):
    os.makedirs(os.path.dirname(logfile), exist_ok=True)
    logging.basicConfig(filename=logfile, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

def run_once(sched):
    try:
        return sched.tick()
    except Exception as e:
        logging.exception("tick failed")

def main(argv=None):
    p = argparse.ArgumentParser()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p.add_argument("--config", default=os.path.join(root, "config.json"))
    args = p.parse_args(argv)
    cfg = json.load(open(args.config))
    logfile = cfg.get("log_file", "logs/daemon.log")
    setup_logging(logfile)
    ready_dir = cfg["ready_dir"]; os.makedirs(ready_dir, exist_ok=True)
    from bili.scheduler import Scheduler
    from bili.state import StateStore
    from bili.uploader import Uploader
    store = StateStore(cfg.get("state_file", "state.json"))
    sched = Scheduler(cfg, store)
    sched.uploader = Uploader()
    stopping = False
    def on_sig(s, f):
        nonlocal stopping; stopping = True
    signal.signal(signal.SIGTERM, on_sig)
    signal.signal(signal.SIGINT, on_sig)
    while not stopping:
        logging.info("tick")
        run_once(sched)
        time.sleep(cfg.get("interval", 300))

if __name__ == "__main__":
    main()
