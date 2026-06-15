"""Task scheduler — connects to APs on schedule and runs speed tests."""

import asyncio
import logging
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .database import Database
from .wifi_connector import WiFiConnector
from .speedtest import SpeedTestRunner
from .metrics import Metrics

logger = logging.getLogger(__name__)


class TaskScheduler:
    def __init__(self, config, db: Database, metrics: Metrics):
        self.config = config
        self.db = db
        self.metrics = metrics
        self.scheduler = AsyncIOScheduler()
        self._running = False
        self._wifi = WiFiConnector(config.wifi.management_interface, config.wifi.backend)
        self._speedtest = SpeedTestRunner(
            config.speedtest.backend, config.speedtest.iperf3_server, config.speedtest.timeout)

    def start(self):
        if self._running:
            return
        tasks = self.db.get_tasks(enabled_only=True)
        for t in tasks:
            self._schedule_one(t)
        logger.info("Scheduler started with %d active tasks", len(tasks))
        self.scheduler.start()
        self._running = True
        self.metrics.task_count.labels(status="active").set(len(tasks))

    def shutdown(self):
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False

    def add_task(self, task_id: int):
        t = self.db.get_task(task_id)
        if t and t.get("enabled"):
            self._schedule_one(t)

    def remove_task(self, task_id: int):
        self.scheduler.remove_job(f"task_{task_id}")

    def reschedule_task(self, task_id: int):
        self.remove_task(task_id)
        self.add_task(task_id)

    def _schedule_one(self, t: dict):
        job_id = f"task_{t['id']}"
        try:
            trigger = CronTrigger.from_crontab(t["schedule"])
        except Exception as e:
            logger.warning("Bad schedule '%s' for task %d: %s", t["schedule"], t["id"], e)
            return
        self.scheduler.add_job(
            self._execute, trigger=trigger, args=[t],
            id=job_id, name=t["name"], replace_existing=True, misfire_grace_time=300)
        logger.info("Scheduled task %d: '%s' every '%s'", t["id"], t["name"], t["schedule"])

    async def _execute(self, t: dict):
        task_id = t["id"]
        ssid = t.get("ssid", "")
        bssid = t.get("bssid", "")
        creds = t.get("credentials_dict", {})
        password = creds.get("password", "")
        start_ts = time.time()
        logger.info("Executing task %d: connect to %s", task_id, ssid)
        self.db.update_task_status(task_id, "running")
        try:
            await self._wifi.disconnect()
            await asyncio.sleep(2)
            cr = await self._wifi.connect(ssid, password)
            if not cr["success"]:
                logger.warning("Task %d connect failed: %s", task_id, cr["message"])
                self.db.update_task_status(task_id, f"connect_failed: {cr['message'][:100]}")
                return

            sr = await self._speedtest.run(self.config.wifi.management_interface)
            rd = sr.to_dict()
            rd["bssid"] = bssid
            rd["ssid"] = ssid
            self.db.add_speedtest(rd)
            self.metrics.update_speedtest(rd, ssid, bssid)

            await self._wifi.disconnect()

            dur = time.time() - start_ts
            status = "success" if sr.success else f"failed: {sr.error[:100]}"
            self.db.update_task_status(task_id, status)
            self.metrics.task_duration.labels(task_id=str(task_id), status=status).set(dur)
            logger.info("Task %d done: %.1f↓ %.1f↑ Mbps in %.0fs",
                        task_id, sr.download_mbps, sr.upload_mbps, dur)
        except Exception as e:
            logger.error("Task %d exception: %s", task_id, e)
            self.db.update_task_status(task_id, f"error: {str(e)[:100]}")
            try:
                await self._wifi.disconnect()
            except Exception:
                pass
