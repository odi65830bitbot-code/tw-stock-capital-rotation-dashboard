# Alpha v3 Backtest Report

本報告僅用於觀察模型驗證，不構成買賣建議。

## Backtest Summary
| model          |   top_n | status               |
|:---------------|--------:|:---------------------|
| Stock Alpha v3 |       5 | insufficient_history |
| Stock Alpha v3 |      10 | insufficient_history |
| Stock Alpha v3 |      20 | insufficient_history |

## Factor Effectiveness
| factor                      |   sample_size |   ic |   rank_ic |   top_decile_return |   bottom_decile_return |   top_minus_bottom | uses_future_data   |   effectiveness_score |
|:----------------------------|--------------:|-----:|----------:|--------------------:|-----------------------:|-------------------:|:-------------------|----------------------:|
| Trading_Volume              |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| Trading_money               |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| ma20                        |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| ma60                        |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| close_above_ma20            |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| close_above_ma60            |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| relative_strength_vs_taiex  |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| relative_strength_vs_sector |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| volatility_20d              |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| max_drawdown_60d            |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| trade_value_1d              |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| trade_value_ma20            |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| trade_value_ratio_20d       |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| turnover_proxy              |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| liquidity_score             |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| foreign_buy_1d              |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| foreign_buy_5d              |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| foreign_buy_20d             |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| investment_trust_buy_1d     |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
| investment_trust_buy_5d     |             0 |  nan |       nan |                 nan |                    nan |                nan | False              |                     0 |
