"use client";

import { QuoteData, ThresholdLevel } from "@/lib/firestore";
import StatusBadge from "./StatusBadge";

interface FundCardProps {
  code: string;
  quote: QuoteData;
  levels: ThresholdLevel[];
}

function getTriggeredLevel(
  changePct: number,
  levels: ThresholdLevel[]
): ThresholdLevel | null {
  const sorted = [...levels].sort((a, b) => a.threshold - b.threshold);
  for (const level of sorted) {
    if (changePct <= level.threshold) {
      return level;
    }
  }
  return null;
}

function getCardBgClass(level: ThresholdLevel | null): string {
  if (!level) return "bg-slate-800/50";
  switch (level.color) {
    case "yellow":
      return "bg-yellow-900/30 border-yellow-600/40";
    case "orange":
      return "bg-orange-900/30 border-orange-600/40";
    case "red":
      return "bg-red-900/30 border-red-600/40";
    default:
      return "bg-slate-800/50";
  }
}

export default function FundCard({ code, quote, levels }: FundCardProps) {
  const triggeredLevel = getTriggeredLevel(quote.change_pct, levels);
  const bgClass = getCardBgClass(triggeredLevel);
  const isUp = quote.change_pct >= 0;
  const changeColor = isUp ? "text-emerald-400" : "text-red-400";
  const changeSign = isUp ? "+" : "";

  return (
    <div
      className={`rounded-xl border border-slate-700/50 p-4 ${bgClass} transition-colors duration-300`}
    >
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-white font-medium text-base">{quote.name}</h3>
          <p className="text-slate-400 text-sm">{code}</p>
        </div>
        <StatusBadge level={triggeredLevel} />
      </div>

      <div className="flex items-end justify-between">
        <div>
          <p className="text-white text-2xl font-bold">
            {quote.price.toFixed(3)}
          </p>
          <p className="text-slate-400 text-xs mt-1">
            昨收 {quote.prev_close.toFixed(3)}
          </p>
        </div>
        <div className="text-right">
          <p className={`text-xl font-bold ${changeColor}`}>
            {changeSign}
            {quote.change_pct.toFixed(2)}%
          </p>
          <p className="text-slate-400 text-xs mt-1">
            {isUp ? "↑" : "↓"}{" "}
            {Math.abs(quote.price - quote.prev_close).toFixed(3)}
          </p>
        </div>
      </div>
    </div>
  );
}
