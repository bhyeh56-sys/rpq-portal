# RPQ Portal Deployment

## Domain Policy

`redpinequant.com` is the main RedPine Quant company website. It serves the company overview and selection screen:

- `https://redpinequant.com/`
- `https://redpinequant.com/risk`
- `https://redpinequant.com/faq`

`https://redpinequant.com/copy` is the Global Prime GP Copy information page.

`https://redpinequant.com/fund` serves the same participation review page used by the fund review domain.

`rpqtfund.com` is the independent RPQ Portal site. Its root page serves the role-based RPQ Portal home with investor portal, admin portal, Unit Price / NAV entry cards, and live MT5 snapshot status. Existing paths such as `/portal/login`, `/admin/investors`, `/admin/unit-price`, `/fx/mt5/snapshot`, and `/docs` must remain proxied to the FastAPI application.

`https://rpqtfund.com/fund` serves the investment association or fund-style participation review page.

`rpqfund.com` is not used.

## Nginx Overview

The `redpinequant.com` server block should terminate TLS and proxy requests to the RPQ Portal FastAPI service.

The `rpqtfund.com` and `www.rpqtfund.com` server blocks should also proxy all application paths to the same FastAPI service. The application uses the `Host` header to render `templates/rpq_portal_home.html` for the root path on:

- `rpqtfund.com`
- `www.rpqtfund.com`

Do not configure `rpqtfund.com` or `www.rpqtfund.com` as a redirect to `/copy`. Do not block `/portal`, `/admin`, `/fx`, or `/docs` at nginx. `/admin` may still be protected by nginx `auth_basic` and should pass the expected admin identity header to the application.

Keep admin, portal, database, and investor functionality separate from the public domain policy.

## Certbot Domains

The public certificates should cover:

- `redpinequant.com`
- `www.redpinequant.com` if the `www` hostname is enabled
- `rpqtfund.com`
- `www.rpqtfund.com`

Do not request certificates for unused domains.

## Smoke Test

Run the production smoke test from the repository root:

```bash
bash scripts/smoke_prod.sh
```

By default it checks:

- `GET https://redpinequant.com/` returns `200`
- `GET https://redpinequant.com/copy` returns `200`
- `GET https://redpinequant.com/risk` returns `200`
- `GET https://redpinequant.com/faq` returns `200`
- `GET https://redpinequant.com/fund` returns `200`
- `GET https://rpqtfund.com/` returns `200` and contains the RPQ Fund Live Snapshot home title
- `GET https://rpqtfund.com/portal/login` returns `200` and contains the investor login title
- `GET https://rpqtfund.com/admin/investors` returns `401` or `200`, depending on nginx auth state
- `GET https://www.rpqtfund.com/` returns `200`
- `GET https://rpqtfund.com/fund` returns `200` and contains the fund review title
- `rpqtfund.com` responses do not redirect to `https://redpinequant.com/copy`

Use `BASE_URL` only when checking a staging instance of the primary public site:

```bash
BASE_URL=https://staging.example.com bash scripts/smoke_prod.sh
```
