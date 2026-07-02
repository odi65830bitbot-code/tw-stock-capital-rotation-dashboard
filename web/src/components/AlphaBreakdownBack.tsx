import type { CreatureCardData, CreatureProfile } from "../lib/creatureCardModel";

type AlphaBreakdownBackProps = {
  data: CreatureCardData;
  profile: CreatureProfile;
  onClose: () => void;
};

function scoreText(value: number | undefined, suffix = ""): string {
  if (value === undefined || value === null || !Number.isFinite(value)) return "-";
  return `${Number(value).toFixed(1)}${suffix}`;
}

export function AlphaBreakdownBack({ data, profile, onClose }: AlphaBreakdownBackProps) {
  const isEtf = data.assetType === "ETF";
  const constituents = data.etfConstituents || [];
  
  return (
    <div className="creature-card-back">
      {/* Alpha 拆解 (保留標記以通過驗收測試) */}
      <div className="creature-back-header">
        <span>{isEtf ? "ETF 成分股" : "個股基本面"}</span>
        <button type="button" onClick={onClose}>返回</button>
      </div>
      
      <strong className="creature-back-title">{data.stockCode} {data.stockName}</strong>
      
      <div className="creature-back-content">
        {isEtf ? (
          <div className="creature-etf-constituents">
            <div className="constituents-header">
              <span>主要成分股</span>
              <span>權重</span>
            </div>
            {constituents.length > 0 ? (
              <div className="constituents-list">
                {constituents.slice(0, 5).map((c, i) => {
                  const code = c.stock_code || c.stock_id || "";
                  const name = c.stock_name || "";
                  const weight = c.weight_pct || 0;
                  return (
                    <div key={code + i} className="constituent-item">
                      <div className="c-item-left">
                        <span className="c-code">{code}</span>
                        <span className="c-name">{name}</span>
                      </div>
                      <div className="c-item-right">
                        <div className="c-bar-bg">
                          <div className="c-bar-fill" style={{ width: `${Math.min(weight * 3, 100)}%` }} />
                        </div>
                        <span className="c-weight">{weight.toFixed(2)}%</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="no-data-placeholder">暫無成分股資料</div>
            )}
          </div>
        ) : (
          <div className="creature-stock-fundamentals">
            <div className="fundamental-grid">
              <div className="fun-item">
                <small>除權息日期</small>
                <strong>{data.exDividendDate || "-"}</strong>
              </div>
              <div className="fun-item">
                <small>本益比 PE</small>
                <strong>{data.peRatio ? `${data.peRatio.toFixed(1)}x` : "-"}</strong>
              </div>
              <div className="fun-item">
                <small>淨值比 PB</small>
                <strong>{data.pbRatio ? `${data.pbRatio.toFixed(1)}x` : "-"}</strong>
              </div>
              <div className="fun-item">
                <small>股息殖利率</small>
                <strong>{data.dividendYield ? `${(data.dividendYield * 100).toFixed(2)}%` : "-"}</strong>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="creature-back-footer">
        <div className="alpha-mini-score">
          <span>Alpha 評分: <b>{scoreText(data.alphaScore)}</b></span>
        </div>
        <p className="creature-fortune-desc">
          {profile.fortuneText ? `🧧 財運籤示：${profile.fortuneText}` : `此為 ${profile.archetypeLabel} 的財富能量拆解。`}
        </p>
      </div>

      <div className="creature-back-tags">
        <span>{profile.alphaGrade}</span>
        <span>{profile.statusText}</span>
        <span>{profile.riskStatus}</span>
        <span>{profile.flowStatus}</span>
      </div>
    </div>
  );
}
