import {
  doc,
  getDoc,
  updateDoc,
  collection,
  query,
  orderBy,
  limit as firestoreLimit,
  getDocs,
  onSnapshot,
  Unsubscribe,
} from "firebase/firestore";
import { db } from "./firebase";

export function getBeijingDateStr(): string {
  const now = new Date();
  const beijingTime = new Date(
    now.getTime() + (8 * 60 + now.getTimezoneOffset()) * 60000
  );
  return beijingTime.toISOString().split("T")[0];
}

export interface FundConfig {
  code: string;
  name: string;
  index: string;
  enabled: boolean;
}

export interface ThresholdLevel {
  name: string;
  threshold: number;
  color: string;
}

export interface AppConfig {
  funds: FundConfig[];
  levels: ThresholdLevel[];
  cooldown_minutes: number;
  pushdeer_key: string;
  fcm_enabled: boolean;
}

export interface QuoteData {
  name: string;
  price: number;
  prev_close: number;
  change_pct: number;
  high: number;
  low: number;
  volume: number;
}

export interface Snapshot {
  date: string;
  updated_at: string;
  quotes: Record<string, QuoteData>;
}

export interface NotificationRecord {
  fund_code: string;
  fund_name: string;
  level: string;
  change_pct: number;
  price: number;
  timestamp: string;
  channels: string[];
  delivered: boolean;
}

export async function getConfig(): Promise<AppConfig | null> {
  const docRef = doc(db, "config", "settings");
  const snapshot = await getDoc(docRef);
  if (snapshot.exists()) {
    return snapshot.data() as AppConfig;
  }
  return null;
}

export async function updateConfig(
  partial: Partial<AppConfig>
): Promise<void> {
  const docRef = doc(db, "config", "settings");
  await updateDoc(docRef, partial);
}

export async function getLatestSnapshot(): Promise<Snapshot | null> {
  const dateStr = getBeijingDateStr();
  const docRef = doc(db, "snapshots", dateStr);
  const snapshot = await getDoc(docRef);
  if (snapshot.exists()) {
    return snapshot.data() as Snapshot;
  }
  return null;
}

export async function getNotifications(
  count: number = 20
): Promise<NotificationRecord[]> {
  const colRef = collection(db, "notifications");
  const q = query(colRef, orderBy("timestamp", "desc"), firestoreLimit(count));
  const snapshot = await getDocs(q);
  return snapshot.docs.map((doc) => doc.data() as NotificationRecord);
}

export function onConfigSnapshot(
  callback: (config: AppConfig | null) => void,
  onError?: (error: Error) => void
): Unsubscribe {
  const docRef = doc(db, "config", "settings");
  return onSnapshot(
    docRef,
    (snapshot) => {
      if (snapshot.exists()) {
        callback(snapshot.data() as AppConfig);
      } else {
        callback(null);
      }
    },
    (error) => {
      console.error("Config snapshot error:", error);
      onError?.(error);
    }
  );
}

export function onLatestSnapshotChange(
  callback: (snapshot: Snapshot | null) => void,
  onError?: (error: Error) => void
): Unsubscribe {
  const dateStr = getBeijingDateStr();
  const docRef = doc(db, "snapshots", dateStr);
  return onSnapshot(
    docRef,
    (snap) => {
      if (snap.exists()) {
        callback(snap.data() as Snapshot);
      } else {
        callback(null);
      }
    },
    (error) => {
      console.error("Snapshot listener error:", error);
      onError?.(error);
    }
  );
}
