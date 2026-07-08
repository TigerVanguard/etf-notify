"use client";

import { useEffect, useState, useCallback } from "react";
import FundManager from "@/components/FundManager";
import ThresholdConfig from "@/components/ThresholdConfig";
import {
  AppConfig,
  FundConfig,
  ThresholdLevel,
  getConfig,
  updateConfig,
} from "@/lib/firestore";

export default function SettingsPage() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);
  // Ad-hoc test key: used only for the test push request, never persisted
  const [testKey, setTestKey] = useState("");
  const [cooldownInput, setCooldownInput] = useState("");

  useEffect(() => {
    loadConfig();
  }, []);

  async function loadConfig() {
    try {
      const cfg = await getConfig();
      setConfig(cfg);
      if (cfg) {
        setCooldownInput(String(cfg.cooldown_minutes));
      } else {
        setError("not_initialized");
      }
    } catch (err) {
      console.error("Failed to load config:", err);
      setError("connection_failed");
    } finally {
      setLoading(false);
    }
  }

  const saveConfig = useCallback(
    async (partial: Partial<AppConfig>): Promise<boolean> => {
      setSaving(true);
      setSaveError(null);
      try {
        await updateConfig(partial);
        setConfig((prev) => (prev ? { ...prev, ...partial } : prev));
        return true;
      } catch (err) {
        console.error("Failed to save config:", err);
        setSaveError("保存失败，请重试");
        return false;
      } finally {
        setSaving(false);
      }
    },
    []
  );

  function handleFundToggle(index: number, enabled: boolean) {
    if (!config) return;
    const updated = [...config.funds];
    updated[index] = { ...updated[index], enabled };
    saveConfig({ funds: updated });
  }

  function handleFundAdd(fund: FundConfig) {
    if (!config) return;
    const updated = [...config.funds, fund];
    saveConfig({ funds: updated });
  }

  function handleFundDelete(index: number) {
    if (!config) return;
    const updated = config.funds.filter((_, i) => i !== index);
    saveConfig({ funds: updated });
  }

  function handleLevelsChange(levels: ThresholdLevel[]) {
    saveConfig({ levels });
  }

  async function handleCooldownBlur() {
    if (!config) return;
    const minutes = parseInt(cooldownInput, 10);
    if (isNaN(minutes) || minutes < 0) {
      setCooldownInput(String(config.cooldown_minutes));
      return;
    }
    if (minutes === config.cooldown_minutes) return;
    const ok = await saveConfig({ cooldown_minutes: minutes });
    if (!ok) {
      setCooldownInput(String(config.cooldown_minutes));
    }
  }

  function handleFcmToggle() {
    if (!config) return;
    saveConfig({ fcm_enabled: !config.fcm_enabled });
  }

  async function handleTestPush() {
    if (!testKey) {
      setTestResult("请先输入用于测试的 PushDeer Key");
      return;
    }
    setTestResult("发送中...");
    try {
      const resp = await fetch(
        `https://api2.pushdeer.com/message/push?pushkey=${encodeURIComponent(testKey)}&text=${encodeURIComponent("[测试] ETF Notify 推送测试成功！")}&type=text`
      );
      if (resp.ok) {
        setTestResult("测试推送已发送，请检查手机");
      } else {
        setTestResult("推送失败，请检查 Key 是否正确");
      }
    } catch {
      setTestResult("网络错误，请稍后重试");
    }
    setTimeout(() => setTestResult(null), 5000);
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen px-4">
        <div className="w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-slate-400 text-sm">正在加载...</p>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen px-4">
        <div className="text-center">
          {error === "connection_failed" ? (
            <>
              <div className="text-4xl mb-4">📡</div>
              <p className="text-slate-300 text-base mb-2">无法连接到数据库</p>
              <p className="text-slate-400 text-sm">
                请检查网络连接，或稍后重试
              </p>
              <button
                onClick={() => { setLoading(true); setError(null); loadConfig(); }}
                className="mt-4 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm rounded-lg transition-colors"
              >
                重试
              </button>
            </>
          ) : (
            <>
              <div className="text-4xl mb-4">⚙️</div>
              <p className="text-slate-300 text-base mb-2">配置未初始化</p>
              <p className="text-slate-400 text-sm">
                请等待 Worker 首次运行自动创建配置（工作日 10:00~14:30）
              </p>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-white">设置</h1>
        {saving ? (
          <span className="text-blue-400 text-xs">保存中...</span>
        ) : saveError ? (
          <span className="text-red-400 text-xs">{saveError}</span>
        ) : null}
      </div>

      {/* Fund Management */}
      <section className="mb-8">
        <h2 className="text-white font-medium text-base mb-3">基金管理</h2>
        <FundManager
          funds={config.funds}
          onToggle={handleFundToggle}
          onAdd={handleFundAdd}
          onDelete={handleFundDelete}
        />
      </section>

      {/* Threshold Settings */}
      <section className="mb-8">
        <h2 className="text-white font-medium text-base mb-3">门限设置</h2>
        <ThresholdConfig
          levels={config.levels}
          onSave={handleLevelsChange}
        />
      </section>

      {/* Cooldown */}
      <section className="mb-8">
        <h2 className="text-white font-medium text-base mb-3">冷却时间</h2>
        <div className="bg-slate-800/50 rounded-lg p-3 flex items-center justify-between">
          <span className="text-slate-300 text-sm">通知冷却时间</span>
          <div className="flex items-center gap-1">
            <input
              type="number"
              min="0"
              value={cooldownInput}
              onChange={(e) => setCooldownInput(e.target.value)}
              onBlur={handleCooldownBlur}
              className="w-20 bg-slate-700 text-white text-sm rounded px-2 py-1 text-right border border-slate-600 focus:border-blue-500 focus:outline-none"
            />
            <span className="text-slate-400 text-sm">分钟</span>
          </div>
        </div>
      </section>

      {/* Push Settings */}
      <section className="mb-8">
        <h2 className="text-white font-medium text-base mb-3">推送设置</h2>
        <div className="space-y-3">
          {/* FCM Toggle */}
          <div className="bg-slate-800/50 rounded-lg p-3 flex items-center justify-between">
            <span className="text-slate-300 text-sm">FCM 推送</span>
            <button
              onClick={handleFcmToggle}
              className={`w-10 h-6 rounded-full transition-colors relative ${
                config.fcm_enabled ? "bg-blue-500" : "bg-slate-600"
              }`}
            >
              <span
                className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                  config.fcm_enabled ? "left-[18px]" : "left-0.5"
                }`}
              />
            </button>
          </div>

          {/* Test Push */}
          <div className="bg-slate-800/50 rounded-lg p-3 space-y-2">
            <label className="text-slate-300 text-sm">测试推送</label>
            <input
              type="text"
              value={testKey}
              onChange={(e) => setTestKey(e.target.value)}
              placeholder="输入 PushDeer Key 用于测试"
              className="w-full bg-slate-700 text-white text-sm rounded px-3 py-2 border border-slate-600 focus:border-blue-500 focus:outline-none placeholder-slate-400"
            />
            <p className="text-slate-500 text-xs">
              推送 Key 保存在 GitHub Secrets 中，此处仅用于临时测试，不会被保存
            </p>
            <button
              onClick={handleTestPush}
              className="w-full bg-slate-700 hover:bg-slate-600 text-white text-sm rounded-lg py-3 transition-colors"
            >
              发送测试推送
            </button>
            {testResult && (
              <p className="text-center text-sm text-blue-400">{testResult}</p>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
