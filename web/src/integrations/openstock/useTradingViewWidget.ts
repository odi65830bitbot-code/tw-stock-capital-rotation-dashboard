// SPDX-License-Identifier: AGPL-3.0-only
// Adapted from Open Dev Society / OpenStock hooks/useTradingViewWidget.tsx.
// Modifications: allowlisted URLs, safe DOM construction, timeout/error state,
// iframe detection and instance-scoped cleanup. See THIRD_PARTY_NOTICES.md.
import { useEffect, useRef, useState } from "react";
import { WIDGET_SCRIPTS } from "./model";

export default function useTradingViewWidget(scriptUrl: string, config: Record<string, unknown>) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "embedded" | "unavailable">("loading");
  const configJSON = JSON.stringify(config);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    setStatus("loading");
    if (!Object.values(WIDGET_SCRIPTS).includes(scriptUrl)) {
      setStatus("unavailable");
      return;
    }
    const instance = document.createElement("div");
    instance.style.height = "100%";
    const widget = document.createElement("div");
    widget.className = "tradingview-widget-container__widget";
    widget.style.cssText = "width:100%;height:100%";
    instance.appendChild(widget);
    container.appendChild(instance);

    const script = document.createElement("script");
    script.src = scriptUrl;
    script.async = true;
    script.textContent = configJSON;
    script.onerror = () => setStatus("unavailable");
    const timer = window.setTimeout(() => setStatus("unavailable"), 12000);
    const observer = new MutationObserver(() => {
      const frame = instance.querySelector("iframe");
      if (frame) {
        frame.title = "TradingView 外部市場資料";
        window.clearTimeout(timer);
        // An iframe being present does NOT prove quote availability inside it.
        setStatus("embedded");
      }
    });
    observer.observe(instance, { childList: true, subtree: true });
    instance.appendChild(script);
    return () => {
      script.onerror = null;
      window.clearTimeout(timer);
      observer.disconnect();
      instance.remove();
    };
  }, [scriptUrl, configJSON]);

  return { containerRef, status };
}
