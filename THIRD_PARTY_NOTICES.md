# OpenStock integration attribution

This project includes modified OpenStock components by **Open Dev Society**:

- Upstream: https://github.com/Open-Dev-Society/OpenStock
- Pinned upstream commit: `05cf71bc8a97131f5718bd6b810bd68d5293de32` (2026-08-21).
- Original files: `components/TradingViewWidget.tsx`, `hooks/useTradingViewWidget.tsx`.
- Local derivatives: `web/src/integrations/openstock/TradingViewWidget.tsx` and `useTradingViewWidget.ts`.
- Modifications (2026-09-18): port from Next.js/shadcn to existing React/Vite app; replace expand overlay with native chart controls; add allowlisted scripts, scoped cleanup, iframe detection, load errors and timeouts; integrate official-pipeline Taiwan lookup and existing local watchlist.
- License: **GNU Affero General Public License version 3**, full unmodified text in `public/licenses/OpenStock-AGPL-3.0.txt`.

The new OpenStock integration directory is provided under AGPL-3.0-only. Existing third-party dependencies retain their respective licenses. This notice does not purport to unilaterally relicense unrelated pre-existing files. Distribution or network deployment of the combined derivative must comply with upstream AGPL requirements, including provision of Corresponding Source; this directory boundary is not an exemption. The integration footer provides a visible source link and license text. Retain attribution and ensure that the source link points to the exact version deployed (update it for forks or later releases).

No OpenStock logos, screenshots, user accounts, email credentials or private databases were copied. TradingView scripts and market data are third-party services, not bundled OpenStock source or a promise of real-time data availability. Provider terms and exchange coverage continue to apply.
