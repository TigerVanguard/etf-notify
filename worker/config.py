import json
import logging
import os

import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "funds": [
        {"code": "159941", "name": "纳指ETF", "index": "纳斯达克100", "enabled": True},
        {"code": "513100", "name": "纳指ETF", "index": "纳斯达克100", "enabled": True},
        {"code": "513500", "name": "标普500ETF", "index": "标普500", "enabled": True},
        {"code": "159612", "name": "标普500ETF", "index": "标普500", "enabled": True},
    ],
    "levels": [
        {"name": "提醒", "threshold": -1.0, "color": "yellow"},
        {"name": "警告", "threshold": -2.0, "color": "orange"},
        {"name": "紧急", "threshold": -3.0, "color": "red"},
    ],
    "cooldown_minutes": 60,
    "fcm_enabled": True,
}


def init_firebase():
    """Initialize Firebase Admin SDK from FIREBASE_CREDENTIALS env var."""
    if firebase_admin._apps:
        return firestore.client()

    creds_json = os.environ.get("FIREBASE_CREDENTIALS")
    if not creds_json:
        raise EnvironmentError(
            "FIREBASE_CREDENTIALS environment variable is not set"
        )

    creds_dict = json.loads(creds_json)
    cred = credentials.Certificate(creds_dict)
    firebase_admin.initialize_app(cred)
    logger.info("Firebase 初始化成功")
    return firestore.client()


def load_config(db=None):
    """Load configuration from Firestore, creating defaults if none exist."""
    if db is None:
        db = firestore.client()

    try:
        doc = db.collection("config").document("settings").get()
        if doc.exists:
            config = doc.to_dict()
            logger.info("从 Firestore 加载配置成功")
            for key, default_value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = default_value
            return config
    except Exception:
        logger.exception("读取 Firestore 配置失败，使用默认配置")
        return dict(DEFAULT_CONFIG)

    logger.info("Firestore 无配置，写入默认配置")
    try:
        db.collection("config").document("settings").set(DEFAULT_CONFIG)
        logger.info("默认配置已写入 Firestore")
    except Exception:
        logger.exception("写入默认配置到 Firestore 失败")
    return dict(DEFAULT_CONFIG)
