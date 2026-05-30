"use client";

import { useEffect, useState } from "react";
import FundCard from "@/components/FundCard";
import {
  AppConfig,
  Snapshot,
  onConfigSnapshot,
  onLatestSnapshotChange,
  getBeijingDateStr,
} from "@/lib/firestore";

type MonitorStatus = "active" | "inactive" | "error";

function getMonitorStatus(snapshot: Snapshot | null): MonitorStatus {
  if (!snapshot) return "inactive";

  const now = new Date();
  const hour = now.getHours();
  const minute = now.getMinutes();
  const currentMinutes = hour * 60 + minute;
  const isTradeTime = currentMinutes >= 600 && currentMinutes <= 870; // 10:00~14:30

  if (!isTradeTime) return "inactive";

  const updatedAt = new Date(snapshot.updated_at);
  const diffMs = now.getTime() - updatedAt.getTime();
  if (diffMs > 15 * 60 * 1000) return "error";

  return "active";
}

function getStatusDot(status: MonitorStatus) {
  switch (status) {
    case "active":
      return "bg-emerald-400 shadow-emerald-400/50";
    case "inactive":
      return "bg-slate-400";
    case "error":
      return "bg-red-400 shadow-red-400/50";
  }
}

function getStatusText(status: MonitorStatus) {
  switch (status) {
    case "active":
      return "监控中";
    case "inactive":
      return "非交易时间";
    case "error":
      return "数据异常";
  }
}

export default function Dashboard() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentDate, setCurrentDate] = useState(getBeijingDateStr);

  useEffect(() => {
    const interval = setInterval(() => {
      const newDate = getBeijingDateStr();
      setCurrentDate((prev) => {
        if (prev !== newDate) return newDate;
        return prev;
      });
    }, 60_000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const unsubConfig = onConfigSnapshot(
      (cfg) => {
        setConfig(cfg);
        setLoading(false);
      },
      (err) => {
        setError("无法连接到数据库，请检查网络连接");
        setLoading(false);
        console.error(err);
      }
    );
    return () => unsubConfig();
  }, []);

  useEffect(() => {
    const unsubSnapshot = onLatestSnapshotChange(
      (snap) => {
        setSnapshot(snap);
      },
      (err) => {
        console.error("快照监听失败:", err);
      }
    );
    return () => unsubSnapshot();
  }, [currentDate]);

  const monitorStatus = getMonitorStatus(snapshot);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen px-4">
        <div className="w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-slate-400 text-sm">正在加载...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen px-4">
        <div className="text-center">
          <div className="text-4xl mb-4">📡</div>
          <p className="text-slate-300 text-base mb-2">连接失败</p>
          <p className="text-slate-400 text-sm">{error}</p>
        </div>
      </div>
    );
  }

  const enabledFunds = config?.funds.filter((f) => f.enabled) ?? [];
  const quotes = snapshot?.quotes ?? {};

  return (
    <div className="px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-white">ETF Notify</h1>
        <div className="flex items-center gap-2">
          <div
            className={`w-2.5 h-2.5 rounded-full shadow-lg ${getStatusDot(monitorStatus)}`}
          />
          <span className="text-slate-400 text-sm">
            {getStatusText(monitorStatus)}
          </span>
        </div>
      </div>

      {/* Fund Cards */}
      {enabledFunds.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-4xl mb-4">📊</div>
          <p className="text-slate-400 text-sm">暂无监控基金</p>
          <p className="text-slate-500 text-xs mt-1">
            请在设置中添加基金
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {enabledFunds.map((fund) => {
            const quote = quotes[fund.code];
            if (!quote) {
              return (
                <div
                  key={fund.code}
                  className="rounded-xl border border-slate-700/50 bg-slate-800/50 p-4"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-white font-medium text-base">
                        {fund.name}
                      </h3>
                      <p className="text-slate-400 text-sm">{fund.code}</p>
                    </div>
                    <span className="text-slate-500 text-sm">等待数据...</span>
                  </div>
                </div>
              );
            }
            return (
              <FundCard
                key={fund.code}
                code={fund.code}
                quote={quote}
                levels={config?.levels ?? []}
              />
            );
          })}
        </div>
      )}

      {/* Last Updated */}
      {snapshot?.updated_at && (
        <p className="text-slate-500 text-xs text-center mt-6">
          最后更新:{" "}
          {new Date(snapshot.updated_at).toLocaleString("zh-CN", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          })}
        </p>
      )}
    </div>
  );
}
