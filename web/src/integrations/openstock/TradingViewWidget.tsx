// SPDX-License-Identifier: AGPL-3.0-only
// Adapted from Open Dev Society / OpenStock components/TradingViewWidget.tsx.
// Vite/CSS port; uses native chart controls instead of the upstream expand overlay.
import { memo } from "react";
import useTradingViewWidget from "./useTradingViewWidget";
import { WIDGET_SCRIPTS, widgetConfig, type WidgetKind } from "./model";

function TradingViewWidget({ symbol, kind, onRetry }: {
  symbol: string; kind: WidgetKind; onRetry: () => void;
}) {
  const { containerRef, status } = useTradingViewWidget(WIDGET_SCRIPTS[kind], widgetConfig(symbol, kind));
  return <div className="os-widget">
    <p className="os-caption" role="status">
      {status === "loading" ? "正在連接 TradingView…" : status === "unavailable"
        ? "外部圖表未能載入，仍可查看下方既有走勢或開啟 TradingView。"
        : "圖表框架已載入；行情與財務資料的可用性依 TradingView 顯示為準。"}
    </p>
    {status === "unavailable" && <button type="button" onClick={onRetry}>重新載入圖表</button>}
    <div className="tradingview-widget-container os-widget-frame" ref={containerRef} />
    <a className="os-caption" href={`https://www.tradingview.com/chart/?symbol=${encodeURIComponent(symbol)}`}
      target="_blank" rel="noopener noreferrer">在 TradingView 查看 {symbol} ↗</a>
  </div>;
}

export default memo(TradingViewWidget);
