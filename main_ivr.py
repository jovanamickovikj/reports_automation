"""
Report pipeline - run 2 of 2 (IVR + mail).

    python main_ivr.py

Takes the report that main.py processed (remembered in pending_ivr.json), saves the IVR files
and sends the automatic mail. It does not download anything and does not wait: schedule it in
Windows Task Scheduler after main.py.
"""
import logging
import sys

import truststore

from pipeline.IvrRun import IvrRun
from pipeline.LogSetup import LogSetup
from pipeline.Settings import Settings

log = logging.getLogger("pipeline")


def main() -> int:
    truststore.inject_into_ssl()
    settings = Settings.load()
    LogSetup.start_logging(settings.log_file)
    try:
        return IvrRun(settings).run()
    except Exception:
        log.exception("IVR run failed")
        return 1  # non-zero exit code, so Task Scheduler shows the run as failed


if __name__ == "__main__":
    sys.exit(main())
