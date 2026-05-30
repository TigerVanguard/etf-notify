"use client";

import { ThresholdLevel } from "@/lib/firestore";

interface StatusBadgeProps {
  level: ThresholdLevel | null;
}

function getBadgeStyle(level: ThresholdLevel | null) {
  if (!level) {
    return {
      bg: "bg-slate-600/50",
      text: "text-slate-300",
      label: "正常",
    };
  }
  switch (level.color) {
    case "yellow":
      return {
        bg: "bg-yellow-500/20",
        text: "text-yellow-300",
        label: level.name,
      };
    case "orange":
      return {
        bg: "bg-orange-500/20",
        text: "text-orange-300",
        label: level.name,
      };
    case "red":
      return {
        bg: "bg-red-500/20",
        text: "text-red-300",
        label: level.name,
      };
    default:
      return {
        bg: "bg-slate-600/50",
        text: "text-slate-300",
        label: level.name,
      };
  }
}

export default function StatusBadge({ level }: StatusBadgeProps) {
  const style = getBadgeStyle(level);
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${style.bg} ${style.text}`}
    >
      {style.label}
    </span>
  );
}
