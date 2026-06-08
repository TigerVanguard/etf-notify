import logging

import requests
from firebase_admin import messaging

logger = logging.getLogger(__name__)

PUSHDEER_API = "https://api2.pushdeer.com/message/push"


def send_pushdeer(key: str, title: str, content: str) -> bool:
    """Send a notification via PushDeer API. Returns True on success."""
    if not key:
        logger.warning("PushDeer Key 未配置，跳过推送")
        return False

    try:
        params = {
            "pushkey": key,
            "text": title,
            "desp": content,
            "type": "markdown",
        }
        resp = requests.get(PUSHDEER_API, params=params, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("code") != 0:
            logger.error("PushDeer 业务失败: title=%s response=%s", title, payload)
            return False
        logger.info("PushDeer 推送成功: %s", title)
        return True
    except Exception:
        logger.exception("PushDeer 推送失败: %s", title)
        return False


def send_fcm(topic: str, title: str, body: str, data: dict | None = None) -> bool:
    """Send a notification via Firebase Cloud Messaging. Returns True on success."""
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            topic=topic,
        )
        response = messaging.send(message)
        logger.info("FCM 推送成功: %s (response=%s)", title, response)
        return True
    except Exception:
        logger.exception("FCM 推送失败: %s", title)
        return False
