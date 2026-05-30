"use client";

import { ThresholdLevel } from "@/lib/firestore";
import { useState } from "react";

interface ThresholdConfigProps {
  levels: ThresholdLevel[];
  onSave: (levels: ThresholdLevel[]) => void;
}

export default function ThresholdConfig({
  levels,
  onSave,
}: ThresholdConfigProps) {
  const [editingLevels, setEditingLevels] = useState<ThresholdLevel[]>(levels);

  function handleChange(index: number, value: string) {
    const num = parseFloat(value);
    if (isNaN(num)) return;
    const updated = [...editingLevels];
    updated[index] = { ...updated[index], threshold: num };
    setEditingLevels(updated);
    onSave(updated);
  }

  function getLevelIcon(color: string) {
    switch (color) {
      case "yellow":
        return "🟡";
      case "orange":
        return "🟠";
      case "red":
        return "🔴";
      default:
        return "⚪";
    }
  }

  return (
    <div className="space-y-3">
      {editingLevels.map((level, index) => (
        <div
          key={level.name}
          className="flex items-center justify-between bg-slate-800/50 rounded-lg p-3"
        >
          <div className="flex items-center gap-2">
            <span>{getLevelIcon(level.color)}</span>
            <span className="text-white text-sm">{level.name}</span>
          </div>
          <div className="flex items-center gap-1">
            <input
              type="number"
              step="0.5"
              value={level.threshold}
              onChange={(e) => handleChange(index, e.target.value)}
              className="w-20 bg-slate-700 text-white text-sm rounded px-2 py-1 text-right border border-slate-600 focus:border-blue-500 focus:outline-none"
            />
            <span className="text-slate-400 text-sm">%</span>
          </div>
        </div>
      ))}
    </div>
  );
}
