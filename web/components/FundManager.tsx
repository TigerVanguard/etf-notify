"use client";

import { FundConfig } from "@/lib/firestore";
import { useState } from "react";

interface FundManagerProps {
  funds: FundConfig[];
  onToggle: (index: number, enabled: boolean) => void;
  onAdd: (fund: FundConfig) => void;
  onDelete: (index: number) => void;
}

export default function FundManager({
  funds,
  onToggle,
  onAdd,
  onDelete,
}: FundManagerProps) {
  const [showAdd, setShowAdd] = useState(false);
  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState("");

  function handleAdd() {
    if (!newCode.trim() || !newName.trim()) return;
    onAdd({
      code: newCode.trim(),
      name: newName.trim(),
      index: "",
      enabled: true,
    });
    setNewCode("");
    setNewName("");
    setShowAdd(false);
  }

  return (
    <div className="space-y-3">
      {funds.map((fund, index) => (
        <div
          key={fund.code}
          className="flex items-center justify-between bg-slate-800/50 rounded-lg p-3"
        >
          <div className="flex items-center gap-3">
            <button
              onClick={() => onToggle(index, !fund.enabled)}
              className={`w-10 h-6 rounded-full transition-colors relative ${
                fund.enabled ? "bg-blue-500" : "bg-slate-600"
              }`}
            >
              <span
                className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                  fund.enabled ? "left-[18px]" : "left-0.5"
                }`}
              />
            </button>
            <div>
              <p className="text-white text-sm">{fund.name}</p>
              <p className="text-slate-400 text-xs">{fund.code}</p>
            </div>
          </div>
          <button
            onClick={() => onDelete(index)}
            className="text-red-400 hover:text-red-300 p-1"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
          </button>
        </div>
      ))}

      {showAdd ? (
        <div className="bg-slate-800/50 rounded-lg p-3 space-y-2">
          <input
            type="text"
            placeholder="基金代码（如 159941）"
            value={newCode}
            onChange={(e) => setNewCode(e.target.value)}
            className="w-full bg-slate-700 text-white text-sm rounded px-3 py-2 border border-slate-600 focus:border-blue-500 focus:outline-none placeholder-slate-400"
          />
          <input
            type="text"
            placeholder="基金名称（如 纳指ETF）"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="w-full bg-slate-700 text-white text-sm rounded px-3 py-2 border border-slate-600 focus:border-blue-500 focus:outline-none placeholder-slate-400"
          />
          <div className="flex gap-2">
            <button
              onClick={handleAdd}
              className="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded py-2 transition-colors"
            >
              添加
            </button>
            <button
              onClick={() => setShowAdd(false)}
              className="flex-1 bg-slate-700 hover:bg-slate-600 text-white text-sm rounded py-2 transition-colors"
            >
              取消
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setShowAdd(true)}
          className="w-full border border-dashed border-slate-600 rounded-lg p-3 text-slate-400 hover:text-slate-300 hover:border-slate-500 text-sm transition-colors"
        >
          + 添加基金
        </button>
      )}
    </div>
  );
}
