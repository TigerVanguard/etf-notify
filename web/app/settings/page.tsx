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
  const [testResult, setTestResult] = useState<string | null>(null);
  const [pushDeerKey, setPushDeerKey] = useState("");
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    loadConfig();
  }, []);

  async function loadConfig() {
    try {
      const cfg = await getConfig();
      setConfig(cfg);
      setPushDeerKey(cfg?.pushdeer_key ?? "");
    } catch (err) {
      console.error("Failed to load config:", err);
    } finally {
      setLoading(false);
    }
  }

  const saveConfig = useCallback(
    async (partial: Partial<AppConfig>) => {
      setSaving(true);
      try {
        await updateConfig(partial);
        setConfig((prev) => (prev ? { ...prev, ...partial } : prev));
      } catch (err) {
        console.error("Failed to save config:", err);
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

  function handleCooldownChange(minutes: number) {
    if (minutes < 0) return;
    saveConfig({ cooldown_minutes: minutes });
  }

  function handlePushDeerKeySave() {
    saveConfig({ pushdeer_key: pushDeerKey });
  }

  function handleFcmToggle() {
    if (!config) return;
    saveConfig({ fcm_enabled: !config.fcm_enabled });
  }

  async function handleTestPush() {
    if (!pushDeerKey) {
      setTestResult("请先输入 PushDeer Key");
      return;
    }
    setTestResult("发送中...");
    try {
      const resp = await fetch(
        `https://api2.pushdeer.com/message/push?pushkey=${encodeURIComponent(pushDeerKey)}&text=${encodeURIComponent("[测试] ETF Notify 推送测试成功！")}&type=text`
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
          <div className="text-4xl mb-4">⚙️</div>
          <p className="text-slate-300 text-base mb-2">配置未初始化</p>
          <p className="text-slate-400 text-sm">
            请先通过 Worker 初始化 Firestore 配置
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-white">设置</h1>
        {saving && (
          <span className="text-blue-400 text-xs">保存中...</span>
        )}
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
              value={config.cooldown_minutes}
              onChange={(e) =>
                handleCooldownChange(parseInt(e.target.value) || 0)
              }
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
          {/* PushDeer Key */}
          <div className="bg-slate-800/50 rounded-lg p-3 space-y-2">
            <label className="text-slate-300 text-sm">PushDeer Key</label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <input
                  type={showKey ? "text" : "password"}
                  value={pushDeerKey}
                  onChange={(e) => setPushDeerKey(e.target.value)}
                  onBlur={handlePushDeerKeySave}
                  placeholder="PDU..."
                  className="w-full bg-slate-700 text-white text-sm rounded px-3 py-2 border border-slate-600 focus:border-blue-500 focus:outline-none placeholder-slate-400 pr-10"
                />
                <button
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-300"
                >
                  {showKey ? (
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
                      />
                    </svg>
                  ) : (
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                      />
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                      />
                    </svg>
                  )}
                </button>
              </div>
            </div>
          </div>

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
      </section>
    </div>
  );
}
